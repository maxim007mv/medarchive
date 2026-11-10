# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Release gate of block N (docs/progress/blocks.md).

Runs the checks of blocks 1..N on the committed HEAD in a separate git worktree and a separate
compose project, so other agents' uncommitted edits and stacks never reach the result, then
appends the result to docs/progress/blocks.md. Tool commands and versions live in the Makefile.

Usage: tools/verify_block.sh N [--keep-stack] [--no-record]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[1]
WORKTREE = Path(os.environ.get("GATE_WORKTREE", "/tmp/medarchive-gate"))
LOG_ROOT = Path(os.environ.get("GATE_LOGS", "/tmp/medarchive-gate-logs"))
BLOCKS_MD = REPO / "docs/progress/blocks.md"

PROJECT = "medarchive_qa"
# The browser goes through the `tls` profile: WebKit keeps the Secure session cookie only on https
# (ADR-048 fallback), and storage is https too so uploads are not mixed content.
STACK_ENV = {
    "COMPOSE_PROJECT_NAME": PROJECT,
    "COMPOSE_PROFILES": "tls",
    "WEB_PORT": "3400",
    "API_PORT": "8900",
    "MINIO_PORT": "9400",
    "MINIO_CONSOLE_PORT": "9401",
    "TLS_WEB_PORT": "3444",
    "TLS_STORAGE_PORT": "9444",
    "S3_PUBLIC_ENDPOINT": "https://localhost:9444",
    "IMAGE_TAG": "qa",
    # Own subnet: Docker rejects a second stack whose network overlaps another's.
    "NET_PREFIX": "10.157.4",
}
WEB_URL = "https://localhost:3444"
API_URL = "http://localhost:8900"
POLICY_VERSION = "2026-11-10"
XSS_TITLE = "<img src=x onerror=alert(1)>"
BASE_IMAGES = ["python:3.12-slim-bookworm", "node:22-alpine"]

# TC ranges each block adds to its gate; gates are cumulative (block N checks blocks 1..N).
BLOCK_TC_RANGES: dict[int, list[tuple[int, int]]] = {
    2: [(91, 92)],
    3: [(1, 4), (93, 93)],
    4: [(10, 24)],
    5: [(30, 44), (50, 50), (57, 57), (85, 85), (90, 90)],
    6: [(51, 60), (70, 84)],
    9: [(80, 81)],
}
# Cases that need the production rate limits; every other E2E test runs with limits off (D-006).
RATE_LIMIT_TCS = ("TC-082", "TC-098")
# From block 7 every in-scope P0 and P1 case is required and security steps become blocking.
HARDENING_BLOCK = 7
# AI suggestion is out of the prototype's scope (ADR-042).
OUT_OF_SCOPE = range(100, 105)
# Not after a letter, so `test_tc091_…` and `@TC-093` match and `ETC-1234` does not.
TC_PATTERN = re.compile(r"(?<![a-z])TC[-_ ]?(\d{3}b?)(?!\d)", re.IGNORECASE)

Summary = Callable[[subprocess.CompletedProcess[str]], tuple[bool, str]]


@dataclass
class Step:
    name: str
    blocking: bool
    status: str  # pass | fail | not run
    detail: str
    seconds: float = 0.0


@dataclass
class TestResult:
    source: str
    name: str
    status: str  # passed | failed | skipped


