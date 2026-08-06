import json
from pathlib import Path
from offline_latex_generator.cleanup.manager import WorkspaceManager

def test_generate_job_id():
    manager = WorkspaceManager()
    job_id1 = manager.generate_job_id()
    job_id2 = manager.generate_job_id()
    assert len(job_id1) == 32
    assert job_id1 != job_id2
    assert job_id1.isalnum()

def test_create_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    
    # Create workspace
    manifest = manager.create_workspace()
    
    # Assert return values
    assert "job_id" in manifest
    assert manifest["status"] == "pending"
    assert "created_at" in manifest
    assert "expires_at" in manifest
    
    # Assert path containment (path MUST NOT be in the returned dictionary)
    assert not any(str(tmp_path) in str(val) for val in manifest.values())
    assert not any("path" in key.lower() for key in manifest.keys())

    # Check directory actually created on disk
    job_dir = tmp_path / manifest["job_id"]
    assert job_dir.exists()
    assert job_dir.is_dir()
    
    # Check manifest.json contents on disk
    manifest_file = job_dir / "manifest.json"
    assert manifest_file.exists()
    
    with open(manifest_file, "r", encoding="utf-8") as f:
        disk_manifest = json.load(f)
        assert disk_manifest["job_id"] == manifest["job_id"]

def test_load_and_save_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]
    
    # Load manifest
    loaded = manager.load_manifest(job_id)
    assert loaded is not None
    assert loaded["job_id"] == job_id
    
    # Save/update manifest
    loaded["status"] = "processing"
    loaded["metadata"]["test_key"] = "test_val"
    manager.save_manifest(job_id, loaded)
    
    # Load again and verify
    reloaded = manager.load_manifest(job_id)
    assert reloaded["status"] == "processing"
    assert reloaded["metadata"]["test_key"] == "test_val"
    assert reloaded["updated_at"] != loaded["created_at"]

def test_delete_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]
    
    job_dir = tmp_path / job_id
    assert job_dir.exists()
    
    # Delete workspace
    success = manager.delete_workspace(job_id)
    assert success is True
    assert not job_dir.exists()
    
    # Attempt loading deleted manifest
    loaded = manager.load_manifest(job_id)
    assert loaded is None
