"""MCQ option detection from OCR text blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class MCQOption:
    """Detected MCQ option with its position and label."""

    label: str  # 'A', 'B', 'C', etc.
    block_index: int  # Index of the OCR block where this option appears
    text: str  # Full text of the option block
    pattern_type: str  # 'parentheses', 'closing_paren', 'period' indicating (A), A), A.


@dataclass(frozen=True)
class OCRTextBlock:
    """Minimal OCR output container for a single text block."""

    text: str


def detect_mcq_options(blocks: Sequence[MCQOption | OCRTextBlock]) -> List[MCQOption]:
    """Detect MCQ option patterns from OCR text blocks.

    Supported patterns:
    - (A), (B), (C), (D) - parentheses
    - A), B), C), D) - closing parenthesis only
    - A. B. C. D. - period (when followed by substantial text)

    Args:
        blocks: Sequence of OCRTextBlock containing text to analyze

    Returns:
        List of MCQOption objects sorted by block index and pattern order
    """

    if not blocks:
        return []

    options: List[MCQOption] = []

    for index, block in enumerate(blocks):
        text = (block.text or "").strip()
        if not text:
            continue

        # Try to extract option from this block
        option = _extract_option(text, index)
        if option:
            options.append(option)

    return options


def _extract_option(text: str, block_index: int) -> MCQOption | None:
    """Extract a single MCQ option from text if it matches a known pattern.

    Args:
        text: Text to analyze
        block_index: Index of the block in the original sequence

    Returns:
        MCQOption if text matches a pattern, None otherwise
    """

    # Pattern 1: (A), (B), etc.
    match = re.match(r"^\s*\(([A-Za-z])\)\s*(.*)$", text)
    if match:
        label = match.group(1).upper()
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="parentheses",
        )

    # Pattern 2: A), B), etc.
    match = re.match(r"^\s*([A-Za-z])\)\s*(.*)$", text)
    if match:
        label = match.group(1).upper()
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="closing_paren",
        )

    # Pattern 3: A. B. C. D. (only if followed by substantial text)
    # This pattern must be at the start and followed by text to avoid false positives
    match = re.match(r"^\s*([A-Za-z])\.\s+(.+)$", text)
    if match:
        label = match.group(1).upper()
        option_text = match.group(2)
        # Only treat as option if the following text is not empty and not a single letter
        if len(option_text.strip()) > 1:
            return MCQOption(
                label=label,
                block_index=block_index,
                text=text,
                pattern_type="period",
            )

    return None


def group_options_by_question(
    question_regions: List[dict],
) -> List[dict]:
    """Associate MCQ options with their containing question region.

    Args:
        question_regions: List of question region dicts from segment_questions()
                         Each must have keys: start_index, end_index, text_blocks

    Returns:
        Updated question regions with 'options' key containing MCQOption list
    """

    for region in question_regions:
        start_idx = region.get("start_index", 0)
        end_idx = region.get("end_index", 0)
        text_blocks = region.get("text_blocks", [])

        # Reconstruct blocks for this region to detect options
        blocks = [OCRTextBlock(text=t) for t in text_blocks]
        options = detect_mcq_options(blocks)

        # Adjust block indices to be relative to the original document
        adjusted_options = [
            MCQOption(
                label=opt.label,
                block_index=opt.block_index + start_idx,
                text=opt.text,
                pattern_type=opt.pattern_type,
            )
            for opt in options
        ]

        region["options"] = adjusted_options

    return question_regions


__all__ = ["MCQOption", "OCRTextBlock", "detect_mcq_options", "group_options_by_question"]
