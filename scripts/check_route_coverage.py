#!/usr/bin/env python3
"""Fail when street-route coverage regresses or a route cache key is missing.

A green route-fetch step is not enough: the step is allowed to fail so the build
can still produce a useful diagnostic, and a router outage could otherwise leave
new events on straight-line corridors.  This gate is run after the rebuild.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def analyze(flows: dict, routes: dict) -> dict:
    events = flows.get("events")
    if not isinstance(events, list):
        raise ValueError("flows have no events list")
    if not isinstance(routes, dict):
        raise ValueError("routes are not a JSON object")
    # routes.json wraps the key -> route mapping under "routes".
    routes = routes.get("routes", routes)
    if not isinstance(routes, dict):
        raise ValueError("routes mapping is not a JSON object")

    with_legs = 0
    with_corridors = 0
    fallback_ids = []
    missing_keys = []
    empty_geometry = []
    total_legs = 0
    leg_keys = set()

    for flow in events:
        flow_id = flow.get("id", "?")
        legs = flow.get("legs") or []
        corridors = flow.get("corridors") or []
        if legs:
            with_legs += 1
        if corridors:
            with_corridors += 1
        if corridors and not legs:
            fallback_ids.append(flow_id)
        for leg in legs:
            total_legs += 1
            key = leg.get("key")
            if not key:
                missing_keys.append(f"{flow_id}:leg-without-key")
                continue
            leg_keys.add(key)
            route = routes.get(key)
            if route is None:
                missing_keys.append(key)
            elif not route.get("geometry"):
                empty_geometry.append(key)

    total = len(events)
    return {
        "total_flows": total,
        "with_legs": with_legs,
        "with_corridors": with_corridors,
        "fallback_ids": fallback_ids,
        "missing_keys": missing_keys,
        "empty_geometry": empty_geometry,
        "total_legs": total_legs,
        "unique_leg_keys": len(leg_keys),
        "coverage": (with_legs / total) if total else 0.0,
    }


def format_report(result: dict) -> str:
    lines = [
        f"Route coverage: {result['with_legs']}/{result['total_flows']} flows have street legs "
        f"({result['coverage'] * 100:.2f}%); {result['total_legs']} legs, "
        f"{result['unique_leg_keys']} unique keys"
    ]
    if result["fallback_ids"]:
        shown = ", ".join(str(item) for item in result["fallback_ids"][:20])
        suffix = "..." if len(result["fallback_ids"]) > 20 else ""
        lines.append(f"  corridor-only flows: {shown}{suffix}")
    if result["missing_keys"]:
        lines.append(f"  missing route keys: {len(result['missing_keys'])}")
    if result["empty_geometry"]:
        lines.append(f"  cached routes with empty geometry: {len(result['empty_geometry'])}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flows", default="web/geo/flows.json")
    parser.add_argument("--routes", default="web/geo/routes.json")
    parser.add_argument(
        "--previous",
        help="flows.json from before the build, to detect a coverage regression",
    )
    parser.add_argument(
        "--max-fallback",
        type=int,
        default=1,
        help="maximum allowed corridor-only flows when no previous checkpoint exists (default: 1)",
    )
    parser.add_argument(
        "--min-covered",
        type=float,
        default=0.995,
        help="minimum covered-flow ratio (default: 0.995)",
    )
    args = parser.parse_args(argv)

    try:
        current = analyze(load(args.flows), load(args.routes))
        previous = None
        if args.previous and Path(args.previous).exists():
            previous = analyze(load(args.previous), load(args.routes))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Route coverage gate: cannot inspect routes: {exc}", file=sys.stderr)
        return 2

    print(format_report(current))
    allowed_fallback = max(0, args.max_fallback)
    if previous is not None:
        # A checkpoint is a ceiling, not a floor: a build with zero fallback
        # flows must not be allowed to introduce a new one.
        previous_fallback = len(previous["fallback_ids"])
        allowed_fallback = previous_fallback
        print(f"  previous checkpoint: {previous_fallback} corridor-only flow(s)")

    failures = []
    if current["total_flows"] == 0:
        failures.append("no flows were built")
    if len(current["fallback_ids"]) > allowed_fallback:
        failures.append(
            f"{len(current['fallback_ids'])} corridor-only flows exceed the allowed {allowed_fallback}"
        )
    if current["coverage"] < args.min_covered:
        failures.append(
            f"coverage {current['coverage'] * 100:.2f}% is below {args.min_covered * 100:.2f}%"
        )
    if current["missing_keys"]:
        failures.append(f"{len(current['missing_keys'])} flow leg(s) have no cached route key")
    if current["empty_geometry"]:
        failures.append(f"{len(current['empty_geometry'])} cached route(s) have no geometry")

    if failures:
        print("Route coverage gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("Route coverage gate: OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
