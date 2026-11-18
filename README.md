# Kilinkolin

An **estimated crowd-flow heat map** for events in Tampere: pick a day, drag the hour, and see
where the estimated crowd is on the streets at that moment. The map is the answer; the panel
names what is on.

Live: https://zakker111.github.io/kilinkolin/ · **v0.16.9** · model **2026.11.16** · schema **3**

## What it does

- **Street heat** — a density field over real walking routes from every district to every event
  happening that day. Dark red is the busiest streets, yellow the quietest. The raster is drawn by
  an `OffscreenCanvas` worker one request at a time, and if the worker stops answering the map
  falls back to drawing it on the main thread instead of staying blank.
- **Arrivals and departures** — the heat includes people walking to events and people leaving
  them, so a venue keeps its crowd through the evening instead of going dark at the start.
- **Day strip + hour scrubber** — 15-minute steps from 06:00 to 06:00 the next day. Moving the
  hour repaints the heat and updates the estimate.
- **What's on** — the day's events in start order with venue and address, the event under the
  pointer expanded in a card under the list (so the rows never shift), and "occurring now" /
  "soon" marks for the chosen hour.
- **Why this number?** — the expanded event shows the capacity and its source, the fill factor,
  the interest signals, the attendance band, the Liiga backtest error, any competition
  discount, and any shared-building venue split. The working is inspectable instead of hidden
  behind a single total.
- **Honest time labels** — an event with no published start is shown as **Start TBA**, not as a
  false 19:00 start. Its heat is spread over a documented **18:00–20:00** window instead of a
  single 19:00 peak, and the panel says so.
- **Event dots** — gigs red, sports blue, student parties amber, stage purple, culture teal and
  community grey. Tap or click a dot for its title, time and venue.
- **Phone layout** — the page detects a phone (`html.is-mobile`) from a narrow or coarse-pointer
  viewport, uses a 50dvh map, a compact legend, larger phone type and touch targets, and
  safe-area padding, and never scrolls sideways. On phones, **Why this number?** opens in a
  bottom sheet so the event list keeps its place, and the tapped event's card stays pinned at the
  top of the event panel while the rows scroll under it; desktop keeps the inline disclosure.
- Pan, wheel-zoom and ± buttons on the map itself.

Every number is an estimate: `≈`, with a range. There is no tracking, no personal data and no
claim of measured attendance.

## Data sources

