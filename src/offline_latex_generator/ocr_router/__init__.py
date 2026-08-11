from __future__ import annotations

from typing import Any
from PIL import Image

from offline_latex_generator.recognizer import get_recognizer, RecognizerError


class OCRRouter:
    """Routes images to the configured OCR recognizer for a given task."""

    SUPPORTED_TASKS = {
        "text",
        "math",
        "layout",
        "table",
    }

    def route(self, task: str, image: Image.Image) -> Any:
        """Route an image to the appropriate recognizer based on task."""
        if task not in self.SUPPORTED_TASKS:
            raise ValueError(f"Unsupported OCR task: {task}")

        if not isinstance(image, Image.Image):
            raise TypeError("Expected a Pillow Image for OCR routing")

        recognizer = get_recognizer(task)
        try:
            return recognizer.recognize(image)
        except RecognizerError as exc:
            raise
        except Exception as exc:
            raise RecognizerError(f"OCR recognizer failed for task '{task}': {exc}") from exc


__all__ = ["OCRRouter"]
