"""Structured JSON generation package — Phase 15.

Provides the canonical intermediate representation between the recognition
phases (7–14) and the downstream LaTeX generation phase (16+).

Public symbols
--------------
Models (immutable DTOs):
    ContentItem        — one logical content element (text / formula / diagram).
    StructuredOption   — one MCQ option with an ordered content body.
    StructuredQuestion — one detected question with body and options.
    StructuredDocument — top-level container for the entire document.

Builder:
    PageElements   — input container grouping per-page recognition outputs.
    build_document — pure assembly function; no OCR, no file I/O.

Serialiser:
    document_to_dict — converts StructuredDocument to a JSON-serialisable dict.
    document_to_json — converts StructuredDocument to a JSON string.
"""

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)
from offline_latex_generator.structurer.builder import (
    PageElements,
    build_document,
)
from offline_latex_generator.structurer.serialiser import (
    document_to_dict,
    document_to_json,
)

__all__ = [
    # Models
    "ContentItem",
    "StructuredOption",
    "StructuredQuestion",
    "StructuredDocument",
    # Builder
    "PageElements",
    "build_document",
    # Serialiser
    "document_to_dict",
    "document_to_json",
]
