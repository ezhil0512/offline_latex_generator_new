"""Unit tests for Phase 19: PDF Preview.

All tests build StructuredDocument objects purely in memory.
Compiler subprocess execution is mocked — no real pdflatex is required.
No files are written to the permanent project folder during any test.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest
from PIL import Image

from offline_latex_generator.preview import PDFPreviewError, generate_pdf_preview
from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_DUMMY_BBOX = (0.0, 0.0, 10.0, 10.0)

# Minimal valid PDF bytes (just enough for the tests that check the type)
_FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf for testing"


def make_text(text: str, page: int = 0) -> ContentItem:
    return ContentItem(
        kind="text",
        text=text,
        latex=None,
        diagram_id=None,
        bbox=_DUMMY_BBOX,
        block_index=0,
        source_page=page,
    )


def make_formula(latex: str) -> ContentItem:
    return ContentItem(
        kind="formula",
        text=None,
        latex=latex,
        diagram_id=None,
        bbox=_DUMMY_BBOX,
        block_index=0,
    )


def make_diagram_item(diagram_id: str) -> ContentItem:
    return ContentItem(
        kind="diagram",
        text=None,
        latex=None,
        diagram_id=diagram_id,
        bbox=_DUMMY_BBOX,
        block_index=0,
    )


def small_pil_image(color: tuple = (255, 0, 0, 255)) -> Image.Image:
    """Return a tiny valid 4×4 PIL image."""
    return Image.new("RGBA", (4, 4), color=color)


def make_simple_doc() -> StructuredDocument:
    """StructuredDocument with one plain-text question and no diagrams."""
    doc = StructuredDocument(pages=1)
    q = StructuredQuestion(
        question_number="1",
        body=(make_text("What is 2+2?"),),
        options=(
            StructuredOption("A", (make_text("3"),)),
            StructuredOption("B", (make_text("4"),)),
        ),
    )
    doc.questions.append(q)
    return doc


def make_formula_doc() -> StructuredDocument:
    """StructuredDocument with Greek symbols and physics notation."""
    doc = StructuredDocument(pages=1)
    body = (
        make_text("Evaluate:"),
        make_formula(r"\int_0^\infty e^{-x}\,dx"),
        make_formula(r"\alpha + \beta = \gamma"),
        make_formula(r"\frac{d}{dt}\vec{F} = m\vec{a}"),
    )
    q = StructuredQuestion("1", body, ())
    doc.questions.append(q)
    return doc


def make_diagram_doc(
    diag_id: str = "diagram_001",
) -> StructuredDocument:
    """StructuredDocument with one diagram in question body."""
    img = small_pil_image()
    q = StructuredQuestion(
        "1",
        (make_text("See diagram:"), make_diagram_item(diag_id)),
        (),
    )
    doc = StructuredDocument(pages=1)
    doc.questions.append(q)
    doc.diagrams[diag_id] = img
    return doc


def make_multi_diagram_doc() -> StructuredDocument:
    """StructuredDocument with two diagrams in different positions."""
    img1 = small_pil_image((255, 0, 0, 255))
    img2 = small_pil_image((0, 255, 0, 255))

    opt_a = StructuredOption("A", (make_text("Option A"),))
    opt_b = StructuredOption(
        "B",
        (make_text("Option B"), make_diagram_item("diagram_002")),
    )
    q = StructuredQuestion(
        "1",
        (make_text("Stem"), make_diagram_item("diagram_001")),
        (opt_a, opt_b),
    )
    doc = StructuredDocument(pages=1)
    doc.questions.append(q)
    doc.diagrams["diagram_001"] = img1
    doc.diagrams["diagram_002"] = img2
    return doc


# ---------------------------------------------------------------------------
# Context-manager mock for tempfile.TemporaryDirectory
# ---------------------------------------------------------------------------


class _MockTmpDir:
    """A mock TemporaryDirectory whose name is a real temp folder on disk.

    Creates an actual temp dir so that file operations inside the
    implementation (os.path.join, open, os.makedirs) work correctly,
    while still being cleaned up after each test.

    ``__enter__`` returns ``self.name`` (a ``str``) to match the real
    ``tempfile.TemporaryDirectory`` context-manager protocol, which yields
    the directory path string — not the manager object itself.
    """

    def __init__(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.name = self._td.name

    def __enter__(self) -> str:
        self._td.__enter__()
        # Must return the string path, NOT self, so that the implementation's
        # `with tempfile.TemporaryDirectory() as tmp_dir:` binds a str.
        return self.name

    def __exit__(self, *args: Any) -> None:
        self._td.__exit__(*args)

    def cleanup(self) -> None:  # noqa: D401
        self._td.cleanup()


# ---------------------------------------------------------------------------
# Helper: patch everything needed for a successful compile
# ---------------------------------------------------------------------------


def _successful_compile_mocks(
    tmp_dir_obj: _MockTmpDir,
    compile_runs: int = 2,
):
    """Return a dict of patch kwargs that simulate a successful pdflatex run.

    After each compile pass the mock writes a fake document.pdf into the
    temp directory so the implementation's existence check passes.
    """
    def _fake_run(cmd, cwd, stdout, stderr, text, timeout):
        # Write fake PDF so the existence check passes
        pdf_path = os.path.join(cwd, "document.pdf")
        with open(pdf_path, "wb") as fh:
            fh.write(_FAKE_PDF_BYTES)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        return mock_result

    return _fake_run


# ---------------------------------------------------------------------------
# 1. Return type — successful PDF bytes
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewReturnType:

    def test_returns_bytes_on_success(self, tmp_path):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            pdf_path = os.path.join(cwd, "document.pdf")
            Path(pdf_path).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = generate_pdf_preview(doc)

        assert isinstance(result, bytes)

    def test_bytes_are_nonempty_on_success(self, tmp_path):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = generate_pdf_preview(doc)

        assert len(result) > 0

    def test_returned_bytes_match_pdf_file_content(self):
        doc = make_simple_doc()
        td = _MockTmpDir()
        expected = b"%PDF-1.4 exact content check"

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(expected)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = generate_pdf_preview(doc)

        assert result == expected


# ---------------------------------------------------------------------------
# 2. Missing compiler → PDFPreviewError
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewMissingCompiler:

    def test_raises_pdf_preview_error_when_compiler_absent(self):
        doc = make_simple_doc()
        with (
            patch("shutil.which", return_value=None),
            patch(
                "offline_latex_generator.preview.pdf_renderer.config.get",
                side_effect=lambda key, default=None: (
                    "pdflatex" if key == "latex.compiler" else
                    None if key == "latex.compiler_path" else
                    default
                ),
            ),
        ):
            with pytest.raises(PDFPreviewError, match="not found"):
                generate_pdf_preview(doc)

    def test_error_is_runtime_error_subclass(self):
        doc = make_simple_doc()
        with (
            patch("shutil.which", return_value=None),
            patch(
                "offline_latex_generator.preview.pdf_renderer.config.get",
                side_effect=lambda key, default=None: (
                    "pdflatex" if key == "latex.compiler" else
                    None if key == "latex.compiler_path" else
                    default
                ),
            ),
        ):
            with pytest.raises(RuntimeError):
                generate_pdf_preview(doc)

    def test_error_mentions_compiler_name(self):
        doc = make_simple_doc()
        with (
            patch("shutil.which", return_value=None),
            patch(
                "offline_latex_generator.preview.pdf_renderer.config.get",
                side_effect=lambda key, default=None: (
                    "xelatex" if key == "latex.compiler" else
                    None if key == "latex.compiler_path" else
                    default
                ),
            ),
        ):
            with pytest.raises(PDFPreviewError, match="xelatex"):
                generate_pdf_preview(doc)


# ---------------------------------------------------------------------------
# 3. Compilation failure → PDFPreviewError
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewCompilationFailure:

    def test_raises_pdf_preview_error_on_nonzero_exit(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            r = MagicMock()
            r.returncode = 1
            r.stderr = "! Emergency stop."
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(PDFPreviewError):
                generate_pdf_preview(doc)

    def test_error_message_contains_exit_info(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            r = MagicMock()
            r.returncode = 2
            r.stderr = "bad syntax"
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(PDFPreviewError, match="fail"):
                generate_pdf_preview(doc)

    def test_raises_on_timeout(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch(
                "subprocess.run",
                side_effect=__import__("subprocess").TimeoutExpired(
                    cmd="pdflatex", timeout=60
                ),
            ),
        ):
            with pytest.raises(PDFPreviewError, match="timed out"):
                generate_pdf_preview(doc)

    def test_raises_on_subprocess_os_error(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch(
                "subprocess.run",
                side_effect=OSError("executable not found"),
            ),
        ):
            with pytest.raises(PDFPreviewError, match="launch"):
                generate_pdf_preview(doc)

    def test_raises_pdf_preview_error_when_pdf_missing_after_success(self):
        """Compiler exits 0 but document.pdf is never written."""
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            # Do NOT write document.pdf — simulate a silent failure
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(PDFPreviewError, match="document.pdf"):
                generate_pdf_preview(doc)


# ---------------------------------------------------------------------------
# 4. Diagram images written to temporary images/ directory
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewDiagramImages:

    def test_diagram_written_to_images_subdir(self):
        doc = make_diagram_doc("diagram_001")
        td = _MockTmpDir()
        written_paths: list[str] = []

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            # Record which PNG files exist at compile time
            images_dir = os.path.join(cwd, "images")
            if os.path.isdir(images_dir):
                for f in os.listdir(images_dir):
                    written_paths.append(os.path.join(images_dir, f))
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert any("diagram_001.png" in p for p in written_paths)

    def test_multiple_diagrams_written(self):
        doc = make_multi_diagram_doc()
        td = _MockTmpDir()
        found_files: set[str] = set()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            images_dir = os.path.join(cwd, "images")
            if os.path.isdir(images_dir):
                found_files.update(os.listdir(images_dir))
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert "diagram_001.png" in found_files
        assert "diagram_002.png" in found_files

    def test_written_diagram_is_valid_png(self):
        doc = make_diagram_doc("diagram_001")
        td = _MockTmpDir()
        captured: dict[str, bytes] = {}

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            png_path = os.path.join(cwd, "images", "diagram_001.png")
            if os.path.isfile(png_path):
                with open(png_path, "rb") as fh:
                    captured["png_bytes"] = fh.read()
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert "png_bytes" in captured
        # PNG magic bytes
        assert captured["png_bytes"][:8] == b"\x89PNG\r\n\x1a\n"

    def test_no_images_dir_created_when_no_diagrams(self):
        doc = make_simple_doc()  # no diagrams
        td = _MockTmpDir()
        images_dir_existed: list[bool] = []

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            images_dir_existed.append(os.path.isdir(os.path.join(cwd, "images")))
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert not any(images_dir_existed)


# ---------------------------------------------------------------------------
# 5. No permanent project-folder writes
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewNoFilesystemWrites:

    def test_project_directory_unchanged_on_success(self):
        """Verify no .pdf files appear in src/ after a successful call."""
        doc = make_diagram_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        # Only scan src/ to avoid traversing .venv (very slow on Windows)
        src_root = Path(__file__).resolve().parents[3] / "src"
        before = set(src_root.rglob("*.pdf"))

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        after = set(src_root.rglob("*.pdf"))
        assert before == after, f"Unexpected PDFs written: {after - before}"

    def test_no_tex_file_in_project_folder(self):
        """Verify no document.tex appears in src/ after a call."""
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        # Only scan src/ to avoid traversing .venv (very slow on Windows)
        src_root = Path(__file__).resolve().parents[3] / "src"
        before_tex = set(src_root.rglob("document.tex"))

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        after_tex = set(src_root.rglob("document.tex"))
        assert before_tex == after_tex


# ---------------------------------------------------------------------------
# 6. Cleanup after success
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewCleanupOnSuccess:

    def test_temp_dir_cleaned_up_after_success(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        temp_name = td.name

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        # The real _MockTmpDir is cleaned by its own __exit__; verify its
        # directory no longer exists after the call.
        assert not os.path.isdir(temp_name)


# ---------------------------------------------------------------------------
# 7. Cleanup after failure
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewCleanupOnFailure:

    def test_temp_dir_cleaned_up_after_compile_failure(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            r = MagicMock()
            r.returncode = 1
            r.stderr = "error"
            return r

        temp_name = td.name

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            with pytest.raises(PDFPreviewError):
                generate_pdf_preview(doc)

        assert not os.path.isdir(temp_name)

    def test_temp_dir_cleaned_up_after_missing_compiler(self):
        doc = make_simple_doc()
        # Temp dir is not even created when compiler is absent; just verify no error.
        with (
            patch("shutil.which", return_value=None),
            patch(
                "offline_latex_generator.preview.pdf_renderer.config.get",
                side_effect=lambda key, default=None: (
                    "pdflatex" if key == "latex.compiler" else
                    None if key == "latex.compiler_path" else
                    default
                ),
            ),
        ):
            with pytest.raises(PDFPreviewError):
                generate_pdf_preview(doc)
        # If we reach here the error was raised cleanly; no hung temp dirs.


# ---------------------------------------------------------------------------
# 8. generate_latex() delegation
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewDelegation:

    def test_generate_latex_called_with_doc(self):
        doc = make_simple_doc()
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
            patch(
                "offline_latex_generator.preview.pdf_renderer.generate_latex",
                wraps=__import__(
                    "offline_latex_generator.generator",
                    fromlist=["generate_latex"],
                ).generate_latex,
            ) as mock_gen,
        ):
            generate_pdf_preview(doc)

        mock_gen.assert_called_once_with(doc)

    def test_latex_written_to_document_tex(self):
        doc = make_simple_doc()
        td = _MockTmpDir()
        captured_tex: dict[str, str] = {}

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            tex_path = os.path.join(cwd, "document.tex")
            if os.path.isfile(tex_path):
                with open(tex_path, "r", encoding="utf-8") as fh:
                    captured_tex["content"] = fh.read()
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert "content" in captured_tex
        assert r"\documentclass" in captured_tex["content"]


# ---------------------------------------------------------------------------
# 9. compile_runs
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewCompileRuns:

    def _run_with_compile_runs(self, doc, runs: int):
        td = _MockTmpDir()
        call_count: list[int] = [0]

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            call_count[0] += 1
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
            patch(
                "offline_latex_generator.preview.pdf_renderer.config.get",
                side_effect=lambda key, default=None: (
                    "pdflatex" if key == "latex.compiler" else
                    None if key == "latex.compiler_path" else
                    runs if key == "latex.compile_runs" else
                    default
                ),
            ),
        ):
            generate_pdf_preview(doc)

        return call_count[0]

    def test_pdflatex_called_twice_by_default(self):
        doc = make_simple_doc()
        count = self._run_with_compile_runs(doc, runs=2)
        assert count == 2

    def test_pdflatex_called_once_when_compile_runs_is_1(self):
        doc = make_simple_doc()
        count = self._run_with_compile_runs(doc, runs=1)
        assert count == 1

    def test_pdflatex_called_three_times_when_compile_runs_is_3(self):
        doc = make_simple_doc()
        count = self._run_with_compile_runs(doc, runs=3)
        assert count == 3


# ---------------------------------------------------------------------------
# 10. Empty StructuredDocument
# ---------------------------------------------------------------------------


class TestGeneratePdfPreviewEmptyDocument:

    def test_empty_document_returns_bytes(self):
        doc = StructuredDocument(pages=1)  # no questions, no preamble
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            result = generate_pdf_preview(doc)

        assert isinstance(result, bytes)

    def test_empty_document_does_not_raise(self):
        doc = StructuredDocument(pages=0)
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            # Must not raise
            generate_pdf_preview(doc)


# ---------------------------------------------------------------------------
# 11. StructuredDocument not mutated
# ---------------------------------------------------------------------------


class TestStructuredDocumentNotMutated:

    def test_questions_list_unchanged(self):
        doc = make_simple_doc()
        original_questions = list(doc.questions)
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert list(doc.questions) == original_questions

    def test_diagrams_dict_unchanged(self):
        doc = make_diagram_doc("diagram_001")
        original_diag_ids = set(doc.diagrams.keys())
        original_img = doc.diagrams["diagram_001"]
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert set(doc.diagrams.keys()) == original_diag_ids
        # Same object — not replaced or mutated
        assert doc.diagrams["diagram_001"] is original_img

    def test_pil_image_pixel_unchanged(self):
        doc = make_diagram_doc("diagram_001")
        img = doc.diagrams["diagram_001"]
        original_pixel = img.getpixel((0, 0))
        td = _MockTmpDir()

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        assert img.getpixel((0, 0)) == original_pixel


# ---------------------------------------------------------------------------
# 12. Content preservation (delegation check)
# ---------------------------------------------------------------------------


class TestContentPreservation:

    def _get_compiled_tex(self, doc: StructuredDocument) -> str:
        """Run generate_pdf_preview with a mock and capture the .tex content."""
        td = _MockTmpDir()
        captured: dict[str, str] = {}

        def fake_run(cmd, cwd, stdout, stderr, text, timeout):
            tex_path = os.path.join(cwd, "document.tex")
            if os.path.isfile(tex_path):
                with open(tex_path, "r", encoding="utf-8") as fh:
                    captured["tex"] = fh.read()
            Path(os.path.join(cwd, "document.pdf")).write_bytes(_FAKE_PDF_BYTES)
            r = MagicMock()
            r.returncode = 0
            r.stderr = ""
            return r

        with (
            patch("shutil.which", return_value="/usr/bin/pdflatex"),
            patch(
                "offline_latex_generator.preview.pdf_renderer.tempfile.TemporaryDirectory",
                return_value=td,
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            generate_pdf_preview(doc)

        return captured.get("tex", "")

    def test_greek_symbols_in_tex(self):
        doc = make_formula_doc()
        tex = self._get_compiled_tex(doc)
        assert r"\alpha" in tex
        assert r"\beta" in tex
        assert r"\gamma" in tex

    def test_physics_notation_in_tex(self):
        doc = make_formula_doc()
        tex = self._get_compiled_tex(doc)
        assert r"\int_0^\infty" in tex
        assert r"\frac{d}{dt}" in tex

    def test_question_order_preserved_in_tex(self):
        doc = StructuredDocument(pages=1)
        for i in (1, 2, 3):
            q = StructuredQuestion(
                str(i),
                (make_text(f"Question {i}"),),
                (),
            )
            doc.questions.append(q)

        tex = self._get_compiled_tex(doc)
        pos1 = tex.index("Question 1")
        pos2 = tex.index("Question 2")
        pos3 = tex.index("Question 3")
        assert pos1 < pos2 < pos3

    def test_option_order_preserved_in_tex(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion(
            "1",
            (make_text("Stem"),),
            (
                StructuredOption("A", (make_text("Alpha"),)),
                StructuredOption("B", (make_text("Bravo"),)),
                StructuredOption("C", (make_text("Charlie"),)),
                StructuredOption("D", (make_text("Delta"),)),
            ),
        )
        doc.questions.append(q)

        tex = self._get_compiled_tex(doc)
        assert tex.index("Alpha") < tex.index("Bravo") < tex.index("Charlie") < tex.index("Delta")

    def test_diagram_in_question_body_in_tex(self):
        doc = make_diagram_doc("diagram_001")
        tex = self._get_compiled_tex(doc)
        assert "diagram_001" in tex
        assert r"\includegraphics" in tex

    def test_diagram_in_option_body_in_tex(self):
        doc = make_multi_diagram_doc()
        tex = self._get_compiled_tex(doc)
        # Both diagrams must appear in the LaTeX
        assert "diagram_001" in tex
        assert "diagram_002" in tex

    def test_special_characters_escaped_in_tex(self):
        doc = StructuredDocument(pages=1)
        q = StructuredQuestion(
            "1",
            (make_text("100% correct & valid"),),
            (),
        )
        doc.questions.append(q)
        tex = self._get_compiled_tex(doc)
        # Escaped by Phase 16 generate_latex
        assert r"\%" in tex
        assert r"\&" in tex


# ---------------------------------------------------------------------------
# 13. Public import surface
# ---------------------------------------------------------------------------


class TestPublicImportSurface:

    def test_pdf_preview_error_importable_from_preview(self):
        from offline_latex_generator.preview import PDFPreviewError  # noqa: F401

    def test_generate_pdf_preview_importable_from_preview(self):
        from offline_latex_generator.preview import generate_pdf_preview  # noqa: F401

    def test_pdf_preview_error_is_runtime_error(self):
        assert issubclass(PDFPreviewError, RuntimeError)

    def test_generate_pdf_preview_is_callable(self):
        assert callable(generate_pdf_preview)
