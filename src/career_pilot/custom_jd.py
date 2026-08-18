from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Sequence


MAX_JD_CHARS = 15_000
MIN_JD_CHARS = 40

KNOWN_CITIES = (
    "青岛",
    "上海",
    "北京",
    "杭州",
    "深圳",
    "广州",
    "南京",
    "苏州",
    "成都",
    "武汉",
    "天津",
    "西安",
    "厦门",
    "宁波",
    "济南",
)

SECTION_LABELS = {
    "responsibilities": ("岗位职责", "职位职责", "工作职责", "工作内容", "职责描述"),
    "requirements": ("任职要求", "岗位要求", "职位要求", "任职资格", "申请条件", "任职条件"),
}

SUSPICIOUS_INSTRUCTION = re.compile(
    r"忽略.{0,12}(?:之前|上述|系统)|(?:system|assistant|developer)\s*(?:prompt|:|：)|"
    r"你是\s*(?:chatgpt|ai|大模型)|返回\s*(?:json|密钥|提示词)",
    re.IGNORECASE,
)

REQUIREMENT_HINT = re.compile(
    r"要求|任职|资格|优先|本科|硕士|博士|毕业|届|每周|"
    r"个月|证书|资质|经验|熟悉|掌握|能力"
)

SKILL_PATTERNS = {
    "data_analysis": r"数据分析|数据挖掘|数据处理",
    "excel": r"\bexcel\b",
    "python": r"\bpython\b",
    "sql": r"\bsql\b",
    "communication": r"沟通|协作|跨部门",
    "market_research": r"市场研究|行业研究|竞品",
    "product_management": r"产品经理|产品设计|\bprd\b|需求分析",
    "operations": r"运营|增长|用户活跃",
    "finance": r"金融|证券|投资|行业研究|财务",
    "ai_literacy": r"人工智能|大模型|\bai\b|\bllm\b|\brag\b|\bagent\b",
}


@dataclass(frozen=True)
class ParsedJD:
    job: Dict[str, object]
    warnings: List[str]


def _clean_line(raw: str) -> str:
    line = raw.strip()
    line = re.sub(r"^[•·●○▪■◆◇★☆\-\u2013\u2014*]+\s*", "", line)
    line = re.sub(r"^\(?\d{1,2}\)?[.\u3001\uff09)]\s*", "", line)
    return line.strip()


def _lines(text: str) -> List[str]:
    expanded = re.sub(r"([\u3002\uff1b;])\s*(?=\d{1,2}[.\u3001\uff09)])", r"\1\n", text)
    return [line for raw in expanded.splitlines() if (line := _clean_line(raw))]


def _label_value(lines: Sequence[str], labels: Sequence[str]) -> str:
    pattern = re.compile(rf"^(?:{'|'.join(map(re.escape, labels))})\s*[:\uff1a]\s*(.+)$", re.IGNORECASE)
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ""


def _section_start(line: str) -> tuple[Optional[str], str]:
    normalized = re.sub(r"\s+", "", line)
    for section, labels in SECTION_LABELS.items():
        for label in labels:
            if normalized == label or normalized in {f"{label}:", f"{label}："}:
                return section, ""
            match = re.match(rf"^{re.escape(label)}\s*[:\uff1a]\s*(.+)$", line)
            if match:
                return section, match.group(1).strip()
    return None, line


def _infer_title(lines: Sequence[str]) -> str:
    labeled = _label_value(lines, ("岗位", "职位", "职位名称", "岗位名称"))
    if labeled:
        return labeled
    role_words = re.compile(r"经理|分析师|实习生|管培生|运营|顾问|研究员|工程师|产品")
    return next((line for line in lines[:6] if len(line) <= 36 and role_words.search(line)), "自定义岗位")


def _infer_company(lines: Sequence[str]) -> str:
    labeled = _label_value(lines, ("公司", "公司名称", "雇主", "企业"))
    if labeled:
        return labeled
    company_words = re.compile(r"公司|集团|银行|证券|基金|保险|科技")
    return next((line for line in lines[:5] if len(line) <= 40 and company_words.search(line)), "未标注公司")


def _parse_cities(text: str, lines: Sequence[str]) -> List[str]:
    labeled = _label_value(lines, ("工作地点", "工作城市", "城市", "地点"))
    haystack = labeled or text
    cities = [city for city in KNOWN_CITIES if city in haystack]
    return cities or ["地点待确认"]


def _infer_role_family(text: str, title: str) -> str:
    if re.search(r"产品经理|产品设计", title):
        return "product"
    if re.search(r"数据|分析师|行业研究", title):
        return "data_analysis"
    if re.search(r"运营|增长|内容", title):
        return "operations"
    if re.search(r"产品经理|产品设计|\bprd\b|需求分析", text, re.IGNORECASE):
        return "product"
    if re.search(r"数据分析|分析师|\bsql\b|\bpython\b|商业分析", text, re.IGNORECASE):
        return "data_analysis"
    if re.search(r"运营|增长|内容策划|用户活跃", text):
        return "operations"
    return "other"


