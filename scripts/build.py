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
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calibration as calib  # noqa: E402  (same directory as this file)
from feeds import kide as kide_feed  # noqa: E402  (adapter lives beside this file)
from feeds import tampere_city as city_feed  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
GEO = os.path.join(WEB, "geo")

KEIKAT_URL = "https://zakker111.github.io/tampere-keikat/data.json"
MODEL_VERSION = "2026.11.11"
SCHEMA_VERSION = 3
FLOWS_SCHEMA_VERSION = 2
COMPETITION_FLOOR = 0.05  # no event loses more than 95% of its independent demand
COMPETITION_MIN_OVERLAP = 0.5  # weaker shared slices are inside the model's noise band
# A missing start is a prior, not a published 19:00. Spread the heat uniformly over
# three hourly candidates in a two-hour window centred on the old 19:00 fallback.
TBA_START_WINDOW = (18 * 60, 20 * 60)
TBA_START_OPTIONS = (18 * 60, 19 * 60, 20 * 60)
TBA_START_WINDOW_LABEL = "18:00–20:00"
TZ = ZoneInfo("Europe/Helsinki")

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
    """Same convention as the page: a start before 06:00 belongs to the previous night."""
    try:
        h, m = (int(x) for x in (s or "19:00").split(":"))
    except (TypeError, ValueError):
        return 19 * 60
    v = h * 60 + m
    return v + 24 * 60 if v < 6 * 60 else v


def start_options(time_s):
    """Candidate start minutes used to spread the heat for a missing start.

    A published time has exactly one candidate. A blank time is modelled uniformly
    over the documented TBA window (18:00, 19:00, 20:00); the row itself keeps its
    empty published time and the UI keeps the TBA label.
    """
    if (time_s or "").strip():
        return [clock_minutes(time_s)]
    return list(TBA_START_OPTIONS)


def clean_feed_time(date_s, time_s):
    """Discard a time that is really the event's day and month.

    The upstream music feed sometimes writes a missing start as ``DD:MM`` for the
    event date (2026-12-05 -> 05:12, 2026-11-21 -> 21:11). Those are not published
    start times and two of them would also move the event to the previous day via
    ``night_date``. Treat them like any other omitted start instead of inventing one.
    """
    if not time_s:
        return time_s
    try:
        day = dt.date.fromisoformat(date_s)
    except (TypeError, ValueError):
        return time_s
    return "" if time_s == f"{day.day:02d}:{day.month:02d}" else time_s


def night_date(date_s, time_s):
    """The day whose 06:00–06:00 strip contains an after-midnight start.

    Source calendars label a 00:30 event with that calendar date, while this site's
    day strip starts at 06:00. Without moving those starts back one date, a 00:30
    event on 9 Dec is drawn at 00:30 on 10 Dec (the next day's `+1` stop).
    """
    try:
        day = dt.date.fromisoformat(date_s)
        hour = int((time_s or "").split(":")[0])
    except (TypeError, ValueError):
        return date_s
    return (day - dt.timedelta(days=1)).isoformat() if hour < 6 else date_s


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
    today_helsinki = dt.datetime.now(TZ).date()
    season = today_helsinki.year + (1 if today_helsinki.month >= 8 else 0)
    url = LIIGA_URL.format(season=season)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "kilinkolin/0.8 (+https://github.com/zakker111)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            games = json.loads(r.read().decode("utf-8"))
        if not isinstance(games, list):
            raise ValueError("unexpected game list")
        rows = []
        observations = []
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
            spectators = g.get("spectators")
            try:
                spectators = int(spectators) if spectators is not None else 0
            except (TypeError, ValueError):
                spectators = 0
            if g.get("ended") and spectators > 0:
                observations.append({
                    "date": start.date().isoformat(), "time": start.strftime("%H:%M"),
                    "title": f"{home} – {away}", "spectators": spectators,
                })
            rows.append([
                start.date().isoformat(), start.strftime("%H:%M"), f"{home} – {away}",
                "Nokia Arena", "hockey", False, g.get("buyTicketsUrl") or "", "sport", "hockey", 0,
                end_min,
            ])
        log(f"[sports] fetched {len(rows)} Tampere home fixtures, "
            f"{len(observations)} with reported attendance")
        return rows, "OK", observations
    except Exception as exc:  # noqa: BLE001 - sports feed failure must not kill the build
        log(f"[sports] fetch failed: {exc}")
        return [], f"FAILED: {exc}", []


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
    # A substring match is a fallback, not a license for a short generic alias to
    # win. "Hatanpään valtatie 1 / Lush Koskikeskus, 00100 Tampere" must resolve to
    # Koskikeskus, not to the city-wide "Tampere" fallback or the first venue that
    # happens to share the street address.
    matches = [(len(key), key, vid) for key, vid in alias_idx.items()
               if vid != "tampere_muu" and len(key) > 4 and key in low]
    if matches:
        _, _, vid = max(matches)
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
        elif 6 <= hour < 15:
            # a 00:30 start is a late-night event, not a daytime one
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


