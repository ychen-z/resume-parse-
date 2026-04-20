"""Excel (.xlsx / .xls) extractor."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from extractors.base import Extractor

logger = logging.getLogger(__name__)


class ExcelExtractor(Extractor):
    """Extract raw text from Excel files.

    Reads every sheet, converts each row to tab-separated text.
    """

    def extract(self, file_path: str | Path) -> str:
        sheets = pd.read_excel(str(file_path), sheet_name=None, dtype=str)
        parts: list[str] = []

        for sheet_name, df in sheets.items():
            parts.append(f"[Sheet: {sheet_name}]")
            # Header row
            parts.append("\t".join(str(c) for c in df.columns))
            # Data rows
            for _, row in df.iterrows():
                vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
                if vals:
                    parts.append("\t".join(vals))

        return "\n".join(parts)
