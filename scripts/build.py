#!/usr/bin/env python3
"""Kilinkolin build pipeline.

sync  -> fetch feeds, normalise events, write web/data.json
full  -> sync + attendance, interest, gravity split, corridors, curves

Everything is estimated: no measured attendance, no tracking.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import urllib.request
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
GEO = os.path.join(WEB, "geo")

KEIKAT_URL = "https://zakker111.github.io/tampere-keikat/data.json"
MODEL_VERSION = "2026.11.2"
SCHEMA_VERSION = 2

# ---------------------------------------------------------------- taxonomy
GROUPS = {
    "gigs": ["rock", "metal", "punk", "pop", "jazz", "electronic", "hiphop", "folk", "classical", "karaoke", "other"],
    "sports": ["hockey", "football", "basketball", "pesapallo", "floorball", "other"],
    "student": ["party", "sitsit", "sauna", "sports", "culture"],
    "stage": ["theatre", "dance", "comedy"],
    "culture": ["literature", "film", "exhibition"],
    "community": ["workshop", "lecture", "fair", "food", "family", "participation"],
    "other": ["other"],
}

MUSIC_GENRES = {"rock", "metal", "punk", "pop", "jazz", "electronic", "hiphop", "folk",
                "classical", "festival", "indie", "country", "blues", "alternative",
                "reggae", "ambient"}

FILL = {
    # gigs
    "rock": 0.55, "metal": 0.50, "punk": 0.55, "pop": 0.70, "jazz": 0.60,
    "electronic": 0.60, "hiphop": 0.60, "folk": 0.50, "classical": 0.75,
    "karaoke": 0.50, "other": 0.50,
    # sports
    "hockey": 0.85, "football": 0.60, "basketball": 0.55, "pesapallo": 0.60, "floorball": 0.50,
    # student
    "party": 0.80, "sitsit": 0.90, "sauna": 0.50, "sports_student": 0.60, "culture_student": 0.55,
    # stage
    "theatre": 0.65, "dance": 0.60, "comedy": 0.70,
    # culture
    "literature": 0.40, "film": 0.50, "exhibition": 0.30,
    # community
    "workshop": 0.50, "lecture": 0.45, "fair": 0.40, "food": 0.50, "family": 0.50, "participation": 0.40,
}

CATEGORY_FALLBACK_FILL = {"gigs": 0.55, "sports": 0.60, "student": 0.75, "stage": 0.65,
                          "culture": 0.40, "community": 0.45, "other": 0.45}

ARRIVAL = {
    "A": [(-120, .02), (-90, .08), (-60, .22), (-45, .28), (-30, .24), (-15, .12), (0, .04)],
    "B": [(-120, .01), (-90, .03), (-60, .12), (-45, .24), (-30, .30), (-15, .20), (0, .08), (15, .02)],
    "C": [(-120, .03), (-90, .07), (-60, .18), (-45, .26), (-30, .24), (-15, .14), (0, .05), (15, .03)],
    "S": [(-120, .01), (-90, .02), (-60, .08), (-45, .18), (-30, .26), (-15, .27), (0, .14), (15, .04)],
}
EGRESS = [(0, .30), (10, .30), (20, .18), (30, .12), (45, .10)]

# approximate event length: the feed has no end time, so the way out starts after a typical run
DURATION_MIN = {"gigs": 150, "sports": 150, "student": 300, "stage": 150,
                "culture": 120, "community": 120, "other": 120}
DURATION_SUB = {"karaoke": 180, "party": 300, "sitsit": 300, "film": 120,
                "exhibition": 180, "comedy": 120, "dance": 120}


def log(*a):
    print(*a, file=sys.stderr)


def clock_minutes(s):
    """Same convention as the page: 02:00–05:59 belongs to the previous night."""
    try:
        h, m = (int(x) for x in (s or "19:00").split(":"))
    except (TypeError, ValueError):
        return 19 * 60
    v = h * 60 + m
    return v + 24 * 60 if v < 6 * 60 else v


def hav_km(a, b):
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_keikat():
    dest = os.path.join(ROOT, "data", "keikat.json")
    try:
        req = urllib.request.Request(KEIKAT_URL, headers={"User-Agent": "kilinkolin/0.1 (+https://github.com/zakker111)"})
        with urllib.request.urlopen(req, timeout=25) as r:
            payload = r.read().decode("utf-8")
        data = json.loads(payload)
        if not data.get("events"):
            raise ValueError("feed has no events")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(payload)
        log(f"[music] fetched {len(data['events'])} events, generated {data.get('generated')}")
        return data, "OK"
    except Exception as exc:  # noqa: BLE001 - feed failure must not kill the build
        log(f"[music] fetch failed: {exc}")
        if os.path.exists(dest):
            log("[music] using cached copy")
            return load_json(dest), "CACHED"
        return {"events": [], "generated": None}, "FAILED"


# ------------------------------------------------------------- normalising
def build_alias_index(venues):
    idx = {}
    for v in venues:
        for key in [v["name"]] + v.get("aliases", []):
            idx[key.strip().lower()] = v["id"]
    return idx


def resolve_venue(raw, alias_idx, venues):
    if not raw:
        return None
    low = raw.strip().lower()
    if low in alias_idx:
        return next(v for v in venues if v["id"] == alias_idx[low])
    # strip address suffix: "Pääkirjasto Metso, Pirkankatu 2, 33210 Tampere"
    head = low.split(",")[0].strip()
    if head in alias_idx:
        return next(v for v in venues if v["id"] == alias_idx[head])
    for key, vid in alias_idx.items():
        if len(key) > 4 and key in low:
            return next(v for v in venues if v["id"] == vid)
    return None


KIND_ALIASES = {
    "sport": "sports", "music_gig": "gigs", "gig": "gigs",
    "theatre": "stage", "comedy": "stage", "dance": "stage",
    "literature": "culture", "film": "culture", "exhibition": "culture",
    "market": "community", "workshop": "community", "lecture": "community",
    "family": "community", "food": "community", "participation": "community",
}
SUBS_BY_KIND = {
    "culture": {"literature", "film", "exhibition"},
    "community": {"fair", "workshop", "lecture", "family", "food", "participation"},
    "stage": {"theatre", "dance", "comedy"},
    "sports": {"hockey", "football", "basketball", "pesapallo", "floorball", "other"},
    "student": {"party", "sitsit", "sauna", "sports", "culture"},
}


def classify(kind, sub, legacy_genre, title):
    """Return (category, subcategory)."""
    title_l = (title or "").lower()
    raw_kind = (kind or "").lower()
    kind = KIND_ALIASES.get(raw_kind, raw_kind)
    if kind in ("culture", "community", "stage", "sports", "student"):
        s = (sub or "other").lower()
        if kind == "stage" and s in ("play", "musical"):
            s = "theatre"
        if s not in GROUPS[kind] and raw_kind in GROUPS[kind]:
            s = raw_kind  # kind "literature"/"film" doubles as the subcategory
        if s not in GROUPS[kind]:
            s = "other"
        return kind, s
    if kind == "music":
        g = (legacy_genre or "other").lower()
        if g not in GROUPS["gigs"]:
            g = "other"
        return "gigs", g

    # keyword fallback
    if any(k in title_l for k in ("sitsit", "appro", "opiskelij", "fuksiais", "wappu")):
        return "student", "party"
    if any(k in title_l for k in ("ottelu", "liiga", "korisliiga", "superpesis", "jalkapallo")):
        return "sports", "other"
    return "other", "other"


def crowd_class(cap, category, sub):
    if category == "student":
        return "S"
    if cap >= 5000:
        return "A"
    if cap >= 500:
        return "B"
    return "C"


def interest_score(ev, cap, category, sub, venue):
    signals = []
    score = 38.0
    if cap >= 12000:
        score += 14; signals.append(("arena scale", 14))
    elif cap >= 4000:
        score += 8; signals.append(("large venue", 8))
    elif cap <= 120:
        score -= 8; signals.append(("small venue", -8))
    try:
        dow = dt.date.fromisoformat(ev["date"]).weekday()
        if dow in (4, 5):
            score += 10; signals.append(("weekend evening", 10))
        elif dow == 6:
            score += 4; signals.append(("sunday", 4))
    except ValueError:
        pass
    hour = ev.get("hour")
    if hour is not None:
        if 18 <= hour <= 22:
            score += 7; signals.append(("prime start time", 7))
        elif hour < 15:
            score -= 5; signals.append(("daytime start", -5))
    if ev.get("free"):
        score += 3; signals.append(("free entry", 3))
    title_l = (ev.get("title") or "").lower()
    for kw, pts, label in (
        ("loppuunmyyty", 18, "sold out"), ("sold out", 18, "sold out"),
        ("ensi-ilta", 7, "premiere"), ("finaali", 9, "final"),
        ("paikallis", 10, "local derby"), ("joulu", 5, "seasonal"),
        ("festivaali", 6, "festival"), ("klubi", 2, "club night"),
    ):
        if kw in title_l:
            score += pts; signals.append((label, pts))
    if category == "sports" and sub == "hockey":
        score += 6; signals.append(("liiga hockey", 6))
    if category == "student":
        score -= 4; signals.append(("student event", -4))
    score = max(5, min(98, score))
    band = "high" if score >= 70 else "medium" if score >= 45 else "low"
    return {"score": round(score), "band": band, "signals": [{"name": n, "points": p} for n, p in signals]}


def attendance_est(cap, category, sub, interest, ev):
    fill = FILL.get(sub, CATEGORY_FALLBACK_FILL.get(category, 0.45))
    if ev.get("seed") and category == "sports" and sub == "hockey":
        fill = 0.92
    mid = cap * fill * (0.72 + 0.45 * interest["score"] / 100.0)
    mid = min(mid, cap * 1.0)
    spread = 0.35 if cap < 500 else 0.22
    return {"low": int(mid * (1 - spread)), "mid": int(mid), "high": int(min(cap, mid * (1 + spread)))}


MODE_BY_KM = [
    (2.0, {"walk": .55, "bike": .10, "tram": .25, "car": .10}),
    (6.0, {"tram": .34, "bus": .16, "walk": .12, "bike": .08, "car": .25, "rail": .05}),
    (15.0, {"bus": .30, "tram": .15, "car": .35, "rail": .12, "bike": .05, "walk": .03}),
    (40.0, {"rail": .40, "car": .40, "bus": .15, "walk": .02, "bike": .03}),
    (1e9, {"rail": .65, "car": .30, "bus": .05}),
]


CLASS_MODE_ADJUST = {
    "A": {"walk": 0.55, "bike": 0.8, "tram": 1.2, "bus": 1.2, "rail": 1.35, "car": 1.0},
    "B": {"walk": 0.8, "bike": 0.9, "tram": 1.1, "bus": 1.1, "rail": 1.1, "car": 1.0},
    "S": {"walk": 1.1, "bike": 1.0, "tram": 1.1, "bus": 1.0, "rail": 0.9, "car": 0.7},
    "C": {"walk": 1.35, "bike": 1.1, "tram": 0.9, "bus": 0.9, "rail": 0.7, "car": 0.8},
}


def modes_for(km, rail):
    for limit, split in MODE_BY_KM:
        if km <= limit:
            s = dict(split)
            if not rail:
                moved = s.pop("rail", 0)
                s["car"] = s.get("car", 0) + moved
            if km < 0.6:
                s = {"walk": .75, "bike": .12, "tram": .08, "car": .05}
            total = sum(s.values())
            return {k: v / total for k, v in s.items()}
    return {"car": 1.0}


def gravity(ev, venue, zones):
    cap = max(venue["capacity"].get("gig", 0), venue["capacity"].get("sport", 0), 20)
    cls = crowd_class(cap, ev["category"], ev["sub"])
    max_km = {"A": 400.0, "B": 60.0, "S": 40.0, "C": 8.0}[cls]
    rows = []
    for z in zones:
        km = hav_km((z["lat"], z["lon"]), (venue["lat"], venue["lon"])) * 1.3
        if km > max_km:
            continue
        student_w = z["student"] if ev["category"] == "student" else 1 + (z["student"] - 1) * 0.35
        profile = (0.55 + 0.45 * z.get("transit", .8)) * student_w
        if z.get("long_distance"):
            profile *= 2.2 if cls == "A" else 0.5
        time_h = max(0.15, km / (18 if km > 6 else 7))
        weight = z["pop"] * profile / (time_h ** 1.6)
        rows.append((z, km, weight))
    total = sum(w for _, _, w in rows) or 1.0
    out = []
    for z, km, w in rows:
        share = w / total
        if share < 0.004:
            continue
        out.append({"zone_id": z["id"], "name": z["name"], "share": round(share, 4),
                    "km": round(km, 1), "modes": modes_for(km, z.get("rail", False))})
    out.sort(key=lambda r: -r["share"])
    return cls, out


def corridors_for(venue, zone_rows, hub_map, attendance_mid, limit=6):
    out = []
    for row in zone_rows[:limit]:
        z = next(zz for zz in ZONES if zz["id"] == row["zone_id"])
        hub = hub_map.get(venue["hubs"][0]) if venue.get("hubs") else None
        if hub and row["km"] > 1.2:
            geom = [[z["lat"], z["lon"]], [hub["lat"], hub["lon"]], [venue["lat"], venue["lon"]]]
        else:
            geom = [[z["lat"], z["lon"]], [venue["lat"], venue["lon"]]]
        mode = max(row["modes"].items(), key=lambda kv: kv[1])[0]
        out.append({
            "zone_id": row["zone_id"],
            "name": row["name"],
            "mode": mode,
            "share": row["share"],
            "people": round(attendance_mid * row["share"]),
            "geometry": geom,
        })
    return out


def legs_for(venue, zone_rows, routes, hub_names, hub_kinds, attendance_mid):
    """Walking legs along real streets: transit hub -> venue, or nearest district -> venue."""
    if not routes:
        return []
    hub_id = (venue.get("hubs") or [None])[0]
    agg = {}
    for row in zone_rows:
        key = None
        label = row["name"]
        km = row["km"]
        hub_key = f"{venue['id']}|hub:{hub_id}" if hub_id else None
        drive_key = f"{venue['id']}|hub:{hub_id}:drive" if hub_id else None
        zone_key = f"{venue['id']}|zone:{row['zone_id']}"
        if km <= 3.0 and zone_key in routes:
            # close districts: people walk the whole way
            key = zone_key
        elif km > 3.0 and drive_key in routes:
            # far districts: walk to the stop, then tram/bus/train along the road corridor
            key, label = drive_key, hub_names.get(hub_id, row["name"])
        elif zone_key in routes:
            key = zone_key
        elif hub_key in routes:
            key, label = hub_key, hubs[:0] and None or hub_names.get(hub_id, row["name"])
        if key is None:
            continue
        rec = agg.setdefault(key, {"share": 0.0, "modes": defaultdict(float), "name": label,
                                   "km": routes[key]["km"], "min": routes[key]["min"]})
        rec["share"] += row["share"]
        for m, s in row["modes"].items():
            rec["modes"][m] += row["share"] * s
    legs = []
    for key, rec in agg.items():
        modes = dict(rec["modes"])
        if "|hub:" in key:
            # a hub leg is the last walk; colour it by the transit mode that fed the hub
            transit = {m: v for m, v in modes.items() if m in ("rail", "tram", "bus")}
            if transit:
                modes = transit
        mode = max(modes.items(), key=lambda kv: kv[1])[0] if modes else "walk"
        if "|hub:" in key:
            hub_id_key = key.split("|hub:")[-1].split(":")[0]
            mode = hub_kinds.get(hub_id_key, mode)  # tram stop -> tram, rail station -> rail
            if key.endswith(":drive"):
                # transit corridor keeps the station's mode
                mode = hub_kinds.get(hub_id_key, mode)
        legs.append({"key": key, "name": rec["name"], "share": round(rec["share"], 4),
                     "people": round(attendance_mid * rec["share"]), "mode": mode,
                     "km": rec["km"], "min": rec["min"]})
    legs.sort(key=lambda r: -r["share"])
    return legs


def summarise_modes(zone_rows, cls="B"):
    adjust = CLASS_MODE_ADJUST.get(cls, {})
    agg = defaultdict(float)
    for r in zone_rows:
        for m, s in r["modes"].items():
            agg[m] += r["share"] * s * adjust.get(m, 1.0)
    total = sum(agg.values()) or 1
    return [{"mode": m, "share": round(v / total, 3)} for m, v in sorted(agg.items(), key=lambda kv: -kv[1])]


# ------------------------------------------------------------------- build
ZONES = []
VENUES = []


def build(mode="full"):
    global ZONES, VENUES
    os.makedirs(GEO, exist_ok=True)
    venues_doc = load_json(os.path.join(ROOT, "registry", "venues.json"))
    zones_doc = load_json(os.path.join(ROOT, "registry", "zones.json"))
    VENUES = venues_doc["venues"]
    ZONES = zones_doc["zones"]
    hubs = venues_doc["transit_hubs"]
    alias_idx = build_alias_index(VENUES)

    routes_path = os.path.join(ROOT, "registry", "routes.json")
    routes_doc = load_json(routes_path) if os.path.exists(routes_path) else {"routes": {}}
    ROUTES = routes_doc.get("routes", {})
    HUB_NAMES = {k: v["name"] for k, v in hubs.items()}
    HUB_KINDS = {k: v.get("kind", "bus") for k, v in hubs.items()}
    log(f"[routes] {len(ROUTES)} walking legs cached")

    feed, music_status = fetch_keikat()
    seed = load_json(os.path.join(ROOT, "data", "seed_events.json"))
    status = {"music": music_status, "seed": "OK"}

    events = []
    unmatched = Counter()

    for row in feed.get("events", []):
        if len(row) < 7:
            continue
        date, time_s, title, venue_raw, genre, free, url = row[:7]
        venue = resolve_venue(venue_raw, alias_idx, VENUES)
        if not venue:
            unmatched[venue_raw] += 1
            venue = next(v for v in VENUES if v["id"] == "tampere_muu")
        hour = None
        if time_s and ":" in time_s:
            try:
                hour = int(time_s.split(":")[0])
            except ValueError:
                hour = None
        category, sub = classify("music", None, genre, title)
        events.append({
            "date": date, "time": time_s or "", "title": title, "venue_raw": venue_raw,
            "venue": venue, "free": bool(free), "url": url, "hour": hour,
            "legacy_genre": (genre or "other"), "category": category, "sub": sub,
            "kind": "music", "seed": False,
        })

    for row in seed.get("events", []):
        date, time_s, title, venue_raw, genre, free, url, kind, sub, is_seed = row[:10]
        venue = resolve_venue(venue_raw, alias_idx, VENUES) or next(v for v in VENUES if v["id"] == "tampere_muu")
        hour = int(time_s.split(":")[0]) if time_s and ":" in time_s else None
        category, sub2 = classify(kind, sub, None, title)
        events.append({
            "date": date, "time": time_s, "title": title, "venue_raw": venue_raw,
            "venue": venue, "free": bool(free), "url": url, "hour": hour,
            "legacy_genre": genre if genre in MUSIC_GENRES else sub2,
            "category": category, "sub": sub2, "kind": kind, "seed": bool(is_seed),
        })

    if unmatched:
        log(f"[venues] unresolved strings mapped to fallback: {dict(unmatched)}")

    today = dt.date.today().isoformat()
    events = [e for e in events if e["date"] >= today]
    events.sort(key=lambda e: (e["date"], e["time"] or "99:99"))

    rows, flows, ev_geo = [], [], []
    by_cat = Counter()
    by_area = Counter()

    for i, e in enumerate(events):
        venue = e["venue"]
        cap = max(venue["capacity"].get("gig", 0), venue["capacity"].get("sport", 0), 20)
        interest = interest_score(e, cap, e["category"], e["sub"], venue)
        att = attendance_est(cap, e["category"], e["sub"], interest, e)
        cls, zone_rows = gravity(e, venue, ZONES)
        legs = legs_for(venue, zone_rows, ROUTES, HUB_NAMES, HUB_KINDS, att["mid"])
        corridors = [] if legs else corridors_for(venue, zone_rows, hubs, att["mid"])
        modes = summarise_modes(zone_rows, cls)
        eid = f"e{i:04d}"
        by_cat[e["category"]] += 1
        by_area[venue["area"]] += 1

        start_min = clock_minutes(e["time"])
        duration = DURATION_SUB.get(e["sub"], DURATION_MIN.get(e["category"], 120))
        end_min = start_min + duration
        egress = []
        for idx, (t, s) in enumerate(EGRESS):
            nxt = EGRESS[idx + 1][0] if idx + 1 < len(EGRESS) else t + 15
            egress.append({"t": t, "share": s, "span": max(5, nxt - t)})

        display_venue = venue["name"] if venue["id"] != "tampere_muu" else (e["venue_raw"] or venue["name"])
        rows.append([
            e["date"], e["time"], e["title"], display_venue,
            e["legacy_genre"], 1 if e["free"] else 0, e["url"],
            eid, e["kind"], e["category"], e["sub"],
            interest["score"], att["mid"], 1 if e["seed"] else 0, venue["id"],
        ])
        flows.append({
            "id": eid, "venue_id": venue["id"], "class": cls,
            "attendance": att, "interest": interest,
            "zones": zone_rows[:8],
            "rest_share": round(max(0.0, 1 - sum(z["share"] for z in zone_rows[:8])), 4),
            "modes": modes, "legs": legs, "corridors": corridors,
            "start": start_min, "end": end_min,
            "arrival": [{"t": t, "share": s} for t, s in ARRIVAL[cls]],
            "egress": egress,
        })
        ev_geo.append({"id": eid, "venue_id": venue["id"], "lat": venue["lat"], "lon": venue["lon"],
                       "date": e["date"], "attendance": att["mid"], "interest": interest["score"]})

    data_doc = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "source_note": "Music from tampere-keikat (read-only). Sports/student/theatre/library rows marked SAMPLE are seed data until their adapters are wired.",
        "source_status": status,
        "coverage": {"by_category": dict(by_cat), "by_area": dict(by_area), "total": len(rows)},
        "events": rows,
    }
    venues_out = {"schema_version": 1, "hubs": hubs, "venues": [
        {"id": v["id"], "name": v["name"], "lat": v["lat"], "lon": v["lon"], "area": v["area"],
         "kind": v["kind"], "capacity": v["capacity"], "approx": v.get("approx", False)}
        for v in VENUES]}

    write(os.path.join(WEB, "data.json"), data_doc)
    write(os.path.join(GEO, "venues.json"), venues_out)
    write(os.path.join(GEO, "zones.json"), {"schema_version": 1, "zones": ZONES})
    write(os.path.join(GEO, "flows.json"), {
        "schema_version": 1, "model_version": MODEL_VERSION,
        "generated": data_doc["generated"], "events": flows, "venues": ev_geo,
    })
    used_routes = {}
    for f in flows:
        for leg in f.get("legs", []):
            if leg["key"] in ROUTES:
                used_routes[leg["key"]] = ROUTES[leg["key"]]
    write(os.path.join(GEO, "routes.json"), {
        "schema_version": 1,
        "source": routes_doc.get("source", "OSRM foot"),
        "generated": data_doc["generated"],
        "routes": used_routes,
    })

    write(os.path.join(GEO, "coverage.json"), {
        "generated": data_doc["generated"], "sources": status,
        "by_category": dict(by_cat), "by_area": dict(by_area), "total": len(rows),
    })

    log(f"[build] {len(rows)} events | " + ", ".join(f"{k}:{v}" for k, v in sorted(by_cat.items())))
    log(f"[build] areas: " + ", ".join(f"{k}:{v}" for k, v in sorted(by_area.items())))
    return len(rows)


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sync", "full"], default="full")
    ap.add_argument("--city", default="tampere")
    args = ap.parse_args()
    if args.city != "tampere":
        log(f"[build] city '{args.city}' not configured yet")
        return 2
    n = build(args.mode)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