@dataclass
class Gate:
    block: int
    logs: Path
    steps: list[Step] = field(default_factory=list)
    results: list[TestResult] = field(default_factory=list)
    # E2E tests tagged with later blocks; None when the E2E step did not run.
    pending_e2e: int | None = None

    def run(
        self,
        name: str,
        command: list[str],
        *,
        blocking: bool = True,
        cwd: Path = WORKTREE,
        env: dict[str, str] | None = None,
        timeout_s: int = 1800,
        summarize: Summary | None = None,
    ) -> bool:
        """Runs one check with its output in a log file and records pass or fail with a summary."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        log = self.logs / f"{len(self.steps) + 1:02d}-{slug}.log"
        started = time.monotonic()
        try:
            done = subprocess.run(
                command,
                cwd=cwd,
                env={**child_env(), **(env or {})},
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self.record(name, blocking, False, f"timeout {timeout_s} s", started)
            return False
        log.write_text(f"$ {' '.join(command)}\n\n{done.stdout}\n{done.stderr}")
        ok, detail = (summarize or exit_code)(done)
        self.record(name, blocking, ok, f"{detail}; лог `{log.name}`", started)
        return ok

    def record(self, name: str, blocking: bool, ok: bool, detail: str, started: float) -> None:
        status = "pass" if ok else "fail"
        detail = " ".join(detail.split())[:400]  # one table row
        self.steps.append(Step(name, blocking, status, detail, time.monotonic() - started))
        print(f"[{status}] {name}: {detail}", flush=True)

    def skip(self, name: str, reason: str) -> None:
        self.steps.append(Step(name, True, "not run", reason))
        print(f"[not run] {name}: {reason}", flush=True)

    def make(
        self, name: str, target: str, *, blocking: bool, summarize: Summary, **variables: str
    ) -> bool:
        assignments = [
            f"{key}={value}" for key, value in {"REPORT_DIR": str(self.logs), **variables}.items()
        ]
        return self.run(
            name,
            ["make", "--no-print-directory", target, *assignments],
            blocking=blocking,
            summarize=summarize,
            timeout_s=2400,
        )


# Inherited values would change what is tested: API settings leak into pytest and compose, and
# `uv run` sets VIRTUAL_ENV for this script only.
NOT_INHERITED = {"VIRTUAL_ENV", "RATE_LIMITS_ENABLED", "TRUSTED_PROXIES", "NET_PREFIX"}


def child_env() -> dict[str, str]:
    """The environment of every check: the caller's, minus stack settings, plus STACK_ENV."""
    inherited = {k: v for k, v in os.environ.items() if k not in NOT_INHERITED}
    return {**inherited, **STACK_ENV}


def exit_code(done: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    return done.returncode == 0, f"exit {done.returncode}"


def last_line(done: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    """Exit code and the last line the check printed (its own verdict)."""
    lines = (done.stdout.strip() or done.stderr.strip()).splitlines()
    return done.returncode == 0, lines[-1][:300] if lines else f"exit {done.returncode}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


# Test reports ------------------------------------------------------------------------------


def read_junit(path: Path, source: str) -> list[TestResult]:
    if not path.exists():
        return []
    results = []
    # Reports are written by our own test runners in this run, not by an outside party.
    for case in ElementTree.parse(path).iter("testcase"):  # noqa: S314
        if case.find("failure") is not None or case.find("error") is not None:
            status = "failed"
        elif case.find("skipped") is not None:
            status = "skipped"
        else:
            status = "passed"
        results.append(TestResult(source, f"{case.get('classname')}::{case.get('name')}", status))
    return results


def read_playwright(path: Path) -> list[TestResult]:
    if not path.exists():
        return []
    results: list[TestResult] = []
    outcome = {"expected": "passed", "skipped": "skipped"}

    def walk(suite: dict[str, Any], titles: list[str]) -> None:
        here = [*titles, suite["title"]]
        for spec in suite.get("specs", []):
            title = " / ".join([*here, spec["title"], *spec.get("tags", [])])
            for test in spec["tests"]:
                status = outcome.get(test["status"], "failed")
                results.append(TestResult(f"e2e:{test['projectName']}", title, status))
        for child in suite.get("suites", []):
            walk(child, here)

    for suite in read_json(path).get("suites", []):
        walk(suite, [])
    return results


def counts(results: list[TestResult]) -> str:
    by = {s: sum(r.status == s for r in results) for s in ("passed", "failed", "skipped")}
    return f"{by['passed']} passed, {by['failed']} failed, {by['skipped']} skipped"


def from_report(parse: Callable[[], list[TestResult]], gate: Gate) -> Summary:
    """Exit code plus the counts of the report the command wrote; an empty report fails."""

    def summarize(done: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        results = parse()
        gate.results.extend(results)
        ok = done.returncode == 0 and bool(results) and all(r.status != "failed" for r in results)
        return ok, f"{counts(results)} (exit {done.returncode})"

    return summarize


# Test-case catalogue -----------------------------------------------------------------------


def catalogue() -> dict[str, str]:
    """TC id -> priority, from MedArchive/05_qa/test-cases.md."""
    text = (WORKTREE / "MedArchive/05_qa/test-cases.md").read_text()
    return dict(re.findall(r"^\| (TC-\d{3}b?) \| [^|]+ \| (P\d) \|", text, re.MULTILINE))


def required_tcs(block: int) -> list[str]:
    in_scope = {tc: p for tc, p in catalogue().items() if int(tc[3:6]) not in OUT_OF_SCOPE}
    required = {
        tc
        for b, ranges in BLOCK_TC_RANGES.items()
        if b <= block
        for low, high in ranges
        for tc in in_scope
        if low <= int(tc[3:6]) <= high
    }
    if block >= HARDENING_BLOCK:
        required |= {tc for tc, p in in_scope.items() if p in ("P0", "P1")}
    return sorted(required)


def results_by_tc(results: list[TestResult]) -> dict[str, list[TestResult]]:
    by_tc: dict[str, list[TestResult]] = {}
    for result in results:
        for number in {m.lower() for m in TC_PATTERN.findall(result.name)}:
            by_tc.setdefault(f"TC-{number}", []).append(result)
    return by_tc


def verdict(tests: list[TestResult]) -> str:
    """pass needs at least one passed test and no failed or skipped (pending) one."""
    statuses = {t.status for t in tests}
    if not tests:
        return "нет теста"
    if "failed" in statuses:
        return "fail"
    return "pass" if statuses == {"passed"} else "pending"


# Steps -------------------------------------------------------------------------------------


def git(*args: str) -> str:
    done = subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True, text=True)
    return done.stdout.strip()


def compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "-p", PROJECT, *args],
        cwd=WORKTREE,
        env=child_env(),
        capture_output=True,
        text=True,
        check=False,
    )


