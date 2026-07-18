"""
evaluation/metrics.py — Session 4 evaluation metrics.

Provides standard OCR quality metrics:
    - Character Error Rate (CER)
    - Word Error Rate (WER)
    - Exact Match Accuracy

Uses the `jiwer` library for CER/WER computation.
"""
from __future__ import annotations

import re
from typing import List, Optional

try:
    import jiwer
    _JIWER_AVAILABLE = True
except ImportError:
    _JIWER_AVAILABLE = False


def _ensure_jiwer():
    """Raise RuntimeError if jiwer is not installed."""
    if not _JIWER_AVAILABLE:
        raise RuntimeError(
            "jiwer is required for CER/WER computation. "
            "Install it with: pip install jiwer>=3.0.0"
        )


# ── Core metric functions ───────────────────────────────────────

def character_error_rate(
    reference: str,
    hypothesis: str,
    *,
    normalize_whitespace: bool = True,
    lowercase: bool = True,
) -> float:
    """
    Compute Character Error Rate (CER) between reference and hypothesis.

    CER = (编辑距离 / 参考文本长度) × 100%

    Args:
        reference: Ground-truth text string.
        hypothesis: OCR-produced text string.
        normalize_whitespace: Collapse multiple spaces before comparison.
        lowercase: Convert both strings to lowercase before comparison.

    Returns:
        CER as a percentage (0.0 = perfect, 100.0 = completely wrong).
        Returns 0.0 when reference is empty.
    """
    _ensure_jiwer()

    if not reference:
        return 0.0 if not hypothesis else 100.0

    transforms = jiwer.Compose([
        jiwer.ToLowerCase() if lowercase else jiwer.RemoveWhiteSpace(),
        jiwer.RemoveMultipleSpaces() if normalize_whitespace else jiwer.RemoveWhiteSpace(),
        jiwer.Strip(),
    ])

    try:
        cer = jiwer.wer(
            reference,
            hypothesis,
            reference_transform=transforms,
            hypothesis_transform=transforms,
        )
    except Exception:
        # Fallback: simple character-level Levenshtein
        return _cer_fallback(reference, hypothesis)

    return round(cer * 100, 4)


def word_error_rate(
    reference: str,
    hypothesis: str,
    *,
    normalize_whitespace: bool = True,
    lowercase: bool = True,
) -> float:
    """
    Compute Word Error Rate (WER) between reference and hypothesis.

    WER = (编辑距离 / 参考词数) × 100%

    Args:
        reference: Ground-truth text string.
        hypothesis: OCR-produced text string.
        normalize_whitespace: Collapse multiple spaces before comparison.
        lowercase: Convert both strings to lowercase before comparison.

    Returns:
        WER as a percentage (0.0 = perfect, 100.0 = completely wrong).
        Returns 0.0 when reference is empty.
    """
    _ensure_jiwer()

    if not reference:
        return 0.0 if not hypothesis else 100.0

    transforms = jiwer.Compose([
        jiwer.ToLowerCase() if lowercase else jiwer.RemoveWhiteSpace(),
        jiwer.RemoveMultipleSpaces() if normalize_whitespace else jiwer.RemoveWhiteSpace(),
        jiwer.Strip(),
    ])

    try:
        wer = jiwer.wer(
            reference,
            hypothesis,
            reference_transform=transforms,
            hypothesis_transform=transforms,
        )
    except Exception:
        # Fallback: word-level Levenshtein
        return _wer_fallback(reference, hypothesis)

    return round(wer * 100, 4)


def exact_match_accuracy(
    reference: str,
    hypothesis: str,
    *,
    normalize_whitespace: bool = True,
    lowercase: bool = True,
) -> float:
    """
    Compute exact-match accuracy (0/1) as a float.

    Returns 1.0 if reference and hypothesis are identical after normalisation,
    0.0 otherwise.
    """
    if not reference and not hypothesis:
        return 1.0

    ref = reference
    hyp = hypothesis

    if lowercase:
        ref = ref.lower()
        hyp = hyp.lower()

    if normalize_whitespace:
        ref = re.sub(r"\s+", " ", ref).strip()
        hyp = re.sub(r"\s+", " ", hyp).strip()

    return 1.0 if ref == hyp else 0.0


