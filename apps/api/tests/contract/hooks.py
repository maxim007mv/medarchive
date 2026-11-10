"""Schemathesis hooks for `make contract`: `SCHEMATHESIS_HOOKS=tests.contract.hooks`.

Every generated request carries the session and CSRF token of a fresh archive with accepted
consent. A 401 (the fuzzer logged out or deleted the archive) makes Schemathesis fetch a new one.
"""

import os
import uuid
from typing import Any

import httpx
import schemathesis
from schemathesis import AuthContext, Case

BASE_URL = os.environ["CONTRACT_BASE_URL"]
POLICY_VERSION = "2026-11-10"
SESSION_COOKIE = "__Host-ma_sid"
ONE_HOUR_S = 3600


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
        case.headers["X-CSRF-Token"] = csrf_token
