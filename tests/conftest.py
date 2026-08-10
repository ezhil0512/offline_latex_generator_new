import os
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
POPPLER_VERSION = "26.02.0-0"
PROJECT_POPPLER_BIN = (
    PROJECT_ROOT
    / ".cache"
    / "poppler-windows"
    / POPPLER_VERSION
    / f"poppler-{POPPLER_VERSION.split('-')[0]}"
    / "Library"
    / "bin"
)


def _has_poppler(bin_path: Path) -> bool:
    return (bin_path / "pdfinfo.exe").is_file() and (bin_path / "pdftoppm.exe").is_file()


def _is_miktex_command(command_path: str | None) -> bool:
    return bool(command_path and "miktex" in command_path.lower())


def pytest_configure(config):
    if sys.platform != "win32":
        return

    configured = os.environ.get("POPPLER_PATH")
    if configured and _has_poppler(Path(configured)):
        poppler_bin = Path(configured)
    else:
        path_pdfinfo = shutil.which("pdfinfo")
        path_pdftoppm = shutil.which("pdftoppm")
        if (
            path_pdfinfo
            and path_pdftoppm
            and not _is_miktex_command(path_pdfinfo)
            and not _is_miktex_command(path_pdftoppm)
        ):
            return

        if not _has_poppler(PROJECT_POPPLER_BIN):
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "install_poppler_windows.py")],
                check=True,
            )
        poppler_bin = PROJECT_POPPLER_BIN

    os.environ["POPPLER_PATH"] = str(poppler_bin)
    os.environ["PATH"] = str(poppler_bin) + os.pathsep + os.environ.get("PATH", "")
