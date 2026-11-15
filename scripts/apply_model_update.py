#!/usr/bin/env python3
"""One-shot migration: event size, transit corridors, venue-size prior and the version badge.

Applied by .github/workflows/apply-model-update.yml, which commits the result and deletes both
itself and this script. Idempotent: a second run is a no-op.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(os.path.join(ROOT, path), "w", encoding="utf-8") as f:
        f.write(text)


def replace_once(text, old, new, label):
    if new in text:
        print(f"  already: {label}")
        return text
    if old not in text:
        raise SystemExit(f"anchor not found: {label}")
    print(f"  patched: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------- build.py
b = read("scripts/build.py")
b = replace_once(
    b,
    "from feeds import city_events as city_feed  # noqa: E402",
    "from feeds import tampere_city as city_feed  # noqa: E402",
    "build import",
)
b = replace_once(b, 'MODEL_VERSION = "2026.11.2"', 'MODEL_VERSION = "2026.11.5"', "model version")

EVENT_CAP = '''def event_capacity(e, venue):
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


'''
b = replace_once(b, "def attendance_est(cap, category, sub, interest, ev):", EVENT_CAP + "def attendance_est(cap, category, sub, interest, ev):", "event_capacity")

b = replace_once(
    b,
    "    mid = cap * fill * (0.72 + 0.45 * interest[\"score\"] / 100.0)\n",
    """    # Venue-size class prior: after capacity is accounted for, an evening in a hall or arena
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
""",
    "venue-size prior",
)

b = replace_once(
    b,
    "def gravity(ev, venue, zones):\n    cap = max(venue[\"capacity\"].get(\"gig\", 0), venue[\"capacity\"].get(\"sport\", 0), 20)\n    cls = crowd_class(cap, ev[\"category\"], ev[\"sub\"])",
    "def gravity(ev, venue, zones):\n    cap = event_capacity(ev, venue)\n    cls = crowd_class(cap, ev[\"category\"], ev[\"sub\"])",
    "gravity event capacity",
)

b = replace_once(
    b,
    """        if km <= 3.0 and usable_route(routes, zone_key):
            # close districts: people walk the whole way
            key = zone_key
        elif km > 3.0 and usable_route(routes, drive_key):
            # far districts: walk to the stop, then tram/bus/train along the road corridor
            key, label = drive_key, hub_names.get(hub_id, row["name"])""",
    """        if km > 3.0 and usable_route(routes, zone_key):
            # far district: draw its own transit corridor to the venue along the street
            # network, instead of collapsing every outer district onto the venue's one hub
            key = zone_key
        elif km <= 3.0 and usable_route(routes, zone_key):
            # close districts: people walk the whole way
            key = zone_key
        elif km > 3.0 and usable_route(routes, drive_key):
            # no district corridor cached yet: use the venue hub's transit corridor
            key, label = drive_key, hub_names.get(hub_id, row["name"])""",
    "legs_for district corridor",
)

b = replace_once(
    b,
    '        rec = agg.setdefault(key, {"share": 0.0, "modes": defaultdict(float), "name": label,\n                                   "km": routes[key]["km"], "min": routes[key]["min"]})',
    '        rec = agg.setdefault(key, {"share": 0.0, "modes": defaultdict(float), "name": label,\n                                   "km": routes[key]["km"], "min": routes[key]["min"],\n                                   "row_km": km})',
    "legs_for row_km",
)

b = replace_once(
    b,
    """            if key.endswith(":drive"):
                # transit corridor keeps the station's mode
                mode = hub_kinds.get(hub_id_key, mode)
        legs.append({"key": key, "name": rec["name"], "share": round(rec["share"], 4),""",
    """            if key.endswith(":drive"):
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
        legs.append({"key": key, "name": rec["name"], "share": round(rec["share"], 4),""",
    "legs_for mode",
)

b = replace_once(
    b,
    '            "kind": item["kind"], "seed": False, "end_min": end_min,\n',
    '            "kind": item["kind"], "seed": False, "end_min": end_min,\n            "max_participants": int(item.get("max_participants") or 0),\n',
    "city max_participants",
)

b = replace_once(
    b,
    '        cap = max(venue["capacity"].get("gig", 0), venue["capacity"].get("sport", 0), 20)\n        interest = interest_score(e, cap, e["category"], e["sub"], venue)',
    '        cap = event_capacity(e, venue)\n        interest = interest_score(e, cap, e["category"], e["sub"], venue)',
    "build loop event capacity",
)
write("scripts/build.py", b)

# ---------------------------------------------------------------- venues
venues_path = "registry/venues.json"
text = read(venues_path)
v = json.loads(text)
have = {x["id"] for x in v["venues"]}
new_venues = [
    {"id": "bar_tullari", "name": "Bar Tullari", "aliases": ["bar tullari"],
     "address": "Tullikamarin aukio 1", "lat": 61.4984998, "lon": 23.7778542, "area": "Keskusta",
     "kind": "bar", "capacity": {"gig": 120, "sport": 0}, "hubs": ["rautsikka"], "walk_min": 4,
     "approx": False, "source": "OpenStreetMap address point"},
    {"id": "h5_bar", "name": "H5 Bar", "aliases": ["h5 bar", "h5 bar & cellar", "sin city", "sin city and h5 bar&cellar", "sincity", "sin city and h5 bar & cellar"],
     "address": "Hämeenkatu 5", "lat": 61.4982248, "lon": 23.7696709, "area": "Keskusta",
     "kind": "bar", "capacity": {"gig": 150, "sport": 0}, "hubs": ["rautsikka"], "walk_min": 3,
     "approx": False, "source": "OpenStreetMap address point"},
    {"id": "megazone", "name": "Megazone Tampere", "aliases": ["megazone", "megazone tampere"],
     "address": "Hammareninkatu 6", "lat": 61.4969307, "lon": 23.7769815, "area": "Tammela",
     "kind": "club", "capacity": {"gig": 80, "sport": 0}, "hubs": ["rautsikka"], "walk_min": 5,
     "approx": False, "source": "OpenStreetMap address point"},
    {"id": "rush_tampere", "name": "Rush Trampoliinipuisto Tampere", "aliases": ["rush", "rush tampere", "rush trampoliinipuisto"],
     "address": "Jokipohjantie 32", "lat": 61.4748503, "lon": 23.7967211, "area": "Nekala",
     "kind": "hall", "capacity": {"gig": 200, "sport": 0}, "hubs": ["hakametsa"], "walk_min": 8,
     "approx": False, "source": "OpenStreetMap address point"},
    {"id": "f54", "name": "F54 (ent. Fame Club)", "aliases": ["f54", "f54 (entinen fame club)", "fame club", "fomo nightclub"],
     "address": "Satakunnankatu 18", "lat": 61.5010994, "lon": 23.7610188, "area": "Keskusta",
     "kind": "club", "capacity": {"gig": 300, "sport": 0}, "hubs": ["tulli"], "walk_min": 4,
     "approx": True, "source": "OpenStreetMap address point"},
]
missing = [x for x in new_venues if x["id"] not in have]
if missing:
    lines = ",\n".join("    " + json.dumps(x, ensure_ascii=False) for x in missing)
    text = text.replace("\n  ]\n}", ",\n" + lines + "\n  ]\n}", 1)
    print(f"  added {len(missing)} venues")
else:
    print("  venues already present")
text = text.replace(
    '"tamk games academy", "solun sauna"]',
    '"tamk games academy", "solun sauna", "clint", "club international tampere"]',
)
write(venues_path, text)

# ---------------------------------------------------------------- zones
zones_path = "registry/zones.json"
text = read(zones_path)
tram = {"keskusta", "tammela", "kaleva", "hervanta", "lentavanniemi", "lielahti",
        "sarkanniemi", "hatanpaa", "hiedanranta"}
rail = {"nokia", "lempaala", "akaa", "orivesi", "muu_suomi"}
for zid in re.findall(r'\{ "id": "([a-z_]+)"', text):
    if '"transit_mode"' in text.split(f'{{ "id": "{zid}"', 1)[1].split("\n", 1)[0]:
        continue
    mode = "tram" if zid in tram else "rail" if zid in rail else "bus"
    text = re.sub(
        r'(\{ "id": "%s".*?)( \},?)$' % re.escape(zid),
        r'\1, "transit_mode": "%s"\2' % mode,
        text, count=1, flags=re.M,
    )
write(zones_path, text)
print("  zones transit_mode")

# ---------------------------------------------------------------- feeds
adapter = read("scripts/feeds/city_events.py")
if "def fetch(" in adapter:
    write("scripts/feeds/tampere_city.py", adapter)
    print("  tampere_city.py written from city_events.py")
    write("scripts/feeds/city_events.py", '''"""Backward-compat shim: the adapter now lives in ``tampere_city``.

Kept so older imports keep working; delegates entirely to ``tampere_city``.
"""
from feeds import tampere_city as _tc  # noqa: E402

fetch = _tc.fetch
URL = _tc.URL
TZ = _tc.TZ
MAX_EVENTS = _tc.MAX_EVENTS
''')
    print("  city_events.py shim")
else:
    print("  feeds already migrated")

# ---------------------------------------------------------------- web
c = read("web/config.js")
c = replace_once(c, '  MODEL_VERSION: "2026.11.2",', '  APP_VERSION: "0.12.3",\n  MODEL_VERSION: "2026.11.5",', "config version")
write("web/config.js", c)

h = read("web/index.html")
h = replace_once(
    h,
    '<div class="eyebrow">Manse — estimated crowd flow</div>',
    '<div class="eyebrow"><span>Manse — estimated crowd flow</span><span id="buildBadge" class="build-badge"></span></div>',
    "index badge",
)
write("web/index.html", h)

s = read("web/styles.css")
s = replace_once(
    s,
    ".eyebrow{width:100%;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.18em;\n  text-transform:uppercase;color:var(--teal);}",
    ".eyebrow{width:100%;font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.18em;\n  text-transform:uppercase;color:var(--teal);display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;}\n.build-badge{font-size:9px;letter-spacing:.08em;text-transform:none;color:var(--paper-dim);opacity:.8;}",
    "styles badge",
)
write("web/styles.css", s)

a = read("web/app.js")
a = replace_once(
    a,
    '''    pill.querySelector(".status-text").textContent = meta.generated
      ? `Estimated flow model · rebuilt ${stamp(meta.generated)}`
      : "Bundled snapshot";
  }''',
    '''    pill.querySelector(".status-text").textContent = meta.generated
      ? `Estimated flow model · rebuilt ${stamp(meta.generated)}`
      : "Bundled snapshot";
    const badge = $("buildBadge");
    if (badge) {
      badge.textContent = `v${CFG.APP_VERSION || "?"} · updated ${meta.generated ? stamp(meta.generated) : "bundled"}`;
    }
  }''',
    "app badge",
)
write("web/app.js", a)

# ---------------------------------------------------------------- docs
g = read("AGENTS.md")
g = replace_once(
    g,
    "registry and never guessed.\n\n### Addresses",
    "registry and never guessed.\n\nEach district in `registry/zones.json` carries a `transit_mode` (`tram`, `bus` or `rail`). It\ncolours the corridor that district's people arrive along: close districts walk/bike, farther ones\nfollow their tram, bus or train, and the venue's own hub is only a fallback.\n\n### Addresses",
    "AGENTS transit note",
)
write("AGENTS.md", g)

ver = read("VERSIONS.md")
section = """### 0.12.3 — 2026-11-15
Event size and venue size now shape the heat, and districts ride their own transit.

- Added: `event_capacity()` in `scripts/build.py` derives an event-level crowd size from the source
  when it can: the city calendar's published `maxParticipants` (capped to the venue's own capacity)
  and Kide title keywords (`treenit`/practice -> a small group of up to 60 instead of the whole
  hall). Otherwise it keeps the venue capacity prior.
- Fixed: a student practice at a big arena (`TTO x PIRATE Kyykkätreenit` at Hakametsä) no longer
  inherits the arena's thousands of seats; big gigs, matches and parties keep their real size. The
  gravity catchment class uses the same event capacity, so the practice no longer pulls from the
  whole province either.
- Added: a venue-size class prior in `attendance_est()` (arena/hall 1.06-1.10x, small pub/bar 0.95x)
  so a big-venue evening reads larger than a small pub or bar even at the same fill. It uses the
  event's own capacity, so a practice booked in an arena stays small.
- Changed: far districts draw their own transit corridor to the venue instead of collapsing onto the
  venue's single hub. Each zone carries a `transit_mode` (tram/bus/rail) in `registry/zones.json`:
  Hervanta -> tram, Tesoma/Pirkkala/Kaukajärvi -> bus, Nokia/Lempäälä -> train; short district legs
  stay walk/bike.
- Added: 5 verifiable Kide venues (Bar Tullari, H5 Bar, Megazone, Rush, F54/Fame Club) plus a CLINT
  alias on TAMK, with real OSM address points; published student rows 38 -> 47.
- Added: the site shows a small `v0.12.3 · updated ...` badge in the top-left, fed by the build
  timestamp, so the running version and the last rebuild are visible.
- Model version 2026.11.5.

"""
ver = replace_once(ver, "## App\n\n### 0.12.2", "## App\n\n" + section + "### 0.12.2", "VERSIONS 0.12.3")
write("VERSIONS.md", ver)

todo = read("TODO.md")
todo = replace_once(
    todo,
    """- [ ] Event scale: a student practice at an arena currently inherits the arena's capacity, so the
      estimate reads in the thousands. Needs a per-event size signal (ticket stock, practice /
      treenit keyword) before that figure means anything.
- [ ] Small-venue events (library talks, workshops) use the 20-person floor; a size signal from the
      calendar's `maxParticipants` should feed the fill prior instead""",
    """- [x] Event scale: student practices (Kide `treenit`/practice keywords) no longer inherit the
      arena capacity; they estimate a small group (up to 60), while big gigs/matches/parties keep
      their real relative size (`event_capacity()` in `build.py`).
- [x] Calendar `maxParticipants` feeds the per-event size when published (capped to venue capacity);
      events without it keep the venue prior rather than a fabricated number.
- [x] Venue-size class prior: big halls/arenas read 6-10 % fuller than the same capacity would
      imply, small pubs/bars 5 % lower, so venue size shows in the heat beyond raw capacity.""",
    "TODO model items",
)
todo = replace_once(
    todo,
    """- [ ] Student: Ankkuri (3 products), Antura, Megazone, CLINT and Bar Tullari publish no street
      address anywhere, so those products stay dropped — a real address or nothing""",
    """- [x] Student: added Bar Tullari, H5 Bar, Megazone, Rush, F54/Fame Club and a CLINT alias on TAMK
      with real OSM address points; published student rows 38 → 47. Ankkuri, Antura, Tarkka and the
      organiser-only names still publish no verifiable venue and stay dropped.""",
    "TODO student venues",
)
todo = replace_once(
    todo,
    """- [x] Route cache complete: every venue has a hub, every flow draws real street geometry
      (0 corridor-only flows, 0 legs under 50 m; 3,150 legs over 7,050 km)""",
    """- [x] Route cache complete: every venue has a hub, every flow draws real street geometry
      (0 corridor-only flows, 0 legs under 50 m; 3,150 legs over 7,050 km)
- [x] Transit corridors by district: each zone's `transit_mode` (tram/bus/rail) colours the
      corridor it sends people along, so far districts no longer collapse onto the venue's one hub""",
    "TODO transit done",
)
todo = todo.replace("today that is 38 of 67", "today that is 47 of 67")
todo = replace_once(
    todo,
    """- **A student event at a big venue inherits that venue's capacity.** `TTO x PIRATE Kyykkätreenit`
  runs at Hakametsän jäähalli, so the fill prior multiplies a several-thousand-seat capacity and the
  page estimates thousands of people for a practice. The range is published with `≈` and the same
  caveat as every other figure, but treat it as an upper bound until the model has a size signal.""",
    """- **A practice no longer inherits the arena.** `TTO x PIRATE Kyykkätreenit` at Hakametsän jäähalli
  now estimates a small group (up to 60) from the Kide `treenit` keyword; other events at big venues
  keep their real size.""",
    "TODO known issue",
)
write("TODO.md", todo)

if not os.path.exists(os.path.join(ROOT, ".gitignore")):
    write(".gitignore", "__pycache__/\n*.pyc\n.DS_Store\n.venv/\nnode_modules/\n*.log\nartifacts/\n")
    print("  .gitignore")

print("model update applied")
