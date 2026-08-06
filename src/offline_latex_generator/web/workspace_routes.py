from flask import Blueprint, jsonify
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
