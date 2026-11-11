"""The app's own OpenAPI against openapi.yaml (test-strategy.md, section 2b).

Always: the app has no operation, path, method or status code that the contract lacks (AGENTS.md:
no invented endpoints). With `CONTRACT_BLOCK=N` (default 1): every contract operation of blocks
1..N exists with exactly the contract's status codes. Blocks per operation: operation-blocks.json.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest
import schemathesis

from app.main import app

HERE = Path(__file__).parent
CONTRACT_PATH = HERE.parents[3] / "openapi.yaml"
HTTP_METHODS = {"get", "put", "post", "patch", "delete", "head", "options"}
OPERATION_BLOCKS: dict[str, int] = json.loads((HERE / "operation-blocks.json").read_text())
GATED_BLOCK = int(os.environ.get("CONTRACT_BLOCK", "1"))


def operations(spec: dict[str, Any]) -> dict[str, tuple[str, str, set[str]]]:
    """operationId -> (method, path, status codes)."""
    return {
        operation["operationId"]: (method, path, set(operation.get("responses", {})))
        for path, item in spec["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }


CONTRACT = operations(schemathesis.openapi.from_path(CONTRACT_PATH).raw_schema)
APP = operations(app.openapi())


def test_operation_blocks_cover_the_contract() -> None:
    assert set(OPERATION_BLOCKS) == set(CONTRACT)


@pytest.mark.parametrize("operation_id", sorted(APP))
def test_app_operation_is_in_contract(operation_id: str) -> None:
    assert operation_id in CONTRACT, f"{operation_id} is not in openapi.yaml"
    app_method, app_path, app_codes = APP[operation_id]
    method, path, codes = CONTRACT[operation_id]
    assert (app_method, app_path) == (method, path)
    assert app_codes <= codes, f"undeclared status codes {sorted(app_codes - codes)}"


@pytest.mark.parametrize(
    "operation_id",
    sorted(op for op, block in OPERATION_BLOCKS.items() if block <= GATED_BLOCK),
)
def test_gated_operation_is_implemented_with_contract_codes(operation_id: str) -> None:
    assert operation_id in APP, f"{operation_id} is not implemented"
    assert APP[operation_id][2] == CONTRACT[operation_id][2]
