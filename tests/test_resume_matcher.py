import json
import unittest
from pathlib import Path

from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile
from career_pilot.resume_matcher import match_with_model, validate_match


ROOT = Path(__file__).parents[1]


class FakeClient:
    def __init__(self, result):
        self.result = result

    def generate_json(self, system_prompt, user_prompt):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.result


class SequenceClient:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def generate_json(self, system_prompt, user_prompt):
        self.calls += 1
        self.last_user_prompt = user_prompt
        return next(self.results)


def fixtures():
    profile = CareerProfile.from_dict(
        json.loads((ROOT / "evals/fixtures/eval_profile.json").read_text(encoding="utf-8"))
    )
    job = next(
        item
        for item in load_catalog(ROOT / "data/jobs/seed_jobs.json")
        if item["id"] == "xiaohongshu-beijing-shanghai-ai-pm-intern"
    )
    resume = {
        "evidence": [
            {"evidence_id": "R001", "text": "参与模型输出评测", "kind": "resume_text"},
            {"evidence_id": "R002", "text": "技术栈：Python", "kind": "resume_text"},
        ]
    }
    result = {
        "job_id": job["id"],
        "decision": "stretch",
        "confidence": "medium",
        "summary": "有相关评测证据，但产品文档证据尚不完整。",
        "hard_requirements": [
            {
                "requirement": "本科及以上在读",
                "status": "met",
                "evidence_refs": ["job.requirements", "profile.education_level"],
            }
        ],
        "requirement_matches": [
            {
                "requirement": "设计评测并分析 Bad Case",
                "status": "matched",
                "rationale": "简历提供模型输出评测证据。",
                "evidence_refs": ["job.responsibilities", "resume.R001"],
            }
        ],
        "strengths": [
            {
                "claim": "具备模型输出评测经验。",
                "evidence_refs": ["job.responsibilities", "resume.R001"],
            }
        ],
        "gaps": [
            {
                "gap": "尚未提供 PRD 证据。",
                "evidence_refs": ["job.requirements"],
                "action": "补充 CareerPilot 简版 PRD。",
            }
        ],
        "resume_edits": [
            {
                "target": "项目描述",
                "current_evidence_refs": ["resume.R001"],
                "suggestion": "突出评测标准和问题归因。",
            }
        ],
        "interview_questions": ["如何定义模型输出评测标准？"],
        "next_actions": ["补充 PRD 作品。"],
    }
    return profile, job, resume, result


