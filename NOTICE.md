# NOTICE

Kilinkolin is an independent project. It is **not** a fork of Tampere Keikat,
though it reuses code and interface patterns from it under the MIT licence.

## Upstream

- Project: **Tampere Keikat** — https://github.com/zakker111/tampere-keikat
- Licence: MIT, © zakker111
- Upstream commit referenced while adapting: `4be498d308a8eb97b22888e93f5b9b734dbabcd5` (2026-11-14)
- What was adapted:
  - The visual language, layout and interaction model of `index.html` (hero, sticky controls, ticket cards, month grid).
  - The row-based event schema `[date, time, title, venue, genre, free, url]` — extended here with
    `[id, kind, category, subcategory, interest, attendance, sample, venue_id]` so older consumers keep working.
  - The idea of per-source status reporting and a bundled fallback feed.

## Data

- Music event data is read at build time from the published Tampere Keikat feed
  (`https://zakker111.github.io/tampere-keikat/data.json`). Read-only; this repo never
  writes to that project.
- Sports fixtures come from the public Liiga game list, filtered to Ilves and Tappara home
  games in Tampere.
- Student events come from Kide's public Tampere product list. Its list endpoint has no coordinates;
  unresolved products use the street address and point published on the product detail. Entries
  with only a vague place or a postal box are dropped and logged, never guessed.
- Stage, culture, library and community events come from Tampereen tapahtumakalenteri, using
  the calendar's own published point and street address.
- Population figures are approximate public statistics.
- Venue points are OpenStreetMap address points where available; approximate points are
  flagged in `registry/venues.json`, not presented as survey-grade.
- Street geometry comes from the FOSSGIS OSRM service over OpenStreetMap data (ODbL).
- No SAMPLE or placeholder rows are published. `data/seed_events.json` is loaded only with
  `--with-samples`, and `validate.py` rejects a placeholder in the live data.

## Not affiliated

OpenStreetMap, FOSSGIS/OSRM, Tampereen tapahtumakalenteri, Liiga, Kide and Tampere Keikat are
third-party services with their own terms. Nothing here implies endorsement by them.
