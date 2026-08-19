"""Unit tests for backend Web API integration routes.

Covers:
- GET /
- POST /api/jobs/<job_id>/process
- GET /api/jobs/<job_id>/preview/html
- GET /api/jobs/<job_id>/preview/pdf
- GET /api/jobs/<job_id>/latex
- Error states: unknown job (404), no uploaded file (400), preview before processing (409), processing failure (500)
- Correct response content-types
- Formula/science content preservation
- Diagram in-memory handling
- Verification that no files are permanently written to the project folder
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from offline_latex_generator.main import create_app
from offline_latex_generator.preview import PDFPreviewError
from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)
from offline_latex_generator.web.workspace_routes import (
    remove_job_document,
    store_job_document,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


_DUMMY_BBOX = (0.0, 0.0, 10.0, 10.0)


def make_dummy_doc() -> StructuredDocument:
    """Return a valid StructuredDocument for testing."""
    img = Image.new("RGBA", (4, 4), color=(255, 0, 0, 255))
    doc = StructuredDocument(pages=1)
    q = StructuredQuestion(
        question_number="1",
        body=(
            ContentItem(
                kind="text",
                text="What is 2+2?",
                latex=None,
                diagram_id=None,
                bbox=_DUMMY_BBOX,
                block_index=0,
            ),
            ContentItem(
                kind="formula",
                text=None,
                latex=r"\alpha + \beta = \gamma",
                diagram_id=None,
                bbox=_DUMMY_BBOX,
                block_index=1,
            ),
            ContentItem(
                kind="diagram",
                text=None,
                latex=None,
                diagram_id="diagram_001",
                bbox=_DUMMY_BBOX,
                block_index=2,
            ),
        ),
        options=(
            StructuredOption(
                label="A",
                body=(
                    ContentItem(
                        kind="text",
                        text="4",
                        latex=None,
                        diagram_id=None,
                        bbox=_DUMMY_BBOX,
                        block_index=3,
                    ),
                ),
            ),
        ),
    )
    doc.questions.append(q)
    doc.diagrams["diagram_001"] = img
    return doc


# ---------------------------------------------------------------------------
# 1. GET / Index Route
# ---------------------------------------------------------------------------


class TestIndexRoute:

    def test_get_index_returns_200(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        assert "<!DOCTYPE html>" in res.text

    def test_get_index_when_template_exists(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "Offline LaTeX Generator" in res.text


# ---------------------------------------------------------------------------
# 2. POST /api/jobs/<job_id>/process Pipeline Execution
# ---------------------------------------------------------------------------


class TestProcessJobRoute:

    def test_process_job_unknown_id_returns_404(self, client):
        res = client.post("/api/jobs/nonexistentjob123/process")
        assert res.status_code == 404
        assert "not found" in res.json["error"]

    def test_process_job_no_file_returns_400(self, client):
        # Create job without uploading a file
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        res = client.post(f"/api/jobs/{job_id}/process")
        assert res.status_code == 400
        assert "No uploaded input file" in res.json["error"]

    def test_process_job_success(self, client):
        # 1. Create job
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        # 2. Upload file
        file_data = (io.BytesIO(b"fake image data"), "sample.png")
        upload_res = client.post(
            f"/api/jobs/{job_id}/upload",
            data={"file": file_data},
            content_type="multipart/form-data",
        )
        assert upload_res.status_code == 200

        # 3. Process with mocked pipeline
        dummy_doc = make_dummy_doc()
        with patch(
            "offline_latex_generator.web.workspace_routes.run_pipeline",
            return_value=dummy_doc,
        ) as mock_pipeline:
            proc_res = client.post(f"/api/jobs/{job_id}/process")
            assert proc_res.status_code == 200
            data = proc_res.json
            assert data["job_id"] == job_id
            assert data["status"] == "completed"
            assert data["pages"] == 1
            assert data["questions_count"] == 1
            mock_pipeline.assert_called_once_with(job_id, "sample.png")

    def test_run_pipeline_real_image_loader(self, client):
        # 1. Create job
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        # 2. Upload valid PNG image
        buf = io.BytesIO()
        Image.new("RGB", (20, 20), color="white").save(buf, format="PNG")
        buf.seek(0)

        upload_res = client.post(
            f"/api/jobs/{job_id}/upload",
            data={"file": (buf, "valid.png")},
            content_type="multipart/form-data",
        )
        assert upload_res.status_code == 200

        # 3. Call process with OCRRouter mocked to test real ImageLoader call cleanly
        with patch("offline_latex_generator.pipeline.runner.OCRRouter.route", return_value=[]):
            proc_res = client.post(f"/api/jobs/{job_id}/process")
            assert proc_res.status_code == 200
            assert proc_res.json["status"] == "completed"

    def test_process_job_failure_returns_500(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        file_data = (io.BytesIO(b"fake image data"), "sample.png")
        client.post(
            f"/api/jobs/{job_id}/upload",
            data={"file": file_data},
            content_type="multipart/form-data",
        )

        with patch(
            "offline_latex_generator.web.workspace_routes.run_pipeline",
            side_effect=RuntimeError("Pipeline crash"),
        ):
            proc_res = client.post(f"/api/jobs/{job_id}/process")
            assert proc_res.status_code == 500
            assert "error" in proc_res.json
            # Internal trace must not be leaked
            assert "RuntimeError" not in proc_res.json["error"]


# ---------------------------------------------------------------------------
# 3. GET /api/jobs/<job_id>/preview/html
# ---------------------------------------------------------------------------


class TestHtmlPreviewRoute:

    def test_html_preview_unknown_job_returns_404(self, client):
        res = client.get("/api/jobs/nonexistentjob123/preview/html")
        assert res.status_code == 404

    def test_html_preview_unprocessed_job_returns_409(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        res = client.get(f"/api/jobs/{job_id}/preview/html")
        assert res.status_code == 409
        assert "has not been processed yet" in res.json["error"]

    def test_html_preview_success(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        doc = make_dummy_doc()
        store_job_document(job_id, doc)

        try:
            res = client.get(f"/api/jobs/{job_id}/preview/html")
            assert res.status_code == 200
            assert res.mimetype == "text/html"
            assert "<!DOCTYPE html>" in res.text
            assert "What is 2+2?" in res.text
            assert r"\alpha + \beta = \gamma" in res.text
            assert 'src="data:image/png;base64,' in res.text
        finally:
            remove_job_document(job_id)


# ---------------------------------------------------------------------------
# 4. GET /api/jobs/<job_id>/preview/pdf
# ---------------------------------------------------------------------------


class TestPdfPreviewRoute:

    def test_pdf_preview_unknown_job_returns_404(self, client):
        res = client.get("/api/jobs/nonexistentjob123/preview/pdf")
        assert res.status_code == 404

    def test_pdf_preview_unprocessed_job_returns_409(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        res = client.get(f"/api/jobs/{job_id}/preview/pdf")
        assert res.status_code == 409
        assert "has not been processed yet" in res.json["error"]

    def test_pdf_preview_success(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        doc = make_dummy_doc()
        store_job_document(job_id, doc)

        fake_pdf_bytes = b"%PDF-1.4 fake pdf data"

        with patch(
            "offline_latex_generator.web.workspace_routes.generate_pdf_preview",
            return_value=fake_pdf_bytes,
        ) as mock_pdf:
            try:
                res = client.get(f"/api/jobs/{job_id}/preview/pdf")
                assert res.status_code == 200
                assert res.mimetype == "application/pdf"
                assert res.data == fake_pdf_bytes
                assert "inline;" in res.headers["Content-Disposition"]
                mock_pdf.assert_called_once_with(doc)
            finally:
                remove_job_document(job_id)

    def test_pdf_preview_failure_returns_500(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        doc = make_dummy_doc()
        store_job_document(job_id, doc)

        with patch(
            "offline_latex_generator.web.workspace_routes.generate_pdf_preview",
            side_effect=PDFPreviewError("pdflatex compilation failed"),
        ):
            try:
                res = client.get(f"/api/jobs/{job_id}/preview/pdf")
                assert res.status_code == 500
                assert "PDF compilation failed" in res.json["error"]
            finally:
                remove_job_document(job_id)


# ---------------------------------------------------------------------------
# 5. GET /api/jobs/<job_id>/latex
# ---------------------------------------------------------------------------


class TestLatexSourceRoute:

    def test_latex_source_unknown_job_returns_404(self, client):
        res = client.get("/api/jobs/nonexistentjob123/latex")
        assert res.status_code == 404

    def test_latex_source_unprocessed_job_returns_409(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        res = client.get(f"/api/jobs/{job_id}/latex")
        assert res.status_code == 409
        assert "has not been processed yet" in res.json["error"]

    def test_latex_source_inline_text_response(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        doc = make_dummy_doc()
        store_job_document(job_id, doc)

        try:
            res = client.get(f"/api/jobs/{job_id}/latex")
            assert res.status_code == 200
            assert "text/plain" in res.mimetype
            assert r"\documentclass{article}" in res.text
            assert "What is 2+2?" in res.text
        finally:
            remove_job_document(job_id)

    def test_latex_source_download_response(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        doc = make_dummy_doc()
        store_job_document(job_id, doc)

        try:
            res = client.get(f"/api/jobs/{job_id}/latex?download=true")
            assert res.status_code == 200
            assert "attachment;" in res.headers["Content-Disposition"]
            assert f"{job_id}.tex" in res.headers["Content-Disposition"]
        finally:
            remove_job_document(job_id)


# ---------------------------------------------------------------------------
# 6. Project Protection Check
# ---------------------------------------------------------------------------


class TestProjectFolderProtection:

    def test_no_permanent_files_written_to_src_during_processing(self, client):
        create_res = client.post("/api/jobs")
        job_id = create_res.json["job_id"]

        file_data = (io.BytesIO(b"fake content"), "sample.png")
        client.post(
            f"/api/jobs/{job_id}/upload",
            data={"file": file_data},
            content_type="multipart/form-data",
        )

        doc = make_dummy_doc()
        src_root = Path(__file__).resolve().parents[2] / "src"
        before = set(src_root.rglob("*.tex")) | set(src_root.rglob("*.pdf"))

        with patch(
            "offline_latex_generator.web.workspace_routes.run_pipeline",
            return_value=doc,
        ):
            client.post(f"/api/jobs/{job_id}/process")
            client.get(f"/api/jobs/{job_id}/preview/html")

        after = set(src_root.rglob("*.tex")) | set(src_root.rglob("*.pdf"))
        assert before == after
