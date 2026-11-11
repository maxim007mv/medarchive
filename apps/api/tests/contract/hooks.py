"""Schemathesis hooks for `make contract`: `SCHEMATHESIS_HOOKS=tests.contract.hooks`.

Every generated request carries the session and CSRF token of a fresh archive with accepted
consent and a unique Idempotency-Key. A 401 (the fuzzer logged out or deleted the archive) makes
Schemathesis fetch a new archive. Cases generated as valid also get valid values for the rules
the schema cannot express: an IANA zone in `tz` and `timezone`, a past document date from
1900-01-01, a period that does not end before it starts, a title that is not blank, no
made-up page token. Statuses the contract documents for requests a generator cannot make valid
are in schemathesis.toml.
"""

import os
import uuid
from datetime import date, timedelta
from typing import Any
from zoneinfo import available_timezones

import httpx
import schemathesis
from schemathesis import AuthContext, Case
from schemathesis.generation.meta import CoveragePhaseData, CoverageScenario

BASE_URL = os.environ["CONTRACT_BASE_URL"]
POLICY_VERSION = "2026-11-10"
SESSION_COOKIE = "__Host-ma_sid"
ONE_HOUR_S = 3600
CSRF_HEADER = "X-CSRF-Token"
IDEMPOTENCY_KEY = "Idempotency-Key"
PLACEHOLDER_TITLE = "Анализ"
# Bounds of the IdempotencyKey parameter in openapi.yaml.
MIN_KEY_LENGTH, MAX_KEY_LENGTH = 16, 64
ZONES = available_timezones()
DEFAULT_ZONE = "Europe/Moscow"
# documents CHECK (document_date >= DATE '1900-01-01') in 07-data-model.sql.
MIN_DOCUMENT_DATE = date(1900, 1, 1)


@schemathesis.auth(refresh_interval=ONE_HOUR_S)
class FreshArchive:
    def get(self, case: Case[Any], ctx: AuthContext) -> tuple[str, str]:
        response = httpx.post(
            f"{BASE_URL}/api/v1/workspaces",
            headers={"Idempotency-Key": str(uuid.uuid4())},
            json={"consent": {"policy_version": POLICY_VERSION, "accepted": True}},
            timeout=10,
        )
        response.raise_for_status()
        return response.cookies[SESSION_COOKIE], response.json()["csrf_token"]

    def set(self, case: Case[Any], data: tuple[str, str], ctx: AuthContext) -> None:
        session, csrf_token = data
        case.cookies[SESSION_COOKIE] = session
        if not _tests_missing_header(case, CSRF_HEADER):
            case.headers[CSRF_HEADER] = csrf_token
        # A schema-valid key the generator repeats with another body is rightly answered 422
        # idempotency_key_reused; missing and malformed keys stay for the negative cases.
        key = case.headers.get(IDEMPOTENCY_KEY)
        if key is not None and MIN_KEY_LENGTH <= len(key) <= MAX_KEY_LENGTH:
            case.headers[IDEMPOTENCY_KEY] = str(uuid.uuid4())
        if case.meta is not None and case.meta.generation.mode.is_positive:
            _make_valid(case)


def _tests_missing_header(case: Case[Any], name: str) -> bool:
    """The coverage case that leaves `name` out to check the API rejects the request."""
    data = case.meta.phase.data if case.meta is not None else None
    return (
        isinstance(data, CoveragePhaseData)
        and data.scenario == CoverageScenario.MISSING_PARAMETER
        and (data.parameter or "").lower() == name.lower()
    )


def _make_valid(case: Case[Any]) -> None:
    """The examples phase leaves out required headers without an example; zones, dates, periods,
    blank titles and page tokens are checked by the API against rules outside the schema."""
    requires_key = any(
        header.name == IDEMPOTENCY_KEY and header.is_required for header in case.operation.headers
    )
    if requires_key and case.headers.get(IDEMPOTENCY_KEY) is None:
        case.headers[IDEMPOTENCY_KEY] = str(uuid.uuid4())
    if isinstance(case.query, dict):
        if _is_unknown_zone(case.query.get("tz")):
            case.query["tz"] = DEFAULT_ZONE
        # Tokens are opaque and signed by the API: only one it issued is valid (TC-043).
        case.query.pop("page_token", None)
        _order_period(case.query)
    if isinstance(case.body, dict):
        if _is_unknown_zone(case.body.get("timezone")):
            case.body["timezone"] = DEFAULT_ZONE
        if _is_out_of_range(case.body.get("document_date")):
            case.body["document_date"] = MIN_DOCUMENT_DATE.isoformat()
        title = case.body.get("title")
        if isinstance(title, str) and not title.strip():
            case.body["title"] = PLACEHOLDER_TITLE
        document_filter = case.body.get("filter")
        if isinstance(document_filter, dict):
            _order_period(document_filter)


def _order_period(container: dict[str, Any]) -> None:
    """A period that starts after it ends is 422 date_range_invalid (TC-039)."""
    start, end = container.get("from"), container.get("to")
    if isinstance(start, str) and isinstance(end, str) and start > end:
        container["from"], container["to"] = end, start


def _is_unknown_zone(value: object) -> bool:
    return value is not None and value not in ZONES


def _is_out_of_range(value: object) -> bool:
    """Before 1900 or in the future (TC-014); yesterday is in the past in every zone."""
    if not isinstance(value, str):
        return False
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return not MIN_DOCUMENT_DATE <= parsed <= date.today() - timedelta(days=1)