def _education_min(requirements: Sequence[str]) -> str:
    for line in requirements:
        if "优先" in line:
            continue
        for level in ("博士", "硕士", "本科", "大专", "专科"):
            if level in line:
                return "专科" if level == "大专" else level
    return "unspecified"


def _graduation_cohort(requirements: Sequence[str]) -> str:
    for line in requirements:
        match = re.search(r"(20\d{2})\s*届", line)
        if not match:
            continue
        year = match.group(1)
        if "以后" in line or "及以后" in line:
            return f"{year}_or_later"
        return year
    return "unspecified"


def _employment_type(text: str) -> str:
    if "实习" in text:
        return "conversion_internship" if "转正" in text else "daily_internship"
    return "campus" if "校招" in text or "应届" in text else "unspecified"


def _skill_tags(text: str) -> List[str]:
    return [
        tag for tag, pattern in SKILL_PATTERNS.items()
        if re.search(pattern, text, re.IGNORECASE)
    ]


def parse_custom_jd(
    text: str,
    *,
    company: str = "",
    title: str = "",
    city: str = "",
    source_url: str = "",
) -> ParsedJD:
    normalized = text.strip()
    if len(normalized) < MIN_JD_CHARS:
        raise ValueError(f"JD 内容太短，请至少粘贴 {MIN_JD_CHARS} 个字符。")
    if len(normalized) > MAX_JD_CHARS:
        raise ValueError(f"JD 超过 {MAX_JD_CHARS} 个字符，请删除无关的公司介绍后重试。")

    source_lines = _lines(normalized)
    safe_lines: List[str] = []
    blocked = 0
    for line in source_lines:
        if SUSPICIOUS_INSTRUCTION.search(line):
            blocked += 1
            continue
        safe_lines.append(line)
    if not safe_lines:
        raise ValueError("JD 中没有可用的岗位内容。")

    responsibilities: List[str] = []
    requirements: List[str] = []
    section: Optional[str] = None
    metadata_prefix = re.compile(r"^(?:公司|公司名称|雇主|企业|岗位|职位|职位名称|岗位名称|工作地点|工作城市|城市|地点)\s*[:\uff1a]")
    for line in safe_lines:
        detected, content = _section_start(line)
        if detected:
            section = detected
            if not content:
                continue
            line = content
        elif metadata_prefix.match(line):
            continue

        target = section
        if target is None:
            target = "requirements" if REQUIREMENT_HINT.search(line) else "responsibilities"
        bucket = requirements if target == "requirements" else responsibilities
        if line not in bucket:
            bucket.append(line)

    if not requirements:
        raise ValueError("未识别到任职要求；请保留“任职要求”标题或学历、经验等条件。")
    if not responsibilities:
        responsibilities = ["原文未分出独立的岗位职责，建议人工复核。"]

    override_cities = [item.strip() for item in re.split(r"[,，/、\s]+", city) if item.strip()]
    url = source_url.strip()
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        raise ValueError("来源链接必须以 http:// 或 https:// 开头。")

    safe_text = "\n".join(safe_lines)
    resolved_company = company.strip() or _infer_company(safe_lines)
    resolved_title = title.strip() or _infer_title(safe_lines)
    resolved_cities = override_cities or _parse_cities(safe_text, safe_lines)
    identity = "\n".join((resolved_company, resolved_title, safe_text))
    job_id = "custom-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    major_policy = next((line for line in requirements if "专业" in line), "unspecified")

    warnings: List[str] = []
    if blocked:
        warnings.append(f"已忽略 {blocked} 行疑似操纵模型的指令性文本。")
    if resolved_company == "未标注公司":
        warnings.append("未识别公司名称，建议在解析前手动补充。")
    if resolved_title == "自定义岗位":
        warnings.append("未识别岗位名称，建议在解析前手动补充。")

    return ParsedJD(
        job={
            "id": job_id,
            "company": resolved_company,
            "title": resolved_title,
            "cities": resolved_cities,
            "role_family": _infer_role_family(safe_text, resolved_title),
            "employment_type": _employment_type(safe_text),
            "graduation_cohort": _graduation_cohort(requirements),
            "education_min": _education_min(requirements),
            "major_policy": major_policy,
            "preliminary_fit": "stretch",
            "fit_reason": "这是本次会话中粘贴的 JD，需结合硬门槛和简历证据进一步判断。",
            "responsibilities": responsibilities[:16],
            "requirements": requirements[:20],
            "skill_tags": _skill_tags(safe_text),
            "source_url": url,
            "source_kind": "user_pasted",
            "source_status": "session_only",
            "checked_at": date.today().isoformat(),
        },
        warnings=warnings,
    )
