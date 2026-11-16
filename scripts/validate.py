#!/usr/bin/env python3
"""Validation gate. Exits 1 on any structural problem, so CI never deploys bad data."""
import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
errors, warnings = [], []


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clock_minutes(s):
    """The page's 06:00–06:00 convention for a start time."""
    try:
        h, m = (int(x) for x in (s or "19:00").split(":"))
    except (TypeError, ValueError):
        return 19 * 60
    v = h * 60 + m
    return v + 24 * 60 if v < 6 * 60 else v


def main():
    for name in ("data.json", "geo/flows.json", "geo/venues.json", "geo/zones.json", "geo/coverage.json", "geo/routes.json"):
        p = os.path.join(WEB, name)
        if not os.path.exists(p):
            errors.append(f"missing {name}")
            continue
        try:
            load(p)
        except json.JSONDecodeError as exc:
            errors.append(f"{name} is not valid JSON: {exc}")
    if errors:
        report()
        return 1

    data = load(os.path.join(WEB, "data.json"))
    flows = load(os.path.join(WEB, "geo", "flows.json"))
    venues = load(os.path.join(WEB, "geo", "venues.json"))
    zones = load(os.path.join(WEB, "geo", "zones.json"))
    routes = load(os.path.join(WEB, "geo", "routes.json")).get("routes", {})

    venues_by_id = {v["id"]: v for v in venues["venues"]}
    venue_ids = set(venues_by_id)
    zone_ids = {z["id"] for z in zones["zones"]}
    events = data.get("events", [])
    if not events:
        errors.append("data.json has no events")

    # A failed source silently removes a whole category from the site. Refuse to deploy
    # partial data; the previous good deployment stays live instead.
    for source, state in (data.get("source_status") or {}).items():
        if source == "seed":
            continue
        if str(state).startswith("FAILED"):
            errors.append(f"source {source} failed: {state}")
        elif state == "EMPTY" and source in ("student", "culture"):
            # These feeds always have future events. An empty result would silently
            # remove a whole category; keep the last good deployment instead.
            errors.append(f"source {source} returned no events")
        elif state == "CACHED":
            warnings.append(f"source {source} used its cached copy")

    seen_ids = set()
    event_rows = {}
    cats = {}
    for i, row in enumerate(events):
        if len(row) < 15:
            errors.append(f"row {i} has {len(row)} columns, expected 15")
            continue
        date, time_s, title, venue, genre, free, url, eid = row[:8]
        venue_id, cat = row[14], row[9]
        cats[cat] = cats.get(cat, 0) + 1
        if eid in seen_ids:
            errors.append(f"duplicate event id {eid}")
        seen_ids.add(eid)
        event_rows[eid] = row
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            errors.append(f"row {i} has bad date {date!r}")
        if venue_id not in venue_ids:
            errors.append(f"row {i} venue_id {venue_id!r} not in venues.json")
        else:
            place = venues_by_id[venue_id]
            if not (place.get("address") or "").strip():
                errors.append(f"row {i} venue {venue_id!r} has no street address")
        if not title or not venue:
            errors.append(f"row {i} missing title or venue")
        if time_s:
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time_s):
                errors.append(f"row {i} has bad time {time_s!r}")
            elif len(date) == 10 and time_s == f"{date[8:10]}:{date[5:7]}":
                errors.append(f"row {i} time {time_s} is the event date, not a start time")
            else:
                hh = int(time_s[:2])
                if 2 <= hh < 6:
                    warnings.append(f"row {i} starts at {time_s} — possible timezone bug ({title[:40]!r})")

    f_events = flows.get("events", [])
    if len(f_events) != len(events):
        errors.append(f"flows has {len(f_events)} events but data has {len(events)}")
    if not routes and any(f.get("legs") for f in f_events):
        errors.append("routes.json has no cached routes but flows contain street legs")
    corridor_flows = [f.get("id") for f in f_events if f.get("corridors")]
    if corridor_flows:
        warnings.append(f"{len(corridor_flows)} flow(s) still use straight-line fallback corridors")
    seen_flow_ids = set()
    for f in f_events:
        fid = f.get("id")
        if fid in seen_flow_ids:
            errors.append(f"duplicate flow id {fid}")
        seen_flow_ids.add(fid)
        if fid not in seen_ids:
            errors.append(f"flow {fid} has no matching event row")
        if f.get("venue_id") not in venue_ids:
            errors.append(f"flow {fid} venue {f.get('venue_id')!r} not in venues.json")
        att = f.get("attendance", {})
        if not (att.get("low", 0) <= att.get("mid", 0) <= att.get("high", 0)):
            errors.append(f"event {f.get('id')} attendance band is inconsistent: {att}")
        a_sum = round(sum(s["share"] for s in f.get("arrival", [])), 2)
        if not 0.98 <= a_sum <= 1.02:
            errors.append(f"event {f.get('id')} arrival shares sum to {a_sum}")
        e_sum = round(sum(s["share"] for s in f.get("egress", [])), 2)
        if f.get("egress") and not 0.98 <= e_sum <= 1.02:
            errors.append(f"event {f.get('id')} egress shares sum to {e_sum}")
        event = event_rows.get(f.get("id"))
        if f.get("start") is None:
            errors.append(f"event {f.get('id')} has no start minute")
        elif event is not None:
            expected = clock_minutes(event[1]) if event[1] else 19 * 60
            if f["start"] != expected:
                errors.append(f"event {f.get('id')} start {f['start']} != published time {event[1]!r} ({expected})")
        if f.get("start") is not None and f.get("end") is not None:
            if f["end"] <= f["start"]:
                errors.append(f"event {f.get('id')} ends before it starts ({f.get('start')}–{f.get('end')})")
            elif f["end"] - f["start"] > 24 * 60:
                errors.append(f"event {f.get('id')} lasts more than 24 hours ({f.get('start')}–{f.get('end')})")
        z_sum = sum(z["share"] for z in f.get("zones", []))
        if z_sum > 1.001:
            errors.append(f"event {f.get('id')} zone shares exceed 1 ({z_sum:.3f})")
        for z in f.get("zones", []):
            if z["zone_id"] not in zone_ids:
                errors.append(f"event {f.get('id')} unknown zone {z['zone_id']!r}")
        for c in f.get("corridors", []):
            if len(c.get("geometry", [])) < 2:
                errors.append(f"event {f.get('id')} corridor to {c.get('zone_id')} has no geometry")
        if not f.get("modes"):
            errors.append(f"event {f.get('id')} has no mode split")
        for leg in f.get("legs", []):
            geo = (routes.get(leg["key"]) or {}).get("geometry") or []
            if not routes:
                break
            if len(geo) < 2:
                errors.append(f"event {f.get('id')} leg {leg['key']} has no cached street geometry")
            if leg.get("people", 0) < 0:
                errors.append(f"event {f.get('id')} leg {leg['key']} has negative people")
        if not f.get("legs") and not f.get("corridors"):
            errors.append(f"event {f.get('id')} has neither street legs nor fallback corridors")

    if not cats.get("gigs"):
        errors.append("no gigs in the feed — music ingest is probably broken")

    # the live site publishes feed data only; SAMPLE placeholders must never ship
    if (data.get("source_status") or {}).get("seed") != "OFF":
        errors.append("seed rows are enabled — build without --with-samples for the live site")
    sampled = [row[2] for row in events if "sample" in str(row[2]).lower()]
    if sampled:
        errors.append(f"{len(sampled)} published row(s) look like SAMPLE placeholders: {sampled[:3]}")

    coverage = data.get("coverage", {})
    total = coverage.get("total", 0)
    if total != len(events):
        warnings.append(f"coverage total {total} != {len(events)} events")

    print(f"events: {len(events)} | categories: {cats}")
    print(f"venues: {len(venue_ids)} | zones: {len(zone_ids)} | flows: {len(f_events)}")
    print(f"model {data.get('model_version')} | schema {data.get('schema_version')} | generated {data.get('generated')}")
    report()
    return 1 if errors else 0


def report():
    for w in warnings:
        print(f"WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    print(f"{len(errors)} errors, {len(warnings)} warnings", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
