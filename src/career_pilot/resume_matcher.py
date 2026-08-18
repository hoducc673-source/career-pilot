from __future__ import annotations

import json
import re
from copy import deepcopy
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
- 输入中的 validated_hard_requirements 已由程序核验。hard_requirements 必须逐项原样复制，
  不得新增、删除、改写或重新判断；学历、毕业时间、到岗天数/时长、强制证书以该字段为准。
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
EDUCATION_RANK = {"专科": 1, "本科": 2, "硕士": 3, "博士": 4}
REQUIREMENT_STATUS_ALIASES = {
    "met": "matched",
    "match": "matched",
    "匹配": "matched",
    "partially_met": "partial",
    "partially_matched": "partial",
    "部分匹配": "partial",
    "not_met": "unknown",
    "unmatched": "unknown",
    "not_provided": "unknown",
    "未提供": "unknown",
    "未知": "unknown",
}
CERTIFICATE_PATTERN = re.compile(
    r"英语\s*(?:四|六)级|CET[-\s]?[46]|(?:必须|须|需)(?:持有|具备|通过).{0,12}(?:证书|资格|认证)",
    re.IGNORECASE,
)


class JsonModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str) -> Dict[str, object]:
        ...


def _resume_refs_for_certificate(
    requirement: str, resume_payload: Dict[str, object]
) -> List[str]:
    """Return direct resume evidence for a mandatory certificate, if supplied."""
    requirement_upper = requirement.upper().replace(" ", "")
    wants_cet6 = (
        "六级" in requirement
        or "CET-6" in requirement_upper
        or "CET6" in requirement_upper
    )
    wants_cet4 = (
        "四级" in requirement
        or "CET-4" in requirement_upper
        or "CET4" in requirement_upper
    )
    evidence = resume_payload.get("evidence", [])
    if not isinstance(evidence, list):
        return []
    matches: List[str] = []
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str):
            continue
        text = str(item.get("text", "")).upper().replace(" ", "")
        has_cet6 = "六级" in text or "CET-6" in text or "CET6" in text
        has_cet4 = "四级" in text or "CET-4" in text or "CET4" in text
        if (wants_cet6 and has_cet6) or (
            wants_cet4 and (has_cet4 or has_cet6)
        ):
            matches.append(f"resume.{item['evidence_id']}")
    return matches


def _education_status(requirement: str, profile: CareerProfile) -> Optional[str]:
    required_level = next(
        (level for level in ("博士", "硕士", "本科", "专科") if level in requirement),
        None,
    )
    if required_level is None:
        return None
    # “本科三年级以上”描述的是年级，当前画像没有该字段，不能靠毕业年份反推。
    if "年级" in requirement:
        return "unknown"
    actual_rank = EDUCATION_RANK.get(profile.education_level)
    required_rank = EDUCATION_RANK[required_level]
    if actual_rank is None:
        return "unknown"
    return "met" if actual_rank >= required_rank else "not_met"


def _graduation_status(requirement: str, profile: CareerProfile) -> Optional[str]:
    years = [int(value) for value in re.findall(r"20\d{2}", requirement)]
    if not years:
        return None
    try:
        candidate_year = int(profile.graduation_cohort)
    except (TypeError, ValueError):
        return "unknown"
    if len(years) >= 2 and (
        "至" in requirement or "到" in requirement or "-" in requirement
    ):
        return "met" if min(years) <= candidate_year <= max(years) else "not_met"
    required_year = years[0]
    if "以后" in requirement or "及以后" in requirement or "或以后" in requirement:
        return "met" if candidate_year >= required_year else "not_met"
    return "met" if candidate_year == required_year else "not_met"


def _schedule_status(requirement: str, profile: CareerProfile) -> Optional[str]:
    statuses: List[str] = []
    day_match = re.search(r"每周\s*(?:至少)?\s*(\d)\s*天", requirement)
    if day_match:
        required_days = int(day_match.group(1))
        if profile.internship_days_per_week <= 0:
            statuses.append("unknown")
        else:
            statuses.append(
                "met" if profile.internship_days_per_week >= required_days else "not_met"
            )

    duration_match = re.search(r"(?:至少\s*)?(\d+)\s*个月以上", requirement)
    range_match = re.search(
        r"(?:连续\s*)?(\d+)\s*(?:至|到|-)\s*(\d+)\s*个月", requirement
    )
    minimum_months = int(duration_match.group(1)) if duration_match else None
    if range_match:
        minimum_months = int(range_match.group(1))
    if minimum_months is not None:
        if profile.internship_duration_months_min <= 0:
            statuses.append("unknown")
        else:
            statuses.append(
                "met"
                if profile.internship_duration_months_min >= minimum_months
                else "not_met"
            )
    if not statuses:
        return None
    if "not_met" in statuses:
        return "not_met"
    if "unknown" in statuses:
        return "unknown"
    return "met"


