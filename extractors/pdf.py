"""PDF extractor with text-first strategy and OCR fallback.

Strategy:
  1. Try PyMuPDF ``page.get_text()`` (fast, free).
  2. If text is too short **or garbled** (e.g. Type3 fonts without ToUnicode),
     fall back to PaddleOCR.
  3. If PaddleOCR result is still poor, fall back to Vision API (GPT-4o).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from extractors.base import Extractor

logger = logging.getLogger(__name__)

# Minimum characters per page to consider embedded-text extraction successful.
_MIN_TEXT_THRESHOLD = 20
# If recognisable characters (CJK + ASCII letters + digits) make up less than
# this fraction of total non-whitespace characters, treat the text as garbled.
_MIN_LEGIBLE_RATIO = 0.6
# If more than this fraction of non-empty lines are garbled, fall back to OCR.
_MAX_GARBLED_LINE_RATIO = 0.15
# Max image dimension sent to OCR – controls memory and latency.
_MAX_IMAGE_DIM = 2048
# When a page image exceeds this height, split it into strips for OCR.
_MAX_STRIP_HEIGHT = 2048


def _is_char_legible(c: str) -> bool:
    """Return True if a single character is recognisable."""
    return (
        "\u4e00" <= c <= "\u9fff"       # CJK Unified Ideographs
        or "\u3400" <= c <= "\u4dbf"    # CJK Extension A
        or "\uf900" <= c <= "\ufaff"    # CJK Compatibility Ideographs
        or "\u3000" <= c <= "\u303f"    # CJK Symbols & Punctuation
        or "\uff00" <= c <= "\uffef"    # Full-width Forms
        or "\u0020" <= c <= "\u007e"    # ASCII printable
    )


def _line_is_garbled(line: str) -> bool:
    """Return True if a single line looks garbled."""
    non_ws = [c for c in line if not c.isspace()]
    if len(non_ws) < 3:
        return False  # too short to judge
    legible = sum(1 for c in non_ws if _is_char_legible(c))
    return (legible / len(non_ws)) < _MIN_LEGIBLE_RATIO


def _is_legible(text: str) -> bool:
    """Return True if *text* looks like real readable content.

    Three-layer heuristic:

    1. **Page-level legible-ratio** – at least ``_MIN_LEGIBLE_RATIO`` of
       non-whitespace characters must be recognisable (CJK or ASCII
       printable).

    2. **Garbled-Chinese detection** – substantial text with zero CJK
       characters yet > 15% non-ASCII is almost certainly a Chinese
       document with broken Type3 fonts.

    3. **Line-level garbled ratio** – even if the page *overall* passes,
       if > 15% of non-empty lines are individually garbled, the page has
       mixed-encoding issues (e.g. headers garbled, body OK) and should
       fall back to OCR for a clean result.
    """
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return False

    total = len(non_ws)

    cjk_count = 0
    ascii_print_count = 0
    non_ascii_count = 0

    for c in non_ws:
        if (
            "\u4e00" <= c <= "\u9fff"
            or "\u3400" <= c <= "\u4dbf"
            or "\uf900" <= c <= "\ufaff"
            or "\u3000" <= c <= "\u303f"
            or "\uff00" <= c <= "\uffef"
        ):
            cjk_count += 1
        elif "\u0020" <= c <= "\u007e":
            ascii_print_count += 1
        else:
            non_ascii_count += 1

    legible_count = cjk_count + ascii_print_count
    ratio = legible_count / total

    # Layer 1: page-level legible-ratio gate
    if ratio < _MIN_LEGIBLE_RATIO:
        return False

    # Layer 2: garbled-Chinese detection (zero CJK + lots of non-ASCII)
    if (
        total >= 100
        and cjk_count == 0
        and non_ascii_count / total > 0.15
    ):
        return False

    # Layer 3: line-level garbled ratio
    # Catches mixed-encoding pages where headers/labels are garbled but
    # body paragraphs are OK – the page ratio looks fine but individual
    # lines reveal the problem.
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) >= 5:
        garbled_lines = sum(1 for ln in lines if _line_is_garbled(ln))
        if garbled_lines / len(lines) > _MAX_GARBLED_LINE_RATIO:
            return False

    return True


class PDFExtractor(Extractor):
    """Extract text from PDF files.

    Handles text-based PDFs, garbled-font PDFs, and scanned PDFs
    transparently.
    """

    def extract(self, file_path: str | Path) -> str:
        doc = fitz.open(str(file_path))
        pages: list[str] = []

        try:
            for page in doc:
                text = page.get_text().strip()

                if len(text) >= _MIN_TEXT_THRESHOLD and _is_legible(text):
                    pages.append(text)
                else:
                    reason = (
                        "garbled text (illegible font encoding)"
                        if len(text) >= _MIN_TEXT_THRESHOLD
                        else f"< {_MIN_TEXT_THRESHOLD} chars"
                    )
                    logger.info(
                        "Page %d: %s, falling back to OCR",
                        page.number + 1,
                        reason,
                    )
                    pages.append(self._ocr_page(page))
        finally:
            doc.close()

        return "\n\n".join(pages)

    # ------------------------------------------------------------------
    # OCR helpers
    # ------------------------------------------------------------------

    def _page_to_image(self, page: fitz.Page) -> Image.Image:
        """Render a PDF page to a PIL Image.

        Scales down so that the *width* does not exceed ``_MAX_IMAGE_DIM``.
        Height is left unconstrained here – ``_ocr_page`` handles slicing.
        """
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Scale by width only – keeps text readable on tall pages
        if img.width > _MAX_IMAGE_DIM:
            ratio = _MAX_IMAGE_DIM / img.width
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        return img

    def _ocr_page(self, page: fitz.Page) -> str:
        """OCR a single page, splitting into strips if it is very tall."""
        img = self._page_to_image(page)

        # If the image is short enough, OCR directly
        if img.height <= _MAX_STRIP_HEIGHT:
            return self._ocr_image(img, page.number)

        # Split tall page into horizontal strips
        logger.info(
            "Page %d is very tall (%dx%d), splitting into strips",
            page.number + 1,
            img.width,
            img.height,
        )

        strips: list[str] = []
        y = 0
        strip_idx = 0
        while y < img.height:
            bottom = min(y + _MAX_STRIP_HEIGHT, img.height)
            strip = img.crop((0, y, img.width, bottom))
            strip_idx += 1
            logger.info(
                "  Strip %d: y=%d–%d (%dx%d)",
                strip_idx, y, bottom, strip.width, strip.height,
            )
            text = self._ocr_image(strip, page.number)
            if text.strip():
                strips.append(text)
            y = bottom

        return "\n".join(strips)

    def _ocr_image(self, img: Image.Image, page_number: int) -> str:
        """OCR a single image: RapidOCR first, Vision API fallback."""
        text = self._paddleocr(img)
        if len(text.strip()) >= _MIN_TEXT_THRESHOLD:
            return text

        logger.info(
            "OCR result too short on page %d, falling back to Vision API",
            page_number + 1,
        )
        return self._vision_api(img)

    # ------------------------------------------------------------------
    # RapidOCR  (ONNX-based, supports Chinese + English out of the box)
    # ------------------------------------------------------------------

    @staticmethod
    def _paddleocr(img: Image.Image) -> str:
        """Run RapidOCR on a PIL Image. Covers Chinese + English."""
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            logger.warning("rapidocr-onnxruntime not installed, skipping OCR")
            return ""

        import numpy as np

        ocr = RapidOCR()
        result, _ = ocr(np.array(img))

        lines: list[str] = []
        if result:
            for line_info in result:
                # line_info: [box, text, confidence]
                text = line_info[1] if len(line_info) > 1 else ""
                if text:
                    lines.append(str(text))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Vision API (GPT-4o)
    # ------------------------------------------------------------------

    @staticmethod
    def _vision_api(img: Image.Image) -> str:
        """Use OpenAI GPT-4o Vision to extract text from an image."""
        try:
            import base64

            import openai
        except ImportError:
            logger.warning("openai not installed, skipping Vision API fallback")
            return ""

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please extract all text from this image. "
                            "Return only the raw text, preserving the original layout as much as possible.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content or ""
