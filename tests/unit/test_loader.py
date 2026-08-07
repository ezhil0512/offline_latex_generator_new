import pytest
from pathlib import Path
from PIL import Image
from reportlab.pdfgen import canvas

from offline_latex_generator.cleanup.manager import WorkspaceManager
from offline_latex_generator.loader import PDFLoader, ImageLoader, DocumentLoaderError


def create_dummy_pdf(path: Path, pages: int = 1):
    """Programmatically generate a dummy PDF file using reportlab."""
    c = canvas.Canvas(str(path))
    for i in range(pages):
        c.drawString(100, 750, f"This is page {i+1} dummy content")
        c.showPage()
    c.save()


def create_dummy_image(path: Path, img_format: str, size=(100, 100), color="blue"):
    """Programmatically generate a dummy image file using Pillow."""
    img = Image.new("RGB", size, color=color)
    img.save(path, format=img_format)


def create_corrupted_file(path: Path):
    """Write garbage bytes to simulate a corrupted file."""
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4\n%garbage bytes that do not make a valid format\n")


def test_get_workspace_file_path_behavior(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    # Create a file inside workspace
    file_path = tmp_path / job_id / "document.pdf"
    file_path.write_text("dummy content")

    # Get path securely
    resolved_path = manager.get_workspace_file_path(job_id, "document.pdf")
    assert resolved_path == file_path.resolve()

    # Rejection: invalid job ID
    with pytest.raises(ValueError):
        manager.get_workspace_file_path("invalid_job_id!", "document.pdf")

    # Rejection: non-existent job ID
    with pytest.raises(FileNotFoundError):
        manager.get_workspace_file_path("1234567890abcdef1234567890abcdef", "document.pdf")

    # Rejection: directory traversal attempt
    with pytest.raises(ValueError):
        manager.get_workspace_file_path(job_id, "../outside.pdf")

    # Rejection: non-existent file
    with pytest.raises(FileNotFoundError):
        manager.get_workspace_file_path(job_id, "nonexistent.pdf")


def test_load_pdf_single_page(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    # Write programmatic PDF
    pdf_filename = "test_single.pdf"
    pdf_path = tmp_path / job_id / pdf_filename
    create_dummy_pdf(pdf_path, pages=1)

    loader = PDFLoader()
    images = loader.load_pdf(job_id, pdf_filename)

    assert len(images) == 1
    assert isinstance(images[0], Image.Image)


def test_load_pdf_multi_page(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    # Write programmatic PDF with 3 pages
    pdf_filename = "test_multi.pdf"
    pdf_path = tmp_path / job_id / pdf_filename
    create_dummy_pdf(pdf_path, pages=3)

    loader = PDFLoader()
    images = loader.load_pdf(job_id, pdf_filename)

    assert len(images) == 3
    for img in images:
        assert isinstance(img, Image.Image)


def test_load_pdf_corrupted(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    corrupt_filename = "corrupted.pdf"
    pdf_path = tmp_path / job_id / corrupt_filename
    create_corrupted_file(pdf_path)

    loader = PDFLoader()
    with pytest.raises(DocumentLoaderError) as exc_info:
        loader.load_pdf(job_id, corrupt_filename)
    assert "Failed to process PDF" in str(exc_info.value) or "Unexpected error" in str(exc_info.value)


def test_load_image_formats(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    formats_to_test = [
        ("image.png", "PNG"),
        ("image.jpg", "JPEG"),
        ("image.jpeg", "JPEG"),
        ("image.bmp", "BMP"),
        ("image.tiff", "TIFF"),
        ("image.tif", "TIFF")
    ]

    loader = ImageLoader()

    for filename, fmt in formats_to_test:
        path = tmp_path / job_id / filename
        create_dummy_image(path, fmt)

        loaded_img = loader.load_image(job_id, filename)
        assert isinstance(loaded_img, Image.Image)
        # Verify color space conversion did NOT happen (original RGB)
        assert loaded_img.mode == "RGB"


def test_load_image_corrupted(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    corrupt_filename = "corrupted.png"
    img_path = tmp_path / job_id / corrupt_filename
    create_corrupted_file(img_path)

    loader = ImageLoader()
    with pytest.raises(DocumentLoaderError) as exc_info:
        loader.load_image(job_id, corrupt_filename)
    assert "Failed to load image file" in str(exc_info.value)


def test_load_image_unsupported_format(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    filename = "document.txt"
    txt_path = tmp_path / job_id / filename
    txt_path.write_text("plain text")

    loader = ImageLoader()
    with pytest.raises(DocumentLoaderError) as exc_info:
        loader.load_image(job_id, filename)
    assert "Unsupported image format" in str(exc_info.value)