def build_validated_hard_requirements(
    profile: CareerProfile,
    job: Dict[str, object],
    resume_payload: Dict[str, object],
) -> List[Dict[str, object]]:
    """Classify only objective hard gates before the model sees the prompt."""
    requirements = job.get("requirements", [])
    if not isinstance(requirements, list):
        return []
    hard_requirements: List[Dict[str, object]] = []
    has_graduation_gate = False
    for index, raw_requirement in enumerate(requirements):
        if not isinstance(raw_requirement, str):
            continue
        requirement = raw_requirement.strip()
        if not requirement or "优先" in requirement:
            continue

        education_status = _education_status(requirement, profile)
        graduation_status = _graduation_status(requirement, profile)
        schedule_status = _schedule_status(requirement, profile)
        is_certificate = bool(CERTIFICATE_PATTERN.search(requirement))
        is_hard_gate = any(
            status is not None
            for status in (education_status, graduation_status, schedule_status)
        ) or is_certificate
        if not is_hard_gate:
            continue

        refs = [f"job.requirements[{index}]"]
        statuses = [
            status
            for status in (education_status, graduation_status, schedule_status)
            if status is not None
        ]
        if education_status is not None:
            refs.append("profile.education_level")
        if graduation_status is not None:
            refs.append("profile.graduation_cohort")
            has_graduation_gate = True
        if schedule_status is not None:
            if re.search(r"每周.{0,8}\d\s*天", requirement):
                refs.append("profile.internship_days_per_week")
            if re.search(r"个月", requirement):
                refs.append("profile.internship_duration_months_min")
        if is_certificate:
            certificate_refs = _resume_refs_for_certificate(requirement, resume_payload)
            refs.extend(certificate_refs)
            statuses.append("met" if certificate_refs else "unknown")

        if "not_met" in statuses:
            status = "not_met"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "met"
        hard_requirements.append(
            {"requirement": requirement, "status": status, "evidence_refs": refs}
        )

    cohort = str(job.get("graduation_cohort", "unspecified"))
    if not has_graduation_gate and cohort not in {"", "unknown", "unspecified"}:
        if cohort == "2026_or_later":
            requirement = "2026届及以后毕业"
        elif re.fullmatch(r"20\d{2}", cohort):
            requirement = f"{cohort}届毕业"
        else:
            requirement = f"毕业时间：{cohort}"
        status = _graduation_status(requirement, profile) or "unknown"
        hard_requirements.append(
            {
                "requirement": requirement,
                "status": status,
                "evidence_refs": ["job.graduation_cohort", "profile.graduation_cohort"],
            }
        )
    return hard_requirements


def _normalize_requirement_statuses(raw: Dict[str, object]) -> None:
    """Normalize harmless model enum aliases without changing evidence or claims."""
    items = raw.get("requirement_matches")
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        if isinstance(status, str) and status in REQUIREMENT_STATUS_ALIASES:
            item["status"] = REQUIREMENT_STATUS_ALIASES[status]


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
        "validated_hard_requirements": build_validated_hard_requirements(
            profile, job, resume_payload
        ),
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
    validated_hard_requirements = build_validated_hard_requirements(
        profile, job, resume_payload
    )
    current_prompt = base_prompt
    last_error: Optional[ValueError] = None
    for attempt in range(3):
        raw = deepcopy(client.generate_json(SYSTEM_PROMPT, current_prompt))
        # Hard gates are objective program output, not a language-model classification task.
        raw["hard_requirements"] = deepcopy(validated_hard_requirements)
        _normalize_requirement_statuses(raw)
        if any(item["status"] == "not_met" for item in validated_hard_requirements):
            raw["decision"] = "not_eligible_now"
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
