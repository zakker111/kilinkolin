# VERSIONS — Kilinkolin

## App

### 0.20.2 — 2026-11-18
Event list: hovering can no longer steal the click it was about to receive.

- Fixed: selecting a row rebuilt the detail card, whose height change moved the
  list under a still pointer and fired another selection — a hover cascade that
  made rows and the Why button unclickable while it ran. On a mouse the list now
  follows real pointer movement (`mousemove`) instead of `mouseenter`.
- Fixed: phones and other coarse pointers no longer select rows on hover at all;
  tapping still does, and the pinned detail card no longer lands on the row under
  the finger.
- Verified: the CI mobile Why-sheet sequence (row tap, open, close, backdrop,
  Escape, focus return) in a 390x844 touch context, desktop hover still selecting
  the row under the mouse, and the validator.

### 0.20.1 — 2026-11-18
Crush hour at a glance: a day sparkline under the hour bar, plus mobile layout fixes.

- Added: a small sparkline between the hour bar and the map plotting total people on routes for
  every 15-minute slot from 06:00 to 06:00. The peak is marked and labelled, and a cursor follows
  the chosen hour. Totals come from `KMap.dayPeople(minute)`, the same rule the estimate card
  uses, so the two cannot disagree.
- Fixed: the Why sheet's "Competition" label no longer runs into its value on a phone.
- Fixed: the legend's category dots wrap instead of overflowing on 320–360 px screens.
- Verified: 390×844 touch layout (sparkline, map, panel, Why sheet, dot taps, playback), no
  horizontal overflow from 320 to 1280 px, no long tasks while scrubbing or playing, the 26
  Python tests and the validator.

### 0.20.0 — 2026-11-18
When to go: the card now names the quietest arrival and when most people arrive.

- Added: a timing line on every timed event card — "Quietest arrival ≈ HH:MM; most arrive ≈ HH:MM."
  — read straight from the per-event `arrival[]` slices the model already ships. No recomputation,
  no new data, no new fetch.
- Verified: the card shows a "Quietest arrival" and a "most arrive" time for a timed event; 27
  Playwright checks, the 26 Python tests and the validator.

### 0.19.0 — 2026-11-18
An event card you can act on: walking directions and a calendar file.

- Added: "Directions" on every detail card opens a keyless maps link to that venue's own published
  point (`google.com/maps/dir/?api=1&travelmode=walking&destination=lat,lon`), so a phone hands it
  to the installed maps app and a desktop opens the directions tab. Walking, because the heat is
  people walking.
- Added: "Add to calendar" builds a one-event `.ics` in the page and downloads it as
  `kilinkolin-<day>-<title>.ics`. Times are written as UTC stamps converted from Helsinki
  wall-clock, so no `VTIMEZONE` block is needed and every calendar reads them; the description
  carries the estimated crowd, labelled as an estimate, and the map's own address.
- Added: a TBA event gets Directions but no calendar entry — a start time that is not published is
  not invented for a file that would then sit in someone's day.
- Verified: the card's directions link carries the venue point and the downloaded file opens in
  the right hour when its UTC stamp is read back in Helsinki; a TBA card offers no calendar
  button. 27 Playwright checks, the 26 Python tests and the validator.

### 0.18.0 — 2026-11-18
Play the day: a play button walks the hour from 06:00 to 06:00.

- Added: the ▶ button beside the hour label steps the slider every 160 ms — 15 minutes per step,
  so a whole day takes about 15 s — and the arrival and egress curves can be watched instead of
  stepped. The button turns into ⏸ while it runs and back when it stops.
- Added: playback starts from the hour already on screen, restarts at 06:00 when the slider is
  already at 06:00 the next morning, and stops at the end. The map stays in its scrubbing mode for
  the run (0.55-quality heat, low-DPR canvas) so the frames keep up, and stopping restores full
  quality.
- Added: a manual scrub, a day switch or a pasted hash stops playback, so the timer never fights
  the controls it is animating.
- Verified: the play button moves the slider forward and toggles ⏸/▶ in the Playwright suite;
  26 Playwright checks, the 26 Python tests and the validator.

### 0.17.0 — 2026-11-18
A view can be linked: the day, hour, zoom and centre live in the URL hash.

