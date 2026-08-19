"""Layout analysis and classification package — Phase 8.

Provides:
- OCRBlock           : normalised input DTO from raw PaddleOCR output
- LayoutRegionType   : string constants for structural region classes
- LayoutElement      : immutable output dataclass for one detected region
- LayoutDetectorError: raised on unrecoverable input errors
- parse_ocr_blocks() : converts raw PaddleOCR result into List[OCRBlock]
- detect_layout()    : classifies OCRBlocks into List[LayoutElement]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class LayoutDetectorError(RuntimeError):
    """Raised when layout detection encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Region type constants
# ---------------------------------------------------------------------------

class LayoutRegionType:
    """String constants for the structural region classes."""

    TEXT = "text"
    HEADING = "heading"
    QUESTION = "question"
    OPTION = "option"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Input DTO
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OCRBlock:
    """Normalised representation of one PaddleOCR detection result.

    Attributes:
        block_index: Zero-based position in the original result list.
        bbox:        Axis-aligned bounding box ``(x0, y0, x1, y1)`` derived
                     from the quad corners; x0 <= x1 and y0 <= y1.
        text:        Recognised text string (may be empty).
        confidence:  Recognition confidence in [0.0, 1.0] as reported by the
                     OCR engine; -1.0 when not available.
    """

    block_index: int
    bbox: Tuple[float, float, float, float]
    text: str
    confidence: float


# ---------------------------------------------------------------------------
# Output dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayoutElement:
    """One detected structural region produced by the layout detector.

    Attributes:
        region_type:   One of the :class:`LayoutRegionType` constants.
        block_indices: Tuple of :class:`OCRBlock` indices that form this element.
        bbox:          Axis-aligned bounding box ``(x0, y0, x1, y1)`` covering
                       all constituent blocks.
        confidence:    Mean OCR confidence of constituent blocks; -1.0 when
                       not available.
        texts:         Tuple of text strings, one per constituent block, in the
                       same order as ``block_indices``.
    """

    region_type: str
    block_indices: Tuple[int, ...]
    bbox: Tuple[float, float, float, float]
    confidence: float
    texts: Tuple[str, ...]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Precompiled patterns — identical to question_detector heuristics so
# classification is consistent across the pipeline.
_RE_QUESTION = re.compile(
    r"^\s*\d+\s*[\.)](?:\s+|$|[A-Za-z])|^\s*question\s+\d+\s*[:\-]",
    re.IGNORECASE,
)
_RE_OPTION = re.compile(
    r"^\s*(?:\([A-Za-z]\)|[A-Za-z][).])\s+",
)
_HEADING_MAX_WORDS = 6
_HEADING_MIN_CONFIDENCE = 0.80


def _quad_to_bbox(
    quad: List[List[float]],
) -> Tuple[float, float, float, float]:
    """Convert a 4-corner quad ``[[x,y], ...]`` to an axis-aligned bbox.

    Args:
        quad: List of 4 ``[x, y]`` corner points (any winding order).

    Returns:
        ``(x0, y0, x1, y1)`` where x0 <= x1 and y0 <= y1.

    Raises:
        LayoutDetectorError: If the quad cannot be parsed.
    """
    try:
        xs = [float(pt[0]) for pt in quad]
        ys = [float(pt[1]) for pt in quad]
    except (TypeError, IndexError, ValueError) as exc:
        raise LayoutDetectorError(
            f"Cannot parse quad corners: {quad!r}"
        ) from exc
    return (min(xs), min(ys), max(xs), max(ys))


def _classify(text: str, confidence: float) -> str:
    """Deterministically classify a text block into a region type.

    The rules are evaluated in priority order:
    1. Empty / whitespace-only text → UNKNOWN
    2. Matches question-number pattern → QUESTION
    3. Matches option label pattern → OPTION
    4. Short text (≤ 6 words) with high confidence → HEADING
    5. Everything else → TEXT
    """
    stripped = text.strip()
    if not stripped:
        return LayoutRegionType.UNKNOWN
    if _RE_QUESTION.search(stripped):
        return LayoutRegionType.QUESTION
    if _RE_OPTION.match(stripped):
        return LayoutRegionType.OPTION
    word_count = len(stripped.split())
    if word_count <= _HEADING_MAX_WORDS and confidence >= _HEADING_MIN_CONFIDENCE:
        return LayoutRegionType.HEADING
    return LayoutRegionType.TEXT


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_ocr_blocks(raw_result: Any) -> List[OCRBlock]:
    """Convert a raw PaddleOCR result into a list of :class:`OCRBlock` objects.

    PaddleOCR 2.x returns a list-of-pages, each page being a list of
    detections.  Each detection has the form::

        [
            [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],  # quad
            ("text", confidence)                         # recognition result
        ]

    This function flattens all pages, normalises each quad to an axis-aligned
    bounding box, and assigns sequential ``block_index`` values.

    Args:
        raw_result: The value returned by ``PaddleOCR.ocr()``.  ``None``, an
                    empty list, or a list of ``None``/empty-list pages are all
                    handled gracefully (returns ``[]``).

    Returns:
        List of :class:`OCRBlock`, one per detected text region, in document
        order.  Returns an empty list for empty or ``None`` input.

    Raises:
        LayoutDetectorError: If an individual detection entry cannot be parsed.
    """
    if not raw_result:
        return []

    blocks: List[OCRBlock] = []
    index = 0

    for page in raw_result:
        if not page:
            continue
        for detection in page:
            try:
                quad, rec = detection[0], detection[1]
                text = str(rec[0]) if rec[0] is not None else ""
                confidence = float(rec[1]) if rec[1] is not None else -1.0
            except (TypeError, IndexError, KeyError, ValueError) as exc:
                raise LayoutDetectorError(
                    f"Malformed OCR detection entry at index {index}: {detection!r}"
                ) from exc

            bbox = _quad_to_bbox(quad)
            blocks.append(
                OCRBlock(
                    block_index=index,
                    bbox=bbox,
                    text=text,
                    confidence=confidence,
                )
            )
            index += 1

    return blocks


def detect_layout(blocks: Sequence[OCRBlock]) -> List[LayoutElement]:
    """Classify a sequence of :class:`OCRBlock` objects into :class:`LayoutElement` regions.

    In Phase 8 each :class:`OCRBlock` maps 1-to-1 to a :class:`LayoutElement`.
    Future phases may merge adjacent blocks of the same type.

    Args:
        blocks: Ordered sequence of :class:`OCRBlock` objects, typically
                produced by :func:`parse_ocr_blocks`.

    Returns:
        List of :class:`LayoutElement`, one per input block, in the same order.
        Returns an empty list for empty input.
    """
    if not blocks:
        return []

    elements: List[LayoutElement] = []
    for block in blocks:
        region_type = _classify(block.text, block.confidence)
        elements.append(
            LayoutElement(
                region_type=region_type,
                block_indices=(block.block_index,),
                bbox=block.bbox,
                confidence=block.confidence,
                texts=(block.text,),
            )
        )
    return elements


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "LayoutDetectorError",
    "LayoutRegionType",
    "OCRBlock",
    "LayoutElement",
    "parse_ocr_blocks",
    "detect_layout",
]
