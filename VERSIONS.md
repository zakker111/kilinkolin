# VERSIONS — Kilinkolin

## App

### 0.12.4 — 2026-11-15
Faster, lighter and properly laid out on a phone.

- Mobile: `map.js` detects a narrow or coarse-pointer viewport (`html.is-mobile`), caps the canvas
  at 1.75x DPR instead of 3x, samples fewer heat points and draws four district labels instead of
  six. The phone map is a 50dvh canvas clamped to 280-520px instead of `100dvh - 300px`; the legend drops
  the duplicate swatch list and sits above the attribution, so it covers about 60px of a 424px map
  instead of roughly a third of it.
- Performance: browser route geometry is simplified with Douglas-Peucker (~9 m) and rounded to five
  decimals in `build.py`. `web/geo/routes.json` goes from 3.25 MB / 153,932 points to 1.43 MB /
  61,894 points (gzip 699 KB -> 270 KB); the full geometry stays in `registry/routes.json`.
- Fixed: the page fetched every JSON file with `cache: "no-store"`, so a repeat visit re-downloaded
  the whole payload. It now uses normal HTTP caching (GitHub Pages sets `max-age=600`).
- Changed: the hour slider updates the event rows' on/soon classes in place (one rAF per frame)
  instead of rebuilding the list and reattaching listeners on every input event.
- Changed: Google Fonts requests only the weights the stylesheet uses (400/600/700 Inter, 400/600
  Plex Mono); `viewport-fit=cover` and safe-area padding handle notched phones.
- Total initial JSON on the local uncompressed preview: 5.0 MB -> 3.2 MB. Pages serves it gzipped.

### 0.12.3 — 2026-11-15
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

### 0.12.2 — 2026-11-15
Student parties and gigs sit on their real street addresses, and the site shows them.

- Added: 21 student and student-night venues the Kide feed names, each on its OpenStreetMap address
  point — Laulumaja (Takojankatu 1 C), Save File (Aleksis Kiven katu 24), Tampereen Ylioppilasteatteri
  (Itsenäisyydenkatu 12–14), Juhlatalo Tapiola (Karhunkatu 71), Tampereen Pursiseura
  (Kekkosenkatu 10), Pii-klubi (Yliopistonkatu 58 B), Kamula (Mustanlahdenkatu 18), TAMK pääkampus
  (Kuntokatu 3), YTHS-sauna (Kalevantie 3 C), Nightclub Mixei, Viihdekeskus ZBase, Viihdemaailma
  Ilona, Galaxie Center, Bricks, Kaijakka, Onda, Sherlock Holmes, Pub Kultainen Apina, Koskikeskus,
  Messukylän työväentalo and Hatanpään soutupaviljonki.
- Changed: published student parties 6 → 38 of the 67 future Kide products. A product is placed only
  when its place matches a venue in the registry; the rest are dropped and logged, never pinned to a
  guessed point (Ankkuri, Antura, Megazone and CLINT publish no street address at all).
- Fixed: 13 registry venues carried a district name ("Keskusta") where the address belongs, with
  points up to 3 km off. Terassi Pub Yläkerta is at Pispalan valtatie 39 — the upstairs of
  Vastavirta-Klubi, not the city centre — which alone corrects 10 published gigs. Others corrected:
  Astor (Aleksis Kiven katu 26), Puisto (Hämeenkatu 14 A), Rosendahl (Pyynikintie 13, the Scandic
  hotel), Ilves Bar & Night (Hatanpään valtatie 1), Myllärit (Åkerlundinkatu 4), Tiiliholvi
  (Kauppakatu 10), Huurre (Sammonkatu 46), Salhojankadun Pub (Salhojankatu 29), Katubaari Axu
  (Ilmarinkatu 47), Paapan Kapakka (Koskikatu 9), Kulttuurikeskus Maanalainen (Itsenäisyydenkatu 2),
  Tuomiokirkko (Tuomiokirkonkatu 3), Tammelan stadion (Kalevan puistotie 21), Hiedanranta /
  Lielahden kartano (Tehdaskartanonkatu 53), Ylisen kartano (Kuruntie 980, Ylöjärvi — 8 km north of
  the old guess) and Kangasalan kirkko (Ainontie 1).
