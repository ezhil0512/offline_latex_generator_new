from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class OCRTextBlock:
    """Minimal OCR output container for a single text block."""

    text: str


def detect_question_boundaries(blocks: Sequence[OCRTextBlock]) -> List[int]:
    """Detect simple question boundaries from OCR text blocks.

    The implementation is intentionally minimal and deterministic. It only looks
    for basic question-number patterns and question-prefix patterns.
    """

    if not blocks:
        return []

    boundaries: List[int] = []
    for index, block in enumerate(blocks):
        text = (block.text or "").strip()
        if not text:
            continue

        if _looks_like_question_start(text):
            boundaries.append(index)

    return boundaries


def _looks_like_question_start(text: str) -> bool:
    patterns = [
        r"^\s*\d+\s*[\.)]\s+",
        r"^\s*question\s+\d+\s*[:\-]",
    ]

    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


__all__ = ["OCRTextBlock", "detect_question_boundaries"]
