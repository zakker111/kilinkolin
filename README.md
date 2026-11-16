# Kilinkolin

An **estimated crowd-flow heat map** for events in Tampere: pick a day, drag the hour, and see
where the estimated crowd is on the streets at that moment. The map is the answer; the panel
names what is on.

Live: https://zakker111.github.io/kilinkolin/ · **v0.13.6** · model **2026.11.6** · schema **2**

## What it does

- **Street heat** — a density field over real walking routes from every district to every event
  happening that day. Dark red is the busiest streets, yellow the quietest.
- **Arrivals and departures** — the heat includes people walking to events and people leaving
  them, so a venue keeps its crowd through the evening instead of going dark at the start.
- **Day strip + hour scrubber** — 15-minute steps from 06:00 to 06:00 the next day. Moving the
  hour repaints the heat and updates the estimate.
- **What's on** — the day's events in start order with venue and address, the event under the
  pointer expanded, and "occurring now" / "soon" marks for the chosen hour.
- **Event dots** — gigs red, sports blue, student parties amber, stage purple, culture teal and
  community grey. Tap or click a dot for its title, time and venue.
- **Phone layout** — the page detects a phone (`html.is-mobile`) from a narrow or coarse-pointer
  viewport, uses a 50dvh map, a compact legend, larger touch targets and safe-area padding, and
  never scrolls sideways.
- Pan, wheel-zoom and ± buttons on the map itself.

Every number is an estimate: `≈`, with a range. There is no tracking, no personal data and no
claim of measured attendance.

## Data sources

- Music: [Tampere Keikat](https://github.com/zakker111/tampere-keikat), read-only.
- Sports: the public Liiga game list, filtered to Ilves and Tappara home games at Nokia Arena.
- Student: Kide's public Tampere product list. Its list endpoint has no coordinates; when a place
  does not match the registry, the product detail's published street address and point are used.
  Entries with only a vague place or a postal box are dropped and logged, never guessed. Every
  future product in the list is considered; there is no row cap.
- Stage, culture, library and community: Tampereen tapahtumakalenteri, which publishes both a
  point and a street address for each location. Every future single-day listing is considered;
  there is no row cap.

`data/seed_events.json` holds SAMPLE placeholders and is **not** read by the normal build. It is
loaded only with `--with-samples`, and `validate.py` refuses to publish a placeholder.

## Performance

- Browser route geometry is simplified at build time (Douglas-Peucker, ~9 m) and rounded to five
  decimals. The full OSRM geometry stays in `registry/routes.json`.
- JSON is fetched with normal HTTP caching, and phone rendering caps canvas DPR and heat samples.
- The hour slider updates row state in place instead of rebuilding the list on every input.

## Build

```bash
python3 scripts/routes.py --from-flow   # add missing walking legs (optional)
python3 scripts/build.py --city tampere --mode full
python3 scripts/validate.py             # schema, conservation, coverage
python3 -m http.server -d web 3003      # preview at http://localhost:3003

# browser smoke test (starts its own server on :4173)
cd tests && npm ci && npx playwright install chromium && npm test
```

The smoke suite covers switching days, both ends of the hour slider (`06:00` and
`06:00 +1`) and tapping a real map dot. The build workflow runs it before deployment.

## Deploy

GitHub Actions → Pages. `Pages → Source` must be **GitHub Actions**.

The workflow refreshes events once a week, on Sundays at 04:00 UTC, and also runs on pushes
that change the build. `validate.py` and the Playwright smoke suite block deployment, so a
failed build leaves the last good site up.

No map key or secret is required: the basemap is OpenStreetMap raster tiles. Optional secret
`DIGITRANSIT_API_KEY` is available at build time for routing.

## Honesty

Venue points are OpenStreetMap address points where available; points that are approximate are
flagged. Capacities nobody publishes are class priors. Music, sports, student and calendar rows
are real published events, never placeholders.

See `AGENTS.md` for the data contract and `VERSIONS.md` for release and model provenance.