- Music: [Tampere Keikat](https://github.com/zakker111/tampere-keikat), read-only. A listing
  whose venue is only a district or cannot be resolved to a street address is dropped and
  logged, never placed at a generic city point.
- Sports: the public Liiga game list, filtered to Ilves and Tappara home games at Nokia Arena.
- Student: Kide's public Tampere product list. Its list endpoint has no coordinates; when a place
  does not match the registry, the product detail's published street address and point are used.
  Entries with only a vague place or a postal box are dropped and logged, never guessed. Every
  future product in the list is considered; there is no row cap.
- Stage, culture, library and community: Tampereen tapahtumakalenteri, which publishes both a
  point and a street address for each location. Every future single-day listing is considered;
  there is no row cap.

`data/seed_events.json` holds SAMPLE placeholders and is **not** read by the normal build. It is
loaded only with `--with-samples`, and `validate.py` refuses to publish a placeholder. Duplicate
listings for the same venue, date, normalized title and start are merged; distinct showtimes are
kept. A missing start is never merged with a timed run.

## Calibration

The hockey fill factor is fitted to the **reported spectators** in the public Liiga game list.
The latest fit used 20 completed Ilves/Tappara home games (22 Sep–15 Nov 2026), moved the fill
from 0.85 to 0.425, and is published with a leave-one-out backtest: median absolute error 19.4 %,
mean error 20.9 %, bias −7.6 %, 55 % of games within ±20 %. Those figures are for hockey only;
they are not a claim about every event.

The city calendar's `maxParticipants` is a **published capacity cap, not measured attendance**.
It is used as the event capacity, capped by the venue's own capacity, and reported as a coverage
count; it is never used as backtest ground truth. The site's panel explains which capacity and
fill each estimate used.

### Shared catchments

Concurrent events that draw from the same districts should not each count the whole shared
catchment. The build therefore applies a **competition factor** after every event has its own
independent estimate. The assumptions are deliberately explicit:

- only events on the same day compete;
- their active windows must overlap; the temporal overlap is the overlap divided by the shorter
  window;
- catchment overlap is the sum of `min(zone share)` over the two events' published top zones;
  the unlisted remainder is **not** assumed to overlap;
- a pair competes only when that top-zone overlap is at least **50%**; weaker overlaps stay
  inside the model's noise band;
- the shared slice is one demand pool sized by the largest exposed event. Each event keeps its
  unique slice and receives a share of the pool proportional to its exposed demand;
- a 5% floor prevents any event from losing more than 95% of its independent demand.

This is a **prior, not a fitted or measured substitution model**. It scales the attendance band,
street legs, corridors and map dots together so the panel and the heat agree. The current build
discounts 300 of 565 events (median factor 0.993 over all events, range 0.439–0.998); a discount
appears in the panel only when the factor is below 0.999, labelled "shared demand, not a measured
split".

### Venue collisions

Two distinct listings at one building and one published start should not each claim the whole
building. The build groups flows by **venue, date and exact published start** and caps the group's
combined mid estimate at the **smallest applicable venue capacity**. For a mixed programme such
as hockey and futsal at Nokia Arena, that is the smaller of the two published configurations
(13,455), not the arena's concert capacity. Above the cap, the cap is allocated in proportion to
each event's independent mid and the integer remainder goes to the largest fractional shares, so
the published combined figure is exactly the capacity. The attendance band, legs, corridors and
map dots scale together.

Every shared group carries `basis.venue_collision` and `data.json.calibration.venue_collisions`.
All such groups are flagged `room_split: "UNRESOLVED"`: the sources publish no room allocation,
and a per-event `maxParticipants` cap does not say which room a listing uses. TBA rows are not
grouped because they have no single published start. The current build has 6 shared groups
covering 14 events; none currently exceeds its capacity (0 capped groups), and all 6 room splits
are unresolved. A synthetic three-event model test covers the over-cap proportional allocation.
The event panel shows a **Venue split** row for these events, including when the group already
fits, so an unresolved shared building is never mistaken for independent rooms.

### Unknown venue capacity

A venue whose hall size nobody publishes is marked `capacity_unknown` in the registry; it does
not inherit the 20-seat model floor or another room's capacity. These events stay in the day list
with their capacity source, but publish no attendance number and add no heat. `attendance.mid`,
`high` and `spread` are `null`, `basis.capacity` is `null`, and `basis.capacity_unknown` is true;
`data.json.calibration.capacity_unknown` counts them. The current build has two: **Sin City** and
the combined **Sin City + H5 Bar**. H5's 150 seats are recorded as known, but they are not used as
the combined capacity.

### Unknown starts

A row with no published start keeps its empty time and stays labelled **Start TBA**. Its heat is
not pinned to 19:00: the arrival and egress curves are averaged uniformly over **18:00, 19:00 and
20:00**, the documented two-hour window centred on the old fallback. Each TBA flow carries
`start_options` and `start_window`; the map mixes those candidate starts, and the row is not
marked "occurring now" against a precise time. This is a prior about uncertainty, not a measured
start. The current build has 22 TBA events.

## Performance

- The build writes `web/geo/days/<date>.json`: that day's flows and only the walking legs they
  use. The browser fetches just the selected day instead of the full 4.2 MB flows + routes pair;
  the 127 day files total 9.6 MB and the largest is 409 KB. The full files remain for validation
  and the route/data gates, and the browser falls back to them if a day file is unavailable.
- Heat is rasterised in an `OffscreenCanvas` worker when available, so a fresh day or route
  change does not block the main thread; the synchronous renderer remains the fallback.
- While dragging, wheeling or zooming, the map renders at a lower internal DPR and restores full
  quality after the interaction. The hour scrubber uses 0.55-quality heat samples and restores
  full quality 160 ms after the last input. Long OSM traces are decimated for the heat.
- The basemap is composed once into a cached tile canvas, so a pan or heat repaint does not
  redraw every tile. Browser route geometry is simplified at build time (Douglas-Peucker, ~9 m)
  and rounded to five decimals; the full OSRM geometry stays in `registry/routes.json`.
- The three Latin WOFF2 font subsets are served from `web/fonts/` with preloads, so rendering
  does not wait on a Google Fonts connection. JSON is fetched with normal HTTP caching.
- The hour slider updates row state in place instead of rebuilding the list on every input.

## Build

```bash
python3 scripts/routes.py --from-flow   # add missing walking legs (optional)
python3 scripts/build.py --city tampere --mode full
python3 scripts/validate.py             # schema, conservation, coverage
python3 -m http.server -d web 3003      # preview at http://localhost:3003

# model + browser tests (the browser suite starts its own server on :4173)
cd tests && npm ci && npx playwright install chromium && npm test
```

The suite runs 18 Python model tests for calibration states, cap edges, dedupe, missing-time
handling, TBA start options, competition cases and venue-collision allocation, plus 8 Python
tests for the route-coverage and data-churn gates. It then runs 24 Playwright checks: switching
days, both ends of the hour slider, tapping a real map dot with a mouse and with a touch,
duplicate-free data, TBA labels and spread window, capacity caps, the competition and venue-split
panel rows, the "Why this number?" panel, the Liiga fitted-fill/backtest text, hovering a row
without moving the list at 1280×900 and at 800×900, tapping a phone row whose card is scrolled
away, the phone Why sheet, the day-bundle fallback, a dragged hour slider bringing the heat back
without queueing a raster per step, and a heat worker that never answers falling back to the
main thread. The build workflow runs it before deployment, then
runs a separate live Pages smoke test after deployment.

## Deploy

GitHub Actions → Pages. `Pages → Source` must be **GitHub Actions**.

The workflow refreshes events once a week, on Sundays at 04:00 UTC, and also runs on pushes
that change the build. Pull requests run the same build, route, validation and browser checks
without deploying. `validate.py` and the test suite block deployment, so a failed build leaves
the last good site up. A main deployment is smoke-tested against the live Pages URL; if that
check fails, the previous Pages artifact is redeployed, the job fails, and a `CI failure` issue
is opened or updated.

No map key or secret is required: the basemap is OpenStreetMap raster tiles. Optional secret
`DIGITRANSIT_API_KEY` is available at build time for routing.

## Honesty

Venue points are OpenStreetMap address points where available; points that are approximate are
flagged. Capacities nobody publishes are class priors, except venues marked `capacity_unknown`
(Sin City), which publish no estimate rather than a prior. Only Liiga hockey has reported
attendance for a backtest; every other category keeps a prior rather than pretending to be
calibrated, the competition factor is a sharing prior rather than a measured split, the venue
collision cap shares one building without claiming a room allocation, and the TBA start window is
an uncertainty prior rather than a measured start. Music, sports, student and calendar rows are
real published events, never placeholders.

See `AGENTS.md` for the data contract and `VERSIONS.md` for release and model provenance.
