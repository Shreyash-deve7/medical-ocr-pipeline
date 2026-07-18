"""scripts/eval_classifier.py — Standalone evaluation for the 3-class document classifier.

Usage:
    python scripts/eval_classifier.py --labels backend/labels.json \
           [--splits backend/dataset_splits.json] \
           [--weights backend/weights/classifier_3class.pth] \
           --output backend/eval_report.json

Behaviour:
  1. If a split file is given (or found), the held-out ``test`` split is used
     as the evaluation set. Otherwise all labelled images are used.
  2. Runs ``DocumentClassifier.predict_3class()`` on each and reports a
     confusion matrix + per-class precision/recall/F1 + macro-F1 + accuracy.
  3. Performs 5-fold cross-validation *on the train split only* to estimate
     generalisation; the test split is never used for tuning.
  4. Writes a detailed JSON report to ``--output``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("eval_classifier")

CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
CLASS_TO_IDX = {cls: i for i, cls in enumerate(CLASSES)}
IDX_TO_CLASS = {i: cls for cls, i in CLASS_TO_IDX.items()}


def load_labels(labels_path: Path) -> Dict[str, Dict]:
    with open(labels_path, encoding="utf-8") as f:
        return json.load(f)


def compute_confusion_matrix(
    predictions: Dict[str, str],
    labels: Dict[str, Dict],
) -> np.ndarray:
    n = len(CLASSES)
    cm = np.zeros((n, n), dtype=int)
    for rel_path, pred_cls in predictions.items():
        if rel_path not in labels:
            continue
        true_cls = labels[rel_path]["true_class"]
        if true_cls not in CLASS_TO_IDX or pred_cls not in CLASS_TO_IDX:
            continue
        cm[CLASS_TO_IDX[true_cls]][CLASS_TO_IDX[pred_cls]] += 1
    return cm


def print_confusion_matrix(cm: np.ndarray) -> None:
    print("\nConfusion Matrix (rows=true, cols=predicted):")
    header = " " * 12 + " ".join(f"{c:>12}" for c in CLASSES)
    print(header)
    for i, true_cls in enumerate(CLASSES):
        row = f"{true_cls:>12} " + " ".join(f"{cm[i][j]:>12}" for j in range(len(CLASSES)))
        print(row)


def compute_metrics(cm: np.ndarray) -> Dict[str, Dict[str, float]]:
    metrics = {}
    for i, cls in enumerate(CLASSES):
        tp = cm[i][i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        metrics[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(cm[i, :].sum()),
        }
    return metrics


def macro_f1(metrics: Dict[str, Dict[str, float]]) -> float:
    vals = [m["f1"] for m in metrics.values()]
    return float(np.mean(vals)) if vals else 0.0


def print_metrics(metrics: Dict[str, Dict[str, float]]) -> None:
    print("\nPer-class metrics:")
    print(f"{'Class':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 54)
    for cls, m in metrics.items():
        print(f"{cls:<12} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>10.3f} {m['support']:>10}")
    print(f"{'MACRO':<12} {'':>10} {'':>10} {macro_f1(metrics):>10.3f}")


def run_predictions(
    cls,
    rel_paths: List[str],
    project_root: Path,
    labels: Dict[str, Dict],
) -> Tuple[Dict[str, str], int]:
    """Return (predictions, skipped)."""
    predictions: Dict[str, str] = {}
    skipped = 0
    for rel_path in rel_paths:
        img_path = project_root / rel_path
        if not img_path.exists():
            logger.warning("Missing image: %s", img_path)
            skipped += 1
            continue
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            logger.warning("Failed to read image: %s", img_path)
            skipped += 1
            continue
        try:
            result = cls.predict_3class(image)
            predictions[rel_path] = result.doc_class
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Classification failed for %s: %s", rel_path, e)
            skipped += 1
    return predictions, skipped


def _cv_fold(
    cls,
    fold_paths: List[str],
    project_root: Path,
    labels: Dict[str, Dict],
) -> np.ndarray:
    preds, _ = run_predictions(cls, fold_paths, project_root, labels)
    return compute_confusion_matrix(preds, labels)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the 3-class document classifier.")
    parser.add_argument("--labels", type=str, default="backend/labels.json", help="Path to labels.json")
    parser.add_argument("--splits", type=str, default="backend/dataset_splits.json",
                        help="Path to dataset_splits.json (optional)")
    parser.add_argument("--weights", type=str, default=None, help="Optional path to classifier weights")
    parser.add_argument("--output", type=str, default="backend/eval_report.json", help="JSON report path")
    parser.add_argument("--folds", type=int, default=5, help="k for k-fold CV on train split")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    labels_path = Path(args.labels)
    if not labels_path.exists():
        logger.error("Labels file not found: %s", labels_path)
        sys.exit(1)

    labels = load_labels(labels_path)
    logger.info("Loaded %d labels from %s", len(labels), labels_path)

    # Resolve split file.
    splits_path = Path(args.splits)
    if not splits_path.is_absolute():
        splits_path = project_root / splits_path
    if not splits_path.exists():
        logger.warning("Splits file not found (%s); evaluating on ALL labels.", splits_path)
        splits_path = None

    # Import classifier. `document_classifier` resolves as a top-level module
    # only when its containing dir (backend/) is on sys.path; it internally does
    # `from backend.classifier import ...`, so the project root must also be on path.
    sys.path.insert(0, str(project_root / "backend"))
    sys.path.insert(0, str(project_root))
    from document_classifier import DocumentClassifier

    logger.info("Initialising DocumentClassifier...")
    cls = DocumentClassifier(weights_path=args.weights)

    # Determine eval set (held-out test) and CV set (train).
    if splits_path is not None:
        with open(splits_path, encoding="utf-8") as f:
            splits = json.load(f)
        test_paths = splits["splits"]["test"]
        train_paths = splits["splits"]["train"]
        val_paths = splits["splits"]["val"]
        logger.info("Splits loaded: train=%d val=%d test=%d",
                    len(train_paths), len(val_paths), len(test_paths))
        eval_paths = test_paths
        eval_name = "test (held-out)"
    else:
        eval_paths = list(labels.keys())
        train_paths = list(labels.keys())
        eval_name = "all labels"

    # ── Held-out evaluation ───────────────────────────────────────
    predictions, skipped = run_predictions(cls, eval_paths, project_root, labels)
    logger.info("Predicted %d images (%s) — skipped %d", len(predictions), eval_name, skipped)

    cm = compute_confusion_matrix(predictions, labels)
    print_confusion_matrix(cm)
    metrics = compute_metrics(cm)
    print_metrics(metrics)

    total = int(cm.sum())
    correct = int(np.trace(cm))
    accuracy = correct / total if total > 0 else 0.0
    mf1 = macro_f1(metrics)
    print(f"\nOverall accuracy: {accuracy:.3f} ({correct}/{total})")
    print(f"Macro-F1: {mf1:.3f}")

    # ── 5-fold CV on train split (estimate only; never tunes) ─────
    cv_results = None
    if splits_path is not None and len(train_paths) >= args.folds:
        logger.info("Running %d-fold CV on train split...", args.folds)
        rng = np.random.default_rng(42)
        idx = np.arange(len(train_paths))
        rng.shuffle(idx)
        fold_size = len(idx) // args.folds
        fold_cms = []
        for k in range(args.folds):
            start = k * fold_size
            end = (k + 1) * fold_size if k < args.folds - 1 else len(idx)
            fold_idx = idx[start:end]
            fold_paths = [train_paths[i] for i in fold_idx]
            fold_cm = _cv_fold(cls, fold_paths, project_root, labels)
            fold_cms.append(fold_cm.tolist())
            fm = compute_metrics(fold_cm)
            logger.info(
                "  fold %d: acc=%.3f macroF1=%.3f (TABLE_R=%.2f HW_R=%.2f PT_R=%.2f)",
                k,
                (np.trace(fold_cm) / fold_cm.sum()) if fold_cm.sum() else 0.0,
                macro_f1(fm),
                fm["TABLE"]["recall"], fm["HANDWRITTEN"]["recall"], fm["PRINTED_TEXT"]["recall"],
            )
        cv_results = {
            "folds": args.folds,
            "confusion_matrices": fold_cms,
            "mean_accuracy": float(np.mean([
                np.trace(np.array(c)) / np.array(c).sum() for c in fold_cms
            ])) if fold_cms else 0.0,
        }

    # ── Save report ───────────────────────────────────────────────
    report = {
        "eval_set": eval_name,
        "accuracy": float(accuracy),
        "macro_f1": float(mf1),
        "confusion_matrix": cm.tolist(),
        "per_class": metrics,
        "predictions": predictions,
        "cv_train": cv_results,
    }
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = project_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved to %s", out_path)


if __name__ == "__main__":
    main()