class ResumeMatcherTests(unittest.TestCase):
    def test_accepts_traceable_match(self):
        profile, job, resume, result = fixtures()
        client = FakeClient(result)
        actual = match_with_model(profile, job, resume, client)
        self.assertEqual(actual["decision"], "stretch")
        self.assertIn("resume.R001", client.user_prompt)
        self.assertIn("每项优势必须同时包含", client.system_prompt)
        self.assertIn('"internship_days_per_week": 5', client.user_prompt)
        self.assertIn('"rag_experience": "none"', client.user_prompt)

    def test_rejects_nonexistent_resume_reference(self):
        profile, job, resume, result = fixtures()
        result["strengths"][0]["evidence_refs"][-1] = "resume.R999"
        with self.assertRaisesRegex(ValueError, "不存在的证据"):
            validate_match(result, profile, job, resume)

    def test_accepts_valid_indexed_job_reference(self):
        profile, job, resume, result = fixtures()
        result["hard_requirements"][0]["evidence_refs"] = [
            "job.requirements[0]",
            "profile.education_level",
        ]
        actual = validate_match(result, profile, job, resume)
        self.assertEqual(actual["hard_requirements"][0]["status"], "met")

    def test_rejects_out_of_range_job_reference(self):
        profile, job, resume, result = fixtures()
        result["hard_requirements"][0]["evidence_refs"] = [
            "job.requirements[99]",
            "profile.education_level",
        ]
        with self.assertRaisesRegex(ValueError, "不存在的证据"):
            validate_match(result, profile, job, resume)

    def test_matched_requirement_requires_candidate_evidence(self):
        profile, job, resume, result = fixtures()
        result["requirement_matches"][0]["evidence_refs"] = ["job.responsibilities"]
        with self.assertRaisesRegex(ValueError, "候选人证据"):
            validate_match(result, profile, job, resume)

    def test_matched_requirement_accepts_profile_evidence(self):
        profile, job, resume, result = fixtures()
        result["requirement_matches"][0]["evidence_refs"] = [
            "job.requirements",
            "profile.education_level",
        ]
        actual = validate_match(result, profile, job, resume)
        self.assertEqual(actual["requirement_matches"][0]["status"], "matched")

    def test_repairs_one_invalid_model_response(self):
        profile, job, resume, valid = fixtures()
        invalid = json.loads(json.dumps(valid, ensure_ascii=False))
        invalid["hard_requirements"][0]["evidence_refs"] = ["profile.education_level"]
        client = SequenceClient([invalid, valid])
        actual = match_with_model(profile, job, resume, client)
        self.assertEqual(actual["decision"], "stretch")
        self.assertEqual(client.calls, 2)
        self.assertIn("未通过程序校验", client.last_user_prompt)

    def test_allows_two_repair_attempts(self):
        profile, job, resume, valid = fixtures()
        invalid_one = json.loads(json.dumps(valid, ensure_ascii=False))
        invalid_one["hard_requirements"][0]["evidence_refs"] = ["profile.education_level"]
        invalid_two = json.loads(json.dumps(valid, ensure_ascii=False))
        invalid_two["requirement_matches"][0]["evidence_refs"] = ["job.responsibilities"]
        client = SequenceClient([invalid_one, invalid_two, valid])
        actual = match_with_model(profile, job, resume, client)
        self.assertEqual(actual["decision"], "stretch")
        self.assertEqual(client.calls, 3)

    def test_rejects_location_as_a_hard_gate(self):
        profile, job, resume, result = fixtures()
        result["hard_requirements"][0] = {
            "requirement": "城市：北京、上海",
            "status": "met",
            "evidence_refs": ["job.cities", "profile.target_cities"],
        }
        with self.assertRaisesRegex(ValueError, "不是可验证硬门槛"):
            validate_match(result, profile, job, resume)

    def test_rejects_unsupported_negative_gap(self):
        profile, job, resume, result = fixtures()
        result["gaps"][0]["gap"] = "候选人的RAG理解深度不足"
        with self.assertRaisesRegex(ValueError, "负面能力判断"):
            validate_match(result, profile, job, resume)

    def test_quantification_advice_requires_verifiable_records(self):
        profile, job, resume, result = fixtures()
        result["resume_edits"][0]["suggestion"] = "补充量化数据。"
        with self.assertRaisesRegex(ValueError, "可核验记录"):
            validate_match(result, profile, job, resume)

    def test_rejects_unsupported_proficiency_claim(self):
        profile, job, resume, result = fixtures()
        result["strengths"][0]["claim"] = "熟练使用Python和SQL。"
        with self.assertRaisesRegex(ValueError, "熟练度或能力强度"):
            validate_match(result, profile, job, resume)

    def test_rejects_mastery_synonym(self):
        profile, job, resume, result = fixtures()
        result["strengths"][0]["claim"] = "掌握Python和SQL。"
        with self.assertRaisesRegex(ValueError, "熟练度或能力强度"):
            validate_match(result, profile, job, resume)

    def test_rejects_negative_in_summary(self):
        profile, job, resume, result = fixtures()
        result["summary"] = "候选人的技术理解可能不足。"
        with self.assertRaisesRegex(ValueError, "负面能力判断"):
            validate_match(result, profile, job, resume)

    def test_rejects_unverifiable_quantification_action(self):
        profile, job, resume, result = fixtures()
        result["next_actions"][0] = "量化项目成果。"
        with self.assertRaisesRegex(ValueError, "可核验记录"):
            validate_match(result, profile, job, resume)

    def test_rejects_rag_resume_edit_when_experience_is_none(self):
        profile, job, resume, result = fixtures()
        result["resume_edits"][0]["target"] = "补充RAG经历"
        with self.assertRaisesRegex(ValueError, "不存在的 RAG 经历"):
            validate_match(result, profile, job, resume)


if __name__ == "__main__":
    unittest.main()
