from offline_latex_generator.question_detector import OCRTextBlock, detect_question_boundaries


def test_detect_question_boundaries_finds_basic_question_numbers():
    blocks = [
        OCRTextBlock(text="1. What is the capital of France?"),
        OCRTextBlock(text="A. Paris"),
        OCRTextBlock(text="B. London"),
        OCRTextBlock(text="2) Which planet is known as the Red Planet?"),
    ]

    boundaries = detect_question_boundaries(blocks)

    assert boundaries == [0, 3]


def test_detect_question_boundaries_handles_question_prefixes():
    blocks = [
        OCRTextBlock(text="Question 1: What is 2 + 2?"),
        OCRTextBlock(text="Question 2: Name the largest ocean."),
    ]

    boundaries = detect_question_boundaries(blocks)

    assert boundaries == [0, 1]