def prepare_worktree(sha: str) -> None:
    if (WORKTREE / ".git").exists():
        git("-C", str(WORKTREE), "checkout", "--quiet", "--detach", "--force", sha)
        git("-C", str(WORKTREE), "clean", "-ffdxq", "-e", "node_modules", "-e", ".venv")
    else:
        git("worktree", "add", "--force", "--detach", str(WORKTREE), sha)
    for secret in (".env", "secrets/kek_keyset.json"):
        target = WORKTREE / secret
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(REPO / secret, target)


def run_static(gate: Gate) -> None:
    gate.run("make lint", ["make", "lint"])
    gate.run("make typecheck", ["make", "typecheck"])
    pytest_xml = gate.logs / "pytest.xml"
    gate.run(
        "make test-api (pytest)",
        ["make", "test-api"],
        env={"PYTEST_ADDOPTS": f"--junitxml={pytest_xml}", "CONTRACT_BLOCK": str(gate.block)},
        summarize=from_report(lambda: read_junit(pytest_xml, "pytest"), gate),
    )
    vitest_xml = gate.logs / "vitest.xml"
    reporters = f"--reporter=default --reporter=junit --outputFile={vitest_xml}"
    gate.run(
        "make test-web (vitest)",
        ["make", "test-web", f"VITEST_ARGS={reporters}"],
        summarize=from_report(lambda: read_junit(vitest_xml, "vitest"), gate),
    )
    gate.run("web build", ["pnpm", "--filter", "web", "build"])


