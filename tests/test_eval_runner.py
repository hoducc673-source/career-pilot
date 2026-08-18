import json
import unittest
from pathlib import Path

from career_pilot.eval_runner import render_evaluation_summary, run_evaluation
from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile


ROOT = Path(__file__).parents[1]


class EvalRunnerTests(unittest.TestCase):
    def test_all_public_evaluation_cases_pass(self):
        cases = json.loads((ROOT / "evals/resume_match_cases.json").read_text(encoding="utf-8"))
        base = json.loads(
            (ROOT / "evals/fixtures/resume_match_base.json").read_text(encoding="utf-8")
        )
        profile = CareerProfile.from_dict(
            json.loads((ROOT / "evals/fixtures/eval_profile.json").read_text(encoding="utf-8"))
        )
        resume = json.loads(
            (ROOT / "evals/fixtures/eval_resume_evidence.json").read_text(encoding="utf-8")
        )
        job = next(
            item
            for item in load_catalog(ROOT / "data/jobs/seed_jobs.json")
            if item["id"] == base["job_id"]
        )

        report = run_evaluation(cases, base, profile, job, resume)
        summary = render_evaluation_summary(report)

        self.assertGreaterEqual(report["case_count"], 10)
        self.assertEqual(report["failed_count"], 0)
        self.assertEqual(report["pass_rate"], 1.0)
        self.assertIn("通过率：100%", summary)


if __name__ == "__main__":
    unittest.main()
