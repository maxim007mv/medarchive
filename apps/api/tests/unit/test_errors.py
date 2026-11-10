import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]  # PyYAML ships no type hints
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict

from app.core.errors import CATALOG, ErrorCode, FieldError, ProblemError, install_error_handlers
from app.core.middleware import RequestContextMiddleware

REPO = Path(__file__).resolve().parents[4]


def _openapi() -> dict[str, Any]:
    spec: dict[str, Any] = yaml.safe_load((REPO / "openapi.yaml").read_text())
    return spec


def _openapi_titles() -> dict[str, tuple[int, str]]:
    titles: dict[str, tuple[int, str]] = {}
    for operations in _openapi()["paths"].values():
        for method, operation in operations.items():
            if method == "parameters":
                continue
            for response in operation["responses"].values():
                content = response.get("content", {}).get("application/problem+json", {})
                for example in content.get("examples", {}).values():
                    value = example["value"]
                    titles[value["code"]] = (value["status"], value["title"])
    return titles


def _texts_catalog() -> dict[str, tuple[int, str]]:
    section = (REPO / "docs/texts.md").read_text().split("## 16. Каталог ошибок", 1)[1]
    rows = re.findall(r"^\| `(\w+)` \| (\d{3}) \| (.+?) \|$", section, re.MULTILINE)
    return {code: (int(status), title) for code, status, title in rows}


def test_catalog_codes_match_openapi_enum() -> None:
    enum = _openapi()["components"]["schemas"]["Problem"]["properties"]["code"]["enum"]

    assert [code.value for code in ErrorCode] == enum
    assert set(CATALOG) == set(ErrorCode)


def test_catalog_matches_texts_dictionary() -> None:
    catalog = {code.value: (entry.status, entry.title) for code, entry in CATALOG.items()}

    assert catalog == _texts_catalog()


def test_catalog_matches_openapi_examples() -> None:
    for code, (status, title) in _openapi_titles().items():
        entry = CATALOG[ErrorCode(code)]
        assert (entry.status, entry.title) == (status, title), code


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_size: int


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/problem/{code}")
    async def raise_problem(code: ErrorCode) -> None:
        raise ProblemError(code, errors=[FieldError("/title", ErrorCode.TITLE_REQUIRED)])

    @app.post("/validate")
    async def validate(body: _Body) -> None:
        return None

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("SELECT ... 'Общий анализ крови'")

    @app.get("/resource")
    async def read_resource() -> None:
        return None

    @app.delete("/resource")
    async def delete_resource() -> None:
        return None

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://api") as client:
        yield client


@pytest.mark.parametrize("code", list(ErrorCode))
async def test_every_code_renders_as_problem(client: AsyncClient, code: ErrorCode) -> None:
    response = await client.get(f"/problem/{code.value}")

    body = response.json()
    assert response.status_code == CATALOG[code].status
    assert response.headers["content-type"] == "application/problem+json"
    assert body["type"] == f"urn:problem-type:medarchive:{code.value}"
    assert body["title"] == CATALOG[code].title
    assert body["code"] == code.value
    assert body["request_id"] == response.headers["x-request-id"]
    assert body["errors"] == [
        {"pointer": "/title", "code": "title_required", "title": "Введите название документа"}
    ]


async def test_validation_error_points_to_fields_without_values(client: AsyncClient) -> None:
    response = await client.post("/validate", json={"page_size": "секрет", "extra": "заметка"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert {error["pointer"] for error in body["errors"]} == {"/page_size", "/extra"}
    assert "секрет" not in response.text
    assert "заметка" not in response.text


async def test_undecodable_body_is_validation_error(client: AsyncClient) -> None:
    response = await client.post(
        "/validate", content=b"?\xff", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


async def test_unhandled_error_is_internal_without_trace(client: AsyncClient) -> None:
    response = await client.get("/crash")

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "internal"
    assert body["request_id"] == response.headers["x-request-id"]
    assert "Traceback" not in response.text
    assert "анализ" not in response.text
    assert "RuntimeError" not in response.text


async def test_unknown_route_is_not_found_problem(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nothing")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_method_not_allowed_lists_methods_of_every_route_on_the_path(
    client: AsyncClient,
) -> None:
    response = await client.options("/resource")

    assert response.status_code == 405
    assert response.headers["allow"] == "DELETE, GET"
    assert response.json()["status"] == 405


async def test_request_id_is_generated_or_taken_when_well_formed(client: AsyncClient) -> None:
    generated = await client.get("/api/v1/nothing")
    forwarded = await client.get("/api/v1/nothing", headers={"X-Request-Id": "req_web_1"})
    injected = await client.get("/api/v1/nothing", headers={"X-Request-Id": "a\tb"})

    assert re.fullmatch(r"req_[0-9a-f]{16}", generated.headers["x-request-id"])
    assert forwarded.headers["x-request-id"] == "req_web_1"
    assert injected.headers["x-request-id"] != "a\tb"
