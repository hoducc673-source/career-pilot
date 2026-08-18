from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .models import CareerProfile, DIMENSION_LABELS, DirectionResult


@dataclass(frozen=True)
class RoleRule:
    name: str
    weights: Dict[str, int]
    experiment: str


ROLE_RULES = (
    RoleRule(
        name="金融分析 / 行业研究",
        weights={"analysis": 3, "research": 3, "detail": 2, "communication": 1, "coding": 1},
        experiment="选择一家上市公司，用公开年报做一页公司概览：业务、三项关键指标、一个机会和一个风险。",
    ),
    RoleRule(
        name="风险管理 / 合规",
        weights={"detail": 3, "analysis": 2, "research": 2, "communication": 1, "coding": 1},
        experiment="找一个公开金融风险案例，整理事件时间线、风险信号、控制措施和你的改进建议。",
    ),
    RoleRule(
        name="商业分析 / 数据分析",
        weights={"analysis": 3, "coding": 3, "research": 2, "communication": 2, "detail": 1},
        experiment="使用一份公开业务数据，用 Excel 或 Python 回答三个业务问题，并制作一页图表结论。",
    ),
    RoleRule(
        name="互联网运营",
        weights={"communication": 3, "uncertainty": 3, "analysis": 2, "sales": 2, "detail": 1},
        experiment="选择一个常用 App，拆解一个拉新或留存活动，写出目标用户、路径、指标和两个改进点。",
    ),
    RoleRule(
        name="金融科技产品 / 产品运营",
        weights={"communication": 3, "analysis": 2, "coding": 2, "uncertainty": 2, "research": 1, "detail": 1},
        experiment="选择一个支付、理财或记账产品，画出核心用户流程，并写一页需求改进说明。",
    ),
    RoleRule(
        name="银行客户经理 / 金融销售",
        weights={"sales": 3, "communication": 3, "detail": 2, "uncertainty": 1, "research": 1},
        experiment="选一个常见金融产品，准备 3 分钟客户需求访谈提纲和一页合规产品介绍，并找同学模拟。",
    ),
)


def _score(profile: CareerProfile, rule: RoleRule) -> int:
    weighted = sum(profile.scores[key] * weight for key, weight in rule.weights.items())
    maximum = sum(rule.weights.values()) * 5
    return round(weighted / maximum * 100)


def _evidence(profile: CareerProfile, rule: RoleRule) -> List[str]:
    ranked = sorted(
        (key for key in rule.weights if profile.scores[key] >= 4),
        key=lambda key: ((profile.scores[key] - 3) * rule.weights[key], rule.weights[key]),
        reverse=True,
    )
    evidence = [
        f"你对“{DIMENSION_LABELS[key]}”的自评为 {profile.scores[key]}/5，该方向对此项权重较高。"
        for key in ranked[:2]
    ]
    if not evidence:
        evidence.append("当前没有达到 4～5 分的直接自评优势，保留该方向仅用于比较。")
    return evidence


def _risks(profile: CareerProfile, rule: RoleRule) -> List[str]:
    weak = sorted(
        (key for key in rule.weights if profile.scores[key] <= 2),
        key=lambda key: rule.weights[key],
        reverse=True,
    )
    risks = [
        f"“{DIMENSION_LABELS[key]}”自评较低，但该方向需要这项能力；建议先通过小实验验证。"
        for key in weak[:2]
    ]
    if risks:
        return risks

    uncertain = sorted(
        (key for key in rule.weights if profile.scores[key] == 3),
        key=lambda key: rule.weights[key],
        reverse=True,
    )
    if uncertain:
        return [
            f"核心能力“{DIMENSION_LABELS[uncertain[0]]}”目前自评为 3/5，缺少明确证据，需要用真实任务验证。"
        ]
    return ["当前只有自评证据，需要用真实任务和岗位 JD 验证，不能直接视为适合。"]


def explore(profile: CareerProfile, limit: int = 3) -> List[DirectionResult]:
    if limit < 1:
        raise ValueError("limit 必须大于 0")
    results = [
        DirectionResult(
            name=rule.name,
            score=_score(profile, rule),
            reasons=_evidence(profile, rule),
            risks=_risks(profile, rule),
            experiment=rule.experiment,
        )
        for rule in ROLE_RULES
    ]
    return sorted(results, key=lambda item: (-item.score, item.name))[:limit]


def render_markdown(profile: CareerProfile, results: List[DirectionResult]) -> str:
    lines = [
        "# CareerPilot 离线职业探索报告",
        "",
        f"专业：{profile.major}",
        "",
        "> 说明：分数只用于候选方向排序，不是录用概率或权威职业测评。",
        "",
    ]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"## {index}. {result.name}（探索分 {result.score}/100）",
                "",
                "支持证据：",
                *[f"- {reason}" for reason in result.reasons],
                "",
                "待验证风险：",
                *[f"- {risk}" for risk in result.risks],
                "",
                f"7 天小实验：{result.experiment}",
                "",
            ]
        )
    lines.append("完成小实验后，请记录：是否愿意继续、哪里有成就感、哪里明显抗拒、结果质量如何。")
    return "\n".join(lines)
