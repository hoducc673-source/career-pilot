from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .job_catalog import load_catalog
from .models import CareerProfile
from .report_renderer import render_match_report


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="把 CareerPilot 匹配 JSON 转成可读报告")
    parser.add_argument("--match", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", default="data/private/profile.json")
    parser.add_argument("--resume-evidence", default="data/private/resume_evidence.json")
    parser.add_argument("--catalog", default="data/jobs/seed_jobs.json")
    args = parser.parse_args()

    try:
        match = _load_json(Path(args.match))
        profile = CareerProfile.from_dict(_load_json(Path(args.profile)))
        resume = _load_json(Path(args.resume_evidence))
        jobs = load_catalog(Path(args.catalog))
        job = next((item for item in jobs if item["id"] == match["job_id"]), None)
        if job is None:
            raise ValueError(f"找不到匹配结果对应的岗位：{match['job_id']}")
        report = render_match_report(match, profile, job, resume)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        print(f"可读报告已生成：{output}")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"报告生成失败：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
