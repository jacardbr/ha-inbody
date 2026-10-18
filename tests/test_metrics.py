"""Tests for the extra-metric discovery helpers (standard library only)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

_path = Path(__file__).resolve().parents[1] / "custom_components" / "ha_inbody" / "metrics.py"
_spec = importlib.util.spec_from_file_location("ha_inbody_metrics", _path)
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


def by_slug(bca, mfa):
    return {x.slug: x for x in m.extra_metrics(bca, mfa)}


class DiscoveryTests(unittest.TestCase):
    def test_handled_fields_are_left_to_the_dedicated_sensors(self):
        found = by_slug({"WT": "70", "BFM": "15", "TBW": "40"}, {"BMI": "22", "PBF": "21", "SMM": "30"})
        self.assertEqual(found, {})

    def test_known_fields_get_names_and_units(self):
        found = by_slug({"ICW": "25.1", "BMR": "1600", "VFL": "5"}, {"WHR": "0.85"})
        self.assertEqual(found["bca_icw"].name, "Intracellular water")
        self.assertEqual(found["bca_icw"].unit, "kg")
        self.assertEqual((found["bca_bmr"].name, found["bca_bmr"].unit), ("Basal metabolic rate", "kcal"))
        self.assertIsNone(found["bca_vfl"].unit)
        self.assertEqual(found["mfa_whr"].name, "Waist-hip ratio")

    def test_unknown_fields_keep_their_raw_key(self):
        found = by_slug({"XYZ": 3}, {})
        self.assertEqual(found["bca_xyz"].name, "BCA XYZ")
        self.assertIsNone(found["bca_xyz"].unit)

    def test_numeric_strings_ok_junk_ignored(self):
        found = by_slug(
            {"A": "1.5", "B": "", "C": None, "D": True, "E": "abc", "F": float("nan"),
             "G": [1, 2], "H": float("inf")},
            {},
        )
        self.assertEqual(sorted(found), ["bca_a"])

    def test_identifiers_and_timestamps_are_skipped(self):
        found = by_slug({"DATETIMES": "20260101", "UID": "9", "SEQ": 4, "TEST_ID": 1, "OK": 2}, {})
        self.assertEqual(sorted(found), ["bca_ok"])

    def test_nested_blocks_are_flattened_with_a_depth_limit(self):
        bca = {"SEG": {"RA": "2.1", "LL": {"LEAN": "9.5", "DEEP": {"TOO": "1"}}}}
        found = by_slug(bca, {})
        self.assertEqual(sorted(found), ["bca_seg_ll_lean", "bca_seg_ra"])
        self.assertEqual(found["bca_seg_ra"].name, "BCA SEG.RA")

    def test_handled_key_name_is_only_skipped_at_top_level(self):
        found = by_slug({"SEG": {"WT": "5"}}, {})
        self.assertIn("bca_seg_wt", found)

    def test_slugs_are_safe_and_unique_per_block(self):
        found = by_slug({"ECW/TBW": "0.38"}, {"ECW/TBW": "0.4"})
        self.assertEqual(sorted(found), ["bca_ecw_tbw", "mfa_ecw_tbw"])

    def test_empty_or_missing_blocks(self):
        self.assertEqual(m.extra_metrics({}, {}), [])
        self.assertEqual(m.extra_metrics(None, None), [])
        self.assertEqual(m.extra_metrics("oops", []), [])

    def test_result_is_sorted(self):
        slugs = [x.slug for x in m.extra_metrics({"B": 1, "A": 1}, {"C": 1})]
        self.assertEqual(slugs, sorted(slugs))


class ReadTests(unittest.TestCase):
    def test_reads_top_level_nested_and_missing(self):
        bca = {"ICW": "25.1", "SEG": {"RA": "2.1"}}
        metrics = by_slug(bca, {"WHR": 0.9})
        self.assertEqual(m.read_metric(bca, {}, metrics["bca_icw"]), 25.1)
        self.assertEqual(m.read_metric(bca, {}, metrics["bca_seg_ra"]), 2.1)
        self.assertEqual(m.read_metric(bca, {"WHR": 0.9}, metrics["mfa_whr"]), 0.9)
        # a later scan that lacks the field
        self.assertIsNone(m.read_metric({}, {}, metrics["bca_icw"]))
        self.assertIsNone(m.read_metric({"SEG": 5}, {}, metrics["bca_seg_ra"]))
        self.assertIsNone(m.read_metric({"ICW": "n/a"}, {}, metrics["bca_icw"]))


class FeaturedTests(unittest.TestCase):
    def test_aliases_and_enabled_by_default(self):
        metrics = by_slug(
            {"InBodyScore": 78, "ICW": 20},
            {"VisceralFatLevel": 9, "WAIST_HIP_RATIO": 0.9, "BMR": 1650},
        )
        names = {s: x.name for s, x in metrics.items()}
        self.assertEqual(names["bca_inbodyscore"], "InBody score")
        self.assertEqual(names["mfa_visceralfatlevel"], "Visceral fat level")
        self.assertEqual(names["mfa_bmr"], "Basal metabolic rate")
        self.assertTrue(all(metrics[s].featured for s in ("bca_inbodyscore", "mfa_visceralfatlevel", "mfa_bmr")))
        self.assertFalse(metrics["bca_icw"].featured)


if __name__ == "__main__":
    unittest.main()
