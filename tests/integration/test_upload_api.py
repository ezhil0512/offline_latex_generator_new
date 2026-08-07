import pytest
import io
from pathlib import Path
from offline_latex_generator.main import create_app
from offline_latex_generator.config import config

@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_upload_valid_pdf_and_image(client):
    # 1. Create job workspace
    res_create = client.post("/api/jobs")
    assert res_create.status_code == 201
    job_id = res_create.json["job_id"]
    
    # 2. Upload valid PDF
    pdf_data = (io.BytesIO(b"%PDF-1.4 dummy contents"), "test_file.pdf")
    res_upload_pdf = client.post(
        f"/api/jobs/{job_id}/upload",
        data={"file": pdf_data},
        content_type="multipart/form-data"
    )
    assert res_upload_pdf.status_code == 200
    data = res_upload_pdf.json
    assert data["job_id"] == job_id
    assert data["filename"] == "test_file.pdf"
    assert data["status"] == "uploaded"
    
    # Rule 1 Check: Verify manifest keys like "status", "created_at" are NOT in the upload response.
    assert "created_at" not in data
    assert "updated_at" not in data
    assert "errors" not in data

    # 3. Upload valid PNG image
    png_data = (io.BytesIO(b"PNG mock header data"), "test_image.PNG") # verify case insensitivity of extension
    res_upload_png = client.post(
        f"/api/jobs/{job_id}/upload",
        data={"file": png_data},
        content_type="multipart/form-data"
    )
    assert res_upload_png.status_code == 200
    assert res_upload_png.json["filename"] == "test_image.PNG"

    # 4. Verify job status shows files in manifest
    res_status = client.get(f"/api/jobs/{job_id}")
    assert res_status.status_code == 200
    assert "test_file.pdf" in res_status.json["files"]
    assert "test_image.PNG" in res_status.json["files"]

def test_upload_duplicate_file_collision_returns_409(client):
    # Create job workspace
    res_create = client.post("/api/jobs")
    job_id = res_create.json["job_id"]
    
    # Upload first time
    pdf_data_1 = (io.BytesIO(b"First upload content"), "sample.pdf")
    res_1 = client.post(f"/api/jobs/{job_id}/upload", data={"file": pdf_data_1}, content_type="multipart/form-data")
    assert res_1.status_code == 200
    
    # Upload second time (exact same name)
    pdf_data_2 = (io.BytesIO(b"Second upload content"), "sample.pdf")
    res_2 = client.post(f"/api/jobs/{job_id}/upload", data={"file": pdf_data_2}, content_type="multipart/form-data")
    
    # Rule 2 Check: Verify duplicate upload returns HTTP 409 Conflict
    assert res_2.status_code == 409
    assert "already exists in workspace" in res_2.json["error"]

def test_upload_invalid_extension_returns_400(client):
    res_create = client.post("/api/jobs")
    job_id = res_create.json["job_id"]
    
    txt_data = (io.BytesIO(b"plain text contents"), "notes.txt")
    res = client.post(f"/api/jobs/{job_id}/upload", data={"file": txt_data}, content_type="multipart/form-data")
    
    assert res.status_code == 400
    assert "is not allowed" in res.json["error"]

def test_upload_empty_file_returns_400(client):
    res_create = client.post("/api/jobs")
    job_id = res_create.json["job_id"]
    
    empty_data = (io.BytesIO(b""), "empty.pdf")
    res = client.post(f"/api/jobs/{job_id}/upload", data={"file": empty_data}, content_type="multipart/form-data")
    
    assert res.status_code == 400
    assert "empty" in res.json["error"]

def test_upload_oversized_file_returns_413(client, monkeypatch):
    # Monkeypatch configuration to restrict size to 10 bytes max
    monkeypatch.setattr(config, "_config_data", {
        "server": {
            "allowed_extensions": ["pdf"],
            "max_upload_size_mb": 0.00001 # 10.48 bytes
        }
    })
    
    res_create = client.post("/api/jobs")
    job_id = res_create.json["job_id"]
    
    # Upload 20 bytes (exceeds limit)
    large_data = (io.BytesIO(b"x" * 20), "large.pdf")
    res = client.post(f"/api/jobs/{job_id}/upload", data={"file": large_data}, content_type="multipart/form-data")
    
    assert res.status_code == 413
    assert "too large" in res.json["error"].lower()

def test_upload_missing_file_part(client):
    res_create = client.post("/api/jobs")
    job_id = res_create.json["job_id"]
    
    res = client.post(f"/api/jobs/{job_id}/upload", data={}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "No file part" in res.json["error"]
