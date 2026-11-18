# TODO — Kilinkolin

## Done

- [x] 0.16.7 stable event detail slot: hovering a row keeps the list in place instead of sliding
      it under the pointer and selecting a neighbour, and on phones the tapped event's card stays
      pinned at the top of the event panel instead of scrolling away above it, and a tapped map
      dot is no longer cleared by the finger lift's `pointerleave`
- [x] 0.16.6 mobile Why sheet and address provenance: bottom-sheet explanation, one-scroll phone
      panel, cached day-data fallback and official Metso/Megazone/Valkeakoski addresses
- [x] 0.16.5 mobile typography and robustness: larger phone type, keyboard event rows, day-bundle
      fallback, safe timestamp parsing and sanitized Why-panel ids
- [x] Repo scaffold: MIT licence, NOTICE, AGENTS, README, VERSIONS
- [x] Venue registry — 46 Tampere venues, coordinates, capacities, areas, hubs
- [x] Audited Tampere capacities against LiveFIN's Venuelista on 2026-11-16; split Tullikamari
      Klubi/Pakkahuone and kept Sin City unknown instead of inheriting H5's 150 seats
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
- [ ] Automatic cache invalidation: drop a venue's `routes.json` keys when its coordinates change
      (done manually for 0.13.2)
- [ ] Mode split is a distance heuristic — Nokia Arena gets 24 % car despite the adjacent station;
      calibrate against real HSL/Digitransit trip data before trusting the shares
- [x] Validation gate + GitHub Actions workflow (weekly sync and rebuild, Pages deploy)
- [x] CI hardening: pull-request checks; route-coverage and build-to-build churn gates; live
      Pages smoke test with last-good artifact rollback; failure issue alerts
- [x] Scheduled refresh fetches route geometry for new origins before deploying, so weekly
      updates keep the street heat instead of straight lines
- [x] Every event contributes: no-time rows count at 19:00, daytime and after-midnight events are
      reachable on the scrubber, and arrival windows match the chosen minute
- [x] Event dots: gigs red, sports blue, student amber; tap a dot for title, time and venue
- [x] Phone layout: stacked controls, larger touch targets, viewport-sized map, no sideways scroll
- [x] Mobile performance: browser route geometry simplified (3.25 MB -> 1.43 MB), canvas DPR capped
      at 1.75, normal HTTP caching, in-place panel updates and a compact legend
- [x] Map performance: padded heat bitmap reused while panning; zoom preview avoids re-rasterising
      every street on every frame (26-event day: 25.3 -> 58.2 fps at DPR 2)
- [x] Per-day payloads: `web/geo/days/<date>.json` loads only the selected day's flows and routes
      (largest day 409 KB vs the 4.2 MB full pair; full files retained for gates and fallback)
- [x] OffscreenCanvas heat worker with synchronous fallback and stale-result protection
- [x] Adaptive render quality: lower DPR while dragging/zooming/wheeling and 0.55 heat samples
      while scrubbing, restored after 160 ms idle
- [x] Cached tile composite, decimated heat traces and a cached day-event list
- [x] Self-hosted Latin WOFF2 font subsets with preloads instead of a Google Fonts connection
- [x] Mobile detection: `html.is-mobile` from viewport/pointer, a 50dvh map and four map labels
- [x] Release 0.13.0: version bump and README, NOTICE, AGENTS and TODO refreshed to the live
      day-and-hour site
- [x] 0.13.1 UI fixes: next-day `06:00 +1` label and one category legend row on desktop
- [x] 0.13.2 address corrections: 28 venues moved to published street addresses and address
      points, plus the generic fallback; 765 stale route legs dropped, the event-used legs in use
      refetched, and the panel's venue-address line restored
- [x] 0.13.3 student events: Kide product details now supply the published address and point when
      the list's free-text place does not match; 15 more student events (47 → 62), six new
      locations and their walking legs; 257 older stale legs refreshed
- [x] Browser smoke test: Playwright checks day switching, both 06:00 slider extremes and a real
      map-dot tap; the build workflow runs it before deploy
- [x] 0.13.4 completeness: removed the silent city (220) and Kide (80) row caps; all 402 eligible
      calendar rows are evaluated and 398 are published (4 duplicate a source), taking the site to
      576 events / 158 venues; the new venues' 434 walking legs were fetched, leaving 0 corridor
      fallbacks. The validator now fails on a `FAILED` source, an event venue without an address,
      or a flow without a matching event/venue.
- [x] 0.13.4 after-midnight dates: a start before 06:00 now belongs to the previous 06:00–06:00
      day strip, so midnight events are no longer drawn one day late.
- [x] 0.13.5 audit fixes: date-leaked music times (`05:12`) become missing starts; repeat city
      performances keep their separate times; Kide multi-day ends no longer create 24–107 hour
      egress windows; shared-address venue matching no longer puts Lush Koskikeskus at Ilves Bar
      & Night; after-midnight labels show `+1`/`+2`; validator covers malformed times, empty
      route caches and over-24-hour events.
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
- [x] 0.13.6 weekly-only refresh: one Sunday 04:00 UTC scheduled run; the daily 05:15 UTC sync
      and Sunday 06:00 UTC retry were removed
- [x] 0.14.0 calibration: fit the hockey fill to 20 completed Liiga games with reported
      spectators (0.85 → 0.425), publish a leave-one-out backtest (median APE 19.4 %, bias
      −7.6 %, 55 % within ±20 %), and keep city `maxParticipants` as a published cap rather
      than pretending it is measured attendance