- Added: the address bar always carries the view as
  `#d=2026-11-18&t=1095&z=13.20&c=61.49780,23.76100` — `d` the day, `t` minutes after midnight
  (the slider's 360-1800 range), `z` the zoom and `c` the map centre as `lat,lon`, since a pan is
  the centre moving. Opening a link restores that day, hour and camera; a day that is no longer
  in the feed is ignored and the first day is shown instead.
- Added: the hash is rewritten with `history.replaceState` ~180 ms after the view settles, so a
  drag writes once instead of once per tick and the back button still leaves the page instead of
  walking every hour of the evening. A pasted or edited hash moves the map, day strip, hour slider
  and panel without a reload.
- Verified: a link to the third day with `t=1380`, `z=14.60` and a shifted centre opens exactly
  that view (slider at 1380, "23:00", that chip marked on), a pan at 19:15 writes `t=1155` plus the
  moved centre and zoom, and reopening that hash lands on the same camera. 25 Playwright checks,
  the 26 Python tests and the validator.

### 0.16.9 — 2026-11-18
The heat comes back when the worker falls behind, and a dead worker no longer leaves a bare map.

- Fixed: the heat layer could vanish and stay away after switching days or dragging the hour
  slider. Every new view posted another full padded raster to the heat worker while the earlier
  ones were still queued, so a drag queued one raster per 15-minute step and the newest view waited
  behind all of them; the main thread deliberately draws no heat until the reply arrives.
  Measured at 1280×900 after 12 day switches and a 45-step drag: 445 rasters posted, 60 still
  queued, and the heat absent for ~10 s after the drag stopped.
- Changed: one raster is in flight at a time. A newer view waits for the current reply, and the
  repaint that follows posts the newest state, so a drag costs one raster per raster completed
  instead of one per tick (221 posts, 221 replies in the same run) and the heat returns at once.
- Fixed: a worker that never answers (killed for memory, blocked, wedged) left the map without
  heat for the rest of the session and logged nothing. A 6 s watchdog now stops it, warns once and
  lets the synchronous renderer draw; the worker's error paths share the same `stopHeatWorker`.
- Verified: 8 fresh loads at 5239 heat pixels each, the stress run returning heat immediately, a
  worker that never answers painting on the main thread, 24 Playwright checks, the 26 Python tests
  and the validator.

### 0.16.8 — 2026-11-18
One simpler answer to the rows sliding under the pointer.

- Changed: the event panel's detail card now sits **under** the row list on any layout with a
  pointer. A card above the list grew over the rows and slid them ~100 px out from under the
  pointer; a card below it can only take space from the list's bottom, so growing it never moves a
  row. Measured at 1280×900: 0 px of row movement with the list at the top, at the bottom and
  near the bottom, and 0 px again when the working expands (403 px of working, all of it visible).
- Removed: the fixed 150 px slot, its inner scroll box, the `scrollTop` reset and the
  `scrollIntoView` call in `app.js` that kept that scroll box usable. The list gains the space
  back (598 px instead of 495 px at 1280×900, about 16 rows) and the selected card is never
  clipped, so nothing has to be scrolled inside it.
- Fixed: the same slide happened in pointer windows between 700 and 1000 px wide, where the panel
  has no fixed height and the card stayed above the list; the card-under-list rule is keyed off
  `html:not(.is-mobile)`, so it covers that range.
- Changed: the idle hint now says the rows are above it on pointer layouts (`row above`), which is
  where they are; phones keep the pinned card on top with the rows under it.
- Verified: hover checks at 1280×900 and 800×900 (no row moves, the card stays inside the panel),
  the working fully visible at 403 px, the phone checks at 390×844, the 21-check Playwright suite,
  the 26 Python tests and the validator.

### 0.16.7 — 2026-11-18
Keep the event rows still, and keep the event a phone taps in view.

- Fixed: hovering an event row grew the detail card above the list (a 52 px hint became a card of
  130 px median and 164 px at its tallest, measured over 96 events), which slid every row down
  about 100 px and left the pointer over a neighbouring event. On desktop the card now keeps a
  fixed 150 px slot and scrolls its own overflow, so the rows never move and the hovered row is
  the row that stays selected. The slot fits 95 of the 96 measured cards exactly and the list
  shows one more row than a slot at the tallest card would; the idle slot is a centred hint with
  no box, so the reserved space reads as a detail pane instead of an empty card.
- Changed: the desktop **Why this number?** working scrolls inside that slot and is scrolled into
  view when it opens, instead of overflowing a small nested scroll box.
- Fixed: on phones the detail card is pinned to the top of the event panel, so tapping an event
  while the list is scrolled no longer draws its card above the panel's own viewport, where the
  tap looked like it did nothing. The rows move under the pinned card and the tapped row still
  turns up selected. The pinned card carries its own opaque fill and a shadow, since the shared
  selected-card rule is translucent and the rows now pass underneath it.
- Fixed: tapping a map dot on a phone was undone by the finger lift. A touch pointer fires
  `pointerleave` straight after the tap, which cleared the highlighted dot, hid the tooltip and
  reset the event card, so a dot tap showed nothing at all on a phone (it worked with a mouse).
  Touch pointers no longer clear the dot their tap just named, so the tip and the card stay.
- Verified: 1280×900 hover checks (row tops and card height unchanged, the hovered row keeps
  `.sel`), 390×844 phone checks (a row tapped inside a scrolled panel keeps its card on screen, a
  tapped map dot keeps its tip and card), the full 21-check Playwright suite, the 26 Python tests
  and the validator.

### 0.16.6 — 2026-11-17
Refine the phone event panel and finish the venue address provenance.

- Changed: on phones, **Why this number?** opens in a modal bottom sheet instead of expanding the
  event panel. The sheet has its own scroll area, closes via Close, Escape or the backdrop, and
  returns focus to the trigger; desktop keeps the inline disclosure.
- Changed: the phone event panel is one `50dvh` scroll area with no nested detail/list caps, so the
  event rows keep their place while the explanation is open.
- Changed: initial and day-switch flow loading share one fallback helper; after a missing day
  bundle, the full `flows.json` + `routes.json` pair is cached and reused instead of re-fetched.
- Changed: redundant phone type overrides were removed, and Metso is marked `approx: false`.
  Megazone (Hammareninkatu 6) and Valkeakosken kesäteatteri (Pässinmäenkatu 30) were checked
  against their official pages and now carry official sources.
- Verified: 390×844 sheet and focus checks, desktop inline disclosure, validator 0 errors (1 known
  straight-line warning) and 26 Python tests.

### 0.16.5 — 2026-11-17
Increase phone legibility and harden the event-selection and fallback paths.

- Changed: phone-specific type sizes raised across the header, day strip, estimate card, legend,
  event list, detail and footer. The event panel gets a little more vertical room, and the map
  zoom buttons grow to 40 px. Desktop typography is unchanged.
- Fixed: event rows are now keyboard-focusable buttons; Enter and Space select the event.
- Fixed: a missing per-day bundle now falls back to the full `flows.json` + `routes.json` pair when
  switching days, matching the initial-load fallback instead of leaving the old day on screen.
- Fixed: generated timestamps are converted to a valid ISO value before the stale badge is set,
  and the "Why" panel id is sanitized before it is used in markup or lookup.
- Verified: phone checks at 390×844 and 320×568 with no sideways scroll, desktop at 1280×900,
  keyboard Enter selection, a 404 day-bundle fallback, 0 validator errors (1 known straight-line
  warning) and 26 Python tests. Browser console is clean.

### 0.16.4 — 2026-11-16
Audit Tampere venue capacities against LiveFIN and keep unpublished rooms unknown.

- Changed: corrections from LiveFIN's open Venuelista (retrieved 2026-11-16): Tampere-talo
  1800→1952, Tavara-asema 1000→1200, TTT-klubi 300→230, Maanalainen 150→70, Vastavirta
  200→100, Public House Huurre 120→90, Paapan Kapakka 90→110, Bar Kotelo 0→200,
  Viihdemaailma Ilona 700→1000, and Yo-talo 900→400 (LiveFIN records live music ended
  2024-05-31).
- Changed: Tullikamari split into Klubi (450) and Pakkahuone (1200). Generic "Tullikamari"
  feed names stay on Klubi because the room is not published.
- Changed: Sin City is a real venue with no published capacity. MerirosvoKolmiot resolves to
  **Sin City + H5 Bar**, not H5 alone; H5's 150 seats are recorded but never used as the
  combined capacity.
- Changed: a venue with `capacity_unknown` publishes no attendance number and no heat:
  `attendance.mid/high/spread` and `basis.capacity` are null, `basis.capacity_unknown` is true,
  and `data.json.calibration.capacity_unknown` counts them. Kide rows at H5 consult the product
  detail place, so a list place of "H5 Bar" cannot hide Sin City.
- Kept: Telakka (local 400 vs LiveFIN 120) and F54 (300 vs LiveFIN Fame Club 850) unchanged;
  the active theatre/club room and successor relationship are not confirmed.
- Model 2026.11.16, schema 3. Verified: 565 events, 156 venues, 2 unknown-capacity events,
  300 discounted events (median factor 0.993, discounted range 0.439–0.998), 6 shared groups
  covering 14 events, 22 TBA flows, 48 published city caps, 0 validator errors (1 known warning:
  2 straight-line corridors) and 26 Python tests. Playwright could not launch in this container
  because `libnspr4.so` is missing; that is an environment limitation, not a test result.

### 0.16.3 — 2026-11-16
Load only the selected day and keep heat rendering off the main thread.

- Changed: `build.py` now writes `web/geo/days/<date>.json` bundles containing the day's flows
  and the union of routes they use. The browser lazy-loads only the selected day and falls back
  to the full `flows.json` + `routes.json` pair if a bundle is missing. All 127 bundles total
  9.6 MB; the largest (26-event day) is 409 KB vs the 4.2 MB full pair. The full files remain for
  validation and the route/data gates.
- Changed: heat rasterisation moved to `web/heat-worker.js` on an OffscreenCanvas. The main
  thread keeps the existing synchronous renderer as a fallback when workers or OffscreenCanvas
  are unavailable; stale worker results are discarded by request id.
- Changed: during drag, wheel and zoom animation the map uses a lower internal DPR, then restores
  full quality after 160 ms idle. The hour scrubber samples heat at 0.55 quality and restores full
  quality after the same delay. Long OSM traces are decimated only for the heat.
- Changed: the basemap is composed into a cached tile canvas, so pan and heat repaints do not
  redraw every raster tile. The day event list is cached per refresh.
- Changed: Bebas Neue, IBM Plex Mono and Inter Latin WOFF2 subsets are self-hosted under
  `web/fonts/` and preloaded; the page no longer opens a Google Fonts connection.
- Verified: 25 Python and 14 Playwright tests pass. On the busiest 26-event day at 1280×900,
  DPR 2, Chromium reports 58.2 fps for a 600 px pan (p95 16.8 ms) and 60.0 fps for continuous
  hour scrubbing, with the worker path active and no console errors. A cached pan and a forced
  fresh rerasterisation at the same camera were pixel-identical, and the zoom/pan screenshots
  showed no clipped heat edge or district-label drift.

### 0.16.2 — 2026-11-16
Keep map panning smooth on busy days.

- Changed: heat is rasterised into a padded bitmap. A pan crops the correct region from that
  bitmap, and the zoom animation scales it, instead of restamping every street on every frame.
  A fresh raster happens only after a large camera move, a zoom settles, or the day/hour changes.
- Fixed: district labels choose from candidates inside the current viewport, so routes kept in
  the padding do not push visible labels offscreen.
- Verified: 25 Python and 14 Playwright tests pass. Chromium 1280×900 at DPR 2 on the busiest
  26-event day: pan improved from 25.3 to 59.7 fps (p95 99.9 ms to 16.7 ms); the zoom preview
  runs at 47.6 fps instead of 32.8 fps.

### 0.16.1 — 2026-11-16
Simplify the heat cache and remove the visual artifacts from the performance pass.

- Changed: removed the 140 ms slider preview and its separate quick/full cache key. The slider
  now draws the single full-quality heat directly.
- Changed: one cache entry now owns both the heat bitmap and the projected route shapes. A hover
  or tile repaint reuses both; a time, day or viewport change rebuilds both. Removed the per-view
  route-geometry map, pan translation branch, `heatInfo`, quick flags and temporary sample arrays.
- Fixed: restored overlapping heat stamps and widened the kernel so zoomed routes no longer show
  a string of beads. Removed the pan shortcut that left a newly exposed map edge unheated until
  the pointer was released.
- Verified: 17 Python and 14 Playwright tests pass; `validate.py` reports 0 errors and the one
  known straight-line corridor warning. Desktop 1280×1000 full redraw is 59 ms one-frame and
  phone 390×844 is 29 ms; heat was visually checked at overview, zoom and pan at both sizes.

### 0.16.0 — 2026-11-16
Stop distinct events at one venue and start from each claiming the whole building.

- Added: a venue/date/start collision guard. Flows are grouped by exact venue, date and published
  start; the group's combined mid is capped at the smallest applicable venue capacity (the smaller
  configuration when a building hosts mixed sport/gig events). Above the cap, the cap is
  allocated in proportion to the independent mids and the integer remainder goes to the largest
  fractional shares, so the combined figure is exactly at or below capacity. The attendance band,
  legs, corridors and map dots scale together. TBA flows are excluded because they have no single
  published start.
