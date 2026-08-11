from types import SimpleNamespace
import sys

from PIL import Image

from offline_latex_generator.config import config
from offline_latex_generator.recognizer import (
    BaseRecognizer,
    Pix2TextRecognizer,
    PaddleOCRRecognizer,
    RecognizerError,
    get_recognizer,
)


def test_get_recognizer_returns_paddleocr_for_text(monkeypatch):
    monkeypatch.setattr(
        config,
        "_config_data",
        {
            "models": {
                "text_ocr": {
                    "engine": "paddleocr",
                    "language": "en",
                }
            }
        },
    )

    class DummyPaddleOCR:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def ocr(self, image, cls=False):
            return [[("hello", 0.99)]]

    fake_module = SimpleNamespace(PaddleOCR=DummyPaddleOCR)
    monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    recognizer = get_recognizer("text")

    assert isinstance(recognizer, PaddleOCRRecognizer)
    result = recognizer.recognize(Image.new("RGB", (10, 10)))
    assert result == [[("hello", 0.99)]]


def test_get_recognizer_returns_pix2text_for_math(monkeypatch):
    monkeypatch.setattr(
        config,
        "_config_data",
        {"models": {"math_ocr": {"engine": "pix2text"}}},
    )

    class DummyPix2Text:
        def predict(self, image):
            return "math-result"

    fake_module = SimpleNamespace(Pix2Text=DummyPix2Text)
    monkeypatch.setitem(sys.modules, "pix2text", fake_module)

    recognizer = get_recognizer("math")

    assert isinstance(recognizer, Pix2TextRecognizer)
    assert recognizer.recognize(Image.new("RGB", (10, 10))) == "math-result"


def test_get_recognizer_unsupported_task_raises(monkeypatch):
    monkeypatch.setattr(config, "_config_data", {})

    try:
        get_recognizer("diagram")
    except RecognizerError as exc:
        assert "Unsupported or unconfigured recognizer" in str(exc)
    else:
        raise AssertionError("Expected RecognizerError for unsupported task")


def test_recognizer_rejects_non_image_input(monkeypatch):
    monkeypatch.setattr(config, "_config_data", {"models": {"math_ocr": {"engine": "pix2text"}}})

    class DummyPix2Text:
        def predict(self, image):
            return "math-result"

    fake_module = SimpleNamespace(Pix2Text=DummyPix2Text)
    monkeypatch.setitem(sys.modules, "pix2text", fake_module)

    recognizer = get_recognizer("math")
    try:
        recognizer.recognize("not-an-image")
    except TypeError as exc:
        assert "Pillow Image" in str(exc)
    else:
        raise AssertionError("Expected TypeError for non-image input")
