# AGENTS.md — Kilinkolin

Working notes for anyone (human or agent) changing this repo.

## What this is

A static site: one **estimated crowd-flow heat map** for Tampere. The controls are a day and an
hour; the map aggregates every event that day into the streets people are estimated to be on at
that moment, plus the number on the move. A right-hand panel names what is on that day and shows
the event under the pointer; hovering a dot on the map names the same event there.
Python builds the data in GitHub Actions; the browser only fetches JSON, tiles and renders.
The workflow refreshes once a week, on Sundays at 04:00 UTC: new events are fetched, their
missing street routes are added, the model is rebuilt, validated and deployed to Pages. It also
runs on pushes that change the build.
Hosted on GitHub Pages at `https://zakker111.github.io/kilinkolin/`.

Not a fork of Tampere Keikat — it reads that project's published feed. See `NOTICE.md`.

## Versions

`APP_VERSION` lives in `web/config.js`. Every release also gets a top entry in `VERSIONS.md`, a
line in `README.md` and a note in `TODO.md`; keep those in step when the site changes.
`MODEL_VERSION` (currently 2026.11.16) lives in `scripts/build.py` and `web/config.js` and changes
only when the model does. `SCHEMA_VERSION` is 3; event positions 0–6 are still frozen.

## Hard rules

1. **Never write to `zakker111/tampere-keikat`.** It is read-only input.
2. **Never commit API keys.** `DIGITRANSIT_API_KEY`, if added, is a *secret* used only in Actions.
   The basemap uses keyless OpenStreetMap tiles; if a paid tile provider is ever configured it
   belongs server-side or as a referrer-restricted key, never in `web/config.js` by hand.
3. **Never present an estimate as a measurement.** Every number is `≈` with a range, and the UI
   says "estimated flow model". Do not remove those labels.
4. **Never invent data.** No fabricated attendance, capacity or population figures. Missing input
   means a wider band plus a note, not a made-up number.
5. **Time zone:** all event times are Europe/Helsinki. The day strip runs 06:00–06:00, so a
   start before 06:00 is moved to the previous date before the event is filtered and published
   (`night_date()` in `build.py`). A suspicious 02:00–05:59 start is still investigated rather
   than accepted as a parsing accident.
6. **Subpath safety:** the site is served from `/kilinkolin/`. Always use relative URLs
   (`./data.json`), never `/data.json`.
7. **Keep attribution:** `LICENSE`, `NOTICE.md` and the footer credit stay.

## Layout

```
web/            index.html, app.js, map.js, heat-worker.js, styles.css, config.js, fonts/,
                data.json, geo/*.json and geo/days/<date>.json
scripts/        build.py (pipeline), calibration.py (fit/backtest), validate.py (gate),
                routes.py (street geometry), feeds/ (adapters)
data/           keikat.json (feed snapshot), seed_events.json (SAMPLE rows, never published)
registry/       venues.json, zones.json  (hand-maintained)
.github/        workflows/build.yml, workflows/ci.yml
```

## Commands

```bash
python3 scripts/routes.py                 # add missing walking legs to the route cache
python3 scripts/routes.py --from-flow     # only legs the current build draws (fast, used in CI)
python3 scripts/build.py --mode full      # fetch, normalise, model, write web/*
python3 scripts/validate.py               # gate: schema + conservation + coverage
python3 -m http.server -d web 3003        # local preview at :3003
cd tests && npm ci && npx playwright install chromium && npm test  # model + browser tests
```

The smoke test starts its own static server on :4173; it is also a blocking pre-deploy step in
`.github/workflows/build.yml`.

## Publishers of data must be real

`data/seed_events.json` holds SAMPLE placeholders and is **not** read by the normal build: only
`python3 scripts/build.py --with-samples` loads it, and `validate.py` fails if `source_status.seed`
is not `OFF` or if a published title contains `SAMPLE`. Never ship a placeholder to the live site.

