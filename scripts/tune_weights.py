"""scripts/tune_weights.py — Optimize heuristic scoring weights via gradient-descent.

Loads all labeled images, extracts the 15-feature vector via the live
``DocumentClassifier._extract_features`` (which delegates to
``classifier.heuristics.compute_features``), then trains a one-vs-rest
logistic-regression scorer with class-balanced instance weights. The learned
``_FEATURE_MEAN`` / ``_FEATURE_STD`` / ``_W`` / ``_B`` arrays are
written directly into ``backend/classifier/heuristics.py``.

Usage: python scripts/tune_weights.py --labels backend/labels.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=str, default="backend/labels.json")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root / "backend"))
    sys.path.insert(0, str(project_root))
    from document_classifier import DocumentClassifier
    from classifier.heuristics import _FEATURE_ORDER

    with open(project_root / args.labels) as f:
        labels = json.load(f)

    cls = DocumentClassifier()

    features = []
    for rel_path, meta in sorted(labels.items()):
        img_path = project_root / rel_path
        if not img_path.exists():
            continue
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        fv = cls._extract_features(image)
        features.append((fv.to_dict(), CLASS_TO_IDX[meta["true_class"]]))

    print(f"Loaded {len(features)} feature vectors")

    feature_names = list(_FEATURE_ORDER)

    X = np.array([[f[name] for name in feature_names] for f, _ in features])
    y = np.array([label for _, label in features])

    n_classes = 3
    n_features = len(feature_names)
    n_samples = len(features)

    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-6
    X_norm = (X - X_mean) / X_std

    W = np.zeros((n_classes, n_features))
    B = np.zeros(n_classes)
    lr = 0.1
    epochs = 4000
    class_counts = np.array([(y == c).sum() for c in range(n_classes)])
    inst_w = np.array([n_samples / (n_classes * class_counts[yi]) for yi in y])

    for c in range(n_classes):
        y_c = (y == c).astype(np.float64)
        w = np.zeros(n_features)
        b = 0.0
        for _ in range(epochs):
            z = X_norm @ w + b
            p = 1 / (1 + np.exp(-z))
            grad_w = (X_norm * (inst_w * (p - y_c))[:, None]).sum(axis=0) / n_samples
            grad_b = np.mean(inst_w * (p - y_c))
            w -= lr * grad_w
            b -= lr * grad_b
        W[c] = w
        B[c] = b

    scores = X_norm @ W.T + B
    preds = np.argmax(scores, axis=1)
    acc = np.mean(preds == y)
    print(f"\nOptimized accuracy: {acc:.3f} ({int(acc * n_samples)}/{n_samples})")

    cm = np.zeros((3, 3), dtype=int)
    for true, pred in zip(y, preds):
        cm[true][pred] += 1
    print("\nConfusion Matrix (rows=true, cols=predicted):")
    header = " " * 12 + " ".join(f"{c:>12}" for c in CLASSES)
    print(header)
    for i, true_cls in enumerate(CLASSES):
        row = f"{true_cls:>12} " + " ".join(f"{cm[i][j]:>12}" for j in range(3))
        print(row)
    for i, cls_name in enumerate(CLASSES):
        rec = cm[i][i] / cm[i].sum() if cm[i].sum() > 0 else 0
        print(f"  {cls_name} recall: {rec:.3f} ({cm[i][i]}/{cm[i].sum()})")

    print("\n" + "=" * 80)
    print("LEARNED WEIGHTS (normalized scale, per class):")
    print("=" * 80)
    header = f"{'Feature':<28}" + "".join(f"{c:>16}" for c in CLASSES)
    print(header)
    print("-" * 80)
    for j, fname in enumerate(feature_names):
        row = f"{fname:<28}" + "".join(f"{W[c][j]:>16.4f}" for c in range(3))
        print(row)
    print(f"{'BIAS':<28}" + "".join(f"{B[c]:>16.4f}" for c in range(3)))

    # Write the retuned arrays into the live heuristics module.
    out_path = project_root / "backend" / "classifier" / "heuristics.py"
    src = out_path.read_text(encoding="utf-8")
    new_block = (
        "_FEATURE_MEAN = np.array([\n"
        + "    " + ", ".join(f"{v:.4f}" for v in X_mean) + ",\n"
        + "])\n"
        + "_FEATURE_STD = np.array([\n"
        + "    " + ", ".join(f"{v:.4f}" for v in X_std) + ",\n"
        + "])\n\n"
        + "_W = np.array([\n"
        + "".join(
            "    [" + ", ".join(f"{W[c][j]:.4f}" for j in range(n_features)) + "],\n"
            for c in range(3)
        )
        + "])\n"
        + f"_B = np.array([" + ", ".join(f"{B[c]:.4f}" for c in range(3)) + "])"
    )
    pattern = re.compile(
        r"_FEATURE_MEAN = np\.array\(\[.*?\]\)\s*"
        r"_FEATURE_STD = np\.array\(\[.*?\]\)\s*"
        r"_W = np\.array\(\[.*?\]\)\s*"
        r"_B = np\.array\(\[.*?\]\)",
        re.DOTALL,
    )
    if pattern.search(src):
        src = pattern.sub(new_block, src)
        out_path.write_text(src, encoding="utf-8")
        print("\n[OK] Wrote retuned weights -> backend/classifier/heuristics.py")
    else:
        print("\n[WARN] Auto-patch failed; manual block:\n" + new_block)


if __name__ == "__main__":
    main()
