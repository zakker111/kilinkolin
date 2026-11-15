#!/usr/bin/env python3
"""Kilinkolin build pipeline.

sync  -> fetch feeds, normalise events, write web/data.json
full  -> sync + attendance, interest, gravity split, corridors, curves

Everything is estimated: no measured attendance, no tracking.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from feeds import kide as kide_feed  # noqa: E402  (adapter lives beside this file)
from feeds import tampere_city as city_feed  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
GEO = os.path.join(WEB, "geo")

KEIKAT_URL = "https://zakker111.github.io/tampere-keikat/data.json"
MODEL_VERSION = "2026.11.5"
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


LIIGA_URL = "https://liiga.fi/api/v2/games?season={season}&tournament=runkosarja"
TAMPERE_TEAMS = {"Ilves", "Tappara"}


def fetch_liiga():
    """Ilves/Tappara home fixtures from Liiga's public game list.

    The feed carries no calendar export, but the game list includes the rink,
    its coordinates and the teams, so home games can be pinned to Nokia Arena.
    """
    season = dt.date.today().year + (1 if dt.date.today().month >= 8 else 0)
    url = LIIGA_URL.format(season=season)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kilinkolin/0.8 (+https://github.com/zakker111)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            games = json.loads(r.read().decode("utf-8"))
        if not isinstance(games, list):
            raise ValueError("unexpected game list")
        rows = []
        for g in games:
            rink = g.get("iceRink") or {}
            home = (g.get("homeTeam") or {}).get("teamName") or ""
            away = (g.get("awayTeam") or {}).get("teamName") or ""
            if home not in TAMPERE_TEAMS or (rink.get("city") or "").upper() != "TAMPERE":
                continue
            try:
                start = dt.datetime.fromisoformat(g["start"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Helsinki"))
            except (KeyError, ValueError):
                continue
            gametime = g.get("gameTime")
            if not isinstance(gametime, (int, float)):
                gametime = 0
            end_min = None
            if gametime > 0:
                # playing-time length (regulation + overtime, excludes intermissions):
                # real end only when the feed carried it, otherwise fall back to the
                # planned playing time so we are not silently wrong about event length
                end_min = start.hour * 60 + start.minute + gametime / 60.0
            rows.append([
                start.date().isoformat(), start.strftime("%H:%M"), f"{home} – {away}",
                "Nokia Arena", "hockey", False, g.get("buyTicketsUrl") or "", "sport", "hockey", 0,
                end_min,
            ])
        log(f"[sports] fetched {len(rows)} Tampere home fixtures")
        return rows, "OK"
    except Exception as exc:  # noqa: BLE001 - sports feed failure must not kill the build
        log(f"[sports] fetch failed: {exc}")
        return [], f"FAILED: {exc}"


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


def resolve_by_address(text, venues):
    """Find a registry venue whose street address appears in the feed's text.

    Some feeds put the address where the venue belongs and the admission in the venue
    field ("Ilmainen" + "… Puuvillatehtaankatu 2"). A street name with a house number is
    a real location, so it is allowed to place the event — nothing is guessed here.
    """
    low = (text or "").lower()
    if not low:
        return None
    for v in venues:
        if v["id"] == "tampere_muu":
            continue
        addr = (v.get("address") or "").strip().lower()
        if len(addr) > 6 and any(c.isdigit() for c in addr) and addr in low:
            return v
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


def event_capacity(e, venue):
    """Per-event size signal, so a big gig/match/party reads big and a practice or
    small talk reads small instead of inheriting the whole venue's capacity.

    Sources of truth, in order:
      * the city calendar's published ``maxParticipants`` (capped to the venue's own
        capacity, since a room cannot hold more than it seats);
      * Kide title keywords for student events (``treenit``/practice -> a small group,
        ``sitsit``/``gaala``/party -> the venue's capacity);
      * otherwise the venue's capacity prior (existing behaviour).
    Missing input keeps the venue prior rather than inventing a number.
    """
    venue_cap = max(venue["capacity"].get("gig", 0), venue["capacity"].get("sport", 0), 20)
    mp = e.get("max_participants")
    if isinstance(mp, int) and mp > 0:
        return max(20, min(mp, venue_cap))
    title_l = (e.get("title") or "").lower()
    if e.get("category") == "student" or e.get("kind") == "student":
        practice_kw = ("treenit", "treeni", "harjoitus", "harjoitukset", "practice",
                       "workout", "opastus", "kyykk")
        if any(k in title_l for k in practice_kw):
            # a practice/training session is a small group, not the whole hall
            return min(venue_cap, 60)
        # sitsit / gaala / party / turnaus keep the venue capacity (big event)
    return venue_cap


def attendance_est(cap, category, sub, interest, ev):
    fill = FILL.get(sub, CATEGORY_FALLBACK_FILL.get(category, 0.45))
    if ev.get("seed") and category == "sports" and sub == "hockey":
        fill = 0.92
    # Venue-size class prior: after capacity is accounted for, an evening in a hall or arena
    # still pulls a fuller room than a small pub or bar, and a 20-seat room is not a sell-out
    # just because its handful of seats is full. Based on the *event's* capacity, so a practice
    # booked in an arena (already reduced by event_capacity) does not get the big-venue boost.
    if cap >= 10000:
        venue_scale = 1.10
    elif cap >= 2000:
        venue_scale = 1.06
    elif cap <= 150:
        venue_scale = 0.95
    else:
        venue_scale = 1.0
    mid = cap * fill * (0.72 + 0.45 * interest["score"] / 100.0) * venue_scale
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
    cap = event_capacity(ev, venue)
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
    if not rows:
        # A venue beyond the usual catchment (Kangasala, Nokia, Hämeenkyrö): the closest
        # districts still send people, so use the nearest ones instead of publishing an
        # event with no origin at all.
        rows = nearest_rows(ev, venue, zones)
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


def nearest_rows(ev, venue, zones, count=3):
    ranked = sorted(zones, key=lambda z: hav_km((z["lat"], z["lon"]), (venue["lat"], venue["lon"])))
    out = []
    for z in ranked[:count]:
        km = hav_km((z["lat"], z["lon"]), (venue["lat"], venue["lon"])) * 1.3
        student_w = z["student"] if ev["category"] == "student" else 1 + (z["student"] - 1) * 0.35
        profile = (0.55 + 0.45 * z.get("transit", .8)) * student_w
        time_h = max(0.15, km / (18 if km > 6 else 7))
        out.append((z, km, z["pop"] * profile / (time_h ** 1.6)))
    return out


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


def usable_route(routes, key):
    """A cached leg worth drawing: a district centroid that sits on the venue itself yields a
    0 km, two-point route, which is geometry in name only and paints nothing."""
    rec = routes.get(key)
    return rec is not None and rec.get("km", 0) >= 0.05


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
        if km > 3.0 and usable_route(routes, zone_key):
            # far district: draw its own transit corridor to the venue along the street
            # network, instead of collapsing every outer district onto the venue's one hub
            key = zone_key
        elif km <= 3.0 and usable_route(routes, zone_key):
            # close districts: people walk the whole way
            key = zone_key
        elif km > 3.0 and usable_route(routes, drive_key):
            # no district corridor cached yet: use the venue hub's transit corridor
            key, label = drive_key, hub_names.get(hub_id, row["name"])
        elif usable_route(routes, zone_key):
            key = zone_key
        elif usable_route(routes, hub_key):
            key, label = hub_key, hub_names.get(hub_id, row["name"])
        if key is None:
            continue
        rec = agg.setdefault(key, {"share": 0.0, "modes": defaultdict(float), "name": label,
                                   "km": routes[key]["km"], "min": routes[key]["min"],
                                   "row_km": km})
        rec["share"] += row["share"]
        for m, s in row["modes"].items():
            rec["modes"][m] += row["share"] * s
    legs = []
    for key, rec in agg.items():
        if rec["km"] < 0.05:
            continue  # would draw nothing: better to fall back to the straight corridors
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
        elif "|zone:" in key:
            # district legs: close ones are walked/biked; farther ones follow that district's
            # transit service — tram where the tram runs, train for the commuter towns,
            # bus everywhere else
            zid = key.split("|zone:")[-1]
            zone = next((z for z in ZONES if z["id"] == zid), None)
            if rec.get("row_km", rec["km"]) <= 3.0:
                mode = "walk"
            elif zone and zone.get("transit_mode"):
                mode = zone["transit_mode"]
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


KIDE_SUBS = (("sitsit", "sitsit"), ("appro", "party"), ("sauna", "sauna"),
             ("treenit", "sports"), ("treeni", "sports"), ("turnaus", "sports"),
             ("teatteri", "culture"), ("näytelm", "culture"))


def kide_rows(alias_idx):
    """Kide products placed on a real registry venue; anything unplaceable is dropped."""
    events, status = kide_feed.fetch()
    rows, skipped = [], Counter()
    for ev in events:
        venue = resolve_venue(ev["place"], alias_idx, VENUES)
        if not venue or venue["id"] == "tampere_muu":
            skipped[ev["place"] or "(no place)"] += 1
            continue
        title_l = ev["title"].lower()
        sub = next((s for key, s in KIDE_SUBS if key in title_l), "party")
        end_min = clock_minutes(ev["time"]) + ev["minutes"] if ev["minutes"] else None
        rows.append([ev["date"], ev["time"], ev["title"], venue["name"], "student",
                     1 if ev["free"] else 0, "", "student", sub, 0, end_min])
    if skipped:
        log(f"[kide] {len(rows)} placed, {sum(skipped.values())} dropped for an unknown venue: "
            + ", ".join(f"{k}×{v}" for k, v in skipped.most_common(4)))
    return rows, status


CITY_PREFIX = "city-"


def norm_title(title):
    """Loose key for spotting the same event published by two sources."""
    return " ".join("".join(c for c in (title or "").lower() if c.isalnum() or c.isspace()).split())


def place_name(address):
    """Readable label for a place that is not in the venue registry."""
    return (address or "").split(",")[0].strip() or address or "Tampere"


def nearest_zone(lat, lon):
    if not ZONES:
        return "Tampere"
    zone = min(ZONES, key=lambda z: hav_km((z["lat"], z["lon"]), (lat, lon)))
    return zone["name"]


def nearest_hubs(lat, lon):
    """The closest registered transit hub: the same modelling assumption the registry venues use."""
    if not HUBS:
        return []
    ranked = sorted(HUBS, key=lambda k: hav_km((HUBS[k]["lat"], HUBS[k]["lon"]), (lat, lon)))
    return ranked[:1]


def place_venue(item):
    """Register a venue from the city calendar's own coordinates and address.

    The calendar publishes the exact point of every location, so this is a real location and
    not a guess. Listings that round to the same point share one venue.
    """
    vid = CITY_PREFIX + hashlib.sha1(
        f"{round(item['lat'], 5)},{round(item['lon'], 5)}".encode()).hexdigest()[:8]
    for v in VENUES:
        if v["id"] == vid:
            return v
    venue = {
        "id": vid, "name": place_name(item["place"]),
        "lat": item["lat"], "lon": item["lon"],
        "area": nearest_zone(item["lat"], item["lon"]),
        "kind": "culture", "capacity": {"gig": int(item.get("max_participants") or 0)},
        "hubs": nearest_hubs(item["lat"], item["lon"]),
        "approx": False, "address": item["place"],
        "source": "tampere city calendar",
    }
    VENUES.append(venue)
    return venue


def venue_record(v):
    row = {"id": v["id"], "name": v["name"], "lat": v["lat"], "lon": v["lon"],
           "area": v["area"], "kind": v["kind"], "capacity": v["capacity"],
           "hubs": v.get("hubs") or [], "approx": v.get("approx", False)}
    if v.get("address"):
        row["address"] = v["address"]
    return row


# ------------------------------------------------------------------- build
ZONES = []
VENUES = []
HUBS = {}


def build(mode="full", with_samples=False):
    global ZONES, VENUES, HUBS
    os.makedirs(GEO, exist_ok=True)
    venues_doc = load_json(os.path.join(ROOT, "registry", "venues.json"))
    zones_doc = load_json(os.path.join(ROOT, "registry", "zones.json"))
    VENUES = venues_doc["venues"]
    ZONES = zones_doc["zones"]
    hubs = venues_doc["transit_hubs"]
    HUBS = hubs
    # A registry venue whose entry lists no transit hub (a church, a village hall, a library) is
    # still reached through one: use the nearest registered hub, the same assumption the venues
    # generated from the city calendar already use. Without this the route seeder has nothing to
    # fetch for it and the event stays on the straight-line fallback forever.
    hubless = [v for v in VENUES if not v.get("hubs")]
    for v in hubless:
        v["hubs"] = nearest_hubs(v["lat"], v["lon"])
    if hubless:
        log(f"[venues] {len(hubless)} venue(s) without a registry hub use their nearest one: "
            + ", ".join(v["id"] for v in hubless))
    alias_idx = build_alias_index(VENUES)

    routes_path = os.path.join(ROOT, "registry", "routes.json")
    routes_doc = load_json(routes_path) if os.path.exists(routes_path) else {"routes": {}}
    ROUTES = routes_doc.get("routes", {})
    HUB_NAMES = {k: v["name"] for k, v in hubs.items()}
    HUB_KINDS = {k: v.get("kind", "bus") for k, v in hubs.items()}
    log(f"[routes] {len(ROUTES)} walking legs cached")

    feed, music_status = fetch_keikat()
    # data/seed_events.json holds SAMPLE placeholders only; they are never published
    seed = load_json(os.path.join(ROOT, "data", "seed_events.json")) if with_samples else {"events": []}
    sports_rows, sports_status = fetch_liiga()
    student_rows, student_status = kide_rows(alias_idx)
    city_items, city_status = city_feed.fetch()
    status = {"music": music_status, "seed": "ON" if with_samples else "OFF",
              "sports": sports_status, "student": student_status, "culture": city_status}

    events = []
    unmatched = Counter()

    for row in feed.get("events", []):
        if len(row) < 7:
            continue
        date, time_s, title, venue_raw, genre, free, url = row[:7]
        venue = resolve_venue(venue_raw, alias_idx, VENUES)
        if not venue or venue["id"] == "tampere_muu":
            # a real street address in the row beats the generic fallback venue
            venue = resolve_by_address(f"{venue_raw} {title}", VENUES) or venue
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

    for row in seed.get("events", []) + sports_rows + student_rows:
        # sports rows may carry an explicit end minute from the Liiga adapter now
        date, time_s, title, venue_raw, genre, free, url, kind, sub, is_seed, *rest = row
        end_min_from_feed = rest[0] if rest and rest[0] is not None else None
        venue = resolve_venue(venue_raw, alias_idx, VENUES) or next(v for v in VENUES if v["id"] == "tampere_muu")
        hour = int(time_s.split(":")[0]) if time_s and ":" in time_s else None
        category, sub2 = classify(kind, sub, None, title)
        events.append({
            "date": date, "time": time_s, "title": title, "venue_raw": venue_raw,
            "venue": venue, "free": bool(free), "url": url, "hour": hour,
            "legacy_genre": genre if genre in MUSIC_GENRES else sub2,
            "category": category, "sub": sub2, "kind": kind, "seed": bool(is_seed),
            "end_min": end_min_from_feed,
        })

    # Theatre, culture and community rows from the city calendar. Each one carries its own
    # published coordinates, so an unregistered place becomes a real venue instead of a fallback.
    seen_titles = {(e["date"], norm_title(e["title"])) for e in events}
    city_kept, city_dup, city_new = 0, 0, 0
    for item in city_items:
        key = (item["date"], norm_title(item["title"]))
        if key in seen_titles:
            city_dup += 1
            continue
        venue = resolve_venue(item["place"], alias_idx, VENUES) or resolve_by_address(item["place"], VENUES)
        if not venue or venue["id"] == "tampere_muu":
            venue = place_venue(item)
            city_new += 1
        category, sub3 = classify(item["kind"], item["sub"], None, item["title"])
        start_min = clock_minutes(item["time"])
        end_min = start_min + item["minutes"] if item["minutes"] else None
        seen_titles.add(key)
        city_kept += 1
        events.append({
            "date": item["date"], "time": item["time"], "title": item["title"],
            "venue_raw": item["place"], "venue": venue, "free": bool(item["free"]),
            "url": item["url"], "hour": int(item["time"].split(":")[0]),
            "legacy_genre": sub3, "category": category, "sub": sub3,
            "kind": item["kind"], "seed": False, "end_min": end_min,
            "max_participants": int(item.get("max_participants") or 0),
        })
    if city_items:
        log(f"[city] {city_kept} events placed ({city_new} on a new calendar location), "
            f"{city_dup} duplicates of another source skipped")

    if unmatched:
        log(f"[venues] unresolved strings mapped to fallback: {dict(unmatched)}")

    today = dt.date.today().isoformat()
    events = [e for e in events if e["date"] >= today]
    events.sort(key=lambda e: (e["date"], e["time"] or "99:99"))

    # A bad network day must not replace the page with an empty map. If every feed failed (or
    # nothing survived the date filter) leave web/data.json and web/geo exactly as they are and
    # exit non-zero, so the workflow stops before committing or deploying the last good data away.
    feeds = {k: status[k] for k in ("music", "sports", "student", "culture")}
    failed = [k for k, v in feeds.items() if str(v).startswith("FAILED")]
    if not events or len(failed) == len(feeds):
        reason = ("every feed failed" if len(failed) == len(feeds)
                  else "no events survived the date filter")
        log(f"[build] {reason} ({', '.join(failed) or 'none failed'}) — keeping the last good data: "
            "web/data.json and web/geo are untouched")
        return 0

    rows, flows, ev_geo = [], [], []
    by_cat = Counter()
    by_area = Counter()

    for i, e in enumerate(events):
        venue = e["venue"]
        cap = event_capacity(e, venue)
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
        # Prefer a real end time from the feed when an adapter provides one.
        if e.get("end_min") is not None:
            end_min = float(e["end_min"])
        else:
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
        "source_note": "Music from tampere-keikat (read-only), hockey fixtures from the Liiga game list, student events from Kide, stage/culture/community events from the Tampere city calendar. Every row comes from a published feed; the SAMPLE seed file is only used with --with-samples.",
        "source_status": status,
        "coverage": {"by_category": dict(by_cat), "by_area": dict(by_area), "total": len(rows)},
        "events": rows,
    }
    venues_out = {"schema_version": 1, "hubs": hubs, "venues": [venue_record(v) for v in VENUES]}

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
    web_routes = {}
    for key, rec in used_routes.items():
        web_routes[key] = {**rec, "geometry": simplify_geometry(rec.get("geometry") or [])}
    write(os.path.join(GEO, "routes.json"), {
        "schema_version": 1,
        "source": routes_doc.get("source", "OSRM foot"),
        "generated": data_doc["generated"],
        "routes": web_routes,
    })

    write(os.path.join(GEO, "coverage.json"), {
        "generated": data_doc["generated"], "sources": status,
        "by_category": dict(by_cat), "by_area": dict(by_area), "total": len(rows),
    })

    log(f"[build] {len(rows)} events | " + ", ".join(f"{k}:{v}" for k, v in sorted(by_cat.items())))
    log(f"[build] areas: " + ", ".join(f"{k}:{v}" for k, v in sorted(by_area.items())))
    return len(rows)


def simplify_geometry(points, eps=0.00008):
    """Drop points that sit within about 9 m of the line between their neighbours.

    The heat is a diffuse density field, so sub-kernel deviations are invisible. Endpoints are
    always kept and coordinates are rounded to five decimals (~1 m). ``registry/routes.json``
    keeps the full OSRM geometry; only the browser copy is simplified.
    """
    if len(points) <= 2:
        return [[round(p[0], 5), round(p[1], 5)] for p in points]
    lat0 = sum(p[0] for p in points) / len(points)
    k = math.cos(math.radians(lat0))
    xy = [(p[1] * k, p[0]) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        x1, y1 = xy[i]
        x2, y2 = xy[j]
        dx, dy = x2 - x1, y2 - y1
        den = math.hypot(dx, dy)
        best, idx = -1.0, None
        for m in range(i + 1, j):
            x, y = xy[m]
            dist = math.hypot(x - x1, y - y1) if den == 0 else abs(dy * x - dx * y + x2 * y1 - y2 * x1) / den
            if dist > best:
                best, idx = dist, m
        if best > eps:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [[round(p[0], 5), round(p[1], 5)] for p, ok in zip(points, keep) if ok]


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["sync", "full"], default="full")
    ap.add_argument("--city", default="tampere")
    ap.add_argument("--with-samples", action="store_true",
                    help="also publish the SAMPLE rows from data/seed_events.json (never for the live site)")
    args = ap.parse_args()
    if args.city != "tampere":
        log(f"[build] city '{args.city}' not configured yet")
        return 2
    n = build(args.mode, args.with_samples)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
