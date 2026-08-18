from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .deepseek_client import DeepSeekClient, DeepSeekError, DeepSeekSettings
from .rag_answerer import answer_with_model
from .rag_index import LexicalRetriever, build_knowledge_base, render_search_results


def main() -> int:
    parser = argparse.ArgumentParser(description="CareerPilot RAG 第一阶段：本地知识检索")
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--root", default=".")
    parser.add_argument("--provider", choices=("retrieve", "deepseek"), default="retrieve")
    parser.add_argument("--output")
    args = parser.parse_args()

    try:
        chunks = build_knowledge_base(Path(args.root))
        results = LexicalRetriever(chunks).search(args.question, top_k=args.top_k)
        print(f"知识库片段数：{len(chunks)}")
        if args.provider == "retrieve":
            print(render_search_results(args.question, results), end="")
        else:
            client = DeepSeekClient(DeepSeekSettings.from_env())
            answer = answer_with_model(args.question, results, client)
            payload = {
                "question": args.question,
                "retrieved_chunks": [
                    {
                        "chunk_id": result.chunk.chunk_id,
                        "source": result.chunk.source,
                        "heading": result.chunk.heading,
                        "score": round(result.score, 6),
                    }
                    for result in results
                ],
                **answer,
            }
            rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            print(rendered, end="")
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(f"RAG 结果已保存：{output}")
    except (OSError, UnicodeError, ValueError, DeepSeekError) as error:
        print(f"检索失败：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
