"""doc-fetch FastAPI service.

Endpoints:
    GET  /health    — health check & supported formats
    POST /extract   — upload a file, get raw text back
    POST /parse     — upload a file, get structured resume JSON back
    POST /evaluate  — upload a resume, get TASTED六力评估 (JSON or Markdown)
    POST /analyze   — upload a resume, get parse + evaluate 组合分析

Run:
    uvicorn api.app:app --host 0.0.0.0 --port 8000
    python -m api.app
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Query, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from extractors import extract_text, get_supported_extensions
from parsers.resume import parse_resume
from parsers.tasted import evaluate_tasted, format_tasted_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="doc-fetch",
    description="多格式文档提取 + 简历结构化解析 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_temp(upload: UploadFile) -> Path:
    """Save an uploaded file to a temp path, preserving the extension."""
    suffix = Path(upload.filename or "file").suffix
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        content = upload.file.read()
        os.write(fd, content)
    finally:
        os.close(fd)
    return Path(tmp_path)


def _validate_extension(filename: str | None) -> None:
    """Raise 400 if the file extension is not supported."""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")
    suffix = Path(filename).suffix.lower()
    supported = get_supported_extensions()
    if suffix not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: '{suffix}'. Supported: {', '.join(supported)}",
        )


# ── Health ──

@app.get("/health")
async def health():
    return {"status": "ok", "supported_formats": get_supported_extensions()}


# ── Extract ──

@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Upload a document and get raw text back.

    Accepts any supported format (PDF, DOCX, XLSX, PPTX, HTML, TXT, ...).
    """
    _validate_extension(file.filename)
    tmp_path = _save_temp(file)
    try:
        text = extract_text(tmp_path)
        return {"filename": file.filename, "chars": len(text), "text": text}
    except Exception as exc:
        logger.error("Extract failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Parse ──

@app.post("/parse")
async def parse(
    file: UploadFile = File(...),
    model: str = Query(default=None, description="LLM model override"),
):
    """Upload a resume document and get structured JSON back.

    Steps: extract text → LLM structured parsing → JSON response.
    """
    _validate_extension(file.filename)
    tmp_path = _save_temp(file)
    try:
        text = extract_text(tmp_path)
        logger.info("Extracted %d chars from %s", len(text), file.filename)

        kwargs = {}
        if model:
            kwargs["model"] = model

        result = parse_resume(text, **kwargs)
        return {
            "filename": file.filename,
            "chars": len(text),
            "data": result,
        }
    except Exception as exc:
        logger.error("Parse failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Evaluate (TASTED 六力) ──

@app.post("/evaluate")
async def evaluate(
    file: UploadFile = File(...),
    model: str = Query(default=None, description="LLM model override"),
    report: bool = Query(default=False, description="Return Markdown report instead of JSON"),
):
    """Upload a resume and get TASTED六力评估 back.

    Based on NetEase's talent model: Taste, Awareness, Standard, Tectonics, Evaluation, Drive.

    - report=false (default): returns structured JSON with scores and evidence
    - report=true: returns human-readable Markdown report
    """
    _validate_extension(file.filename)
    tmp_path = _save_temp(file)
    try:
        text = extract_text(tmp_path)
        logger.info("Extracted %d chars from %s for TASTED evaluation", len(text), file.filename)

        kwargs = {}
        if model:
            kwargs["model"] = model

        result = evaluate_tasted(text, **kwargs)

        if report:
            markdown = format_tasted_report(result)
            return {
                "filename": file.filename,
                "format": "markdown",
                "report": markdown,
            }
        else:
            return {
                "filename": file.filename,
                "format": "json",
                "data": result,
            }
    except Exception as exc:
        logger.error("Evaluate failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Analyze (Parse + Evaluate 组合) ──

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    model: str = Query(default=None, description="LLM model override"),
    report: bool = Query(default=False, description="Include Markdown report for TASTED"),
):
    """Upload a resume and get comprehensive analysis: structured data + TASTED六力评估.

    This endpoint combines /parse and /evaluate into a single call for convenience.

    Returns:
        - parsed: structured resume JSON (education, work experience, projects, etc.)
        - evaluation: TASTED六力评估 (scores, evidence, recommendation)
        - report (optional): Markdown report when report=true
    """
    _validate_extension(file.filename)
    tmp_path = _save_temp(file)
    try:
        # Extract text once
        text = extract_text(tmp_path)
        logger.info("Extracted %d chars from %s for combined analysis", len(text), file.filename)

        kwargs = {}
        if model:
            kwargs["model"] = model

        # Run both in sequence (could be parallelized with asyncio.gather if needed)
        logger.info("Running structured parsing...")
        parsed_result = parse_resume(text, **kwargs)

        logger.info("Running TASTED evaluation...")
        tasted_result = evaluate_tasted(text, **kwargs)

        response = {
            "filename": file.filename,
            "chars": len(text),
            "parsed": parsed_result,
            "evaluation": tasted_result,
        }

        if report:
            response["report"] = format_tasted_report(tasted_result)

        # Add quick summary at top level for convenience
        summary = tasted_result.get("summary", {})
        candidate = tasted_result.get("candidate", {})
        response["summary"] = {
            "candidateName": candidate.get("name") or parsed_result.get("resumeBase", {}).get("applicantName"),
            "currentPosition": candidate.get("currentPosition"),
            "yearsOfExperience": candidate.get("yearsOfExperience"),
            "tastedLevel": summary.get("level"),
            "tastedScore": summary.get("totalScore"),
            "recommendation": summary.get("recommendation"),
            "strengths": summary.get("strengths"),
            "weaknesses": summary.get("weaknesses"),
        }

        return response

    except Exception as exc:
        logger.error("Analyze failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)


# ── Run with: python -m api.app ──

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)
