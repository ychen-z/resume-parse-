"""doc-fetch – Extract raw text from documents in various formats.

Usage:
    python main.py <file_path>                      Extract a single file
    python main.py <dir_path>                       Extract all supported files in a directory
    python main.py <path> -o output.txt             Write result to a file
    python main.py <path> --parse                   Extract + parse into structured JSON
    python main.py <path> --parse -o out.json       Parse and write JSON to file
    python main.py <path> --evaluate                Extract + TASTED六力评估 (JSON)
    python main.py <path> --evaluate --report       Extract + TASTED六力评估 (Markdown报告)
    python main.py <path> --evaluate -o report.md   评估结果写入文件
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from extractors import extract_text, get_supported_extensions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _process_file(path: Path) -> str | None:
    """Extract text from a single file, returning None on failure."""
    try:
        text = extract_text(path)
        logger.info("OK  %s  (%d chars)", path.name, len(text))
        return text
    except ValueError as exc:
        logger.warning("SKIP  %s  (%s)", path.name, exc)
        return None
    except Exception as exc:
        logger.error("FAIL  %s  (%s)", path.name, exc)
        return None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Extract raw text from documents.",
    )
    parser.add_argument(
        "path",
        help="File or directory to extract text from.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Write output to this file instead of stdout.",
    )
    parser.add_argument(
        "-p",
        "--parse",
        action="store_true",
        help="Parse extracted text into structured resume JSON via LLM.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model for --parse (default from .env DEFAULT_LLM_PROVIDER).",
    )
    parser.add_argument(
        "-e",
        "--evaluate",
        action="store_true",
        help="Evaluate resume against NetEase TASTED六力 model via LLM.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="With --evaluate: output a human-readable Markdown report instead of JSON.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    target = Path(args.path)
    if not target.exists():
        logger.error("Path does not exist: %s", target)
        sys.exit(1)

    results: list[str] = []

    if target.is_file():
        text = _process_file(target)
        if text is not None:
            results.append(text)
    elif target.is_dir():
        supported = set(get_supported_extensions())
        files = sorted(
            f for f in target.iterdir() if f.is_file() and f.suffix.lower() in supported
        )
        if not files:
            logger.warning("No supported files found in %s", target)
            sys.exit(0)

        for f in files:
            text = _process_file(f)
            if text is not None:
                results.append(f"=== {f.name} ===\n{text}")
    else:
        logger.error("Not a file or directory: %s", target)
        sys.exit(1)

    output = "\n\n".join(results)

    # --parse: send extracted text through LLM for structured resume JSON
    if args.parse:
        from parsers.resume import parse_resume

        if not output.strip():
            logger.error("No text extracted, nothing to parse.")
            sys.exit(1)

        logger.info("Parsing extracted text into structured resume JSON...")
        parsed = parse_resume(output, model=args.model)
        output = json.dumps(parsed, ensure_ascii=False, indent=2)

    # --evaluate: TASTED六力评估
    if args.evaluate:
        from parsers.tasted import evaluate_tasted, format_tasted_report

        if not output.strip():
            logger.error("No text extracted, nothing to evaluate.")
            sys.exit(1)

        logger.info("Evaluating resume against TASTED六力 model...")
        eval_result = evaluate_tasted(output, model=args.model)

        if args.report:
            output = format_tasted_report(eval_result)
        else:
            output = json.dumps(eval_result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        logger.info("Written to %s", args.output)
    else:
        print(output)


if __name__ == "__main__":
    main()