def venue_capacity(venue, category):
    """The venue's seat count for this kind of event.

    An arena's concert capacity is not its hockey capacity. Using the larger number for a
    Liiga game inflated every hockey estimate; the registry carries both, so pick the one
    that matches the event instead of taking the maximum.
    """
    sport = int(venue["capacity"].get("sport", 0) or 0)
    if category == "sports" and sport > 0:
        return max(sport, 20)
    return max(int(venue["capacity"].get("gig", 0) or 0), 20)


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
    venue_cap = venue_capacity(venue, e.get("category"))
    mp = e.get("max_participants")
    if isinstance(mp, int) and mp > 0:
        # The 20-seat floor is a model prior for unknown venues. Applying it to a
        # published cap would make the capacity exceed maxParticipants.
        return min(mp, venue_cap)
    title_l = (e.get("title") or "").lower()
    if e.get("category") == "student" or e.get("kind") == "student":
        practice_kw = ("treenit", "treeni", "harjoitus", "harjoitukset", "practice",
                       "workout", "opastus", "kyykk")
        if any(k in title_l for k in practice_kw):
            # a practice/training session is a small group, not the whole hall
            return min(venue_cap, 60)
        # sitsit / gaala / party / turnaus keep the venue capacity (big event)
    return venue_cap


def fill_value(e):
    return FILL.get(e["sub"], CATEGORY_FALLBACK_FILL.get(e["category"], 0.45))


def allocate_collision(mids, capacity):
    """Allocate a shared venue cap across simultaneous events.

    Returns ``(allocated_mids, factor)``. If the group already fits, the mids are
    unchanged and the factor is 1. Above the cap, the cap is split in proportion to
    each event's independent mid and the integer remainder goes to the largest
    fractional shares. This makes the combined mid exactly equal to the venue cap.
    """
    total = sum(mids)
    if total <= capacity or total <= 0:
        return list(mids), 1.0
    if capacity <= 0:
        return [0 for _ in mids], 0.0
    raw = [mid * capacity / total for mid in mids]
    allocated = [int(math.floor(value)) for value in raw]
    remainder = capacity - sum(allocated)
    order = sorted(range(len(mids)), key=lambda i: raw[i] - allocated[i], reverse=True)
    for i in order[:remainder]:
        allocated[i] += 1
    return allocated, capacity / total


def apply_flow_scale(flow, factor, mid_override=None):
    """Scale a flow's attendance, legs and corridors together."""
    for key in ("low", "mid", "high"):
        flow["attendance"][key] = int(round(flow["attendance"][key] * factor))
    if mid_override is not None:
        flow["attendance"]["mid"] = int(mid_override)
        flow["attendance"]["low"] = min(flow["attendance"]["low"], flow["attendance"]["mid"])
        flow["attendance"]["high"] = max(flow["attendance"]["high"], flow["attendance"]["mid"])
    for leg in flow.get("legs", []):
        leg["people"] = int(round(float(leg.get("people", 0)) * factor))
    for corridor in flow.get("corridors", []):
        corridor["people"] = int(round(float(corridor.get("people", 0)) * factor))


def attendance_est(cap, category, sub, interest, ev, fill_override=None):
    fill = fill_override if fill_override is not None else fill_value(ev)
    if ev.get("seed") and category == "sports" and sub == "hockey" and fill_override is None:
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
    return {"low": int(mid * (1 - spread)), "mid": int(mid), "high": int(min(cap, mid * (1 + spread))),
            "spread": spread}


