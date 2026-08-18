from __future__ import annotations

import copy
from typing import Dict, List, Union

from .models import CareerProfile
from .resume_matcher import validate_match


PathPart = Union[str, int]


def _set_path(document: object, path: List[PathPart], value: object) -> None:
    if not path:
        raise ValueError("评测 mutation.path 不能为空")
    current = document
    for part in path[:-1]:
        if isinstance(part, int):
            if not isinstance(current, list) or not 0 <= part < len(current):
                raise ValueError(f"评测 mutation.path 数组位置无效：{part}")
            current = current[part]
        else:
            if not isinstance(current, dict) or part not in current:
                raise ValueError(f"评测 mutation.path 字段不存在：{part}")
            current = current[part]

    final = path[-1]
    if isinstance(final, int):
        if not isinstance(current, list) or not 0 <= final < len(current):
            raise ValueError(f"评测 mutation.path 数组位置无效：{final}")
        current[final] = value
    else:
        if not isinstance(current, dict) or final not in current:
            raise ValueError(f"评测 mutation.path 字段不存在：{final}")
        current[final] = value


def run_evaluation(
    cases: List[Dict[str, object]],
    base_match: Dict[str, object],
    profile: CareerProfile,
    job: Dict[str, object],
    resume_payload: Dict[str, object],
) -> Dict[str, object]:
    results: List[Dict[str, object]] = []

    for case in cases:
        candidate = copy.deepcopy(base_match)
        mutation = case.get("set")
        if mutation is not None:
            if not isinstance(mutation, dict):
                raise ValueError(f"评测 {case.get('id')} 的 set 必须是对象")
            path = mutation.get("path")
            if not isinstance(path, list) or not all(isinstance(part, (str, int)) for part in path):
                raise ValueError(f"评测 {case.get('id')} 的 set.path 不合法")
            _set_path(candidate, path, mutation.get("value"))

        actual = "accept"
        error = ""
        try:
            validate_match(candidate, profile, job, resume_payload)
        except ValueError as exc:
            actual = "reject"
            error = str(exc)

        expected = case.get("expected")
        expected_error = str(case.get("error_contains", ""))
        passed = actual == expected and (not expected_error or expected_error in error)
        results.append(
            {
                "id": case.get("id"),
                "description": case.get("description"),
                "expected": expected,
                "actual": actual,
                "passed": passed,
                "error": error,
            }
        )

    passed_count = sum(1 for result in results if result["passed"])
    return {
        "case_count": len(results),
        "passed_count": passed_count,
        "failed_count": len(results) - passed_count,
        "pass_rate": passed_count / len(results) if results else 0.0,
        "results": results,
    }


def render_evaluation_summary(report: Dict[str, object]) -> str:
    lines = [
        "# CareerPilot 评测结果",
        "",
        f"案例数：{report['case_count']}",
        f"通过：{report['passed_count']}",
        f"失败：{report['failed_count']}",
        f"通过率：{report['pass_rate']:.0%}",
        "",
    ]
    for result in report["results"]:
        marker = "PASS" if result["passed"] else "FAIL"
        lines.append(f"- [{marker}] {result['id']}：{result['description']}")
        if not result["passed"]:
            lines.append(
                f"  预期 {result['expected']}，实际 {result['actual']}，错误：{result['error']}"
            )
    return "\n".join(lines) + "\n"
