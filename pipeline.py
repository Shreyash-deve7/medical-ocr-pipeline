#!/usr/bin/env python
"""
pipeline.py — Unified CLI entry point for the OCR pipeline.

Supports single-image and batch processing modes with full timing metrics.

Usage:
    # Single image
    python pipeline.py --input path/to/image.png --output result.json

    # Batch mode
    python pipeline.py --input-dir ./images --output-dir ./results

    # With optional stages
    python pipeline.py --input img.png --output result.json --with-summary --with-evaluation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the backend package is importable (script lives at repo root)
_root = Path(__file__).parent
sys.path.insert(0, str(_root))          # repo root  → import `backend.xxx`
sys.path.insert(0, str(_root / "backend"))  # backend/  → import `agents.xxx`, `services.xxx`, etc.

from backend.pipeline import run_pipeline, run_pipeline_batch


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline.py",
        description="Unified OCR pipeline CLI — preprocess → classify → OCR → extract → validate → diagnose",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --input photo.png --output result.json
  python pipeline.py --input-dir ./scans --output-dir ./output
  python pipeline.py --input img.png --output out.json --with-summary --with-evaluation
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", metavar="PATH", help="Path to a single input image")
    group.add_argument("--input-dir", metavar="DIR", help="Directory of images for batch processing")

    out_group = parser.add_mutually_exclusive_group(required=True)
    out_group.add_argument("--output", metavar="FILE", help="Path to output JSON file (single-image mode)")
    out_group.add_argument("--output-dir", metavar="DIR", help="Output directory for batch results")

    parser.add_argument(
        "--with-summary",
        action="store_true",
        help="Include the doctor-facing summary stage",
    )
    parser.add_argument(
        "--with-evaluation",
        action="store_true",
        help="Include the evaluation stage (uses sample_images ground truth)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: True)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Disable pretty-printing (no indentation, no newlines)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    pretty = not args.compact
    indent = 2 if pretty else None

    # ── Single-image mode ────────────────────────────────────────────────────
    if args.input:
        image_path = Path(args.input)
        if not image_path.exists():
            print(f"ERROR: Input file not found: {image_path}", file=sys.stderr)
            sys.exit(1)

        result = run_pipeline(
            str(image_path),
            include_summary=args.with_summary,
            include_evaluation=args.with_evaluation,
        )
        result_dict = result.to_dict()

        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(result_dict, indent=indent, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"Result written to {out_path}")
        else:
            print(json.dumps(result_dict, indent=indent, ensure_ascii=False))

        # Print timing summary
        timing = result_dict.get("timing", {})
        if timing:
            print("\nTiming (ms):")
            for stage, ms in timing.items():
                print(f"  {stage:>12}: {ms:>6} ms")
        if result_dict.get("errors"):
            print("\nErrors encountered:")
            for stage, err in result_dict["errors"].items():
                print(f"  {stage}: {err}")
        sys.exit(0)

    # ── Batch mode ───────────────────────────────────────────────────────────
    if args.input_dir:
        input_path = Path(args.input_dir)
        output_path = Path(args.output_dir) if args.output_dir else Path("./pipeline_output")
        output_path.mkdir(parents=True, exist_ok=True)

        results = run_pipeline_batch(
            str(input_path),
            str(output_path),
            include_summary=args.with_summary,
            include_evaluation=args.with_evaluation,
        )

        succeeded = sum(1 for r in results if "error" not in r)
        failed = sum(1 for r in results if "error" in r)
        print(f"\nBatch complete: {succeeded} succeeded, {failed} failed → {output_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()