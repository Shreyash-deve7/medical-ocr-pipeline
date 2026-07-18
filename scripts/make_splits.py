"""scripts/make_splits.py — Create a stratified train/val/test split of labels.json.

Produces backend/dataset_splits.json with the structure::

    {
      "meta": {"seed": 42, "train": 0.7, "val": 0.15, "test": 0.15,
                "created": "...", "n_total": ...},
      "splits": {
        "train": ["rel/path", ...],
        "val":   ["rel/path", ...],
        "test":  ["rel/path", ...]
      },
      "class_counts": {
        "train": {"TABLE": n, ...},
        "val":   {...},
        "test":  {...}
      }
    }

The ``test`` split is held out and MUST NOT be used for any tuning
(weights, heuristic thresholds, fusion coefficients, etc.).

Usage:
    python scripts/make_splits.py --labels backend/labels.json \
           --out backend/dataset_splits.json --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CLASSES = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")

# Minimum per-class allocation for the (small) test/val folds so no class is
# accidentally empty in any split.
MIN_PER_SPLIT = 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Stratified dataset splitter")
    parser.add_argument("--labels", default="backend/labels.json")
    parser.add_argument("--out", default="backend/dataset_splits.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train", type=float, default=0.70)
    parser.add_argument("--val", type=float, default=0.15)
    parser.add_argument("--test", type=float, default=0.15)
    args = parser.parse_args()

    if abs(args.train + args.val + args.test - 1.0) > 1e-6:
        raise SystemExit("train+val+test must sum to 1.0")

    project_root = Path(__file__).resolve().parent.parent
    labels_path = project_root / args.labels
    with open(labels_path, encoding="utf-8") as f:
        labels = json.load(f)

    random.seed(args.seed)

    # Group by true class.
    by_class = defaultdict(list)
    for rel_path, meta in labels.items():
        true_cls = meta.get("true_class")
        if true_cls not in CLASSES:
            continue
        by_class[true_cls].append(rel_path)

    train, val, test = [], [], []
    counts: dict[str, dict[str, int]] = {
        "train": {c: 0 for c in CLASSES},
        "val": {c: 0 for c in CLASSES},
        "test": {c: 0 for c in CLASSES},
    }

    for cls, members in by_class.items():
        random.shuffle(members)
        n = len(members)
        # Guarantee at least MIN_PER_SPLIT of this class in val and test.
        n_test = max(MIN_PER_SPLIT, int(round(n * args.test)))
        n_val = max(MIN_PER_SPLIT, int(round(n * args.val)))
        n_test = min(n_test, n - 2 * MIN_PER_SPLIT)
        n_val = min(n_val, n - n_test - MIN_PER_SPLIT)
        n_train = n - n_val - n_test

        test += members[:n_test]
        val += members[n_test:n_test + n_val]
        train += members[n_test + n_val:]

        counts["train"][cls] = n_train
        counts["val"][cls] = n_val
        counts["test"][cls] = n_test

    random.shuffle(train)
    random.shuffle(val)
    random.shuffle(test)

    out = {
        "meta": {
            "seed": args.seed,
            "train": args.train,
            "val": args.val,
            "test": args.test,
            "created": datetime.now(timezone.utc).isoformat(),
            "n_total": len(train) + len(val) + len(test),
            "label_source": str(labels_path.relative_to(project_root)),
        },
        "splits": {"train": train, "val": val, "test": test},
        "class_counts": counts,
    }

    out_path = project_root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Wrote {out_path}")
    print(f"  total={out['meta']['n_total']} "
          f"train={len(train)} val={len(val)} test={len(test)}")
    for split in ("train", "val", "test"):
        cc = counts[split]
        print(f"  {split:5s}: " + " ".join(f"{c}={cc[c]}" for c in CLASSES))


if __name__ == "__main__":
    main()
