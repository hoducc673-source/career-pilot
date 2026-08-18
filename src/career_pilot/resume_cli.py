from __future__ import annotations

import argparse
from pathlib import Path

from career_pilot.resume_parser import save_resume_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="导入脱敏 DOCX 简历并生成可引用证据")
    parser.add_argument("--resume", type=Path, required=True, help="脱敏 DOCX 简历路径")
    parser.add_argument("--output", type=Path, required=True, help="私有 JSON 输出路径")
    args = parser.parse_args()

    payload = save_resume_evidence(args.resume, args.output)
    print(f"简历导入成功：{payload['evidence_count']} 条证据")
    print(f"本地输出：{args.output}")


if __name__ == "__main__":
    main()
