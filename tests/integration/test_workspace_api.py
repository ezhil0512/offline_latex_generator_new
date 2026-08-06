import pytest
from pathlib import Path
from offline_latex_generator.main import create_app

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"

def test_create_get_delete_job_flow(client, tmp_path):
    # 1. Create a job
    res_create = client.post("/api/jobs")
    assert res_create.status_code == 201
    data = res_create.json
    assert "job_id" in data
    assert data["status"] == "pending"
    job_id = data["job_id"]
    
    # Assert path containment (internal filesystem paths are not returned in the payload)
    assert not any(str(tmp_path) in str(val) for val in data.values())
    assert not any("path" in key.lower() for key in data.keys())

    # Check directory actually exists
    job_dir = tmp_path / job_id
    assert job_dir.exists()
    assert (job_dir / "manifest.json").exists()

    # 2. Get status
    res_get = client.get(f"/api/jobs/{job_id}")
    assert res_get.status_code == 200
    assert res_get.json["job_id"] == job_id
    assert res_get.json["status"] == "pending"

    # Assert path containment on GET as well
    assert not any(str(tmp_path) in str(val) for val in res_get.json.values())

    # 3. Delete job workspace
    res_delete = client.delete(f"/api/jobs/{job_id}")
    assert res_delete.status_code == 200
    assert res_delete.json["status"] == "deleted"
    assert res_delete.json["job_id"] == job_id
    
    # Check directory is gone
    assert not job_dir.exists()

    # 4. Get status again (should be 404)
    res_get_deleted = client.get(f"/api/jobs/{job_id}")
    assert res_get_deleted.status_code == 404

    # 5. Delete again (should be 404)
    res_delete_deleted = client.delete(f"/api/jobs/{job_id}")
    assert res_delete_deleted.status_code == 404

def test_get_invalid_job_id(client):
    res = client.get("/api/jobs/nonexistentjobid123")
    assert res.status_code == 404
