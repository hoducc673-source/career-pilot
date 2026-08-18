import unittest
from pathlib import Path

from career_pilot.rag_index import (
    DEFAULT_KNOWLEDGE_FILES,
    LexicalRetriever,
    build_knowledge_base,
    chunk_markdown,
)


ROOT = Path(__file__).parents[1]


class RagIndexTests(unittest.TestCase):
    def test_chunk_ids_are_stable(self):
        content = "# 标题\n\n第一段内容。\n\n## 子标题\n\n第二段内容。"
        first = chunk_markdown("docs/test.md", content)
        second = chunk_markdown("docs/test.md", content)
        self.assertEqual([item.chunk_id for item in first], [item.chunk_id for item in second])
        self.assertEqual(first[1].heading, "标题 > 子标题")

    def test_real_knowledge_base_excludes_private_files(self):
        chunks = build_knowledge_base(ROOT)
        self.assertGreater(len(chunks), 10)
        self.assertTrue(all(chunk.source in DEFAULT_KNOWLEDGE_FILES for chunk in chunks))
        self.assertTrue(all("private" not in chunk.source for chunk in chunks))
        self.assertTrue(all(".env" not in chunk.source for chunk in chunks))

    def test_retrieves_hard_requirement_definition(self):
        chunks = build_knowledge_base(ROOT)
        results = LexicalRetriever(chunks).search("哪些内容属于硬门槛？", top_k=4)
        self.assertTrue(results)
        combined = " ".join(result.chunk.text for result in results)
        self.assertIn("硬门槛", combined)
        self.assertTrue(any(result.chunk.source.endswith("JD_SCHEMA.md") for result in results))

    def test_unknown_english_token_returns_no_results(self):
        chunks = build_knowledge_base(ROOT)
        results = LexicalRetriever(chunks).search("quantum_banana_xyz", top_k=4)
        self.assertEqual(results, [])

    def test_rejects_invalid_top_k(self):
        chunks = build_knowledge_base(ROOT)
        with self.assertRaisesRegex(ValueError, "top_k"):
            LexicalRetriever(chunks).search("硬门槛", top_k=0)


if __name__ == "__main__":
    unittest.main()
