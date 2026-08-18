from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Protocol, Set

from .jd_analyzer import profile_to_dict
from .models import CareerProfile


SYSTEM_PROMPT = """你是 CareerPilot 的简历—岗位证据匹配器。
你必须只依据输入 JSON 返回且只返回合法 JSON，禁止补写候选人没有提供的经历、技能或成果。

证据规则：
1. 简历证据只能写成 resume.R001 这样的引用，且编号必须来自输入。
2. 岗位证据只能引用输入中存在的 job 字段，例如 job.requirements、job.responsibilities；列表项可使用 job.requirements[0] 形式的精确引用。
3. 画像证据只能引用输入中存在的 profile 字段，例如 profile.graduation_cohort。
4. 每项优势必须同时包含至少一个 resume.* 和一个 job.* 引用。
5. requirement_matches 中 matched 或 partial 的项目必须引用候选人证据（resume.* 或 profile.*）；unknown 代表“尚未提供证据”，不能推断为不会。
6. gaps 只描述“岗位要求与现有证据之间的缺口”，不得把缺少材料写成确定的能力缺陷。
7. 不得引用姓名、电话、邮箱、照片等身份信息。
8. hard_requirements、requirement_matches 和 gaps 每一项都必须包含至少一个 job.* 引用。
9. profile.rag_experience=none 表示候选人已明确确认目前没有 RAG 经历，可以据此写成当前事实；这与普通的“简历未提供证据”不同。
10. 到岗天数和持续月份必须使用 profile.internship_days_per_week 与 profile.internship_duration_months_min 判断。
11. 技能栏只证明“简历列出了该工具”，不能推导为熟练、精通、掌握或擅长；摘要和优势中禁止使用未经直接证据支持的能力强度词。
12. profile.rag_experience=none 时，RAG 只能作为未来学习任务，不得作为当前简历修改建议。
13. 建议补充数字时必须明确限定为“仅使用已有可核验记录”，不得暗示编造数据量、准确率或提升幅度。

判断规则：
- hard_requirements 只放明确硬门槛：学历、毕业时间、到岗天数/时长、强制证书。
- 工作城市是岗位属性，不得单独列为 hard_requirements。
- “相关专业优先”“有经验优先”和一般能力要求不是硬门槛。
- decision 只能是 likely_apply、stretch、not_eligible_now。
- confidence 只能是 low、medium、high。
- 如果有明确未满足的硬门槛，decision 必须为 not_eligible_now。
- 2026_or_later 表示 2026 年或以后毕业均符合毕业年份范围。

JSON 顶层字段必须是：
job_id、decision、confidence、summary、hard_requirements、requirement_matches、strengths、gaps、resume_edits、interview_questions、next_actions。

字段结构：
- hard_requirements: requirement、status、evidence_refs；status 为 met/not_met/unknown。
- requirement_matches: requirement、status、rationale、evidence_refs；status 为 matched/partial/unknown。
- strengths: claim、evidence_refs，最多4项。
- gaps: gap、evidence_refs、action，最多4项。
- resume_edits: target、current_evidence_refs、suggestion，最多3项，只能优化已有事实的表达，不能创造数字。
- interview_questions: 字符串数组，最多5项。
- next_actions: 字符串数组，最多4项，按优先级排列。
"""

HARD_GATE_JOB_REFS = {
    "job.requirements",
    "job.education_min",
    "job.graduation_cohort",
}

UNSUPPORTED_NEGATIVE = re.compile(r"(?:能力|理解|经验|水平|基础).{0,4}(?:不足|较弱|欠缺)|不会|不具备")
UNSUPPORTED_PROFICIENCY = re.compile(r"熟练|精通|擅长|掌握|能力较强")


class JsonModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, object]:
        ...


def build_match_prompt(
    profile: CareerProfile, job: Dict[str, object], resume_payload: Dict[str, object]
) -> str:
    raw_evidence = resume_payload.get("evidence", [])
    prompt_evidence = [
        {
            "evidence_ref": f"resume.{item['evidence_id']}",
            "text": item.get("text", ""),
            "kind": item.get("kind", "resume_text"),
        }
        for item in raw_evidence
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    ] if isinstance(raw_evidence, list) else []
    payload = {
        "profile": profile_to_dict(profile),
        "job": job,
        "resume_evidence": prompt_evidence,
    }
    return "请完成简历与岗位的证据匹配，并返回规定 JSON：\n" + json.dumps(
        payload, ensure_ascii=False, indent=2
    )


