"""Create local secrets for docker compose: `.env` from `.env.example` and the Tink KEK keyset.

Existing values are never changed: regenerating the KEK or a key would make stored documents or
issued tokens unreadable. Keys added to `.env.example` later are appended to an existing `.env`.
Run with `make secrets`; it needs the API environment for Tink.
"""

import os
import secrets
from pathlib import Path

import tink
from tink import aead, json_proto_keyset_format, secret_key_access

ROOT = Path(__file__).resolve().parents[2]
ENV_TEMPLATE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
KEK_FILE = ROOT / "secrets" / "kek_keyset.json"
# token_urlsafe(32) gives 43 characters: above the 32-character minimum of the API secrets.
SECRET_BYTES = 32


def assignment(line: str) -> tuple[str, str] | None:
    key, separator, value = line.partition("=")
    if not separator or line.startswith("#"):
        return None
    return key, value


def filled(key: str, value: str) -> str:
    return f"{key}={value or secrets.token_urlsafe(SECRET_BYTES)}"


def fill_empty_values(template: str) -> str:
    lines = []
    for line in template.splitlines():
        parsed = assignment(line)
        lines.append(filled(*parsed) if parsed else line)
    return "\n".join(lines) + "\n"


def missing_assignments(template: str, env: str) -> list[str]:
    present = {parsed[0] for line in env.splitlines() if (parsed := assignment(line))}
    return [
        filled(*parsed)
        for line in template.splitlines()
        if (parsed := assignment(line)) and parsed[0] not in present
    ]


def write_private(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(content)


def sync_env() -> None:
    template = ENV_TEMPLATE.read_text()
    if not ENV_FILE.exists():
        write_private(ENV_FILE, fill_empty_values(template))
        print("created .env")
        return
    env = ENV_FILE.read_text()
    added = missing_assignments(template, env)
    if not added:
        print("kept .env")
        return
    with ENV_FILE.open("a") as file:
        if env and not env.endswith("\n"):
            file.write("\n")
        file.write("\n".join(added) + "\n")
    print("added to .env: " + ", ".join(line.partition("=")[0] for line in added))


def new_kek_keyset() -> str:
    aead.register()
    handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    keyset: str = json_proto_keyset_format.serialize(handle, secret_key_access.TOKEN)
    return keyset


def main() -> None:
    sync_env()
    if KEK_FILE.exists():
        print(f"kept {KEK_FILE.relative_to(ROOT)}")
        return
    write_private(KEK_FILE, new_kek_keyset())
    print(f"created {KEK_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
