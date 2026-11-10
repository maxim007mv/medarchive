"""Create local secrets for docker compose: `.env` from `.env.example` and the Tink KEK keyset.

Existing files are never overwritten: regenerating the KEK would make stored documents unreadable.
Run with `make secrets`; it needs the API environment for Tink.
"""

import os
import secrets
from collections.abc import Callable
from pathlib import Path

import tink
from tink import aead, json_proto_keyset_format, secret_key_access

ROOT = Path(__file__).resolve().parents[2]
ENV_TEMPLATE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
KEK_FILE = ROOT / "secrets" / "kek_keyset.json"
SECRET_BYTES = 32


def fill_empty_values(template: str) -> str:
    lines = []
    for line in template.splitlines():
        key, separator, value = line.partition("=")
        if separator and not line.startswith("#") and not value:
            line = f"{key}={secrets.token_urlsafe(SECRET_BYTES)}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def write_private(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(content)


def new_kek_keyset() -> str:
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    keyset: str = json_proto_keyset_format.serialize(handle, secret_key_access.TOKEN)
    return keyset


def create_once(path: Path, render: Callable[[], str]) -> None:
    if path.exists():
        print(f"kept {path.relative_to(ROOT)}")
        return
    write_private(path, render())
    print(f"created {path.relative_to(ROOT)}")


def main() -> None:
    create_once(ENV_FILE, lambda: fill_empty_values(ENV_TEMPLATE.read_text()))
    create_once(KEK_FILE, new_kek_keyset)


if __name__ == "__main__":
    main()
