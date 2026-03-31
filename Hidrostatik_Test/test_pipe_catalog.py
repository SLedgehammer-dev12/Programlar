from __future__ import annotations

import unittest

from pipe_catalog import find_pipe_size, find_schedule, get_pipe_size_options, get_schedule_options


class PipeCatalogTests(unittest.TestCase):
    def test_catalog_contains_full_size_range(self) -> None:
        options = get_pipe_size_options()
        self.assertGreaterEqual(len(options), 44)
        self.assertTrue(any("NPS 1/8" in option for option in options))
        self.assertTrue(any("NPS 48" in option for option in options))
        self.assertTrue(any("NPS 80" in option for option in options))

    def test_schedule_lookup_returns_wall_thickness(self) -> None:
        size_label = next(option for option in get_pipe_size_options() if option.startswith("NPS 16 "))
        schedule_label = next(option for option in get_schedule_options(size_label) if "40 / XS" in option)

        pipe_size = find_pipe_size(size_label)
        schedule = find_schedule(size_label, schedule_label)

        self.assertIsNotNone(pipe_size)
        self.assertIsNotNone(schedule)
        self.assertEqual(pipe_size["outside_diameter_mm"], 406.4)
        self.assertEqual(schedule["wall_thickness_mm"], 12.7)

    def test_large_diameter_catalog_exposes_unlabeled_b3610_wall_thickness_rows(self) -> None:
        size_label = next(option for option in get_pipe_size_options() if option.startswith("NPS 48 "))
        options = get_schedule_options(size_label)

        self.assertIn("WT 8.74 mm (B36.10)", options)
        self.assertIn("Sch STD - 9.53 mm", options)
        self.assertIn("Sch XS - 12.70 mm", options)


if __name__ == "__main__":
    unittest.main()
