# Kilinkolin

An **estimated crowd-flow heat map** for Tampere. Pick a day and an hour; the map shows where
people are likely to be walking or riding to events at that moment, following real streets.
No event listings, no clutter. Kilinkolin is a made-up name ("kilinkolin" is the sitsit toast).

Live: https://zakker111.github.io/kilinkolin/

## What it does

- **Day strip + hour slider** — choose a date, drag 15:00 to 02:00 in 15-minute steps. The heat
  aggregates every event that day, weighted by how much of each crowd is arriving in that window.
- **Street heat** — close districts walk; farther ones ride tram, bus or train, so their corridor
  follows the main road to the venue. Yellow = thin flow, deep red = concentrated.
- **Estimate card** — `≈ people estimated on routes` for the chosen time, plus how many events feed it.
- Pan, wheel-zoom and ± buttons on the map itself.

Every number is an estimate: `≈`, with a range. No tracking, no personal data, no claim of
measured attendance.

## Build

```bash
python3 scripts/routes.py --from-flow    # add missing street geometry to the cache
python3 scripts/build.py --mode full     # writes web/data.json + web/geo/*.json
python3 scripts/validate.py              # schema, conservation, coverage checks
python3 -m http.server -d web 3003       # preview
```

## Deploy

GitHub Actions → Pages. `Pages → Source` must be **GitHub Actions**.

- No map key or secret is required: the basemap is OpenStreetMap raster tiles and the route
  cache is built ahead of time, never in the browser.
- Optional **secret** `DIGITRANSIT_API_KEY` — not used by the default build.

The workflow runs a daily event sync (05:15 UTC), a weekly full rebuild (Sun 04:00 UTC), and on
pushes. It fetches street geometry for new origins, rebuilds, validates and deploys. A failed
validation blocks deployment; the last good site stays up.

## Data & honesty

- Music events come from [Tampere Keikat](https://github.com/zakker111/tampere-keikat) (MIT), read-only.
- Sports, student, theatre and library rows in the demo feed are **SAMPLE** rows until their
  adapters are wired (see `TODO.md`). They contribute to the hourly aggregate but are never
  presented as measured.
- Attendance = venue capacity × fill prior × interest score. Origins = population gravity over
  travel impedance; corridors are the OSRM road network, not observed trips.
- See `AGENTS.md` for rules and `VERSIONS.md` for model/schema provenance.
