import unittest
from datetime import date

from career_pilot.usage_guard import DailyUsageGuard


class DailyUsageGuardTests(unittest.TestCase):
    def test_blocks_after_daily_limit(self):
        guard = DailyUsageGuard(2)
        day = date(2026, 8, 18)
        first = guard.reserve(day)
        second = guard.reserve(day)
        blocked = guard.reserve(day)
        self.assertTrue(first.allowed)
        self.assertEqual(first.remaining, 1)
        self.assertTrue(second.allowed)
        self.assertEqual(second.remaining, 0)
        self.assertFalse(blocked.allowed)
        self.assertEqual(blocked.remaining, 0)

    def test_resets_on_new_utc_day(self):
        guard = DailyUsageGuard(1)
        self.assertTrue(guard.reserve(date(2026, 8, 18)).allowed)
        self.assertFalse(guard.reserve(date(2026, 8, 18)).allowed)
        next_day = guard.reserve(date(2026, 8, 19))
        self.assertTrue(next_day.allowed)
        self.assertEqual(next_day.remaining, 0)

    def test_rejects_non_positive_limit(self):
        with self.assertRaisesRegex(ValueError, "大于等于 1"):
            DailyUsageGuard(0)


if __name__ == "__main__":
    unittest.main()
