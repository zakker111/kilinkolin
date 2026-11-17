"""Small model regression tests. Run with the Playwright smoke suite via npm test."""
import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build  # noqa: E402


VENUE = {
    "id": "nokia_arena",
    "name": "Nokia Arena",
    "aliases": [],
    "lat": 61.4936,
    "lon": 23.7722,
    "area": "Keskusta",
    "capacity": {"sport": 13455, "gig": 15000},
    "hubs": ["tampere"],
}


def observation(day, title="Ilves – Tappara", spectators=5000):
    return {"date": day.isoformat(), "time": "19:00", "title": title, "spectators": spectators}


def observations(count=20, spectators=5000):
    start = dt.date(2026, 9, 1)
    return [observation(start + dt.timedelta(days=i), spectators=spectators) for i in range(count)]


class ModelTest(unittest.TestCase):
    def setUp(self):
        self.prior = build.FILL["hockey"]
        build.VENUES = [VENUE]
        self.addCleanup(self.restore)
        self.addCleanup(setattr, build, "VENUES", [])

    def restore(self):
        build.FILL["hockey"] = self.prior

    def prior_observations(self):
        """Make the prior exactly right, so no fit can improve on it."""
        out = []
        for obs in observations():
            ev = {
                "date": obs["date"], "time": obs["time"], "title": obs["title"],
                "venue": VENUE, "free": False, "hour": 19,
                "category": "sports", "sub": "hockey", "kind": "sport", "seed": False,
            }
            cap = build.event_capacity(ev, VENUE)
            interest = build.interest_score(ev, cap, "sports", "hockey", VENUE)
            actual = build.attendance_est(cap, "sports", "hockey", interest, ev,
                                           fill_override=self.prior)["mid"]
            out.append({**obs, "spectators": actual})
        return out

    def test_unavailable_calibration_keeps_prior(self):
        result = build.calibrate_liiga([], build.build_alias_index(build.VENUES))
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["sample"], 0)
        self.assertEqual(result["fitted_fill"], self.prior)
        self.assertNotIn("from", result)
        self.assertNotIn("mape", result)

    def test_insufficient_calibration_keeps_prior(self):
        result = build.calibrate_liiga(observations(7), build.build_alias_index(build.VENUES))
        self.assertEqual(result["status"], "INSUFFICIENT")
        self.assertEqual(result["sample"], 7)
        self.assertEqual(result["fitted_fill"], self.prior)
        self.assertNotIn("mape", result)

    def test_fit_wins_when_it_beats_prior_out_of_sample(self):
        result = build.calibrate_liiga(observations(), build.build_alias_index(build.VENUES))
        self.assertEqual(result["status"], "FITTED")
        self.assertEqual(result["sample"], 20)
        self.assertNotEqual(result["fitted_fill"], self.prior)
        self.assertLess(result["mape"], result["prior_mape"])
        self.assertIn("fitted_mape", result)
        self.assertEqual(build.FILL["hockey"], result["fitted_fill"])

    def test_prior_wins_when_fit_cannot_beat_prior_out_of_sample(self):
        result = build.calibrate_liiga(self.prior_observations(), build.build_alias_index(build.VENUES))
        self.assertEqual(result["status"], "PRIOR")
        self.assertEqual(result["sample"], 20)
        self.assertEqual(result["fitted_fill"], self.prior)
        self.assertNotIn("mape", result)
        self.assertNotIn("fitted_mape", result)

    def test_equal_concurrent_events_share_one_catchment(self):
        def flow(mid, start, end, zones):
            return {"start": start, "end": end,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": z, "share": s} for z, s in zones.items()]}

        a = flow(1000, 19 * 60, 21 * 60, {"keskusta": 0.6, "kaleva": 0.4})
        b = flow(1000, 19 * 60, 21 * 60, {"keskusta": 0.6, "kaleva": 0.4})
        factor_a, peers_a = build.competition_factor(a, [b])
        factor_b, peers_b = build.competition_factor(b, [a])
        self.assertAlmostEqual(factor_a, 0.5, places=3)
        self.assertAlmostEqual(factor_b, 0.5, places=3)
        self.assertEqual(peers_a, 1)
        self.assertEqual(peers_b, 1)

    def test_competition_ignores_disjoint_catchments(self):
        def flow(mid, zones):
            return {"start": 19 * 60, "end": 21 * 60,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": z, "share": s} for z, s in zones.items()]}

        a = flow(1000, {"keskusta": 1.0})
        b = flow(1000, {"hervanta": 1.0})
        factor, peers = build.competition_factor(a, [b])
        self.assertEqual(factor, 1.0)
        self.assertEqual(peers, 0)

    def test_competition_ignores_sequential_events(self):
        def flow(mid, start, end):
            return {"start": start, "end": end,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": "keskusta", "share": 1.0}]}

        a = flow(1000, 19 * 60, 21 * 60)
        b = flow(1000, 21 * 60, 23 * 60)
        factor, peers = build.competition_factor(a, [b])
        self.assertEqual(factor, 1.0)
        self.assertEqual(peers, 0)

    def test_competition_counts_a_shared_slice_once_at_the_largest_event(self):
        def flow(mid):
            return {"start": 19 * 60, "end": 21 * 60,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": "keskusta", "share": 1.0}]}

        big = flow(900)
        small = flow(100)
        big_factor, _ = build.competition_factor(big, [small])
        small_factor, _ = build.competition_factor(small, [big])
        self.assertAlmostEqual(big_factor, 0.9, places=3)
        self.assertAlmostEqual(small_factor, 0.9, places=3)
        self.assertAlmostEqual(900 * big_factor + 100 * small_factor, 900, places=3)
        self.assertGreater(small_factor, 0.5)

    def test_competition_keeps_unique_catchment_demand(self):
        def flow(mid, zones):
            return {"start": 19 * 60, "end": 21 * 60,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": z, "share": s} for z, s in zones.items()]}

        a = flow(1000, {"keskusta": 0.6, "kaleva": 0.4})
        b = flow(1000, {"keskusta": 0.6, "hervanta": 0.4})
        factor, peers = build.competition_factor(a, [b])
        self.assertAlmostEqual(factor, 0.7, places=3)
        self.assertEqual(peers, 1)

    def test_competition_ignores_weak_catchment_overlap(self):
        def flow(mid, zones):
            return {"start": 19 * 60, "end": 21 * 60,
                    "attendance": {"low": mid, "mid": mid, "high": mid},
                    "zones": [{"zone_id": z, "share": s} for z, s in zones.items()]}

        a = flow(1000, {"keskusta": 0.4, "kaleva": 0.6})
        b = flow(1000, {"keskusta": 0.4, "hervanta": 0.6})
        factor, peers = build.competition_factor(a, [b])
        self.assertEqual(factor, 1.0)
        self.assertEqual(peers, 0)

    def test_venue_collision_caps_combined_attendance(self):
        targets, factor = build.allocate_collision([400, 300, 100], 500)
        self.assertEqual(sum(targets), 500)
        self.assertEqual(targets, [250, 188, 62])
        self.assertAlmostEqual(factor, 0.625)

    def test_venue_collision_leaves_a_group_below_capacity(self):
        targets, factor = build.allocate_collision([100, 50], 200)
        self.assertEqual(targets, [100, 50])
        self.assertEqual(factor, 1.0)

    def test_published_cap_below_model_floor_is_not_raised(self):
        event = {"category": "community", "max_participants": 8}
        self.assertEqual(build.event_capacity(event, VENUE), 8)
        self.assertLess(build.event_capacity(event, VENUE), 20)

    def test_published_cap_above_venue_capacity_is_capped(self):
        event = {"category": "community", "max_participants": 300}
        capped_venue = {**VENUE, "capacity": {"sport": 0, "gig": 200}}
        self.assertEqual(build.event_capacity(event, capped_venue), 200)
        self.assertEqual(
            build.capacity_source(event, capped_venue),
            "city calendar maxParticipants, capped by the venue's capacity",
        )

    def test_unknown_capacity_is_not_floored_to_twenty(self):
        unknown = {**VENUE, "capacity": {"sport": 0, "gig": 0},
                   "capacity_unknown": True, "capacity_source": "capacity unpublished"}
        event = {"category": "student"}
        self.assertEqual(build.venue_capacity(unknown, "student"), 0)
        self.assertIsNone(build.event_capacity(event, unknown))
        self.assertIn("no estimate", build.capacity_source(event, unknown))
        self.assertEqual(build.event_capacity({"category": "community", "max_participants": 80}, unknown), 80)

    def test_exact_duplicate_is_merged_and_metadata_filled(self):
        def event(title, time, venue_id, url=""):
            return {"date": "2026-12-05", "time": time, "title": title,
                    "venue": {"id": venue_id}, "url": url, "free": False, "seed": False}

        kept, merged = build.dedupe_events([
            event("Us", "", "telakka"),
            event("Us", "", "telakka", "https://example.test/us"),
            event("Us", "19:00", "telakka"),
            event("Us", "13:00", "telakka"),
            event("Us", "", "other_venue"),
            event("Us", "19:00", "other_venue"),
        ])
        self.assertEqual(merged, 1)
        self.assertEqual(len(kept), 5)
        self.assertEqual(kept[0]["url"], "https://example.test/us")
        self.assertEqual(sum(e["time"] == "19:00" for e in kept), 2)

    def test_missing_and_published_start_are_not_merged(self):
        def event(time):
            return {"date": "2026-12-05", "time": time, "title": "Us",
                    "venue": {"id": "telakka"}, "free": False, "seed": False}

        kept, merged = build.dedupe_events([event(""), event("19:00")])
        self.assertEqual(merged, 0)
        self.assertEqual(len(kept), 2)

    def test_missing_start_uses_a_documented_spread_window(self):
        self.assertEqual(build.clock_minutes(""), 19 * 60)
        self.assertEqual(build.start_options(""), [18 * 60, 19 * 60, 20 * 60])
        self.assertEqual(build.start_options("19:00"), [19 * 60])
        self.assertEqual(build.night_date("2026-12-05", ""), "2026-12-05")


if __name__ == "__main__":
    unittest.main()
