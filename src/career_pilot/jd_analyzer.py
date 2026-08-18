from __future__ import annotations

import json
from typing import Dict, List, Protocol

from .models import CareerProfile, DIMENSION_LABELS


SYSTEM_PROMPT = """你是 CareerPilot 的岗位证据分析器。
你的任务是比较候选人画像与一个真实岗位，返回且只返回合法 JSON。
不得编造候选人经历、技能、证书或岗位要求。
没有证据时必须使用 unknown，并把缺口写清楚。
“未提供证据”不等于候选人不会或缺乏；只能写“尚未提供相关证据”，不能写成确定的负面事实。
hard_requirements 只允许放明确的硬门槛，例如学历、毕业时间、到岗天数或强制证书。
“相关专业优先”“有经验优先”和一般能力要求属于偏好或待验证能力，不能误写成硬门槛。
evidence_refs 只能引用输入中真实存在的 profile.* 或 job.* 字段。
每一个 evidence_refs 都必须至少包含一个引用，绝不能返回空数组。
当要求来自岗位但候选人没有对应证据、状态为 unknown 时，至少引用 job.requirements；不要为了填满数组编造 profile 证据。
decision 只能是 likely_apply、stretch、not_eligible_now。
confidence 只能是 low、medium、high。
JSON 顶层字段必须包含 job_id、decision、confidence、summary、hard_requirements、strengths、gaps、next_actions。
hard_requirements 每项包含 requirement、status、evidence_refs，status 只能是 met、not_met、unknown。
strengths 每项包含 claim、evidence_refs。
gaps 每项包含 gap、evidence_refs、action。
next_actions 是字符串数组。"""


class JsonModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, object]:
        ...


def profile_to_dict(profile: CareerProfile) -> Dict[str, object]:
    return {
        "major": profile.major,
        "graduation_cohort": profile.graduation_cohort,
        "education_level": profile.education_level,
        "target_cities": profile.target_cities,
        "primary_direction": profile.primary_direction,
        "secondary_direction": profile.secondary_direction,
        "internship_days_per_week": profile.internship_days_per_week,
        "internship_duration_months_min": profile.internship_duration_months_min,
        "rag_experience": profile.rag_experience,
        "scores": profile.scores,
    }


def build_user_prompt(profile: CareerProfile, job: Dict[str, object]) -> str:
    payload = {"profile": profile_to_dict(profile), "job": job}
    return "请基于以下 JSON 输入完成岗位分析，并返回 JSON：\n" + json.dumps(
        payload, ensure_ascii=False, indent=2
    )


def _validate_evidence_refs(refs: object, path: str) -> None:
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        raise ValueError(f"{path}.evidence_refs 必须是字符串数组")
    if not refs:
        raise ValueError(f"{path}.evidence_refs 不能为空")
    for ref in refs:
        if not (ref.startswith("profile.") or ref.startswith("job.")):
            raise ValueError(f"{path} 包含非法证据引用：{ref}")