## Data contracts

`web/data.json`:
```json
{ "generated": "... UTC", "schema_version": 3, "model_version": "...",
  "source_status": {...}, "coverage": {...},
  "calibration": {"liiga": {...}, "competition": {...}, "tba_start": {...},
                  "venue_collisions": {...}, "city_capacity": {...}},
  "events": [["date","time","title","venue","genre","free","url",
              "id","kind","category","sub","interest","attendance","sample","venue_id"]] }
```
Indices 0–6 are frozen (older consumers read them positionally). Append only. Index 12
(`attendance`) is null only for a `capacity_unknown` flow; treat null as no estimate, never as
zero. An empty `time` means the source published no start. The UI must label it TBA, and the heat must not be pinned
to 19:00: the flow carries `start_options` (18:00, 19:00, 20:00) and `start_window`
("18:00–20:00"), and the browser averages the arrival/egress curves over those candidate
starts. The row's empty time is never filled in to look published.

`web/geo/days/<date>.json`: the same flow objects for one night plus the union of the walking
routes those flows reference, keyed by `venue|hub:*` / `venue|zone:*`. It also carries the
`schema_version`, `model_version`, `generated` and `date` stamps. The browser loads only the
selected day's bundle; `geo/flows.json` and `geo/routes.json` stay complete for validation and
the route/data gates, and are the fallback when a day bundle cannot be fetched.

`web/geo/flows.json`: per event `attendance{low,mid,high,spread}` (or a null band with
`unknown:true` when the venue capacity is unpublished), `interest{score,band,signals}`,
`basis{capacity,capacity_unknown,capacity_source,fill,fill_source,interest,
spread,published_max_participants,competition{factor,peers},
venue_collision{group_size,venue_capacity,combined_mid_before,combined_mid_after,factor,room_split}}`,
`start_known`, `zones[]` (share
of arrivals), `modes[]`, `legs[]`, `corridors[]` (straight fallback only), `arrival[]` and
`egress[]` 15-minute slices. TBA flows also carry `start_options` and `start_window`.
`attendance`, `legs[].people` and `corridors[].people` are scaled together by the competition
factor and then by the venue-collision allocation.

### Calibration contract

- **Only realized attendance can produce a backtest error.** Liiga publishes `spectators` for
  completed games; that is the only calibration target. The city calendar's `maxParticipants` is
  a published cap, not an observed crowd, so never turn it into a fake “actual” or an error rate.
- The hockey fill is fitted on completed Tampere home games. The fit replaces the prior only
  when its leave-one-out MAPE is lower than the prior's; otherwise keep the prior and say why.
  This compares the factor on games it did not see with the fixed prior, rather than rewarding an
  in-sample fit. When the fit wins, report leave-one-out error. Keep the sample size, date range,
  prior, fitted factor, in-sample MAPE for the fit, and leave-one-out median/mean error and bias
  in `data.json.calibration.liiga`; the UI reads those fields. If there are fewer than eight games,
  keep the prior and say the sample is insufficient.
- Capacity provenance must be explicit: `city calendar maxParticipants`, `venue registry sport
  capacity`, `venue registry gig capacity`, or the 20-seat floor. Do not use an arena's concert
  capacity for a hockey game.
- A venue with `capacity_unknown: true` has no published hall size. `venue_capacity()` returns 0
  and `event_capacity()` returns None unless the event carries a published `maxParticipants`.
  Its flow publishes `attendance{low:null,mid:null,high:null,spread:null,unknown:true}` and
  `basis{capacity:null,capacity_unknown:true,capacity_source:<note>}`. The event stays in the day
  list but adds no heat; it never inherits the 20-seat floor or another room's capacity. Count
  these events in `data.json.calibration.capacity_unknown`.
- `validate.py` must fail if an event's capacity or mid estimate exceeds a published
  `maxParticipants` cap, if the coverage count disagrees with the flows, if two rows have the
  same venue/date/title/start, or if the calibration block is malformed.
