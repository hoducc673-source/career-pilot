from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .config import load_env_file
from .deepseek_client import DeepSeekClient, DeepSeekError, DeepSeekSettings
from .jd_analyzer import analyze_with_model, demo_analysis
from .job_catalog import load_catalog
from .models import CareerProfile


def _load_profile(path: Path) -> CareerProfile:
    return CareerProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _find_job(jobs, job_id: str):
    for job in jobs:
        if job["id"] == job_id:
            return job
    raise ValueError(f"没有找到岗位：{job_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="CareerPilot JD 证据分析")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--provider", choices=("demo", "deepseek"))
    parser.add_argument("--profile", default="data/private/profile.json")
    parser.add_argument("--catalog", default="data/jobs/seed_jobs.json")
    args = parser.parse_args()

    try:
        load_env_file()
        provider = args.provider or os.environ.get("MODEL_PROVIDER", "demo")
        profile = _load_profile(Path(args.profile))
        job = _find_job(load_catalog(Path(args.catalog)), args.job_id)
        if provider == "demo":
            analysis = demo_analysis(profile, job)
        elif provider == "deepseek":
            client = DeepSeekClient(DeepSeekSettings.from_env())
            analysis = analyze_with_model(profile, job, client)
        else:
            raise ValueError(f"不支持的模型供应商：{provider}")
    except (OSError, json.JSONDecodeError, ValueError, DeepSeekError) as error:
        print(f"分析失败：{error}", file=sys.stderr)
        return 2

    print(json.dumps(analysis, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
