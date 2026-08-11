from offline_latex_generator.question_detector import OCRTextBlock, detect_question_boundaries
from offline_latex_generator.question_segmenter import segment_questions


def test_segment_questions_creates_structured_regions():
    blocks = [
        OCRTextBlock(text="1. What is the capital of France?"),
        OCRTextBlock(text="A. Paris"),
        OCRTextBlock(text="B. London"),
        OCRTextBlock(text="2) Which planet is known as the Red Planet?"),
    ]

    regions = segment_questions(blocks)

    assert len(regions) == 2
    assert regions[0]["question_text"] == "1. What is the capital of France?"
    assert regions[0]["text_blocks"] == ["1. What is the capital of France?", "A. Paris", "B. London"]
    assert regions[1]["question_text"] == "2) Which planet is known as the Red Planet?"
