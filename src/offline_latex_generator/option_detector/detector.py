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
    block_indices: Tuple[int, ...] = ()  # All constituent OCR block indices


@dataclass(frozen=True)
class OCRTextBlock:
    """Minimal OCR output container for a single text block."""

    text: str


_RE_STRIP_LABEL_STRICT = re.compile(
    r"^\s*(?:\([A-Za-z]\)|[A-Za-z][).])\s*"
)


def _is_standalone_label(text: str, opt: MCQOption) -> bool:
    """Check if text contains only the option label with no substantial option body text."""
    remainder = _RE_STRIP_LABEL_STRICT.sub("", text).strip()
    return len(remainder) == 0


def _same_line_or_adjacent(
    bbox1: Tuple[float, float, float, float] | None,
    bbox2: Tuple[float, float, float, float] | None,
) -> bool:
    """Check spatial proximity of two bounding boxes (same line or horizontally adjacent)."""
    if not bbox1 or not bbox2:
        return True  # Fallback if bboxes are not provided (e.g. in basic unit test mocks)
    x0a, y0a, x1a, y1a = bbox1
    x0b, y0b, x1b, y1b = bbox2

    h1 = y1a - y0a
    h2 = y1b - y0b
    max_h = max(h1, h2, 1.0)

    mid_ya = (y0a + y1a) / 2.0
    mid_yb = (y0b + y1b) / 2.0

    # Vertical alignment (on the same line or slightly below)
    if abs(mid_yb - mid_ya) > max_h * 1.8:
        return False

    # Horizontal alignment (block 2 to the right of or aligned with block 1)
    if x0b < x0a - 20.0:
        return False

    return True


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

    from offline_latex_generator.question_detector import _looks_like_question_start

    options: List[MCQOption] = []
    skip_indices = set()

    for index, block in enumerate(blocks):
        if index in skip_indices:
            continue

        text = (block.text or "").strip()
        if not text:
            continue

        # Try to extract option from this block
        option = _extract_option(text, index)
        if option:
            curr_idx = getattr(block, "block_index", index)
            curr_indices = option.block_indices or (curr_idx,)

            # Check if this option is a standalone label whose content is in the next block
            if _is_standalone_label(text, option) and index + 1 < len(blocks):
                next_block = blocks[index + 1]
                next_text = (next_block.text or "").strip()
                next_opt = _extract_option(next_text, getattr(next_block, "block_index", index + 1))
                next_q = _looks_like_question_start(next_text)

                bbox_curr = getattr(block, "bbox", None)
                bbox_next = getattr(next_block, "bbox", None)

                if not next_opt and not next_q and _same_line_or_adjacent(bbox_curr, bbox_next):
                    merged_text = f"{text} {next_text}"
                    next_idx = getattr(next_block, "block_index", index + 1)
                    curr_indices = (curr_idx, next_idx)
                    option = MCQOption(
                        label=option.label,
                        block_index=curr_idx,
                        text=merged_text,
                        pattern_type=option.pattern_type,
                        block_indices=curr_indices,
                    )
                    skip_indices.add(index + 1)
                else:
                    option = MCQOption(
                        label=option.label,
                        block_index=curr_idx,
                        text=option.text,
                        pattern_type=option.pattern_type,
                        block_indices=curr_indices,
                    )
            else:
                option = MCQOption(
                    label=option.label,
                    block_index=curr_idx,
                    text=option.text,
                    pattern_type=option.pattern_type,
                    block_indices=curr_indices,
                )

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

    # Pattern 1: (A), (B), (b) etc.
    match = re.match(r"^\s*\(([A-Za-z])\)\s*(.*)$", text)
    if match:
        label = match.group(1)
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="parentheses",
        )

    # Pattern 2: A), B), b) etc.
    match = re.match(r"^\s*([A-Za-z])\)\s*(.*)$", text)
    if match:
        label = match.group(1)
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="closing_paren",
        )

    # Pattern 3: (A 5.33, (b 5.33 (open parenthesis only)
    match = re.match(r"^\s*\(([A-Za-z])\s+(.+)$", text)
    if match:
        label = match.group(1)
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="open_paren",
        )

    # Pattern 4: A. B. C. D. (only if followed by substantial text)
    match = re.match(r"^\s*([A-Za-z])\.\s+(.+)$", text)
    if match:
        label = match.group(1)
        option_text = match.group(2)
        if len(option_text.strip()) > 1:
            return MCQOption(
                label=label,
                block_index=block_index,
                text=text,
                pattern_type="period",
            )

    # Pattern 5: b5.33, B5.33, a30, c2.6, d1 (OCR variants missing delimiters)
    match = re.match(r"^\s*([A-Da-d])(?=\d|\s*\d)(.*)$", text)
    if match:
        label = match.group(1)
        return MCQOption(
            label=label,
            block_index=block_index,
            text=text,
            pattern_type="compact_letter",
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
        adjusted_options = []
        for opt in options:
            indices = opt.block_indices if opt.block_indices else (opt.block_index,)
            adj_indices = tuple(bi + start_idx for bi in indices)
            adjusted_options.append(
                MCQOption(
                    label=opt.label,
                    block_index=opt.block_index + start_idx,
                    text=opt.text,
                    pattern_type=opt.pattern_type,
                    block_indices=adj_indices,
                )
            )

        region["options"] = adjusted_options

    return question_regions


__all__ = ["MCQOption", "OCRTextBlock", "detect_mcq_options", "group_options_by_question"]