- Added: the panel and the row list show the venue's street address beside its name, read from
  `web/geo/venues.json`, so a dot's address is visible without opening anything else. Calendar rows
  already label themselves by address.
- Fixed: Kide sells one event once per organiser — "Baby's First Game Jam" arrived four times, one
  per guild, each spelling the campus differently. Duplicate (date, start, title) listings are merged
  and place strings are whitespace-normalised.
- Verified: 371 events, 363 of them on a venue with a house number (the rest are parks, a racecourse
  and a summer theatre whose listing publishes no number); `validate.py` 0 errors; 126 venues.
- Note: the coordinates are OpenStreetMap address points, not venue-published points, and the
  capacity of a newly registered venue is a class prior — the same estimate as every other figure.

### 0.12.1 — 2026-11-15
The route cache is complete: no event falls back to a straight line.

- Fixed: `web/geo/venues.json` never carried a venue's `hubs`, so `scripts/routes.py` saw every
  calendar venue as hub-less and could not build its transit legs; registry venues with an empty
  `hubs` list (Kangasalan kirkko, Ylisen kartano, three libraries, Valkeakosken kesäteatteri) had no
  leg the seeder could fetch at all. 88 of 339 events sat on the straight-line fallback.
- Fixed: hub-less venues now use their nearest registered hub (`venue_catalogue()` in
  `scripts/routes.py`, the same rule in the build). Legs wanted went from 1,257 to 2,493.
- Fixed: a district centroid sitting on the venue produced a 0 km, two-point "route" — geometry in
  name only. Legs shorter than 50 m are now ignored and the hub leg is drawn instead, so Kangasalan
  kirkko gets the 14.0 km tram corridor from Hervanta and Ylisen kartano the 7.4 km bus leg from
  Tesoma.
- Changed: the workflow's second fetch pass runs `--max 1500`, so a backlog clears in one run
  instead of trickling in over days.
- Verified live: 339 events, 0 without street legs, 0 corridor-only flows, 0 legs under 50 m,
  3,150 legs over 7,050 km of OSM footways, 701 distinct routes shipped to the browser.
- Note: the model is unchanged — the same estimated flows, now drawn on real streets.

### 0.12.0 — 2026-11-15
Stage, culture, library and community events from the city's own calendar.

- Added: `scripts/feeds/city_events.py` reads Tampereen tapahtumakalenteri
  (`tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q=`; public JSON, no
  key, the whole calendar in one ~3 MB response) and publishes its stage, culture, library and
  community rows. Every location in that calendar carries a latitude/longitude **and** a street
  address, so the rows are placed on the published point — nothing is geocoded or guessed.
- Added: 217 calendar events land on the map — 21 stage, 74 culture, 122 community — taking the
  live site from 122 to 339 events over 77 days.
- Added: `place_venue()` turns a calendar location the registry does not know into a real venue
  (published coordinates, full address, nearest district, nearest transit hub); `web/geo/venues.json`
  now carries every venue's address. 137 calendar listings use such a venue, the other 80 resolve to
  a registry venue by name or address (Pääkirjasto Metso, Vapriikki, Tampere-talo, …).
- Added: `resolve_by_address` already handled "address in the row"; the calendar makes that the
  normal path rather than the exception.
- Changed: `source_status.culture` reports the calendar, and the all-feeds-failed guard counts four
  sources.
- Changed: `scripts/routes.py` also loads the generated venues, and the workflow fetches missing legs
  in two bounded passes (`--from-flow --max 300`, then `--max 400`). Calendar venues therefore gain
  real walking geometry as the cache fills: 59 of their 147 flows drew street legs on the first run,
  the rest still use the straight fallback corridors until the next runs catch up.
