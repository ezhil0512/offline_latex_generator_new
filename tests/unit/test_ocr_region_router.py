import pytest
from PIL import Image

from offline_latex_generator.ocr_router import OCRRouter
from offline_latex_generator.layout_detector import LayoutElement, LayoutRegionType
from offline_latex_generator.formula_reconstructor import FormulaRegion
from offline_latex_generator.recognizer import RecognizerError


class DummyRecognizer:
    def __init__(self, name):
        self.name = name
        self.last_image = None

    def recognize(self, image):
        self.last_image = image
        return f"{self.name}:{image.size[0]}x{image.size[1]}"


def test_formula_region_routes_to_math(monkeypatch):
    rec = DummyRecognizer("math")

    def fake_get_recognizer(task):
        assert task == "math"
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (100, 100))
    formula = FormulaRegion((0, 1), (10.0, 20.0, 50.0, 60.0), 0.9, ("x", "="))

    result = router.route_region(page_img, formula)
    assert result == "math:40x40"
    assert rec.last_image.size == (40, 40)


def test_layout_element_routes_to_text(monkeypatch):
    rec = DummyRecognizer("text")

    def fake_get_recognizer(task):
        assert task == "text"
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (100, 100))
    element = LayoutElement(LayoutRegionType.TEXT, (0,), (5.0, 10.0, 25.0, 30.0), 0.9, ("hello",))

    result = router.route_region(page_img, element)
    assert result == "text:20x20"
    assert rec.last_image.size == (20, 20)


def test_correct_bbox_crop_dimensions(monkeypatch):
    rec = DummyRecognizer("crop_test")

    def fake_get_recognizer(task):
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (200, 200))
    element = LayoutElement(LayoutRegionType.HEADING, (0,), (10.0, 20.0, 110.0, 70.0), 0.9, ("Header",))

    router.route_region(page_img, element)
    assert rec.last_image.size == (100, 50)


def test_float_coordinate_normalization(monkeypatch):
    rec = DummyRecognizer("float_test")

    def fake_get_recognizer(task):
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (100, 100))
    formula = FormulaRegion((0,), (10.2, 15.7, 49.8, 60.1), 0.9, ("y",))

    router.route_region(page_img, formula)
    assert rec.last_image.size == (40, 46)


def test_boundary_clamping(monkeypatch):
    rec = DummyRecognizer("clamp_test")

    def fake_get_recognizer(task):
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (100, 100))
    element = LayoutElement(LayoutRegionType.TEXT, (0,), (-20.0, -10.0, 150.0, 120.0), 0.9, ("out of bounds",))

    router.route_region(page_img, element)
    assert rec.last_image.size == (100, 100)


def test_invalid_image_type():
    router = OCRRouter()
    element = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("test",))

    with pytest.raises(TypeError, match="Pillow Image"):
        router.route_region("not-an-image", element)


def test_invalid_region_type():
    router = OCRRouter()
    page_img = Image.new("RGB", (50, 50))

    with pytest.raises(TypeError, match="Unsupported region type"):
        router.route_region(page_img, "invalid-region-string")


def test_existing_route_behavior_remains_unchanged(monkeypatch):
    rec = DummyRecognizer("direct")

    def fake_get_recognizer(task):
        assert task == "table"
        return rec

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    result = router.route("table", Image.new("RGB", (30, 30)))
    assert result == "direct:30x30"


def test_recognition_error_handling(monkeypatch):
    class FailingRecognizer:
        def recognize(self, image):
            raise RuntimeError("OCR explosion")

    def fake_get_recognizer(task):
        return FailingRecognizer()

    from offline_latex_generator import ocr_router as router_pkg
    monkeypatch.setattr(router_pkg, "get_recognizer", fake_get_recognizer)

    router = OCRRouter()
    page_img = Image.new("RGB", (50, 50))
    formula = FormulaRegion((0,), (0, 0, 20, 20), 0.9, ("bad",))

    with pytest.raises(RecognizerError, match="OCR recognizer failed"):
        router.route_region(page_img, formula)
