#!/usr/bin/env python3
"""Walking-route cache.

Fetches pedestrian routes from each venue's transit hubs and from the closest
neighbourhoods, so the map can draw where people actually walk instead of a dot
at a district centroid. Results are cached in registry/routes.json: reruns only
fetch what is missing, and the site never calls a router at runtime.

Source: FOSSGIS OSRM foot instance (OpenStreetMap data, ODbL).
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "registry", "routes.json")
ENDPOINT = "https://routing.openstreetmap.de/routed-foot/route/v1/driving"
CAR_ENDPOINT = "https://routing.openstreetmap.de/routed-car/route/v1/driving"
MAX_ZONES = 40         # every district within reach, so the whole journey shows
HUB_LIMIT = 2          # transit hubs per venue
SLEEP = 0.12


def hav_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(doc):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def decimate(coords, target):
    """Keep the shape, drop points: full OSRM geometry is far denser than a canvas needs."""
    if len(coords) <= target:
        return coords
    step = len(coords) / float(target - 1)
    out = [coords[int(round(i * step))] for i in range(target - 1)]
    out.append(coords[-1])
    return out


def fetch(a, b, tries=3, profile="foot"):
    """Route a -> b by profile (foot or car), returned as [[lat, lon], ...] or None."""
    ep = CAR_ENDPOINT if profile == "car" else ENDPOINT
    url = (f"{ep}/{a[1]:.6f},{a[0]:.6f};{b[1]:.6f},{b[0]:.6f}"
           "?overview=full&geometries=geojson&steps=false")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "kilinkolin/0.4 (github.com/zakker111/kilinkolin)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.load(resp)
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                coords = [[round(p[1], 5), round(p[0], 5)] for p in r["geometry"]["coordinates"]]
                coords = decimate(coords, 70)
                if len(coords) >= 2:
                    return {"km": round(r["distance"] / 1000, 2), "min": round(r["duration"] / 60),
                            "walk": True, "geometry": coords}
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            time.sleep(1.2 * (attempt + 1))
    return None


def wanted(venues, zones, hubs):
    """Legs to cache, keyed exactly as build.py expects."""
    legs = {}
    for v in venues:
        here = (v["lat"], v["lon"])
        for hid in (v.get("hubs") or [])[:HUB_LIMIT]:
            h = hubs.get(hid)
            if not h:
                continue
            legs[f"{v['id']}|hub:{hid}"] = (
                (h["lat"], h["lon"]), here, f"{v['name']} ← {h['name']}")
            # transit corridor: buses/trams follow the road network, so use the car profile
            legs[f"{v['id']}|hub:{hid}:drive"] = (
                (h["lat"], h["lon"]), here, f"{v['name']} ← {h['name']} (transit)")
        near = sorted(zones, key=lambda z: hav_km((z["lat"], z["lon"]), here))[:MAX_ZONES]
        for z in near:
            km = hav_km((z["lat"], z["lon"]), here)
            # up to 9 km: beyond a literal walk this is the road/street corridor people travel along
            if km < 0.35 or km > 9.0:
                continue
            legs[f"{v['id']}|zone:{z['id']}"] = (
                (z["lat"], z["lon"]), here, f"{v['name']} ← {z['name']}")
    return legs


def wanted_from_flows(venues, zones, hubs):
    """Only the legs the current build actually draws: what a weekly refresh needs."""
    path = os.path.join(ROOT, "web", "geo", "flows.json")
    if not os.path.exists(path):
        return {}
    vy = {v["id"]: v for v in venues}
    zy = {z["id"]: z for z in zones}
    legs = {}
    for flow in load(path).get("events", []):
        v = vy.get(flow.get("venue_id"))
        if not v:
            continue
        here = (v["lat"], v["lon"])
        for leg in flow.get("legs", []):
            key = leg.get("key")
            if not key or key in legs:
                continue
            if "|zone:" in key:
                z = zy.get(key.split("|zone:")[1])
                if z:
                    legs[key] = ((z["lat"], z["lon"]), here, leg.get("name", key))
            elif "|hub:" in key:
                hid = key.split("|hub:")[1].split(":")[0]
                h = hubs.get(hid)
                if h:
                    legs[key] = ((h["lat"], h["lon"]), here, leg.get("name", key))
    return legs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and refetch everything")
    ap.add_argument("--from-flow", action="store_true", help="only legs referenced by web/geo/flows.json")
    ap.add_argument("--max", type=int, default=500, help="stop after this many network fetches")
    args = ap.parse_args()

    venues_doc = load(os.path.join(ROOT, "registry", "venues.json"))
    zones_doc = load(os.path.join(ROOT, "registry", "zones.json"))
    venues, zones, hubs = venues_doc["venues"], zones_doc["zones"], venues_doc["transit_hubs"]

    # Calendar events put a venue in web/geo/venues.json that the registry does not list yet
    # (a library hall, a school auditorium). They carry their own published coordinates, so
    # their legs can be routed like any other venue instead of falling back to straight lines.
    generated = os.path.join(ROOT, "web", "geo", "venues.json")
    if os.path.exists(generated):
        known = {v["id"] for v in venues}
        for v in load(generated).get("venues", []):
            if v["id"] not in known and v.get("lat") and v.get("lon"):
                venues.append(v)

    doc = {"schema_version": 1, "source": "FOSSGIS OSRM foot (OpenStreetMap, ODbL)"}
    if os.path.exists(CACHE) and not args.refresh:
        doc = load(CACHE)
    routes = doc.setdefault("routes", {})

    legs = wanted_from_flows(venues, zones, hubs) if args.from_flow else wanted(venues, zones, hubs)
    todo = [k for k in legs if k not in routes]
    print(f"{len(legs)} legs needed, {len(todo)} to fetch, {len(routes)} already cached")

    fetched = failed = 0
    for i, key in enumerate(todo, 1):
        if fetched >= args.max:
            print("hit --max, stopping")
            break
        a, b, label = legs[key]
        profile = "car" if key.endswith(":drive") else "foot"
        res = fetch(a, b, profile=profile)
        fetched += 1
        if res:
            routes[key] = res
            routes[key]["profile"] = profile
        else:
            failed += 1
            print(f"  FAILED {label}")
        if i % 20 == 0:
            save(doc)
            print(f"  {i}/{len(todo)} ({failed} failed)")
        time.sleep(SLEEP)

    doc["generated"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    save(doc)
    total_km = sum(r["km"] for r in routes.values())
    print(f"saved {len(routes)} routes ({total_km:.0f} km of walking legs), {failed} failures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
