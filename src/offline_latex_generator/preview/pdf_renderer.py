"""PDF preview renderer — Phase 19.

Converts a :class:`~offline_latex_generator.structurer.models.StructuredDocument`
to a compiled PDF and returns the raw PDF bytes.

Design decisions
----------------
* **Input:**  ``StructuredDocument`` (Phase 15 canonical IR).
* **Output:** Raw PDF ``bytes``; no files are written to the project folder.
* **LaTeX generation:** Delegates entirely to Phase 16 ``generate_latex()``.
  All content preservation guarantees (text, formulas, Greek symbols, physics,
  chemistry, biology notation, special characters, question/option/diagram
  ordering) are inherited from Phase 16 without modification.
* **Diagram handling:** PIL images stored in ``StructuredDocument.diagrams`` are
  saved as PNG files inside a temporary ``images/`` subdirectory during compilation
  only.  They are removed when the temporary directory is cleaned up.
* **Compiler:** Uses the local ``pdflatex`` (or the compiler configured under
  ``latex.compiler`` / ``latex.compiler_path``).  Runs ``latex.compile_runs``
  times (default ``2``) as specified in ``config/default.yaml``.
* **Error handling:** ``PDFPreviewError`` is raised when the compiler binary is
  not found, when any compile run exits with a non-zero return code, when a
  subprocess timeout occurs, or when the output ``document.pdf`` is unexpectedly
  absent after compilation.
* **Cleanup:** ``tempfile.TemporaryDirectory`` guarantees cleanup on both success
  and failure paths — no manual ``try/finally`` required for the directory itself.
* **No mutation:** ``StructuredDocument`` and its PIL images are never modified.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from offline_latex_generator.config import config
from offline_latex_generator.generator import generate_latex
from offline_latex_generator.structurer.models import StructuredDocument

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Public error type
# ---------------------------------------------------------------------------


class PDFPreviewError(RuntimeError):
    """Raised when PDF preview generation fails.

    Possible causes:
    - The LaTeX compiler binary was not found on the system PATH.
    - The LaTeX compiler exited with a non-zero return code.
    - A subprocess timeout occurred during compilation.
    - The compiled ``document.pdf`` output file was unexpectedly absent.
    """


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_compiler() -> str:
    """Return the absolute path to the LaTeX compiler binary.

    Raises
    ------
    PDFPreviewError
        If the compiler binary cannot be found.
    """
    compiler: str = config.get("latex.compiler", "pdflatex")
    compiler_path: str | None = config.get("latex.compiler_path")

    compiler_bin: str | None = None

    if compiler_path:
        candidate = os.path.join(compiler_path, compiler)
        if os.path.isfile(candidate) or os.path.isfile(candidate + ".exe"):
            compiler_bin = candidate

    if not compiler_bin:
        compiler_bin = shutil.which(compiler)

    if not compiler_bin:
        raise PDFPreviewError(
            f"LaTeX compiler '{compiler}' not found on the system PATH. "
            "Install pdflatex (e.g. MiKTeX or TeX Live) to enable PDF preview."
        )

    return compiler_bin


def _run_compile_pass(
    compiler_bin: str,
    tmp_dir: str,
    timeout: int,
) -> None:
    """Execute one pdflatex compilation pass.

    Parameters
    ----------
    compiler_bin:
        Absolute path to the pdflatex (or equivalent) executable.
    tmp_dir:
        Working directory for the subprocess (contains ``document.tex``).
    timeout:
        Maximum seconds to wait for each compiler pass.

    Raises
    ------
    PDFPreviewError
        On subprocess timeout, unexpected subprocess failure, or non-zero
        exit code.
    """
    cmd = [compiler_bin, "-interaction=nonstopmode", "document.tex"]

    try:
        result = subprocess.run(
            cmd,
            cwd=tmp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise PDFPreviewError(
            f"LaTeX compiler timed out after {timeout} seconds."
        )
    except Exception as exc:
        raise PDFPreviewError(
            f"Failed to launch LaTeX compiler subprocess: {exc}"
        ) from exc

    if result.returncode != 0:
        # Extract the first compiler error from the log file if available
        log_path = os.path.join(tmp_dir, "document.log")
        first_error = _extract_first_log_error(log_path)
        if first_error:
            raise PDFPreviewError(
                f"LaTeX compilation failed: {first_error}"
            )
        raise PDFPreviewError(
            f"LaTeX compilation failed with exit code {result.returncode}. "
            f"Stderr: {result.stderr[:500]}"
        )


def _extract_first_log_error(log_path: str) -> str | None:
    """Parse the pdflatex log file and return the first error message, if any."""
    if not os.path.isfile(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("!"):
                return stripped[1:].strip()
    except OSError:
        pass
    return None


def _write_diagram_images(doc: StructuredDocument, tmp_dir: str) -> None:
    """Write PIL diagram images from *doc* to *tmp_dir*/images/ as PNG files.

    Only diagrams that appear in ``StructuredDocument.diagrams`` are written.
    No project-folder writes occur.

    Parameters
    ----------
    doc:
        The structured document whose ``.diagrams`` mapping is read.
    tmp_dir:
        Temporary directory; an ``images/`` subdirectory is created here.
    """
    if not doc.diagrams:
        return

    images_dir = os.path.join(tmp_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    for diagram_id, pil_image in doc.diagrams.items():
        dest = os.path.join(images_dir, f"{diagram_id}.png")
        # Save a copy — never mutate the in-memory PIL image
        pil_image.save(dest, format="PNG")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_pdf_preview(doc: StructuredDocument) -> bytes:
    """Compile a ``StructuredDocument`` to PDF and return the raw PDF bytes.

    The entire compilation takes place inside a ``tempfile.TemporaryDirectory``
    that is automatically removed — on success *and* on error — when the
    function returns.  No files are written to the project folder.

    Parameters
    ----------
    doc:
        The structured document produced by Phase 15 (``build_document``).

    Returns
    -------
    bytes
        Raw PDF file contents as a byte string.

    Raises
    ------
    PDFPreviewError
        If the LaTeX compiler binary is not found, if any compilation pass
        fails, if a subprocess timeout occurs, or if the output PDF file is
        unexpectedly absent after compilation.

    Notes
    -----
    * ``StructuredDocument`` and its PIL images are never modified.
    * Content preservation (text, formulas, Greek symbols, physics/chemistry/
      biology notation, special characters, question/option/diagram ordering)
      is guaranteed by Phase 16 ``generate_latex()``.
    * The number of compiler passes is controlled by ``latex.compile_runs``
      in ``config/default.yaml`` (default ``2``).
    """
    # 1. Resolve compiler early — raises PDFPreviewError if not found
    compiler_bin = _resolve_compiler()

    # 2. Read configuration
    compile_runs: int = int(config.get("latex.compile_runs", 2))
    timeout: int = 60  # seconds per compiler pass

    # 3. Generate LaTeX string (Phase 16 — all content preservation happens here)
    latex_str = generate_latex(doc)
    if not doc.preamble and not doc.questions:
        latex_str = latex_str.replace(r"\begin{document}", r"\begin{document}" + "\n\\null")

    # 4. Compile inside a temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 4a. Write real diagram images to tmp/images/
        _write_diagram_images(doc, tmp_dir)

        # 4b. Write LaTeX source
        tex_path = os.path.join(tmp_dir, "document.tex")
        with open(tex_path, "w", encoding="utf-8") as fh:
            fh.write(latex_str)

        # 4c. Run configured number of compiler passes
        for _ in range(max(1, compile_runs)):
            _run_compile_pass(compiler_bin, tmp_dir, timeout)

        # 4d. Read the generated PDF into memory before cleanup
        pdf_path = os.path.join(tmp_dir, "document.pdf")
        if not os.path.isfile(pdf_path):
            raise PDFPreviewError(
                "Compilation succeeded (exit code 0) but 'document.pdf' was "
                "not produced. Check the LaTeX log for details."
            )

        with open(pdf_path, "rb") as fh:
            pdf_bytes = fh.read()

    # 5. Temporary directory has been removed; return PDF bytes
    return pdf_bytes


__all__ = ["PDFPreviewError", "generate_pdf_preview"]