def capacity_source(e, venue):
    """Human-readable provenance for the capacity used by the estimate."""
    mp = e.get("max_participants")
    venue_cap = venue_capacity(venue, e.get("category"))
    if isinstance(mp, int) and mp > 0:
        if mp > venue_cap:
            return "city calendar maxParticipants, capped by the venue's capacity"
        return "city calendar maxParticipants"
    if e.get("category") == "sports" and int(venue["capacity"].get("sport", 0) or 0) > 0:
        return "venue registry sport capacity"
    if int(venue["capacity"].get("gig", 0) or 0) > 0:
        return "venue registry gig capacity"
    return "model floor (20 seats)"


def fill_source(e, calibration):
    """Human-readable provenance for the fill factor used by the estimate."""
    if e.get("category") == "sports" and e.get("sub") == "hockey":
        liiga = (calibration or {}).get("liiga") or {}
        if liiga.get("status") == "FITTED":
            return f"fitted on {liiga['sample']} Liiga games with reported attendance"
        if liiga.get("status") == "PRIOR":
            return "hockey prior (the fitted factor did not beat the prior)"
        return "hockey prior (not enough reported attendance to fit)"
    return "category prior"


def calibrate_liiga(observations, alias_idx):
    """Fit the hockey fill factor to realized Liiga attendance and backtest it.

    The production factor is fitted on every completed game with reported spectators. The
    published error is leave-one-out: each game is predicted by a factor fitted without it,
    so the error is not the same in-sample fit that produced the factor. The fitted factor
    replaces the prior only when that out-of-sample error beats the prior's. If there are
    fewer than eight observations, the prior stays.
    """
    prior = FILL.get("hockey", 0.85)
    venue = resolve_venue("Nokia Arena", alias_idx, VENUES)
    samples = []
    if venue and venue["id"] != "tampere_muu":
        for obs in observations:
            ev = {
                "date": obs["date"], "time": obs["time"], "title": obs["title"],
                "venue": venue, "free": False, "hour": int(obs["time"].split(":")[0]),
                "category": "sports", "sub": "hockey", "kind": "sport", "seed": False,
            }
            cap = event_capacity(ev, venue)
            interest = interest_score(ev, cap, "sports", "hockey", venue)
            samples.append({"actual": int(obs["spectators"]), "cap": cap,
                            "interest": interest, "ev": ev})

    base = {
        "source": "Liiga public game list",
        "metric": "reported spectators",
        "sample": len(samples),
        "prior_fill": round(prior, 3),
        "fitted_fill": round(prior, 3),
        "status": "UNAVAILABLE" if not samples else "INSUFFICIENT",
        "method": "one hockey fill factor, fitted by mean absolute percentage error; "
                  "it replaces the prior only when its leave-one-out MAPE is lower; "
                  "the published error is leave-one-out",
    }
    if samples:
        base["from"] = min(s["ev"]["date"] for s in samples)
        base["to"] = max(s["ev"]["date"] for s in samples)
    if len(samples) < 8:
        return base

    def predict(sample, factor):
        return attendance_est(sample["cap"], "sports", "hockey", sample["interest"],
                              sample["ev"], fill_override=factor)["mid"]

    fit = calib.fit_single_factor(samples, predict, prior)
    prior_mape = sum(abs(predict(s, prior) - s["actual"]) / s["actual"] for s in samples) / len(samples)
    loo = calib.leave_one_out(samples, predict, prior)
    if fit and loo and loo["sample"] == len(samples) and loo["mape"] < prior_mape:
        fitted = fit[0]
        base["status"] = "FITTED"
        base["fitted_mape"] = round(fit[1], 3)
        base.update(loo)
    else:
        fitted = prior
        base["status"] = "PRIOR"
    FILL["hockey"] = fitted
    base["fitted_fill"] = round(fitted, 3)
    base["prior_mape"] = round(prior_mape, 3)
    return base


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


def catchment_overlap(zones_a, zones_b):
    """Intersection of two events' top-zone arrival shares, in [0, 1].

    Only the published top-zone rows are compared. The unlisted remainder is not
    assumed to overlap: two events can both have a long tail without drawing the same
    people.
    """
    a = {z["zone_id"]: float(z.get("share", 0.0)) for z in (zones_a or [])}
    b = {z["zone_id"]: float(z.get("share", 0.0)) for z in (zones_b or [])}
    return min(1.0, sum(min(a[key], b[key]) for key in a.keys() & b.keys()))


