from flask import Blueprint, jsonify, request
from offline_latex_generator.config import config
from offline_latex_generator.cleanup.manager import workspace_manager
from offline_latex_generator.utils.logger import logger

workspace_bp = Blueprint("workspace", __name__)

@workspace_bp.route("/api/jobs", methods=["POST"])
def create_job():
    """Endpoint to create a new job workspace.
    Returns initial manifest metadata.
    """
    try:
        manifest = workspace_manager.create_workspace()
        return jsonify(manifest), 201
    except Exception as e:
        logger.error(f"Failed to create job workspace: {e}")
        return jsonify({"error": "Failed to create workspace"}), 500

@workspace_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    """Endpoint to retrieve a job's status and manifest metadata."""
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404
    return jsonify(manifest), 200

@workspace_bp.route("/api/jobs/<job_id>", methods=["DELETE"])
def delete_job_workspace(job_id):
    """Endpoint to manually delete/cleanup a job's workspace."""
    # Check if job exists first to return appropriate error code
    manifest = workspace_manager.load_manifest(job_id)
    if manifest is None:
        return jsonify({"error": f"Job {job_id} not found"}), 404

    success = workspace_manager.delete_workspace(job_id)
    if not success:
        return jsonify({"error": f"Failed to delete workspace for job {job_id}"}), 500

    return jsonify({"job_id": job_id, "status": "deleted"}), 200

@workspace_bp.route("/api/jobs/<job_id>/upload", methods=["POST"])
def upload_file(job_id):
    """Endpoint to upload a file to a job's workspace.
    Validates file type, size, and presence, then saves it.
    """
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

    # Reject empty file
    if size == 0:
        return jsonify({"error": "Uploaded file is empty"}), 400

    # Validate file size
    max_size_mb = config.get("server.max_upload_size_mb", 50)
    if size > max_size_mb * 1024 * 1024:
        return jsonify({"error": "File too large"}), 413

    try:
        saved_filename = workspace_manager.save_file(job_id, file, filename)
        return jsonify({
            "job_id": job_id,
            "filename": saved_filename,
            "status": "uploaded"
        }), 200
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Failed to save upload: {e}")
        return jsonify({"error": "Failed to save file"}), 500

