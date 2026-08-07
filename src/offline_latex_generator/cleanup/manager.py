import json
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger


def _utc_now() -> datetime:
    """Return the current UTC time with high-precision.

    Uses ``time.time()`` instead of ``datetime.now(timezone.utc)`` because
    on Windows the latter relies on ``GetSystemTimeAsFileTime`` which only
    has ~15.6 ms resolution.  ``time.time()`` uses the precise variant and
    therefore avoids duplicate timestamps in rapid-fire calls.
    """
    return datetime.fromtimestamp(time.time(), tz=timezone.utc)

class WorkspaceManager:
    """Manages the lifecycle of temporary job workspaces."""

    def __init__(self):
        self._workspace_root: Optional[Path] = None

    def get_workspace_root(self) -> Path:
        """Determines and returns the workspace root as a Path."""
        root_config = config.get("workspace.root")
        if root_config:
            root_path = Path(root_config)
        else:
            root_path = Path(tempfile.gettempdir()) / "offline_latex_generator"

        # Create the root folder if it doesn't exist
        root_path.mkdir(parents=True, exist_ok=True)
        return root_path

    def _get_workspace_path(self, job_id: str) -> Path:
        """Returns the internal Path for a job's workspace.
        This is an internal helper and MUST NOT be exposed or returned in public methods/APIs.
        """
        return self.get_workspace_root() / job_id

    def generate_job_id(self) -> str:
        """Generates a unique job identifier."""
        return uuid.uuid4().hex

    def create_workspace(self) -> Dict[str, Any]:
        """Creates a temporary workspace for a new job.
        
        Returns the initial manifest metadata (NOT the workspace Path).
        """
        job_id = self.generate_job_id()
        workspace_path = self._get_workspace_path(job_id)
        workspace_path.mkdir(parents=True, exist_ok=True)

        # Calculate timestamps
        now = _utc_now()
        ttl_minutes = int(config.get("workspace.ttl_minutes", 30))
        expires_at = now + timedelta(minutes=ttl_minutes)

        manifest = {
            "job_id": job_id,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "errors": [],
            "metadata": {}
        }

        manifest_path = workspace_path / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Created workspace for job {job_id}")
        return manifest

    def load_manifest(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Loads and returns the manifest for a given job.
        Returns None if the workspace does not exist or the manifest is missing.
        """
        # Validate job_id to prevent directory traversal
        if not job_id or not job_id.isalnum():
            logger.warning(f"Invalid job_id structure: {job_id}")
            return None

        workspace_path = self._get_workspace_path(job_id)
        manifest_path = workspace_path / "manifest.json"

        if not manifest_path.exists():
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to read manifest for job {job_id}: {e}")
            return None

    def save_manifest(self, job_id: str, manifest: Dict[str, Any]) -> None:
        """Saves the manifest for a given job."""
        if not job_id or not job_id.isalnum():
            raise ValueError(f"Invalid job ID: {job_id}")

        workspace_path = self._get_workspace_path(job_id)
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace for job {job_id} does not exist")

        manifest_path = workspace_path / "manifest.json"
        
        # Update modification timestamp
        manifest["updated_at"] = _utc_now().isoformat()

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    def save_file(self, job_id: str, file_stream, filename: str) -> str:
        """Saves an uploaded file to the job's workspace.
        
        Returns the secured filename.
        Does NOT return the filesystem path.
        """
        # Validate job ID
        if not job_id or not job_id.isalnum():
            raise ValueError(f"Invalid job ID: {job_id}")

        workspace_path = self._get_workspace_path(job_id)
        if not workspace_path.exists():
            raise FileNotFoundError(f"Workspace for job {job_id} does not exist")

        # Secure filename
        from werkzeug.utils import secure_filename
        safe_filename = secure_filename(filename)
        if not safe_filename:
            raise ValueError("Filename is empty after applying secure_filename")

        # Resolve paths to prevent directory traversal
        target_path = (workspace_path / safe_filename).resolve()
        resolved_workspace = workspace_path.resolve()
        
        try:
            # Check directory traversal
            target_path.relative_to(resolved_workspace)
        except ValueError:
            raise ValueError("Directory traversal attempt detected")

        # Check if file already exists
        if target_path.exists():
            raise FileExistsError(f"File '{safe_filename}' already exists in workspace")

        # Save the file
        file_stream.save(target_path)
        logger.info(f"Saved file {safe_filename} in workspace for job {job_id}")

        # Update manifest
        manifest = self.load_manifest(job_id)
        if manifest is not None:
            if "files" not in manifest:
                manifest["files"] = []
            if safe_filename not in manifest["files"]:
                manifest["files"].append(safe_filename)
            self.save_manifest(job_id, manifest)

        return safe_filename


    def delete_workspace(self, job_id: str) -> bool:
        """Deletes a job's workspace immediately.
        
        Returns True if the workspace was successfully deleted, False otherwise.
        """
        if not job_id or not job_id.isalnum():
            logger.warning(f"Invalid job ID for deletion: {job_id}")
            return False

        workspace_path = self._get_workspace_path(job_id)
        if not workspace_path.exists():
            logger.warning(f"Workspace path {workspace_path} does not exist for deletion")
            return False

        try:
            shutil.rmtree(workspace_path)
            logger.info(f"Deleted workspace for job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete workspace for job {job_id}: {e}")
            return False

# Global instance
workspace_manager = WorkspaceManager()