- Added: every group member carries `basis.venue_collision{group_size,venue_capacity,
  combined_mid_before,combined_mid_after,factor,room_split}` and
  `data.json.calibration.venue_collisions` records the group/event/capped/unresolved counts. Every
  shared group is `room_split: "UNRESOLVED"`: the sources publish no room allocation, and a
  per-event `maxParticipants` cap does not say which room a listing uses.
- Added: the **Why this number?** panel shows a **Venue split** row for every shared group, even
  when the combined estimate already fits, naming the group size, the building cap and the
  unresolved split. The footer explains the shared-building rule.
- Added: 2 venue-collision model tests for proportional capping and unchanged below-cap groups
  (17 Python total) and a browser panel/data test (14 Playwright total). The validator now
  recomputes every group's combined mid and fails above capacity or on count/metadata drift.
- Model 2026.11.11, schema 3. Verified: 567 events, 154 venues, 22 TBA flows, 49 published city
  caps, 305 discounted events (median factor 0.992 over all events, range 0.439–0.998), 6 shared
  venue/start groups covering 14 events (0 currently above capacity, 6 unresolved room splits),
  0 validator errors and one known straight-line corridor warning; Liiga calibration remains
  FITTED (20 games, fill 0.425, leave-one-out MAPE 20.9%).

### 0.15.1 — 2026-11-16
Spread TBA heat over a documented window instead of pinning it to 19:00.

- Changed: events with no published start now carry `start_options` (18:00, 19:00, 20:00) and
  `start_window` (`18:00–20:00`). The map averages the arrival and egress curves over those
  candidate starts, so the heat is an uncertainty band rather than a single 19:00 peak. The
  published time stays empty and the row/panel still say **TBA**; TBA rows are no longer marked
  "occurring now" against a precise start.
