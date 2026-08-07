import pytest
import json
from pathlib import Path
from offline_latex_generator.cleanup.manager import WorkspaceManager

class MockFileStream:
    def __init__(self, content: bytes):
        self.content = content
    def save(self, path):
        # path is expected to be a pathlib.Path
        with open(path, "wb") as f:
            f.write(self.content)

def test_save_file_success(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    
    # Create workspace
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]
    
    # Mock file stream
    file_stream = MockFileStream(b"PDF header content")
    saved_name = manager.save_file(job_id, file_stream, "test_document.pdf")
    
    assert saved_name == "test_document.pdf"
    
    # Verify file content on disk
    saved_file_path = tmp_path / job_id / "test_document.pdf"
    assert saved_file_path.exists()
    assert saved_file_path.read_bytes() == b"PDF header content"
    
    # Verify manifest updated
    updated_manifest = manager.load_manifest(job_id)
    assert "test_document.pdf" in updated_manifest["files"]

def test_save_file_collision_returns_http_409(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]
    
    file_stream1 = MockFileStream(b"First content")
    file_stream2 = MockFileStream(b"Second content")
    
    # Save first time
    manager.save_file(job_id, file_stream1, "colliding.png")
    
    # Save second time (should raise FileExistsError)
    with pytest.raises(FileExistsError) as exc_info:
        manager.save_file(job_id, file_stream2, "colliding.png")
    
    assert "already exists in workspace" in str(exc_info.value)
    # Confirm original file content did not change
    saved_file_path = tmp_path / job_id / "colliding.png"
    assert saved_file_path.read_bytes() == b"First content"

def test_save_file_empty_safe_filename_rejection(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]
    
    file_stream = MockFileStream(b"Content")
    
    # Filenames that become empty after secure_filename
    invalid_filenames = [".", "", "../../../", "___"] # secure_filename converts "___" to "", but wait! secure_filename("___") might return "___" or empty depending on version. Let's use ones we are sure are empty.
    # secure_filename(".") is empty. secure_filename("../../../") is empty.
    
    for fname in [".", "../../../", ""]:
        with pytest.raises(ValueError) as exc_info:
            manager.save_file(job_id, file_stream, fname)
        assert "empty after applying secure_filename" in str(exc_info.value)

def test_save_file_directory_traversal_neutralized(monkeypatch, tmp_path):
    """secure_filename neutralizes traversal attempts by flattening the path.
    The file is saved safely inside the workspace with a sanitized name.
    """
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    file_stream = MockFileStream(b"Neutralized content")

    # secure_filename("../other_job_id/hacked.txt") -> "other_job_id_hacked.txt"
    saved_name = manager.save_file(job_id, file_stream, "../other_job_id/hacked.txt")
    assert saved_name == "other_job_id_hacked.txt"

    # Verify the file landed inside the workspace, not outside
    saved_path = tmp_path / job_id / "other_job_id_hacked.txt"
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"Neutralized content"

    # Verify nothing was written outside the workspace
    outside_path = tmp_path / "other_job_id" / "hacked.txt"
    assert not outside_path.exists()
