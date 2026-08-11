from PIL import Image

from offline_latex_generator.ocr_router import OCRRouter
from offline_latex_generator.recognizer import RecognizerError


class DummyRecognizer:
    def recognize(self, image):
        return "recognized"


def test_ocr_router_routes_to_text_recognizer(monkeypatch):
    def fake_get_recognizer(task):
        assert task == "text"
        return DummyRecognizer()

    from offline_latex_generator import ocr_router as router_pkg

    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    result = router.route("text", Image.new("RGB", (8, 8)))

    assert result == "recognized"


def test_ocr_router_rejects_unknown_task():
    router = OCRRouter()
    try:
        router.route("unknown", Image.new("RGB", (8, 8)))
    except ValueError as exc:
        assert "Unsupported OCR task" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported task")


def test_ocr_router_rejects_non_image_input():
    router = OCRRouter()
    try:
        router.route("text", "not-image")
    except TypeError as exc:
        assert "Pillow Image" in str(exc)
    else:
        raise AssertionError("Expected TypeError for non-image input")


def test_ocr_router_wraps_recognizer_errors(monkeypatch):
    class FailingRecognizer:
        def recognize(self, image):
            raise RuntimeError("internal fail")

    def fake_get_recognizer(task):
        return FailingRecognizer()

    from offline_latex_generator import ocr_router as router_pkg

    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    try:
        router.route("text", Image.new("RGB", (8, 8)))
    except RecognizerError as exc:
        assert "OCR recognizer failed" in str(exc)
    else:
        raise AssertionError("Expected RecognizerError when recognizer fails")
