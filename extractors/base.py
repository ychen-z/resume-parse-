"""Base extractor interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class Extractor(ABC):
    """Base class for all document extractors.

    Subclasses implement ``extract`` to convert a file into raw text.
    """

    @abstractmethod
    def extract(self, file_path: str | Path) -> str:
        """Extract raw text from the given file.

        Args:
            file_path: Path to the source file.

        Returns:
            Extracted plain text content.
        """
        ...
