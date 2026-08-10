#!/usr/bin/env python3
"""
Install a project-local Poppler build for Windows development and tests.

The files are downloaded into .cache/, which is ignored by git. The script is
safe to run repeatedly and prints the Poppler bin path for POPPLER_PATH.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


VERSION = "26.02.0-0"
ZIP_NAME = f"Release-{VERSION}.zip"
DOWNLOAD_URL = (
    "https://github.com/oschwartz10612/poppler-windows/releases/download/"
    f"v{VERSION}/{ZIP_NAME}"
)
SHA256 = "993e4a94376ed712fafc7058d724ea0b943d118bbd2305cd9ed55174eb85cda5"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = PROJECT_ROOT / ".cache" / "poppler-windows"
INSTALL_ROOT = CACHE_ROOT / VERSION
POPPLER_BIN = INSTALL_ROOT / f"poppler-{VERSION.split('-')[0]}" / "Library" / "bin"


def has_poppler(bin_path: Path) -> bool:
    return (bin_path / "pdfinfo.exe").is_file() and (bin_path / "pdftoppm.exe").is_file()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        with target.open("wb") as file:
            shutil.copyfileobj(response, file)


def install() -> Path:
    if has_poppler(POPPLER_BIN):
        return POPPLER_BIN

    with tempfile.TemporaryDirectory(prefix="olg-poppler-") as tmp:
        archive_path = Path(tmp) / ZIP_NAME
        print(f"Downloading Poppler {VERSION}...")
        download(DOWNLOAD_URL, archive_path)

        actual_hash = sha256_file(archive_path)
        if actual_hash.lower() != SHA256.lower():
            raise RuntimeError(
                f"Hash mismatch for {ZIP_NAME}: expected {SHA256}, got {actual_hash}"
            )

        if INSTALL_ROOT.exists():
            shutil.rmtree(INSTALL_ROOT)
        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(INSTALL_ROOT)

    if not has_poppler(POPPLER_BIN):
        raise RuntimeError(f"Poppler install did not create expected bin path: {POPPLER_BIN}")

    return POPPLER_BIN


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This helper is only needed on Windows.")

    bin_path = install()
    print(f"POPPLER_PATH={bin_path}")


if __name__ == "__main__":
    main()
