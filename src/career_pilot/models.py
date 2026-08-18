from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


DIMENSIONS = (
    "analysis",
    "communication",
    "detail",
    "coding",
    "research",
    "sales",
    "uncertainty",
)

DIMENSION_LABELS = {
    "analysis": "数据与逻辑分析",
    "communication": "沟通与协作",
    "detail": "细节与规范",
    "coding": "编程与工具",
    "research": "研究与信息整理",
    "sales": "客户沟通与影响",
    "uncertainty": "面对变化与不确定性",
}


@dataclass(frozen=True)
class CareerProfile:
    major: str
    scores: Dict[str, int]
    graduation_cohort: str = "unknown"
    education_level: str = "本科"
    target_cities: List[str] = field(default_factory=list)
    primary_direction: str = "unknown"
    secondary_direction: str = "unknown"
    internship_days_per_week: int = 0
    internship_duration_months_min: int = 0
    rag_experience: str = "unknown"

    @classmethod
    def from_dict(cls, raw: Dict[str, object]) -> "CareerProfile":
        major = str(raw.get("major", "")).strip()
        raw_scores = raw.get("scores")
        if not major:
            raise ValueError("major 不能为空")
        if not isinstance(raw_scores, dict):
            raise ValueError("scores 必须是一个对象")

        scores: Dict[str, int] = {}
        for dimension in DIMENSIONS:
            value = raw_scores.get(dimension)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{dimension} 必须是 1～5 的整数")
            if not 1 <= value <= 5:
                raise ValueError(f"{dimension} 必须位于 1～5")
            scores[dimension] = value
        raw_cities = raw.get("target_cities", [])
        if not isinstance(raw_cities, list) or not all(isinstance(city, str) for city in raw_cities):
            raise ValueError("target_cities 必须是字符串数组")
        days_per_week = raw.get("internship_days_per_week", 0)
        if not isinstance(days_per_week, int) or isinstance(days_per_week, bool) or not 0 <= days_per_week <= 7:
            raise ValueError("internship_days_per_week 必须是 0～7 的整数")
        duration_months = raw.get("internship_duration_months_min", 0)
        if not isinstance(duration_months, int) or isinstance(duration_months, bool) or duration_months < 0:
            raise ValueError("internship_duration_months_min 必须是非负整数")
        rag_experience = str(raw.get("rag_experience", "unknown"))
        if rag_experience not in {"unknown", "none", "learning", "project", "work"}:
            raise ValueError("rag_experience 必须是 unknown/none/learning/project/work")
        return cls(
            major=major,
            scores=scores,
            graduation_cohort=str(raw.get("graduation_cohort", "unknown")),
            education_level=str(raw.get("education_level", "本科")),
            target_cities=raw_cities,
            primary_direction=str(raw.get("primary_direction", "unknown")),
            secondary_direction=str(raw.get("secondary_direction", "unknown")),
            internship_days_per_week=days_per_week,
            internship_duration_months_min=duration_months,
            rag_experience=rag_experience,
        )


@dataclass(frozen=True)
class DirectionResult:
    name: str
    score: int
    reasons: List[str]
    risks: List[str]
    experiment: str
