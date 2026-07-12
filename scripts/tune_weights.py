"""scripts/tune_weights.py — Optimize heuristic scoring weights via grid search.

Loads all labeled images, extracts feature vectors, then searches for the
weight/bias combination that maximizes accuracy on the dataset.

Usage: python scripts/tune_weights.py --labels backend/labels.json
"""
from __future__ import annotations
import argparse
import json
import sys
import itertools
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
    from document_classifier import DocumentClassifier, FeatureVector, CLASSES_3

    with open(project_root / args.labels) as f:
        labels = json.load(f)

    cls = DocumentClassifier()

    # Extract features for all images.
    features = []  # (feature_dict, true_class_idx)
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

    # Features to use in the linear model.
    feature_names = [
        "n_horizontal", "n_vertical", "line_density",
        "stroke_width_cv", "cc_aspect_std", "cc_area_cv",
        "run_length_cv", "grid_score",
        "projection_periodicity", "projection_peak_sharpness",
        "orientation_concentration", "orientation_entropy",
        "ink_coverage",
    ]

    # Build feature matrix X (N x F) and label vector y (N).
    X = np.array([[f[name] for name in feature_names] for f, _ in features])
    y = np.array([label for _, label in features])

    # One-vs-rest logistic regression via gradient descent (simple, no sklearn).
    # We learn a weight vector w (F,) and bias b (scalar) for each class.
    # Score(class) = w_class . x + b_class. Predict argmax.
    n_classes = 3
    n_features = len(feature_names)
    n_samples = len(features)

    # Normalize features.
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-6
    X_norm = (X - X_mean) / X_std

    # Train one-vs-rest logistic regression for each class.
    W = np.zeros((n_classes, n_features))
    B = np.zeros(n_classes)
    lr = 0.1
    epochs = 2000

    for c in range(n_classes):
        y_c = (y == c).astype(np.float64)
        w = np.zeros(n_features)
        b = 0.0
        for epoch in range(epochs):
            z = X_norm @ w + b
            p = 1 / (1 + np.exp(-z))
            grad_w = X_norm.T @ (p - y_c) / n_samples
            grad_b = np.mean(p - y_c)
            w -= lr * grad_w
            b -= lr * grad_b
        W[c] = w
        B[c] = b

    # Evaluate.
    scores = X_norm @ W.T + B  # (N, 3)
    preds = np.argmax(scores, axis=1)
    acc = np.mean(preds == y)
    print(f"\nOptimized accuracy: {acc:.3f} ({int(acc * n_samples)}/{n_samples})")

    # Confusion matrix.
    cm = np.zeros((3, 3), dtype=int)
    for true, pred in zip(y, preds):
        cm[true][pred] += 1
    print("\nConfusion Matrix (rows=true, cols=predicted):")
    header = " " * 12 + " ".join(f"{c:>12}" for c in CLASSES)
    print(header)
    for i, true_cls in enumerate(CLASSES):
        row = f"{true_cls:>12} " + " ".join(f"{cm[i][j]:>12}" for j in range(3))
        print(row)

    # Per-class recall.
    for i, cls_name in enumerate(CLASSES):
        recall = cm[i][i] / cm[i].sum() if cm[i].sum() > 0 else 0
        print(f"  {cls_name} recall: {recall:.3f} ({cm[i][i]}/{cm[i].sum()})")

    # Print the learned weights (in original feature scale).
    print("\n" + "=" * 80)
    print("LEARNED WEIGHTS (normalized scale, per class):")
    print("=" * 80)
    header = f"{'Feature':<28}" + "".join(f"{c:>16}" for c in CLASSES)
    print(header)
    print("-" * 80)
    for j, fname in enumerate(feature_names):
        row = f"{fname:<28}" + "".join(f"{W[c][j]:>16.4f}" for c in range(3))
        print(row)
    bias_row = "".join(f"{B[c]:>16.4f}" for c in range(3))
    print(f"{'BIAS':<28}" + bias_row)

    # Convert to original scale for the heuristic scorer.
    # Score = W . X_norm + B = W . ((X - mean) / std) + B
    #       = (W / std) . X + (B - W . (mean / std))
    print("\n" + "=" * 80)
    print("CONVERTED WEIGHTS (original feature scale, for _CLASS_WEIGHTS):")
    print("=" * 80)
    W_orig = W / X_std  # scale weights
    B_orig = B - W @ (X_mean / X_std)  # adjust bias
    header = f"{'Feature':<28}" + "".join(f"{c:>16}" for c in CLASSES)
    print(header)
    print("-" * 80)
    for j, fname in enumerate(feature_names):
        row = f"{fname:<28}" + "".join(f"{W_orig[c][j]:>16.4f}" for c in range(3))
        print(row)
    bias_row2 = "".join(f"{B_orig[c]:>16.4f}" for c in range(3))
    print(f"{'BIAS':<28}" + bias_row2)

    # Print normalization parameters and weights in copy-pasteable Python format.
    print("\n" + "=" * 80)
    print("COPY-PASTE FOR document_classifier.py _score_features:")
    print("=" * 80)
    print("        _FEATURE_MEAN = np.array([")
    print("            " + ", ".join(f"{v:.4f}" for v in X_mean) + ",")
    print("        ])")
    print("        _FEATURE_STD = np.array([")
    print("            " + ", ".join(f"{v:.4f}" for v in X_std) + ",")
    print("        ])")
    print("        _W = np.array([")
    for c in range(3):
        print("            [" + ", ".join(f"{W[c][j]:.4f}" for j in range(n_features)) + "],")
    print("        ])")
    print("        _B = np.array([" + ", ".join(f"{B[c]:.4f}" for c in range(3)) + "])")


if __name__ == "__main__":
    main()
