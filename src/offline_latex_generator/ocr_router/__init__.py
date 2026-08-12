from __future__ import annotations

import math
from typing import Any, Union
from PIL import Image

from offline_latex_generator.layout_detector import LayoutElement
from offline_latex_generator.formula_reconstructor import FormulaRegion
from offline_latex_generator.recognizer import get_recognizer, RecognizerError


def _crop_region(image: Image.Image, bbox: tuple[float, float, float, float]) -> Image.Image:
    """Safely clamp and crop image based on bbox coordinates."""
    width, height = image.size
    x0, y0, x1, y1 = bbox
    
    crop_x0 = max(0, min(width, int(math.floor(x0))))
    crop_y0 = max(0, min(height, int(math.floor(y0))))
    crop_x1 = max(crop_x0, min(width, int(math.ceil(x1))))
    crop_y1 = max(crop_y0, min(height, int(math.ceil(y1))))
    
    # Ensure non-zero dimension crops where possible
    if crop_x1 <= crop_x0 and width > 0:
        crop_x1 = min(width, crop_x0 + 1)
        if crop_x1 <= crop_x0:
            crop_x0 = max(0, crop_x1 - 1)
            
    if crop_y1 <= crop_y0 and height > 0:
        crop_y1 = min(height, crop_y0 + 1)
        if crop_y1 <= crop_y0:
            crop_y0 = max(0, crop_y1 - 1)
            
    return image.crop((crop_x0, crop_y0, crop_x1, crop_y1))


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

    def route_region(self, page_image: Image.Image, region: Union[LayoutElement, FormulaRegion]) -> Any:
        """Route a region of a page image to the appropriate OCR engine based on region type."""
        if not isinstance(page_image, Image.Image):
            raise TypeError("Expected a Pillow Image for page_image")

        if isinstance(region, FormulaRegion):
            task = "math"
        elif isinstance(region, LayoutElement):
            task = "text"
        else:
            raise TypeError(f"Unsupported region type: {type(region)}")

        cropped = _crop_region(page_image, region.bbox)
        return self.route(task, cropped)


__all__ = ["OCRRouter"]
