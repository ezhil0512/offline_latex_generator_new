"""Structured document serialisation — Phase 15.

Provides :func:`document_to_dict` and :func:`document_to_json` for
converting a :class:`StructuredDocument` to a plain Python dict / JSON
string that is fully serialisable without any PIL Image objects.

Rules
-----
- PIL ``Image.Image`` objects stored in ``StructuredDocument.diagrams``
  are **never** included in the output.  Each diagram is represented by
  its string ID only (``"diagram_id": "diagram_001"``).
- The ``diagrams`` top-level key in the output JSON lists all known
  diagram IDs as a list of strings in sorted order.
- All other fields are recursively converted to plain Python primitives.
- Round-trip guarantee: ``json.loads(document_to_json(doc))`` succeeds
  without error for any valid :class:`StructuredDocument`.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from offline_latex_generator.structurer.models import (
    ContentItem,
    StructuredDocument,
    StructuredOption,
    StructuredQuestion,
)


# ---------------------------------------------------------------------------
# Internal converters
# ---------------------------------------------------------------------------


def _content_item_to_dict(item: ContentItem) -> Dict[str, Any]:
    return {
        "kind": item.kind,
        "text": item.text,
        "latex": item.latex,
        "diagram_id": item.diagram_id,
        "bbox": list(item.bbox),
        "block_index": item.block_index,
        "source_page": item.source_page,
        "confidence": item.confidence,
    }


def _option_to_dict(opt: StructuredOption) -> Dict[str, Any]:
    return {
        "label": opt.label,
        "body": [_content_item_to_dict(ci) for ci in opt.body],
    }


def _question_to_dict(q: StructuredQuestion) -> Dict[str, Any]:
    return {
        "question_number": q.question_number,
        "body": [_content_item_to_dict(ci) for ci in q.body],
        "options": [_option_to_dict(opt) for opt in q.options],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def document_to_dict(doc: StructuredDocument) -> Dict[str, Any]:
    """Convert a :class:`StructuredDocument` to a JSON-serialisable dict.

    PIL ``Image.Image`` objects are replaced by their string diagram IDs.
    The ``"diagrams"`` key in the output contains a sorted list of all
    diagram ID strings (the actual images remain in
    ``StructuredDocument.diagrams`` for later export).

    Args:
        doc: The assembled :class:`StructuredDocument`.

    Returns:
        A plain Python ``dict`` that can be passed directly to
        ``json.dumps()`` without error.
    """
    return {
        "pages": doc.pages,
        "preamble": [_content_item_to_dict(ci) for ci in doc.preamble],
        "questions": [_question_to_dict(q) for q in doc.questions],
        # Only the IDs — PIL images are deliberately excluded
        "diagrams": sorted(doc.diagrams.keys()),
    }


def document_to_json(doc: StructuredDocument, *, indent: int = 2) -> str:
    """Serialise a :class:`StructuredDocument` to a JSON string.

    Args:
        doc:    The assembled :class:`StructuredDocument`.
        indent: JSON indentation level (default ``2``).

    Returns:
        A UTF-8 JSON string.  ``json.loads()`` of this string succeeds
        without error.
    """
    return json.dumps(document_to_dict(doc), ensure_ascii=False, indent=indent)


__all__ = [
    "document_to_dict",
    "document_to_json",
]
