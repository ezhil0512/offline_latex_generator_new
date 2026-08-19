import pytest
from offline_latex_generator.layout_detector import LayoutElement, LayoutRegionType
from offline_latex_generator.formula_reconstructor import merge_formula_fragments, FormulaRegion


def test_basic_fragment_merging():
    """Test merging spatially close layout elements containing math symbols."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (12, 0, 22, 10), 0.9, ("=",))
    el3 = LayoutElement(LayoutRegionType.TEXT, (2,), (24, 0, 34, 10), 0.9, ("2",))
    
    result = merge_formula_fragments([el1, el2, el3])
    
    assert len(result) == 1
    assert isinstance(result[0], FormulaRegion)
    assert result[0].block_indices == (0, 1, 2)
    assert result[0].bbox == (0, 0, 34, 10)
    assert result[0].confidence == 0.9
    assert result[0].texts == ("x", "=", "2")


def test_non_formula_elements_remain_unchanged():
    """Test that text without math symbols is not merged."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("The",))
    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (12, 0, 30, 10), 0.9, ("apple",))
    
    result = merge_formula_fragments([el1, el2])
    
    assert len(result) == 2
    assert result[0] is el1
    assert result[1] is el2


def test_spatially_distant_fragments():
    """Test that fragments far apart are not merged."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (100, 0, 110, 10), 0.9, ("=",))
    
    result = merge_formula_fragments([el1, el2])
    
    assert len(result) == 2
    assert isinstance(result[0], LayoutElement)
    assert isinstance(result[1], FormulaRegion)


def test_non_text_elements_break_cluster():
    """Test that HEADING, QUESTION, OPTION elements are not merged and break clusters."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    el2 = LayoutElement(LayoutRegionType.OPTION, (1,), (12, 0, 22, 10), 0.9, ("(A)",))
    el3 = LayoutElement(LayoutRegionType.TEXT, (2,), (24, 0, 34, 10), 0.9, ("=",))
    
    result = merge_formula_fragments([el1, el2, el3])
    
    assert len(result) == 3
    assert result[0] is el1
    assert result[1] is el2
    assert isinstance(result[2], FormulaRegion)


def test_multiple_independent_formulas():
    """Test merging multiple independent formulas."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (12, 0, 22, 10), 0.9, ("=",))
    
    # Next line
    el3 = LayoutElement(LayoutRegionType.TEXT, (2,), (0, 20, 10, 30), 0.9, ("y",))
    el4 = LayoutElement(LayoutRegionType.TEXT, (3,), (12, 20, 22, 30), 0.9, ("+",))
    
    result = merge_formula_fragments([el1, el2, el3, el4])
    
    assert len(result) == 2
    assert isinstance(result[0], FormulaRegion)
    assert result[0].texts == ("x", "=")
    assert isinstance(result[1], FormulaRegion)
    assert result[1].texts == ("y", "+")


def test_empty_input():
    assert merge_formula_fragments([]) == []


def test_input_immutability():
    """Test that original elements are untouched."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    el1_copy = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("x",))
    
    merge_formula_fragments([el1])
    
    assert el1 == el1_copy


def test_negative_confidence():
    """Test average confidence handles -1.0 appropriately."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), -1.0, ("x",))
    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (12, 0, 22, 10), -1.0, ("=",))
    
    result = merge_formula_fragments([el1, el2])
    
    assert len(result) == 1
    assert result[0].confidence == -1.0


def test_explicit_math_and_degree_symbols_detected():
    """Test that explicit math symbols (° , _ , ^ , \\frac) trigger formula region detection."""
    el_deg = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("45°",))
    res_deg = merge_formula_fragments([el_deg])
    assert len(res_deg) == 1
    assert isinstance(res_deg[0], FormulaRegion)

    el_sub = LayoutElement(LayoutRegionType.TEXT, (1,), (0, 0, 10, 10), 0.9, ("x_1",))
    res_sub = merge_formula_fragments([el_sub])
    assert len(res_sub) == 1
    assert isinstance(res_sub[0], FormulaRegion)

    el_sup = LayoutElement(LayoutRegionType.TEXT, (2,), (0, 0, 10, 10), 0.9, ("10^3",))
    res_sup = merge_formula_fragments([el_sup])
    assert len(res_sup) == 1
    assert isinstance(res_sup[0], FormulaRegion)

    el_frac = LayoutElement(LayoutRegionType.TEXT, (3,), (0, 0, 10, 10), 0.9, (r"\frac{a}{b}",))
    res_frac = merge_formula_fragments([el_frac])
    assert len(res_frac) == 1
    assert isinstance(res_frac[0], FormulaRegion)


def test_plain_text_and_decimals_negative_tests():
    """Test that ordinary English text, numbers, and decimals do NOT trigger formula region detection."""
    el1 = LayoutElement(LayoutRegionType.TEXT, (0,), (0, 0, 10, 10), 0.9, ("The refractive index is 1.54.",))
    res1 = merge_formula_fragments([el1])
    assert len(res1) == 1
    assert isinstance(res1[0], LayoutElement)

    el2 = LayoutElement(LayoutRegionType.TEXT, (1,), (0, 0, 10, 10), 0.9, ("There are 45 students in the class.",))
    res2 = merge_formula_fragments([el2])
    assert len(res2) == 1
    assert isinstance(res2[0], LayoutElement)

    el3 = LayoutElement(LayoutRegionType.TEXT, (2,), (0, 0, 10, 10), 0.9, ("prism P2 with index 1.72",))
    res3 = merge_formula_fragments([el3])
    assert len(res3) == 1
    assert isinstance(res3[0], LayoutElement)
