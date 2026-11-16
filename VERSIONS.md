# Versions

## 0.13.6 — 2026-11-16

Weekly-only scheduled refresh.

- One scheduled run: Sunday 04:00 UTC. The daily 05:15 UTC sync and the Sunday 06:00 UTC retry
  were removed, so the schedule refreshes the site at most once a week.
- The build still runs on pushes that touch the build and on manual dispatch.
- No data, model, schema or UI change: model 2026.11.6, schema 2.

## 0.13.5 — 2026-11-15

Audit fixes: date-leaked music times, repeat city performances, Kide multi-day ends, shared-address
venue matching, after-midnight labels and a stricter validator.

- **Music times:** a start parsed from a feed row that also carried the event date (`05:12`
  meaning 5 December) is no longer published as a 05:12 start. The row keeps its date and the
  time is treated as missing, so the model uses the class default instead of inventing a start.
- **Repeat city performances:** the same title at the same venue on the same day keeps each
  published start time instead of collapsing to one row. Calendar rows are deduplicated on
  (date, start, title, venue), not title alone.
- **Kide multi-day ends:** a product whose end date is later than its start no longer produces a
  24–107 hour egress window. The end is clamped to the event's own day (or the next 06:00 for an
  after-midnight finish).
- **Shared-address matching:** a venue whose address matches another venue's address no longer
  inherits the wrong name. Lush Koskikeskus stays at Koskikeskus instead of moving to Ilves Bar
  & Night, which shares the mall address.
- **After-midnight labels:** events starting after midnight show `+1` (or `+2` on a long strip)
  on the hour axis, so the label matches the day the event actually starts.
- **Validator:** malformed times, an empty route cache and events longer than 24 hours now fail
  `validate.py` instead of reaching the site.
- No schema change: schema 2, model 2026.11.6.

## 0.13.4 — 2026-11-15

Completeness and after-midnight dates.

- **No silent row caps:** the city calendar's 220-row cap and Kide's 80-row cap were removed.
  All 402 eligible calendar rows are evaluated and 398 are published (4 duplicate another
  source), taking the site to 576 events across 158 venues.
- **New venues routed:** the 434 walking legs for the new venues were fetched, leaving 0
  corridor-only fallbacks.
- **After-midnight dates:** a start before 06:00 belongs to the previous 06:00–06:00 day strip,
  so a midnight event is no longer drawn one day late.
- **Validator:** fails on a `FAILED` source, an event venue without an address, or a flow
  without a matching event/venue.
- No schema change: schema 2, model 2026.11.6.

## 0.13.3 — 2026-11-15

Student events with published addresses, plus a browser smoke test.

- **Kide product details:** when the product list's free-text place does not match the registry,
  the public product detail's published street address and point are used. 15 more student
  events (47 → 62), six new locations and their walking legs; 257 older stale legs refreshed.
- **Smoke test:** Playwright checks day switching, both `06:00` slider extremes and a real map-dot
  tap. The build workflow runs it before deploy.
- No schema change: schema 2, model 2026.11.6.

## 0.13.2 — 2026-11-15

Address corrections.

- 28 venues moved from district names to published street addresses and OpenStreetMap address
  points, plus the generic fallback. 765 stale route legs dropped; the legs in use were refetched.
- The panel's `venue · address` line is restored.
- No schema change: schema 2, model 2026.11.6.

## 0.13.1 — 2026-11-15

UI fixes.

- The next-day label reads `06:00 +1` instead of a bare `06:00`.
- The desktop legend has one category row again; the duplicated swatch block is gone.
- No schema change: schema 2, model 2026.11.6.

## 0.13.0 — 2026-11-15

Day-and-hour site.

- The site is one estimated crowd-flow heat map: pick a day, drag the hour, see the estimated
  crowd on the streets at that moment.
- The right-hand panel names the day's events in start order and expands the event under the
  pointer; hovering a map dot names the same event.
- Arrivals and departures are both in the heat, so a venue keeps its crowd through the evening.
- No listings, calendar or checklist views; the map is the product.
- Schema 2, model 2026.11.6.

## 0.12.0 — 2026-11-14

Street-level heat and transit corridors.

- Walking legs routed over OpenStreetMap footways and cached (401 legs, 906 km), drawn as
  weighted bands instead of district blobs.
- Districts beyond walking range send people along their tram, bus or rail corridor; the venue's
  own hub is only a fallback.
- Browser route geometry simplified at build time to keep the payload small.
- Schema 2, model 2026.11.6.

## 0.11.0 — 2026-11-13

Flow map only.

- Keyless OpenStreetMap tile basemap with the site's own pan/zoom, canvas heat/corridor/arrival
  overlay, presets, time scrubber and legend.
- Date picker and event selector; per-event vs global scale.
- Removed the calendar/list/checklist views at the author's request.
- Schema 2, model 2026.11.6.

## 0.10.0 — 2026-11-12

First public data model.

- Music feed ingest, venue alias resolution, taxonomy and crowd class.
- Interest score with signal breakdown.
- Attendance priors with ranges (Crown class A/B/S/C).
- Gravity origin split, mode split, corridor geometry and arrival/egress curves.
- Schema 2, model 2026.11.6.

## Provenance

- `app_version`: **0.13.6** — weekly-only scheduled refresh
- `model_version`: **2026.11.6** — fill priors by category
- `schema_version`: **2** — events array positions 0–6 frozen; append only
- `venues`: 74 registry venues plus generated calendar locations (published point and address);
  capacity unknown for generated venues; 154 venues in the current build, approximate coordinates
  flagged per venue.
- `sources`: Tampere Keikat (music), Liiga (sports), Kide (student), Tampereen
  tapahtumakalenteri (stage, culture, library, community).
- `routing`: cached OSRM foot geometry in `registry/routes.json`; browser copy simplified.
- `basemap`: OpenStreetMap raster tiles, no key.

## How versions are chosen

- `APP_VERSION` changes for any user-visible change, however small.
- `MODEL_VERSION` changes only when the estimate changes: priors, curves, mode split, capacity
  classes or the aggregation. A docs-only or UI-only release keeps the model version.
- `SCHEMA_VERSION` changes only when `web/data.json` or `web/geo/flows.json` changes shape.
  Positions 0–6 of each event row are frozen for older consumers; new fields are appended.