- Added: `data.json.calibration.tba_start` records the `PRIOR` window, the three assumed starts,
  the method and the TBA flow count. `start` (19:00) remains only an internal representative for
  sorting and competition overlap; it is not presented as a published start.
- Added: the TBA heat window to the panel note, map tooltip and footer. The map tooltip now says
  `TBA · 18:00–20:00` instead of `TBA · 19:00`.
- Tests: extended the missing-start model test for the 18:00/19:00/20:00 options (15 Python
  total) and added a browser test that checks a TBA flow contributes heat at 18:00, 19:00 and
  20:00 and less than its full demand at the 19:00 representative (13 Playwright total).
- Model 2026.11.10, schema 3. Verified: 566 events, 154 venues, 22 TBA flows, 49 published city
  caps, 303 discounted events (median factor 0.993, range 0.437–1.0), 0 validator errors and one
  known straight-line corridor warning; Liiga calibration remains FITTED (20 games, fill 0.425,
  leave-one-out MAPE 20.9%).

### 0.15.0 — 2026-11-16
Stop concurrent events from each counting the same shared catchment.

- Added: a competition factor for simultaneous events. Same-day peers compete only when their
  active windows overlap and at least 50% of their published top-zone arrival shares overlap.
  The shared slice is counted once as a demand pool sized by the largest exposed event; each
  event keeps its unique slice and receives a pool share proportional to its exposure. A 5%
  floor applies. This is an explicit prior, not a fitted or measured substitution model.
- Changed: the factor scales the attendance band, street legs, corridors, `data.json` attendance
  and `ev_geo.attendance` together, so the panel and the heat agree. Each flow publishes
  `basis.competition{factor,peers}`; `data.json.calibration.competition` records `status: PRIOR`,
  the method, floor, minimum overlap and discounted-flow count.
- Added: the event panel shows a **Competition** row only when the factor is below 0.999, with
  “shared demand, not a measured split”; the footer says concurrent events share one pool.
- Added: 6 competition model tests (15 Python total) and a browser panel test (12 Playwright
  total). They cover equal events, disjoint catchments, sequential windows, weak overlaps,
  unique-slice retention and a large peer not erasing a small event.
- Fixed: music rows whose venue is only a district (`Nekala`) are dropped and logged instead of
  being published at the unlocatable `tampere_muu` fallback; the validator correctly rejected
  those rows. The live music snapshot also shrank from 97 to 61 rows, so the current event count
  is lower than 0.14.1 — feed churn, not silent truncation.
- Model 2026.11.9, schema 3. Verified: 565 events, 154 venues, 22 TBA starts, 49 published city
  caps, 302 discounted events (median factor 0.993, range 0.437–1.0), 0 validator errors and one
  known straight-line corridor warning; Liiga calibration remains FITTED (20 games, fill 0.425,
  leave-one-out MAPE 20.9%).

### 0.14.1 — 2026-11-16
Collapse duplicate listings and stop showing assumed starts as published times.

- Fixed: duplicate listings at the same venue, date, normalized title and start are merged.
  Distinct showtimes are preserved, and a row with no start is never merged with a timed run.
  The current build merged one duplicate (“Us” at Telakka) and kept both Molli performances.
- Changed: 44 events without a published start are now labelled **Start TBA** in the panel and
  `TBA` in the row list. Their heat is still modelled at 19:00, and the panel/footer say so.
  The map tooltip shows `TBA · 19:00` rather than presenting 19:00 as published.
- Added: the validator rejects two rows with the same venue/date/title/start.
- Added: 9 Python model tests for calibration states, published-cap edge cases, dedupe and
  missing-time handling; 11 Playwright tests cover TBA labels, cap invariants, duplicate-free
  data and the FITTED/PRIOR/INSUFFICIENT/UNAVAILABLE panel copy.
- Changed: the fitted hockey factor replaces the prior only when its leave-one-out MAPE is lower
  than the prior's. This keeps the choice out of sample and makes the PRIOR state reachable.
- Model 2026.11.8, schema 3. Verified: 597 events, 155 venues, 0 validator errors; one newly
  added Kide venue still uses the documented corridor fallback until its street route is fetched.

### 0.14.0 — 2026-11-16
Fit the hockey estimate to reported Liiga attendance and show the working.

- Added: `scripts/calibration.py` fits one hockey fill factor by mean absolute percentage error
  against the `spectators` published for completed Liiga games. The production factor is fitted
  on all 20 completed Ilves/Tappara home games in the current sample (22 Sep–15 Nov 2026).
- Changed: hockey fill 0.85 → 0.425. The prior was overestimating by 91 % MAPE; the fitted
  in-sample error is 16.7 %, and the published leave-one-out error is 20.9 % MAPE / 19.4 %
  median APE, bias −7.6 %, with 55 % of games inside ±20 %.
- Fixed: hockey capacity uses Nokia Arena's sport capacity (13,455), not its larger concert
  capacity (15,000). The previous maximum-of-both rule inflated every Liiga estimate.
- Added: city calendar `maxParticipants` remains a published cap, not observed attendance. The
  build reports 49 events with a published cap, caps each estimate at that figure or the venue's
  own capacity, and never uses the cap as a backtest target.
- Added: every flow carries `basis{capacity, capacity_source, fill, fill_source, interest,
  spread, published_max_participants}`; `data.json` carries the `calibration` block.
- Added: the event panel's **Why this number?** disclosure shows capacity provenance, fill
  provenance, interest signals, attendance band, Liiga backtest error and city-cap coverage.
- Model 2026.11.7, schema 3 (event positions 0–6 unchanged).
- Verified: 596 events, 155 venues, 0 validator errors; 5 Playwright smoke tests pass,
  including the Liiga hockey fitted-fill/backtest panel. One newly added Kide venue still uses
  the documented straight-line corridor fallback until its street route is fetched.

### 0.13.6 — 2026-11-16
Run the scheduled refresh once a week.

- Changed: the scheduled build now runs only on Sundays at 04:00 UTC. The daily 05:15 UTC sync
  and the Sunday 06:00 UTC retry were removed, so a successful week no longer rebuilds twice.
- Kept: pushes that change the build and manual `workflow_dispatch` runs still rebuild and deploy.
- No data, model or schema change: model 2026.11.6, schema 2.

