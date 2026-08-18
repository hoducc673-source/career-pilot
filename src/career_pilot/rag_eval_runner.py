from __future__ import annotations

from typing import Dict, List, Sequence

from .rag_index import KnowledgeChunk, LexicalRetriever, SearchResult


def _evaluate_case(case: Dict[str, object], results: Sequence[SearchResult]) -> List[str]:
    failures: List[str] = []
    if case.get("expected_no_results") is True:
        if results:
            failures.append(f"预期无结果，实际返回 {len(results)} 条")
        return failures

    if not results:
        return ["预期有检索结果，实际为空"]

    top_source = case.get("expected_top_source")
    if isinstance(top_source, str) and results[0].chunk.source != top_source:
        failures.append(
            f"首条来源应为 {top_source}，实际为 {results[0].chunk.source}"
        )

    any_source = case.get("expected_any_source")
    if isinstance(any_source, str) and not any(
        result.chunk.source == any_source for result in results
    ):
        failures.append(f"结果中缺少来源 {any_source}")

    text_contains = case.get("expected_text_contains")
    combined_text = " ".join(
        result.chunk.heading + " " + result.chunk.text for result in results
    )
    if isinstance(text_contains, str) and text_contains not in combined_text:
        failures.append(f"结果原文中缺少关键词：{text_contains}")

    forbidden = case.get("forbidden_source_contains", [])
    if isinstance(forbidden, list):
        for marker in forbidden:
            if isinstance(marker, str) and any(
                marker in result.chunk.source for result in results
            ):
                failures.append(f"检索结果包含禁止来源标记：{marker}")
    return failures


def run_rag_retrieval_evaluation(
    cases: List[Dict[str, object]],
    chunks: Sequence[KnowledgeChunk],
    top_k: int = 4,
) -> Dict[str, object]:
    retriever = LexicalRetriever(chunks)
    results_report: List[Dict[str, object]] = []
    for case in cases:
        question = case.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"RAG 评测 {case.get('id')} 缺少有效问题")
        results = retriever.search(question, top_k=top_k)
        failures = _evaluate_case(case, results)
        results_report.append(
            {
                "id": case.get("id"),
                "question": question,
                "passed": not failures,
                "failures": failures,
                "retrieved": [
                    {
                        "chunk_id": result.chunk.chunk_id,
                        "source": result.chunk.source,
                        "heading": result.chunk.heading,
                        "score": round(result.score, 6),
                    }
                    for result in results
                ],
            }
        )

    passed_count = sum(1 for item in results_report if item["passed"])
    return {
        "case_count": len(results_report),
        "passed_count": passed_count,
        "failed_count": len(results_report) - passed_count,
        "pass_rate": passed_count / len(results_report) if results_report else 0.0,
        "knowledge_chunk_count": len(chunks),
        "results": results_report,
    }


def render_rag_eval_summary(report: Dict[str, object]) -> str:
    lines = [
        "# CareerPilot RAG 检索评测",
        "",
        f"知识片段：{report['knowledge_chunk_count']}",
        f"案例数：{report['case_count']}",
        f"通过：{report['passed_count']}",
        f"失败：{report['failed_count']}",
        f"通过率：{report['pass_rate']:.0%}",
        "",
    ]
    for item in report["results"]:
        marker = "PASS" if item["passed"] else "FAIL"
        lines.append(f"- [{marker}] {item['id']}：{item['question']}")
        for failure in item["failures"]:
            lines.append(f"  - {failure}")
    return "\n".join(lines) + "\n"
