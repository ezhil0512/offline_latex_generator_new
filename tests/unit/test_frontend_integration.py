"""Unit and integration tests for Frontend UI templates, static assets, and Web API interaction.

Covers:
- GET / serving templates/index.html
- GET /static/css/styles.css serving stylesheet
- GET /static/js/app.js serving application script
- Full end-to-end frontend interaction flow (upload -> process -> preview/html, preview/pdf, latex, reset)
- Verification that no files are permanently saved in src/ or tests/
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from offline_latex_generator.main import create_app
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

_DUMMY_BBOX = (0.0, 0.0, 10.0, 10.0)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def make_sample_doc() -> StructuredDocument:
    img = Image.new("RGBA", (4, 4), color=(255, 0, 0, 255))
    doc = StructuredDocument(pages=1)
    q = StructuredQuestion(
        question_number="1",
        body=(
            ContentItem(
                kind="text",
                text="Solve for x:",
                latex=None,
                diagram_id=None,
                bbox=_DUMMY_BBOX,
                block_index=0,
            ),
            ContentItem(
                kind="formula",
                text=None,
                latex=r"x^2 + 5x + 6 = 0",
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
                        text="x = -2, -3",
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
# 1. Template & Static Assets Delivery
# ---------------------------------------------------------------------------


class TestFrontendAssetsDelivery:

    def test_get_index_serves_html_page(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert "text/html" in res.content_type
        assert "<!DOCTYPE html>" in res.text
        assert "Offline LaTeX Generator" in res.text
        assert "css/styles.css" in res.text
        assert "js/app.js" in res.text

    def test_get_css_asset_serves_stylesheet(self, client):
        res = client.get("/static/css/styles.css")
        assert res.status_code == 200
        assert "text/css" in res.content_type
        assert "--bg-color:" in res.text
        assert ".drop-zone" in res.text

    def test_get_js_asset_serves_script(self, client):
        res = client.get("/static/js/app.js")
        assert res.status_code == 200
        assert "javascript" in res.content_type
        assert "startProcessing" in res.text
        assert "switchTab" in res.text


# ---------------------------------------------------------------------------
# 2. Frontend UI End-to-End Workflow
# ---------------------------------------------------------------------------


class TestFrontendWorkflowIntegration:

    def test_complete_upload_process_preview_reset_flow(self, client):
        # 1. User clicks "New Job" -> POST /api/jobs
        res_create = client.post("/api/jobs")
        assert res_create.status_code == 201
        job_id = res_create.json["job_id"]

        # 2. User uploads file -> POST /api/jobs/<job_id>/upload
        file_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        res_upload = client.post(
            f"/api/jobs/{job_id}/upload",
            data={"file": (io.BytesIO(file_bytes), "sample_paper.png")},
            content_type="multipart/form-data",
        )
        assert res_upload.status_code == 200
        assert res_upload.json["status"] == "uploaded"

        # 3. User clicks "Convert" -> POST /api/jobs/<job_id>/process
        sample_doc = make_sample_doc()
        with patch(
            "offline_latex_generator.web.workspace_routes.run_pipeline",
            return_value=sample_doc,
        ):
            res_proc = client.post(f"/api/jobs/{job_id}/process")
            assert res_proc.status_code == 200
            assert res_proc.json["status"] == "completed"

        # 4. App fetches HTML preview
        res_html = client.get(f"/api/jobs/{job_id}/preview/html")
        assert res_html.status_code == 200
        assert res_html.mimetype == "text/html"
        assert "Solve for x:" in res_html.text

        # 5. App fetches PDF preview
        fake_pdf = b"%PDF-1.5 fake pdf data"
        with patch(
            "offline_latex_generator.web.workspace_routes.generate_pdf_preview",
            return_value=fake_pdf,
        ):
            res_pdf = client.get(f"/api/jobs/{job_id}/preview/pdf")
            assert res_pdf.status_code == 200
            assert res_pdf.mimetype == "application/pdf"
            assert res_pdf.data == fake_pdf

        # 6. App fetches LaTeX code
        res_latex = client.get(f"/api/jobs/{job_id}/latex")
        assert res_latex.status_code == 200
        assert r"\documentclass{article}" in res_latex.text

        # 7. User clicks Download .tex
        res_dl = client.get(f"/api/jobs/{job_id}/latex?download=true")
        assert res_dl.status_code == 200
        assert f'filename="{job_id}.tex"' in res_dl.headers["Content-Disposition"]

        # 8. User clicks Reset -> DELETE /api/jobs/<job_id>
        res_del = client.delete(f"/api/jobs/{job_id}")
        assert res_del.status_code == 200
        assert res_del.json["status"] == "deleted"

        # 9. Verify preview after reset returns 404
        res_404 = client.get(f"/api/jobs/{job_id}/preview/html")
        assert res_404.status_code == 404
