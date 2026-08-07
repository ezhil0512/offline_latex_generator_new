import pytest
import io
from PIL import Image
from reportlab.pdfgen import canvas

from offline_latex_generator.main import create_app
from offline_latex_generator.loader import PDFLoader, ImageLoader


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def generate_pdf_bytes(pages: int = 1) -> io.BytesIO:
    """Generate a valid PDF in memory using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i in range(pages):
        c.drawString(100, 750, f"Page {i+1} content")
        c.showPage()
    c.save()
    buf.seek(0)
    return buf


def generate_image_bytes(fmt: str = "PNG") -> io.BytesIO:
    """Generate a valid image in memory using Pillow."""
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color="red")
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def test_pdf_loader_integration(client):
    # 1. Create a job workspace
    res_create = client.post("/api/jobs")
    assert res_create.status_code == 201
    job_id = res_create.json["job_id"]

    # 2. Generate PDF bytes programmatically
    pdf_buf = generate_pdf_bytes(pages=2)

    # 3. Upload file via the API
    res_upload = client.post(
        f"/api/jobs/{job_id}/upload",
        data={"file": (pdf_buf, "document.pdf")},
        content_type="multipart/form-data"
    )
    assert res_upload.status_code == 200

    # 4. Call the loader using ONLY job_id and filename
    loader = PDFLoader()
    images = loader.load_pdf(job_id, "document.pdf")

    # 5. Verify returned Pillow Image objects
    assert len(images) == 2
    for img in images:
        assert isinstance(img, Image.Image)


def test_image_loader_integration(client):
    # 1. Create a job workspace
    res_create = client.post("/api/jobs")
    assert res_create.status_code == 201
    job_id = res_create.json["job_id"]

    # 2. Generate PNG image bytes programmatically
    png_buf = generate_image_bytes("PNG")

    # 3. Upload file via the API
    res_upload = client.post(
        f"/api/jobs/{job_id}/upload",
        data={"file": (png_buf, "image.png")},
        content_type="multipart/form-data"
    )
    assert res_upload.status_code == 200

    # 4. Call the loader using ONLY job_id and filename
    loader = ImageLoader()
    img = loader.load_image(job_id, "image.png")

    # 5. Verify returned Pillow Image object
    assert isinstance(img, Image.Image)
    assert img.mode == "RGB"
