from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, Iterable, List, Optional, Set

from .jd_analyzer import profile_to_dict
from .models import CareerProfile


DECISION_LABELS = {
    "likely_apply": "建议申请",
    "stretch": "拉伸匹配：可以尝试，但需要补强",
    "not_eligible_now": "当前不建议申请：存在未满足的硬门槛",
}

CONFIDENCE_LABELS = {"low": "低", "medium": "中", "high": "高"}
HARD_STATUS_LABELS = {"met": "满足", "not_met": "不满足", "unknown": "待确认"}
MATCH_STATUS_LABELS = {"matched": "匹配", "partial": "部分匹配", "unknown": "证据不足"}


def _refs(items: Iterable[Dict[str, object]]) -> Set[str]:
    result: Set[str] = set()
    for item in items:
        refs = item.get("evidence_refs", item.get("current_evidence_refs", []))
        if isinstance(refs, list):
            result.update(ref for ref in refs if isinstance(ref, str))
    return result


def _format_refs(refs: object) -> str:
    if not isinstance(refs, list):
        return "无"
    return "、".join(f"`{ref}`" for ref in refs)


def _format_value(value: object) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _resolve_value(source: Dict[str, object], key: str) -> object:
    indexed = re.fullmatch(r"(.+)\[(\d+)\]", key)
    if not indexed:
        return source.get(key, "[无法解析]")
    field, raw_index = indexed.groups()
    value = source.get(field)
    index = int(raw_index)
    if not isinstance(value, list) or index >= len(value):
        return "[无法解析]"
    return value[index]


def render_match_report(
    match: Dict[str, object],
    profile: CareerProfile,
    job: Dict[str, object],
    resume_payload: Dict[str, object],
    generated_on: Optional[str] = None,
) -> str:
    generated_on = generated_on or date.today().isoformat()
    decision = DECISION_LABELS.get(str(match["decision"]), str(match["decision"]))
    confidence = CONFIDENCE_LABELS.get(str(match["confidence"]), str(match["confidence"]))

    lines: List[str] = [
        f"# {job['company']}｜{job['title']} 匹配报告",
        "",
        f"生成日期：{generated_on}  ",
        f"工作城市：{_format_value(job['cities'])}  ",
        f"结论：**{decision}**  ",
        f"置信度：{confidence}",
        "",
        "## 一句话结论",
        "",
        str(match["summary"]),
        "",
        "## 硬门槛",
        "",
        "| 要求 | 判断 | 证据 |",
        "|---|---|---|",
    ]

    for item in match["hard_requirements"]:
        status = HARD_STATUS_LABELS.get(str(item["status"]), str(item["status"]))
        lines.append(f"| {item['requirement']} | {status} | {_format_refs(item['evidence_refs'])} |")

    lines.extend(["", "## 岗位要求匹配", ""])
    for item in match["requirement_matches"]:
        status = MATCH_STATUS_LABELS.get(str(item["status"]), str(item["status"]))
        lines.extend(
            [
                f"### {item['requirement']}｜{status}",
                "",
                str(item["rationale"]),
                "",
                f"证据：{_format_refs(item['evidence_refs'])}",
                "",
            ]
        )

    lines.extend(["## 可用于申请的优势", ""])
    for item in match["strengths"]:
        lines.append(f"- {item['claim']}（证据：{_format_refs(item['evidence_refs'])}）")

    lines.extend(["", "## 证据缺口与行动", ""])
    for index, item in enumerate(match["gaps"], start=1):
        lines.extend(
            [
                f"{index}. **缺口：**{item['gap']}",
                f"   **行动：**{item['action']}",
                f"   **证据：**{_format_refs(item['evidence_refs'])}",
                "",
            ]
        )

    lines.extend(
        [
            "## 简历表达建议",
            "",
            "> 以下建议必须经过本人事实确认，不可直接写入正式简历，也不得补造经历或数字。",
            "",
        ]
    )
    for index, item in enumerate(match["resume_edits"], start=1):
        lines.extend(
            [
                f"{index}. **调整位置：**{item['target']}",
                f"   **建议：**{item['suggestion']}",
                f"   **现有证据：**{_format_refs(item['current_evidence_refs'])}",
                "",
            ]
        )

    lines.extend(["## 面试准备题", ""])
    for index, question in enumerate(match["interview_questions"], start=1):
        lines.append(f"{index}. {question}")

    lines.extend(["", "## 下一步清单", ""])
    for action in match["next_actions"]:
        lines.append(f"- [ ] {action}")

    used_refs = set()
    for key in ("hard_requirements", "requirement_matches", "strengths", "gaps"):
        used_refs.update(_refs(match[key]))
    used_refs.update(_refs(match["resume_edits"]))

    resume_by_ref = {
        f"resume.{item['evidence_id']}": str(item.get("text", ""))
        for item in resume_payload.get("evidence", [])
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    }
    profile_values = profile_to_dict(profile)

    lines.extend(["", "## 证据索引", "", "### 简历证据", ""])
    for ref in sorted(ref for ref in used_refs if ref.startswith("resume.")):
        lines.append(f"- `{ref}`：{resume_by_ref.get(ref, '[无法解析]')}")

    lines.extend(["", "### 画像与岗位证据", ""])
    for ref in sorted(ref for ref in used_refs if ref.startswith(("profile.", "job."))):
        namespace, key = ref.split(".", 1)
        source = profile_values if namespace == "profile" else job
        lines.append(f"- `{ref}`：{_format_value(_resolve_value(source, key))}")

    lines.extend(
        [
            "",
            "---",
            "",
            "本报告用于辅助决策，不代表录用概率。所有简历修改和投递行为均需本人确认。",
            "",
        ]
    )
    return "\n".join(lines)
