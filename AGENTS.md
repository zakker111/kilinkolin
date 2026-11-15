# AGENTS.md — Kilinkolin

Working notes for anyone (human or agent) changing this repo.

## What this is

A static site: one **estimated crowd-flow heat map** for Tampere. The only controls are a day and
an hour; the map aggregates every event that day into the streets people are estimated to be on
at that moment, plus the number on the move. There are no event listings by design.
Python builds the data in GitHub Actions; the browser only fetches JSON, tiles and renders.
The workflow refreshes every day at 05:15 UTC and does a guaranteed full rebuild on Sundays at
04:00 UTC: new events are fetched, their missing street routes are added, the model is rebuilt,
validated and deployed to Pages.
Hosted on GitHub Pages at `https://zakker111.github.io/kilinkolin/`.

Not a fork of Tampere Keikat — it reads that project's published feed. See `NOTICE.md`.

## Hard rules

1. **Never write to `zakker111/tampere-keikat`.** It is read-only input.
2. **Never commit API keys.** `DIGITRANSIT_API_KEY`, if added, is a *secret* used only in Actions.
   The basemap uses keyless OpenStreetMap tiles; if a paid tile provider is ever configured it
   belongs server-side or as a referrer-restricted key, never in `web/config.js` by hand.
3. **Never present an estimate as a measurement.** Every number is `≈` with a range, and the UI
   says "estimated flow model". Do not remove those labels.
4. **Never invent data.** No fabricated attendance, capacity or population figures. Missing input
   means a wider band plus a note, not a made-up number.
5. **Time zone:** all event times are Europe/Helsinki. A start between 02:00 and 06:00 is a
   suspected parsing bug — investigate, don't publish silently.
6. **Subpath safety:** the site is served from `/kilinkolin/`. Always use relative URLs
   (`./data.json`), never `/data.json`.
7. **Keep attribution:** `LICENSE`, `NOTICE.md` and the footer credit stay.

## Layout

```
web/            index.html, app.js, map.js, styles.css, config.js, data.json, geo/*.json
scripts/        build.py (pipeline), validate.py (gate)
data/           keikat.json (feed snapshot), seed_events.json (SAMPLE rows)
registry/       venues.json, zones.json  (hand-maintained)
.github/        workflows/build.yml
```

## Commands

```bash
python3 scripts/routes.py                 # add missing walking legs to the route cache
python3 scripts/routes.py --from-flow     # only legs the current build draws (fast, used in CI)
python3 scripts/build.py --mode full      # fetch, normalise, model, write web/*
python3 scripts/validate.py               # gate: schema + conservation + coverage
python3 -m http.server -d web 3003        # local preview at :3003
```

## Data contracts

`web/data.json`:
```json
{ "generated": "... UTC", "schema_version": 2, "model_version": "...",
  "source_status": {...}, "coverage": {...},
  "events": [["date","time","title","venue","genre","free","url",
              "id","kind","category","sub","interest","attendance","sample","venue_id"]] }
```
Indices 0–6 are frozen (older consumers read them positionally). Append only.

`web/geo/flows.json`: per event `attendance{low,mid,high}`, `interest{score,band,signals}`,
`zones[]` (share of arrivals), `modes[]`, `legs[]`, `corridors[]` (straight fallback only),
`arrival[]` and `egress[]` 15-minute slices.

`legs[]` is what the map draws: `{key, name, share, people, mode, km, min}`. `key` resolves into
`web/geo/routes.json`, a cache of real pedestrian geometry (`venue|hub:<id>` or `venue|zone:<id>`),
fetched by `scripts/routes.py` from the FOSSGIS OSRM foot instance and
committed under `registry/routes.json`. Never call a router at runtime and never invent geometry:
missing cache entries fall back to the straight `corridors[]` lines.

Every event must resolve to a venue in `registry/venues.json`.

## Adding a feed adapter

1. Write `scripts/feeds/<source>.py` exposing `fetch() -> list[dict]`.
2. Register it in `build.py`; each adapter records `OK` / `EMPTY` / `FAILED`.
3. An adapter must never raise past its own boundary — one broken source must not blank the site.
4. Rows from a new source are real: do **not** mark them `sample`.

## Before committing

- `validate.py` exits 0.
- `git diff` contains no key, no `vendor/` churn, no build output outside `web/`.
- `TODO.md` updated; `VERSIONS.md` entry if behaviour or schema changed.
- If the UI changed, load it locally and check that picking a day and dragging the hour repaints
  the heat over the tiles and that the estimate box agrees with the map.
