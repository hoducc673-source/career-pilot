from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .job_catalog import load_catalog, render_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 CareerPilot JD 数据集")
    parser.add_argument("--catalog", default="data/jobs/seed_jobs.json")
    args = parser.parse_args()
    try:
        jobs = load_catalog(Path(args.catalog))
    except (OSError, ValueError) as error:
        print(f"数据错误：{error}", file=sys.stderr)
        return 2
    print(render_summary(jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