### 0.13.5 — 2026-11-16
Fix malformed source times, repeated showings, and overlong student events.

- Fixed: the music feed writes the event's day and month into the time field when a start is
  missing (`2026-12-05` -> `05:12`, `2026-11-21` -> `21:11`). The build now treats those 16
  values as missing starts, so they use the documented 19:00 fallback and stay on their
  published date instead of moving to the previous night.
- Fixed: city-calendar dedupe keyed only on date and title, dropping five legitimate repeat
  performances (for example a 13:00 and an 18:00 show). The key now includes the start time.
- Fixed: Kide multi-day bookings produced egress windows of 24–107 hours. An end more than 24
  hours after the start is no longer trusted; the event keeps its start and uses the model's
  typical duration.
- Fixed: venue matching preferred a short generic alias (`Tampere`) and a shared street address
  over the venue named in the address. `Lush pikkujoulut Koskikeskuksessa` no longer appears at
  Ilves Bar & Night.
- Fixed: after-midnight starts in the panel and map tooltip now show `+1` (and a 24-hour
  event's end `+2`), matching the hour slider.
- Added validation for malformed times, date-as-time values, start/time consistency, an empty
  route cache, and events longer than 24 hours. The 06:00 boundary is no longer warned as a
  suspicious time.
- Verified: 595 events, 154 venues, 4,031 cached legs (19,763 km), 0 corridor fallbacks, 0
  missing route keys, 0 validator errors/warnings; 3 Playwright smoke tests pass.
- Model 2026.11.6: after-midnight starts are no longer scored as daytime events; schema 2.

### 0.13.4 — 2026-11-15
Publish every future event, not just the first page of a sorted feed.

- Fixed: the city calendar adapter cut its sorted list at 220 rows and the Kide adapter at 80.
  Because each run sorted the same source and kept the first rows, the missing tail could never be
  picked up by a later daily refresh. The caps are gone; all future single-day rows are evaluated.
  This adds 181 calendar events and publishes 576 events across 158 venues (232 community,
  115 culture, 51 stage, 71 gigs, 45 sports, 62 student).
- Fixed: after-midnight starts were drawn on the following day. The day strip runs 06:00–06:00,
  so a source date with a start before 06:00 now moves back one date before filtering and
  publishing (`night_date()`). This puts PISTOT Bileristeily at 00:00 on the 9 Dec night strip,
  not at 00:00 on 10 Dec.
- Added: the validator now refuses a deployment when any live source reports `FAILED`, when a
  published event's venue has no address, or when a flow has no matching event/venue. Partial
  feed failures leave the last good site live instead of silently deleting a whole category.
- Verified: 576 events, 158 venues, 2,714 used walking legs, 0 corridor-only flows, 0 missing
  route keys; `validate.py` exits 0 with the two known 05:12 music warnings. The route cache has
  3,829 legs (18,772 km); the new calendar venues' 434 missing legs were fetched before the
  final rebuild.
- No model or schema change: model 2026.11.5, schema 2.

### 0.13.3 — 2026-11-15
Student events completed from Kide's published product locations.

- Fixed: 17 future Kide products were dropped because the list endpoint carries only a free-text
  place and no coordinates. The public product detail publishes the organiser's street address and
  point; 15 of them now have a real venue. Student events go from 47 to 62.
- Added: Bommari (Korkeakoulunkatu 5), Vertex Oy (Vaajakatu 9), TTHP (Korkeakoulunkatu 3),
  Staabi ry (Kalevantie 4), Tampereen Opiskelijapuolikas (Ratinan rantatie 1) and the Kide
  location at Korkeakoulunkatu 7, each on its published address point; their walking legs are in
  the route cache.
- Still excluded, deliberately: the VETO apartment tour (starts in Niemenranta and moves between
  homes, so no single address) and Yrityspäivät (a PL 54 postal box). Neither is guessed.
- No model or schema change: model 2026.11.5, schema 2, 395 events.

### 0.13.2 — 2026-11-15
Venue addresses and points corrected across the registry.

- Fixed: 28 venues carried a district name, a neighbouring street number or a point several
  hundred metres to several kilometres away. Every corrected venue now has a published street
  address and an OpenStreetMap or official address point, and the map dot and its walking legs
  start at the same place. The generic `tampere_muu` fallback no longer claims to be in Keskusta.
- Notable corrections: Tampere-talo (770 m east of its hall), Klubi and Telakka (1.6-1.7 km from
  Tullikamarin aukio), TTT-Klubi (Hämeenpuisto 34 -> Hallituskatu 19), Hakametsän jäähalli
  (Ilmarinkatu 10 -> Keltinkatu 2), Nokia Arena (Tampere-talon aukio -> Kansikatu 3), Tavara-asema
  (Ratapihankatu 21 -> 33), Monttu (Hämeenkatu 17), Bricks (Hämeenkatu 18), G Livelab
  (Puutarhakatu 1) and Komediateatteri (Lapintie 1 -> 3a, 700 m north).
- Fixed: ten library venues and four sports venues sat on district centroids, including
  Koilliskeskuksen kirjasto and Koukkuniemen kirjasto (3.3 km off), Koivistonkylän kirjasto
  (2.1 km), Kauppi, Tesoma, Pyynikki, Hakametsä, Särkänniemi and Valkeakosken kesäteatteri. All now
  use their street address and address point.
- Fixed: F54's approximate flag was stale; its Satakunnankatu 18 address point is exact.
- Fixed: the panel's day list dropped each event's venue id, so the venue address never rendered
  even when the data had it. Rows now show `venue · street address` again.
- Changed: removed 765 stale cached legs for the corrected venues and refetched the event-used legs
  the current events actually use (about 13,600 km of cached walking geometry). No route now starts at an old
  venue point.
- Fixed: 14 venues corrected in earlier releases still had route-cache entries ending at
  their old points; 257 event-used legs are refreshed as well.
- No model or schema change: model 2026.11.5, schema 2, 380 events.

### 0.13.1 — 2026-11-15
Two UI fixes from the desktop and phone browser sweep.

- Fixed: the hour scrubber's last stop is 06:00 the next morning, but it read exactly like 06:00
  the same day. The time label now shows `06:00 +1`, the estimate card shows the next date, and an
  event end after midnight carries `+1` too.
- Fixed: the desktop legend repeated the category list in two rows. The compact single-row legend
  is now phone-only; desktop keeps the fuller labelled swatches.
- No model, schema or data change.

### 0.13.0 — 2026-11-15
Mobile-first release, with the documentation brought up to date.

- This release promotes the 0.12.4 mobile and performance work as the current baseline: phone
  detection, a 50dvh map, compact legend, capped canvas DPR, simplified route geometry, normal
  HTTP caching and in-place panel updates.
- Rewrote `README.md` around the site as it works now — day strip, hour scrubber, street heat,
  event dots and the "What's on" panel — instead of the old event-selector description.
- Updated `NOTICE.md`: it lists the four live feeds and no longer claims that sports, student,
  theatre or library rows are SAMPLE placeholders.
- Updated `AGENTS.md` with the version-bump rule and `TODO.md` with the release entry.
- No model, schema or data change: model 2026.11.5, schema 2, 380 events at release.

### 0.12.4 — 2026-11-15
Faster, lighter and properly laid out on a phone.

- Mobile: `map.js` detects a narrow or coarse-pointer viewport (`html.is-mobile`), caps the canvas
  at 1.75x DPR instead of 3x, samples fewer heat points and draws four district labels instead of
  six. The phone map is a 50dvh canvas clamped to 280-520px instead of `100dvh - 300px`; the legend drops
  the duplicate swatch list and sits above the attribution, so it covers about 60px of a 424px map
  instead of roughly a third of it.
- Performance: browser route geometry is simplified with Douglas-Peucker (~9 m) and rounded to five
  decimals in `build.py`. `web/geo/routes.json` goes from 3.25 MB / 153,932 points to 1.43 MB /
  61,894 points (gzip 699 KB -> 270 KB); the full geometry stays in `registry/routes.json`.
- Fixed: the page fetched every JSON file with `cache: "no-store"`, so a repeat visit re-downloaded
  the whole payload. It now uses normal HTTP caching (GitHub Pages sets `max-age=600`).
- Changed: the hour slider updates the event rows' on/soon classes in place (one rAF per frame)
  instead of rebuilding the list and reattaching listeners on every input event.
- Changed: Google Fonts requests only the weights the stylesheet uses (400/600/700 Inter, 400/600
  Plex Mono); `viewport-fit=cover` and safe-area padding handle notched phones.
- Total initial JSON on the local uncompressed preview: 5.0 MB -> 3.2 MB. Pages serves it gzipped.

### 0.12.3 — 2026-11-15
Event size and venue size now shape the heat, and districts ride their own transit.

- Added: `event_capacity()` in `scripts/build.py` derives an event-level crowd size from the source
  when it can: the city calendar's published `maxParticipants` (capped to the venue's own capacity)
  and Kide title keywords (`treenit`/practice -> a small group of up to 60 instead of the whole
  hall). Otherwise it keeps the venue capacity prior.
