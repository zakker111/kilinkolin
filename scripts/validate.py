#!/usr/bin/env python3
"""Validation gate. Exits 1 on any structural problem, so CI never deploys bad data."""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
errors, warnings = [], []


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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

    venue_ids = {v["id"] for v in venues["venues"]}
    zone_ids = {z["id"] for z in zones["zones"]}
    events = data.get("events", [])
    if not events:
        errors.append("data.json has no events")

    seen_ids = set()
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
        try:
            dt.date.fromisoformat(date)
        except ValueError:
            errors.append(f"row {i} has bad date {date!r}")
        if venue_id not in venue_ids:
            errors.append(f"row {i} venue_id {venue_id!r} not in venues.json")
        if not title or not venue:
            errors.append(f"row {i} missing title or venue")
        if time_s and ":" in time_s:
            hh = int(time_s.split(":")[0])
            if 2 <= hh <= 6:
                warnings.append(f"row {i} starts at {time_s} — possible timezone bug ({title[:40]!r})")

    f_events = flows.get("events", [])
    if len(f_events) != len(events):
        errors.append(f"flows has {len(f_events)} events but data has {len(events)}")
    for f in f_events:
        att = f.get("attendance", {})
        if not (att.get("low", 0) <= att.get("mid", 0) <= att.get("high", 0)):
            errors.append(f"event {f.get('id')} attendance band is inconsistent: {att}")
        a_sum = round(sum(s["share"] for s in f.get("arrival", [])), 2)
        if not 0.98 <= a_sum <= 1.02:
            errors.append(f"event {f.get('id')} arrival shares sum to {a_sum}")
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
