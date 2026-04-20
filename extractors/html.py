"""HTML extractor."""

from __future__ import annotations

import logging
from pathlib import Path

from bs4 import BeautifulSoup

from extractors.base import Extractor

logger = logging.getLogger(__name__)


class HTMLExtractor(Extractor):
    """Extract raw text from HTML files by stripping tags."""

    def extract(self, file_path: str | Path) -> str:
        raw = Path(file_path).read_bytes()
        encoding = _detect_encoding(raw)
        html = raw.decode(encoding, errors="replace")

        soup = BeautifulSoup(html, "html.parser")

        # Remove script / style blocks
        for tag in soup(["script", "style"]):
            tag.decompose()

        return soup.get_text(separator="\n", strip=True)


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