- Fixed: a student practice at a big arena (`TTO x PIRATE Kyykkätreenit` at Hakametsä) no longer
  inherits the arena's thousands of seats; big gigs, matches and parties keep their real size. The
  gravity catchment class uses the same event capacity, so the practice no longer pulls from the
  whole province either.
- Added: a venue-size class prior in `attendance_est()` (arena/hall 1.06-1.10x, small pub/bar 0.95x)
  so a big-venue evening reads larger than a small pub or bar even at the same fill. It uses the
  event's own capacity, so a practice booked in an arena stays small.
- Changed: far districts draw their own transit corridor to the venue instead of collapsing onto the
  venue's single hub. Each zone carries a `transit_mode` (tram/bus/rail) in `registry/zones.json`:
  Hervanta -> tram, Tesoma/Pirkkala/Kaukajärvi -> bus, Nokia/Lempäälä -> train; short district legs
  stay walk/bike.
- Added: 5 verifiable Kide venues (Bar Tullari, H5 Bar, Megazone, Rush, F54/Fame Club) plus a CLINT
  alias on TAMK, with real OSM address points; published student rows 38 -> 47.
- Added: the site shows a small `v0.12.3 · updated ...` badge in the top-left, fed by the build
  timestamp, so the running version and the last rebuild are visible.
- Model version 2026.11.5.

### 0.12.2 — 2026-11-15
Student parties and gigs sit on their real street addresses, and the site shows them.

- Added: 21 student and student-night venues the Kide feed names, each on its OpenStreetMap address
  point — Laulumaja (Takojankatu 1 C), Save File (Aleksis Kiven katu 24), Tampereen Ylioppilasteatteri
  (Itsenäisyydenkatu 12–14), Juhlatalo Tapiola (Karhunkatu 71), Tampereen Pursiseura
  (Kekkosenkatu 10), Pii-klubi (Yliopistonkatu 58 B), Kamula (Mustanlahdenkatu 18), TAMK pääkampus
  (Kuntokatu 3), YTHS-sauna (Kalevantie 3 C), Nightclub Mixei, Viihdekeskus ZBase, Viihdemaailma
  Ilona, Galaxie Center, Bricks, Kaijakka, Onda, Sherlock Holmes, Pub Kultainen Apina, Koskikeskus,
  Messukylän työväentalo and Hatanpään soutupaviljonki.
- Changed: published student parties 6 → 38 of the 67 future Kide products. A product is placed only
  when its place matches a venue in the registry; the rest are dropped and logged, never pinned to a
  guessed point (Ankkuri, Antura, Megazone and CLINT publish no street address at all).
- Fixed: 13 registry venues carried a district name ("Keskusta") where the address belongs, with
  points up to 3 km off. Terassi Pub Yläkerta is at Pispalan valtatie 39 — the upstairs of
  Vastavirta-Klubi, not the city centre — which alone corrects 10 published gigs. Others corrected:
  Astor (Aleksis Kiven katu 26), Puisto (Hämeenkatu 14 A), Rosendahl (Pyynikintie 13, the Scandic
  hotel), Ilves Bar & Night (Hatanpään valtatie 1), Myllärit (Åkerlundinkatu 4), Tiiliholvi
  (Kauppakatu 10), Huurre (Sammonkatu 46), Salhojankadun Pub (Salhojankatu 29), Katubaari Axu
  (Ilmarinkatu 47), Paapan Kapakka (Koskikatu 9), Kulttuurikeskus Maanalainen (Itsenäisyydenkatu 2),
  Tuomiokirkko (Tuomiokirkonkatu 3), Tammelan stadion (Kalevan puistotie 21), Hiedanranta /
  Lielahden kartano (Tehdaskartanonkatu 53), Ylisen kartano (Kuruntie 980, Ylöjärvi — 8 km north of
  the old guess) and Kangasalan kirkko (Ainontie 1).
