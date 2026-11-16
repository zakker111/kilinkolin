"""Tests for the CI gates that protect published data and route coverage."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_data_churn  # noqa: E402
import check_route_coverage  # noqa: E402


def event(date="2026-11-17", category="gigs", event_id="e1"):
    # Only the date (0), id (7) and category (9) fields matter to the churn guard.
    return [date, "19:00", "Test event", "Venue", "", 0, "", event_id,
            category, category, ""]


def data(events, generated="2026-11-16 18:00 UTC"):
    return {"generated": generated, "events": events}


class ChurnGuardTest(unittest.TestCase):
    def test_material_drop_fails(self):
        result = check_data_churn.compare(
            data([event(event_id=f"e{i}") for i in range(20)]),
            data([event(event_id=f"e{i}") for i in range(14)]),
        )
        categories = {item["category"] for item in result["violations"]}
        self.assertIn("gigs", categories)
        self.assertIn("total", categories)
        self.assertEqual(result["total"]["before"], 20)
        self.assertEqual(result["total"]["after"], 14)

    def test_small_drop_is_allowed(self):
        result = check_data_churn.compare(
            data([event(event_id=f"e{i}") for i in range(20)]),
            data([event(event_id=f"e{i}") for i in range(19)]),
        )
        self.assertEqual(result["violations"], [])

    def test_expired_previous_events_are_not_counted(self):
        result = check_data_churn.compare(
            data([event(date="2026-11-15", event_id=f"old{i}") for i in range(20)]),
            data([event(date="2026-11-17", event_id=f"new{i}") for i in range(2)]),
        )
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["total"]["before"], 0)
        self.assertEqual(result["total"]["after"], 2)

    def test_a_source_drop_is_reported_for_its_mapped_feed(self):
        result = check_data_churn.compare(
            data([event(category="sports", event_id=f"s{i}") for i in range(10)]),
            data([event(category="sports", event_id=f"s{i}") for i in range(5)]),
        )
        self.assertEqual(result["violations"][0]["source"], "sports")


class RouteCoverageTest(unittest.TestCase):
    def flows(self, legs=None, corridors=None):
        return {
            "events": [{
                "id": "e1",
                "legs": legs or [],
                "corridors": corridors or [],
            }]
        }

    def test_covered_flow_passes(self):
        routes = {"v|zone:a": {"geometry": [[61.5, 23.7], [61.6, 23.8]]}}
        result = check_route_coverage.analyze(
            self.flows([{"key": "v|zone:a"}]), routes
        )
        self.assertEqual(result["with_legs"], 1)
        self.assertEqual(result["fallback_ids"], [])
        self.assertEqual(result["missing_keys"], [])

    def test_corridor_only_flow_is_counted(self):
        result = check_route_coverage.analyze(
            self.flows(corridors=[{"zone_id": "a"}]), {}
        )
        self.assertEqual(result["fallback_ids"], ["e1"])
        self.assertEqual(result["with_legs"], 0)

    def test_missing_route_key_is_reported(self):
        result = check_route_coverage.analyze(
            self.flows([{"key": "missing"}]), {}
        )
        self.assertEqual(result["missing_keys"], ["missing"])


if __name__ == "__main__":
    unittest.main()
