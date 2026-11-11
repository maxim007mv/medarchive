import uuid

import pytest
from api_stack import Api, create_archive
from documents_support import write_headers

BODY = {"upload_id": str(uuid.uuid4())}


async def test_be16_suggestion_is_turned_off_with_503(api: Api) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        response = await client.post(
            "/api/v1/suggestions", headers=write_headers(created), json=BODY
        )

    assert response.status_code == 503
    assert response.json()["code"] == "ai_unavailable"


@pytest.mark.parametrize(
    ("dropped", "status", "code"),
    [
        ("X-CSRF-Token", 403, "csrf_failed"),
        ("Idempotency-Key", 400, "idempotency_key_missing"),
    ],
)
async def test_be16_suggestion_checks_the_write_first(
    api: Api, dropped: str, status: int, code: str
) -> None:
    async with api.client() as client:
        created = await create_archive(client)
        headers = {k: v for k, v in write_headers(created).items() if k != dropped}
        response = await client.post("/api/v1/suggestions", headers=headers, json=BODY)

    assert response.status_code == status
    assert response.json()["code"] == code