def stack_state(done: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    listing = compose("ps", "-a", "--format", "json").stdout
    services = [json.loads(line) for line in listing.splitlines() if line.strip()]
    states = {s["Service"]: s["Health"] or f"{s['State']}({s['ExitCode']})" for s in services}
    healthy = done.returncode == 0 and all(v in ("healthy", "exited(0)") for v in states.values())
    services_state = ", ".join(f"{name} {state}" for name, state in sorted(states.items()))
    return healthy, f"exit {done.returncode}; {services_state or 'no containers'}"


def run_stack(gate: Gate) -> bool:
    compose("down", "-v", "--remove-orphans")
    return gate.run(
        "compose up, all services healthy",
        [
            "docker",
            "compose",
            "-p",
            PROJECT,
            "up",
            "-d",
            "--build",
            "--wait",
            "--wait-timeout",
            "300",
        ],
        summarize=stack_state,
    )


def require_tests(gate: Gate, name: str, source: str, needle: str) -> None:
    """A gate item met by the existence of passing tests whose report name contains `needle`."""
    tests = [r for r in gate.results if r.source == source and needle in r.name.lower()]
    ok = bool(tests) and all(r.status == "passed" for r in tests)
    gate.steps.append(Step(name, True, "pass" if ok else "fail", f"{counts(tests)} ({needle})"))


def run_block2_checks(gate: Gate) -> None:
    require_tests(gate, "UI unit tests (FE-03..FE-09)", "vitest", "components/")
    require_tests(gate, "error catalog contract (BE-03)", "pytest", "catalog")
    for major in ("17", "18"):
        gate.run(
            f"migrations up/down on PostgreSQL {major}",
            ["bash", "tools/check_migrations.sh", major, "medarchive/api:qa"],
            summarize=last_line,
        )


def set_rate_limits(gate: Gate, *, enabled: bool) -> bool:
    """Recreates the api with RATE_LIMITS_ENABLED (D-006) and an empty limit store."""
    compose("exec", "-T", "redis", "redis-cli", "FLUSHALL")
    value = str(enabled).lower()
    return gate.run(
        f"api with RATE_LIMITS_ENABLED={value}",
        ["docker", "compose", "-p", PROJECT, "up", "-d", "--wait", "api"],
        env={"RATE_LIMITS_ENABLED": value},
    )


def run_playwright(gate: Gate, name: str, grep: str, *extra: str) -> None:
    results_dir = gate.logs / re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    gate.run(
        name,
        # Three workers: each test seeds its own archive, and the Docker VM is shared (D-011).
        [
            "pnpm",
            "--filter",
            "e2e",
            "exec",
            "playwright",
            "test",
            "--workers=3",
            "--grep",
            grep,
            *extra,
        ],
        env={
            "E2E_BASE_URL": WEB_URL,
            "E2E_RESULTS_DIR": str(results_dir),
            "E2E_COMPOSE_PROJECT": PROJECT,
        },
        timeout_s=3600,
        summarize=from_report(lambda: read_playwright(results_dir / "report.json"), gate),
    )


def run_e2e(gate: Gate, *, rate_limited: bool) -> None:
    """Functional tests run without limits (each test creates its own archive from one IP);
    the limit cases TC-082 and TC-098 run afterwards with the production limits, one by one."""
    grep = rf"@b[1-{gate.block}]\b"
    limit_cases = "|".join(f"@{tc}" for tc in RATE_LIMIT_TCS)
    if not rate_limited:
        repeat = ["--repeat-each=3"] if gate.block >= HARDENING_BLOCK else []  # QA-04: no flaky
        run_playwright(gate, f"e2e {grep}, limits off", grep, "--grep-invert", limit_cases, *repeat)
    else:
        if set(RATE_LIMIT_TCS) & set(required_tcs(gate.block)):
            both = rf"^(?=.*{grep})(?=.*({limit_cases})\b)"
            run_playwright(gate, "e2e TC-082, TC-098, limits on", both, "--workers=1")
        return
    listing = subprocess.run(
        ["pnpm", "--filter", "e2e", "exec", "playwright", "test", "--list", "--grep-invert", grep],
        cwd=WORKTREE,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    found = re.search(r"Total: (\d+) tests?", listing)
    gate.pending_e2e = int(found.group(1)) if found else None


# They end the hook's session, so each case makes it create a new archive (10 per hour per IP).
SESSION_ENDING_OPERATIONS = {"sessions.delete", "workspace.delete"}


def run_schemathesis(gate: Gate) -> None:
    """Two passes: the session-ending operations apart, with few examples."""
    blocks = read_json(WORKTREE / "apps/api/tests/contract/operation-blocks.json")
    gated = {op for op, block in blocks.items() if block <= gate.block}
    passes = [
        ("schemathesis --checks all", gated - SESSION_ENDING_OPERATIONS, "25"),
        ("schemathesis --checks all, session-ending", gated & SESSION_ENDING_OPERATIONS, "3"),
    ]
    for name, operations, examples in passes:
        if not operations:
            continue
        # The QA stack's Redis holds rate-limit counters only; the hook needs a fresh budget.
        compose("exec", "-T", "redis", "redis-cli", "FLUSHALL")
        report = gate.logs / f"schemathesis-{len(gate.steps)}.xml"
        regex = "|".join(re.escape(op) for op in sorted(operations))
        options = {
            "--url": API_URL,
            "--checks": "all",
            "--include-operation-id-regex": f"^({regex})$",
            "--max-examples": examples,
            "--seed": "20261110",
            "--workers": "1",
            "--report": "junit",
            "--report-junit-path": str(report),
        }
        gate.run(
            name,
            ["uv", "run", "schemathesis", "run", "../../openapi.yaml"]
            + [part for pair in options.items() for part in pair],
            blocking=gate.block >= HARDENING_BLOCK,
            cwd=WORKTREE / "apps/api",
            env={"CONTRACT_BASE_URL": API_URL, "SCHEMATHESIS_HOOKS": "tests.contract.hooks"},
            summarize=from_report(partial(read_junit, report, "schemathesis"), gate),
        )


def pii_markers() -> list[str]:
    """Titles, file names and notes the tests store: none may reach logs or plaintext columns."""
    manifest = read_json(WORKTREE / "qa/fixtures/manifest.json")
    markers = [s["title"] for s in manifest["sources"]]
    markers += [Path(s["path"]).name for s in manifest["sources"]]
    markers += [g["name"] for g in manifest["generated"]]
    return [*markers, XSS_TITLE, "Натощак"]


def run_pii_scan(gate: Gate) -> None:
    """TC-096 and T8 after the E2E run: logs of all services and a data-only dump of schema app."""
    started = time.monotonic()
    logs = compose("logs", "--no-color").stdout
    dump = compose(
        "exec",
        "-T",
        "db",
        "pg_dump",
        "-U",
        "postgres",
        "-d",
        "medarchive",
        "--data-only",
        "--schema=app",
    )
    if dump.returncode != 0:
        gate.record(
            "PII scan: logs and DB dump (TC-096)",
            gate.block >= HARDENING_BLOCK,
            False,
            f"pg_dump failed: {dump.stderr.strip()[-200:]}",
            started,
        )
        return
    markers = pii_markers()
    in_logs = [m for m in markers if m in logs]
    in_db = [m for m in markers if m in dump.stdout or m.encode().hex() in dump.stdout]
    ok = not in_logs and not in_db
    detail = (
        f"{len(markers)} markers; in logs {len(in_logs)}, in DB plaintext {len(in_db)}, "
        f"dump {len(dump.stdout)} bytes"
    )
    gate.record(
        "PII scan: logs and DB dump (TC-096)", gate.block >= HARDENING_BLOCK, ok, detail, started
    )
    status = "passed" if ok else "failed"
    gate.results.append(
        TestResult("gate", "TC-096 no titles, notes or file names in plaintext", status)
    )
    (gate.logs / "pii-found.json").write_text(json.dumps({"logs": len(in_logs), "db": len(in_db)}))


def run_supply_chain(gate: Gate) -> None:
    blocking = gate.block >= HARDENING_BLOCK
    reports = gate.logs
    gate.make(
        "pip-audit (OPS-04)",
        "audit-python",
        blocking=blocking,
        summarize=lambda done: pip_audit(done, reports / "pip-audit.json"),
    )
    gate.make(
        "pnpm audit --prod (OPS-04)",
        "audit-node",
        blocking=blocking,
        summarize=lambda done: pnpm_audit(done, reports / "pnpm-audit.json"),
    )
    gate.make(
        "gitleaks, git history (OPS-04)",
        "gitleaks",
        blocking=blocking,
        summarize=lambda done: gitleaks(done, reports / "gitleaks.json"),
    )
    # The images we ship block; raw base images are reported only: the web image removes npm,
    # where all fixable findings of node:22-alpine live (D-004).
    for image in ["medarchive/api:qa", "medarchive/web:qa", *BASE_IMAGES]:
        report = reports / f"trivy-{image.replace('/', '-').replace(':', '-')}.json"
        gate.make(
            f"trivy {image} (OPS-04, OPS-05)",
            "trivy",
            blocking=blocking and image not in BASE_IMAGES,
            summarize=partial(trivy, report=report),
            IMAGE=image,
        )


def pip_audit(done: subprocess.CompletedProcess[str], report: Path) -> tuple[bool, str]:
    if not report.exists():
        return False, f"no report (exit {done.returncode})"
    deps = read_json(report)["dependencies"]
    vulns = sorted(f"{d['name']} {v['id']}" for d in deps for v in d.get("vulns", []))
    return done.returncode == 0 and not vulns, f"{len(deps)} packages, vulnerabilities {vulns}"


def pnpm_audit(done: subprocess.CompletedProcess[str], report: Path) -> tuple[bool, str]:
    try:
        found = read_json(report)["metadata"]["vulnerabilities"]
    except (OSError, ValueError, KeyError):
        return False, f"unreadable report (exit {done.returncode})"
    return done.returncode == 0, ", ".join(f"{level} {n}" for level, n in found.items())


def gitleaks(done: subprocess.CompletedProcess[str], report: Path) -> tuple[bool, str]:
    if not report.exists():
        return False, f"no report (exit {done.returncode})"
    rules = sorted({leak["RuleID"] for leak in read_json(report)})
    return done.returncode == 0, f"findings by rule {rules} (values redacted)"


def trivy(done: subprocess.CompletedProcess[str], report: Path) -> tuple[bool, str]:
    if not report.exists():
        return False, f"no report (exit {done.returncode}) {done.stderr.strip()[-200:]}"
    vulns = [
        v for r in read_json(report).get("Results", []) for v in r.get("Vulnerabilities") or []
    ]
    found = []
    for severity in ("CRITICAL", "HIGH"):
        ids = sorted({v["VulnerabilityID"] for v in vulns if v["Severity"] == severity})
        found.append(f"{severity} {len(ids)} {ids[:5]}")
    return done.returncode == 0, f"fixable {', '.join(found)}"


def new_session_cookie() -> str:
    request = urllib.request.Request(  # noqa: S310 (fixed http URL of the local stack)
        f"{API_URL}/api/v1/workspaces",
        data=json.dumps({"consent": {"policy_version": POLICY_VERSION, "accepted": True}}).encode(),
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        return str(response.headers["Set-Cookie"]).split(";", 1)[0]


def run_zap(gate: Gate) -> None:
    blocking = gate.block >= HARDENING_BLOCK
    try:
        cookie = new_session_cookie()
    except OSError as error:
        gate.skip("ZAP baseline", f"no session for the scan: {error}")
        return
    report = gate.logs / "zap.json"
    gate.make(
        "ZAP baseline, no High",
        "zap",
        blocking=blocking,
        summarize=lambda done: zap(done, report),
        COMPOSE_PROJECT=PROJECT,
        ZAP_COOKIE=cookie,
    )


def zap(done: subprocess.CompletedProcess[str], report: Path) -> tuple[bool, str]:
    if not report.exists():
        return False, f"no report (exit {done.returncode})"
    alerts = [a for site in read_json(report)["site"] for a in site["alerts"]]
    risks = {"High": "3", "Medium": "2", "Low": "1"}
    names = {
        risk: sorted({a["name"] for a in alerts if a["riskcode"] == code})
        for risk, code in risks.items()
    }
    return not names["High"], "; ".join(f"{risk} {found}" for risk, found in names.items())


def run_k6(gate: Gate) -> None:
    gate.make(
        "k6 GET /documents p95 < 300 ms, 50 VU, 1000 docs",
        "load",
        blocking=True,
        summarize=last_line,
        COMPOSE_PROJECT=PROJECT,
    )


# Record ------------------------------------------------------------------------------------


def report_markdown(gate: Gate, sha: str, subject: str, required: list[str], passed: bool) -> str:
    now = datetime.now().astimezone().strftime("%d.%m.%Y %H:%M %Z")
    lines = [
        f"#### Прогон {now}, `{sha[:7]}`: {'PASS' if passed else 'FAIL'}",
        "",
        f"Коммит `{sha[:7]}` «{subject}». Стек `{PROJECT}` (браузер `{WEB_URL}`, api :8900), "
        f"логи `{gate.logs}`. Команда `tools/verify_block.sh {gate.block}`.",
        "",
        "| Шаг | Блокирует | Итог | Подробности | с |",
        "|---|---|---|---|---|",
    ]
    for step in gate.steps:
        detail = step.detail.replace("|", "\\|")
        blocking = "да" if step.blocking else "нет"
        lines.append(
            f"| {step.name} | {blocking} | {step.status} | {detail} | {step.seconds:.0f} |"
        )
    by_tc = results_by_tc(gate.results)
    if required:
        lines += ["", "| TC | Итог | Тесты |", "|---|---|---|"]
        for tc in required:
            tests = by_tc.get(tc, [])
            sources = ", ".join(sorted({f"{t.source} {t.status}" for t in tests})) or "-"
            lines.append(f"| {tc} | {verdict(tests)} | {sources} |")
    pending = "не посчитаны, E2E не запускался" if gate.pending_e2e is None else gate.pending_e2e
    lines += ["", f"E2E-тесты блоков после {gate.block} (pending, не запускались): {pending}.", ""]
    return "\n".join(lines)


def append_to_blocks_md(block: int, section: str) -> None:
    """Inserts the run before «### Дефекты» of the block's section, or at the section's end."""
    text = BLOCKS_MD.read_text()
    heading = re.search(rf"^## Блок {block}\b.*$", text, re.MULTILINE)
    if heading is None:
        BLOCKS_MD.write_text(f"{text.rstrip()}\n\n## Блок {block}\n\n{section}")
        return
    body = text[heading.end() :]
    next_block = re.search(r"^## ", body, re.MULTILINE)
    body = body[: next_block.start()] if next_block else body
    defects = re.search(r"^### Дефекты", body, re.MULTILINE)
    at = heading.end() + (defects.start() if defects else len(body))
    BLOCKS_MD.write_text(f"{text[:at].rstrip()}\n\n{section}\n{text[at:].lstrip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("block", type=int, choices=range(1, 10))
    parser.add_argument("--keep-stack", action="store_true", help="leave the QA stack running")
    parser.add_argument("--no-record", action="store_true", help="do not write blocks.md")
    args = parser.parse_args()

    sha = git("rev-parse", "HEAD")
    subject = git("log", "-1", "--format=%s")
    logs = LOG_ROOT / f"{datetime.now():%Y%m%d-%H%M}-{sha[:7]}-b{args.block}"
    logs.mkdir(parents=True, exist_ok=True)
    gate = Gate(args.block, logs)
    print(f"gate of block {args.block} on {sha[:7]} {subject}; logs {logs}", flush=True)

    prepare_worktree(sha)
    gate.run("deps: pnpm install", ["pnpm", "install", "--frozen-lockfile"])
    gate.run("deps: uv sync", ["uv", "sync", "--directory", "apps/api", "--frozen"])
    gate.run("make fixtures", ["make", "fixtures"])
    gate.run(
        "playwright browsers",
        ["pnpm", "--filter", "e2e", "exec", "playwright", "install", "chromium", "webkit"],
    )
    run_static(gate)
    stack_ok = run_stack(gate)
    if args.block >= 2:
        run_block2_checks(gate)
    if stack_ok:
        gate.run(
            "hardening (OPS-05, OPS-07)",
            ["bash", "tools/check_hardening.sh", PROJECT, "qa"],
            blocking=args.block >= HARDENING_BLOCK,
            summarize=lambda d: (d.returncode == 0, d.stdout.strip().replace("\n", "; ")),
        )
        if set_rate_limits(gate, enabled=False):
            run_e2e(gate, rate_limited=False)
            if args.block >= HARDENING_BLOCK:
                run_k6(gate)
        if set_rate_limits(gate, enabled=True):
            run_e2e(gate, rate_limited=True)
            if args.block >= 3:
                run_schemathesis(gate)
            if args.block >= 4:
                run_pii_scan(gate)
            if args.block >= 5:
                run_zap(gate)
    else:
        gate.skip("stack checks: hardening, e2e, contract, PII, ZAP, k6", "stack is not healthy")
    run_supply_chain(gate)
    if not args.keep_stack:
        compose("down")

    required = required_tcs(args.block)
    by_tc = results_by_tc(gate.results)
    passed = all(verdict(by_tc.get(tc, [])) == "pass" for tc in required) and all(
        step.status == "pass" for step in gate.steps if step.blocking
    )
    section = report_markdown(gate, sha, subject, required, passed)
    (logs / "summary.md").write_text(section)
    if not args.no_record:
        append_to_blocks_md(args.block, section)
    print(section)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
