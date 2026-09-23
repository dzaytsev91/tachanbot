import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DatePeriod:
    start: date
    end: date

    @property
    def key(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"


def local_now() -> datetime:
    return datetime.now(ZoneInfo(os.getenv("TZ", "Europe/Moscow")))


def previous_week(today: date | None = None) -> DatePeriod:
    current_day = today or local_now().date()
    current_monday = current_day - timedelta(days=current_day.weekday())
    return DatePeriod(
        start=current_monday - timedelta(days=7),
        end=current_monday,
    )


def current_week_key(today: date | None = None) -> str:
    current_day = today or local_now().date()
    monday = current_day - timedelta(days=current_day.weekday())
    return monday.isoformat()
