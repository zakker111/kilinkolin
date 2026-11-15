# TODO — Kilinkolin

## Done

- [x] Repo scaffold: MIT licence, NOTICE, AGENTS, README, VERSIONS
- [x] Venue registry — 46 Tampere venues, coordinates, capacities, areas, hubs
- [x] Zone registry — 26 districts + 13 municipalities/Pirkanmaa bands
- [x] Pipeline: music feed ingest, venue alias resolution, taxonomy, crowd class
- [x] Interest score with signal breakdown
- [x] Attendance priors with ranges (Crown class A/B/S/C)
- [x] Gravity origin split, mode split, corridor geometry, arrival/egress curves
- [x] Flow map only: keyless OSM tile basemap with own pan/zoom, canvas heat/corridor/arrival
      overlay, four presets, time scrubber, per-event vs global scale, legend
- [x] Date picker + event selector, side panel with attendance, interest, origins, modes
- [x] Heat verified rendering over Tampere tiles (see screenshots in `artifacts/`)
- [x] Removed calendar/list/checklist views at the author's request
- [x] Reduced the site to heat map + estimate only; "how they arrive" is a mode-coloured heat layer
- [x] Simplified to day + hour controls: no event listing, heat aggregates every event at that moment
- [x] Transit corridors for districts beyond walking range (tram/bus/train along the road network)
- [x] Street-level heat: walking legs routed over OSM footways, cached (401 legs, 906 km), drawn as
      weighted bands instead of district blobs
- [ ] Route from individual tram/bus stops rather than district centroids and hubs
- [ ] Cache invalidation: `routes.py --refresh` when venues change coordinates
- [ ] Mode split is a distance heuristic — Nokia Arena gets 24 % car despite the adjacent station;
      calibrate against real HSL/Digitransit trip data before trusting the shares
- [x] Validation gate + GitHub Actions workflow (daily sync, weekly rebuild, Pages deploy)
- [x] Scheduled refresh fetches route geometry for new origins before deploying, so weekly
      updates keep the street heat instead of straight lines
- [x] Every event contributes: no-time rows count at 19:00, daytime and after-midnight events are
      reachable on the scrubber, and arrival windows match the chosen minute
- [x] Event dots: gigs red, sports blue, student amber; tap a dot for title, time and venue
- [x] Phone layout: stacked controls, larger touch targets, viewport-sized map, no sideways scroll
- [x] Sports adapter: Liiga public game list, Ilves/Tappara home games at Nokia Arena

## Next

### Feeds (highest value)
- [ ] `feeds/city_events.py` — walk `tapahtumat.tampere.fi` topic IDs (library topic
      `677f933068bf7f5f79171c68` verified), plus `tampere.fi/api/eventz-today/<paragraph>` sections
- [ ] `feeds/students.py` — treykalenteri (HTML, no WP REST), Tamko, Yo-talo, Kide
- [x] Sports: Liiga JSON (Ilves/Tappara home games) lives in `fetch_liiga` in `build.py`
- [ ] Sports: basket.fi, pesistulokset.fi, F-liiga, Veikkausliiga adapters
- [ ] Student: still blocked — TREY calendar is a JS app over an unauthenticated Strapi API;
      Kide's public API has no Tampere locality filter
- [ ] `feeds/ticketmaster.py` — Discovery API, `countryCode=FI` (needs free key)
- [ ] `feeds/longtail.py` — Tampere-talo, Nokia Arena, Särkänniemi, Vapriikki,
      TTT/Komediateatteri/Telakka, seurakunnat, markets
- [ ] Replace every `SAMPLE` row in `data/seed_events.json` with real adapter output

### Model
- [ ] `calibration.py` — scrape reported league attendance, fit fill factors, publish backtest error
- [ ] Competition factor (two big events same evening split the same catchment)
- [ ] Parking / tram capacity ceilings on car and transit shares
- [ ] Student-night egress: model last-service cutoff instead of a flat tail

### Map
- [ ] District boundary polygons instead of centroid blobs
- [ ] Corridors routed along street/hub geometry instead of straight segments
- [ ] Optional satellite or paid tile provider behind `TILE_URL`
- [ ] "Open route in Google Maps" deep link per corridor
- [ ] Pinch-zoom for touch devices (buttons and wheel work now)

### Platform
- [ ] Multi-city: `registry/cities/<city>.json`, Helsinki next
- [ ] Digitransit travel times instead of the distance/speed approximation
- [ ] Methods page with fill-factor table and assumptions

## Known issues

- **Sports/student/theatre/library rows are `SAMPLE` placeholders.** Clearly badged in the UI.
- **Coordinates are approximate** (100–300 m) for venues not individually verified.
- **Mode split is a distance heuristic**, not real routes. Treat shares as indicative.
- **`tampere-keikat` feed only contains music**, and only future events.
- **liiga.fi schedule** is now read from `api/v2/games`; the contract is undocumented and may move.
- **Student parties are still `SAMPLE`** — no dependable public Tampere feed found yet.
- **Tile provider policy**: the default OSM tile service is fine for a small site but has no
  SLA; swap `TILE_URL` for a paid/self-hosted provider if traffic grows.
- **Corridors are schematic** straight-ish lines, not street routing.

## Decisions

- Google Maps basemap via Maps JavaScript API; **no** `visualization.HeatmapLayer` (deprecated 2025,
  removal announced for May 2026). Overlay is a dependency-free canvas layer, so no CDN failure mode.
- Heat ramp: dark red = more likely origin, pale rose = less likely; 1 % floor; light basemap
  while heat is shown.
- Corridor geometry comes from our own zone→hub→venue model, never stored Google Directions content.
- Estimates are never written back as observations.
