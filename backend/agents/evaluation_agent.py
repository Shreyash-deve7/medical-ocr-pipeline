"""
evaluation_agent.py — Agent 7 of the MedVault agentic pipeline.

Computes OCR accuracy (CER / WER via ``jiwer``) and structured-extraction
quality (field accuracy) against ground-truth annotations. Purely algorithmic
(reference.md Section E Agent 7: no LLM prompt).

Design mirrors the other agents:
  - ``jiwer`` is imported lazily inside the metric helpers so the module imports
    even when the optional dependency is absent (graceful degradation).
  - Everything is stdlib + backend modules, so it is unit-testable offline.
  - Never raises on missing ground truth — it returns ``None`` metrics + a
    warning and lets the caller decide how to present the result.

Public surface:
    EvaluationReport dataclass (cer, wer, field_accuracy, samples_evaluated, ...)
    EvaluationAgent.cer(ref, hyp)
    EvaluationAgent.wer(ref, hyp)
    EvaluationAgent.field_accuracy(extracted, ground_truth)
    EvaluationAgent.evaluate_ocr_dataset(images_dir, ground_truth, run_ocr_fn)
    EvaluationAgent.run(ground_truth_text, hypothesis_text, ...)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from loguru import logger


@dataclass
class EvaluationReport:
    """Aggregated evaluation metrics for one (or many) pipeline runs."""

    cer: Optional[float] = None
    wer: Optional[float] = None
    field_accuracy: Optional[float] = None
    samples_evaluated: int = 0
    ocr_available: bool = True
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cer": self.cer,
            "wer": self.wer,
            "field_accuracy": self.field_accuracy,
            "samples_evaluated": self.samples_evaluated,
            "ocr_available": self.ocr_available,
            "notes": list(self.notes),
        }


def _normalise_text(text: str) -> str:
    """Lower-case, collapse whitespace, strip — robust CER/WER comparison."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _normalise_test_key(name: str) -> str:
    """Best-effort canonical test-name key for field-accuracy matching."""
    return re.sub(r"[^a-z0-9]", "", (name or "").strip().lower())


