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
- [x] Every published event resolves to a venue with a real address: a street address found in a
      row now outranks the generic fallback, and Finlaysonin kirkko (Puuvillatehtaankatu 2) is
      registered with its OSM coordinates and the parish's published capacity
- [x] Sunday retry cron (`0 6 * * 0`) after the weekly 04:00 rebuild
- [x] A total feed failure keeps the last good data: the build refuses to write an empty
      map and exits non-zero, so the workflow stops before committing or deploying
- [x] City calendar adapter: `scripts/feeds/city_events.py` publishes stage, culture, library
      and community events (217 today) with the calendar's own coordinates and addresses
- [x] Calendar locations outside the registry become real generated venues (published point,
      address, nearest district and hub) instead of falling back to `tampere_muu`
- [x] Far venues (Kangasala, Nokia, Hämeenkyrö) fall back to their nearest districts, so they
      no longer produce an event with no origin zones
- [x] Route cache complete: every venue has a hub, every flow draws real street geometry
      (0 corridor-only flows, 0 legs under 50 m; 3,150 legs over 7,050 km)
- [x] Transit corridors by district: each zone's `transit_mode` (tram/bus/rail) colours the
      corridor it sends people along, so far districts no longer collapse onto the venue's one hub
- [x] Student venues: 21 student-party venues registered on their OpenStreetMap address points
      (Laulumaja, Save File, TAMK, Pii-klubi, Pursiseura, Juhlatalo Tapiola, Kamula, Ylioppilas-
      teatteri and the nightclubs Kide uses), so published student parties went 6 → 38 of 67
- [x] Gig addresses: 13 registry venues carried a district name where the address belongs and sat
      up to 3 km off; every one now has its street address and address point (Terassi Pub Yläkerta
      alone was 10 gigs, plotted in the city centre instead of Pispalan valtatie 39)
- [x] The panel and the row list show `venue · address`, so a dot's address is visible on the site

## Next

### Feeds (highest value)
- [x] `feeds/city_events.py` — the whole public calendar in one call
      (`api/search/internal-content-fetch?lang=fi&country=FI&q=`), which also covers the library
      programme; topic-by-topic walking is no longer needed
- [ ] City calendar: per-event size signal, so a library talk and a Tampere-talo gala do not both
      read as the small-venue floor
- [x] Student: `scripts/feeds/kide.py` reads Kide's public Tampere product list (real start and
      end times) and `kide_rows()` in `build.py` places each product on a registry venue
- [x] Student: the venues Kide names are now in the registry with OSM address points (Laulumaja,
      Save File, Tampereen Ylioppilasteatteri, Juhlatalo Tapiola, Pursiseura, Pii-klubi, Kamula,
      TAMK, YTHS-sauna, Mixei, ZBase, Ilona, Galaxie, Bricks, Kaijakka, Onda, Sherlock Holmes,
      Kultainen Apina, Koskikeskus, Messukylän työväentalo, Hatanpään soutupaviljonki)
- [x] Student: added Bar Tullari, H5 Bar, Megazone, Rush, F54/Fame Club and a CLINT alias on TAMK
      with real OSM address points; published student rows 38 → 47. Ankkuri, Antura, Tarkka and the
      organiser-only names still publish no verifiable venue and stay dropped.
- [ ] `feeds/trey.py` — treykalenteri.fi serves a JS app over HTML with no public JSON (the
      WordPress REST and Tribe endpoints return the app shell), so it would need a headless parse
- [ ] Sports: basket.fi, pesistulokset.fi, F-liiga, Veikkausliiga adapters
- [ ] `feeds/ticketmaster.py` — Discovery API, `countryCode=FI` (needs free key)
- [ ] `feeds/longtail.py` — Tampere-talo, Nokia Arena, Särkänniemi, Vapriikki,
      TTT/Komediateatteri/Telakka, seurakunnat, markets
- [ ] Retire `data/seed_events.json` entirely once a student and a culture/venue adapter exist

