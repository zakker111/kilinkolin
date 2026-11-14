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
- Population figures are approximate public statistics.
- Venue coordinates are approximate (see `registry/venues.json`), not survey-grade.
- Rows flagged `SAMPLE` in the UI are placeholder rows for categories whose real feeds
  are not wired yet (sports, student, theatre, library). They are never presented as real.
- Street geometry comes from the FOSSGIS OSRM service over OpenStreetMap data (ODbL).

## Not affiliated

Google Maps, Ticketmaster, Eventz / Tampereen tapahtumakalenteri, Digitransit, Liiga,
Korisliiga, Superpesis, TREY, Tamko and Kide are third-party services with their own terms.
Nothing here implies endorsement by them.