def competition_factor(flow, peers):
    """Count an overlapping catchment's shared slice once, not once per event.

    For each same-day peer, the shared exposure is the fraction of the shorter active
    window that overlaps times the overlap of the two top-zone catchments. Only pairs
    with at least ``COMPETITION_MIN_OVERLAP`` shared catchment are treated as competing;
    below that the overlap is inside the model's noise band.

    The shared slice is one demand pool sized by the largest exposed event. Each event
    keeps its unique slice and receives a share of the pool proportional to its own
    exposed demand. This is an explicit sharing prior, not a fitted substitution model:
    two equal events with the same time and full catchment overlap each keep half; a
    small event keeps its unique catchment and a proportional share of a larger event's
    pool instead of being erased. Disjoint catchments and non-overlapping times do not
    compete.
    """
    start, end = flow.get("start"), flow.get("end")
    demand = max(1.0, float((flow.get("attendance") or {}).get("mid", 0.0)))
    if start is None or end is None or end <= start:
        return 1.0, 0
    duration = max(1.0, end - start)
    exposures = []
    for other in peers:
        other_start, other_end = other.get("start"), other.get("end")
        if other_start is None or other_end is None or other_end <= other_start:
            continue
        overlap = min(end, other_end) - max(start, other_start)
        if overlap <= 0:
            continue
        temporal = min(1.0, overlap / max(1.0, min(duration, other_end - other_start)))
        shared = catchment_overlap(flow.get("zones"), other.get("zones"))
        if shared < COMPETITION_MIN_OVERLAP:
            continue
        other_demand = max(1.0, float((other.get("attendance") or {}).get("mid", 0.0)))
        exposures.append((other_demand, temporal * shared))
    if not exposures:
        return 1.0, 0

    # The largest pairwise slice is the shared pool; do not discount the same slice
    # repeatedly just because several peers share it. Peer exposures are summed to
    # apportion that pool between everyone drawing on it.
    own_shared = demand * max(exposure for _, exposure in exposures)
    peer_shared = sum(other_demand * exposure for other_demand, exposure in exposures)
    total_shared = own_shared + peer_shared
    pool = max([own_shared] + [other_demand * exposure for other_demand, exposure in exposures])
    retained = demand - own_shared + pool * own_shared / total_shared
    factor = min(1.0, max(COMPETITION_FLOOR, retained / demand))
    return factor, len(exposures)


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
            detail = kide_feed.fetch_detail(ev.get("product_id"))
            venue = kide_detail_venue(ev, detail)
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


def dedupe_events(events):
    """Collapse duplicate listings for the same venue, date and start.

    A repeated performance keeps its distinct start time. A row with no start time is not
    merged with a timed row: the missing time is an assumption, not evidence that the two
    listings are the same event. The first listing keeps its identity; missing end/url/cap
    fields are filled from the duplicate.
    """
    kept, by_key = [], {}
    merged = 0
    for e in events:
        key = (e["date"], e["venue"]["id"], norm_title(e["title"]), (e.get("time") or "").strip())
        first = by_key.get(key)
        if first is None:
            by_key[key] = e
            kept.append(e)
            continue
        merged += 1
        if first.get("end_min") is None and e.get("end_min") is not None:
            first["end_min"] = e["end_min"]
        if not first.get("max_participants") and e.get("max_participants"):
            first["max_participants"] = e["max_participants"]
        if not first.get("url") and e.get("url"):
            first["url"] = e["url"]
        # A sample row only stays a sample when every duplicate is a sample. Conflicting
        # free/paid claims keep the first source's value instead of inventing one.
        first["seed"] = bool(first.get("seed") and e.get("seed"))
    return kept, merged


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


