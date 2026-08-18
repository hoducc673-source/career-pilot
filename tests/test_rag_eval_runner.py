import json
import unittest
from pathlib import Path

from career_pilot.rag_eval_runner import (
    render_rag_eval_summary,
    run_rag_retrieval_evaluation,
)
from career_pilot.rag_index import build_knowledge_base


ROOT = Path(__file__).parents[1]


class RagEvalRunnerTests(unittest.TestCase):
    def test_public_rag_retrieval_evaluation_passes(self):
        cases = json.loads((ROOT / "evals/rag_retrieval_cases.json").read_text(encoding="utf-8"))
        chunks = build_knowledge_base(ROOT)
        report = run_rag_retrieval_evaluation(cases, chunks)
        summary = render_rag_eval_summary(report)

        self.assertGreaterEqual(report["case_count"], 10)
        self.assertEqual(report["failed_count"], 0)
        self.assertEqual(report["pass_rate"], 1.0)
        self.assertIn("通过率：100%", summary)


if __name__ == "__main__":
    unittest.main()
