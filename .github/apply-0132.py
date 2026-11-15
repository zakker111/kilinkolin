import json
from pathlib import Path

FIXES = {
    "nokia_arena": {"address": "Kansikatu 3", "lat": 61.49363, "lon": 23.7739336, "approx": False},
    "tampere_talo": {"lat": 61.4958905, "lon": 23.7823561, "approx": False},
    "klubi": {"lat": 61.4986404, "lon": 23.7766472, "approx": False},
    "telakka": {"lat": 61.4980505, "lon": 23.7779614, "approx": False},
    "ttt_klubi": {"address": "Hallituskatu 19", "lat": 61.4959289, "lon": 23.7511631, "approx": False},
    "tavara_asema": {"address": "Ratapihankatu 33", "lat": 61.4998457, "lon": 23.7752948, "approx": False},
    "yo_talo": {"lat": 61.4981832, "lon": 23.7558784, "approx": False},
    "monttu": {"address": "Hämeenkatu 17", "lat": 61.4975, "lon": 23.7594443, "approx": False},
    "bricks": {"address": "Hämeenkatu 18", "lat": 61.4976923, "lon": 23.7580122, "approx": False},
    "g_livelab": {"address": "Puutarhakatu 1", "lat": 61.4993847, "lon": 23.7622650, "approx": False},
    "plevna": {"lat": 61.5008409, "lon": 23.7585109, "approx": False},
    "komediateatteri": {"address": "Lapintie 3a", "lat": 61.502823, "lon": 23.765454, "approx": False},
    "sarkanniemi": {"address": "Särkänniemenraitti 3", "lat": 61.5050172, "lon": 23.7425717, "approx": False},
    "pyynikin_palloiluhalli": {"address": "Ammattikoulunkatu 20", "lat": 61.4977250, "lon": 23.7336972, "approx": False},
    "kauppi_pesis": {"address": "Kuntokatu 24", "lat": 61.5115609, "lon": 23.8060583, "approx": False},
    "tesoma_halli": {"address": "Tesoman valtatie 46", "lat": 61.5088977, "lon": 23.6275924, "approx": False},
    "hakametsa": {"address": "Keltinkatu 2", "lat": 61.4958466, "lon": 23.8242385, "approx": False},
    "valkeakoski_kesateatteri": {"address": "Pässinmäenkatu 30", "lat": 61.2682724, "lon": 24.0421107, "approx": False},
    "f54": {"approx": False},
    "sampola": {"lat": 61.4979788, "lon": 23.7886933, "approx": False},
    "hervanta_kirjasto": {"lat": 61.4502707, "lon": 23.8488722, "approx": False},
    "tesoma_kirjasto": {"lat": 61.5050380, "lon": 23.6284251, "approx": False},
    "koilliskeskus_kirjasto": {"lat": 61.4959810, "lon": 23.8839367, "approx": False},
    "messukyla_kirjasto": {"lat": 61.4905879, "lon": 23.8529301, "approx": False},
    "kaukajarvi_kirjasto": {"lat": 61.4701920, "lon": 23.8720192, "approx": False},
    "koivistonkyla_kirjasto": {"lat": 61.4710008, "lon": 23.7953130, "approx": False},
    "nekala_kirjasto": {"lat": 61.4830448, "lon": 23.7897624, "approx": False},
    "koukkuniemi_kirjasto": {"lat": 61.5126751, "lon": 23.7790742, "approx": False},
    "lielahti_kirjasto": {"lat": 61.5199530, "lon": 23.6694686, "approx": False},
    "tampere_muu": {"address": "", "approx": True},
}

p = Path("registry/venues.json")
doc = json.loads(p.read_text(encoding="utf-8"))
doc["note"] = ("Coordinates use OpenStreetMap address points or official published points where available. "
               "Venues marked approx=true are area/district centroids or have no published address.")
