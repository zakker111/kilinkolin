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
- [x] Feed end times: the Liiga adapter passes the playing time when a game carries one, so the
      hockey egress curve uses a real end instead of the 150-minute default
- [x] Sample data removed from the live build — `--with-samples` is the only way to load
      `data/seed_events.json`, and `validate.py` fails if any published row looks like a placeholder
- [x] Right-hand panel: the chosen day's events in start order, the one under the pointer expanded,
      rows and map dots highlighting each other, "occurring now" marked from the chosen hour
- [x] Fixed: the legend markup held a duplicated swatch block, and the swatch styles only loaded
      under the phone media query, so the desktop legend lost a row
- [x] Fixed: hovering a dot never showed anything (only taps did) and a tooltip could stay stuck
      over an empty patch of map
- [x] Student adapter: Kide public product list, real start and end times, strict venue matching
      (unplaceable products dropped and logged, never guessed)
- [x] Student rows carry the real end minute from the feed (sitsit, gaala, sauna evening), so their
      egress curve no longer uses the 300-minute default

## Next

### Feeds (highest value)
- [ ] `feeds/city_events.py` — walk `tapahtumat.tampere.fi` topic IDs (library topic
      `677f933068bf7f5f79171c68` verified), plus `tampere.fi/api/eventz-today/<paragraph>` sections
- [x] Student: `scripts/feeds/kide.py` reads Kide's public Tampere product list (real start and
      end times) and `kide_rows()` in `build.py` places each product on a registry venue
- [ ] Student: add the venues Kide names that the registry does not have yet (Laulumaja, Save File,
      Ankkuri, Tampereen Yliopistoteatteri…), each with a real address and a published capacity —
      61 of 67 current products are dropped for an unknown place rather than guessed
- [ ] `feeds/students.py` — treykalenteri (HTML, no WP REST), Tamko, Yo-talo
- [x] Sports: Liiga JSON (Ilves/Tappara home games) lives in `fetch_liiga` in `build.py`
- [ ] Sports: basket.fi, pesistulokset.fi, F-liiga, Veikkausliiga adapters
- [x] Student: Kide's public product list works with `?city=Tampere` (67 future products, 11 of
      them naming a known venue) and is now the `student` source
- [ ] `feeds/ticketmaster.py` — Discovery API, `countryCode=FI` (needs free key)
- [ ] `feeds/longtail.py` — Tampere-talo, Nokia Arena, Särkänniemi, Vapriikki,
      TTT/Komediateatteri/Telakka, seurakunnat, markets
- [ ] Retire `data/seed_events.json` entirely once a student and a culture/venue adapter exist

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

- **Student events are matched, not geocoded.** Kide gives a place name but no coordinates, so a
  product is only published when its place is already a registry venue; today that is 6 of 67. The
  rest are dropped and logged, never placed on a guessed address.
- **Music, Liiga hockey and Kide student events are published.** Stage, culture and community
  adapters are still unwired, and their `SAMPLE` rows stay out of the build, so those categories
  are empty.
- **Coordinates are approximate** (100–300 m) for venues not individually verified.
- **Mode split is a distance heuristic**, not real routes. Treat shares as indicative.
- **`tampere-keikat` feed only contains music**, and only future events.
- **liiga.fi schedule** is now read from `api/v2/games`; the contract is undocumented and may move.
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
