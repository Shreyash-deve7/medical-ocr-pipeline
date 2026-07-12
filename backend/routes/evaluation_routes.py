"""
backend/routes/evaluation_routes.py — /api/pipeline/evaluate (Session 7).

Returns an evaluation JSON combining:
  - the existing ``benchmark_results.json`` run summary, and
  - live OCR accuracy (CER / WER via jiwer, computed in the EvaluationAgent)
    plus extraction field-accuracy over the synthetic ``tests/sample_images``
    ground-truth fixtures.

Heavy OCR runs *inside* the handler (lazy imports) and the result is cached in
process memory; pass ``force=true`` to recompute. If the OCR backend is
unavailable the endpoint still returns a valid JSON object with
``evaluation.ocr_available=false`` (never 500).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

router = APIRouter()

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_BENCHMARK_PATH = _BACKEND_DIR / "benchmark_results.json"
_SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "sample_images"
_GROUND_TRUTH_PATH = _SAMPLE_DIR / "ground_truth.json"

# Process-wide cache so repeated calls don't re-run OCR.
_CACHE: Dict[str, Any] = {}


def _load_benchmark() -> Optional[Dict[str, Any]]:
    if not _BENCHMARK_PATH.exists():
        return None
    try:
        return json.loads(_BENCHMARK_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_samples() -> Dict[str, int]:
    if not _GROUND_TRUTH_PATH.exists():
        return {}
    try:
        gt = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    counts: Dict[str, int] = {}
    for ann in gt.values():
        dc = ann.get("doc_class", "UNKNOWN")
        counts[dc] = counts.get(dc, 0) + 1
    return counts


def _compute_evaluation() -> Dict[str, Any]:
    """Run the EvaluationAgent over the sample fixtures; cache the result."""
    from agents.evaluation_agent import EvaluationAgent  # lazy
    from agents.extraction_agent import ExtractionAgent

    agent = EvaluationAgent()
    result = {
        "cer": None,
        "wer": None,
        "field_accuracy": None,
        "samples_evaluated": 0,
        "ocr_available": False,
        "notes": [],
    }

    if not _GROUND_TRUTH_PATH.exists():
        result["notes"].append("no ground_truth.json in sample_images")
        return result

    gt = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    # 1) OCR CER / WER over all annotated samples.
    ocr_report = agent.evaluate_ocr_dataset(str(_SAMPLE_DIR), gt)
    result["cer"] = ocr_report.cer
    result["wer"] = ocr_report.wer
    result["ocr_available"] = ocr_report.ocr_available
    result["samples_evaluated"] = ocr_report.samples_evaluated
    result["notes"].extend(ocr_report.notes)

    # 2) Field accuracy on the PRINTED subset (heuristic extraction, no LLM).
    printed = {k: v for k, v in gt.items() if v.get("doc_class") == "PRINTED_TEXT"}
    if printed and ocr_report.ocr_available:
        try:
            import cv2
            from agents.ocr_router_agent import run_ocr

            ex_agent = ExtractionAgent(llm_client=None)
            accs: list = []
            for fname, ann in printed.items():
                img_path = _SAMPLE_DIR / fname
                if not img_path.exists():
                    continue
                image = cv2.imread(str(img_path))
                if image is None:
                    continue
                ocr_result = run_ocr(image, ann.get("doc_class", "PRINTED_TEXT"))
                ext = ex_agent.run(ocr_result)
                expected = agent.parse_expected_fields(ann.get("text", ""))
                fa = agent.field_accuracy(ext.lab_results, expected)
                if fa is not None:
                    accs.append(fa)
            if accs:
                result["field_accuracy"] = sum(accs) / len(accs)
        except Exception as e:  # pragma: no cover - OCR/extraction edge cases
            result["notes"].append(f"field_accuracy skipped: {e}")

    return result


@router.get("/api/pipeline/evaluate")
@router.post("/api/pipeline/evaluate")
def evaluate_pipeline(force: bool = Query(False, description="Recompute (ignore cache)")):
    benchmark = _load_benchmark()
    sample_counts = _count_samples()

    if force or "evaluation" not in _CACHE:
        _CACHE["evaluation"] = _compute_evaluation()

    evaluation = _CACHE["evaluation"]
    return {
        "status": "ok",
        "benchmark_summary": (benchmark or {}).get("summary") if benchmark else None,
        "benchmark_available": benchmark is not None,
        "sample_images": sample_counts,
        "evaluation": evaluation,
        "notes": [
            "CER/WER computed via jiwer over tests/sample_images ground truth.",
            "benchmark_results.json contains timing metadata only (no OCR transcription).",
        ],
    }
