"""Resume parser – convert raw text into structured JSON via LangChain."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Project root & default prompt file.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "llm.md"

# Load .env from project root (won't overwrite existing env vars).
load_dotenv(_PROJECT_ROOT / ".env")


def _load_prompt(prompt_path: Path | None = None) -> str:
    """Read the system prompt from *prompt_path* (or the default llm.md)."""
    path = prompt_path or _PROMPT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def parse_resume(
    text: str,
    *,
    model: str | None = None,
    prompt_path: Path | None = None,
) -> dict:
    """Parse raw resume text into structured JSON.

    Configuration is read from ``.env``:
      - ``OPENAI_API_KEY`` – required.
      - ``BASE_URL`` – optional, API base URL.
      - ``DEFAULT_LLM_PROVIDER`` – default model name.

    Args:
        text: Raw text extracted from a resume document.
        model: Override model name (default from ``DEFAULT_LLM_PROVIDER``).
        prompt_path: Optional override for the system prompt file.

    Returns:
        A dict matching the schema defined in ``prompts/llm.md``.
    """
    system_prompt = _load_prompt(prompt_path)

    # Resolve model: explicit arg > env DEFAULT_LLM_PROVIDER > fallback
    resolved_model = model or os.environ.get("DEFAULT_LLM_PROVIDER", "gpt-4o")

    # Build LLM
    llm_kwargs: dict = {"model": resolved_model, "temperature": 0}

    base_url = os.environ.get("BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if base_url:
        llm_kwargs["base_url"] = base_url

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DASHSCOPE_API_KEY")
    if api_key:
        llm_kwargs["api_key"] = api_key

    llm = ChatOpenAI(**llm_kwargs).bind(
        response_format={"type": "json_object"},
    )

    # Build chain: prompt → LLM → JSON parser
    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "{text}"),
    ])
    chain = prompt | llm | JsonOutputParser()

    logger.info("Calling LLM: model=%s, base_url=%s", resolved_model, base_url or "default")
    result = chain.invoke({"system_prompt": system_prompt, "text": text})

    logger.info(
        "Resume parsed: %d top-level keys, model=%s",
        len(result),
        resolved_model,
    )
    return result
