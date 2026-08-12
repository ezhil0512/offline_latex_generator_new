import re
from dataclasses import dataclass
from typing import List, Tuple, Union, Sequence

from offline_latex_generator.layout_detector import LayoutElement, LayoutRegionType


@dataclass(frozen=True)
class FormulaRegion:
    """A detected formula region merged from one or more layout fragments.

    Attributes:
        block_indices: Tuple of original OCRBlock indices that form this element.
        bbox:          Axis-aligned bounding box ``(x0, y0, x1, y1)`` covering
                       all constituent blocks.
        confidence:    Mean OCR confidence of constituent blocks; -1.0 when
                       not available.
        texts:         Tuple of text strings, one per constituent block, in the
                       same order as ``block_indices``.
    """
    block_indices: Tuple[int, ...]
    bbox: Tuple[float, float, float, float]
    confidence: float
    texts: Tuple[str, ...]


_RE_MATH = re.compile(
    r"[\=\+\<\>\^\~∑√πθαβγδεζηικλμνξορστυφχψω∞∫≈≠≤≥×÷±]|(?:\b(?:sin|cos|tan|log|ln)\b)",
    re.IGNORECASE
)


def _are_adjacent(bbox1: Tuple[float, float, float, float], bbox2: Tuple[float, float, float, float]) -> bool:
    """Check if two bounding boxes are horizontally adjacent on the same line."""
    x0a, y0a, x1a, y1a = bbox1
    x0b, y0b, x1b, y1b = bbox2
    
    h1 = y1a - y0a
    h2 = y1b - y0b
    avg_h = (h1 + h2) / 2.0
    if avg_h <= 0:
        return False
        
    # Must significantly overlap vertically (meaning they are on the same line)
    # A fragment like a superscript might be higher, but still overlaps the main line.
    vert_overlap = min(y1a, y1b) - max(y0a, y0b)
    # We require at least some positive vertical overlap, or a very small negative gap
    if vert_overlap < -avg_h * 0.2:
        return False
        
    # Check horizontal gap
    if x1a <= x0b:
        horiz_gap = x0b - x1a
    elif x1b <= x0a:
        horiz_gap = x0a - x1b
    else:
        horiz_gap = 0.0
        
    # Max horizontal gap of 3 times the height
    return horiz_gap <= avg_h * 3.0


def _has_math_indicators(cluster: List[LayoutElement]) -> bool:
    for el in cluster:
        for text in el.texts:
            if _RE_MATH.search(text):
                return True
    return False


def _merge_cluster(cluster: List[LayoutElement]) -> FormulaRegion:
    indices = []
    texts = []
    x0s, y0s, x1s, y1s = [], [], [], []
    confidences = []
    
    for el in cluster:
        indices.extend(el.block_indices)
        texts.extend(el.texts)
        x0s.append(el.bbox[0])
        y0s.append(el.bbox[1])
        x1s.append(el.bbox[2])
        y1s.append(el.bbox[3])
        if el.confidence >= 0:
            confidences.append(el.confidence)
            
    bbox = (min(x0s), min(y0s), max(x1s), max(y1s))
    avg_conf = sum(confidences) / len(confidences) if confidences else -1.0
    
    return FormulaRegion(
        block_indices=tuple(indices),
        bbox=bbox,
        confidence=avg_conf,
        texts=tuple(texts)
    )


def merge_formula_fragments(elements: Sequence[LayoutElement]) -> List[Union[LayoutElement, FormulaRegion]]:
    """Merge spatially adjacent formula-like layout elements into FormulaRegions.
    
    Args:
        elements: Sequence of LayoutElement objects from Phase 8.
        
    Returns:
        A list containing original LayoutElements and merged FormulaRegions.
    """
    result: List[Union[LayoutElement, FormulaRegion]] = []
    current_cluster: List[LayoutElement] = []
    
    def flush_cluster():
        if not current_cluster:
            return
        if _has_math_indicators(current_cluster):
            result.append(_merge_cluster(current_cluster))
        else:
            result.extend(current_cluster)
        current_cluster.clear()
        
    for el in elements:
        if el.region_type != LayoutRegionType.TEXT:
            flush_cluster()
            result.append(el)
            continue
            
        if not current_cluster:
            current_cluster.append(el)
        else:
            last_el = current_cluster[-1]
            if _are_adjacent(last_el.bbox, el.bbox):
                current_cluster.append(el)
            else:
                flush_cluster()
                current_cluster.append(el)
                
    flush_cluster()
    return result
