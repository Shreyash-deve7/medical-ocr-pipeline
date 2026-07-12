"""scripts/diagnose_features.py — Dump feature vectors + scores for all labeled images.

Helps tune the heuristic weights by showing which features drive misclassifications.
Usage: python scripts/diagnose_features.py --labels backend/labels.json
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import cv2
import numpy as np

CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--labels", type=str, default="backend/labels.json")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root / "backend"))
    from document_classifier import DocumentClassifier, CLASSES_3

    with open(project_root / args.labels) as f:
        labels = json.load(f)

    cls = DocumentClassifier()  # heuristic-only (no weights)

    # Collect features per true class.
    by_class = defaultdict(list)
    misclassified = []

    for rel_path, meta in sorted(labels.items()):
        img_path = project_root / rel_path
        if not img_path.exists():
            continue
        image = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        true_cls = meta["true_class"]
        fv = cls._extract_features(image)
        scores = cls._score_features(fv)
        pred = max(scores, key=scores.get)
        by_class[true_cls].append((rel_path, fv, scores, pred))
        if pred != true_cls:
            misclassified.append((rel_path, true_cls, pred, fv, scores))

    # Print per-class feature averages.
    print("=" * 100)
    print("PER-CLASS FEATURE AVERAGES")
    print("=" * 100)
    feature_names = [f for f in vars(fv).keys()]
    header = f"{'Feature':<28}" + "".join(f"{c:>16}" for c in CLASSES)
    print(header)
    print("-" * 100)
    for fname in feature_names:
        row = f"{fname:<28}"
        for c in CLASSES:
            vals = [t[1].__dict__[fname] for t in by_class[c]]
            avg = np.mean(vals) if vals else 0.0
            row += f"{avg:>16.4f}"
        print(row)

    # Print score averages.
    print("\n" + "=" * 100)
    print("PER-CLASS SCORE AVERAGES")
    print("=" * 100)
    header = f"{'True Class':<28}" + "".join(f"{c:>16}" for c in CLASSES_3)
    print(header)
    print("-" * 100)
    for true_cls in CLASSES:
        row = f"{true_cls:<28}"
        for score_cls in CLASSES_3:
            vals = [t[2][score_cls] for t in by_class[true_cls]]
            avg = np.mean(vals) if vals else 0.0
            row += f"{avg:>16.4f}"
        print(row)

    # Print misclassified details.
    print("\n" + "=" * 100)
    print(f"MISCLASSIFIED ({len(misclassified)} images)")
    print("=" * 100)
    for rel_path, true_cls, pred, fv, scores in misclassified:
        print(f"\n{Path(rel_path).name}")
        print(f"  True: {true_cls}  Pred: {pred}")
        print(f"  Scores: " + "  ".join(f"{c}={scores[c]:.3f}" for c in CLASSES_3))
        print(f"  ink={fv.ink_coverage:.3f} grid={fv.grid_score:.3f} "
              f"n_h={fv.n_horizontal:.3f} n_v={fv.n_vertical:.3f} "
              f"ld={fv.line_density:.3f}")
        print(f"  sw_cv={fv.stroke_width_cv:.3f} cc_asp_std={fv.cc_aspect_std:.3f} "
              f"cc_area_cv={fv.cc_area_cv:.3f}")
        print(f"  proj_per={fv.projection_periodicity:.3f} "
              f"proj_sharp={fv.projection_peak_sharpness:.3f} "
              f"orient_conc={fv.orientation_concentration:.3f} "
              f"orient_ent={fv.orientation_entropy:.3f}")


if __name__ == "__main__":
    main()
