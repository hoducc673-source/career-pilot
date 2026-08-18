from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
from typing import Optional


class UsageLimitError(RuntimeError):
    """Raised before a model request when the public demo budget is exhausted."""


@dataclass(frozen=True)
class UsageReservation:
    allowed: bool
    remaining: int


class DailyUsageGuard:
    """Thread-safe, in-process daily request counter for a public demo."""

    def __init__(self, daily_limit: int):
        if daily_limit < 1:
            raise ValueError("daily_limit 必须大于等于 1")
        self.daily_limit = daily_limit
        self._lock = Lock()
        self._day: Optional[date] = None
        self._used = 0

    @staticmethod
    def _today_utc() -> date:
        return datetime.now(timezone.utc).date()

    def reserve(self, current_day: Optional[date] = None) -> UsageReservation:
        day = current_day or self._today_utc()
        with self._lock:
            if self._day != day:
                self._day = day
                self._used = 0
            if self._used >= self.daily_limit:
                return UsageReservation(allowed=False, remaining=0)
            self._used += 1
            return UsageReservation(
                allowed=True, remaining=self.daily_limit - self._used
            )

    def remaining(self, current_day: Optional[date] = None) -> int:
        day = current_day or self._today_utc()
        with self._lock:
            if self._day != day:
                return self.daily_limit
            return max(0, self.daily_limit - self._used)
