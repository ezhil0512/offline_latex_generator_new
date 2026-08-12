"""Diagram extraction package — Phase 14.

Provides:
- DiagramRegion           : immutable DTO holding a cropped diagram image and its provenance.
- DiagramExtractorError   : raised on unrecoverable input errors.
- extract_diagram_region(): crops a page image to a bounding box and wraps it in DiagramRegion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from PIL import Image


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DiagramExtractorError(RuntimeError):
    """Raised when diagram extraction encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Output DTO
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagramRegion:
    """Immutable representation of one extracted diagram region.

    Attributes:
        bbox:        Axis-aligned bounding box ``(x0, y0, x1, y1)`` of the
                     region within the source page image (in page pixels, before
                     clamping).
        image:       Cropped PIL ``Image.Image`` containing only the diagram
                     region, with coordinates clamped to the source page bounds.
        source_page: Zero-based page index from which this region was extracted.
                     Defaults to 0.
    """

    bbox: Tuple[float, float, float, float]
    image: Image.Image
    source_page: int = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_crop(image: Image.Image, bbox: Tuple[float, float, float, float]) -> Image.Image:
    """Clamp *bbox* to image boundaries and return the cropped sub-image.

    Replicates the same floor/ceil normalisation and minimum-1-pixel guarantee
    used by ``OCRRouter._crop_region`` (Phase 10) so that both functions behave
    identically for the same inputs.

    Args:
        image: Source PIL ``Image.Image``.
        bbox:  ``(x0, y0, x1, y1)`` — may contain floats and/or out-of-bounds
               values.

    Returns:
        Cropped PIL ``Image.Image``, always at least 1×1 when the source image
        has positive dimensions.
    """
    width, height = image.size
    x0, y0, x1, y1 = bbox

    crop_x0 = max(0, min(width, int(math.floor(x0))))
    crop_y0 = max(0, min(height, int(math.floor(y0))))
    crop_x1 = max(crop_x0, min(width, int(math.ceil(x1))))
    crop_y1 = max(crop_y0, min(height, int(math.ceil(y1))))

    # Ensure non-zero dimension crops where possible (mirrors OCRRouter contract)
    if crop_x1 <= crop_x0 and width > 0:
        crop_x1 = min(width, crop_x0 + 1)
        if crop_x1 <= crop_x0:
            crop_x0 = max(0, crop_x1 - 1)

    if crop_y1 <= crop_y0 and height > 0:
        crop_y1 = min(height, crop_y0 + 1)
        if crop_y1 <= crop_y0:
            crop_y0 = max(0, crop_y1 - 1)

    return image.crop((crop_x0, crop_y0, crop_x1, crop_y1))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_diagram_region(
    page_image: Image.Image,
    bbox: Tuple[float, float, float, float],
    source_page: int = 0,
) -> DiagramRegion:
    """Crop *page_image* to *bbox* and return an immutable :class:`DiagramRegion`.

    Args:
        page_image:  Full-page PIL ``Image.Image`` to crop from.
        bbox:        Axis-aligned bounding box ``(x0, y0, x1, y1)`` in page-pixel
                     coordinates.  Float values are floor/ceil-normalised and
                     clamped to the image boundaries identically to the Phase 10
                     OCR router crop behaviour.
        source_page: Zero-based page index.  Defaults to 0.

    Returns:
        :class:`DiagramRegion` containing the cropped image, the original *bbox*
        (before clamping), and *source_page*.

    Raises:
        TypeError:  If *page_image* is not a PIL ``Image.Image``.
        ValueError: If *bbox* does not have exactly 4 elements.
    """
    if not isinstance(page_image, Image.Image):
        raise TypeError(
            f"page_image must be a PIL Image.Image, got {type(page_image).__name__}"
        )

    try:
        if len(bbox) != 4:
            raise ValueError(
                f"bbox must have exactly 4 coordinates (x0, y0, x1, y1), "
                f"got {len(bbox)}"
            )
    except TypeError:
        raise ValueError(
            f"bbox must be a sequence of 4 coordinates, got {type(bbox).__name__}"
        )

    cropped = _safe_crop(page_image, bbox)

    return DiagramRegion(
        bbox=tuple(float(c) for c in bbox),  # type: ignore[arg-type]
        image=cropped,
        source_page=source_page,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "DiagramExtractorError",
    "DiagramRegion",
    "extract_diagram_region",
]
