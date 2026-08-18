"""Workspace management and pipeline API routes.

Exposes REST endpoints for:
- GET  /                           : serves future frontend index.html or API status metadata.
- POST /api/jobs                   : creates job workspace.
- GET  /api/jobs/<job_id>          : retrieves job manifest status.
- DELETE /api/jobs/<job_id>        : deletes job workspace.
- POST /api/jobs/<job_id>/upload   : uploads document file to job workspace.
- POST /api/jobs/<job_id>/process  : executes processing pipeline.
- GET  /api/jobs/<job_id>/preview/html : returns Phase 18 HTML preview.
- GET  /api/jobs/<job_id>/preview/pdf  : returns Phase 19 PDF preview.
- GET  /api/jobs/<job_id>/latex        : returns Phase 16 LaTeX source code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from flask import Blueprint, Response, jsonify, request

from offline_latex_generator.cleanup.manager import workspace_manager
from offline_latex_generator.config import config
from offline_latex_generator.generator import generate_latex
from offline_latex_generator.pipeline import run_pipeline
from offline_latex_generator.preview import (
    PDFPreviewError,
    generate_html_preview,
    generate_pdf_preview,
)
from offline_latex_generator.structurer.models import StructuredDocument
from offline_latex_generator.utils.logger import logger

workspace_bp = Blueprint("workspace", __name__)

# In-memory cache storing active job StructuredDocuments for fast preview rendering
_JOB_DOCUMENTS: Dict[str, StructuredDocument] = {}


def store_job_document(job_id: str, doc: StructuredDocument) -> None:
    """Cache the in-memory StructuredDocument for an active job."""
    _JOB_DOCUMENTS[job_id] = doc


def get_job_document(job_id: str) -> Optional[StructuredDocument]:
    """Retrieve the cached StructuredDocument for an active job."""
    return _JOB_DOCUMENTS.get(job_id)


def remove_job_document(job_id: str) -> None:
    """Remove the cached StructuredDocument for a deleted/cleaned job."""
    _JOB_DOCUMENTS.pop(job_id, None)


# ---------------------------------------------------------------------------
# 1. GET /
# ---------------------------------------------------------------------------


@workspace_bp.route("/", methods=["GET"])
def index():
    """Serve the future frontend index.html if present, or API metadata."""
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    index_file = templates_dir / "index.html"
    if index_file.exists():
        from flask import render_template

        return render_template("index.html")

    return (
        jsonify(
            {
                "name": "Offline LaTeX Generator API",
                "status": "healthy",
                "version": "0.1.0",
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Workspace Lifecycle Endpoints
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs", methods=["POST"])
def create_job():
    """Create a new job workspace. Returns initial manifest metadata."""
    try:
        manifest = workspace_manager.create_workspace()
        return jsonify(manifest), 201
    except Exception as e:
        logger.error(f"Failed to create job workspace: {e}")
        return jsonify({"error": "Failed to create workspace"}), 500


@workspace_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Retrieve job status and manifest metadata."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404
    return jsonify(manifest), 200


@workspace_bp.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job_workspace(job_id):
    """Manually delete/cleanup a job workspace."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    remove_job_document(job_id)
    success = workspace_manager.delete_workspace(job_id)
    if not success:
        return (
            jsonify({"error": f"Failed to delete workspace for job {job_id}"}),
            500,
        )

    return jsonify({"job_id": job_id, "status": "deleted"}), 200