- The competition factor is a prior, never a fitted or measured substitution model. Only
  same-day events with overlapping active windows compete. Catchment overlap compares the
  published top-zone shares (unlisted remainder excluded) and must be at least 50%. The shared
  slice is pooled once at the largest exposed demand and apportioned by exposure; unique slices
  are retained and a 5% floor applies. Do not turn this into a raw peer-demand ratio: that
  erased small events whenever many peers shared one central zone.
- `data.json.calibration.competition` records `status: PRIOR`, the method, the floor, the
  minimum overlap and the count of discounted flows. Every flow carries
  `basis.competition{factor,peers}`; the panel shows the row only when `factor < 0.999`.
- Venue collisions are grouped on **venue + date + exact published start**. TBA rows are not
  grouped because they have no single published start. Cap the combined mid at the **smallest
  applicable venue capacity** in the group (for mixed sport/gig configurations this is the
  smaller published capacity), allocate the cap in proportion to the independent mids, and keep
  the integer total exactly at or below the cap. Every shared group is an **unresolved room
  split**: a per-event `maxParticipants` cap does not identify a room allocation. Emit
  `basis.venue_collision{group_size,venue_capacity,combined_mid_before,combined_mid_after,
  factor,room_split}` on every member and counts in `calibration.venue_collisions`. The panel
  shows a **Venue split** row for these events even when the group already fits. The validator
  must recompute each group's combined mid and fail if it exceeds the cap or the metadata counts
  disagree. Do not group TBA rows or treat distinct room bookings as separate buildings without
  a published room split.
- `data.json.calibration.tba_start` records the unknown-start prior: `status: PRIOR`, the
  documented `18:00–20:00` window, candidate starts 18:00/19:00/20:00, and the TBA flow count.
  The build emits `start_options` and `start_window`; `map.js` averages the curves over the
  options. Do not collapse a TBA event back to one 19:00 arrival peak. A TBA row is not marked
  "occurring now" because it has no precise start.

`legs[]` is what the map draws: `{key, name, share, people, mode, km, min}`. `key` resolves into
`web/geo/routes.json`, a cache of real pedestrian geometry (`venue|hub:<id>` or
`venue|zone:<id>`), fetched by `scripts/routes.py` from the FOSSGIS OSRM foot instance and
committed under `registry/routes.json`. Never call a router at runtime and never invent geometry:
missing cache entries fall back to the straight `corridors[]` lines. The browser copy is simplified
at build time (Douglas-Peucker, about 9 m, five decimals) to keep the payload small; it is not the
routing cache, and `registry/routes.json` keeps the full OSRM geometry.

Every event must resolve to a real venue: a registry venue, or a venue generated from a feed's own
published coordinates (the city calendar supplies both the point and the address). Generated
venues live in `web/geo/venues.json` with an `address`; they are never hand-written into the
registry and never guessed. A music row whose venue is only a district (for example `Nekala`)
is dropped and logged instead of being published at `tampere_muu`. `validate.py` fails if any
published event's venue has no address, if a source reports `FAILED`, or if a flow has no
matching event.

Feeds are not row-capped. A source that returns more events must publish all of them; silently
truncating a sorted feed on every run would make the missing tail permanent.

`map.js` sets `html.is-mobile` from `(max-width: 700px)` or a coarse pointer up to 1024px. On a
phone it caps canvas DPR at 1.75 (2 on desktop), samples fewer heat points and draws four map
labels; the CSS uses a 50dvh map (clamped 280-520px) and hides the duplicate legend swatches.
On phones the event's "Why" detail opens in a modal bottom sheet so the panel rows stay in place;
the sheet body is the only scroll area. Desktop keeps the inline disclosure.
Keep phone checks to a 390x844 touch viewport.

