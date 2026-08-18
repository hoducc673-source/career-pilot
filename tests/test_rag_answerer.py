import unittest

from career_pilot.rag_answerer import answer_with_model, validate_rag_answer
from career_pilot.rag_index import KnowledgeChunk, SearchResult


def search_results():
    return [
        SearchResult(
            chunk=KnowledgeChunk(
                chunk_id="K123456789A",
                source="docs/JD_SCHEMA.md",
                heading="硬门槛判定规则",
                text="最低学历和明确毕业时间属于硬门槛。",
            ),
            score=10.0,
            matched_terms=("硬门", "门槛"),
        )
    ]


class SequenceClient:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = 0

    def generate_json(self, system_prompt, user_prompt):
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return next(self.outputs)


class RagAnswererTests(unittest.TestCase):
    def test_accepts_answer_with_retrieved_citation(self):
        result = validate_rag_answer(
            {
                "answer": "最低学历属于硬门槛。[K123456789A]",
                "citations": ["K123456789A"],
                "insufficient_evidence": False,
            },
            search_results(),
        )
        self.assertFalse(result["insufficient_evidence"])

    def test_rejects_unretrieved_citation(self):
        with self.assertRaisesRegex(ValueError, "未检索到"):
            validate_rag_answer(
                {
                    "answer": "这是答案。[KFFFFFFFFFF]",
                    "citations": ["KFFFFFFFFFF"],
                    "insufficient_evidence": False,
                },
                search_results(),
            )

    def test_rejects_citation_missing_from_answer(self):
        with self.assertRaisesRegex(ValueError, "不一致"):
            validate_rag_answer(
                {
                    "answer": "最低学历属于硬门槛。",
                    "citations": ["K123456789A"],
                    "insufficient_evidence": False,
                },
                search_results(),
            )

    def test_returns_without_api_when_retrieval_is_empty(self):
        client = SequenceClient([])
        result = answer_with_model("不存在的问题", [], client)
        self.assertTrue(result["insufficient_evidence"])
        self.assertEqual(client.calls, 0)

    def test_repairs_invalid_citation_once(self):
        invalid = {
            "answer": "错误引用。[KFFFFFFFFFF]",
            "citations": ["KFFFFFFFFFF"],
            "insufficient_evidence": False,
        }
        valid = {
            "answer": "最低学历属于硬门槛。[K123456789A]",
            "citations": ["K123456789A"],
            "insufficient_evidence": False,
        }
        client = SequenceClient([invalid, valid])
        result = answer_with_model("什么是硬门槛？", search_results(), client)
        self.assertEqual(client.calls, 2)
        self.assertEqual(result["citations"], ["K123456789A"])
        self.assertIn("上一次输出未通过", client.user_prompt)


if __name__ == "__main__":
    unittest.main()
