from __future__ import annotations

from typing import List, Sequence, Dict, Any

from offline_latex_generator.question_detector import OCRTextBlock, detect_question_boundaries


def segment_questions(blocks: Sequence[OCRTextBlock]) -> List[Dict[str, Any]]:
    """Convert detected question boundaries into simple structured regions.

    The output is intentionally minimal: each region contains the question text
    and the text blocks that belong to that question.
    """

    if not blocks:
        return []

    boundaries = detect_question_boundaries(blocks)
    if not boundaries:
        return []

    regions: List[Dict[str, Any]] = []
    for index, start in enumerate(boundaries):
        end = boundaries[index + 1] if index + 1 < len(boundaries) else len(blocks)
        region_blocks = [block.text for block in blocks[start:end]]
        question_text = region_blocks[0] if region_blocks else ""
        regions.append(
            {
                "start_index": start,
                "end_index": end,
                "question_text": question_text,
                "text_blocks": region_blocks,
            }
        )

    return regions


__all__ = ["segment_questions"]