The heat raster comes from `heat-worker.js` on an `OffscreenCanvas`, and `paintFlow` draws no heat
while a request is in flight, so `startHeatRender` keeps exactly one raster in flight: a newer view
waits for the current reply and the repaint after it posts the newest state. Posting per slider
tick queues a raster per 15-minute step and the map stays heat-less until the worker drains them
(measured: ~10 s after a drag). A worker that says nothing for `HEAT_WORKER_GRACE` (6 s) is
treated as gone: `stopHeatWorker` terminates it and the synchronous renderer draws for the rest of
the session, with one warning in the console.

On any layout with a pointer (`html:not(.is-mobile)`) the event panel's detail card sits under the
row list: a card above the list grew over the rows and slid them out from under the pointer, while
a card below it can only take space from the list's bottom, so no row moves and no fixed slot or
inner scroll box is needed. On phones the card is sticky at the panel top instead, so the event
just tapped stays in view while the rows scroll under it; that panel is one scroll area, never
two. A touch pointer leaves the canvas when the finger lifts, so `pointerleave` must not clear the
dot that a tap has just selected.

Each district in `registry/zones.json` carries a `transit_mode` (`tram`, `bus` or `rail`). It
colours the corridor that district's people arrive along: close districts walk/bike, farther ones
follow their tram, bus or train, and the venue's own hub is only a fallback.

### Addresses

A registry venue must carry a **street address** (`"address": "Takojankatu 1 C"`), not a district
name, and its point must sit on that address — use the OpenStreetMap address point and set
`"approx": false`. `"Keskusta"` in the address field is a bug: it moves the dot kilometres away
and hides the real address from every visitor. The panel and the row list render
`venue · address` from `web/geo/venues.json`, so a wrong or vague address is visible on the site.

Route geometry is cached by venue ID, not by coordinate. When a venue moves, delete its
`venue|hub:*` and `venue|zone:*` keys from `registry/routes.json`, rebuild so `flows.json`
carries the new point, run `scripts/routes.py --from-flow`, then rebuild and validate.
Capacity for a venue nobody publishes a hall size for stays a class prior; say so in `VERSIONS.md`
rather than presenting it as published. A venue explicitly marked `capacity_unknown` instead
publishes no estimate at all (Sin City is the current case); do not give it a class prior.

### Student parties

`scripts/feeds/kide.py` is the student source. Its product **list** carries a free-text place and
no coordinates. A product is first matched to a registry venue (name or `aliases`, whitespace-
normalised, with the spellings Kide actually uses added as aliases). If that fails, the public
product detail can supply the organiser's published `streetAddress`, postal code and point; use it
only when the street has a number and the point is in the Tampere region. Vague places
(`Tampereen seutu`) and postal boxes (`PL 54`) are dropped and logged, never guessed. After
`kide_rows` adds one of these generated venues, rebuild the alias index before resolving the
student rows. The same event sold separately by four guilds is merged on (date, start, title).
A venue marked `prefer_detail_place` (H5) always consults the product detail, because the list
place can name one room while the event is at several (H5 Bar vs Sin City + H5).

## Adding a feed adapter

1. Write `scripts/feeds/<source>.py` exposing `fetch() -> list[dict]`.
2. Register it in `build.py`; each adapter records `OK` / `EMPTY` / `FAILED`.
3. An adapter must never raise past its own boundary — one broken source must not blank the site.
4. Rows from a new source are real: do **not** mark them `sample`.

## Before committing

- `validate.py` exits 0.
- `git diff` contains no key, no `vendor/` churn, no build output outside `web/`.
- `TODO.md` updated; `VERSIONS.md` entry if behaviour or schema changed.
- `AGENTS.md` updated when the layout, controls or data contract change.
- `README.md` updated when the user-facing behaviour or data sources change; the app version in
  `web/config.js`, `README.md` and `VERSIONS.md` must agree.
- If the UI changed, load it locally and check that picking a day and dragging the hour repaints
  the heat over the tiles and that the estimate box agrees with the map.