- Changed: a venue beyond its class catchment (Kangasala, Nokia, Hämeenkyrö, Lempäälä) now draws on
  its nearest districts instead of producing an event with no origin at all.
- Fixed: those far venues produced invalid flows ("no mode split", "neither legs nor corridors") that
  the validator rejected; 20 such rows are gone.
- Kept: multi-day and ongoing listings (an exhibition open for months) are not published as a daily
  crowd event, music-only calendar rows are skipped because `tampere-keikat` already supplies gigs,
  and rows duplicating another source (same day, same title) are dropped — 3 today.
- Note: a calendar venue's capacity is unknown unless the listing publishes `maxParticipants`, so its
  crowd is estimated at the small-venue floor and the figure is an estimate like every other one.

### 0.11.2 — 2026-11-15
A failed rebuild no longer blanks the map.

- Added: a second Sunday cron (`0 6 * * 0`) after the weekly `0 4 * * 0` rebuild, so a failed
  weekly run gets one automatic retry the same morning.
- Fixed: when every feed fails, or nothing survives the date filter, the build leaves
  `web/data.json` and `web/geo/*` untouched and exits non-zero, so the workflow stops before
  committing or deploying. Before, a total feed outage produced an empty event list and replaced
  the live data with a blank map.
- Note: one failed source still publishes the others; only an empty result stops the build.

### 0.11.1 — 2026-11-15
Every published event sits on a venue with a real address.

- Fixed: one gig had `Ilmainen` ("free") in the venue field and its street address folded into the
  title, so it was pinned to the generic `tampere_muu` fallback. `resolve_by_address()` now accepts a
  street name with a house number found in the row and places the event on that registry venue —
  a real address, not a guess.
- Fixed: `registry/venues.json` listed `ilmainen` as an alias of the generic fallback venue, which
  is how that row lost its address. Removed.
- Added: Finlaysonin kirkko, Puuvillatehtaankatu 2 (`61.5022, 23.7550`, OpenStreetMap), capacity 220
  as published by the Tampereen seurakunnat, so concert rows at that address have a venue.
- Note: all 122 published events — 71 gigs, 45 hockey fixtures, 6 student events — now resolve to one
  of 26 venues, each with an address and coordinates; the map draws a dot for every one of them.

### 0.11.0 — 2026-11-15
Student parties from Kide, on their real addresses.

- Added: `scripts/feeds/kide.py`, the first adapter in a `scripts/feeds/` package. It reads Kide's
  public product list for Tampere (`api.kide.app/api/products?city=Tampere`, no key) and returns the
  event name, the organiser, the place and a **real** start and end time — the student platform
  publishes both, so a sitsit or a gaala now has a real egress curve instead of the 300-minute
  default.
- Added: `kide_rows()` in `build.py` places each product on a venue from `registry/venues.json` by
  name or alias and publishes it as the `student` category. A product whose place is not a registry
  venue is **dropped and logged**, never placed on a guessed coordinate: 6 of today's 67 products
  land on a real address (Telakka, Klubi, Tampere-talo, Hakametsän jäähalli), 61 are left out with
  their place names printed in the build log.
- Changed: `source_status` gained a `student` key alongside `music`, `sports` and `seed`, so a broken
  Kide feed reports `FAILED` there instead of silently shrinking the day.
- Fixed: a malformed product (or a `minPrice` money object instead of a number) no longer loses the
  whole source — the adapter skips that one row.
- Kept: `seed` is still `OFF` and no `SAMPLE` row is published; `validate.py` still refuses one.
- Note: everything else on the page remains an estimate from the flow model.

### 0.10.0 — 2026-11-15
Only real events, and the day's programme beside the map.