- Added: the panel and the row list show the venue's street address beside its name, read from
  `web/geo/venues.json`, so a dot's address is visible without opening anything else. Calendar rows
  already label themselves by address.
- Fixed: Kide sells one event once per organiser — "Baby's First Game Jam" arrived four times, one
  per guild, each spelling the campus differently. Duplicate (date, start, title) listings are merged
  and place strings are whitespace-normalised.
- Verified: 371 events, 363 of them on a venue with a house number (the rest are parks, a racecourse
  and a summer theatre whose listing publishes no number); `validate.py` 0 errors; 126 venues.
- Note: the coordinates are OpenStreetMap address points, not venue-published points, and the
  capacity of a newly registered venue is a class prior — the same estimate as every other figure.

### 0.12.1 — 2026-11-15
The route cache is complete: no event falls back to a straight line.

- Fixed: `web/geo/venues.json` never carried a venue's `hubs`, so `scripts/routes.py` saw every
  calendar venue as hub-less and could not build its transit legs; registry venues with an empty
  `hubs` list (Kangasalan kirkko, Ylisen kartano, three libraries, Valkeakosken kesäteatteri) had no
  leg the seeder could fetch at all. 88 of 339 events sat on the straight-line fallback.
- Fixed: hub-less venues now use their nearest registered hub (`venue_catalogue()` in
  `scripts/routes.py`, the same rule in the build). Legs wanted went from 1,257 to 2,493.
- Fixed: a district centroid sitting on the venue produced a 0 km, two-point "route" — geometry in
  name only. Legs shorter than 50 m are now ignored and the hub leg is drawn instead, so Kangasalan
  kirkko gets the 14.0 km tram corridor from Hervanta and Ylisen kartano the 7.4 km bus leg from
  Tesoma.
- Changed: the workflow's second fetch pass runs `--max 1500`, so a backlog clears in one run
  instead of trickling in over days.
- Verified live: 339 events, 0 without street legs, 0 corridor-only flows, 0 legs under 50 m,
  3,150 legs over 7,050 km of OSM footways, 701 distinct routes shipped to the browser.
- Note: the model is unchanged — the same estimated flows, now drawn on real streets.

### 0.12.0 — 2026-11-15
Stage, culture, library and community events from the city's own calendar.

- Added: `scripts/feeds/city_events.py` reads Tampereen tapahtumakalenteri
  (`tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q=`; public JSON, no
  key, the whole calendar in one ~3 MB response) and publishes its stage, culture, library and
  community rows. Every location in that calendar carries a latitude/longitude **and** a street
  address, so the rows are placed on the published point — nothing is geocoded or guessed.
- Added: 217 calendar events land on the map — 21 stage, 74 culture, 122 community — taking the
  live site from 122 to 339 events over 77 days.
- Added: `place_venue()` turns a calendar location the registry does not know into a real venue
  (published coordinates, full address, nearest district, nearest transit hub); `web/geo/venues.json`
  now carries every venue's address. 137 calendar listings use such a venue, the other 80 resolve to
  a registry venue by name or address (Pääkirjasto Metso, Vapriikki, Tampere-talo, …).
- Added: `resolve_by_address` already handled "address in the row"; the calendar makes that the
  normal path rather than the exception.
- Changed: `source_status.culture` reports the calendar, and the all-feeds-failed guard counts four
  sources.
- Changed: `scripts/routes.py` also loads the generated venues, and the workflow fetches missing legs
  in two bounded passes (`--from-flow --max 300`, then `--max 400`). Calendar venues therefore gain
  real walking geometry as the cache fills: 59 of their 147 flows drew street legs on the first run,
  the rest still use the straight fallback corridors until the next runs catch up.
- Changed: a venue beyond its class catchment (Kangasala, Nokia, Hämeenkyrö, Lempäälä) now draws on
  its nearest districts instead of producing an event with no origin at all.
- Fixed: those far venues produced invalid flows ("no mode split", "neither legs nor corridors") that
  the validator rejected; 20 such rows are gone.
- Kept: multi-day and ongoing listings (an exhibition open for months) are not published as a daily
  crowd event, music-only calendar rows are skipped because `tampere-keikat` already supplies gigs,
  and rows duplicating another source (same day, same title) are dropped — 3 today.
- Note: a calendar venue's capacity is unknown unless the listing publishes `maxParticipants`, so its
  crowd is estimated at the small-venue floor and the figure is an estimate like every other one.

### 0.11.2 — 2026-11-15
A failed rebuild no longer blanks the map.

- Added: a second Sunday cron (`0 6 * * 0`) after the weekly `0 4 * * 0` rebuild, so a failed
  weekly run gets one automatic retry the same morning.
- Fixed: when every feed fails, or nothing survives the date filter, the build leaves
  `web/data.json` and `web/geo/*` untouched and exits non-zero, so the workflow stops before
  committing or deploying. Before, a total feed outage produced an empty event list and replaced
  the live data with a blank map.
- Note: one failed source still publishes the others; only an empty result stops the build.

### 0.11.1 — 2026-11-15
Every published event sits on a venue with a real address.

- Fixed: one gig had `Ilmainen` ("free") in the venue field and its street address folded into the
  title, so it was pinned to the generic `tampere_muu` fallback. `resolve_by_address()` now accepts a
  street name with a house number found in the row and places the event on that registry venue —
  a real address, not a guess.
- Fixed: `registry/venues.json` listed `ilmainen` as an alias of the generic fallback venue, which
  is how that row lost its address. Removed.
- Added: Finlaysonin kirkko, Puuvillatehtaankatu 2 (`61.5022, 23.7550`, OpenStreetMap), capacity 220
  as published by the Tampereen seurakunnat, so concert rows at that address have a venue.
- Note: all 122 published events — 71 gigs, 45 hockey fixtures, 6 student events — now resolve to one
  of 26 venues, each with an address and coordinates; the map draws a dot for every one of them.

### 0.11.0 — 2026-11-15
Student parties from Kide, on their real addresses.

- Added: `scripts/feeds/kide.py`, the first adapter in a `scripts/feeds/` package. It reads Kide's
  public product list for Tampere (`api.kide.app/api/products?city=Tampere`, no key) and returns the
  event name, the organiser, the place and a **real** start and end time — the student platform
  publishes both, so a sitsit or a gaala now has a real egress curve instead of the 300-minute
  default.
