from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Dict, List


REQUIRED_FIELDS = {
    "id",
    "company",
    "title",
    "cities",
    "role_family",
    "employment_type",
    "graduation_cohort",
    "education_min",
    "major_policy",
    "preliminary_fit",
    "fit_reason",
    "responsibilities",
    "requirements",
    "skill_tags",
    "source_url",
    "source_kind",
    "source_status",
    "checked_at",
}

ALLOWED_ROLE_FAMILIES = {"data_analysis", "product", "operations"}
ALLOWED_FITS = {"likely_apply", "stretch", "not_eligible_now"}


def load_catalog(path: Path) -> List[Dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("JD 数据集必须是数组")
    validate_catalog(raw)
    return raw


def validate_catalog(jobs: List[Dict[str, object]]) -> None:
    seen_ids = set()
    for index, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ValueError(f"第 {index + 1} 条岗位不是对象")
        missing = REQUIRED_FIELDS - set(job)
        if missing:
            raise ValueError(f"岗位 {index + 1} 缺少字段：{sorted(missing)}")
        if job["id"] in seen_ids:
            raise ValueError(f"岗位 id 重复：{job['id']}")
        seen_ids.add(job["id"])
        if job["role_family"] not in ALLOWED_ROLE_FAMILIES:
            raise ValueError(f"未知岗位族：{job['role_family']}")
        if job["preliminary_fit"] not in ALLOWED_FITS:
            raise ValueError(f"未知初筛结果：{job['preliminary_fit']}")
        if not isinstance(job["cities"], list) or not job["cities"]:
            raise ValueError(f"岗位 {job['id']} 的 cities 必须是非空数组")
        if not str(job["source_url"]).startswith("https://"):
            raise ValueError(f"岗位 {job['id']} 缺少 HTTPS 来源")


def render_summary(jobs: List[Dict[str, object]]) -> str:
    fit_counts = Counter(str(job["preliminary_fit"]) for job in jobs)
    city_counts = Counter(city for job in jobs for city in job["cities"])
    tag_counts = Counter(tag for job in jobs for tag in job["skill_tags"])

    lines = [
        "# JD 种子数据集摘要",
        "",
        f"岗位数：{len(jobs)}",
        "",
        "初筛：" + "，".join(f"{key}={fit_counts[key]}" for key in sorted(fit_counts)),
        "城市覆盖：" + "，".join(f"{key}={city_counts[key]}" for key in sorted(city_counts)),
        "高频技能：" + "，".join(f"{key}={count}" for key, count in tag_counts.most_common(8)),
    ]
    return "\n".join(lines)
