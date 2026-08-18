import json
import unittest
from pathlib import Path

from career_pilot.deepseek_client import build_payload
from career_pilot.jd_analyzer import analyze_with_model, demo_analysis, validate_analysis
from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile


ROOT = Path(__file__).parents[1]


def load_profile():
    raw = json.loads((ROOT / "data" / "private" / "profile.json").read_text(encoding="utf-8"))
    return CareerProfile.from_dict(raw)


def get_job(job_id):
    jobs = load_catalog(ROOT / "data" / "jobs" / "seed_jobs.json")
    return next(job for job in jobs if job["id"] == job_id)


class FakeClient:
    def __init__(self, result):
        self.result = result

    def generate_json(self, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.result


class JDAnalyzerTests(unittest.TestCase):
    def test_demo_analysis_surfaces_strength_and_gap(self):
        result = demo_analysis(load_profile(), get_job("alibaba-beijing-shanghai-pm-intern"))
        self.assertEqual(result["decision"], "likely_apply")
        self.assertTrue(any("沟通" in item["claim"] for item in result["strengths"]))
        self.assertTrue(any("PRD" in item["gap"] for item in result["gaps"]))

    def test_demo_analysis_respects_hard_education_gate(self):
        result = demo_analysis(load_profile(), get_job("taikang-beijing-product-research"))
        self.assertEqual(result["decision"], "not_eligible_now")
        self.assertTrue(any(item["status"] == "not_met" for item in result["hard_requirements"]))
        self.assertIn("暂不投递", result["next_actions"][0])
        self.assertTrue(any("硬门槛" in item["gap"] for item in result["gaps"]))

    def test_rejects_untraceable_evidence(self):
        raw = demo_analysis(load_profile(), get_job("haier-qingdao-platform-ops"))
        raw["strengths"][0]["evidence_refs"] = ["memory.user_is_good"]
        with self.assertRaisesRegex(ValueError, "非法证据"):
            validate_analysis(raw, "haier-qingdao-platform-ops")

    def test_model_client_output_is_validated(self):
        job = get_job("haier-qingdao-platform-ops")
        expected = demo_analysis(load_profile(), job)
        client = FakeClient(expected)
        result = analyze_with_model(load_profile(), job, client)
        self.assertEqual(result["job_id"], job["id"])
        self.assertIn("返回且只返回合法 JSON", client.system_prompt)
        self.assertIn("绝不能返回空数组", client.system_prompt)
        self.assertIn("未提供证据", client.system_prompt)
        self.assertIn("不能误写成硬门槛", client.system_prompt)
        self.assertIn('"profile"', client.user_prompt)

    def test_deepseek_payload_requests_json_object(self):
        payload = build_payload("deepseek-v4-pro", "system", "user")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main()