- Removed: the ten `SAMPLE` placeholder rows are no longer published. The build reads
  `data/seed_events.json` only with `--with-samples`, `source_status.seed` reports `OFF`, and
  `validate.py` fails the deploy if a placeholder reaches the live data. The site now shows music
  and Liiga hockey only — nothing invented.
- Added: a right-hand panel listing the chosen day's events in start order with the venue and kind.
  The row for the hour you are looking at is marked "occurring now", events starting within two
  hours are marked soon, and each row carries the estimated attendance with "≈".
- Added: hover support on the map. Pointing at a dot names the event in the panel and enlarges the
  dot; pointing at a row rings the matching dot. Tapping still works on phones.
- Fixed: the legend markup contained a duplicated swatch block and a stray closing tag, and the
  swatch rules sat inside the phone media query, so the desktop legend was missing a row.
- Fixed: a tooltip could stay on screen over an empty patch of map, and the hover hit radius did
  not match the tooltip's.
- Note: `≈` figures remain estimates from the flow model, not measured attendance.

### 0.9.0 — 2026-11-15
Dots for what is on, and a phone-first layout.

- Added: one dot per event on the chosen day, coloured by kind — gigs red, sports blue,
  student parties amber — so the map says what is happening where without a listing.
- Added: tap or click a dot for the event name, start time and venue. Estimates stay estimates;
  the dots are the only place a title appears.
- Added: Liiga sports adapter (`fetch_liiga` in `scripts/build.py`) — Ilves and Tappara home
  fixtures from the public Liiga game list, pinned to Nokia Arena with the rink's own coordinates.
  Away games are excluded; the feed refreshes on every scheduled rebuild.
- Changed: phone layout stacks the day strip and hour control, enlarges touch targets, trims the
  legend and sizes the map to the viewport so nothing scrolls sideways.
- Note: student rows are still `SAMPLE` placeholders — no dependable public Tampere student feed
  was found (the TREY calendar is a JS app over a Strapi API that refused unauthenticated reads).

### 0.8.0 — 2026-11-15
Traffic both ways.

- Added: the estimate now counts departures as well as arrivals. Each event gets an estimated end
  (150 min for gigs, 300 for student nights, 120 for culture and community events), and the egress
  curve spreads the crowd over the 45 minutes after it.
- Changed: the heat and the count include people heading home, so a venue no longer goes dark the
  moment the event starts and lights up again when it ends.
- Changed: the legend reads "Estimated traffic on the streets" because the layer is no longer
  arrivals only.
- Note: the feed has no end times; they are approximations like every other number here.

### 0.7.2 — 2026-11-15
Every event contributes.

- Fixed: the arrival curves are per-slot shares, but the page read them as cumulative totals, so
  an event contributed nothing at its own start hour and the heat peaked about an hour early.
  The 15-minute window is now matched to the chosen minute.
- Fixed: six events without a listed start time were dropped by the aggregation; they now count at
  19:00, and the footer says so.
- Fixed: the hour scrubber only covered 15:00–02:00, so daytime events were never visible. It now
  runs 06:00–06:00 next day, and the default hour is the day's busiest across that range.
- Changed: heat opacity follows the size of the crowd, so a three-person event no longer paints
  the whole city while a busy hour still reaches deep red.
- Fixed: the rebuild badge formatted its UTC stamp in the browser's timezone, so an early-morning
  rebuild was labelled with the previous day.

### 0.7.1 — 2026-11-14
Weekly refresh of the events and their streets.

- Added: the Actions workflow now fetches street geometry for any new origin legs
  (`routes.py --from-flow`), rebuilds the model with them, and commits `registry/routes.json`
  alongside the data before deploying.
- Changed: the cadence is explicit — daily sync 05:15 UTC, guaranteed full rebuild Sunday 04:00 UTC.
- Fixed: new events no longer fall back to straight-line corridors just because their route was
  never cached.

### 0.7.0 — 2026-11-14
Pick a day, drag the hour.

- Removed: the event dropdown. No gig, team or title is listed anywhere; the map answers only
  where the estimated crowd is on its routes.
