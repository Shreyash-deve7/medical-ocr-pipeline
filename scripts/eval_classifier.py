"""scripts/eval_classifier.py — Standalone evaluation script for the 3-class document classifier.

Usage:
    python scripts/eval_classifier.py --labels backend/labels.json [--weights backend/weights/classifier_3class.pth]

The script:
1. Loads images referenced in ``labels.json``.
2. Runs ``DocumentClassifier.predict_3class()`` on each.
3. Prints a confusion matrix and per-class precision/recall/F1.
4. Optionally saves a detailed JSON report to ``backend/eval_report.json``.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Tuple

import cv2
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("eval_classifier")

CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
CLASS_TO_IDX = {cls: i for i, cls in enumerate(CLASSES)}
IDX_TO_CLASS = {i: cls for cls, i in CLASS_TO_IDX.items()}


def load_labels(labels_path: Path) -> Dict[str, Dict]:
    with open(labels_path) as f:
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
        true_idx = CLASS_TO_IDX[true_cls]
        pred_idx = CLASS_TO_IDX[pred_cls]
        cm[true_idx][pred_idx] += 1
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


def print_metrics(metrics: Dict[str, Dict[str, float]]) -> None:
    print("\nPer-class metrics:")
    print(f"{'Class':<12} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 54)
    for cls, m in metrics.items():
        print(f"{cls:<12} {m['precision']:>10.3f} {m['recall']:>10.3f} {m['f1']:>10.3f} {m['support']:>10}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the 3-class document classifier.")
    parser.add_argument("--labels", type=str, default="backend/labels.json", help="Path to labels.json")
    parser.add_argument("--weights", type=str, default=None, help="Optional path to classifier weights")
    parser.add_argument("--output", type=str, default="backend/eval_report.json", help="Path to save detailed JSON report")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    labels_path = Path(args.labels)
    if not labels_path.exists():
        logger.error(f"Labels file not found: {labels_path}")
        sys.exit(1)

    labels = load_labels(labels_path)
    logger.info(f"Loaded {len(labels)} labels from {labels_path}")

    # Import classifier (add backend to path).
    sys.path.insert(0, str(project_root / "backend"))
    from document_classifier import DocumentClassifier

    logger.info("Initialising DocumentClassifier...")
    cls = DocumentClassifier(weights_path=args.weights)

    # Run predictions.
    predictions = {}
    skipped = 0
    for rel_path, meta in sorted(labels.items()):
        img_path = project_root / rel_path
        if not img_path.exists():
            logger.warning(f"Missing image: {img_path}")
            skipped += 1
            continue
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            logger.warning(f"Failed to read image: {img_path}")
            skipped += 1
            continue
        try:
            result = cls.predict_3class(image)
            predictions[rel_path] = result.doc_class
        except Exception as e:
            logger.error(f"Classification failed for {rel_path}: {e}")
            skipped += 1

    logger.info(f"Predicted {len(predictions)} images (skipped {skipped})")

    # Compute metrics.
    cm = compute_confusion_matrix(predictions, labels)
    print_confusion_matrix(cm)
    metrics = compute_metrics(cm)
    print_metrics(metrics)

    # Overall accuracy.
    total = cm.sum()
    correct = np.trace(cm)
    accuracy = correct / total if total > 0 else 0.0
    print(f"\nOverall accuracy: {accuracy:.3f} ({int(correct)}/{int(total)})")

    # Save report.
    report = {
        "accuracy": float(accuracy),
        "confusion_matrix": cm.tolist(),
        "per_class": metrics,
        "predictions": predictions,
        "labels": labels,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
