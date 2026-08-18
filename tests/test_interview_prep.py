from __future__ import annotations

import unittest
from pathlib import Path

from career_pilot.interview_prep import (
    generate_interview_prep,
    render_interview_prep_markdown,
    validate_interview_prep,
)
from career_pilot.job_catalog import load_catalog
from career_pilot.models import CareerProfile


ROOT = Path(__file__).parents[1]


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def generate_json(self, system_prompt, user_prompt):
        output = self.outputs[self.calls]
        self.calls += 1
        return output


def profile():
    return CareerProfile.from_dict(
        {
            "major": "金融学",
            "graduation_cohort": "2029",
            "education_level": "本科",
            "target_cities": ["青岛", "上海", "北京"],
            "internship_days_per_week": 5,
            "internship_duration_months_min": 3,
            "rag_experience": "project",
            "scores": {
                "analysis": 3,
                "communication": 4,
                "detail": 3,
                "coding": 5,
                "research": 3,
                "sales": 4,
                "uncertainty": 3,
            },
        }
    )


def job():
    jobs = load_catalog(ROOT / "data" / "jobs" / "seed_jobs.json")
    return next(item for item in jobs if item["id"] == "zhongrui-qingdao-product-ops")


def resume():
    return {
        "evidence": [
            {"evidence_id": "R001", "text": "使用 Excel 整理课程调研数据并制作图表", "kind": "experience"},
            {"evidence_id": "R002", "text": "在学生项目中与四名同学协作完成展示", "kind": "experience"},
        ],
        "evidence_count": 2,
    }


def valid_output():
    questions = []
    for index in range(1, 5):
        questions.append(
            {
                "id": f"Q{index}",
                "question": f"请介绍一段与岗位要求相关的经历 {index}。",
                "why_it_matters": "用于核验岗位要求与简历证据的关联。",
                "evidence_refs": ["job.requirements[0]", "resume.R001"],
                "answer_structure": ["交代情境与目标", "说明你亲自执行的步骤", "只引用可核验的结果"],
                "honesty_boundary": "不要补造未记录的数字或职责。",
            }
        )
    return {
        "job_id": "zhongrui-qingdao-product-ops",
        "opening": "重点准备数据整理和协作经历的真实细节。",
        "focus_areas": [
            {
                "label": "数据整理",
                "rationale": "岗位职责与简历中的 Excel 事实可形成追问线索。",
                "evidence_refs": ["job.responsibilities[1]", "resume.R001"],
            },
            {
                "label": "协作过程",
                "rationale": "岗位涉及跨部门工作，可核验学生项目中的协作细节。",
                "evidence_refs": ["job.skill_tags", "resume.R002"],
            },
        ],
        "questions": questions,
        "questions_to_ask": [
            {
                "question": f"这个岗位前三个月最重要的交付是什么 {index}？",
                "rationale": "帮助确认职责优先级。",
                "evidence_refs": ["job.responsibilities"],
            }
            for index in range(1, 4)
        ],
        "preparation_checklist": [
            {"item": f"核对简历证据 R001 的真实细节 {index}。", "evidence_refs": ["resume.R001"]}
            for index in range(1, 5)
        ],
    }


class InterviewPrepTests(unittest.TestCase):
    def test_validates_and_renders_evidence_based_prep(self):
        result = validate_interview_prep(valid_output(), profile(), job(), resume())
        report = render_interview_prep_markdown(result, profile(), job(), resume(), "2026-08-18")
        self.assertIn("## 岗位专属问题", report)
        self.assertIn("`resume.R001`：使用 Excel", report)
        self.assertIn("不是可直接背诵的代写答案", report)

    def test_rejects_unknown_or_unbalanced_evidence(self):
        output = valid_output()
        output["questions"][0]["evidence_refs"] = ["job.requirements[0]", "resume.R999"]
        with self.assertRaisesRegex(ValueError, "不存在"):
            validate_interview_prep(output, profile(), job(), resume())

        output = valid_output()
        output["questions"][0]["evidence_refs"] = ["resume.R001"]
        with self.assertRaisesRegex(ValueError, "job"):
            validate_interview_prep(output, profile(), job(), resume())

    def test_rejects_written_first_person_answer(self):
        output = valid_output()
        output["questions"][0]["answer_structure"][1] = "我负责清洗全部数据并实现显著提升"
        with self.assertRaisesRegex(ValueError, "代写答案"):
            validate_interview_prep(output, profile(), job(), resume())

    def test_retries_after_validation_failure(self):
        invalid = valid_output()
        invalid["questions"][0]["id"] = "bad"
        client = FakeClient([invalid, valid_output()])
        result = generate_interview_prep(profile(), job(), resume(), client)
        self.assertEqual(result["questions"][0]["id"], "Q1")
        self.assertEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()
