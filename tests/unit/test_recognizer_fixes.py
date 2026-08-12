from __future__ import annotations

import sys
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from offline_latex_generator.config import config
from offline_latex_generator.recognizer import (
    PaddleOCRRecognizer,
    RecognizerError,
    get_recognizer,
)


# ---------------------------------------------------------------------------
# Fix 1 - PIL -> NumPy conversion
# ---------------------------------------------------------------------------

class TestPaddleOCRNumpyConversion:

    def _make_paddle_fake(self, monkeypatch):
        received = []

        class DummyPaddleOCR:
            def __init__(self, **kwargs):
                pass

            def ocr(self, image, cls=False):
                received.append(image)
                return [[("hello", 0.99)]]

        fake_module = SimpleNamespace(PaddleOCR=DummyPaddleOCR)
        monkeypatch.setitem(sys.modules, "paddleocr", fake_module)
        monkeypatch.setattr(
            config,
            "_config_data",
            {"models": {"text_ocr": {"engine": "paddleocr", "language": "en"}}},
        )
        return received

    def test_ocr_receives_ndarray_not_pil(self, monkeypatch):
        received = self._make_paddle_fake(monkeypatch)
        pil_img = Image.new("RGB", (20, 20))
        PaddleOCRRecognizer().recognize(pil_img)
        assert len(received) == 1
        assert isinstance(received[0], np.ndarray), f"Expected ndarray, got {type(received[0])}"

    def test_ndarray_shape_matches_image(self, monkeypatch):
        received = self._make_paddle_fake(monkeypatch)
        w, h = 30, 15
        PaddleOCRRecognizer().recognize(Image.new("RGB", (w, h)))
        arr = received[0]
        assert arr.shape == (h, w, 3), f"Unexpected shape: {arr.shape}"

    def test_return_value_is_unchanged(self, monkeypatch):
        self._make_paddle_fake(monkeypatch)
        result = PaddleOCRRecognizer().recognize(Image.new("RGB", (10, 10)))
        assert result == [[("hello", 0.99)]]

    def test_public_signature_accepts_pil_image(self, monkeypatch):
        self._make_paddle_fake(monkeypatch)
        PaddleOCRRecognizer().recognize(Image.new("L", (8, 8)))

    def test_non_image_still_rejected(self, monkeypatch):
        self._make_paddle_fake(monkeypatch)
        with pytest.raises(TypeError, match="Pillow Image"):
            PaddleOCRRecognizer().recognize("not-an-image")


# ---------------------------------------------------------------------------
# Fix 2 - Layout / Table config fallback in get_recognizer()
# ---------------------------------------------------------------------------

class TestGetRecognizerLayoutTableFallback:

    def _install_paddle_fake(self, monkeypatch):
        class DummyPaddleOCR:
            def __init__(self, **kwargs):
                pass

            def ocr(self, image, cls=False):
                return [[("ok", 1.0)]]

        fake_module = SimpleNamespace(PaddleOCR=DummyPaddleOCR)
        monkeypatch.setitem(sys.modules, "paddleocr", fake_module)

    def test_get_recognizer_layout_returns_paddleocr(self, monkeypatch):
        self._install_paddle_fake(monkeypatch)
        monkeypatch.setattr(config, "_config_data", {"models": {"layout": {"engine": "paddleocr"}}})
        assert isinstance(get_recognizer("layout"), PaddleOCRRecognizer)

    def test_get_recognizer_table_returns_paddleocr(self, monkeypatch):
        self._install_paddle_fake(monkeypatch)
        monkeypatch.setattr(config, "_config_data", {"models": {"table": {"engine": "paddleocr"}}})
        assert isinstance(get_recognizer("table"), PaddleOCRRecognizer)

    def test_task_ocr_key_still_wins_when_present(self, monkeypatch):
        self._install_paddle_fake(monkeypatch)
        monkeypatch.setattr(
            config,
            "_config_data",
            {"models": {"text_ocr": {"engine": "paddleocr", "language": "en"}, "text": {"engine": "wrong"}}},
        )
        assert isinstance(get_recognizer("text"), PaddleOCRRecognizer)

    def test_layout_without_config_raises(self, monkeypatch):
        monkeypatch.setattr(config, "_config_data", {})
        with pytest.raises(RecognizerError, match="Unsupported or unconfigured recognizer"):
            get_recognizer("layout")

    def test_table_without_config_raises(self, monkeypatch):
        monkeypatch.setattr(config, "_config_data", {})
        with pytest.raises(RecognizerError, match="Unsupported or unconfigured recognizer"):
            get_recognizer("table")

    def test_layout_recognizer_can_process_image(self, monkeypatch):
        self._install_paddle_fake(monkeypatch)
        monkeypatch.setattr(config, "_config_data", {"models": {"layout": {"engine": "paddleocr"}}})
        result = get_recognizer("layout").recognize(Image.new("RGB", (16, 16)))
        assert result is not None
