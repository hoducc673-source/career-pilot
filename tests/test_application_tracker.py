from __future__ import annotations

import unittest
from datetime import date

from career_pilot.application_tracker import (
    application_from_job,
    applications_from_csv,
    applications_to_csv,
    create_application,
    find_duplicate,
    summarize_applications,
    upsert_application,
)


class ApplicationTrackerTests(unittest.TestCase):
    def test_create_update_and_duplicate_detection(self):
        record = create_application(
            company="海尔",
            title="产品运营",
            city="青岛",
            deadline="2026-09-01",
        )
        self.assertEqual(record["status"], "saved")
        self.assertEqual(find_duplicate([record], record), record["id"])

        updated = {**record, "status": "applied", "next_action": "准备一面"}
        records = upsert_application([record], updated)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "applied")
        self.assertEqual(records[0]["created_at"], record["created_at"])

    def test_builds_record_from_job(self):
        record = application_from_job(
            {
                "company": "小红书",
                "title": "产品实习生",
                "cities": ["北京", "上海"],
                "source_url": "https://example.com/job",
            }
        )
        self.assertEqual(record["city"], "北京、上海")
        self.assertIn("定制简历", record["next_action"])

    def test_csv_round_trip_and_formula_neutralization(self):
        record = create_application(
            company="=HYPERLINK(\"https://bad.example\")",
            title="数据分析师",
            status="已投递",
            notes="跟进中",
        )
        payload = applications_to_csv([record])
        self.assertIn("'=HYPERLINK", payload)

        safe_record = create_application(company="海尔", title="数据分析师", status="applied")
        restored = applications_from_csv(applications_to_csv([safe_record]).encode("utf-8"))
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["company"], "海尔")
        self.assertEqual(restored[0]["status"], "applied")

    def test_summarizes_deadlines_and_pipeline(self):
        records = [
            create_application(company="A", title="A1", status="applied", deadline="2026-08-17"),
            create_application(company="B", title="B1", status="interview", deadline="2026-08-22"),
            create_application(company="C", title="C1", status="offer", deadline="2026-08-15"),
        ]
        summary = summarize_applications(records, today=date(2026, 8, 18))
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["due_soon"], 1)
        self.assertEqual(summary["interview"], 1)
        self.assertEqual(summary["offer"], 1)

    def test_rejects_invalid_csv_and_url(self):
        with self.assertRaisesRegex(ValueError, "缺少字段"):
            applications_from_csv(b"company,title\nA,B\n")
        with self.assertRaisesRegex(ValueError, "http"):
            create_application(company="A", title="B", source_url="example.com")


if __name__ == "__main__":
    unittest.main()