def validate_analysis(raw: Dict[str, object], expected_job_id: str) -> Dict[str, object]:
    required = {
        "job_id",
        "decision",
        "confidence",
        "summary",
        "hard_requirements",
        "strengths",
        "gaps",
        "next_actions",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(f"模型输出缺少字段：{sorted(missing)}")
    if raw["job_id"] != expected_job_id:
        raise ValueError("模型输出 job_id 与输入不一致")
    if raw["decision"] not in {"likely_apply", "stretch", "not_eligible_now"}:
        raise ValueError("模型输出 decision 不合法")
    if raw["confidence"] not in {"low", "medium", "high"}:
        raise ValueError("模型输出 confidence 不合法")
    if not isinstance(raw["summary"], str) or not raw["summary"].strip():
        raise ValueError("模型输出 summary 不能为空")
    if not isinstance(raw["next_actions"], list) or not all(
        isinstance(item, str) and item.strip() for item in raw["next_actions"]
    ):
        raise ValueError("模型输出 next_actions 必须是非空字符串数组")

    sections = {
        "hard_requirements": {"requirement", "status", "evidence_refs"},
        "strengths": {"claim", "evidence_refs"},
        "gaps": {"gap", "evidence_refs", "action"},
    }
    for section, fields in sections.items():
        items = raw[section]
        if not isinstance(items, list):
            raise ValueError(f"模型输出 {section} 必须是数组")
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not fields.issubset(item):
                raise ValueError(f"模型输出 {section}[{index}] 字段不完整")
            _validate_evidence_refs(item["evidence_refs"], f"{section}[{index}]")
            if section == "hard_requirements" and item["status"] not in {"met", "not_met", "unknown"}:
                raise ValueError(f"模型输出 {section}[{index}].status 不合法")
    return raw


def analyze_with_model(
    profile: CareerProfile, job: Dict[str, object], client: JsonModelClient
) -> Dict[str, object]:
    raw = client.generate_json(SYSTEM_PROMPT, build_user_prompt(profile, job))
    return validate_analysis(raw, str(job["id"]))


def demo_analysis(profile: CareerProfile, job: Dict[str, object]) -> Dict[str, object]:
    hard_requirements: List[Dict[str, object]] = []
    for requirement in job["requirements"]:
        requirement_text = str(requirement)
        status = "unknown"
        refs = ["job.requirements"]
        if "硕士" in requirement_text:
            status = "met" if "硕士" in profile.education_level else "not_met"
            refs.append("profile.education_level")
        elif "本科" in requirement_text:
            status = "met" if profile.education_level in {"本科", "硕士", "博士"} else "not_met"
            refs.append("profile.education_level")
        elif "2027" in requirement_text:
            status = "met" if profile.graduation_cohort == "2027" else "unknown"
            refs.append("profile.graduation_cohort")
        elif ("金融" in requirement_text or "经济" in requirement_text) and "金融" in profile.major:
            status = "met"
            refs.append("profile.major")
        hard_requirements.append(
            {"requirement": requirement_text, "status": status, "evidence_refs": refs}
        )

    strengths: List[Dict[str, object]] = []
    if "communication" in job["skill_tags"] and profile.scores["communication"] >= 4:
        strengths.append(
            {
                "claim": f"沟通与协作自评 {profile.scores['communication']}/5，与岗位高频要求方向一致。",
                "evidence_refs": ["profile.scores.communication", "job.skill_tags"],
            }
        )
    if any(tag in job["skill_tags"] for tag in {"ai_literacy", "agent", "python"}) and profile.scores["coding"] >= 4:
        strengths.append(
            {
                "claim": "数字工具学习意愿较强，但这只是方向性优势，不代表已经掌握岗位技能。",
                "evidence_refs": ["profile.scores.coding", "job.skill_tags"],
            }
        )

    gaps: List[Dict[str, object]] = []
    if "data_analysis" in job["skill_tags"] and profile.scores["analysis"] <= 3:
        gaps.append(
            {
                "gap": "数据分析能力目前只有中性自评，没有作品证据。",
                "evidence_refs": ["profile.scores.analysis", "job.skill_tags"],
                "action": "完成一份包含数据清洗、指标、图表和业务结论的分析作品。",
            }
        )
    if any(tag in job["skill_tags"] for tag in {"product_management", "prd"}):
        gaps.append(
            {
                "gap": "当前画像没有产品原型或PRD证据。",
                "evidence_refs": ["profile.primary_direction", "job.skill_tags"],
                "action": "为 CareerPilot 补充一页用户流程和一份简版 PRD。",
            }
        )

    decision = str(job["preliminary_fit"])
    if decision == "not_eligible_now":
        gaps.append(
            {
                "gap": "当前存在无法通过短期作品弥补的硬门槛。",
                "evidence_refs": ["profile.education_level", "job.requirements"],
                "action": "停止投递该岗位，寻找职责相近但最低学历为本科的岗位。",
            }
        )
        next_actions = [
            "暂不投递该岗位，避免浪费投递机会。",
            "把岗位职责保留为长期能力参考。",
            "搜索同类本科校招或实习岗位。",
        ]
    else:
        next_actions = [
            "核验官方页面是否仍可投递。",
            "加入脱敏简历证据后重新分析。",
            "优先完成与岗位缺口对应的小作品。",
        ]
    return validate_analysis(
        {
            "job_id": job["id"],
            "decision": decision,
            "confidence": "low",
            "summary": "这是不调用大模型的离线基线，只使用问卷和人工结构化 JD；加入脱敏简历后才能提高置信度。",
            "hard_requirements": hard_requirements,
            "strengths": strengths,
            "gaps": gaps,
            "next_actions": next_actions,
        },
        str(job["id"]),
    )
