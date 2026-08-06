import json
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger

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
        now = datetime.now(timezone.utc)
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
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

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
