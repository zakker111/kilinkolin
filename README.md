# Kilinkolin

An **estimated crowd-flow map** for events in Tampere: pick a day and an event, and see where its
crowd comes from, how it travels, and when it arrives. No lists, no clutter — just the map.
Kilinkolin is a made-up name ("kilinkolin" is the sitsit toast).

Live: https://zakker111.github.io/kilinkolin/

## What it does

- **Origin heat map** — dark red = more likely origin, pale rose = less likely, on an
  OpenStreetMap basemap. No API key needed.
- **Corridors** — mode-coloured routes from the main origins, with moving arrival dots.
- **Time scrubber** — 2 hours before to 1 hour after the start; the arrival dots move with it.
- **Event panel** — estimated attendance with range, interest score and its signals,
  origin split, mode split, arrival profile.
- Pan, wheel-zoom and ± buttons on the map itself.

Every number is an estimate: `≈`, with a range. No tracking, no personal data, no claim of
measured attendance.

## Build

```bash
python3 scripts/build.py --mode full   # writes web/data.json + web/geo/*.json
python3 scripts/validate.py            # schema, conservation, coverage checks
python3 -m http.server -d web 3003     # preview
```

## Deploy

GitHub Actions → Pages. `Pages → Source` must be **GitHub Actions**.

- No map key or secret is required: the basemap is OpenStreetMap raster tiles.
- Optional **secret** `DIGITRANSIT_API_KEY` — build-time routing (not yet used by the default build).

The workflow runs a daily event sync (05:15 UTC), a weekly full rebuild (Sun 04:00 UTC),
and on pushes. A failed validation blocks deployment; the last good site stays up.

## Data & honesty

- Music events come from [Tampere Keikat](https://github.com/zakker111/tampere-keikat) (MIT), read-only.
- Sports rows come from the public Liiga game list, student parties from Kide's Tampere product
  list, and stage, culture, library and community rows from the city's own event calendar. Every
  row is a real listing from one of those feeds; `validate.py` rejects a placeholder.
- Every event sits on a venue with a **street address**, and the panel and the row list show that
  address beside the venue. The student source publishes no coordinates, so a product is published
  only when its place is already a registry venue — otherwise it is dropped and logged.
- Attendance = venue capacity × fill prior × interest score, calibrated against reported league
  attendance once that scraper lands. Origins = population gravity over travel impedance.
- See `AGENTS.md` for rules and `VERSIONS.md` for model/schema provenance.
