"""evaluation/benchmark.py - Session 4 benchmarking script."""
from __future__ import annotations

import json, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend'))

from backend.agents.ocr_result import OCRResult

# ── Module-level fake OCR (defined before any imports) ──────────
def _fake_run_ocr(preprocessed_image, doc_class):
    return OCRResult(raw_output='', engine='FakeOCR', confidence=0.0, processing_time_seconds=0.0)

# Force-import ocr_router_agent so it registers in sys.modules
import backend.agents.ocr_router_agent

# Patch in sys.modules (for the 'from agents.ocr_router_agent import run_ocr' inside _run_ocr)
sys.modules['backend.agents.ocr_router_agent'].run_ocr = _fake_run_ocr

# Import pipeline and ALSO patch its local binding from 'from agents.ocr_router_agent import run_ocr'
from backend import pipeline as _pl
_pl.run_ocr = _fake_run_ocr   # <-- this is the binding _run_ocr() uses

from backend.pipeline import run_pipeline
from evaluation.metrics import compute_batch_metrics, compute_detail

SAMPLE_DIR = ROOT / 'tests' / 'sample_images'
GT_PATH = SAMPLE_DIR / 'ground_truth.json'
OUTPUT_PATH = ROOT / 'eval_reports' / 'metrics_latest.json'

class _FakeExtractionLLM:
    def complete(self, prompt, inp): return json.dumps({'lab_results': []})

class _FakeDiagnosisLLM:
    def complete(self, prompt, inp): return json.dumps({
        'clinical_patterns': [], 'abnormal_values': [], 'urgent_flags': [],
        'suggested_followup': [], 'summary_for_doctor': 'Benchmark run (no LLM).',
    })

def main():
    print('='*60); print('  PIPELINE BENCHMARK'); print('='*60)
    if not GT_PATH.exists():
        print(f'ERROR: Ground truth not found at {GT_PATH}'); sys.exit(1)
    gt_data = json.loads(GT_PATH.read_text(encoding='utf-8'))
    image_files = [f for f in GT_PATH.parent.iterdir() if f.suffix in ('.png','.jpg','.jpeg')]
    print(f'Found {len(image_files)} images, {len(gt_data)} ground truth entries')
    print('OCR routed to FakeOCR (GPU-free mode)')
    results, references, hypotheses = [], [], []
    for img_path in sorted(image_files):
        fname = img_path.name
        if fname not in gt_data:
            print(f'  SKIP {fname}'); continue
        gt_text = gt_data[fname].get('text', '')
        references.append(gt_text)
        print(f'  Processing: {fname}')
        t0 = time.perf_counter()
        try:
            pipeline_result = run_pipeline(str(img_path), llm_client=_FakeExtractionLLM(),
                                           diagnosis_client=_FakeDiagnosisLLM(), include_summary=False)
            elapsed_s = time.perf_counter() - t0
            ocr_text = ''
            if pipeline_result.ocr:
                raw = pipeline_result.ocr.get('raw_output', '')
                ocr_text = raw if isinstance(raw, str) else ''
            hypotheses.append(ocr_text)
            detail = compute_detail(gt_text, ocr_text, doc_id=fname)
            detail['pipeline_timing_seconds'] = round(elapsed_s, 3)
            detail['pipeline_timing_ms'] = pipeline_result.timing
            detail['doc_class'] = gt_data[fname].get('doc_class', 'UNKNOWN')
            results.append(detail)
            print(f'    CER={detail["cer"]:.2f}%  WER={detail["wer"]:.2f}%  time={elapsed_s:.2f}s')
        except Exception as e:
            print(f'    ERROR: {e}'); hypotheses.append('')
            results.append({'doc_id': fname, 'cer': 100.0, 'wer': 100.0, 'exact_match': 0.0,
                            'error': str(e), 'doc_class': gt_data[fname].get('doc_class', 'UNKNOWN')})
    agg = compute_batch_metrics(references, hypotheses)
    print('\n' + '='*60); print('  AGGREGATE RESULTS'); print('='*60)
    print(f'  Images: {agg["count"]}  jiwer: {agg["jiwer_available"]}')
    print(f'  CER mean={agg["cer_mean"]:.2f}%  std={agg["cer_std"]:.2f}%  min={agg["cer_min"]:.2f}%  max={agg["cer_max"]:.2f}%')
    print(f'  WER mean={agg["wer_mean"]:.2f}%  std={agg["wer_std"]:.2f}%  min={agg["wer_min"]:.2f}%  max={agg["wer_max"]:.2f}%')
    print(f'  Exact match acc: {agg["exact_match_accuracy"]:.2%}')
    report = {'generated_at': datetime.now(timezone.utc).isoformat(), 'benchmark_mode': 'fake_ocr',
              'sample_dir': str(SAMPLE_DIR), 'aggregate': agg, 'per_image': results}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\n  Report: {OUTPUT_PATH}'); print('Done.')
    return report

if __name__ == '__main__': main()