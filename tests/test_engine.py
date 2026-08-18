import unittest

from career_pilot.engine import explore
from career_pilot.models import CareerProfile


class ExploreTests(unittest.TestCase):
    def test_returns_requested_number_sorted_by_score(self):
        profile = CareerProfile.from_dict(
            {
                "major": "金融学",
                "scores": {
                    "analysis": 5,
                    "communication": 3,
                    "detail": 4,
                    "coding": 5,
                    "research": 4,
                    "sales": 1,
                    "uncertainty": 3,
                },
            }
        )
        results = explore(profile, limit=3)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].name, "商业分析 / 数据分析")
        self.assertGreaterEqual(results[0].score, results[1].score)
        self.assertTrue(all(result.reasons for result in results))
        self.assertTrue(all(result.experiment for result in results))

    def test_neutral_score_is_not_presented_as_supporting_evidence(self):
        profile = CareerProfile.from_dict(
            {
                "major": "金融学",
                "scores": {
                    "analysis": 3,
                    "communication": 4,
                    "detail": 3,
                    "coding": 5,
                    "research": 3,
                    "sales": 4,
                    "uncertainty": 3,
                },
            }
        )
        business_analysis = explore(profile, limit=1)[0]
        self.assertTrue(all("3/5" not in reason for reason in business_analysis.reasons))
        self.assertTrue(any("3/5" in risk for risk in business_analysis.risks))

    def test_rejects_missing_dimension(self):
        with self.assertRaisesRegex(ValueError, "uncertainty"):
            CareerProfile.from_dict(
                {
                    "major": "金融学",
                    "scores": {
                        "analysis": 3,
                        "communication": 3,
                        "detail": 3,
                        "coding": 3,
                        "research": 3,
                        "sales": 3,
                    },
                }
            )

    def test_rejects_invalid_limit(self):
        profile = CareerProfile(
            major="金融学",
            scores={
                "analysis": 3,
                "communication": 3,
                "detail": 3,
                "coding": 3,
                "research": 3,
                "sales": 3,
                "uncertainty": 3,
            },
        )
        with self.assertRaisesRegex(ValueError, "limit"):
            explore(profile, limit=0)


if __name__ == "__main__":
    unittest.main()
