from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .eval_runner import render_evaluation_summary, run_evaluation
from .job_catalog import load_catalog
from .models import CareerProfile


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 CareerPilot 离线安全评测")
    parser.add_argument("--cases", default="evals/resume_match_cases.json")
    parser.add_argument("--base", default="evals/fixtures/resume_match_base.json")
    parser.add_argument("--profile", default="evals/fixtures/eval_profile.json")
    parser.add_argument("--resume", default="evals/fixtures/eval_resume_evidence.json")
    parser.add_argument("--catalog", default="data/jobs/seed_jobs.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        cases = _load_json(Path(args.cases))
        base = _load_json(Path(args.base))
        profile = CareerProfile.from_dict(_load_json(Path(args.profile)))
        resume = _load_json(Path(args.resume))
        jobs = load_catalog(Path(args.catalog))
        job = next((item for item in jobs if item["id"] == base["job_id"]), None)
        if job is None:
            raise ValueError(f"评测基线岗位不存在：{base['job_id']}")
        report = run_evaluation(cases, base, profile, job, resume)
        summary = render_evaluation_summary(report)
        print(summary, end="")
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"机器可读结果：{output}")
        return 0 if report["failed_count"] == 0 else 1
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        print(f"评测运行失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
