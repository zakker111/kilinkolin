#!/usr/bin/env python3
"""Validation gate. Exits 1 on any structural problem, so CI never deploys bad data."""
import datetime as dt
import json
import os
import re
import sys
from collections import defaultdict

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


def norm_title(title):
    """Same key as build.norm_title, including Finnish letters."""
    return " ".join("".join(c for c in (title or "").lower() if c.isalnum() or c.isspace()).split())


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
    calibration = data.get("calibration") or {}
    flows = load(os.path.join(WEB, "geo", "flows.json"))
    day_dir = os.path.join(WEB, "geo", "days")
    day_files = {}
    for day in sorted({row[0] for row in data.get("events", []) if len(row) >= 1}):
        path = os.path.join(day_dir, f"{day}.json")
        if not os.path.exists(path):
            errors.append(f"missing per-day flow bundle geo/days/{day}.json")
            continue
        try:
            doc = load(path)
        except json.JSONDecodeError as exc:
            errors.append(f"geo/days/{day}.json is not valid JSON: {exc}")
            continue
        if doc.get("date") != day:
            errors.append(f"geo/days/{day}.json has date {doc.get('date')!r}")
        if not isinstance(doc.get("events"), list):
            errors.append(f"geo/days/{day}.json has no event list")
        else:
            day_files[day] = doc
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

    liiga = calibration.get("liiga") or {}
    if not calibration:
        warnings.append("data.json has no calibration block")
    elif not liiga:
        warnings.append("data.json.calibration has no liiga block")
    else:
        status = liiga.get("status")
        if status not in ("FITTED", "PRIOR", "INSUFFICIENT", "UNAVAILABLE"):
            errors.append(f"unknown Liiga calibration status {status!r}")
        sample = liiga.get("sample")
        if not isinstance(sample, int) or sample < 0:
            errors.append(f"Liiga calibration sample is invalid: {sample!r}")
        if status == "FITTED":
            if not isinstance(sample, int) or sample < 8:
                errors.append(f"Liiga calibration is FITTED on only {sample!r} games")
            try:
                fitted_fill = float(liiga.get("fitted_fill"))
            except (TypeError, ValueError):
                errors.append(f"Liiga fitted fill is invalid: {liiga.get('fitted_fill')!r}")
            else:
                if not 0 < fitted_fill <= 1:
                    errors.append(f"Liiga fitted fill is out of range: {fitted_fill!r}")
        for key in ("mape", "median_ape", "bias"):
            value = liiga.get(key)
            if value is None:
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                errors.append(f"Liiga calibration {key} is invalid: {value!r}")
                continue
            if not -2 <= value <= 2:
                errors.append(f"Liiga calibration {key} is implausible: {value!r}")
            if key == "mape" and value < 0:
                errors.append(f"Liiga calibration mape is negative: {value!r}")
    city_capacity = calibration.get("city_capacity") or {}
    competition = calibration.get("competition") or {}
    tba_start = calibration.get("tba_start") or {}
    venue_collisions = calibration.get("venue_collisions") or {}

    seen_ids = set()
    seen_listings = set()
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
        listing = (date, venue_id, time_s or "", norm_title(title))
        if listing in seen_listings:
            errors.append(f"duplicate event listing: {title!r} at {venue_id!r} on {date} {time_s or 'TBA'}")
        seen_listings.add(listing)
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

    if flows.get("schema_version") != 2:
        warnings.append(f"flows schema is {flows.get('schema_version')!r}, expected 2")
    f_events = flows.get("events", [])
    if len(f_events) != len(events):
        errors.append(f"flows has {len(f_events)} events but data has {len(events)}")
    if not routes and any(f.get("legs") for f in f_events):
        errors.append("routes.json has no cached routes but flows contain street legs")
    corridor_flows = [f.get("id") for f in f_events if f.get("corridors")]
    if corridor_flows:
        warnings.append(f"{len(corridor_flows)} flow(s) still use straight-line fallback corridors")
    seen_flow_ids = set()
    published_caps = 0
    discounted_flows = 0
    unknown_start_flows = 0
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
        basis = f.get("basis") or {}
        capacity_unknown = bool(basis.get("capacity_unknown"))
        if capacity_unknown:
            if att.get("mid") is not None or att.get("high") is not None:
                errors.append(f"event {f.get('id')} has an attendance number despite unknown capacity: {att}")
            if att.get("low") is not None and (not isinstance(att["low"], int) or att["low"] < 0):
                errors.append(f"event {f.get('id')} unknown-capacity lower bound is invalid: {att.get('low')!r}")
            if att.get("spread") is not None:
                errors.append(f"event {f.get('id')} unknown-capacity spread should be null: {att.get('spread')!r}")
            if att.get("unknown") is not True:
                errors.append(f"event {f.get('id')} unknown-capacity flow must be marked unknown")
        else:
            if not (att.get("low", 0) <= att.get("mid", 0) <= att.get("high", 0)):
                errors.append(f"event {f.get('id')} attendance band is inconsistent: {att}")
            if att.get("spread") is not None and not 0 <= float(att["spread"]) <= 1:
                errors.append(f"event {f.get('id')} attendance spread is out of range: {att['spread']!r}")
        if not basis:
            warnings.append(f"event {f.get('id')} has no estimate basis")
        else:
            if not 0 <= float(basis.get("fill", -1)) <= 1:
                errors.append(f"event {f.get('id')} fill is out of range: {basis.get('fill')!r}")
            if capacity_unknown:
                if basis.get("capacity") is not None:
                    errors.append(f"event {f.get('id')} unknown capacity must not carry a number: {basis.get('capacity')!r}")
                if not (basis.get("capacity_source") or "").strip():
                    errors.append(f"event {f.get('id')} unknown capacity has no source note")
            elif int(basis.get("capacity", 0)) <= 0:
                errors.append(f"event {f.get('id')} basis capacity is not positive")
            mp = basis.get("published_max_participants")
            if mp is not None:
                published_caps += 1
                if capacity_unknown:
                    errors.append(f"event {f.get('id')} has a published maxParticipants but an unknown venue capacity")
                elif not isinstance(mp, int) or mp <= 0:
                    errors.append(f"event {f.get('id')} published maxParticipants is invalid: {mp!r}")
                else:
                    if int(basis.get("capacity", 0)) > mp:
                        errors.append(f"event {f.get('id')} capacity {basis.get('capacity')} exceeds maxParticipants {mp}")
                    if att.get("mid") is not None and int(att["mid"]) > mp:
                        errors.append(f"event {f.get('id')} estimate {att.get('mid')} exceeds maxParticipants {mp}")
            comp = basis.get("competition") or {}
            if comp:
                try:
                    factor = float(comp.get("factor"))
                except (TypeError, ValueError):
                    errors.append(f"event {f.get('id')} competition factor is invalid: {comp.get('factor')!r}")
                else:
                    if not 0 < factor <= 1:
                        errors.append(f"event {f.get('id')} competition factor is out of range: {factor!r}")
                    if factor < 0.999:
                        discounted_flows += 1
                peers = comp.get("peers")
                if not isinstance(peers, int) or peers < 0:
                    errors.append(f"event {f.get('id')} competition peers is invalid: {peers!r}")
            vc = basis.get("venue_collision") or {}
            if vc:
                if not isinstance(vc.get("group_size"), int) or vc["group_size"] < 2:
                    errors.append(f"event {f.get('id')} venue_collision group_size is invalid: {vc.get('group_size')!r}")
                if not isinstance(vc.get("venue_capacity"), int) or vc["venue_capacity"] <= 0:
                    errors.append(f"event {f.get('id')} venue_collision capacity is invalid: {vc.get('venue_capacity')!r}")
                try:
                    c_factor = float(vc.get("factor"))
                except (TypeError, ValueError):
                    errors.append(f"event {f.get('id')} venue_collision factor is invalid: {vc.get('factor')!r}")
                else:
                    if not 0 < c_factor <= 1:
                        errors.append(f"event {f.get('id')} venue_collision factor is out of range: {c_factor!r}")
                if vc.get("room_split") != "UNRESOLVED":
                    errors.append(f"event {f.get('id')} venue_collision room_split is invalid: {vc.get('room_split')!r}")
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
        start_options = f.get("start_options")
        if start_options is None:
            if event is not None and not event[1]:
                errors.append(f"event {f.get('id')} has no published start and no spread window")
        else:
            if not isinstance(start_options, list) or len(start_options) < 2:
                errors.append(f"event {f.get('id')} start_options is invalid: {start_options!r}")
            else:
                if start_options != sorted(start_options):
                    errors.append(f"event {f.get('id')} start_options is not sorted: {start_options!r}")
                if any(not isinstance(v, int) for v in start_options):
                    errors.append(f"event {f.get('id')} start_options has a non-integer: {start_options!r}")
                if event is not None and event[1]:
                    errors.append(f"event {f.get('id')} has start_options despite a published time")
                if f.get("start") not in start_options:
                    errors.append(f"event {f.get('id')} start is not in start_options: {f.get('start')!r}")
                if f.get("start_window") != tba_start.get("window"):
                    errors.append(f"event {f.get('id')} start_window does not match calibration")
                lo, hi = (tba_start.get("window_minutes") or [None, None])[:2]
                if not isinstance(lo, int) or not isinstance(hi, int) or lo >= hi:
                    errors.append("tba_start.window_minutes is invalid")
                elif any(not lo <= v <= hi for v in start_options):
                    errors.append(f"event {f.get('id')} start_options is outside the documented window")
                unknown_start_flows += 1
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

    if city_capacity and city_capacity.get("events_with_published_capacity") != published_caps:
        errors.append(
            f"city capacity coverage says {city_capacity.get('events_with_published_capacity')!r} "
            f"events but flows publish {published_caps}"
        )
    capacity_unknown = calibration.get("capacity_unknown") or {}
    if capacity_unknown:
        unknown_flows = sum(1 for f in f_events if (f.get("basis") or {}).get("capacity_unknown"))
        if capacity_unknown.get("events") != unknown_flows:
            errors.append(
                f"capacity coverage says {capacity_unknown.get('events')!r} "
                f"events but {unknown_flows} flows have unknown capacity"
            )
    if competition and competition.get("events_with_competition") != discounted_flows:
        errors.append(
            f"competition coverage says {competition.get('events_with_competition')!r} "
            f"events but {discounted_flows} flows are discounted"
        )

    collision_groups = defaultdict(list)
    for f in f_events:
        if (f.get("basis") or {}).get("capacity_unknown"):
            continue
        if not f.get("start_known"):
            continue
        event = event_rows.get(f.get("id"))
        if event is None:
            continue
        collision_groups[(f.get("venue_id"), event[0], f.get("start"))].append(f)
    collision_groups = {key: group for key, group in collision_groups.items() if len(group) > 1}
    collision_ids = {f.get("id") for group in collision_groups.values() for f in group}
    capped_groups = 0
    unresolved_splits = 0
    for key, group in collision_groups.items():
        capacities = set()
        combined = 0
        first = None
        for f in group:
            vc = (f.get("basis") or {}).get("venue_collision") or {}
            if not vc:
                errors.append(f"event {f.get('id')} is in a same-venue collision without metadata")
                continue
            if vc.get("group_size") != len(group):
                errors.append(f"event {f.get('id')} venue_collision group_size {vc.get('group_size')!r} != {len(group)}")
            capacities.add(vc.get("venue_capacity"))
            combined += int(f.get("attendance", {}).get("mid", 0))
            first = first or vc
        if first is None:
            continue
        if len(capacities) != 1:
            errors.append(f"same-venue collision {key} has inconsistent capacity {capacities}")
            continue
        capacity = next(iter(capacities))
        if not isinstance(capacity, int) or capacity <= 0:
            errors.append(f"same-venue collision {key} has invalid capacity {capacity!r}")
            continue
        if combined > capacity:
            errors.append(f"same-venue collision {key} publishes {combined} people above capacity {capacity}")
        if first.get("combined_mid_after") != combined:
            errors.append(f"same-venue collision {key} combined_mid_after {first.get('combined_mid_after')!r} != {combined}")
        if int(first.get("combined_mid_before", 0)) > capacity:
            capped_groups += 1
        if first.get("room_split") == "UNRESOLVED":
            unresolved_splits += 1
    for f in f_events:
        if ((f.get("basis") or {}).get("venue_collision") and f.get("id") not in collision_ids):
            errors.append(f"event {f.get('id')} has venue_collision metadata but no same-venue peer")
    if venue_collisions:
        expected_events = sum(len(group) for group in collision_groups.values())
        checks = {
            "groups": len(collision_groups),
            "events": expected_events,
            "capped_groups": capped_groups,
            "unresolved_room_splits": unresolved_splits,
        }
        for name, expected in checks.items():
            if venue_collisions.get(name) != expected:
                errors.append(
                    f"venue collision coverage says {name}={venue_collisions.get(name)!r} but {expected} computed"
                )
    if tba_start and tba_start.get("events_with_unknown_start") != unknown_start_flows:
        errors.append(
            f"TBA coverage says {tba_start.get('events_with_unknown_start')!r} "
            f"events but {unknown_start_flows} flows carry a spread window"
        )

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