- [x] 0.14.1 duplicate listings: exact same venue/date/title/start is merged, distinct
      showtimes are kept, and a missing start is never merged with a timed run; the validator
      rejects duplicate rows
- [x] 0.14.1 TBA starts: events with no published time are labelled Start TBA / TBA while the
      heat was modelled at 19:00; 0.15.1 replaces that single peak with the documented window
- [x] 0.14.1 regression tests: calibration states, cap edge cases, dedupe and missing-time
      handling in Python, plus TBA/cap/state checks in the browser suite
- [x] 0.15.0 competition factor: same-day events whose active windows overlap and whose
      top-zone catchments overlap by at least 50% now share one demand pool instead of each
      counting the same people; unique catchment slices stay, and a 5% floor applies. The
      factor scales attendance, legs, corridors and map dots together.
- [x] 0.15.0 competition explainability: every flow carries `basis.competition{factor,peers}`,
      the calibration block records the PRIOR method/floor/minimum overlap, and the panel shows
      a **Competition** row only when the factor is below 0.999.
- [x] 0.15.0 competition regression coverage: 6 model tests for equal/disjoint/sequential/weak
      overlaps and pool allocation, plus a browser test that opens a discounted event's working
- [x] 0.15.0 venue honesty: music rows with only a district name are dropped and logged instead
      of publishing at the unlocatable `tampere_muu` fallback
- [x] 0.15.1 TBA heat window: events without a published start keep TBA labels but average
      their arrival and egress curves over 18:00, 19:00 and 20:00 instead of a single 19:00 peak;
      flows carry `start_options` and `start_window`, and the UI names the window
- [x] 0.15.1 TBA regression: model test checks the documented start options, browser test checks
      heat is present across the window and below full demand at the 19:00 representative
- [x] 0.16.0 venue collision guard: distinct events at one venue/date/published start are
      grouped, their combined mid is capped at the smallest applicable venue capacity, and the
      cap is allocated in proportion to independent demand; TBA rows are excluded because they
      have no single published start
- [x] 0.16.0 room-split honesty: every shared group carries `basis.venue_collision` with
      `room_split: UNRESOLVED`; per-event `maxParticipants` is not treated as a room allocation,
      and the panel shows a **Venue split** row even when the group already fits
- [x] 0.16.0 collision regression: proportional-cap and below-cap model tests, a browser test for
      the capped group and panel row, plus validator recomputation of every group's combined mid
- [x] 0.16.1 heat renderer simplification: one full-quality path replaced the slider preview and
      its split cache; the heat bitmap and projected shapes share one key; removed the per-view
      route map and pan translation branch; restored overlapping stamps so zoomed heat is smooth
- [x] 0.14.0 explainability: every flow carries its capacity and fill provenance, and the
      event panel has a "Why this number?" disclosure with the attendance band, interest
      signals, Liiga backtest and city-cap coverage
- [x] Hockey capacity now uses the venue's sport capacity (Nokia Arena 13,455) rather than its
      larger concert capacity, which had inflated every Liiga estimate
- [x] A total feed failure keeps the last good data: the build refuses to write an empty
      map and exits non-zero, so the workflow stops before committing or deploying
- [x] City calendar adapter: `scripts/feeds/city_events.py` publishes stage, culture, library
      and community events (398 today) with the calendar's own coordinates and addresses; no row
      cap hides the later months
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
- [x] `calibration.py` — read Liiga reported spectators, fit the hockey fill, publish a
      leave-one-out backtest error; city `maxParticipants` is cap coverage, not a target
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

- **Student events are matched, not geocoded.** Kide's list gives a place name but no coordinates;
  unresolved products use the address and point published on the product detail. Today 62 of 64
  future products are published. Two are still dropped and logged because they have no single
  place: the VETO apartment tour (starts in Niemenranta, moves between homes) and Yrityspäivät
  (a postal box, PL 54). Neither is placed on a guessed address.
- **A practice no longer inherits the arena.** `TTO x PIRATE Kyykkätreenit` at Hakametsän jäähalli
  now estimates a small group (up to 60) from the Kide `treenit` keyword; other events at big venues
  keep their real size.
- **Calendar venues have no capacity.** The city calendar publishes a point and an address, not a
  hall size, so those events sit on the model's small-venue floor unless the listing carries
  `maxParticipants`. Big calendar events at registry venues (Tampere-talo, Vapriikki, Nokia Arena)
  keep their real capacity.
- **New venues get their capacity from the class prior.** Laulumaja, Save File, the nightclubs and
  the rest carry a `gig` capacity nobody publishes (150-300 seats); treat those figures as priors.
- **One fallback venue has no address.** `tampere_muu` (elsewhere in Tampere) is used only when no
  venue resolves; it now carries a blank address instead of a misleading "Keskusta". Calendar
  parks and squares (Keskustori, Hämeenpuisto) are real published points with area names, not
  house numbers.
- **Calendar routes are seeded by CI.** New venues get their legs from the bounded fetch in the
  workflow (`--max 1500`); until that runs, a brand-new venue uses the straight fallback.
- **Music, Liiga hockey, Kide student events and the city calendar are published.** Stage, culture
  and community rows come only from the calendar plus the registry venues it names, so a venue that
  lists nowhere else can still be missing.
- **Coordinates are address points.** Registry venues were checked against OpenStreetMap and
  official addresses on 2026-11-15; `approx: true` remains only for `tampere_muu` and generated
  area venues without a house number.
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
