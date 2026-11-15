# VERSIONS — Kilinkolin

## App

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

- `model_version`: **2026.11.1** — fill priors by category, gravity β = 1.6,
  impedance from distance/speed approximation, class-based mode adjustment.
- `events_schema`: **2** — row indices 0–6 frozen; 7–14 appended.
- `flows_schema`: **1** — attendance, interest, zones, modes, corridors, arrival, egress.
- `venues`: 1 — 46 venues, 12 hubs, approximate coordinates flagged per venue.
- `zones`: 1 — 26 Tampere districts + 13 surrounding/Pirkanmaa bands.
- Calibration dataset: **none yet** (priors only) — backtest pending.
- Upstream feed: `tampere-keikat` @ 2026-11-14 12:05 UTC snapshot.
- Adapted interface: `tampere-keikat` @ `4be498d` (MIT).

## Versioning rules

- **MAJOR** — the UI can no longer read the data (row indices changed, file removed).
- **MINOR** — new source, category, view or model capability.
- **PATCH** — fixes, copy, styling, data corrections.

Every build stamps `generated`, `schema_version` and `model_version` into `web/data.json`
and `web/geo/flows.json`, so a rendered map can be traced to the exact code, model
parameters and input snapshot that produced it.