def _allowed_refs(
    profile: CareerProfile, job: Dict[str, object], resume_payload: Dict[str, object]
) -> Set[str]:
    profile_refs = {f"profile.{key}" for key in profile_to_dict(profile)}
    job_refs = {f"job.{key}" for key in job}
    for key, value in job.items():
        if isinstance(value, list):
            job_refs.update(f"job.{key}[{index}]" for index in range(len(value)))
    evidence = resume_payload.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("resume_evidence.evidence 必须是数组")
    resume_refs = {
        f"resume.{item['evidence_id']}"
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    return profile_refs | job_refs | resume_refs


def _validate_refs(
    refs: object,
    path: str,
    allowed: Set[str],
    require_job: bool = False,
    require_resume: bool = False,
    require_candidate: bool = False,
) -> List[str]:
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
        raise ValueError(f"{path} 必须是非空字符串数组")
    unknown = [ref for ref in refs if ref not in allowed]
    if unknown:
        raise ValueError(f"{path} 包含不存在的证据引用：{unknown}")
    if require_job and not any(ref.startswith("job.") for ref in refs):
        raise ValueError(f"{path} 必须包含 job.* 引用")
    if require_resume and not any(ref.startswith("resume.") for ref in refs):
        raise ValueError(f"{path} 必须包含 resume.* 引用")
    if require_candidate and not any(
        ref.startswith(("resume.", "profile.")) for ref in refs
    ):
        raise ValueError(f"{path} 必须包含 resume.* 或 profile.* 候选人证据")
    return refs


def _validate_text_list(value: object, path: str) -> None:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{path} 必须是非空字符串数组")


def validate_match(
    raw: Dict[str, object],
    profile: CareerProfile,
    job: Dict[str, object],
    resume_payload: Dict[str, object],
) -> Dict[str, object]:
    required = {
        "job_id",
        "decision",
        "confidence",
        "summary",
        "hard_requirements",
        "requirement_matches",
        "strengths",
        "gaps",
        "resume_edits",
        "interview_questions",
        "next_actions",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(f"模型输出缺少字段：{sorted(missing)}")
    if raw["job_id"] != job["id"]:
        raise ValueError("模型输出 job_id 与输入不一致")
    if raw["decision"] not in {"likely_apply", "stretch", "not_eligible_now"}:
        raise ValueError("模型输出 decision 不合法")
    if raw["confidence"] not in {"low", "medium", "high"}:
        raise ValueError("模型输出 confidence 不合法")
    if not isinstance(raw["summary"], str) or not raw["summary"].strip():
        raise ValueError("模型输出 summary 不能为空")
    if UNSUPPORTED_NEGATIVE.search(raw["summary"]):
        raise ValueError("模型输出 summary 把待验证事项写成了负面能力判断")

    allowed = _allowed_refs(profile, job, resume_payload)
    sections = {
        "hard_requirements": {"requirement", "status", "evidence_refs"},
        "requirement_matches": {"requirement", "status", "rationale", "evidence_refs"},
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
            if section == "hard_requirements" and item["status"] not in {
                "met",
                "not_met",
                "unknown",
            }:
                raise ValueError(f"模型输出 {section}[{index}].status 不合法")
            if section == "requirement_matches" and item["status"] not in {
                "matched",
                "partial",
                "unknown",
            }:
                raise ValueError(f"模型输出 {section}[{index}].status 不合法")
            require_resume = section == "strengths"
            require_candidate = section == "requirement_matches" and item["status"] in {
                "matched",
                "partial",
            }
            _validate_refs(
                item["evidence_refs"],
                f"{section}[{index}].evidence_refs",
                allowed,
                require_job=section in {"hard_requirements", "requirement_matches", "strengths", "gaps"},
                require_resume=require_resume,
                require_candidate=require_candidate,
            )
            refs = item["evidence_refs"]
            if section == "hard_requirements" and not any(
                ref in HARD_GATE_JOB_REFS or ref.startswith("job.requirements[")
                for ref in refs
            ):
                raise ValueError(
                    f"{section}[{index}] 不是可验证硬门槛；必须引用学历、毕业时间或 job.requirements"
                )
            if section == "gaps" and UNSUPPORTED_NEGATIVE.search(str(item["gap"])):
                raise ValueError(
                    f"{section}[{index}].gap 把证据缺失写成了确定的负面能力判断"
                )
            if section == "strengths" and UNSUPPORTED_PROFICIENCY.search(str(item["claim"])):
                raise ValueError(
                    f"{section}[{index}].claim 使用了简历事实无法证明的熟练度或能力强度表述"
                )

    edits = raw["resume_edits"]
    if not isinstance(edits, list):
        raise ValueError("模型输出 resume_edits 必须是数组")
    for index, item in enumerate(edits):
        fields = {"target", "current_evidence_refs", "suggestion"}
        if not isinstance(item, dict) or not fields.issubset(item):
            raise ValueError(f"模型输出 resume_edits[{index}] 字段不完整")
        _validate_refs(
            item["current_evidence_refs"],
            f"resume_edits[{index}].current_evidence_refs",
            allowed,
            require_resume=True,
        )
        suggestion = str(item["suggestion"])
        if "量化" in suggestion and not any(
            marker in suggestion for marker in ("可核验", "已有记录", "真实记录")
        ):
            raise ValueError(
                f"resume_edits[{index}].suggestion 建议量化时必须明确只使用可核验记录"
            )
        if profile.rag_experience == "none" and "RAG" in (
            str(item["target"]) + suggestion
        ):
            raise ValueError(
                f"resume_edits[{index}] 不能建议把已确认不存在的 RAG 经历写入当前简历"
            )

    _validate_text_list(raw["interview_questions"], "interview_questions")
    _validate_text_list(raw["next_actions"], "next_actions")
    for index, action in enumerate(raw["next_actions"]):
        if "量化" in action and not any(
            marker in action for marker in ("可核验", "已有记录", "真实记录")
        ):
            raise ValueError(
                f"next_actions[{index}] 建议量化时必须明确只使用可核验记录"
            )
    return raw


def match_with_model(
    profile: CareerProfile,
    job: Dict[str, object],
    resume_payload: Dict[str, object],
    client: JsonModelClient,
) -> Dict[str, object]:
    base_prompt = build_match_prompt(profile, job, resume_payload)
    current_prompt = base_prompt
    last_error: Optional[ValueError] = None
    for attempt in range(3):
        raw = client.generate_json(SYSTEM_PROMPT, current_prompt)
        try:
            return validate_match(raw, profile, job, resume_payload)
        except ValueError as error:
            last_error = error
            if attempt == 2:
                break
            current_prompt = (
                base_prompt
                + "\n\n上一次输出未通过程序校验。校验错误："
                + str(error)
                + "\n请重新生成完整 JSON，修正该错误，并继续严格遵守所有证据规则。"
            )
    raise ValueError(f"模型三次输出均未通过校验；最后错误：{last_error}") from last_error
