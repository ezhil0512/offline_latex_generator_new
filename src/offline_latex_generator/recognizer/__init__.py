from __future__ import annotations

from typing import Any
from PIL import Image
import numpy as np

from offline_latex_generator.config import config
from offline_latex_generator.utils.logger import logger


class RecognizerError(RuntimeError):
    """Raised when an OCR recognizer fails."""
    pass


class BaseRecognizer:
    """Base recognizer interface for OCR engines."""

    def recognize(self, image: Image.Image) -> Any:
        raise NotImplementedError("Recognizer implementations must override recognize()")


class PaddleOCRRecognizer(BaseRecognizer):
    """Wrapper for the PaddleOCR engine."""

    def __init__(self) -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RecognizerError("PaddleOCR is not installed") from exc

        model_dir = config.get("models.text_ocr.model_dir")
        language = config.get("models.text_ocr.language", "en")
        self._ocr = PaddleOCR(use_angle_cls=False, lang=language, det=True, rec=True, cls=False, use_gpu=False)
        self._model_dir = model_dir

    def recognize(self, image: Image.Image) -> Any:
        if not isinstance(image, Image.Image):
            raise TypeError("Expected a Pillow Image for recognizer")
        try:
            # Convert PIL Image to numpy array (PaddleOCR requires numpy.ndarray)
            img_array = np.array(image)
            result = self._ocr.ocr(img_array, cls=False)
            return result
        except Exception as exc:
            logger.error(f"PaddleOCR recognition failed: {exc}")
            raise RecognizerError("PaddleOCR recognition failed") from exc


class Pix2TextRecognizer(BaseRecognizer):
    """Wrapper for the Pix2Text engine."""

    def __init__(self) -> None:
        try:
            import pix2text
        except ImportError as exc:
            raise RecognizerError("Pix2Text is not installed") from exc

        self._model = pix2text.Pix2Text()

    def recognize(self, image: Image.Image) -> Any:
        if not isinstance(image, Image.Image):
            raise TypeError("Expected a Pillow Image for recognizer")
        try:
            result = self._model.predict(image)
            return result
        except Exception as exc:
            logger.error(f"Pix2Text recognition failed: {exc}")
            raise RecognizerError("Pix2Text recognition failed") from exc


def get_recognizer(task: str) -> BaseRecognizer:
    task = task.lower()
    # Try task_ocr pattern first (text_ocr, math_ocr)
    engine = config.get(f"models.{task}_ocr.engine")
    # Fallback to simple task pattern (layout, table)
    if engine is None:
        engine = config.get(f"models.{task}.engine")
    if task == "math":
        return Pix2TextRecognizer()
    if engine == "paddleocr":
        return PaddleOCRRecognizer()
    raise RecognizerError(f"Unsupported or unconfigured recognizer for task: {task}")


__all__ = [
    "BaseRecognizer",
    "PaddleOCRRecognizer",
    "Pix2TextRecognizer",
    "get_recognizer",
    "RecognizerError",
]
