from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import explore, render_markdown
from .models import CareerProfile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CareerPilot 离线职业探索工具")
    parser.add_argument("--profile", required=True, help="职业偏好问卷 JSON 路径")
    parser.add_argument("--limit", type=int, default=3, help="输出候选方向数量")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        profile_path = Path(args.profile)
        raw = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = CareerProfile.from_dict(raw)
        results = explore(profile, limit=args.limit)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"输入错误：{error}", file=sys.stderr)
        return 2

    print(render_markdown(profile, results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
