import pytest

from app.core.ratelimit import GENERAL, SESSIONS_CREATE, RatePolicy, Subject, gcra

NOW = 1_794_300_000_000  # Unix ms


def _burst(policy: RatePolicy, count: int, now: int) -> int | None:
    tat: int | None = None
    for _ in range(count):
        decision = gcra(policy, tat, now)
        assert decision.allowed
        tat = decision.new_tat_ms
    return tat


def test_login_allows_five_then_denies_sixth() -> None:
    tat: int | None = None
    remaining = []
    for _ in range(5):
        decision = gcra(SESSIONS_CREATE, tat, NOW)
        assert decision.allowed
        remaining.append(decision.remaining)
        tat = decision.new_tat_ms

    sixth = gcra(SESSIONS_CREATE, tat, NOW)

    assert remaining == [4, 3, 2, 1, 0]
    assert not sixth.allowed
    assert sixth.remaining == 0
    assert sixth.reset_s == 180  # 900 s / 5 attempts
    assert sixth.new_tat_ms is None


def test_one_request_returns_after_emission_interval() -> None:
    tat = _burst(SESSIONS_CREATE, 5, NOW)

    assert not gcra(SESSIONS_CREATE, tat, NOW + 179_999).allowed
    assert gcra(SESSIONS_CREATE, tat, NOW + 180_000).allowed


def test_full_quota_returns_after_window() -> None:
    tat = _burst(SESSIONS_CREATE, 5, NOW)

    assert gcra(SESSIONS_CREATE, tat, NOW + 900_000).remaining == 4


def test_reset_counts_seconds_to_full_quota() -> None:
    decision = gcra(GENERAL, None, NOW)

    assert decision.remaining == 299
    assert decision.reset_s == 1  # 60 s / 300 requests = 0.2 s, rounded up


@pytest.mark.parametrize(
    ("policy", "header"),
    [
        (GENERAL, '"general";q=300;w=60'),
        (RatePolicy("burst", 30, 60, Subject.SESSION), '"burst";q=30;w=60'),
    ],
)
def test_policy_header(policy: RatePolicy, header: str) -> None:
    assert policy.header == header