- Added: a day strip and a 15-minute hour scrubber. The heat aggregates every event that day,
  weighted by how much of each crowd is arriving in that 15-minute window (arrival curves), so
  moving the hour changes the streets and the count.
- Changed: the estimate card reads `≈ people estimated on routes` for the chosen day and hour.
- Changed: the day's busiest hour is picked as the default when you choose a day.

### 0.6.2 — 2026-11-14
Transit corridors.

- Changed: districts beyond walking range no longer draw a 9 km foot path. Their crowd is
  assigned to the nearest transit hub and the heat follows the road corridor from that hub
  to the venue (tram/bus/train), coloured by the hub's mode.
- Changed: footer wording explains close districts walk, farther ones ride.

### 0.6.1 — 2026-11-14
One traffic heat.

- Removed: the "how they arrive" toggle. Three mode-coloured heat clouds overlapped into mud and
  the walking traffic is the part that actually maps onto streets.
- Changed: the single heat layer is the walking traffic from every district, coloured red where
  the flow is concentrated and yellow where it is thin.

### 0.6.0 — 2026-11-14
Whole journeys, sourced by district.

- Changed: every origin district routes from its own centre to the venue over the street network,
  so the heat shows the roads across town instead of collapsing far districts onto a transit hub.
- Added: 1 214 cached walking legs (5 832 km); the cache is committed and routing stays build-only.
- Added: origin patches sized by crowd, so a distant district reads as a source area even when its
  approach path is long and thin.
- Fixed: `deposit()` referenced a `zoom` it never received, which silently emptied the heat layer.
- Changed: the heat field normalises against the 97th percentile instead of the maximum, so one
  saturated core no longer flattens every approach street.
- Note: past 9 km the path follows the main road corridor as a stand-in for the transit ride.

### 0.5.0 — 2026-11-14
Traffic heat instead of route lines.

- Changed: the overlay is now a density field. Intensity is deposited along every walking street
  (people per metre), smoothed in a half-resolution buffer and mapped through the red→yellow ramp,
  so the map shows where the walking traffic is rather than drawing the probability of a route.
- Changed: default zoom is 14 so a street is more than a pixel wide; kernels tightened to ~50-150 m.
- Changed: "how they arrive" uses the same density field, one cloud per mode, limited to the three
  largest modes so the colours do not mix into mud.
- Kept: the attendance estimate overlay and the origin labels.

### 0.4.2 — 2026-11-14
Heat map legibility pass.

- Fixed: a leftover reference aborted the overlay after the first leg, so most bands were missing.
- Fixed: small events (372 people at Klubi) showed an all-yellow web; colour now uses a square-root
  spread of share-of-arrivals, so the busiest legs stay red without flattening everything to yellow.
- Changed: bands shrink as you zoom in, so at street level they follow the road instead of covering it.
- Changed: soft blurred halo instead of stacked hard strokes; the plate under the heat is lighter.

### 0.4.1 — 2026-11-14
Heat palette turned around.

- Changed: the ramp is now red for the most likely streets, through orange, to yellow for the
  least likely ones (previously deep red fading to pale rose).
- Changed: band opacity raised slightly so the yellow ends stay readable on the light basemap.

### 0.4.0 — 2026-11-14
Heat on the actual streets.

- Added: walking legs routed over OpenStreetMap footways (`scripts/routes.py`, FOSSGIS OSRM),
  cached in `registry/routes.json` and shipped as `web/geo/routes.json` — no routing at runtime.
- Added: the map draws each leg as a street-following band whose width and depth encode how many
  people walk it; overlapping legs merge into a heat corridor toward the venue.
- Changed: legs come from a venue's transit hub (for districts over 3 km) or from the district
  itself (walkable ones), and hub legs are coloured by what the hub is — train, tram, bus.
