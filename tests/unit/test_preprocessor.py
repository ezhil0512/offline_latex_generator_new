from PIL import Image

from offline_latex_generator.cleanup.manager import WorkspaceManager
from offline_latex_generator.loader import ImageLoader
from offline_latex_generator.preprocessor import ImagePreprocessor
from offline_latex_generator.config import config


def test_process_returns_processed_image_when_enabled(monkeypatch):
    monkeypatch.setattr(
        config,
        "_config_data",
        {
            "pipeline": {
                "preprocessing": {
                    "deskew": True,
                    "enhance_contrast": True,
                    "binarize": True,
                }
            }
        },
    )

    image = Image.new("RGB", (80, 80), color=(120, 120, 120))
    processor = ImagePreprocessor()
    processed = processor.process(image)

    assert isinstance(processed, Image.Image)
    assert processed.size == image.size
    assert processed.tobytes() != image.tobytes()


def test_process_is_noop_when_all_flags_disabled(monkeypatch):
    monkeypatch.setattr(
        config,
        "_config_data",
        {
            "pipeline": {
                "preprocessing": {
                    "deskew": False,
                    "enhance_contrast": False,
                    "binarize": False,
                }
            }
        },
    )

    image = Image.new("RGB", (40, 40), color=(30, 60, 90))
    processor = ImagePreprocessor()
    processed = processor.process(image)

    assert processed.tobytes() == image.tobytes()


def test_process_keeps_input_when_only_deskew_is_enabled(monkeypatch):
    monkeypatch.setattr(
        config,
        "_config_data",
        {
            "pipeline": {
                "preprocessing": {
                    "deskew": True,
                    "enhance_contrast": False,
                    "binarize": False,
                }
            }
        },
    )

    image = Image.new("RGB", (40, 40), color=(10, 20, 30))
    processor = ImagePreprocessor()
    processed = processor.process(image)

    assert processed.tobytes() == image.tobytes()


def test_process_rejects_non_image_input():
    processor = ImagePreprocessor()

    try:
        processor.process("not-an-image")
    except TypeError as exc:
        assert "Pillow Image" in str(exc)
    else:
        raise AssertionError("Expected TypeError for non-image input")


def test_process_uses_loader_output(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    sample_path = tmp_path / job_id / "sample.png"
    Image.new("RGB", (64, 64), color=(20, 40, 80)).save(sample_path)

    loaded = ImageLoader().load_image(job_id, "sample.png")
    processed = ImagePreprocessor().process(loaded)

    assert isinstance(loaded, Image.Image)
    assert isinstance(processed, Image.Image)
    assert processed.size == loaded.size
