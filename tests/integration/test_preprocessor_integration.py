from PIL import Image

from offline_latex_generator.loader import ImageLoader
from offline_latex_generator.preprocessor import ImagePreprocessor
from offline_latex_generator.cleanup.manager import WorkspaceManager


def test_preprocessor_integration_with_loader(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path))
    manager = WorkspaceManager()
    manifest = manager.create_workspace()
    job_id = manifest["job_id"]

    sample_path = tmp_path / job_id / "sample.png"
    Image.new("RGB", (80, 80), color=(200, 100, 50)).save(sample_path)

    loaded = ImageLoader().load_image(job_id, "sample.png")
    processed = ImagePreprocessor().process(loaded)

    assert isinstance(loaded, Image.Image)
    assert isinstance(processed, Image.Image)
    assert processed.size == loaded.size