- Changed: default zoom is street level (13.2) so the bands read as streets.
- Fallback: if a leg has no cached geometry the straight-line corridor is drawn instead.

### 0.3.0 — 2026-11-14
Heat map and estimate only.

- Changed: the page is the map plus a small estimate overlay. Nothing else — no event panel,
  no presets, no scrubber, no scale toggle.
- Added: "How they arrive" is now its own heat layer — each area's plume coloured by that area's
  main mode, sized by its share of arrivals, with a mode legend.
- Changed: event choice is one grouped dropdown (day → events).

### 0.2.0 — 2026-11-14
Map-only release.

- Changed: the site is the crowd-flow map and nothing else. Calendar, list, category
  checklist and presets are gone; a date picker and event selector replace them.
- Changed: basemap is now keyless OpenStreetMap raster tiles drawn on a canvas, with our own
  pan/zoom. The Google maps branch and `GOOGLE_MAPS_API_KEY` were removed — the heat layer is
  painted over tiles we control, so the map works with no key and no billing.
- Added: a translucent plate under the heat so the red ramp reads against a detailed basemap,
  label collision avoidance, ± zoom buttons, OSM attribution.

### 0.1.0 — 2026-11-14
First working build.

- Added: calendar, list and flow-map views; grouped category checklist with quick presets.
- Added: music ingest from the Tampere Keikat feed (read-only), venue alias resolution across
  36 raw venue strings → 46 registry venues.
- Added: interest score, attendance ranges, gravity origin split, mode split, corridors,
  arrival/egress curves.
- Added: Google Maps basemap wiring with a no-key setup notice; canvas heat/corridor/arrival overlay.
- Added: validation gate and GitHub Actions workflow (daily sync, weekly rebuild, Pages deploy).
- Known: sports/student/theatre/library rows are `SAMPLE` placeholders until their feeds land.
- Fixed (inherited from the upstream interface): weekday labels were off by one
  (`getDay()` on a Monday-first array); removed an unconditional analytics tag that fired
  before consent.

## Data & model

- `model_version`: **2026.11.2** — fill priors by category, gravity β = 1.6,
  impedance from distance/speed approximation, class-based mode adjustment; the Liiga adapter
  supplies a real end minute when the game list carries playing time.
- `events_schema`: **2** — row indices 0–6 frozen; 7–14 appended.
- `flows_schema`: **1** — attendance, interest, zones, modes, corridors, arrival, egress.
- `venues`: 1 — 69 registry venues, each with a street address and an OpenStreetMap address point,
  plus calendar venues generated from the city calendar's own published points (address kept,
  capacity unknown), 12 hubs, approximate coordinates flagged per venue.
- `zones`: 1 — 26 Tampere districts + 13 surrounding/Pirkanmaa bands.
- Calibration dataset: **none yet** (priors only) — backtest pending.
- Upstream feeds: `tampere-keikat` @ 2026-11-14 12:05 UTC snapshot; Liiga game list
  (`liiga.fi/api/v2/games`) filtered to Ilves/Tappara home games in Tampere; Kide public product
  list (`api.kide.app/api/products?city=Tampere`) for student events; Tampereen tapahtumakalenteri
  (`tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q=`) for stage,
  culture, library and community events.
- `sports` rows come from the Liiga adapter, `student` rows from the Kide adapter and `culture`
  (stage/culture/community) rows from the city calendar; `SAMPLE` placeholders are no longer
  published. Kide and calendar rows carry a real end minute when the source does.
- Adapted interface: `tampere-keikat` @ `4be498d` (MIT).

## Versioning rules

- **MAJOR** — the UI can no longer read the data (row indices changed, file removed).
- **MINOR** — new source, category, view or model capability.
- **PATCH** — fixes, copy, styling, data corrections.

Every build stamps `generated`, `schema_version` and `model_version` into `web/data.json`
and `web/geo/flows.json`, so a rendered map can be traced to the exact code, model
parameters and input snapshot that produced it.
