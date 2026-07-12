"""
tests/_cer_probe.py — isolated PaddleOCR CER probe (subprocess helper).

PaddlePaddle has a known Windows DLL-cleanup crash (0xc0000139) at interpreter
exit. To keep the pytest parent process clean, real OCR evaluation runs in this
isolated subprocess: it prints ``CER_RESULT=<json>`` and flushes before exit so
the parent can read the metric even if the subprocess crashes on teardown.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.evaluation_agent import EvaluationAgent


def main():
    sample_dir = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    gt = json.load(open(os.path.join(sample_dir, "ground_truth.json"), "r", encoding="utf-8"))
    printed = {k: v for k, v in gt.items() if v.get("doc_class") == "PRINTED_TEXT"}
    rep = EvaluationAgent().evaluate_ocr_dataset(sample_dir, printed, limit=limit)
    payload = {
        "cer": rep.cer,
        "wer": rep.wer,
        "ocr_available": rep.ocr_available,
        "samples_evaluated": rep.samples_evaluated,
        "notes": rep.notes,
    }
    sys.stdout.write("CER_RESULT=" + json.dumps(payload))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
