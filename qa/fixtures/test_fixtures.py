"""QA-01 fixture checks: manifest integrity, claimed properties, determinism.

Run from the repo root:
    uv run --with pytest==9.2.0 --with 'pypdf[crypto]==7.0.1' pytest qa/fixtures
pypdf needs the crypto extra to open AES-encrypted files at all.
"""

import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path

import pypdf
import pytest
from pypdf import PasswordType
from pypdf.errors import PdfReadError

FIXTURES_DIR = Path(__file__).resolve().parent
REPO_ROOT = FIXTURES_DIR.parents[1]
MANIFEST = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
SOURCES = MANIFEST["sources"]
GENERATED = MANIFEST["generated"]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GENERATOR_TIMEOUT_S = 300


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_generator(out: Path) -> None:
    subprocess.run(
        ["uv", "run", "--quiet", str(FIXTURES_DIR / "generate.py"), "--out", str(out)],
        check=True,
        timeout=GENERATOR_TIMEOUT_S,
    )


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("generated")
    run_generator(out)
    return out


@pytest.mark.parametrize("entry", SOURCES, ids=lambda entry: Path(entry["path"]).name)
def test_source_matches_manifest(entry: dict) -> None:
    path = REPO_ROOT / entry["path"]
    assert path.stat().st_size == entry["size_bytes"]
    assert sha256(path) == entry["sha256"]


def test_expected_order_follows_default_sort() -> None:
    # TZ-backend §3.6: document date desc, ties in upload order, undated last.
    # Sources are listed in upload order.
    def sort_key(upload_index: int) -> tuple[bool, int, int]:
        document_date = SOURCES[upload_index]["document_date"]
        ordinal = date.fromisoformat(document_date).toordinal() if document_date else 0
        return document_date is None, -ordinal, upload_index

    positions = range(len(SOURCES))
    sorted_uploads = sorted(positions, key=sort_key)
    assert [SOURCES[i]["expected_order"] for i in sorted_uploads] == list(positions)


@pytest.mark.parametrize("entry", GENERATED, ids=lambda entry: entry["name"])
def test_generated_matches_manifest(generated: Path, entry: dict) -> None:
    path = generated / entry["name"]
    assert path.stat().st_size == entry["size_bytes"]
    assert sha256(path) == entry["sha256"]


def test_big_is_valid_pdf_above_upload_limit(generated: Path) -> None:
    path = generated / "big-21mb.pdf"
    assert path.stat().st_size > MANIFEST["upload_limit_bytes"]
    assert len(pypdf.PdfReader(path, strict=True).pages) == 1


def test_fake_is_png_without_pdf_signature(generated: Path) -> None:
    data = (generated / "fake.pdf").read_bytes()
    assert data.startswith(PNG_SIGNATURE)
    assert not data.startswith(b"%PDF-")


def test_encrypted_uses_aes256_with_known_password(generated: Path) -> None:
    reader = pypdf.PdfReader(generated / "encrypted.pdf")
    assert reader.is_encrypted
    encrypt = reader.trailer["/Encrypt"]
    assert (encrypt["/V"], encrypt["/R"]) == (5, 6)
    assert reader.decrypt("wrong") == PasswordType.NOT_DECRYPTED
    assert reader.decrypt("secret") != PasswordType.NOT_DECRYPTED
    assert len(reader.pages) == 1


def test_broken_has_signature_but_does_not_open(generated: Path) -> None:
    path = generated / "broken.pdf"
    assert path.read_bytes().startswith(b"%PDF-")
    with pytest.raises(PdfReadError):
        pypdf.PdfReader(path)


def test_cyrillic_is_byte_copy_of_first_source(generated: Path) -> None:
    source = REPO_ROOT / SOURCES[0]["path"]
    assert (generated / "cyrillic «имя» файла.pdf").read_bytes() == source.read_bytes()


def test_generator_is_deterministic(generated: Path, tmp_path: Path) -> None:
    run_generator(tmp_path)
    first = {path.name: sha256(path) for path in generated.iterdir()}
    second = {path.name: sha256(path) for path in tmp_path.iterdir()}
    assert first == second
    assert set(first) == {entry["name"] for entry in GENERATED}
