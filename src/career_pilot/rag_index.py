from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


DEFAULT_KNOWLEDGE_FILES = (
    "docs/PROJECT_BRIEF.md",
    "docs/CAREERPILOT_PRD_V0.1.md",
    "docs/JD_SCHEMA.md",
    "docs/ROADMAP.md",
    "docs/RAG_MINI_PROJECT_PLAN.md",
    "README.md",
)

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
ENGLISH_PATTERN = re.compile(r"[a-z0-9_]+")
CHINESE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    source: str
    heading: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    chunk: KnowledgeChunk
    score: float
    matched_terms: Tuple[str, ...]


def _stable_chunk_id(source: str, heading: str, text: str) -> str:
    raw = f"{source}\n{heading}\n{text}".encode("utf-8")
    return "K" + hashlib.sha256(raw).hexdigest()[:10].upper()


def _split_long_text(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = [part.strip() for part in re.split(r"(?<=[。！？；.!?;])", text) if part.strip()]
    pieces: List[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = ""
        if len(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(
                sentence[start : start + max_chars]
                for start in range(0, len(sentence), max_chars)
            )
        else:
            current = sentence if not current else current + " " + sentence
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(source: str, content: str, max_chars: int = 700) -> List[KnowledgeChunk]:
    if max_chars < 100:
        raise ValueError("max_chars 不能小于 100")

    chunks: List[KnowledgeChunk] = []
    heading_stack: List[str] = []
    block_lines: List[str] = []

    def current_heading() -> str:
        return " > ".join(heading_stack) if heading_stack else "文档说明"

    def flush() -> None:
        if not block_lines:
            return
        text = re.sub(r"\s+", " ", " ".join(block_lines)).strip()
        block_lines.clear()
        if not text:
            return
        heading = current_heading()
        for piece in _split_long_text(text, max_chars=max_chars):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=_stable_chunk_id(source, heading, piece),
                    source=source,
                    heading=heading,
                    text=piece,
                )
            )

    in_code_fence = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        heading_match = HEADING_PATTERN.match(line) if not in_code_fence else None
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(title)
        elif not line:
            continue
        else:
            block_lines.append(line)
    flush()
    return chunks


def build_knowledge_base(root: Path) -> List[KnowledgeChunk]:
    chunks: List[KnowledgeChunk] = []
    for relative in DEFAULT_KNOWLEDGE_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"知识库文件不存在：{relative}")
        chunks.extend(chunk_markdown(relative, path.read_text(encoding="utf-8")))
    if not chunks:
        raise ValueError("知识库没有可用片段")
    if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
        raise ValueError("知识片段编号发生碰撞")
    return chunks


def tokenize(text: str) -> List[str]:
    lowered = text.lower()
    terms = ENGLISH_PATTERN.findall(lowered)
    for sequence in CHINESE_PATTERN.findall(lowered):
        if len(sequence) <= 8:
            terms.append(sequence)
        if len(sequence) == 1:
            terms.append(sequence)
        else:
            terms.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return terms


class LexicalRetriever:
    def __init__(self, chunks: Sequence[KnowledgeChunk]):
        if not chunks:
            raise ValueError("检索器至少需要一个知识片段")
        self.chunks = list(chunks)
        self.term_counts: List[Counter[str]] = [
            Counter(tokenize(chunk.heading + " " + chunk.text)) for chunk in chunks
        ]
        document_frequency: Counter[str] = Counter()
        for counts in self.term_counts:
            document_frequency.update(counts.keys())
        total = len(chunks)
        self.idf: Dict[str, float] = {
            term: math.log((total + 1) / (frequency + 1)) + 1.0
            for term, frequency in document_frequency.items()
        }

    def search(self, question: str, top_k: int = 4) -> List[SearchResult]:
        if not question.strip():
            raise ValueError("问题不能为空")
        if top_k < 1:
            raise ValueError("top_k 必须大于等于 1")

        query_terms = set(tokenize(question))
        normalized_question = re.sub(r"\s+", "", question.lower())
        scored: List[SearchResult] = []
        for chunk, counts in zip(self.chunks, self.term_counts):
            matched: Set[str] = query_terms & counts.keys()
            if not matched:
                continue
            weighted_overlap = sum(
                self.idf.get(term, 0.0) * (1.0 + math.log(counts[term])) for term in matched
            )
            length_penalty = math.sqrt(max(1.0, sum(counts.values()) / 30.0))
            score = weighted_overlap / length_penalty
            compact_text = re.sub(r"\s+", "", chunk.text.lower())
            if normalized_question and normalized_question in compact_text:
                score += 4.0
            heading_terms = set(tokenize(chunk.heading))
            score += 0.6 * len(query_terms & heading_terms)
            scored.append(
                SearchResult(
                    chunk=chunk,
                    score=score,
                    matched_terms=tuple(sorted(matched)),
                )
            )
        scored.sort(key=lambda result: (-result.score, result.chunk.chunk_id))
        return scored[:top_k]


def render_search_results(question: str, results: Iterable[SearchResult]) -> str:
    results = list(results)
    lines = [f"问题：{question}", f"检索结果：{len(results)} 条", ""]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. [{result.chunk.chunk_id}] {result.chunk.source}｜{result.chunk.heading}",
                f"   得分：{result.score:.3f}｜命中词：{', '.join(result.matched_terms)}",
                f"   原文：{result.chunk.text}",
                "",
            ]
        )
    if not results:
        lines.append("知识库中没有找到相关片段。")
    return "\n".join(lines).rstrip() + "\n"
