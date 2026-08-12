"""Unit tests for Phase 14: Diagram Extraction.

Tests cover:
1.  Valid bbox creates a DiagramRegion.
2.  Output image is a PIL Image.Image.
3.  Normal crop dimensions are correct.
4.  Float bbox coordinates are normalised (floor/ceil).
5.  Out-of-bounds bbox is safely clamped.
6.  Zero-size bbox produces the minimum-1-pixel crop guaranteed by _safe_crop.
7.  Invalid page_image raises TypeError.
8.  Invalid bbox length raises ValueError.
9.  DiagramRegion is frozen / immutable.
10. source_page default (0) and an explicit non-zero value are preserved.
"""

from __future__ import annotations

import dataclasses

import pytest
from PIL import Image

from offline_latex_generator.diagram_extractor import (
    DiagramRegion,
    extract_diagram_region,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _page(width: int = 100, height: int = 80) -> Image.Image:
    """Return a plain RGB test image of the requested dimensions."""
    return Image.new("RGB", (width, height), color=(200, 200, 200))


# ---------------------------------------------------------------------------
# Test 1 — valid bbox creates a DiagramRegion
# ---------------------------------------------------------------------------


def test_valid_bbox_returns_diagram_region():
    region = extract_diagram_region(_page(), bbox=(10.0, 10.0, 50.0, 40.0))
    assert isinstance(region, DiagramRegion)


# ---------------------------------------------------------------------------
# Test 2 — output image is a PIL Image.Image
# ---------------------------------------------------------------------------


def test_output_image_is_pil_image():
    region = extract_diagram_region(_page(), bbox=(5.0, 5.0, 30.0, 25.0))
    assert isinstance(region.image, Image.Image)


# ---------------------------------------------------------------------------
# Test 3 — normal crop dimensions
# ---------------------------------------------------------------------------


def test_normal_crop_dimensions():
    # bbox (10, 20, 50, 60) on a 100×80 page
    # expected width  = 50 - 10 = 40
    # expected height = 60 - 20 = 40
    region = extract_diagram_region(_page(100, 80), bbox=(10.0, 20.0, 50.0, 60.0))
    w, h = region.image.size
    assert w == 40, f"Expected width 40, got {w}"
    assert h == 40, f"Expected height 40, got {h}"


# ---------------------------------------------------------------------------
# Test 4 — float coordinate normalisation (floor/ceil)
# ---------------------------------------------------------------------------


def test_float_bbox_normalisation():
    # x0=10.9 → floor → 10
    # y0=20.1 → floor → 20
    # x1=50.3 → ceil  → 51
    # y1=60.7 → ceil  → 61
    # expected width  = 51 - 10 = 41
    # expected height = 61 - 20 = 41
    region = extract_diagram_region(_page(100, 80), bbox=(10.9, 20.1, 50.3, 60.7))
    w, h = region.image.size
    assert w == 41, f"Expected width 41 after float normalisation, got {w}"
    assert h == 41, f"Expected height 41 after float normalisation, got {h}"


# ---------------------------------------------------------------------------
# Test 5 — out-of-bounds bbox is safely clamped
# ---------------------------------------------------------------------------


def test_out_of_bounds_bbox_is_clamped():
    # Page is 100×80; bbox far exceeds both dimensions
    region = extract_diagram_region(_page(100, 80), bbox=(-50.0, -30.0, 200.0, 300.0))
    w, h = region.image.size
    # Clamped to page: (0, 0, 100, 80)
    assert w == 100, f"Expected width 100 after clamping, got {w}"
    assert h == 80,  f"Expected height 80 after clamping, got {h}"


# ---------------------------------------------------------------------------
# Test 6 — zero-size bbox produces minimum-1-pixel crop
# ---------------------------------------------------------------------------


def test_zero_size_bbox_minimum_crop():
    # bbox where x0==x1 and y0==y1 — the _safe_crop contract guarantees
    # that when the image has positive dimensions the result is at least 1×1.
    region = extract_diagram_region(_page(100, 80), bbox=(30.0, 30.0, 30.0, 30.0))
    w, h = region.image.size
    assert w >= 1, f"Expected minimum width 1 for zero-size bbox, got {w}"
    assert h >= 1, f"Expected minimum height 1 for zero-size bbox, got {h}"


# ---------------------------------------------------------------------------
# Test 7 — invalid page_image raises TypeError
# ---------------------------------------------------------------------------


def test_non_image_page_raises_type_error():
    with pytest.raises(TypeError, match="PIL Image"):
        extract_diagram_region("not-an-image", bbox=(0.0, 0.0, 10.0, 10.0))


def test_none_page_raises_type_error():
    with pytest.raises(TypeError, match="PIL Image"):
        extract_diagram_region(None, bbox=(0.0, 0.0, 10.0, 10.0))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 8 — invalid bbox length raises ValueError
# ---------------------------------------------------------------------------


def test_bbox_too_short_raises_value_error():
    with pytest.raises(ValueError, match="bbox must have exactly 4"):
        extract_diagram_region(_page(), bbox=(10.0, 20.0, 30.0))  # type: ignore[arg-type]


def test_bbox_too_long_raises_value_error():
    with pytest.raises(ValueError, match="bbox must have exactly 4"):
        extract_diagram_region(_page(), bbox=(10.0, 20.0, 30.0, 40.0, 50.0))  # type: ignore[arg-type]


def test_bbox_empty_raises_value_error():
    with pytest.raises(ValueError):
        extract_diagram_region(_page(), bbox=())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 9 — DiagramRegion is frozen / immutable
# ---------------------------------------------------------------------------


def test_diagram_region_is_frozen():
    region = extract_diagram_region(_page(), bbox=(5.0, 5.0, 20.0, 15.0))
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        region.source_page = 99  # type: ignore[misc]


def test_diagram_region_bbox_is_frozen():
    region = extract_diagram_region(_page(), bbox=(5.0, 5.0, 20.0, 15.0))
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        region.bbox = (0.0, 0.0, 1.0, 1.0)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test 10 — source_page default and explicit value
# ---------------------------------------------------------------------------


def test_source_page_defaults_to_zero():
    region = extract_diagram_region(_page(), bbox=(0.0, 0.0, 10.0, 10.0))
    assert region.source_page == 0


def test_source_page_explicit_value_preserved():
    region = extract_diagram_region(
        _page(), bbox=(0.0, 0.0, 10.0, 10.0), source_page=5
    )
    assert region.source_page == 5


# ---------------------------------------------------------------------------
# Additional — original bbox stored verbatim in DiagramRegion
# ---------------------------------------------------------------------------


def test_diagram_region_stores_original_bbox():
    bbox = (10.9, 20.1, 50.3, 60.7)
    region = extract_diagram_region(_page(100, 80), bbox=bbox)
    # bbox stored as floats; compare element-wise
    assert len(region.bbox) == 4
    assert pytest.approx(region.bbox[0]) == 10.9
    assert pytest.approx(region.bbox[1]) == 20.1
    assert pytest.approx(region.bbox[2]) == 50.3
    assert pytest.approx(region.bbox[3]) == 60.7