def kide_detail_venue(ev, detail):
    """Use the address and point published in a Kide product detail.

    The list endpoint only has a free-text place; the detail is the organiser's own
    published location. A vague place name or a postal box is not an address, so it is
    still dropped rather than guessed.
    """
    if not isinstance(detail, dict):
        return None
    try:
        lat = float(detail.get("latitude"))
        lon = float(detail.get("longitude"))
    except (TypeError, ValueError):
        return None
    street = " ".join((detail.get("streetAddress") or "").split())
    low = street.lower()
    if (not street or not re.search(r"\d", street) or low in {"tampereen seutu", "tampere"}
            or low.startswith("pl ") or not (61.0 < lat < 62.0 and 22.5 < lon < 25.0)):
        return None
    postal = " ".join((detail.get("postalCode") or "").split())
    city = " ".join((detail.get("city") or "").split())
    address = street + (", " + " ".join(p for p in (postal, city) if p) if postal or city else "")
    # Prefer a venue name that the detail address actually contains. A bare address
    # match is ambiguous in a shared building: "Hatanpään valtatie 1 / Lush
    # Koskikeskus" must not become Ilves Bar & Night just because both are at number 1.
    existing = resolve_venue(address, build_alias_index(VENUES), VENUES)
    if existing and existing["id"] != "tampere_muu":
        return existing
    existing = resolve_by_address(address, VENUES)
    if existing and existing["id"] != "tampere_muu":
        return existing
    vid = "kide-" + hashlib.sha1(
        f"{address.lower()}|{round(lat, 5)},{round(lon, 5)}".encode()).hexdigest()[:8]
    for v in VENUES:
        if v["id"] == vid:
            return v
    venue = {
        "id": vid, "name": (ev.get("place") or place_name(street)).strip(),
        "lat": lat, "lon": lon, "area": nearest_zone(lat, lon),
        "kind": "student", "capacity": {"gig": 0},
        "hubs": nearest_hubs(lat, lon), "approx": False, "address": address,
        "source": "kide product location",
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
    sports_rows, sports_status, liiga_observations = fetch_liiga()
    calibration = {"liiga": calibrate_liiga(liiga_observations, alias_idx)}
    student_rows, student_status = kide_rows(alias_idx)
    # kide_rows can add a venue whose location came from the product detail endpoint;
    # include those names before the student rows are resolved a second time.
    alias_idx = build_alias_index(VENUES)
    city_items, city_status = city_feed.fetch()
    status = {"music": music_status, "seed": "ON" if with_samples else "OFF",
              "sports": sports_status, "student": student_status, "culture": city_status}

    events = []
    unmatched = Counter()
    leaked_times = 0

    for row in feed.get("events", []):
        if len(row) < 7:
            continue
        date, time_s, title, venue_raw, genre, free, url = row[:7]
        cleaned = clean_feed_time(date, time_s)
        if time_s and not cleaned:
            leaked_times += 1
        time_s = cleaned
        venue = resolve_venue(venue_raw, alias_idx, VENUES)
        if not venue or venue["id"] == "tampere_muu":
            # a real street address in the row beats the generic fallback venue
            venue = resolve_by_address(f"{venue_raw} {title}", VENUES) or venue
        if not venue or venue["id"] == "tampere_muu":
            # A district or other vague place is not a street address. Drop the row
            # instead of publishing it at an unlocatable fallback venue.
            unmatched[venue_raw or "(no venue)"] += 1
            continue
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
    # Keep every row: dedupe_events() below is the single duplicate gate and includes the venue,
    # so two venues showing the same title at the same time both survive.
    city_kept, city_new = 0, 0
    for item in city_items:
        venue = resolve_venue(item["place"], alias_idx, VENUES) or resolve_by_address(item["place"], VENUES)
        if not venue or venue["id"] == "tampere_muu":
            before = len(VENUES)
            venue = place_venue(item)
            if len(VENUES) > before:
                city_new += 1
        category, sub3 = classify(item["kind"], item["sub"], None, item["title"])
        start_min = clock_minutes(item["time"])
        end_min = start_min + item["minutes"] if item["minutes"] else None
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
        log(f"[city] {city_kept} events placed ({city_new} new calendar venue(s))")

    events, merged_listings = dedupe_events(events)
    if merged_listings:
        log(f"[events] merged {merged_listings} duplicate listing(s) at the same venue and start")

    if unmatched:
        log(f"[venues] music rows dropped for an unknown venue: {dict(unmatched)}")
    if leaked_times:
        log(f"[music] {leaked_times} start time(s) repeated the event date; treated as missing")

    # The UI's day strip runs 06:00–06:00, so an 00:30 start belongs to the previous
    # strip. Do this before the date filter; an after-midnight event earlier today is
    # already past, while one tomorrow belongs on today's strip.
    for e in events:
        e["date"] = night_date(e["date"], e["time"])
    today = dt.datetime.now(TZ).date().isoformat()
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
    city_capacity = {"events_with_published_capacity": 0}
    tba_events = sum(1 for e in events if not (e.get("time") or "").strip())

    for i, e in enumerate(events):
        venue = e["venue"]
        cap = event_capacity(e, venue)
        interest = interest_score(e, cap, e["category"], e["sub"], venue)
        att = attendance_est(cap, e["category"], e["sub"], interest, e)
        if isinstance(e.get("max_participants"), int) and e["max_participants"] > 0:
            city_capacity["events_with_published_capacity"] += 1
        cls, zone_rows = gravity(e, venue, ZONES)
        legs = legs_for(venue, zone_rows, ROUTES, HUB_NAMES, HUB_KINDS, att["mid"])
        corridors = [] if legs else corridors_for(venue, zone_rows, hubs, att["mid"])
        modes = summarise_modes(zone_rows, cls)
        eid = f"e{i:04d}"
        by_cat[e["category"]] += 1
        by_area[venue["area"]] += 1

        start_min = clock_minutes(e["time"])
        starts = start_options(e["time"])
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
            "start_known": bool((e.get("time") or "").strip()),
            "basis": {
                "capacity": cap,
                "capacity_source": capacity_source(e, venue),
                "fill": round(fill_value(e), 3),
                "fill_source": fill_source(e, calibration),
                "interest": interest["score"],
                "spread": att["spread"],
                "published_max_participants": e.get("max_participants") or None,
            },
            "zones": zone_rows[:8],
            "rest_share": round(max(0.0, 1 - sum(z["share"] for z in zone_rows[:8])), 4),
            "modes": modes, "legs": legs, "corridors": corridors,
            "start": start_min, "end": end_min,
            "arrival": [{"t": t, "share": s} for t, s in ARRIVAL[cls]],
            "egress": egress,
        })
        if len(starts) > 1:
            flows[-1]["start_options"] = starts
            flows[-1]["start_window"] = TBA_START_WINDOW_LABEL
        ev_geo.append({"id": eid, "venue_id": venue["id"], "lat": venue["lat"], "lon": venue["lon"],
                       "date": e["date"], "attendance": att["mid"], "interest": interest["score"]})

    # Competition is applied after every event has an independent demand estimate. It
    # scales the whole flow (attendance, legs and corridors) so the panel, dots and heat
    # all use the same adjusted number. See competition_factor() for the assumptions.
    by_date = defaultdict(list)
    for i, e in enumerate(events):
        by_date[e["date"]].append(i)
    competition_events = 0
    for i, e in enumerate(events):
        peers = [flows[j] for j in by_date[e["date"]] if j != i]
        factor, peer_count = competition_factor(flows[i], peers)
        flows[i]["basis"]["competition"] = {
            "factor": round(factor, 3),
            "peers": peer_count,
        }
        if round(factor, 3) < 0.999:
            competition_events += 1
        if factor < 1.0:
            for key in ("low", "mid", "high"):
                flows[i]["attendance"][key] = int(round(flows[i]["attendance"][key] * factor))
            rows[i][12] = flows[i]["attendance"]["mid"]
            ev_geo[i]["attendance"] = flows[i]["attendance"]["mid"]
            for leg in flows[i].get("legs", []):
                leg["people"] = int(round(float(leg.get("people", 0)) * factor))
            for corridor in flows[i].get("corridors", []):
                corridor["people"] = int(round(float(corridor.get("people", 0)) * factor))
    # Venue/date/start collision guard. Distinct listings at one building and one
    # published start are not separate rooms until the source says so; cap the group
    # at the smallest applicable venue capacity and flag an unpublished room split.
    collision_groups = defaultdict(list)
    for i, flow in enumerate(flows):
        if not flow.get("start_known"):
            continue  # a TBA row has no single published start to collide on
        collision_groups[(flow["venue_id"], events[i]["date"], flow["start"])].append(i)
    venue_collisions = {
        "status": "CAP",
        "groups": 0,
        "events": 0,
        "capped_groups": 0,
        "unresolved_room_splits": 0,
        "method": "same venue + date + published start: cap combined mid at the smallest "
                  "applicable venue capacity and allocate proportionally; flag every shared "
                  "group as an unresolved room split",
        "note": "TBA rows have no single published start and are not grouped. A published "
                "maxParticipants is a per-event cap, not evidence of which room a listing uses.",
    }
    for idxs in collision_groups.values():
        if len(idxs) < 2:
            continue
        venue_collisions["groups"] += 1
        venue_collisions["events"] += len(idxs)
        capacity = min(venue_capacity(events[i]["venue"], events[i]["category"])
                       for i in idxs)
        before = sum(flows[i]["attendance"]["mid"] for i in idxs)
        targets, factor = allocate_collision(
            [flows[i]["attendance"]["mid"] for i in idxs], capacity)
        # A per-event maxParticipants does not identify which room each listing uses,
        # so every shared-building group stays an unresolved split.
        room_split = "UNRESOLVED"
        venue_collisions["unresolved_room_splits"] += 1
        if before > capacity:
            venue_collisions["capped_groups"] += 1
        for i, target in zip(idxs, targets):
            flow = flows[i]
            if target != flow["attendance"]["mid"]:
                apply_flow_scale(flow, target / flow["attendance"]["mid"], target)
                rows[i][12] = flow["attendance"]["mid"]
                ev_geo[i]["attendance"] = flow["attendance"]["mid"]
            flow["basis"]["venue_collision"] = {
                "group_size": len(idxs),
                "venue_capacity": capacity,
                "combined_mid_before": before,
                "combined_mid_after": sum(targets),
                "factor": round(factor, 3),
                "room_split": room_split,
                "note": "Same venue and published start; the combined estimate shares one "
                        "building cap. Room-level allocation is not published.",
            }
    calibration["venue_collisions"] = venue_collisions

    calibration["tba_start"] = {
        "status": "PRIOR",
        "window": TBA_START_WINDOW_LABEL,
        "window_minutes": list(TBA_START_WINDOW),
        "assumed_starts": ["18:00", "19:00", "20:00"],
        "method": "unknown starts are averaged uniformly over 18:00, 19:00 and 20:00; "
                  "arrival and egress curves are mixed instead of pinned to one peak",
        "events_with_unknown_start": tba_events,
        "note": "The feed published no start; the row keeps its empty time and the UI says TBA. "
                "This is a documented uncertainty window, not a measured start.",
    }
    calibration["competition"] = {
        "status": "PRIOR",
        "method": "shared-catchment demand pool: require >=50% top-zone overlap and an "
                  "overlapping active window; count the shared slice once at the largest "
                  "exposed event and apportion it by exposure; floor 0.05",
        "floor": COMPETITION_FLOOR,
        "min_catchment_overlap": COMPETITION_MIN_OVERLAP,
        "events_with_competition": competition_events,
        "note": "Not fitted or measured: a prior for sharing demand between concurrent events. "
                "Only top-zone shares are compared; the unlisted remainder is not assumed to overlap. "
                "Unique catchment slices are retained, so a smaller event is not erased by a larger peer.",
    }

    calibration["city_capacity"] = {
        "source": "Tampere city calendar maxParticipants",
        "events_with_published_capacity": city_capacity["events_with_published_capacity"],
        "note": "maxParticipants is a published cap, not realized attendance; it is never used as backtest ground truth.",
    }
    data_doc = {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "calibration": calibration,
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
        "schema_version": FLOWS_SCHEMA_VERSION, "model_version": MODEL_VERSION,
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
    routes_doc_out = {
        "schema_version": 1,
        "source": routes_doc.get("source", "OSRM foot"),
        "generated": data_doc["generated"],
        "routes": web_routes,
    }
    write(os.path.join(GEO, "routes.json"), routes_doc_out)

    # The page used to download every flow and every route on first paint.  Most
    # visits only need the selected day, so publish one self-contained bundle per
    # date and let the browser fetch those lazily.  Keep the full files above for
    # consumers that still expect them and for the validation/coverage gates.
    days_dir = os.path.join(GEO, "days")
    os.makedirs(days_dir, exist_ok=True)
    for name in os.listdir(days_dir):
        if name.endswith(".json"):
            os.remove(os.path.join(days_dir, name))
    date_by_id = {row[7]: row[0] for row in rows}
    by_day = defaultdict(list)
    for flow in flows:
        by_day[date_by_id.get(flow["id"])].append(flow)
    for day, day_flows in sorted(by_day.items()):
        if not day:
            continue
        day_routes = {}
        for flow in day_flows:
            for leg in flow.get("legs", []):
                key = leg["key"]
                if key in web_routes:
                    day_routes[key] = web_routes[key]
        write(os.path.join(days_dir, f"{day}.json"), {
            "schema_version": FLOWS_SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "generated": data_doc["generated"],
            "date": day,
            "events": day_flows,
            "routes": day_routes,
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
