from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deepseek_client import DeepSeekClient, DeepSeekError, DeepSeekSettings
from .job_catalog import load_catalog
from .models import CareerProfile
from .resume_matcher import match_with_model


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _find_job(jobs, job_id: str):
    for job in jobs:
        if job["id"] == job_id:
            return job
    raise ValueError(f"没有找到岗位：{job_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CareerPilot 简历—JD 证据匹配")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--profile", default="data/private/profile.json")
    parser.add_argument("--resume-evidence", default="data/private/resume_evidence.json")
    parser.add_argument("--catalog", default="data/jobs/seed_jobs.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        profile = CareerProfile.from_dict(_load_json(Path(args.profile)))
        resume_payload = _load_json(Path(args.resume_evidence))
        job = _find_job(load_catalog(Path(args.catalog)), args.job_id)
        client = DeepSeekClient(DeepSeekSettings.from_env())
        result = match_with_model(profile, job, resume_payload, client)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            print(f"匹配结果已保存：{output}")
        else:
            print(rendered, end="")
    except (OSError, json.JSONDecodeError, ValueError, DeepSeekError) as error:
        print(f"匹配失败：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
