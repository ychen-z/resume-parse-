"""Extractor registry – maps file extensions to extractor instances."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from extractors.base import Extractor
from extractors.docx import DocxExtractor
from extractors.html import HTMLExtractor
from extractors.pdf import PDFExtractor
from extractors.plaintext import PlainTextExtractor
from extractors.pptx import PptxExtractor
from extractors.xlsx import ExcelExtractor

logger = logging.getLogger(__name__)

# ── Default registry ──

_REGISTRY: Dict[str, Extractor] = {}


def _build_default_registry() -> None:
    """Populate the registry with built-in extractors."""
    pdf = PDFExtractor()
    docx = DocxExtractor()
    xlsx = ExcelExtractor()
    pptx = PptxExtractor()
    html = HTMLExtractor()
    plain = PlainTextExtractor()

    mapping: dict[str, Extractor] = {
        ".pdf": pdf,
        ".docx": docx,
        ".doc": docx,  # python-docx can handle some .doc files
        ".xlsx": xlsx,
        ".xls": xlsx,
        ".pptx": pptx,
        ".html": html,
        ".htm": html,
        ".txt": plain,
        ".md": plain,
        ".csv": plain,
        ".log": plain,
        ".json": plain,
        ".xml": plain,
        ".rst": plain,
    }
    _REGISTRY.update(mapping)


_build_default_registry()


# ── Public API ──


def register(ext: str, extractor: Extractor) -> None:
    """Register a custom extractor for a file extension.

    Args:
        ext: File extension including the dot, e.g. ``".pdf"``.
        extractor: An ``Extractor`` instance.
    """
    _REGISTRY[ext.lower()] = extractor


def get_supported_extensions() -> list[str]:
    """Return a sorted list of supported file extensions."""
    return sorted(_REGISTRY.keys())


def extract_text(file_path: str | Path) -> str:
    """Extract raw text from *file_path* using the appropriate extractor.

    Args:
        file_path: Path to the source file.

    Returns:
        Extracted plain text.

    Raises:
        ValueError: If the file extension is not supported.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    extractor = _REGISTRY.get(suffix)

    if extractor is None:
        raise ValueError(
            f"Unsupported file format: '{suffix}'. "
            f"Supported: {', '.join(get_supported_extensions())}"
        )

    logger.info("Extracting %s with %s", path.name, type(extractor).__name__)
    return extractor.extract(path)