- Added: `kide_rows()` in `build.py` places each product on a venue from `registry/venues.json` by
  name or alias and publishes it as the `student` category. A product whose place is not a registry
  venue is **dropped and logged**, never placed on a guessed coordinate: 6 of today's 67 products
  land on a real address (Telakka, Klubi, Tampere-talo, Hakametsän jäähalli), 61 are left out with
  their place names printed in the build log.
- Changed: `source_status` gained a `student` key alongside `music`, `sports` and `seed`, so a broken
  Kide feed reports `FAILED` there instead of silently shrinking the day.
- Fixed: a malformed product (or a `minPrice` money object instead of a number) no longer loses the
  whole source — the adapter skips that one row.
- Kept: `seed` is still `OFF` and no `SAMPLE` row is published; `validate.py` still refuses one.
- Note: everything else on the page remains an estimate from the flow model.

### 0.10.0 — 2026-11-15
Only real events, and the day's programme beside the map.

- Removed: the ten `SAMPLE` placeholder rows are no longer published. The build reads
  `data/seed_events.json` only with `--with-samples`, `source_status.seed` reports `OFF`, and
  `validate.py` fails the deploy if a placeholder reaches the live data. The site now shows music
  and Liiga hockey only — nothing invented.
- Added: a right-hand panel listing the chosen day's events in start order with the venue and kind.
  The row for the hour you are looking at is marked "occurring now", events starting within two
  hours are marked soon, and each row carries the estimated attendance with "≈".
- Added: hover support on the map. Pointing at a dot names the event in the panel and enlarges the
  dot; pointing at a row rings the matching dot. Tapping still works on phones.
- Fixed: the legend markup contained a duplicated swatch block and a stray closing tag, and the
  swatch rules sat inside the phone media query, so the desktop legend was missing a row.
- Fixed: a tooltip could stay on screen over an empty patch of map, and the hover hit radius did
  not match the tooltip's.
- Note: `≈` figures remain estimates from the flow model, not measured attendance.

### 0.9.0 — 2026-11-15
Dots for what is on, and a phone-first layout.

- Added: one dot per event on the chosen day, coloured by kind — gigs red, sports blue,
  student parties amber — so the map says what is happening where without a listing.
- Added: tap or click a dot for the event name, start time and venue. Estimates stay estimates;
  the dots are the only place a title appears.
- Added: Liiga sports adapter (`fetch_liiga` in `scripts/build.py`) — Ilves and Tappara home
  fixtures from the public Liiga game list, pinned to Nokia Arena with the rink's own coordinates.
  Away games are excluded; the feed refreshes on every scheduled rebuild.
- Changed: phone layout stacks the day strip and hour control, enlarges touch targets, trims the
  legend and sizes the map to the viewport so nothing scrolls sideways.
- Note: student rows are still `SAMPLE` placeholders — no dependable public Tampere student feed
  was found (the TREY calendar is a JS app over a Strapi API that refused unauthenticated reads).

### 0.8.0 — 2026-11-15
Traffic both ways.

- Added: the estimate now counts departures as well as arrivals. Each event gets an estimated end
  (150 min for gigs, 300 for student nights, 120 for culture and community events), and the egress
  curve spreads the crowd over the 45 minutes after it.
- Changed: the heat and the count include people heading home, so a venue no longer goes dark the
  moment the event starts and lights up again when it ends.
- Changed: the legend reads "Estimated traffic on the streets" because the layer is no longer
  arrivals only.
- Note: the feed has no end times; they are approximations like every other number here.

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

- `model_version`: **2026.11.16** — Liiga-fitted hockey fill, other categories use priors;
  gravity β = 1.6, impedance from distance/speed approximation, class-based mode adjustment;
  event capacity from published participant counts and Kide practice keywords, a venue-size
  class prior, district transit corridors, and a real end minute when the source publishes one.
  A venue marked `capacity_unknown` publishes no attendance estimate instead of a class prior.
  A competition prior pools a shared top-zone catchment once for same-day events whose active
  windows overlap by at least 50% of their smaller catchment share. Unknown starts are averaged
  over 18:00, 19:00 and 20:00 instead of a single 19:00 peak. A venue/date/published-start
  collision cap shares one building capacity across distinct listings and flags the room split
  as unresolved.
- `events_schema`: **3** — row indices 0–6 frozen; 7–14 appended; calibration, competition,
  venue collisions, TBA start metadata and basis added.
- `flows_schema`: **2** — attendance/spread, interest, basis (including competition and venue
  collision), `start_known`, `start_options`/`start_window` for TBA flows, zones, modes,
  corridors, arrival, egress.
- `venues`: 1 — 74 registry venues, each with a street address and an OpenStreetMap address point,
  plus calendar venues generated from the city calendar's own published points (address kept,
  capacity unknown); 154 venues in the current build, approximate coordinates flagged per venue.
- `zones`: 1 — 40 zones: Tampere districts plus surrounding/Pirkanmaa bands and a long-distance band.
- Calibration dataset: **Liiga reported spectators** — 20 completed Ilves/Tappara home games
  (22 Sep–15 Nov 2026), hockey fill 0.425, leave-one-out median APE 19.4 %, MAPE 20.9 %, bias
  −7.6 %, 55 % within ±20 %. The fit replaces the prior only when its leave-one-out MAPE is
  lower than the prior's. City `maxParticipants` is a published cap, not attendance; it is
  coverage, not a backtest target.
- Upstream feeds: `tampere-keikat` feed snapshot read at build time; Liiga game list
  (`liiga.fi/api/v2/games`) filtered to Ilves/Tappara home games in Tampere; Kide public product
  list (`api.kide.app/api/products?city=Tampere`) for student events; Tampereen tapahtumakalenteri
  (`tapahtumat.tampere.fi/api/search/internal-content-fetch?lang=fi&country=FI&q=`) for stage,
  culture, library and community events.
- `sports` rows come from the Liiga adapter, `student` rows from the Kide adapter and `culture`
  (stage/culture/community) rows from the city calendar; `SAMPLE` placeholders are no longer
  published. Kide and calendar rows carry a real end minute when the source does.
- Adapted interface: `tampere-keikat` @ `4be498d` (MIT).

## Versioning rules

- **MAJOR** — the UI can no longer read the data (row indices changed, file removed).
- **MINOR** — new source, category, view or model capability.
- **PATCH** — fixes, copy, styling, data corrections.

Every build stamps `generated`, `schema_version` and `model_version` into `web/data.json`
and `web/geo/flows.json`, so a rendered map can be traced to the exact code, model
parameters and input snapshot that produced it.
