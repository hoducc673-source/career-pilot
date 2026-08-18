import unittest
from pathlib import Path

from career_pilot.job_catalog import load_catalog, render_summary


CATALOG_PATH = Path(__file__).parents[1] / "data" / "jobs" / "seed_jobs.json"


class JobCatalogTests(unittest.TestCase):
    def test_seed_catalog_is_valid(self):
        jobs = load_catalog(CATALOG_PATH)
        self.assertEqual(len(jobs), 11)
        self.assertEqual(len({job["id"] for job in jobs}), len(jobs))

    def test_catalog_covers_target_cities(self):
        jobs = load_catalog(CATALOG_PATH)
        cities = {city for job in jobs for city in job["cities"]}
        self.assertTrue({"青岛", "上海", "北京"}.issubset(cities))

    def test_catalog_contains_a_hard_gate_example(self):
        jobs = load_catalog(CATALOG_PATH)
        self.assertTrue(any(job["preliminary_fit"] == "not_eligible_now" for job in jobs))

    def test_summary_contains_skill_frequency(self):
        summary = render_summary(load_catalog(CATALOG_PATH))
        self.assertIn("高频技能", summary)
        self.assertIn("communication", summary)


if __name__ == "__main__":
    unittest.main()