# ── Batch aggregation ───────────────────────────────────────────

def compute_batch_metrics(
    references: List[str],
    hypotheses: List[str],
) -> dict:
    """
    Compute CER, WER, and accuracy over a batch of reference/hypothesis pairs.

    Args:
        references: List of ground-truth text strings.
        hypotheses: List of OCR-produced text strings (same length as references).

    Returns:
        dict with keys:
            cer_mean, cer_std, cer_min, cer_max,
            wer_mean, wer_std, wer_min, wer_max,
            exact_match_accuracy,
            count (number of pairs),
            jiwer_available (bool),
    """
    if len(references) != len(hypotheses):
        raise ValueError(
            f"references and hypotheses must have the same length, "
            f"got {len(references)} and {len(hypotheses)}"
        )

    if not references:
        return {
            "cer_mean": 0.0, "cer_std": 0.0, "cer_min": 0.0, "cer_max": 0.0,
            "wer_mean": 0.0, "wer_std": 0.0, "wer_min": 0.0, "wer_max": 0.0,
            "exact_match_accuracy": 1.0,
            "count": 0,
            "jiwer_available": _JIWER_AVAILABLE,
        }

    cer_values = [character_error_rate(r, h) for r, h in zip(references, hypotheses)]
    wer_values = [word_error_rate(r, h) for r, h in zip(references, hypotheses)]
    acc_values = [exact_match_accuracy(r, h) for r, h in zip(references, hypotheses)]

    import statistics

    return {
        # CER
        "cer_mean": round(statistics.mean(cer_values), 4),
        "cer_std": round(statistics.stdev(cer_values) if len(cer_values) > 1 else 0.0, 4),
        "cer_min": round(min(cer_values), 4),
        "cer_max": round(max(cer_values), 4),
        # WER
        "wer_mean": round(statistics.mean(wer_values), 4),
        "wer_std": round(statistics.stdev(wer_values) if len(wer_values) > 1 else 0.0, 4),
        "wer_min": round(min(wer_values), 4),
        "wer_max": round(max(wer_values), 4),
        # Accuracy
        "exact_match_accuracy": round(statistics.mean(acc_values), 4),
        # Metadata
        "count": len(references),
        "jiwer_available": _JIWER_AVAILABLE,
    }


# ── Fallback implementations (no jiwer dependency) ───────────────

def _levenshtein_distance(s1: str, s2: str) -> int:
    """Pure-Python Levenshtein distance for fallback."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev[j + 1] + 1
            deletions = curr[j] + 1
            substitutions = prev[j] + (c1 != c2)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]


def _cer_fallback(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 100.0
    dist = _levenshtein_distance(reference.lower(), hypothesis.lower())
    return round(dist / max(len(reference), 1) * 100, 4)


def _wer_fallback(reference: str, hypothesis: str) -> float:
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    if not ref_words:
        return 0.0 if not hyp_words else 100.0
    dist = _levenshtein_distance(" ".join(ref_words), " ".join(hyp_words))
    # Use word count as denominator
    return round(dist / max(len(ref_words), 1) * 100, 4)


# ── Per-result detail record ────────────────────────────────────

def compute_detail(
    reference: str,
    hypothesis: str,
    doc_id: Optional[str] = None,
) -> dict:
    """
    Compute all metrics for a single reference/hypothesis pair with metadata.

    Returns a dict suitable for appending to a JSON report.
    """
    return {
        "doc_id": doc_id,
        "cer": character_error_rate(reference, hypothesis),
        "wer": word_error_rate(reference, hypothesis),
        "exact_match": exact_match_accuracy(reference, hypothesis),
        "reference_length_chars": len(reference),
        "hypothesis_length_chars": len(hypothesis),
        "reference_length_words": len(reference.split()),
        "hypothesis_length_words": len(hypothesis.split()),
    }