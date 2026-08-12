"""MCQ option detection and grouping package."""

from offline_latex_generator.option_detector.detector import (
    MCQOption,
    OCRTextBlock,
    detect_mcq_options,
    group_options_by_question,
)

__all__ = ["MCQOption", "OCRTextBlock", "detect_mcq_options", "group_options_by_question"]
