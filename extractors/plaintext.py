"""Plain-text extractor (txt, md, csv, log, etc.)."""

from __future__ import annotations

import logging
from pathlib import Path

from extractors.base import Extractor

logger = logging.getLogger(__name__)


class PlainTextExtractor(Extractor):
    """Read files that are already plain text, with encoding auto-detection."""

    def extract(self, file_path: str | Path) -> str:
        raw = Path(file_path).read_bytes()
        encoding = _detect_encoding(raw)
        return raw.decode(encoding, errors="replace")


def _detect_encoding(data: bytes) -> str:
    """Best-effort encoding detection."""
    try:
        import chardet

        result = chardet.detect(data)
        if result and result.get("encoding"):
            return result["encoding"]
    except ImportError:
        pass
    return "utf-8"
