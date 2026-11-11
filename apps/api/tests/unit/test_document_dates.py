"""«Today» for date_in_future is the user's day, not the server's (TC-014 runs it via the API)."""

from datetime import date

from freezegun import freeze_time

from app.modules.documents.dependencies import today_in


@freeze_time("2026-11-10T09:00:00Z")  # 12:00 in Moscow
def test_today_follows_the_user_zone_at_noon() -> None:
    assert today_in("Europe/Moscow") == date(2026, 11, 10)


@freeze_time("2026-11-10T20:59:00Z")  # 23:59 in Moscow
def test_last_minute_of_the_day_in_moscow() -> None:
    assert today_in("Europe/Moscow") == date(2026, 11, 10)


@freeze_time("2026-11-10T21:30:00Z")  # 11.11 00:30 in Moscow, still 10.11 in UTC
def test_after_midnight_in_moscow() -> None:
    assert today_in("Europe/Moscow") == date(2026, 11, 11)
    assert today_in("UTC") == date(2026, 11, 10)
