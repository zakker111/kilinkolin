#!/usr/bin/env python3
"""Guard against a feed silently dropping a material share of future events.

The build refreshes live feeds, so a partial adapter result can look healthy while
publishing fewer events than the previous build.  Compare the checked-in data
from before the build with the newly built data and fail when one category drops
by more than the configured percentage and event count.

Expired events are excluded: both sides are filtered to the current build's
generated date so a normal week of events passing does not look like a feed loss.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

CATEGORY_SOURCE = {
    "gigs": "music",
    "sports": "sports",
    "student": "student",
    "culture": "culture",
    "community": "culture",
    "stage": "culture",
}


def load(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def _events(data: dict) -> list:
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("data has no events list")
    return events


def _date(row) -> str:
    if isinstance(row, list) and row and isinstance(row[0], str):
        return row[0]
    return ""


def _category(row) -> str:
    if isinstance(row, list) and len(row) > 9 and row[9]:
        return str(row[9])
    return "unknown"


def counts(events: list, since: str) -> Counter:
    """Count events on or after ``since`` by their published category."""
    result = Counter()
    for row in events:
        if since and _date(row) < since:
            continue
        result[_category(row)] += 1
    return result


def compare(
    previous: dict,
    current: dict,
    max_drop_ratio: float = 0.10,
    min_drop: int = 3,
) -> dict:
    """Return a per-category comparison and any threshold violations."""
    generated = str(current.get("generated") or "")
    since = generated[:10]
    if not since:
        raise ValueError("current data has no generated date")

    prev_counts = counts(_events(previous), since)
    cur_counts = counts(_events(current), since)
    categories = sorted(set(prev_counts) | set(cur_counts))

    changes = []
    violations = []
    for category in categories:
        before = prev_counts[category]
        after = cur_counts[category]
        drop = before - after
        limit = max(min_drop, math.ceil(before * max_drop_ratio))
        change = {
            "category": category,
            "source": CATEGORY_SOURCE.get(category, category),
            "before": before,
            "after": after,
            "drop": drop,
            "limit": limit,
        }
        changes.append(change)
        if before and drop >= limit:
            violations.append(change)

    total_before = sum(prev_counts.values())
    total_after = sum(cur_counts.values())
    total_limit = max(min_drop, math.ceil(total_before * max_drop_ratio))
    total = {
        "category": "total",
        "source": "all sources",
        "before": total_before,
        "after": total_after,
        "drop": total_before - total_after,
        "limit": total_limit,
    }
    if total_before and total["drop"] >= total_limit:
        violations.append(total)

    return {
        "generated": generated,
        "since": since,
        "max_drop_ratio": max_drop_ratio,
        "min_drop": min_drop,
        "changes": changes,
        "total": total,
        "violations": violations,
    }


def _pct(value: int, total: int) -> str:
    return f"{(value / total * 100):.1f}%" if total else "0.0%"


def format_report(result: dict) -> str:
    lines = [
        f"Data churn guard: {result['total']['before']} -> {result['total']['after']} future events "
        f"(since {result['since']})"
    ]
    for change in result["changes"]:
        before, after = change["before"], change["after"]
        lines.append(
            f"  {change['category']:<12} {before:>4} -> {after:>4}  "
            f"drop {change['drop']:>4} ({_pct(change['drop'], before)})"
        )
    if result["violations"]:
        lines.append("FAIL: material event loss detected:")
        for item in result["violations"]:
            lines.append(
                f"  {item['category']}: {item['before']} -> {item['after']} "
                f"(drop {item['drop']}, limit {item['limit']}); source={item['source']}"
            )
    else:
        lines.append("OK: no category exceeded its churn threshold.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", help="data.json from before the build")
    parser.add_argument("--current", default="web/data.json", help="newly built data.json")
    parser.add_argument(
        "--max-drop-pct",
        type=float,
        default=10.0,
        help="maximum allowed drop per category, in percent (default: 10)",
    )
    parser.add_argument(
        "--min-drop",
        type=int,
        default=3,
        help="minimum event loss before a category can fail (default: 3)",
    )
    parser.add_argument(
        "--allow-drop",
        action="store_true",
        help="report a violation without failing (manual override only)",
    )
    args = parser.parse_args(argv)

    if not args.previous or not Path(args.previous).exists():
        print("Data churn guard: no previous data checkpoint; skipping (first build).")
        return 0

    try:
        result = compare(
            load(args.previous),
            load(args.current),
            max_drop_ratio=max(0.0, args.max_drop_pct / 100.0),
            min_drop=max(0, args.min_drop),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Data churn guard: cannot compare data: {exc}", file=sys.stderr)
        return 2

    print(format_report(result))
    if result["violations"] and not args.allow_drop:
        print(
            "Data churn guard failed. If the drop is intentional, rerun the workflow "
            "with the allow_data_drop input; otherwise inspect the affected feed.",
            file=sys.stderr,
        )
        return 1
    if result["violations"]:
        print("Data churn guard: override enabled; continuing after a reported drop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
