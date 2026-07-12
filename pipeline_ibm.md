# Medical OCR Pipeline — End-to-End Architecture

> **Intern Guide** | Domain: Hepatology Lab Reports | Focus: Image Preprocessing → Document Type Detection → OCR Routing → Structured JSON Extraction

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Stage 1 — Image Preprocessing](#3-stage-1--image-preprocessing)
4. [Stage 2 — Document Type Classification](#4-stage-2--document-type-classification)
5. [Stage 3 — OCR Routing Engine](#5-stage-3--ocr-routing-engine)
6. [Stage 4 — Structured JSON Extraction](#6-stage-4--structured-json-extraction)
7. [Hepatology Reference Terminology](#7-hepatology-reference-terminology)
8. [Project Structure](#8-project-structure)
9. [Setup & Installation](#9-setup--installation)
10. [Running the Pipeline](#10-running-the-pipeline)
11. [Testing Guidelines](#11-testing-guidelines)
12. [Evaluation Metrics](#12-evaluation-metrics)
13. [Contribution Guidelines](#13-contribution-guidelines)
14. [Resources & References](#14-resources--references)

---

## 1. Project Overview

This repository implements a fully automated, end-to-end pipeline that takes a raw medical document image as input and produces a structured, validated JSON object as output. The pipeline is purpose-built for **Hepatology** (liver disease department) lab reports but is extensible to other medical specialties.

### Problem Statement

Medical lab reports arrive in many physical forms:
- Printed tables from laboratory information systems (LIS)
- Handwritten notes added by clinicians
- Scanned pages that are skewed, noisy, or low-contrast

A single unified pipeline must handle all these variations and output clean, machine-readable data that can be consumed by downstream diagnosis and clinical decision support systems.

### Scope for this Repo

| Input | Output |
|---|---|
| Raw image (JPEG / PNG / TIFF / PDF page) | Validated JSON with test name, value, unit, reference range, flag |
| Any orientation, lighting condition, scan quality | Normalised, preprocessed image record |
| Table / Handwritten / Printed text | OCR engine chosen automatically per document type |

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        INPUT IMAGE                               │
│           (JPEG / PNG / TIFF / Scanned PDF page)                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 1 — IMAGE PREPROCESSING                                   │
│  • Orientation correction (deskew / rotate)                      │
│  • Noise removal (Gaussian, median, bilateral filter)            │
│  • Contrast enhancement (CLAHE)                                  │
│  • Binarisation (Otsu / adaptive threshold)                      │
│  • Size normalisation                                            │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 2 — DOCUMENT TYPE CLASSIFIER                              │
│  Classifies image into one of three categories:                  │
│  ┌────────────┐  ┌─────────────────┐  ┌────────────────────┐    │
│  │   TABLE    │  │  HANDWRITTEN    │  │  PRINTED TEXT      │    │
│  └────────────┘  └─────────────────┘  └────────────────────┘    │
└──────┬─────────────────────┬─────────────────────┬──────────────┘
       │                     │                     │
       ▼                     ▼                     ▼
┌────────────┐      ┌─────────────────┐   ┌────────────────────┐
│  OCR 1     │      │    OCR 2        │   │      OCR 3         │
│  (Tables)  │      │ (Handwriting)   │   │  (Printed Text)    │
│ PaddleOCR  │      │  TrOCR /        │   │  Tesseract /       │
│ /Surya     │      │  SuryaOCR       │   │  EasyOCR /         │
│ /Docling   │      │                 │   │  olmOCR            │
└─────┬──────┘      └────────┬────────┘   └────────┬───────────┘
      └─────────────────────┬┘                    ─┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  STAGE 4 — STRUCTURED JSON EXTRACTION + FORMATTING MODEL         │
│  • Parse raw OCR text → fields                                   │
│  • Normalise units (g/dL, U/L, mg/dL, etc.)                     │
│  • Map to Hepatology reference ranges                            │
│  • Flag abnormal values (HIGH / LOW / CRITICAL)                  │
│  • Validate with Pydantic schema                                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
                   VALIDATED JSON OUTPUT
```

---

## 3. Stage 1 — Image Preprocessing

**Source repo:** [`intern-ocr-imagepreprocessing-ishika`](https://github.com/ibm-techlab-summer-internship/intern-ocr-imagepreprocessing-ishika)
**Owner:** Ishika (preprocessing intern)

> The pipeline imports preprocessing functions **directly** from the above repo as a Git submodule.
> Do **not** re-implement preprocessing here — consume the published functions only.

### 3.1 How to Pull the Preprocessing Code

Add it as a submodule once when setting up this repo:

```bash
git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-imagepreprocessing-ishika.git \
  extern/preprocessing

git submodule update --init --recursive
```

Your local tree will then have:

```
extern/
└── preprocessing/          ← Ishika's full repo cloned here
    ├── preprocessing/
    │   ├── pipeline.py     ← preprocess() lives here
    │   ├── orientation.py
    │   ├── noise.py
    │   ├── contrast.py
    │   ├── binarise.py
    │   └── resize.py
    └── requirements.txt
```

### 3.2 How to Import in This Pipeline

```python
# At the top of pipeline.py — add extern/ to sys.path once
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "extern" / "preprocessing"))

# Now import directly from Ishika's module
from preprocessing.pipeline import preprocess
from preprocessing.orientation import correct_orientation
from preprocessing.noise import denoise
from preprocessing.contrast import enhance_contrast
from preprocessing.binarise import binarise
from preprocessing.resize import resize_to_ocr_standard

# Usage
result = preprocess("sample_images/lft_report.jpg")
preprocessed_image = result["preprocessed_image"]
```

### 3.3 Contract — What This Pipeline Expects from That Repo

The preprocessing repo **must** export the following function signatures. If Ishika changes a signature, update the import here too and open a PR.

```python
def preprocess(image_path: str) -> dict:
    """
    Master function — runs full pipeline.
    Returns:
        {
          "preprocessed_image": np.ndarray,   # ← used by classifier + OCR stages
          "transformations_applied": [...],
          "quality_metrics_before": {...},
          "quality_metrics_after":  {...}
        }
    """
```

### 3.4 Why Preprocessing is Mandatory

Raw scanned images frequently suffer from:

| Issue | Effect on OCR | Fix applied by Ishika's repo |
|---|---|---|
| Skew / rotation | Characters misaligned, lines merged | Deskew + rotate |
| Low contrast | Text blends into background | CLAHE |
| Salt-and-pepper noise | Characters broken | Median filter |
| Shadows / uneven lighting | Partial text loss | Adaptive binarisation |
| Wrong resolution | Detail lost or processing too slow | Resize to 300 DPI equivalent |

### 3.5 Quality Metrics Passed Through

```json
{
  "sharpness_laplacian_var": 142.3,
  "contrast_rms": 0.61,
  "snr_db": 28.4,
  "skew_angle_degrees": -2.1,
  "resolution_dpi": 300,
  "binarisation_method": "otsu"
}
```

---

## 4. Stage 2 — Document Type Classification

### 4.1 Three Target Classes

| Class ID | Label | Description | OCR Route |
|---|---|---|---|
| 0 | `TABLE` | Printed lab report grid with rows/columns, borders, or aligned whitespace | OCR 1 |
| 1 | `HANDWRITTEN` | Cursive, freehand, or mixed print-handwrite text | OCR 2 |
| 2 | `PRINTED_TEXT` | Computerised typed text, paragraphs, letterhead, radiology narrative | OCR 3 |

### 4.2 Classifier Approach

**Option A — Rule-Based Heuristic (recommended first pass)**

```python
# classifier/heuristic_classifier.py

def classify_document(preprocessed_image: np.ndarray) -> str:
    """
    Returns one of: 'TABLE', 'HANDWRITTEN', 'PRINTED_TEXT'

    Decision logic:
    1. Detect horizontal and vertical lines using HoughLinesP.
       If line density > threshold AND grid pattern found → TABLE.
    2. Compute stroke width variation and connected-component
       aspect-ratio distribution.
       If high stroke width variance → HANDWRITTEN.
    3. Else → PRINTED_TEXT.
    """
```

**Option B — Lightweight CNN Classifier (optional enhancement)**

Train a MobileNetV3-Small on a labelled dataset of:
- Printed lab tables (positive for TABLE)
- Handwritten prescriptions / doctor notes (positive for HANDWRITTEN)
- Typed radiology / discharge summaries (positive for PRINTED_TEXT)

Use transfer learning; dataset size of 300–500 images per class is sufficient.

### 4.3 Confidence Thresholding

```python
{
  "predicted_class": "TABLE",
  "confidence": 0.91,
  "fallback_class": "PRINTED_TEXT",
  "fallback_triggered": false
}
```

If `confidence < 0.70`, run both the predicted OCR engine and the fallback engine, then pick the result with higher field completeness.

---

## 5. Stage 3 — OCR Routing Engine

Each OCR engine lives in its own intern repo. This pipeline adds them as Git submodules and imports their extraction functions directly — **no copy-paste of OCR code into this repo**.

### 5.0 Submodule Setup — All OCR Repos

Run once after cloning this repo:

```bash
# OCR 1 — Tables
git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-paddleocr-aditya.git \
  extern/ocr_table_paddle

git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman.git \
  extern/ocr_table_surya

git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-granite-docling.git \
  extern/ocr_table_docling

# OCR 2 — Handwriting
git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-trocr-aditi.git \
  extern/ocr_handwritten_trocr

git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman.git \
  extern/ocr_handwritten_surya   # Surya handles both table layout + handwriting

# OCR 3 — Printed text
git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-tesseract-sarika.git \
  extern/ocr_printed_tesseract

git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-easyocr-ankit.git \
  extern/ocr_printed_easyocr

git submodule add \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-olmocr-devansh.git \
  extern/ocr_printed_olmocr

git submodule update --init --recursive
```

Add all `extern/` submodule paths to `sys.path` in one helper:

```python
# ocr/submodule_paths.py
import sys
from pathlib import Path

EXTERN = Path(__file__).parent.parent / "extern"

SUBMODULE_PATHS = [
    EXTERN / "ocr_table_paddle",
    EXTERN / "ocr_table_surya",
    EXTERN / "ocr_table_docling",
    EXTERN / "ocr_handwritten_trocr",
    EXTERN / "ocr_handwritten_surya",
    EXTERN / "ocr_printed_tesseract",
    EXTERN / "ocr_printed_easyocr",
    EXTERN / "ocr_printed_olmocr",
    EXTERN / "preprocessing",
]

for p in SUBMODULE_PATHS:
    sys.path.insert(0, str(p))
```

---

### 5.1 OCR 1 — Table Extraction

**Use when:** Document class is `TABLE`

**Source repos (priority order):**

| Priority | Intern Repo | Owner | Strength |
|---|---|---|---|
| 1st | [`intern-ocr-paddleocr-aditya`](https://github.com/ibm-techlab-summer-internship/intern-ocr-paddleocr-aditya) | Aditya | PP-Structure table recovery, free |
| 2nd | [`intern-ocr-suryaocr-anshuman`](https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman) | Anshuman | Multi-column layout + table parsing |
| 3rd | [`intern-ocr-granite-docling`](https://github.com/ibm-techlab-summer-internship/intern-ocr-granite-docling) | Task pool | Best for LIS-generated PDFs |

**How to import and call:**

```python
# ocr/ocr1_table.py
from ocr_submodule_paths import *   # ensures extern/ is on sys.path

# Primary: PaddleOCR PP-Structure (Aditya's repo)
from paddleocr_table.extractor import extract_table as paddle_extract_table

# Fallback: SuryaOCR (Anshuman's repo)
from suryaocr.extractor import extract_table as surya_extract_table

def extract_table(image: np.ndarray) -> list[list[str]]:
    """
    Try PaddleOCR first; fall back to Surya if confidence < 0.75.
    Returns a 2-D list — row 0 is the header row.
    Example:
    [
      ["Test Name", "Result", "Unit", "Reference Range", "Flag"],
      ["ALT (SGPT)",  "78",   "U/L",  "7–56",           "HIGH"],
      ...
    ]
    """
    try:
        result = paddle_extract_table(image)
        if result["confidence"] >= 0.75:
            return result["table"]
    except Exception:
        pass
    return surya_extract_table(image)["table"]
```

**Contract — what Aditya's and Anshuman's repos must export:**

```python
# Expected function in each OCR repo's extractor module
def extract_table(image: np.ndarray) -> dict:
    """
    Returns:
    {
      "table": list[list[str]],   # 2-D grid, row 0 = headers
      "confidence": float,        # 0.0 – 1.0
      "engine": str               # e.g. "PaddleOCR-PP-Structure"
    }
    """
```

---

### 5.2 OCR 2 — Handwritten Text Recognition

**Use when:** Document class is `HANDWRITTEN`

**Source repos (priority order):**

| Priority | Intern Repo | Owner | Strength |
|---|---|---|---|
| 1st | [`intern-ocr-trocr-aditi`](https://github.com/ibm-techlab-summer-internship/intern-ocr-trocr-aditi) | Aditi | SOTA handwriting (TrOCR-large), GPU |
| 2nd | [`intern-ocr-suryaocr-anshuman`](https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman) | Anshuman | Multi-script, CPU-friendly fallback |

**How to import and call:**

```python
# ocr/ocr2_handwritten.py
from ocr_submodule_paths import *

# Primary: TrOCR (Aditi's repo)
from trocr.extractor import extract_handwritten as trocr_extract

# Fallback: SuryaOCR (Anshuman's repo)
from suryaocr.extractor import extract_handwritten as surya_extract_hw

def extract_handwritten(image: np.ndarray) -> str:
    """
    Returns raw transcribed string.
    Tries TrOCR first; falls back to SuryaOCR if GPU unavailable.
    """
    try:
        return trocr_extract(image)["text"]
    except RuntimeError:  # GPU not available
        return surya_extract_hw(image)["text"]
```

**Contract — what Aditi's repo must export:**

```python
def extract_handwritten(image: np.ndarray) -> dict:
    """
    Returns:
    {
      "text": str,          # full transcribed text, newlines preserved
      "confidence": float,
      "engine": str         # e.g. "TrOCR-large-handwritten"
    }
    """
```

---

### 5.3 OCR 3 — Printed Text Extraction

**Use when:** Document class is `PRINTED_TEXT`

**Source repos (priority order):**

| Priority | Intern Repo | Owner | Strength |
|---|---|---|---|
| 1st | [`intern-ocr-olmocr-devansh`](https://github.com/ibm-techlab-summer-internship/intern-ocr-olmocr-devansh) | Devansh | Highest accuracy (2-7B LLM-based), GPU |
| 2nd | [`intern-ocr-easyocr-ankit`](https://github.com/ibm-techlab-summer-internship/intern-ocr-easyocr-ankit) | Ankit | Multi-language, CPU-friendly |
| 3rd | [`intern-ocr-tesseract-sarika`](https://github.com/ibm-techlab-summer-internship/intern-ocr-tesseract-sarika) | Sarika | Fast, no GPU, reliable baseline |

**How to import and call:**

```python
# ocr/ocr3_printed.py
from ocr_submodule_paths import *

# Primary: olmOCR (Devansh's repo)
from olmocr.extractor import extract_text as olmocr_extract

# Secondary: EasyOCR (Ankit's repo)
from easyocr_wrapper.extractor import extract_text as easyocr_extract

# Fallback: Tesseract (Sarika's repo)
from tesseract_wrapper.extractor import extract_text as tesseract_extract

def extract_printed_text(image: np.ndarray) -> str:
    """
    Returns raw text with newlines preserved.
    Priority: olmOCR (GPU) → EasyOCR → Tesseract.
    """
    for fn in [olmocr_extract, easyocr_extract, tesseract_extract]:
        try:
            result = fn(image)
            if result.get("text", "").strip():
                return result["text"]
        except Exception:
            continue
    return ""
```

**Contract — what each printed-text OCR repo must export:**

```python
def extract_text(image: np.ndarray) -> dict:
    """
    Returns:
    {
      "text": str,          # full extracted text, newlines preserved
      "confidence": float,
      "engine": str         # e.g. "olmOCR-2-7B", "EasyOCR", "Tesseract-5"
    }
    """
```

---

### 5.4 Unified OCR Router

```python
# ocr/router.py
import time
from ocr.ocr1_table       import extract_table
from ocr.ocr2_handwritten import extract_handwritten
from ocr.ocr3_printed     import extract_printed_text

def run_ocr(preprocessed_image: np.ndarray, doc_class: str) -> dict:
    """
    Routes image to the correct OCR engine based on doc_class.
    Returns:
    {
      "doc_class": "TABLE",
      "ocr_engine_used": "PaddleOCR-PP-Structure",
      "raw_output": <str or list[list[str]]>,
      "processing_time_seconds": 1.24
    }
    """
    t0 = time.time()
    dispatch = {
        "TABLE":        extract_table,
        "HANDWRITTEN":  extract_handwritten,
        "PRINTED_TEXT": extract_printed_text,
    }
    raw = dispatch[doc_class](preprocessed_image)
    return {
        "doc_class": doc_class,
        "raw_output": raw,
        "processing_time_seconds": round(time.time() - t0, 2),
    }
```

---

## 6. Stage 4 — Structured JSON Extraction

### 6.1 Objective

Convert the raw OCR output (plain text or 2-D table array) into a validated, structured JSON object following a fixed schema for Hepatology lab reports.

### 6.2 Target JSON Schema

```json
{
  "document_metadata": {
    "patient_id": "string | null",
    "patient_name": "string | null",
    "date_of_collection": "YYYY-MM-DD | null",
    "date_of_report": "YYYY-MM-DD | null",
    "lab_name": "string | null",
    "referring_doctor": "string | null",
    "department": "Hepatology"
  },
  "lab_results": [
    {
      "test_name": "ALT (SGPT)",
      "test_abbreviation": "ALT",
      "value": 78.0,
      "unit": "U/L",
      "reference_range": {
        "low": 7.0,
        "high": 56.0,
        "unit": "U/L"
      },
      "flag": "HIGH",
      "clinical_significance": "Elevated ALT suggests hepatocellular injury"
    }
  ],
  "pipeline_metadata": {
    "preprocessing_transformations": ["deskew", "clahe", "otsu_binarise"],
    "doc_class": "TABLE",
    "ocr_engine": "PaddleOCR-PP-Structure",
    "extraction_confidence": 0.94,
    "schema_version": "1.0"
  }
}
```

### 6.3 Extraction Approach — LLM Formatting Prompt

After raw OCR text is obtained, pass it through an LLM (Granite 3.3 or equivalent) with the following system prompt template to convert unstructured text to JSON:

```
SYSTEM PROMPT:
You are a medical data extraction assistant specialised in Hepatology lab reports.

Given the raw OCR text below, extract all laboratory test results and return ONLY
a valid JSON object conforming exactly to this schema:

{
  "lab_results": [
    {
      "test_name": <full test name as appears in report>,
      "test_abbreviation": <abbreviation if present, else null>,
      "value": <numeric value as float>,
      "unit": <unit string — normalise to SI units where possible>,
      "reference_range": { "low": <float|null>, "high": <float|null>, "unit": <string> },
      "flag": <"HIGH" | "LOW" | "CRITICAL_HIGH" | "CRITICAL_LOW" | "NORMAL" | "UNKNOWN">,
      "clinical_significance": <one-sentence clinical note relevant to liver/hepatology>
    }
  ]
}

Rules:
- For units: use U/L for enzymes, g/dL for haemoglobin/albumin, mg/dL for bilirubin/creatinine,
  μmol/L for ammonia, seconds(s) for PT/INR ratio is unitless.
- If a value is not present in the text, use null.
- Do NOT invent values. Extract only what is present.
- Flags: mark CRITICAL_HIGH if value > 3× upper reference limit.

RAW OCR TEXT:
{ocr_raw_text}
```

### 6.4 Schema Validation

Use **Pydantic v2** to validate every extracted JSON:

```python
# extraction/schema.py

from pydantic import BaseModel, validator
from typing import Optional, Literal

class ReferenceRange(BaseModel):
    low: Optional[float]
    high: Optional[float]
    unit: str

class LabResult(BaseModel):
    test_name: str
    test_abbreviation: Optional[str]
    value: Optional[float]
    unit: str
    reference_range: ReferenceRange
    flag: Literal["HIGH", "LOW", "CRITICAL_HIGH", "CRITICAL_LOW", "NORMAL", "UNKNOWN"]
    clinical_significance: Optional[str]

class LabReport(BaseModel):
    document_metadata: dict
    lab_results: list[LabResult]
    pipeline_metadata: dict
```

---

## 7. Hepatology Reference Terminology

All reference ranges below are drawn from **Sherlock's Diseases of the Liver and Biliary System (13th Edition)** and **AASLD (American Association for the Study of Liver Diseases) Practice Guidelines**.

### 7.1 Liver Function Tests (LFTs) — Standard Reference Ranges

| Test | Abbreviation | Normal Range | Unit | Clinical Relevance |
|---|---|---|---|---|
| Alanine Aminotransferase | ALT / SGPT | 7 – 56 | U/L | Hepatocellular injury marker |
| Aspartate Aminotransferase | AST / SGOT | 10 – 40 | U/L | Liver + muscle damage |
| Alkaline Phosphatase | ALP | 44 – 147 | U/L | Cholestasis, bone disease |
| Gamma-Glutamyl Transferase | GGT | M: 8–61, F: 5–36 | U/L | Alcohol use, cholestasis |
| Total Bilirubin | T.Bil | 0.2 – 1.2 | mg/dL | Haemolysis, hepatocellular |
| Direct (Conjugated) Bilirubin | D.Bil | 0.0 – 0.3 | mg/dL | Obstructive jaundice |
| Indirect (Unconjugated) Bilirubin | I.Bil | 0.2 – 0.9 | mg/dL | Haemolysis, Gilbert's |
| Total Protein | TP | 6.3 – 8.2 | g/dL | Synthetic function |
| Albumin | Alb | 3.5 – 5.0 | g/dL | Chronic liver disease severity |
| Globulin | Glob | 2.0 – 3.5 | g/dL | Autoimmune hepatitis |
| A/G Ratio | A/G | 1.2 – 2.2 | — | Protein metabolism |
| Prothrombin Time | PT | 11 – 13.5 | seconds | Synthetic function |
| INR | INR | 0.8 – 1.2 | — | Coagulation / MELD score |

### 7.2 Additional Hepatology Tests

| Test | Abbreviation | Normal Range | Unit | Notes |
|---|---|---|---|---|
| Serum Ammonia | NH3 | 15 – 45 | μmol/L | Hepatic encephalopathy |
| Alpha-Fetoprotein | AFP | < 10 | ng/mL | HCC screening |
| HBsAg | HBsAg | Non-reactive | — | Hepatitis B surface antigen |
| Anti-HCV | Anti-HCV | Non-reactive | — | Hepatitis C antibody |
| Ferritin | Ferritin | M: 24–336, F: 11–307 | ng/mL | Haemochromatosis, NASH |
| Ceruloplasmin | CP | 20 – 60 | mg/dL | Wilson's disease |
| Anti-Mitochondrial Ab | AMA | Negative | — | Primary Biliary Cholangitis |
| Anti-Smooth Muscle Ab | ASMA | Negative | — | Autoimmune hepatitis |

### 7.3 Common Hepatology Abbreviations

```
NAFLD  — Non-Alcoholic Fatty Liver Disease
NASH   — Non-Alcoholic Steatohepatitis
CLD    — Chronic Liver Disease
LC     — Liver Cirrhosis
HCC    — Hepatocellular Carcinoma
PBC    — Primary Biliary Cholangitis
PSC    — Primary Sclerosing Cholangitis
AIH    — Autoimmune Hepatitis
HBV    — Hepatitis B Virus
HCV    — Hepatitis C Virus
MELD   — Model for End-Stage Liver Disease
CP     — Child-Pugh score
HE     — Hepatic Encephalopathy
SBP    — Spontaneous Bacterial Peritonitis
TIPS   — Transjugular Intrahepatic Portosystemic Shunt
```

---

## 8. Project Structure

```
intern-ocr-medical-pipeline/
│
├── README.md                               ← THIS FILE
├── requirements.txt
├── .gitmodules                             ← Submodule declarations (auto-generated)
├── .env.example                            ← API key template (never commit .env)
├── .gitignore
│
├── extern/                                 ← Git submodules — DO NOT edit code here
│   ├── preprocessing/                      ← intern-ocr-imagepreprocessing-ishika
│   ├── ocr_table_paddle/                   ← intern-ocr-paddleocr-aditya
│   ├── ocr_table_surya/                    ← intern-ocr-suryaocr-anshuman
│   ├── ocr_table_docling/                  ← intern-ocr-granite-docling
│   ├── ocr_handwritten_trocr/              ← intern-ocr-trocr-aditi
│   ├── ocr_handwritten_surya/              ← intern-ocr-suryaocr-anshuman
│   ├── ocr_printed_tesseract/              ← intern-ocr-tesseract-sarika
│   ├── ocr_printed_easyocr/                ← intern-ocr-easyocr-ankit
│   └── ocr_printed_olmocr/                 ← intern-ocr-olmocr-devansh
│
├── classifier/
│   ├── __init__.py
│   ├── heuristic_classifier.py             ← Rule-based: TABLE / HW / PRINTED
│   └── cnn_classifier.py                   ← (Optional) CNN-based classifier
│
├── ocr/
│   ├── __init__.py
│   ├── submodule_paths.py                  ← Adds all extern/ dirs to sys.path
│   ├── router.py                           ← run_ocr() entry point
│   ├── ocr1_table.py                       ← Imports from extern/ocr_table_*
│   ├── ocr2_handwritten.py                 ← Imports from extern/ocr_handwritten_*
│   └── ocr3_printed.py                     ← Imports from extern/ocr_printed_*
│
├── extraction/
│   ├── __init__.py
│   ├── schema.py                           ← Pydantic models
│   ├── formatter.py                        ← LLM prompt + JSON extraction
│   ├── unit_normaliser.py                  ← Standardise units to SI
│   └── reference_ranges.py                ← Hepatology reference range DB
│
├── diagnosis/
│   ├── __init__.py
│   ├── engine.py                           ← Rule + LLM diagnosis engine
│   ├── hepatology_kb.py                    ← Knowledge base (Sherlock's + AASLD)
│   └── report_generator.py                ← Human-readable diagnosis report
│
├── pipeline.py                             ← Main entry point: run_pipeline()
├── tests/
│   ├── test_preprocessing.py
│   ├── test_classifier.py
│   ├── test_ocr_router.py
│   ├── test_extraction.py
│   └── sample_images/                      ← Test images (anonymised)
│
└── notebooks/
    ├── 01_preprocessing_exploration.ipynb
    ├── 02_classifier_training.ipynb
    └── 03_extraction_evaluation.ipynb
```

---

## 9. Setup & Installation

### 9.1 Prerequisites

- Python 3.11+
- Git
- Tesseract 5 system binary (for OCR 3 fallback)
- CUDA 12.x (optional, for TrOCR / olmOCR GPU acceleration)

### 9.2 Clone and Install

```bash
# Clone this repo WITH all submodules in one command
git clone --recurse-submodules \
  https://github.com/ibm-techlab-summer-internship/intern-ocr-medical-pipeline.git
cd intern-ocr-medical-pipeline

# If you already cloned without --recurse-submodules, run:
git submodule update --init --recursive

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install this pipeline's own dependencies
pip install -r requirements.txt

# Install each submodule's dependencies
pip install -r extern/preprocessing/requirements.txt
pip install -r extern/ocr_table_paddle/requirements.txt
pip install -r extern/ocr_handwritten_trocr/requirements.txt
pip install -r extern/ocr_printed_tesseract/requirements.txt
pip install -r extern/ocr_printed_easyocr/requirements.txt
pip install -r extern/ocr_printed_olmocr/requirements.txt
```

> **Tip:** To update all submodules to their latest commits at any time:
> ```bash
> git submodule update --remote --merge
> ```

### 9.3 Required `requirements.txt`

```
# Image processing
opencv-python>=4.9.0.80
Pillow>=10.3.0
deskew>=1.5.0
pymupdf>=1.24.0

# OCR engines
paddlepaddle>=2.6.1
paddleocr>=2.7.3
easyocr>=1.7.1
pytesseract>=0.3.13
surya-ocr>=0.6.0

# Handwriting OCR
transformers>=4.41.0
torch>=2.3.0

# LLM for formatting
openai>=1.30.0          # or ibm-watsonx-ai

# Schema validation
pydantic>=2.7.0

# Utilities
numpy>=1.26.0
pandas>=2.2.0
python-dotenv>=1.0.1
loguru>=0.7.2
```

### 9.4 Environment Variables

Create a `.env` file (never commit it — it is in `.gitignore`):

```bash
# .env.example — copy to .env and fill in values
LLM_API_KEY=your_api_key_here
LLM_API_ENDPOINT=https://...
LLM_MODEL_ID=ibm/granite-3-3-8b-instruct
```

---

## 10. Running the Pipeline

### 10.1 Single Image

```python
from pipeline import run_pipeline

result = run_pipeline(image_path="sample_images/lft_report.jpg")
print(result)   # Validated JSON dict
```

### 10.2 CLI

```bash
python pipeline.py --input sample_images/lft_report.jpg --output output/result.json
```

### 10.3 Batch Processing

```bash
python pipeline.py --input_dir sample_images/ --output_dir output/ --log_level INFO
```

### 10.4 Expected Output (example)

```json
{
  "document_metadata": {
    "patient_id": "IPD-2024-0091",
    "patient_name": null,
    "date_of_collection": "2024-11-14",
    "date_of_report": "2024-11-14",
    "lab_name": "Apollo Diagnostics",
    "referring_doctor": "Dr. R. Sharma",
    "department": "Hepatology"
  },
  "lab_results": [
    {
      "test_name": "ALT (SGPT)",
      "test_abbreviation": "ALT",
      "value": 78.0,
      "unit": "U/L",
      "reference_range": { "low": 7.0, "high": 56.0, "unit": "U/L" },
      "flag": "HIGH",
      "clinical_significance": "Elevated ALT suggests hepatocellular injury"
    },
    {
      "test_name": "Total Bilirubin",
      "test_abbreviation": "T.Bil",
      "value": 3.2,
      "unit": "mg/dL",
      "reference_range": { "low": 0.2, "high": 1.2, "unit": "mg/dL" },
      "flag": "HIGH",
      "clinical_significance": "Elevated bilirubin indicates jaundice; investigate cholestasis vs haemolysis"
    }
  ],
  "pipeline_metadata": {
    "preprocessing_transformations": ["deskew", "clahe", "otsu_binarise"],
    "doc_class": "TABLE",
    "ocr_engine": "PaddleOCR-PP-Structure",
    "extraction_confidence": 0.94,
    "schema_version": "1.0"
  }
}
```

---

## 11. Testing Guidelines

### 11.1 Unit Tests

Each module must have its own test file in `tests/`. Run with:

```bash
pytest tests/ -v --tb=short
```

| Test File | What to Test |
|---|---|
| `test_preprocessing.py` | PSNR improvement, skew correction accuracy, output shape |
| `test_classifier.py` | Accuracy ≥ 85% on 50-image labelled test set |
| `test_ocr_router.py` | Correct engine called for each doc class |
| `test_extraction.py` | JSON schema validation passes, no Pydantic errors |

### 11.2 Sample Test Images Required

Prepare at least 5 anonymised sample images per category:
- `tests/sample_images/table/` — printed lab tables
- `tests/sample_images/handwritten/` — handwritten doctor notes
- `tests/sample_images/printed_text/` — typed radiology / discharge notes

**Important:** Remove all real patient identifiers before committing test images.

---

## 12. Evaluation Metrics

### 12.1 OCR Accuracy

| Metric | Formula | Target |
|---|---|---|
| Character Error Rate (CER) | Edit distance / total chars | < 5% |
| Word Error Rate (WER) | Word-level edit distance | < 8% |
| Field Extraction Accuracy | Correctly extracted fields / total fields | > 90% |

### 12.2 Table Structure Accuracy

| Metric | Description | Target |
|---|---|---|
| Row Detection Accuracy | % rows correctly identified | > 95% |
| Column Alignment | % values in correct column | > 92% |
| Header Mapping | % headers correctly labelled | > 95% |

### 12.3 JSON Quality

- Schema validation pass rate: **100%** (Pydantic hard gate)
- Unit normalisation accuracy: > 98%
- Flag correctness (vs manual annotation): > 95%

---

## 13. Contribution Guidelines

1. Create a feature branch: `git checkout -b feature/your-name-task-description`
2. Write code with docstrings following Google style.
3. Write or update tests for your module.
4. Run `pytest tests/` before pushing — no failures allowed.
5. Open a Pull Request with a short description of what you changed and why.
6. Do **not** commit `.env`, model weights, or patient data.
7. All secrets must be in environment variables (see `.env.example`).

---

## 14. Resources & References

### OCR & Document Understanding
- PaddleOCR PP-Structure: https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/README.md
- TrOCR paper: https://arxiv.org/abs/2109.10282
- Surya OCR: https://github.com/VikParuchuri/surya
- Tesseract 5 docs: https://tesseract-ocr.github.io/tessdoc/

### Image Preprocessing
- OpenCV documentation: https://docs.opencv.org/
- CLAHE explanation: https://docs.opencv.org/4.x/d5/daf/tutorial_py_histogram_equalization.html
- Deskew library: https://github.com/sbrunner/deskew

### Hepatology Medical Reference
- Sherlock S, Dooley J. *Diseases of the Liver and Biliary System*, 13th Ed. Wiley-Blackwell, 2018.
- AASLD Practice Guidelines: https://www.aasld.org/publications/practice-guidelines
- Harrison's Principles of Internal Medicine — Hepatology chapters
- Lab Tests Online — Reference Ranges: https://labtestsonline.org

### LLM / Formatting
- IBM Watsonx AI SDK: https://ibm.github.io/watsonx-ai-python-sdk/
- Pydantic v2 docs: https://docs.pydantic.dev/latest/

---

*Pipeline README v1.0 — Medical OCR Intern Project*