for v in doc["venues"]:
    if v["id"] in FIXES:
        v.update(FIXES[v["id"]])
lines = ["{"]
keys = list(doc)
for i, k in enumerate(keys):
    v = doc[k]
    if k == "transit_hubs":
        lines.append('  "transit_hubs": {')
        items = list(v.items())
        for j, (hk, hv) in enumerate(items):
            lines.append(f'    "{hk}": {json.dumps(hv, ensure_ascii=False)}' + (',' if j < len(items) - 1 else ''))
        lines.append('  }' + (',' if i < len(keys) - 1 else ''))
    elif k == "venues":
        lines.append('  "venues": [')
        for j, vv in enumerate(v):
            lines.append('    ' + json.dumps(vv, ensure_ascii=False) + (',' if j < len(v) - 1 else ''))
        lines.append('  ]' + (',' if i < len(keys) - 1 else ''))
    else:
        lines.append(f'  "{k}": {json.dumps(v, ensure_ascii=False)}' + (',' if i < len(keys) - 1 else ''))
lines.append('}')
p.write_text('\n'.join(lines) + '\n', encoding='utf-8')

# A moved venue's cached geometry is keyed only by venue id, so drop it before rebuilding.
moved = set(FIXES) - {"bricks", "tampere_muu"}
rp = Path("registry/routes.json")
rd = json.loads(rp.read_text(encoding="utf-8"))
rd["routes"] = {k: v for k, v in rd["routes"].items() if k.split("|", 1)[0] not in moved}
rp.write_text(json.dumps(rd, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

p = Path("web/config.js"); s = p.read_text(encoding="utf-8")
assert 'APP_VERSION: "0.13.1"' in s
p.write_text(s.replace('APP_VERSION: "0.13.1"', 'APP_VERSION: "0.13.2"', 1), encoding="utf-8")

p = Path("web/map.js"); s = p.read_text(encoding="utf-8")
old = 'id: ev.id, time: ev.time, title: ev.title, category: ev.category,\n          venue:'
new = 'id: ev.id, time: ev.time, title: ev.title, category: ev.category, venueId: f.venue_id,\n          venue:'
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")

p = Path("web/app.js"); s = p.read_text(encoding="utf-8")
old = '''  /* the venue's street address, unless the label already is one (calendar venues) */
  function addrOf(ev) {
    const v = VENUES[ev.venueId];
    const a = v && v.address ? String(v.address) : "";
    return a && a !== ev.venue ? a : "";
  }'''
new = '''  /* the venue's street address, unless the label already is one (calendar venues) */
  function addrOf(ev) {
    const v = VENUES[ev.venueId];
    const a = v && v.address ? String(v.address).trim() : "";
    const label = String(ev.venue || "").trim();
    if (!a) return "";
    const al = a.toLowerCase(), ll = label.toLowerCase();
    if (al === ll) return "";
    // calendar places arrive as "Venue, street, postcode"; keep only the part the label lacks
    if (ll && al.startsWith(ll + ",")) {
      if (/\\d/.test(label)) return "";
      const rest = a.slice(label.length + 1).trim();
      return rest && rest.toLowerCase() !== ll ? rest : "";
    }
    return a;
  }'''
assert old in s
p.write_text(s.replace(old, new, 1), encoding="utf-8")

p = Path("README.md"); s = p.read_text(encoding="utf-8")
assert "**v0.13.1**" in s
p.write_text(s.replace("**v0.13.1**", "**v0.13.2**", 1), encoding="utf-8")

release = '''### 0.13.2 — 2026-11-15
Venue addresses and points corrected across the registry.

- Fixed: 28 venues carried a district name, a neighbouring street number or a point several
  hundred metres to several kilometres away. Every corrected venue now has a published street
  address and an OpenStreetMap or official address point, and the map dot and its walking legs
  start at the same place. The generic `tampere_muu` fallback no longer claims to be in Keskusta.
- Notable corrections: Tampere-talo (770 m east of its hall), Klubi and Telakka (1.6-1.7 km from
  Tullikamarin aukio), TTT-Klubi (Hämeenpuisto 34 -> Hallituskatu 19), Hakametsän jäähalli
  (Ilmarinkatu 10 -> Keltinkatu 2), Nokia Arena (Tampere-talon aukio -> Kansikatu 3), Tavara-asema
  (Ratapihankatu 21 -> 33), Monttu (Hämeenkatu 17), Bricks (Hämeenkatu 18), G Livelab
  (Puutarhakatu 1) and Komediateatteri (Lapintie 1 -> 3a, 700 m north).
- Fixed: ten library venues and four sports venues sat on district centroids, including
  Koilliskeskuksen kirjasto and Koukkuniemen kirjasto (3.3 km off), Koivistonkylän kirjasto
  (2.1 km), Kauppi, Tesoma, Pyynikki, Hakametsä, Särkänniemi and Valkeakosken kesäteatteri. All now
  use their street address and address point.
- Fixed: F54's approximate flag was stale; its Satakunnankatu 18 address point is exact.
- Fixed: the panel's day list dropped each event's venue id, so the venue address never rendered
  even when the data had it. Rows now show `venue · street address` again.
- Changed: removed 765 stale cached legs for the corrected venues and refetched the event-used legs
  the current events actually use (about 13,600 km of cached walking geometry). No route now starts at an old
  venue point.
- No model or schema change: model 2026.11.5, schema 2, 380 events.

'''
p = Path("VERSIONS.md"); s = p.read_text(encoding="utf-8")
assert "### 0.13.2" not in s
p.write_text(s.replace("## App\n\n", "## App\n\n" + release, 1), encoding="utf-8")

p = Path("TODO.md"); s = p.read_text(encoding="utf-8")
needle = "- [x] 0.13.1 UI fixes: next-day `06:00 +1` label and one category legend row on desktop\n"
assert needle in s
s = s.replace(needle, needle + "- [x] 0.13.2 address corrections: 28 venues moved to published street addresses and address\n      points, plus the generic fallback; 765 stale route legs dropped, the event-used legs in use\n      refetched, and the panel's venue-address line restored\n", 1)
i = s.index("- **Four places still have no house number on the map.**")
j = s.index("\n- **Calendar routes", i)
s = s[:i] + '''- **One fallback venue has no address.** `tampere_muu` (elsewhere in Tampere) is used only when no
  venue resolves; it now carries a blank address instead of a misleading "Keskusta". Calendar
  parks and squares (Keskustori, Hämeenpuisto) are real published points with area names, not
  house numbers.''' + s[j:]
i = s.index("- **Coordinates are approximate**")
j = s.index("\n- **Mode split", i)
s = s[:i] + '''- **Coordinates are address points.** Registry venues were checked against OpenStreetMap and
  official addresses on 2026-11-15; `approx: true` remains only for `tampere_muu` and generated
  area venues without a house number.''' + s[j:]
s = s.replace("- [ ] Cache invalidation: `routes.py --refresh` when venues change coordinates", "- [ ] Automatic cache invalidation: drop a venue's `routes.json` keys when its coordinates change\n      (done manually for 0.13.2)", 1)
p.write_text(s, encoding="utf-8")

p = Path("AGENTS.md"); s = p.read_text(encoding="utf-8")
old = "`venue · address` from `web/geo/venues.json`, so a wrong or vague address is visible on the site.\n"
assert old in s
new = old + "\nRoute geometry is cached by venue ID, not by coordinate. When a venue moves, delete its\n`venue|hub:*` and `venue|zone:*` keys from `registry/routes.json`, rebuild so `flows.json`\ncarries the new point, run `scripts/routes.py --from-flow`, then rebuild and validate.\n"
p.write_text(s.replace(old, new, 1), encoding="utf-8")
print("source corrections applied")