@workspace_bp.route("/api/jobs/<job_id>/upload", methods=["POST"])
def upload_file(job_id):
    """Upload a document file to a job workspace."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected for upload"}), 400

    # Validate file extension
    filename = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_extensions = config.get("server.allowed_extensions", [])
    if ext not in allowed_extensions:
        return jsonify({"error": f"Extension '{ext}' is not allowed"}), 400

    # Measure file size
    try:
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
    except Exception as e:
        logger.error(f"Failed to determine file size: {e}")
        return jsonify({"error": "Failed to read file stream"}), 400

    if size == 0:
        return jsonify({"error": "Uploaded file is empty"}), 400

    max_size_mb = config.get("server.max_upload_size_mb", 50)
    if size > max_size_mb * 1024 * 1024:
        return jsonify({"error": "File too large"}), 413

    try:
        saved_filename = workspace_manager.save_file(job_id, file, filename)
        return (
            jsonify(
                {
                    "job_id": job_id,
                    "filename": saved_filename,
                    "status": "uploaded",
                }
            ),
            200,
        )
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        return jsonify({"error": "Failed to save file"}), 500


# ---------------------------------------------------------------------------
# 2. POST /api/jobs/<job_id>/process
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs/<job_id>/process", methods=["POST"])
def process_job(job_id):
    """Execute document processing pipeline for an uploaded file."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    files = manifest.get("files", [])
    if not files:
        return (
            jsonify({"error": "No uploaded input file found in workspace"}),
            400,
        )

    filename = files[0]
    try:
        file_path = workspace_manager.get_workspace_file_path(job_id, filename)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    try:
        manifest["status"] = "processing"
        workspace_manager.save_manifest(job_id, manifest)

        # Run pipeline
        doc = run_pipeline(file_path)

        # Cache StructuredDocument in job document store
        store_job_document(job_id, doc)

        manifest["status"] = "completed"
        if "metadata" not in manifest or not isinstance(manifest["metadata"], dict):
            manifest["metadata"] = {}
        manifest["metadata"]["pages"] = doc.pages
        manifest["metadata"]["questions_count"] = len(doc.questions)
        manifest["metadata"]["diagrams_count"] = len(doc.diagrams)
        workspace_manager.save_manifest(job_id, manifest)

        return (
            jsonify(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "pages": doc.pages,
                    "questions_count": len(doc.questions),
                    "diagrams_count": len(doc.diagrams),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Processing failed for job {job_id}: {e}")
        manifest["status"] = "failed"
        manifest["errors"].append(str(e))
        try:
            workspace_manager.save_manifest(job_id, manifest)
        except Exception:
            pass
        return (
            jsonify({"error": "Processing failed due to an internal server error"}),
            500,
        )


# ---------------------------------------------------------------------------
# 3. GET /api/jobs/<job_id>/preview/html
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs/<job_id>/preview/html", methods=["GET"])
def get_html_preview(job_id):
    """Retrieve Phase 18 HTML preview for a processed job."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    doc = get_job_document(job_id)
    if doc is None:
        return (
            jsonify(
                {
                    "error": f"Job {job_id} has not been processed yet. Call /api/jobs/{job_id}/process first."
                }
            ),
            409,
        )

    try:
        html_str = generate_html_preview(doc)
        return Response(html_str, mimetype="text/html; charset=utf-8"), 200
    except Exception as e:
        logger.error(f"Failed to generate HTML preview for job {job_id}: {e}")
        return jsonify({"error": "Failed to generate HTML preview"}), 500


# ---------------------------------------------------------------------------
# 4. GET /api/jobs/<job_id>/preview/pdf
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs/<job_id>/preview/pdf", methods=["GET"])
def get_pdf_preview(job_id):
    """Retrieve Phase 19 PDF preview bytes for a processed job."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    doc = get_job_document(job_id)
    if doc is None:
        return (
            jsonify(
                {
                    "error": f"Job {job_id} has not been processed yet. Call /api/jobs/{job_id}/process first."
                }
            ),
            409,
        )

    try:
        pdf_bytes = generate_pdf_preview(doc)
        return (
            Response(
                pdf_bytes,
                mimetype="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{job_id}.pdf"'
                },
            ),
            200,
        )
    except PDFPreviewError as e:
        logger.error(f"PDF compilation failed for job {job_id}: {e}")
        return jsonify({"error": f"PDF compilation failed: {e}"}), 500
    except Exception as e:
        logger.error(f"Failed to generate PDF preview for job {job_id}: {e}")
        return jsonify({"error": "Failed to generate PDF preview"}), 500


# ---------------------------------------------------------------------------
# 5. GET /api/jobs/<job_id>/latex
# ---------------------------------------------------------------------------


@workspace_bp.route("/api/jobs/<job_id>/latex", methods=["GET"])
def get_latex_source(job_id):
    """Retrieve Phase 16 LaTeX source code for a processed job."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    doc = get_job_document(job_id)
    if doc is None:
        return (
            jsonify(
                {
                    "error": f"Job {job_id} has not been processed yet. Call /api/jobs/{job_id}/process first."
                }
            ),
            409,
        )

    try:
        latex_str = generate_latex(doc)
        is_download = request.args.get("download", "").lower() == "true"
        headers = {}
        if is_download:
            headers["Content-Disposition"] = f'attachment; filename="{job_id}.tex"'

        return (
            Response(
                latex_str,
                mimetype="text/plain; charset=utf-8",
                headers=headers,
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Failed to generate LaTeX for job {job_id}: {e}")
        return jsonify({"error": "Failed to generate LaTeX source"}), 500


__all__ = [
    "workspace_bp",
    "store_job_document",
    "get_job_document",
    "remove_job_document",
]
