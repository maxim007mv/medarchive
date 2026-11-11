# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pypdf==7.0.1", "cryptography==50.0.2"]
# ///
"""Generate the upload edge-case fixtures for QA-01.

Run from the repo root: uv run qa/fixtures/generate.py [--out DIR]
The output is byte-identical on every run; see manifest.json for hashes.
"""

import argparse
import io
import random
import secrets
from pathlib import Path
from unittest import mock

import pypdf

FIXTURES_DIR = Path(__file__).resolve().parent
SOURCE_PDF = (
    FIXTURES_DIR.parents[1] / "MedArchive/05_qa/fixtures/01-general-blood-test.pdf"
)
DEFAULT_OUT = FIXTURES_DIR / "generated"

BIG_SIZE_BYTES = 22_020_097  # 21 MiB + 1 byte, above the 20 MiB upload limit
ENCRYPTION_PASSWORD = "secret"
ENCRYPTION_SEED = 1
PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108000000003a7e9b55"
    "0000000a4944415478da6360000000020001e527defc0000000049454e44ae426082"
)


def minimal_pdf(content: bytes) -> bytes:
    """One-page PDF whose page content stream is `content`, with a correct xref table."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    pdf += b"startxref\n%d\n%%%%EOF\n" % xref_offset
    return bytes(pdf)


def padded_pdf(size_bytes: int) -> bytes:
    """Valid PDF of exactly `size_bytes`, padded with whitespace in the content stream."""
    padding = size_bytes - len(minimal_pdf(b""))
    # Second pass absorbs the extra digits of /Length and startxref.
    padding -= len(minimal_pdf(b" " * padding)) - size_bytes
    pdf = minimal_pdf(b" " * padding)
    if len(pdf) != size_bytes:
        raise RuntimeError(f"padded PDF is {len(pdf)} bytes, expected {size_bytes}")
    return pdf


def encrypted_pdf(source: bytes) -> bytes:
    writer = pypdf.PdfWriter(clone_from=io.BytesIO(source))
    buffer = io.BytesIO()
    # pypdf takes the file key, salts, AES IVs and /ID from secrets.token_bytes.
    # A seeded stream makes the file reproducible; the password is public anyway.
    seeded = random.Random(ENCRYPTION_SEED)
    with mock.patch.object(secrets, "token_bytes", seeded.randbytes):
        writer.encrypt(ENCRYPTION_PASSWORD, algorithm="AES-256")
        writer.write(buffer)
    return buffer.getvalue()


def build_fixtures(source: bytes) -> dict[str, bytes]:
    return {
        "big-21mb.pdf": padded_pdf(BIG_SIZE_BYTES),
        "fake.pdf": PNG_1X1,
        "encrypted.pdf": encrypted_pdf(source),
        "broken.pdf": source[: len(source) // 2],
        "cyrillic «имя» файла.pdf": source,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="output directory"
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    fixtures = build_fixtures(SOURCE_PDF.read_bytes())
    for name, data in fixtures.items():
        (args.out / name).write_bytes(data)
    print(f"wrote {len(fixtures)} fixtures to {args.out}")


if __name__ == "__main__":
    main()
