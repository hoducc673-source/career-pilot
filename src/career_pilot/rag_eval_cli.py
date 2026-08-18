from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .rag_eval_runner import render_rag_eval_summary, run_rag_retrieval_evaluation
from .rag_index import build_knowledge_base


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 CareerPilot RAG 离线检索评测")
    parser.add_argument("--cases", default="evals/rag_retrieval_cases.json")
    parser.add_argument("--root", default=".")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
        if not isinstance(cases, list):
            raise ValueError("RAG 评测案例必须是数组")
        chunks = build_knowledge_base(Path(args.root))
        report = run_rag_retrieval_evaluation(cases, chunks, top_k=args.top_k)
        print(render_rag_eval_summary(report), end="")
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            print(f"机器可读结果：{output}")
        return 0 if report["failed_count"] == 0 else 1
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"RAG 评测失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
