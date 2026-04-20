"""TASTED evaluator – score resumes against NetEase's six-force talent model."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TASTED_PROMPT_PATH = _PROJECT_ROOT / "prompts" / "tasted-eval.md"

load_dotenv(_PROJECT_ROOT / ".env")


def _load_prompt(prompt_path: Path | None = None) -> str:
    path = prompt_path or _TASTED_PROMPT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def evaluate_tasted(
    text: str,
    *,
    model: str | None = None,
    prompt_path: Path | None = None,
) -> dict:
    """Evaluate a resume against the TASTED six-force model.

    Args:
        text: Raw resume text (or already-extracted plain text).
        model: Override model name (default from ``DEFAULT_LLM_PROVIDER``).
        prompt_path: Optional override for the TASTED prompt file.

    Returns:
        A dict with keys: candidate, tastedEvaluation, summary.
    """
    system_prompt = _load_prompt(prompt_path)

    resolved_model = model or os.environ.get("DEFAULT_LLM_PROVIDER", "gpt-4o")

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

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human", "请对以下简历进行TASTED六力评估：\n\n{text}"),
    ])
    chain = prompt | llm | JsonOutputParser()

    logger.info("Evaluating TASTED: model=%s, base_url=%s", resolved_model, base_url or "default")
    result = chain.invoke({"system_prompt": system_prompt, "text": text})

    # Log summary
    summary = result.get("summary", {})
    candidate = result.get("candidate", {})
    logger.info(
        "TASTED evaluated: candidate=%s, level=%s, totalScore=%s, recommendation=%s",
        candidate.get("name", "unknown"),
        summary.get("level", "?"),
        summary.get("totalScore", "?"),
        summary.get("recommendation", "?"),
    )
    return result


def format_tasted_report(result: dict) -> str:
    """Format a TASTED evaluation result as a human-readable Markdown report."""
    candidate = result.get("candidate", {})
    evaluation = result.get("tastedEvaluation", {})
    summary = result.get("summary", {})

    force_labels = {
        "taste": "T · 审美力 (Taste)",
        "awareness": "A · 洞察力 (Awareness)",
        "standard": "S · 标准感 (Standard)",
        "tectonics": "T · 结构力 (Tectonics)",
        "evaluation": "E · 判断力 (Evaluation)",
        "drive": "D · 自驱力 (Drive)",
    }

    lines = [
        f"# TASTED 六力评估报告",
        f"",
        f"**候选人**：{candidate.get('name', 'N/A')}",
        f"**当前职位**：{candidate.get('currentPosition', 'N/A')}",
        f"**工作年限**：{candidate.get('yearsOfExperience', 'N/A')} 年",
        f"",
        f"---",
        f"",
        f"## 六力评分",
        f"",
        f"| 能力 | 得分 | 评语 |",
        f"|------|------|------|",
    ]

    for key, label in force_labels.items():
        force = evaluation.get(key, {})
        score = force.get("score")
        score_display = f"{score}/10" if score is not None else "N/A"
        comment = force.get("comment", "").replace("\n", " ")
        lines.append(f"| {label} | {score_display} | {comment} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 各项详细证据",
        f"",
    ]

    for key, label in force_labels.items():
        force = evaluation.get(key, {})
        evidence_list = force.get("evidence") or []
        score = force.get("score")
        lines.append(f"### {label}｜{score}/10" if score else f"### {label}｜N/A")
        if evidence_list:
            for ev in evidence_list:
                lines.append(f"- {ev}")
        else:
            lines.append("- 无明确证据")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 综合评估",
        f"",
        f"| 项目 | 内容 |",
        f"|------|------|",
        f"| 综合总分 | **{summary.get('totalScore', 'N/A')}** / 60 |",
        f"| 综合等级 | **{summary.get('level', 'N/A')}** |",
        f"| 招聘建议 | **{summary.get('recommendation', 'N/A')}** |",
        f"",
        f"**突出优势**：{', '.join(summary.get('strengths') or [])}",
        f"",
        f"**待提升项**：{', '.join(summary.get('weaknesses') or [])}",
        f"",
        f"**综合评语**：",
        f"",
        f"{summary.get('overallComment', '')}",
        f"",
    ]

    return "\n".join(lines)
