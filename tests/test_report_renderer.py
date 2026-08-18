import json
import unittest
from pathlib import Path

from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile
from career_pilot.report_renderer import render_match_report


ROOT = Path(__file__).parents[1]


class ReportRendererTests(unittest.TestCase):
    def test_renders_traceable_human_readable_report(self):
        profile = CareerProfile.from_dict(
            json.loads((ROOT / "data/private/profile.json").read_text(encoding="utf-8"))
        )
        resume = json.loads(
            (ROOT / "data/private/resume_evidence.json").read_text(encoding="utf-8")
        )
        match = json.loads(
            (ROOT / "data/private/matches/xiaohongshu-ai-pm-v8.json").read_text(
                encoding="utf-8"
            )
        )
        job = next(
            item
            for item in load_catalog(ROOT / "data/jobs/seed_jobs.json")
            if item["id"] == match["job_id"]
        )

        report = render_match_report(match, profile, job, resume, generated_on="2026-08-15")

        self.assertIn("小红书｜AI产品经理实习生", report)
        self.assertIn("拉伸匹配", report)
        self.assertIn("每周至少4天且3个月以上", report)
        self.assertIn("`resume.R014`", report)
        self.assertIn("山东财经大学", report)
        self.assertIn("不可直接写入正式简历", report)
        self.assertIn("- [ ]", report)


if __name__ == "__main__":
    unittest.main()
