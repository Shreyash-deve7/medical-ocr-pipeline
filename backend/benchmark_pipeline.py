"""
benchmark_pipeline.py — Classify -> OCR timing benchmark for pipeline_v1.

Measures the real pipeline flow on the Patient_Kastoor and WhatsApp datasets:
  1. preprocess + classify (printed / handwritten)
  2. OCR: printed -> PaddleOCR (GPU), handwritten -> Qwen2.5-VL (GPU)

Paddle and torch CUDA DLLs clash in one process (Hard Rule #2), so the OCR
stages run in SEPARATE subprocesses (one for Paddle, one for torch). The
classify stage is CPU-only and runs on its own.

Run:
  venv\\Scripts\\python.exe pipeline_v1\\backend\\benchmark_pipeline.py run-all
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = Path(__file__).resolve().parent
DATASETS = ["Patient_Kastoor", "WhatsApp.Unknown.2026-04-27.at.12.10.10"]
VALID_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

PRED_FILE = BACKEND / "predictions.json"
OCR_PRINTED_FILE = BACKEND / "ocr_printed.json"
OCR_HW_FILE = BACKEND / "ocr_handwritten.json"
RESULTS_FILE = BACKEND / "benchmark_results.json"


def _repo_root() -> Path:
    return ROOT


def collect_images(dataset: str) -> list[Path]:
    base = _repo_root() / dataset
    if not base.exists():
        return []
    out = []
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        if "__MACOSX" in p.parts:
            continue
        if p.name.startswith("._"):
            continue
        if p.suffix.lower() not in VALID_EXT:
            continue
        out.append(p)
    return out


def _stats(values: list[float]) -> dict:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0, "n": 0}
    s = sorted(values)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {
        "mean": round(statistics.mean(s), 4),
        "median": round(statistics.median(s), 4),
        "p95": round(p95, 4),
        "min": round(s[0], 4),
        "max": round(s[-1], 4),
        "n": len(s),
    }


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(_repo_root()))
    except ValueError:
        return str(p)


def stage_classify():
    sys.path.insert(0, str(BACKEND))
    from image_processing import preprocess_image
    from document_classifier import DocumentClassifier

    weights = os.environ.get("CLASSIFIER_WEIGHTS", "")
    classifier = DocumentClassifier(weights_path=weights if weights else None)
    mode = "mobilenet_gpu" if (classifier.model is not None and weights) else "heuristic_cpu"
    print(f"[classify] mode={mode}")

    predictions: dict[str, dict] = {}
    for dataset in DATASETS:
        for p in collect_images(dataset):
            t0 = time.time()
            try:
                img = preprocess_image(str(p))
                doc_type = classifier.predict(img)
                dt = round(time.time() - t0, 4)
                predictions[_rel(p)] = {"doc_type": doc_type, "classify_seconds": dt, "status": "ok"}
            except Exception as e:
                dt = round(time.time() - t0, 4)
                predictions[_rel(p)] = {"doc_type": "error", "classify_seconds": dt,
                                        "status": "error", "error": str(e)}
            print(f"  {_rel(p)} -> {predictions[_rel(p)]['doc_type']} ({predictions[_rel(p)]['classify_seconds']}s)")

    PRED_FILE.write_text(json.dumps({"mode": mode, "predictions": predictions}, indent=2), encoding="utf-8")
    print(f"[classify] wrote {PRED_FILE}")


def stage_ocr_printed():
    sys.path.insert(0, str(BACKEND))
    from backend.ocr.providers.paddle_provider import run_paddle_ocr_on_document, _verify_gpu

    gpu = _verify_gpu()
    print(f"[ocr-printed] use_gpu={gpu}")
    preds = json.loads(PRED_FILE.read_text(encoding="utf-8"))
    mode = preds["mode"]
    printed = [k for k, v in preds["predictions"].items() if v.get("doc_type") == "printed"]

    results = []
    warmed = False
    for rel in printed:
        p = _repo_root() / rel
        if not p.exists():
            results.append({"path": rel, "status": "error", "error": "missing file"})
            continue
        try:
            if not warmed:
                run_paddle_ocr_on_document(str(p), use_gpu=True)
                warmed = True
                continue
            t0 = time.time()
            lines = run_paddle_ocr_on_document(str(p), use_gpu=True)
            dt = round(time.time() - t0, 4)
            confs = [l["confidence"] for l in lines]
            results.append({
                "path": rel, "status": "ok", "ocr_seconds": dt,
                "line_count": len(lines),
                "avg_confidence": round(statistics.mean(confs), 4) if confs else 0.0,
                "text_length": sum(len(l["text"]) for l in lines),
            })
        except Exception as e:
            results.append({"path": rel, "status": "error", "error": str(e)})
        print(f"  {rel} -> {results[-1].get('ocr_seconds', 'ERR')}s lines={results[-1].get('line_count', '?')}")

    OCR_PRINTED_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[ocr-printed] wrote {OCR_PRINTED_FILE} ({len(results)} images)")


def stage_ocr_handwritten():
    sys.path.insert(0, str(BACKEND))
    from backend.ocr.providers.qwen_provider import QwenVLProvider

    server_url = os.environ.get("QWEN_VL_SERVER_URL", "")
    print(f"[ocr-handwritten] server_url={server_url or '(in-process)'}")
    preds = json.loads(PRED_FILE.read_text(encoding="utf-8"))
    hw = [k for k, v in preds["predictions"].items() if v.get("doc_type") == "handwritten"]

    results = []
    provider = None
    try:
        provider = QwenVLProvider(server_url=server_url)
    except Exception as e:
        print(f"[ocr-handwritten] model unavailable: {e}")
        for rel in hw:
            results.append({"path": rel, "status": "skipped", "error": f"model unavailable: {e}"})
        OCR_HW_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"[ocr-handwritten] wrote {OCR_HW_FILE} (skipped)")
        return

    warmed = False
    for rel in hw:
        p = _repo_root() / rel
        if not p.exists():
            results.append({"path": rel, "status": "error", "error": "missing file"})
            continue
        try:
            if not warmed:
                provider.extract_text(str(p), p.suffix.lstrip("."))
                warmed = True
                continue
            t0 = time.time()
            text = provider.extract_text(str(p), p.suffix.lstrip("."))
            dt = round(time.time() - t0, 4)
            results.append({"path": rel, "status": "ok", "ocr_seconds": dt, "text_length": len(text)})
        except Exception as e:
            results.append({"path": rel, "status": "error", "error": str(e)})
        print(f"  {rel} -> {results[-1].get('ocr_seconds', 'ERR')}s chars={results[-1].get('text_length', '?')}")

    OCR_HW_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"[ocr-handwritten] wrote {OCR_HW_FILE} ({len(results)} images)")


def stage_report():
    preds = json.loads(PRED_FILE.read_text(encoding="utf-8")) if PRED_FILE.exists() else {"mode": "?", "predictions": {}}
    printed_ocr = json.loads(OCR_PRINTED_FILE.read_text(encoding="utf-8")) if OCR_PRINTED_FILE.exists() else []
    hw_ocr = json.loads(OCR_HW_FILE.read_text(encoding="utf-8")) if OCR_HW_FILE.exists() else []

    printed_map = {r["path"]: r for r in printed_ocr}
    hw_map = {r["path"]: r for r in hw_ocr}

    per_image = []
    for rel, meta in preds["predictions"].items():
        rec = {
            "path": rel,
            "doc_type": meta.get("doc_type"),
            "classify_seconds": meta.get("classify_seconds"),
        }
        ocr = printed_map.get(rel) or hw_map.get(rel)
        if ocr:
            rec["ocr_seconds"] = ocr.get("ocr_seconds")
            rec["status"] = ocr.get("status")
            rec["line_count"] = ocr.get("line_count")
            rec["avg_confidence"] = ocr.get("avg_confidence")
            rec["text_length"] = ocr.get("text_length")
            rec["error"] = ocr.get("error")
        if rec.get("classify_seconds") is not None and rec.get("ocr_seconds") is not None:
            rec["total_seconds"] = round(rec["classify_seconds"] + rec["ocr_seconds"], 4)
        per_image.append(rec)

    classify_times = [r["classify_seconds"] for r in per_image if r.get("classify_seconds") is not None]
    printed_times = [r["ocr_seconds"] for r in per_image if r.get("doc_type") == "printed" and r.get("ocr_seconds") is not None]
    hw_times = [r["ocr_seconds"] for r in per_image if r.get("doc_type") == "handwritten" and r.get("ocr_seconds") is not None]
    total_times = [r["total_seconds"] for r in per_image if r.get("total_seconds") is not None]
    printed_confs = [r["avg_confidence"] for r in per_image if r.get("avg_confidence")]

    n_printed = sum(1 for r in per_image if r.get("doc_type") == "printed")
    n_hw = sum(1 for r in per_image if r.get("doc_type") == "handwritten")

    summary = {
        "classification_mode": preds.get("mode"),
        "total_images": len(per_image),
        "printed": n_printed,
        "handwritten": n_hw,
        "classify_seconds": _stats(classify_times),
        "ocr_printed_seconds": _stats(printed_times),
        "ocr_handwritten_seconds": _stats(hw_times),
        "total_seconds": _stats(total_times),
        "printed_avg_confidence": round(statistics.mean(printed_confs), 4) if printed_confs else 0.0,
    }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": DATASETS,
        "summary": summary,
        "per_image": per_image,
    }
    RESULTS_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n==================== BENCHMARK SUMMARY ====================")
    print(f"Classification mode : {summary['classification_mode']}")
    print(f"Images              : {summary['total_images']} (printed={n_printed}, handwritten={n_hw})")
    print(f"Classify (s)        : {summary['classify_seconds']}")
    print(f"OCR printed (s)     : {summary['ocr_printed_seconds']}")
    print(f"OCR handwritten (s) : {summary['ocr_handwritten_seconds']}")
    print(f"Total/image (s)     : {summary['total_seconds']}")
    print(f"Printed avg conf    : {summary['printed_avg_confidence']}")
    print(f"Results saved to    : {RESULTS_FILE}")
    print("===========================================================")

    try:
        subprocess.run("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu "
                       "--format=csv,noheader", shell=True, check=False)
    except Exception:
        pass


def run_all():
    py = sys.executable
    script = str(__file__)
    print(f"[run-all] using python: {py}")
    subprocess.run([py, script, "classify"], check=True)
    subprocess.run([py, script, "ocr-printed"], check=True)
    subprocess.run([py, script, "ocr-handwritten"], check=True)
    subprocess.run([py, script, "report"], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["classify", "ocr-printed", "ocr-handwritten", "report", "run-all"])
    args = ap.parse_args()
    if args.mode == "classify":
        stage_classify()
    elif args.mode == "ocr-printed":
        stage_ocr_printed()
    elif args.mode == "ocr-handwritten":
        stage_ocr_handwritten()
    elif args.mode == "report":
        stage_report()
    elif args.mode == "run-all":
        run_all()


if __name__ == "__main__":
    main()
