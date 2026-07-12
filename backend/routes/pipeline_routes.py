"""
backend/routes/pipeline_routes.py — POST /api/pipeline/run (Session 8).

The unified entry-point that orchestrates the full agentic DAG
(preprocess -> classify -> OCR router -> extract -> validate -> diagnose ->
[summary] -> [evaluate]) over an uploaded medical-lab image and returns a single
``PipelineResult`` JSON.

The heavy OCR / LLM paths live behind the existing offline agents (faked via
``ocr_router_agent.AGENT_FACTORIES`` in tests), so the default request path is
LLM-free / network-free / GPU-free. A malformed upload returns 400 — never 500.

Also exposes ``/api/gpu/status`` and ``/api/gpu/preload`` so the frontend can
monitor and trigger GPU model loading (classifier CNN + PaddleOCR + Qwen-VL).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter()


@router.get("/api/gpu/status")
def gpu_status_endpoint():
    """Return the current GPU / model-load status (no auth required)."""
    from gpu_manager import gpu_status
    return gpu_status().to_dict()


@router.post("/api/gpu/preload")
def gpu_preload_endpoint():
    """Trigger eager GPU model preloading (classifier + PaddleOCR + Qwen-VL).

    Returns immediately; loading runs in a background thread. Poll
    ``/api/gpu/status`` to track progress.
    """
    from gpu_manager import preload_models
    preload_models(blocking=False)
    return {"status": "preload_started", "message": "Models are loading in the background. Poll /api/gpu/status for progress."}


@router.post("/api/pipeline/run")
async def run_pipeline_endpoint(
    file: UploadFile = File(...),
    evaluate: bool = Form(False, description="Merge Agent 7 evaluation metrics"),
    summary: bool = Form(False, description="Attach a doctor-facing summary"),
    use_graph: bool = Form(True, description="Orchestrate via the PipelineGraph DAG"),
):
    """
    Run the full pipeline over a multipart image upload.

    :returns: a ``PipelineResult`` JSON (preprocessing + classification +
        extracted LabReport + validation + diagnosis; summary/evaluation optional).
    """
    if file is None:
        raise HTTPException(status_code=400, detail="No image file provided")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty image file")

    # Lazy import keeps the router importable without loading OCR/agent deps.
    from services.pipeline_service import run_pipeline

    try:
        result = run_pipeline(
            content,
            evaluate=evaluate,
            summary=summary,
            use_graph=use_graph,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Pipeline failed: {e}")

    return result.to_dict()