class EvaluationAgent:
    """Agent 7 — OCR (jiwer) + extraction-quality evaluation."""

    # ── jiwer wrappers (lazy import) ──────────────────────────────

    @staticmethod
    def _jiwer():
        try:
            import jiwer  # type: ignore
        except Exception as e:  # pragma: no cover - optional dep missing
            logger.warning("jiwer unavailable: {}; CER/WER disabled", e)
            return None
        return jiwer

    def cer(self, reference: str, hypothesis: str) -> Optional[float]:
        """Character Error Rate in [0, 1] (None if jiwer missing)."""
        jiwer = self._jiwer()
        if jiwer is None:
            return None
        try:
            return float(jiwer.cer(_normalise_text(reference), _normalise_text(hypothesis)))
        except Exception as e:  # pragma: no cover - degenerate input
            logger.warning("jiwer.cer failed: {}", e)
            return None

    def wer(self, reference: str, hypothesis: str) -> Optional[float]:
        """Word Error Rate in [0, 1] (None if jiwer missing)."""
        jiwer = self._jiwer()
        if jiwer is None:
            return None
        try:
            return float(jiwer.wer(_normalise_text(reference), _normalise_text(hypothesis)))
        except Exception as e:  # pragma: no cover - degenerate input
            logger.warning("jiwer.wer failed: {}", e)
            return None

    # ── Field-level extraction accuracy ──────────────────────────

    def field_accuracy(self, extracted: List[Dict[str, Any]],
                       ground_truth: List[Dict[str, Any]],
                       value_tolerance: float = 0.01) -> Optional[float]:
        """
        Fraction of ground-truth fields correctly recovered in ``extracted``.

        A ground-truth field is "correct" when an extracted field shares a
        normalised test name AND (if both values present) the values agree
        within ``value_tolerance`` relative error. Returns None when
        ``ground_truth`` is empty.
        """
        if not ground_truth:
            return None
        gt_by_key: Dict[str, Dict[str, Any]] = {}
        for g in ground_truth:
            key = _normalise_test_key(g.get("test_name", ""))
            if key:
                gt_by_key[key] = g

        matched = 0
        for g in ground_truth:
            key = _normalise_test_key(g.get("test_name", ""))
            if not key or key not in gt_by_key:
                continue
            ex = next((e for e in extracted
                       if _normalise_test_key(e.get("test_name", "")) == key), None)
            if ex is None:
                continue
            gv = g.get("value")
            ev = ex.get("value")
            if gv is None or ev is None:
                matched += 1  # name match is enough when value absent
                continue
            try:
                if abs(float(ev) - float(gv)) <= max(value_tolerance * abs(float(gv)), value_tolerance):
                    matched += 1
            except (TypeError, ValueError):
                continue
        return matched / len(ground_truth)

    # ── Dataset-level OCR evaluation ─────────────────────────────

    def evaluate_ocr_dataset(self, images_dir: str,
                             ground_truth: Dict[str, Dict[str, Any]],
                             run_ocr_fn: Optional[Callable] = None,
                             limit: Optional[int] = None) -> EvaluationReport:
        """
        Run OCR over every annotated image in ``images_dir`` and compute mean
        CER / WER against the ground-truth ``text``.

        :param images_dir: directory containing the sample images.
        :param ground_truth: ``{filename: {"doc_class": ..., "text": ...}}``.
        :param run_ocr_fn: ``callable(image_ndarray, doc_class) -> OCRResult``;
            defaults to ``agents.ocr_router_agent.run_ocr``.
        :param limit: evaluate at most this many samples (for quick smoke runs).
        :returns: :class:`EvaluationReport` (cer/wer are means over samples where
            OCR produced non-empty output; ``ocr_available`` is False when no
            sample could be OCR'd).
        """
        import os

        import cv2

        if run_ocr_fn is None:
            from agents.ocr_router_agent import run_ocr as run_ocr_fn

        report = EvaluationReport(ocr_available=False)
        cers: List[float] = []
        wers: List[float] = []
        evaluated = 0

        items = list(ground_truth.items())
        if limit is not None:
            items = items[:limit]

        for filename, ann in items:
            path = os.path.join(images_dir, filename)
            if not os.path.exists(path):
                report.notes.append(f"missing sample: {filename}")
                continue
            try:
                image = cv2.imread(path)
                if image is None:
                    report.notes.append(f"unreadable image: {filename}")
                    continue
                doc_class = ann.get("doc_class", "PRINTED_TEXT")
                ocr_result = run_ocr_fn(image, doc_class)
            except Exception as e:
                report.notes.append(f"ocr error on {filename}: {e}")
                continue

            hyp = self._ocr_to_text(ocr_result)
            ref = ann.get("text", "")
            if not hyp:
                report.notes.append(f"empty ocr on {filename}")
                continue

            report.ocr_available = True
            evaluated += 1
            c = self.cer(ref, hyp)
            w = self.wer(ref, hyp)
            if c is not None:
                cers.append(c)
            if w is not None:
                wers.append(w)

        report.samples_evaluated = evaluated
        report.cer = (sum(cers) / len(cers)) if cers else None
        report.wer = (sum(wers) / len(wers)) if wers else None
        if evaluated == 0:
            report.notes.append("no samples could be OCR'd (OCR backend unavailable?)")
        return report

    @staticmethod
    def parse_expected_fields(text: str) -> List[Dict[str, Any]]:
        """
        Best-effort parse of ``"Test 78 U/L"`` style lines into
        ``[{"test_name": ..., "value": ..., "unit": ...}, ...]`` for use as
        extraction ground truth when a structured annotation is unavailable.
        """
        out: List[Dict[str, Any]] = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.search(r"([A-Za-z][A-Za-z \-/]*?)\s+([\d.]+)\s*([A-Za-z/µ]+)?\s*$", line)
            if not m:
                continue
            name = m.group(1).strip()
            try:
                value = float(m.group(2))
            except ValueError:
                continue
            unit = (m.group(3) or "").strip()
            if name:
                out.append({"test_name": name, "value": value, "unit": unit})
        return out

    @staticmethod
    def _ocr_to_text(ocr_result) -> str:
        """Flatten an :class:`OCRResult` raw output to comparable text."""
        raw = getattr(ocr_result, "raw_output", "")
        if isinstance(raw, list):
            rows = []
            for row in raw:
                cells = row if isinstance(row, (list, tuple)) else [row]
                rows.append(" ".join(str(c) for c in cells if str(c).strip()))
            return "\n".join(rows)
        return str(raw)

    # ── Top-level run ─────────────────────────────────────────────

    def run(self, ground_truth_text: str, hypothesis_text: str,
            extracted_json: Optional[List[Dict[str, Any]]] = None,
            ground_truth_json: Optional[List[Dict[str, Any]]] = None) -> EvaluationReport:
        """
        Single-pair evaluation.

        :returns: :class:`EvaluationReport` with cer/wer (from the text pair) and
            field_accuracy (when both JSON args are supplied).
        """
        report = EvaluationReport(samples_evaluated=1)
        report.cer = self.cer(ground_truth_text, hypothesis_text)
        report.wer = self.wer(ground_truth_text, hypothesis_text)
        if extracted_json is not None and ground_truth_json is not None:
            report.field_accuracy = self.field_accuracy(extracted_json, ground_truth_json)
        return report
