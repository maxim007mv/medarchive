import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.modules.documents import service
from app.modules.documents.files import StoredFile


async def test_file_checks_run_at_most_four_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = threading.Lock()
    running = peak = 0

    def slow_check(*args: object, **kwargs: object) -> StoredFile:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return StoredFile(size_bytes=1, sha256=b"", page_count=1)

    monkeypatch.setattr(service, "store_verified_pdf", slow_check)
    unused: Any = None
    storage: Any = SimpleNamespace(quarantine=SimpleNamespace(size=lambda key: 1))
    session: Any = SimpleNamespace(workspace_id=uuid4())
    upload: Any = SimpleNamespace(id=uuid4(), quarantine_key="q/x.bin")

    await asyncio.gather(
        *(
            service._store_upload(unused, session, unused, storage, upload, uuid4())
            for _ in range(12)
        )
    )

    assert peak == service.MAX_CONCURRENT_FILE_CHECKS
