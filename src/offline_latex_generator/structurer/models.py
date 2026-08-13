"""Structured JSON generation data models — Phase 15.

Provides immutable dataclasses that form the canonical intermediate
representation between the per-element recognition phases (7–14) and
the downstream LaTeX generation phase (16+).

Public types
------------
ContentItem       : one logical piece of content — text, formula, or diagram.
StructuredOption  : a single MCQ option with an ordered body of ContentItems.
StructuredQuestion: one detected question with body and options.
StructuredDocument: top-level container for the whole processed document.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple

from PIL import Image


# ---------------------------------------------------------------------------
# ContentItem
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContentItem:
    """One logical piece of content at any position in the document.

    Attributes
    ----------
    kind:
        ``"text"``    — normal / heading / question-stem text.
        ``"formula"`` — a recognised mathematical formula.
        ``"diagram"`` — an extracted image/diagram.
    text:
        Plain-text content; set for ``kind="text"``, ``None`` otherwise.
    latex:
        Pix2Text-recognised LaTeX string; set for ``kind="formula"``,
        ``None`` otherwise.
    diagram_id:
        Stable reference ID (e.g. ``"diagram_001"``); set for
        ``kind="diagram"``, ``None`` otherwise.
    bbox:
        Axis-aligned bounding box ``(x0, y0, x1, y1)`` in page-pixel
        coordinates.  Used to preserve document order.
    block_index:
        Zero-based index of the originating OCR block in document order.
        ``None`` when the item has no single originating block (e.g. a merged
        formula spanning several blocks — use the first block index then).
    source_page:
        Zero-based page index from which this item was extracted.
        Defaults to ``0`` for single-page documents.
    confidence:
        OCR confidence in [0.0, 1.0]; ``-1.0`` when not available.
    """

    kind: Literal["text", "formula", "diagram"]
    text: Optional[str]
    latex: Optional[str]
    diagram_id: Optional[str]
    bbox: Tuple[float, float, float, float]
    block_index: Optional[int]
    source_page: int = 0
    confidence: float = -1.0


# ---------------------------------------------------------------------------
# StructuredOption
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StructuredOption:
    """One MCQ option with an ordered sequence of content items.

    Attributes
    ----------
    label:
        Uppercase letter label, e.g. ``"A"``, ``"B"``, ``"C"``, ``"D"``.
    body:
        Ordered list of :class:`ContentItem` objects that make up the
        option content (text, embedded formula, embedded diagram, …).
    """

    label: str
    body: Tuple[ContentItem, ...]

    def __post_init__(self) -> None:
        if not self.label or not self.label.strip():
            raise ValueError("StructuredOption.label must not be empty.")


# ---------------------------------------------------------------------------
# StructuredQuestion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StructuredQuestion:
    """One detected question with body content and MCQ options.

    Attributes
    ----------
    question_number:
        Human-readable question number as it appears in the document,
        e.g. ``"1"``, ``"2"``, ``"Q3"``.
    body:
        Ordered list of :class:`ContentItem` objects forming the question
        stem.  Diagrams that appear between the stem and the options, or
        inside the stem itself, are embedded here in document order.
    options:
        Ordered list of :class:`StructuredOption` objects in label order.
        Empty for non-MCQ questions.
    """

    question_number: str
    body: Tuple[ContentItem, ...]
    options: Tuple[StructuredOption, ...]


# ---------------------------------------------------------------------------
# StructuredDocument
# ---------------------------------------------------------------------------


@dataclass
class StructuredDocument:
    """Top-level container for the entire processed document.

    This is the only **mutable** class in the module — ``diagrams`` must
    be populated during assembly and the ``pages`` count is set once.
    All nested DTOs (:class:`StructuredQuestion`, :class:`ContentItem`, …)
    remain frozen.

    Attributes
    ----------
    pages:
        Total number of pages in the source document.
    questions:
        Ordered list of :class:`StructuredQuestion` objects in document order.
    preamble:
        Ordered list of :class:`ContentItem` objects that appear *before*
        the first detected question (e.g. exam header, instructions).
    diagrams:
        Mapping from stable diagram ID (e.g. ``"diagram_001"``) to the
        in-memory cropped :class:`PIL.Image.Image`.  The PIL images are
        never serialised to JSON; ``document_to_dict()`` replaces them
        with their string IDs.  Images are held here until the ZIP-export
        phase writes them to disk.
    """

    pages: int
    questions: List[StructuredQuestion] = field(default_factory=list)
    preamble: List[ContentItem] = field(default_factory=list)
    diagrams: Dict[str, Image.Image] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "ContentItem",
    "StructuredOption",
    "StructuredQuestion",
    "StructuredDocument",
]