### Model
- [ ] `calibration.py` — scrape reported league attendance, fit fill factors, publish backtest error
- [ ] Competition factor (two big events same evening split the same catchment)
- [ ] Parking / tram capacity ceilings on car and transit shares
- [ ] Student-night egress: model last-service cutoff instead of a flat tail
- [x] Event scale: student practices (Kide `treenit`/practice keywords) no longer inherit the
      arena capacity; they estimate a small group (up to 60), while big gigs/matches/parties keep
      their real relative size (`event_capacity()` in `build.py`).
- [x] Calendar `maxParticipants` feeds the per-event size when published (capped to venue capacity);
      events without it keep the venue prior rather than a fabricated number.
- [x] Venue-size class prior: big halls/arenas read 6-10 % fuller than the same capacity would
      imply, small pubs/bars 5 % lower, so venue size shows in the heat beyond raw capacity.

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
  product is only published when its place is already a registry venue; today that is 47 of 67. The
  rest are dropped and logged, never placed on a guessed address.
- **A practice no longer inherits the arena.** `TTO x PIRATE Kyykkätreenit` at Hakametsän jäähalli
  now estimates a small group (up to 60) from the Kide `treenit` keyword; other events at big venues
  keep their real size.
- **Calendar venues have no capacity.** The city calendar publishes a point and an address, not a
  hall size, so those events sit on the model's small-venue floor unless the listing carries
  `maxParticipants`. Big calendar events at registry venues (Tampere-talo, Vapriikki, Nokia Arena)
  keep their real capacity.
- **New venues get their capacity from the class prior.** Laulumaja, Save File, the nightclubs and
  the rest carry a `gig` capacity nobody publishes (150-300 seats); treat those figures as priors.
- **Four places still have no house number on the map.** Monttu (its address is not published
  anywhere), Bricks (Hämeenkatu, no number in OSM), Valkeakosken kesäteatteri, and the calendar
  venues that are parks or squares by nature (Keskustori, Hämeenpuisto). They keep an approximate
  point and `approx: true`.
- **Calendar routes are seeded by CI.** New venues get their legs from the bounded fetch in the
  workflow (`--max 1500`); until that runs, a brand-new venue uses the straight fallback.
- **Music, Liiga hockey, Kide student events and the city calendar are published.** Stage, culture
  and community rows come only from the calendar plus the registry venues it names, so a venue that
  lists nowhere else can still be missing.
- **Coordinates are approximate** (100–300 m) for venues not individually verified; the venues
  added in 0.12.2 use their OpenStreetMap address point.
- **Mode split is a distance heuristic**, not real routes. Treat shares as indicative.
- **`tampere-keikat` feed only contains music**, and only future events.
- **liiga.fi schedule** is now read from `api/v2/games`; the contract is undocumented and may move.
- **Kide's API** is likewise undocumented (`api.kide.app/api/products?city=Tampere`); a shape
  change shows up as `source_status.student` = `FAILED`, not as a broken page.
- **The city calendar API** is undocumented too
  (`api/search/internal-content-fetch?lang=fi&country=FI&q=`), needs both parameters and the
  calendar's own host, and returns the whole calendar in one ~3 MB response. A shape change shows
  up as `source_status.culture` = `FAILED`.
- **Tile provider policy**: the default OSM tile service is fine for a small site but has no
  SLA; swap `TILE_URL` for a paid/self-hosted provider if traffic grows.

## Decisions

- Google Maps basemap via Maps JavaScript API; **no** `visualization.HeatmapLayer` (deprecated 2025,
  removal announced for May 2026). Overlay is a dependency-free canvas layer, so no CDN failure mode.
- Heat ramp: dark red = more likely origin, pale rose = less likely; 1 % floor; light basemap
  while heat is shown.
- Corridor geometry comes from our own zone→hub→venue model, never stored Google Directions content.
- Estimates are never written back as observations.
- A feed's place string is never turned into coordinates by guesswork: if the venue registry does
  not already hold that venue and its address, the event is dropped and logged — except when the
  feed itself publishes the point and the address, which is what the city calendar does.
- A registry venue's address is a **street address from OpenStreetMap**, never a district name; the
  UI shows it, so a vague address is a visible bug rather than a private shortcut.
