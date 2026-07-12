"""
tests/sample_images/_generate.py — generate PHI-free synthetic sample images.

Produces 5 TABLE / 5 HANDWRITTEN / 5 PRINTED_TEXT images (PNG) plus a
``ground_truth.json`` mapping each filename to its ``doc_class`` and expected
OCR ``text``. The printed set uses clean, high-contrast lab-report text so the
OCR engine can reproduce it with very low CER (used by the jiwer < 5% check).

Run:  .venv\\Scripts\\python.exe tests\\sample_images\\_generate.py
"""
from __future__ import annotations

import json
import os
import random

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))


def _font(size: int):
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _new_white(w, h):
    return Image.new("RGB", (w, h), (255, 255, 255))


# Clean lab-report lines used for the PRINTED_TEXT + TABLE ground truth.
LAB_LINES = [
    "Alanine Aminotransferase 78 U/L",
    "Aspartate Aminotransferase 65 U/L",
    "Alkaline Phosphatase 120 U/L",
    "Albumin 3.2 g/dL",
    "Total Bilirubin 1.5 mg/dL",
    "Gamma Glutamyl Transferase 55 U/L",
    "Creatinine 0.9 mg/dL",
]


def make_printed(path, seed):
    rng = random.Random(seed)
    img = _new_white(700, 900)
    d = ImageDraw.Draw(img)
    f = _font(34)
    y = 60
    lines = LAB_LINES[: 5 + (seed % 3)]
    rendered = []
    for line in lines:
        d.text((50, y), line, fill=(0, 0, 0), font=f)
        rendered.append(line)
        y += 90
    img.save(path)
    return "\n".join(rendered)


def make_table(path, seed):
    img = _new_white(700, 900)
    d = ImageDraw.Draw(img)
    cols, rows = 3, 6
    cw, rh = (700 - 80) / cols, (900 - 80) / rows
    # grid
    for c in range(cols + 1):
        x = 40 + c * cw
        d.line([(x, 40), (x, 900 - 40)], fill=(0, 0, 0), width=2)
    for r in range(rows + 1):
        y = 40 + r * rh
        d.line([(40, y), (700 - 40, y)], fill=(0, 0, 0), width=2)
    # header + values
    header = ["Test", "Result", "Unit"]
    f = _font(26)
    rendered_rows = [header]
    for r in range(rows):
        vals = header[:] if r == 0 else [
            ["ALT", "AST", "ALP"][r % 3],
            str([78, 65, 120, 55, 40, 99][r % 6]),
            ["U/L", "U/L", "U/L", "g/dL", "mg/dL", "U/L"][r % 6],
        ]
        rendered_rows.append(vals)
        for c in range(cols):
            x = 40 + c * cw + 8
            y = 40 + r * rh + 8
            d.text((x, y), str(vals[c]), fill=(0, 0, 0), font=f)
    img.save(path)
    # ground-truth text: header row + data rows joined
    return "\n".join(" | ".join(str(v) for v in row) for row in rendered_rows)


def make_handwritten(path, seed):
    rng = random.Random(seed * 13 + 1)
    img = _new_white(700, 900)
    d = ImageDraw.Draw(img)
    # scattered freehand strokes (no long straight lines) — matches classifier
    for _ in range(60):
        x1 = rng.randint(40, 660)
        y1 = rng.randint(40, 860)
        ang = rng.uniform(0, 2 * 3.14159)
        length = rng.randint(12, 45)
        x2 = x1 + int(__import__("math").cos(ang) * length)
        y2 = y1 + int(__import__("math").sin(ang) * length)
        d.line([(x1, y1), (x2, y2)], fill=(0, 0, 0), width=2)
    img.save(path)
    # Handwritten is not CER-evaluated (no reliable ground transcription);
    # we keep a human-readable placeholder note for inventory only.
    return "handwritten clinical note (freehand strokes)"


def main():
    gt: dict = {}
    for i in range(5):
        p = os.path.join(HERE, f"printed_{i+1}.png")
        gt[os.path.basename(p)] = {"doc_class": "PRINTED_TEXT", "text": make_printed(p, i)}
    for i in range(5):
        p = os.path.join(HERE, f"table_{i+1}.png")
        gt[os.path.basename(p)] = {"doc_class": "TABLE", "text": make_table(p, i)}
    for i in range(5):
        p = os.path.join(HERE, f"handwritten_{i+1}.png")
        gt[os.path.basename(p)] = {"doc_class": "HANDWRITTEN", "text": make_handwritten(p, i)}

    with open(os.path.join(HERE, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump(gt, f, indent=2, ensure_ascii=False)
    print(f"Generated {len(gt)} sample images + ground_truth.json in {HERE}")


if __name__ == "__main__":
    main()
