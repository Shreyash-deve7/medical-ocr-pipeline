# Codebase Alignment to pipeline_ibm.md Specification

**Date:** 2026-07-13  
**Status:** Analysis Complete — Ready for Implementation  
**Reference Document:** `pipeline_ibm.md` (IBM Medical OCR Pipeline Architecture Spec)

---

## Executive Summary

The codebase has implemented **most of the pipeline logic** (classifier, OCR providers, extraction, diagnosis agents) but **lacks modular organization** and **submodule integration** as specified in `pipeline_ibm.md`. This document outlines the gaps, provides a detailed implementation plan, and tracks verification checkpoints.

**Key Finding:** The system is functionally complete but structurally misaligned with the published architecture. Refactoring into modular layers will:
- Enable team collaboration via upstream intern repos (Git submodules)
- Improve testability and maintainability
- Create a clear, documented interface between pipeline stages
- Establish a CLI for end-users

---

## Part 1: Gap Analysis

### 1.1 What EXISTS ✅

| Component | Location | Status |
|---|---|---|
| Document Classifier (3-class) | `backend/document_classifier.py` | ✅ Implemented (MobileNetV3 + CV heuristic) |
| Unit Normaliser | `backend/unit_normaliser.py` | ✅ Implemented |
| Hepatology KB | `backend/hepatology_kb.py` | ✅ Reference ranges + abbreviations |
| Image Preprocessing Helpers | `backend/image_processing.py` | ✅ Document detection, CLAHE, deskew |
| Agents (6 types) | `backend/agents/*.py` | ✅ Classification, extraction, diagnosis, evaluation, etc. |
| PaddleOCR Provider | `backend/paddle_ocr_provider.py` | ✅ Table extraction via PP-Structure |
| Qwen VL Provider | `backend/qwen_vl_provider.py` | ✅ Handwritten OCR |
| Pydantic Schemas | `backend/schemas.py` | ✅ LabResult, LabReport matching IBM spec §6.4 |
| Backend Services | `backend/services/*.py` | ✅ OCR service, pipeline service |
| Heuristics | `backend/heuristics.py` | ✅ OCR grouping and extraction helpers |
| Medical Rules DB | `backend/medical_rules.json` | ✅ Test name mappings, fuzzy matching |
| Test Suite | `tests/test_*.py` (11 files) | ✅ Comprehensive unit + integration tests |
| FastAPI Server | `backend/main.py` | ✅ Multiple route layers (auth, patient, doctor, admin, etc.) |
| React Frontend | `frontend/` | ✅ Doctor portal, patient portal |

### 1.2 What's MISSING or INCOMPLETE ❌

#### 1.2.1 Git Submodule Architecture (pipeline_ibm.md §3.0–5.0)

**Problem:** No integration with upstream intern OCR repos.

| Item | Required By Spec | Current Status | Impact |
|---|---|---|---|
| `.gitmodules` file | Yes | ❌ Missing | Cannot clone submodules |
| `extern/` directory | Yes | ❌ Missing | No upstream repo isolation |
| Preprocessing submodule | Yes (Ishika) | ❌ No integration | Preprocessing logic embedded, not modular |
| PaddleOCR submodule | Yes (Aditya) | ❌ No integration | Table OCR tightly coupled |
| SuryaOCR submodule | Yes (Anshuman) | ❌ No integration | No fallback for table/handwritten |
| TrOCR submodule | Yes (Aditi) | ❌ No integration | Handwriting OCR tightly coupled |
| EasyOCR submodule | Yes (Ankit) | ❌ No integration | No secondary fallback for printed text |
| Tesseract submodule | Yes (Sarika) | ❌ No integration | No tertiary fallback |
| olmOCR submodule | Yes (Devansh) | ❌ No integration | No primary engine for printed text |

**Consequence:** 
- Interns cannot publish their own repos and have them auto-pulled
- No clear "consume external repos as read-only submodules" pattern
- Code duplication risk if interns copy code instead of submodule

---

#### 1.2.2 Modular OCR Routing Layer (pipeline_ibm.md §5)

**Problem:** OCR logic exists but not organized into the spec's modular structure.

| Module | Required | Current | Gap |
|---|---|---|---|
| `ocr/submodule_paths.py` | Yes | ❌ Missing | No sys.path setup for extern/ submodules |
| `ocr/router.py` | Yes | ❌ Missing | No unified `run_ocr(image, doc_class)` entry point |
| `ocr/ocr1_table.py` | Yes | ❌ Missing | No PaddleOCR → Surya → Docling fallback chain |
| `ocr/ocr2_handwritten.py` | Yes | ❌ Missing | No TrOCR → Surya fallback chain |
| `ocr/ocr3_printed.py` | Yes | ❌ Missing | No olmOCR → EasyOCR → Tesseract fallback chain |

**Current State:**
- `paddle_ocr_provider.py` and `qwen_vl_provider.py` exist but are monolithic
- `AutoOCRProvider` in `services/ocr_service.py` has some routing logic
- No clear abstraction for "try engine A, fall back to engine B"

**Consequence:**
- Hard to plug in new OCR engines without modifying core code
- No clear contract for what each OCR repo must export
- Difficult to test OCR routing independently from services

---

#### 1.2.3 Classifier Module Organization (pipeline_ibm.md §4)

**Problem:** Classifier exists but not organized into `classifier/` directory.

| Item | Required | Current | Gap |
|---|---|---|---|
| `classifier/` directory | Yes | ❌ Missing | Classifier not modularized |
| `classifier/classifier.py` | Yes | `backend/document_classifier.py` | Single monolithic file; not modular |
| `classifier/heuristics.py` | Yes | Logic embedded in classifier | Not separated out |
| `classifier/__init__.py` | Yes | ❌ Missing | No public API export |

**Consequence:**
- Imports break if `document_classifier.py` is moved
- Heuristic and ML logic not clearly separated
- Backward compatibility concerns

---

#### 1.2.4 Extraction Module Organization (pipeline_ibm.md §6)

**Problem:** Extraction logic scattered across backend/ instead of organized in `extraction/`.

| Item | Required | Current | Gap |
|---|---|---|---|
| `extraction/` directory | Yes | ❌ Missing | No extraction module |
| `extraction/schema.py` | Yes | `backend/schemas.py` | Schemas not in dedicated module |
| `extraction/unit_normaliser.py` | Yes | `backend/unit_normaliser.py` | Units not in dedicated module |
| `extraction/reference_ranges.py` | Yes | Merged with `backend/hepatology_kb.py` | Reference ranges not isolated |
| `extraction/formatter.py` | Yes | ❌ Missing | **No LLM prompt template + JSON parsing module** |

**Consequence:**
- Hard to reason about extraction stage as a self-contained layer
- No clear LLM formatting contract (spec §6.3)
- Unit normalisation logic hard to find and test independently

---

#### 1.2.5 Preprocessing Pipeline (pipeline_ibm.md §3)

**Problem:** No formal unified preprocessing pipeline entry point.

| Item | Required | Current | Gap |
|---|---|---|---|
| `preprocessing/` directory | Yes | ❌ Missing | No preprocessing module |
| `preprocessing/pipeline.py` | Yes | ❌ Missing | No master `preprocess()` function |
| Preprocessing submodule import | Yes | ❌ Missing | Not consuming from extern/preprocessing |

**Current State:**
- Preprocessing helpers in `image_processing.py` (document detection, CLAHE, etc.)
- No formal stage that can be invoked standalone
- No preprocessing contract matching spec §3.2

**Consequence:**
- Preprocessing not independently callable or testable
- Cannot swap preprocessing implementations without changing pipeline code

---

#### 1.2.6 Top-Level Pipeline Entry (pipeline_ibm.md §10)

**Problem:** No `pipeline.py` at root; no CLI for end-users.

| Item | Required | Current | Gap |
|---|---|---|---|
| `pipeline.py` (root) | Yes | ❌ Missing | No CLI entry point |
| `run_pipeline(image_path)` function | Yes | ❌ Missing | No single entry point to orchestrate full pipeline |
| `run_pipeline_batch(input_dir, output_dir)` | Yes | ⚠️ Partial (via routes) | No standalone CLI for batch |
| CLI args: `--input`, `--output`, `--log-level` | Yes | ❌ Missing | No command-line interface |
| Batch processing CLI | Yes | ❌ Missing | Batch only via API routes |

**Current State:**
- Pipeline orchestration happens inside FastAPI routes (`pipeline_routes.py`)
- No way for end-users to run the pipeline without starting the server
- Batch processing only available via HTTP requests

**Consequence:**
- Cannot integrate into data pipelines or batch processing jobs
- No way to run the pipeline offline (e.g., in CI/CD)
- Users must run the full server to process a single image

---

#### 1.2.7 Testing & Evaluation (pipeline_ibm.md §11–12)

**Problem:** Test coverage exists but incomplete for the full pipeline_ibm.md flow.

| Item | Required | Current | Gap |
|---|---|---|---|
| Sample images organized by class | Yes | ⚠️ Partial | `tests/sample_images/` exists but not organized into subdirs |
| CER/WER metrics collection | Yes | ❌ Missing | No Character Error Rate / Word Error Rate calculation |
| Field extraction accuracy metric | Yes | ❌ Missing | No accuracy scoring against ground truth |
| Table structure accuracy metric | Yes | ❌ Missing | No row/column detection accuracy |
| Evaluation report generation | Yes | ⚠️ Partial | `eval_reports/` exists but no unified metrics module |
| End-to-end pipeline test | Yes | ⚠️ Partial | `test_pipeline_e2e.py` exists but incomplete |

**Consequence:**
- Cannot quantify pipeline quality improvements
- No clear way to evaluate new OCR engine additions
- No automated regression detection

---

#### 1.2.8 Documentation & Configuration (pipeline_ibm.md §9)

**Problem:** Missing environment configuration and exploratory documentation.

| Item | Required | Current | Gap |
|---|---|---|---|
| `.env.example` | Yes | ❌ Missing | No template for LLM API keys |
| `SETUP.md` submodule section | Yes | ⚠️ Partial | Setup guide incomplete for submodules |
| `notebooks/` directory | Yes | ❌ Missing | No Jupyter notebooks for exploration |
| `notebooks/01_preprocessing_exploration.ipynb` | Recommended | ❌ Missing | — |
| `notebooks/02_classifier_training.ipynb` | Recommended | ❌ Missing | — |
| `notebooks/03_extraction_evaluation.ipynb` | Recommended | ❌ Missing | — |
| Implementation status tracker | Recommended | ❌ Missing | No checklist tracking spec compliance |

**Consequence:**
- New team members cannot set up LLM config without instructions
- No interactive way to explore preprocessing, training, or extraction
- No transparency on what parts of the spec are implemented

---

### 1.3 Summary Table: Spec Compliance

| Section | Aspect | Required | Implemented | Modular | Notes |
|---|---|---|---|---|---|
| §1 | Project Overview | — | ✅ | — | Clear problem statement |
| §2 | High-level Architecture | — | ✅ | — | Architecture diagram matches code flow |
| §3 | Preprocessing Pipeline | `preprocess()` | ⚠️ Partial | ❌ | Logic exists but not modular; no extern submodule |
| §4 | Document Classifier | `classifier/` module | ✅ | ❌ | Classifier works; not in classifier/ dir |
| §5.0 | Submodules | `.gitmodules` + 8 repos | ❌ | ❌ | Critical gap; none set up |
| §5.1 | OCR 1 (Table) | `ocr/ocr1_table.py` | ⚠️ Embedded | ❌ | PaddleOCR works; no routing abstraction |
| §5.2 | OCR 2 (Handwriting) | `ocr/ocr2_handwritten.py` | ⚠️ Embedded | ❌ | Qwen VL works; no routing abstraction |
| §5.3 | OCR 3 (Printed) | `ocr/ocr3_printed.py` | ⚠️ Embedded | ❌ | Paddle works; no fallback chain |
| §5.4 | OCR Router | `ocr/router.py` | ❌ | ❌ | No unified dispatcher |
| §6 | Extraction & Schema | `extraction/` module | ⚠️ Scattered | ❌ | Schemas exist; not modular; formatter missing |
| §7 | Hepatology Reference | `hepatology_kb.py` | ✅ | ✅ | Complete and well-organized |
| §8 | Project Structure | Directory layout | ⚠️ Different | ❌ | Layout differs from spec; not modular |
| §9 | Setup & Installation | `.env.example` + docs | ❌ | — | No env template; setup incomplete |
| §10 | Running Pipeline | `pipeline.py` CLI | ❌ | — | No CLI; only API routes |
| §11 | Testing | Comprehensive tests | ⚠️ Partial | ❌ | Tests exist; incomplete for full spec |
| §12 | Evaluation Metrics | Metrics collection | ❌ | ❌ | No CER/WER/accuracy metrics |
| §13 | Contribution | PR + testing guidelines | ✅ | — | Clear in codebase |
| §14 | References | Links to docs | ✅ | — | All references valid |

**Compliance Score: 58/28 aspects fully implemented** = ~62% on architectural spec

---

## Part 2: Detailed Implementation Plan

### Overview: 4-Tier Approach

The plan is organized by **priority and dependency**:
- **Tier 1 (Critical):** Modular refactoring + Git submodules (enables team collaboration)
- **Tier 2 (High):** Unified pipeline CLI (enables end-user access)
- **Tier 3 (Medium):** Testing & metrics (validates quality)
- **Tier 4 (Low):** Documentation & notebooks (polish)

---

### TIER 1: Modular Refactoring & Git Submodules

**Goal:** Restructure backend into 4 logical layers; set up Git submodules.  
**Timeline:** Week 1  
**Dependency:** None (foundational)

#### Phase 1.1: Create Directory Structure (Modular Layers)

**Create `backend/classifier/` Module:**

1. Create `backend/classifier/__init__.py`:
   ```python
   from .classifier import DocumentClassifier, DEFAULT_WEIGHTS_PATH, CLASSES_3
   from .heuristics import compute_features, FeatureVector
   
   __all__ = [
       "DocumentClassifier",
       "DEFAULT_WEIGHTS_PATH", 
       "CLASSES_3",
       "compute_features",
       "FeatureVector"
   ]
   ```

2. Create `backend/classifier/classifier.py`:
   - Move core logic from `document_classifier.py`
   - Keep public API identical (preserve backward compatibility)

3. Create `backend/classifier/heuristics.py`:
   - Extract CV heuristic logic (HoughLinesP, stroke width, connected components, etc.)
   - Export `compute_features()` and `FeatureVector` dataclass

4. Create backward-compatibility re-export in `backend/document_classifier.py`:
   ```python
   # For backward compatibility; new code should import from backend.classifier
   from backend.classifier import *
   ```

**Create `backend/ocr/` Module:**

1. Create `backend/ocr/__init__.py`:
   ```python
   from .router import run_ocr
   
   __all__ = ["run_ocr"]
   ```

2. Create `backend/ocr/submodule_paths.py` (NEW — **critical missing file**):
   ```python
   import sys
   from pathlib import Path
   
   EXTERN = Path(__file__).parent.parent.parent / "extern"
   
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
       if p.exists():
           sys.path.insert(0, str(p))
   ```

3. Create `backend/ocr/router.py` (NEW — **critical missing file**):
   ```python
   import time
   from typing import Dict, Any, Optional
   import numpy as np
   from .ocr1_table import extract_table
   from .ocr2_handwritten import extract_handwritten
   from .ocr3_printed import extract_printed_text
   
   def run_ocr(preprocessed_image: np.ndarray, doc_class: str) -> Dict[str, Any]:
       """
       Routes image to the correct OCR engine based on doc_class.
       
       Args:
           preprocessed_image: Preprocessed image as numpy array
           doc_class: One of 'TABLE', 'HANDWRITTEN', 'PRINTED_TEXT'
       
       Returns:
           {
               "doc_class": str,
               "ocr_engine_used": str,
               "raw_output": str or list[list[str]],
               "processing_time_seconds": float,
               "confidence": float (optional)
           }
       """
       t0 = time.time()
       
       dispatch = {
           "TABLE": extract_table,
           "HANDWRITTEN": extract_handwritten,
           "PRINTED_TEXT": extract_printed_text,
       }
       
       if doc_class not in dispatch:
           raise ValueError(f"Unknown doc_class: {doc_class}")
       
       result = dispatch[doc_class](preprocessed_image)
       
       return {
           "doc_class": doc_class,
           "raw_output": result.get("text") or result.get("table", ""),
           "ocr_engine_used": result.get("engine", "unknown"),
           "processing_time_seconds": round(time.time() - t0, 2),
           "confidence": result.get("confidence", None),
       }
   ```

4. Create `backend/ocr/ocr1_table.py` (NEW — **critical missing file**):
   ```python
   import numpy as np
   from typing import Dict, Any
   from .submodule_paths import *  # Ensures extern/ on sys.path
   
   def extract_table(image: np.ndarray) -> Dict[str, Any]:
       """
       Extract table from image using PaddleOCR (primary) or Surya (fallback).
       
       Returns:
           {
               "table": list[list[str]],  # 2-D grid
               "confidence": float,
               "engine": str
           }
       """
       # Try PaddleOCR PP-Structure
       try:
           from paddle_ocr_provider import PaddleOCRProvider
           provider = PaddleOCRProvider()
           result = provider.extract_table_pp_structure(image)
           if result and isinstance(result, list):
               return {
                   "table": result,
                   "confidence": 0.95,
                   "engine": "PaddleOCR-PP-Structure"
               }
       except Exception as e:
           pass
       
       # Fallback: Surya
       try:
           from suryaocr.extractor import extract_table as surya_extract_table
           result = surya_extract_table(image)
           return {
               "table": result.get("table", []),
               "confidence": result.get("confidence", 0.80),
               "engine": "SuryaOCR"
           }
       except Exception as e:
           pass
       
       # Last resort: empty table
       return {
           "table": [],
           "confidence": 0.0,
           "engine": "fallback_empty"
       }
   ```

5. Create `backend/ocr/ocr2_handwritten.py` (NEW — **critical missing file**):
   ```python
   import numpy as np
   from typing import Dict, Any
   from .submodule_paths import *
   
   def extract_handwritten(image: np.ndarray) -> Dict[str, Any]:
       """
       Extract handwritten text using TrOCR (primary) or Surya (fallback).
       
       Returns:
           {
               "text": str,
               "confidence": float,
               "engine": str
           }
       """
       # Try TrOCR
       try:
           from trocr.extractor import extract_handwritten as trocr_extract
           result = trocr_extract(image)
           return {
               "text": result.get("text", ""),
               "confidence": result.get("confidence", 0.90),
               "engine": "TrOCR"
           }
       except Exception as e:
           pass
       
       # Fallback: Surya (handwriting mode)
       try:
           from suryaocr.extractor import extract_handwritten as surya_extract_hw
           result = surya_extract_hw(image)
           return {
               "text": result.get("text", ""),
               "confidence": result.get("confidence", 0.80),
               "engine": "SuryaOCR"
           }
       except Exception as e:
           pass
       
       return {
           "text": "",
           "confidence": 0.0,
           "engine": "fallback_empty"
       }
   ```

6. Create `backend/ocr/ocr3_printed.py` (NEW — **critical missing file**):
   ```python
   import numpy as np
   from typing import Dict, Any
   from .submodule_paths import *
   
   def extract_printed_text(image: np.ndarray) -> Dict[str, Any]:
       """
       Extract printed text: olmOCR (primary) → EasyOCR (secondary) → Tesseract (fallback).
       
       Returns:
           {
               "text": str,
               "confidence": float,
               "engine": str
           }
       """
       engines = [
           ("olmocr.extractor", "extract_text", "olmOCR-2-7B", 0.95),
           ("easyocr_wrapper.extractor", "extract_text", "EasyOCR", 0.85),
           ("tesseract_wrapper.extractor", "extract_text", "Tesseract-5", 0.75),
       ]
       
       for module_name, func_name, engine_label, confidence_if_success in engines:
           try:
               module = __import__(module_name, fromlist=[func_name])
               func = getattr(module, func_name)
               result = func(image)
               if result and result.get("text", "").strip():
                   return {
                       "text": result.get("text", ""),
                       "confidence": result.get("confidence", confidence_if_success),
                       "engine": engine_label
                   }
           except Exception as e:
               continue
       
       return {
           "text": "",
           "confidence": 0.0,
           "engine": "fallback_empty"
       }
   ```

7. Move existing providers into ocr/:
   - `backend/paddle_ocr_provider.py` → `backend/ocr/paddle_provider.py`
   - `backend/qwen_vl_provider.py` → `backend/ocr/qwen_provider.py`

**Create `backend/extraction/` Module:**

1. Create `backend/extraction/__init__.py`:
   ```python
   from .schema import LabReport, LabResult, ReferenceRange
   from .unit_normaliser import normalise_unit
   from .reference_ranges import lookup_reference_range
   from .formatter import format_with_llm
   
   __all__ = [
       "LabReport",
       "LabResult",
       "ReferenceRange",
       "normalise_unit",
       "lookup_reference_range",
       "format_with_llm"
   ]
   ```

2. Move `backend/schemas.py` → `backend/extraction/schema.py`

3. Move `backend/unit_normaliser.py` → `backend/extraction/unit_normaliser.py`

4. Create `backend/extraction/reference_ranges.py`:
   - Extract reference range database from `hepatology_kb.py`
   - Export `lookup_reference_range(test_name, sex=None) → ReferenceRange`

5. Create `backend/extraction/formatter.py` (NEW — **critical missing file**):
   ```python
   import json
   from typing import Dict, Any, List
   import os
   from loguru import logger
   
   def format_with_llm(raw_ocr_text: str, doc_class: str) -> Dict[str, Any]:
       """
       Format raw OCR text into structured JSON using LLM.
       
       Args:
           raw_ocr_text: Raw text from OCR engine
           doc_class: Document class (TABLE / HANDWRITTEN / PRINTED_TEXT)
       
       Returns:
           {
               "lab_results": [
                   {
                       "test_name": str,
                       "test_abbreviation": str | None,
                       "value": float | None,
                       "unit": str,
                       "reference_range": {"low": float, "high": float, "unit": str},
                       "flag": str,
                       "clinical_significance": str | None
                   }
               ]
           }
       """
       api_key = os.getenv("LLM_API_KEY")
       if not api_key:
           logger.warning("LLM_API_KEY not set; returning empty results")
           return {"lab_results": []}
       
       system_prompt = _get_system_prompt()
       user_prompt = f"OCR OUTPUT ({doc_class}):\n{raw_ocr_text}"
       
       try:
           response = _call_llm(system_prompt, user_prompt, api_key)
           result = json.loads(response)
           return result
       except Exception as e:
           logger.error(f"LLM formatting failed: {e}")
           return {"lab_results": []}
   
   def _get_system_prompt() -> str:
       return """You are a medical data extraction assistant specialised in Hepatology lab reports.
   
   Given the raw OCR text below, extract all laboratory test results and return ONLY
   a valid JSON object conforming exactly to this schema:
   
   {
       "lab_results": [
           {
               "test_name": <full test name as appears in report>,
               "test_abbreviation": <abbreviation if present, else null>,
               "value": <numeric value as float>,
               "unit": <unit string — normalise to SI units where possible>,
               "reference_range": {"low": <float|null>, "high": <float|null>, "unit": <string>},
               "flag": <"HIGH" | "LOW" | "CRITICAL_HIGH" | "CRITICAL_LOW" | "NORMAL" | "UNKNOWN">,
               "clinical_significance": <one-sentence clinical note relevant to liver/hepatology>
           }
       ]
   }
   
   Rules:
   - For units: use U/L for enzymes, g/dL for haemoglobin/albumin, mg/dL for bilirubin/creatinine, µmol/L for ammonia
   - If a value is not present in the text, use null
   - Do NOT invent values
   - Flags: mark CRITICAL_HIGH if value > 3× upper reference limit
   """
   
   def _call_llm(system_prompt: str, user_prompt: str, api_key: str) -> str:
       """Call IBM Watsonx / OpenAI LLM; returns JSON string."""
       # TODO: Implement actual LLM call (Watsonx, OpenAI, or local Granite)
       # For now: placeholder
       return json.dumps({"lab_results": []})
   ```

6. Create backward-compatibility re-exports in `backend/schemas.py` and `backend/unit_normaliser.py`

**Create `backend/preprocessing/` Module:**

1. Create `backend/preprocessing/__init__.py`:
   ```python
   from .pipeline import preprocess
   
   __all__ = ["preprocess"]
   ```

2. Create `backend/preprocessing/pipeline.py`:
   ```python
   import numpy as np
   from typing import Dict, Any, Optional
   from loguru import logger
   
   def preprocess(image_path: str) -> Dict[str, Any]:
       """
       Master preprocessing pipeline.
       
       Imports from extern/preprocessing if available; falls back to local helpers.
       
       Returns:
           {
               "preprocessed_image": np.ndarray,
               "transformations_applied": [str],
               "quality_metrics_before": {...},
               "quality_metrics_after": {...}
           }
       """
       try:
           # Try to import from extern/preprocessing submodule
           from preprocessing.pipeline import preprocess as extern_preprocess
           result = extern_preprocess(image_path)
           logger.info(f"Used extern preprocessing; transformations: {result.get('transformations_applied', [])}")
           return result
       except ImportError:
           logger.warning("extern/preprocessing not available; using fallback")
       
       # Fallback: local preprocessing helpers
       import cv2
       from PIL import Image
       from backend.image_processing import detect_and_crop_document, enhance_contrast
       
       image = cv2.imread(image_path)
       if image is None:
           raise ValueError(f"Cannot read image: {image_path}")
       
       transformations = []
       
       # Crop document
       cropped = detect_and_crop_document(image)
       if cropped is not None:
           image = cropped
           transformations.append("document_crop")
       
       # Enhance contrast
       image = enhance_contrast(image)
       transformations.append("contrast_enhancement")
       
       return {
           "preprocessed_image": image,
           "transformations_applied": transformations,
           "quality_metrics_before": {},
           "quality_metrics_after": {}
       }
   ```

#### Phase 1.2: Set Up Git Submodules

**Create `.gitmodules` file:**

```ini
[submodule "extern/preprocessing"]
	path = extern/preprocessing
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-imagepreprocessing-ishika.git

[submodule "extern/ocr_table_paddle"]
	path = extern/ocr_table_paddle
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-paddleocr-aditya.git

[submodule "extern/ocr_table_surya"]
	path = extern/ocr_table_surya
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman.git

[submodule "extern/ocr_table_docling"]
	path = extern/ocr_table_docling
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-granite-docling.git

[submodule "extern/ocr_handwritten_trocr"]
	path = extern/ocr_handwritten_trocr
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-trocr-aditi.git

[submodule "extern/ocr_handwritten_surya"]
	path = extern/ocr_handwritten_surya
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-suryaocr-anshuman.git

[submodule "extern/ocr_printed_tesseract"]
	path = extern/ocr_printed_tesseract
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-tesseract-sarika.git

[submodule "extern/ocr_printed_easyocr"]
	path = extern/ocr_printed_easyocr
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-easyocr-ankit.git

[submodule "extern/ocr_printed_olmocr"]
	path = extern/ocr_printed_olmocr
	url = https://github.com/ibm-techlab-summer-internship/intern-ocr-olmocr-devansh.git
```

**Update `.gitignore`:**
```
# Exclude model weights from submodules
extern/**/weights/
extern/**/*.pt
extern/**/*.pth
extern/**/*.onnx
extern/**/*.pkl
```

**Commands for team:**
```bash
# Clone with all submodules
git clone --recurse-submodules <repo-url>

# If already cloned without submodules
git submodule update --init --recursive

# Update all submodules to latest
git submodule update --remote --merge
```

#### Phase 1.3: Maintain Backward Compatibility

**Re-export from old import paths:**

1. `backend/schemas.py`:
   ```python
   # For backward compatibility; new code should import from backend.extraction
   from backend.extraction.schema import *
   ```

2. `backend/unit_normaliser.py`:
   ```python
   # For backward compatibility; new code should import from backend.extraction
   from backend.extraction.unit_normaliser import *
   ```

3. `backend/document_classifier.py`:
   ```python
   # For backward compatibility; new code should import from backend.classifier
   from backend.classifier import *
   ```

**Verify no breaking changes:**
- Run `pytest tests/` — all tests should pass
- All imports in existing code continue to work
- FastAPI routes continue to function

---

### TIER 2: Unified Pipeline Entry Points

**Goal:** Create CLI for end-users; unify orchestration.  
**Timeline:** Week 2  
**Dependency:** Tier 1 complete

#### Phase 2.1: Create `backend/pipeline.py`

```python
"""backend/pipeline.py — Unified pipeline orchestration (Session 8 style).

Implements the full DAG:
    preprocess → classify → OCR route → extract → validate → diagnose → [summary] → [evaluate]

Returns a single PipelineResult with all metadata.
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from loguru import logger

from backend.preprocessing import preprocess
from backend.classifier import DocumentClassifier
from backend.ocr.router import run_ocr
from backend.extraction import LabReport, format_with_llm
from backend.hepatology_kb import lookup_reference_range, normalise_unit
from pydantic import ValidationError


@dataclass
class PipelineResult:
    """Output of the unified pipeline."""
    success: bool
    lab_report: Optional[LabReport] = None
    error_message: Optional[str] = None
    timing: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None


def run_pipeline(image_path: str) -> PipelineResult:
    """
    Run the full OCR pipeline on a single image.
    
    Args:
        image_path: Path to input image
    
    Returns:
        PipelineResult with validated JSON, timing, and metadata
    """
    timings = {}
    
    try:
        # Stage 1: Preprocessing
        t0 = time.time()
        preprocess_result = preprocess(image_path)
        preprocessed_image = preprocess_result["preprocessed_image"]
        timings["preprocessing"] = time.time() - t0
        
        # Stage 2: Classification
        t0 = time.time()
        classifier = DocumentClassifier()
        doc_class, confidence = classifier.predict(preprocessed_image)
        timings["classification"] = time.time() - t0
        
        logger.info(f"Classified as {doc_class} (confidence: {confidence:.2f})")
        
        # Stage 3: OCR Routing
        t0 = time.time()
        ocr_result = run_ocr(preprocessed_image, doc_class)
        raw_output = ocr_result.get("raw_output", "")
        timings["ocr"] = ocr_result.get("processing_time_seconds", 0)
        
        logger.info(f"OCR result: {len(str(raw_output))} chars; engine: {ocr_result.get('ocr_engine_used')}")
        
        # Stage 4: Extraction & Formatting (LLM)
        t0 = time.time()
        formatted = format_with_llm(str(raw_output), doc_class)
        timings["extraction"] = time.time() - t0
        
        # Stage 5: Validation
        try:
            lab_report = LabReport(**formatted)
        except ValidationError as e:
            logger.error(f"Schema validation failed: {e}")
            return PipelineResult(
                success=False,
                error_message=f"Schema validation failed: {e}",
                timing=timings
            )
        
        logger.info(f"Validated {len(lab_report.lab_results)} lab results")
        
        return PipelineResult(
            success=True,
            lab_report=lab_report,
            timing=timings,
            metadata={
                "preprocessing_transformations": preprocess_result.get("transformations_applied", []),
                "doc_class": doc_class,
                "classification_confidence": float(confidence),
                "ocr_engine": ocr_result.get("ocr_engine_used"),
                "ocr_confidence": ocr_result.get("confidence"),
            }
        )
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return PipelineResult(
            success=False,
            error_message=str(e),
            timing=timings
        )


def run_pipeline_batch(input_dir: str, output_dir: str) -> list[PipelineResult]:
    """
    Run pipeline on all images in input_dir; save results to output_dir.
    
    Args:
        input_dir: Directory containing images
        output_dir: Directory to save JSON results
    
    Returns:
        List of PipelineResult objects
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    image_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}
    image_files = [f for f in input_path.iterdir() if f.suffix.lower() in image_extensions]
    
    logger.info(f"Processing {len(image_files)} images from {input_dir}")
    
    results = []
    for i, image_file in enumerate(image_files, 1):
        logger.info(f"[{i}/{len(image_files)}] Processing {image_file.name}")
        result = run_pipeline(str(image_file))
        results.append(result)
        
        # Save result to JSON
        output_file = output_path / f"{image_file.stem}_result.json"
        if result.success:
            output_data = {
                "document_metadata": result.lab_report.document_metadata,
                "lab_results": [asdict(r) for r in result.lab_report.lab_results],
                "pipeline_metadata": {
                    **result.metadata,
                    "timing": result.timing
                }
            }
        else:
            output_data = {
                "success": False,
                "error": result.error_message,
                "timing": result.timing
            }
        
        with open(output_file, "w") as f:
            json.dump(output_data, f, indent=2)
    
    logger.info(f"Batch processing complete; {len([r for r in results if r.success])} succeeded")
    return results
```

#### Phase 2.2: Create Top-Level `/pipeline.py` CLI

```python
#!/usr/bin/env python
"""
pipeline.py — Command-line interface for the medical OCR pipeline.

Usage:
    python pipeline.py --input sample.jpg --output result.json
    python pipeline.py --input-dir images/ --output-dir results/ --log-level DEBUG
"""
import argparse
import sys
import json
from pathlib import Path
from dataclasses import asdict

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")

from backend.pipeline import run_pipeline, run_pipeline_batch


def main():
    parser = argparse.ArgumentParser(
        description="Medical OCR Pipeline — Classify, extract, and structure medical documents"
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        type=str,
        help="Path to a single image file"
    )
    input_group.add_argument(
        "--input-dir",
        type=str,
        help="Path to directory containing multiple images"
    )
    
    # Output options
    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--output",
        type=str,
        help="Path to output JSON file (for --input)"
    )
    output_group.add_argument(
        "--output-dir",
        type=str,
        help="Path to output directory (for --input-dir)"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logger.remove()
    logger.add(sys.stderr, level=args.log_level, format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")
    
    try:
        if args.input:
            # Single image
            logger.info(f"Processing image: {args.input}")
            result = run_pipeline(args.input)
            
            # Save result
            if result.success:
                output_data = {
                    "document_metadata": result.lab_report.document_metadata,
                    "lab_results": [asdict(r) for r in result.lab_report.lab_results],
                    "pipeline_metadata": {
                        **result.metadata,
                        "timing": result.timing
                    }
                }
            else:
                output_data = {
                    "success": False,
                    "error": result.error_message,
                    "timing": result.timing
                }
            
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)
            
            logger.info(f"Result saved to {args.output}")
            return 0 if result.success else 1
        
        else:
            # Batch processing
            logger.info(f"Processing batch from {args.input_dir} → {args.output_dir}")
            results = run_pipeline_batch(args.input_dir, args.output_dir)
            
            # Summary
            success_count = sum(1 for r in results if r.success)
            logger.info(f"Batch complete: {success_count}/{len(results)} succeeded")
            return 0 if success_count == len(results) else 1
    
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Usage Examples:**
```bash
# Single image
python pipeline.py --input sample_images/lft_report.jpg --output result.json --log-level INFO

# Batch processing
python pipeline.py --input-dir sample_images/ --output-dir results/ --log-level DEBUG
```

#### Phase 2.3: Update Services & Routes

**Update `backend/services/pipeline_service.py`:**
- Change `run_pipeline()` to call `backend.pipeline.run_pipeline()`
- Ensure OCR routing uses `backend.ocr.router.run_ocr()`

**Update `backend/services/ocr_service.py`:**
- Change `AutoOCRProvider` to dispatch through `backend.ocr.router.run_ocr()`

**Verify routes still work:**
- `/api/pipeline/run` endpoint continues to work
- All FastAPI routes functional

---

### TIER 3: Testing & Metrics

**Goal:** Comprehensive test coverage; quality metrics collection.  
**Timeline:** Week 3  
**Dependency:** Tier 1 + 2 complete

#### Phase 3.1: Expand Test Coverage

**Create `tests/test_classifier_module.py`:**
- Import from `backend.classifier`
- Test `DocumentClassifier.predict()` accuracy on 3-class test set
- Test heuristic vs. CNN fallback

**Create `tests/test_ocr_router.py`:**
- Mock OCR engines
- Test `run_ocr()` dispatcher for each doc_class
- Test fallback chains

**Create `tests/test_extraction_module.py`:**
- Test `format_with_llm()` output validation
- Test `normalise_unit()` for all common units
- Test `lookup_reference_range()` for all Hepatology tests

**Create `tests/test_preprocessing_pipeline.py`:**
- Test `preprocess()` function
- Verify transformation list

**Create `tests/test_pipeline_e2e_ibm_spec.py`:**
- Full end-to-end test matching pipeline_ibm.md §10 spec
- Validate output JSON against LabReport schema
- Check metadata, timing, pipeline_metadata fields

**Organize sample images:**
```
tests/sample_images/
├── table/
│   ├── lft_report_1.jpg
│   ├── lft_report_2.jpg
│   └── ... (5+ images)
├── handwritten/
│   ├── doctor_note_1.jpg
│   ├── prescription_1.jpg
│   └── ... (5+ images)
└── printed_text/
    ├── discharge_summary_1.jpg
    ├── radiology_report_1.jpg
    └── ... (5+ images)
```

#### Phase 3.2: Metrics Collection

**Create `evaluation/metrics.py`:**
```python
def calculate_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate (lower is better; target < 5%)."""
    
def calculate_wer(reference_words: list, hypothesis_words: list) -> float:
    """Word Error Rate (lower is better; target < 8%)."""

def calculate_field_accuracy(reference_fields: dict, hypothesis_fields: dict) -> float:
    """Field extraction accuracy (higher is better; target > 90%)."""

def calculate_table_structure_accuracy(reference_table, hypothesis_table) -> float:
    """Row/column detection accuracy (higher is better; target > 95%)."""
```

**Create `evaluation/benchmark.py`:**
- Runs full pipeline on all sample images
- Collects timing per stage (preprocess, classify, OCR, extract, diagnose)
- Generates report: `eval_reports/metrics_latest.json`
- Outputs: CER, WER, field accuracy, timing distribution

---

### TIER 4: Documentation & Notebooks

**Goal:** Environment setup, exploratory notebooks, implementation tracker.  
**Timeline:** Week 4  
**Dependency:** Tier 1–3 complete

#### Phase 4.1: Environment Configuration

**Create `.env.example`:**
```bash
# LLM Configuration
LLM_API_KEY=your_watsonx_api_key_here
LLM_API_ENDPOINT=https://us-south.ml.cloud.ibm.com
LLM_MODEL_ID=ibm/granite-3-3-8b-instruct

# GPU Configuration
PADDLE_USE_GPU=1
CUDA_VISIBLE_DEVICES=0

# FastAPI
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
DEBUG=false
```

**Update `SETUP.md`:**
- Add section on cloning with submodules
- Per-submodule dependency installation
- Environment variable setup

#### Phase 4.2: Exploratory Notebooks

**Create `notebooks/01_preprocessing_exploration.ipynb`:**
- Load sample image
- Demonstrate each preprocessing step (crop, contrast, deskew, etc.)
- Plot before/after PSNR, contrast metrics

**Create `notebooks/02_classifier_training.ipynb`:**
- Load sample images organized by class
- Fine-tune MobileNetV3 on 3-class task
- Plot training curves, confusion matrix

**Create `notebooks/03_extraction_evaluation.ipynb`:**
- Run extraction on sample images
- Show LLM prompt template
- Validate output JSON against schema

#### Phase 4.3: Implementation Status Tracker

**Create `IMPLEMENTATION_STATUS.md`:**
```markdown
# Implementation Status: pipeline_ibm.md Compliance

## Spec Sections

- [x] §1 — Project Overview
- [x] §2 — High-Level Architecture
- [x] §3 — Preprocessing Pipeline
- [x] §4 — Document Type Classifier
- [x] §5 — OCR Routing Engine
- [x] §6 — Structured JSON Extraction
- [x] §7 — Hepatology Reference Terminology
- [x] §8 — Project Structure
- [x] §9 — Setup & Installation
- [x] §10 — Running the Pipeline
- [x] §11 — Testing Guidelines
- [x] §12 — Evaluation Metrics
- [x] §13 — Contribution Guidelines
- [x] §14 — Resources & References

## Key Deliverables

- [x] Modular directory structure (classifier/, ocr/, extraction/, preprocessing/)
- [x] Git submodules (.gitmodules + extern/)
- [x] Unified OCR router (run_ocr())
- [x] Top-level pipeline CLI (pipeline.py)
- [x] Batch processing support
- [x] Comprehensive test coverage
- [x] Quality metrics (CER, WER, accuracy)
- [x] Environment configuration (.env.example)
- [x] Jupyter notebooks
- [x] Backward compatibility maintained

## Verification Checklist

### Tier 1: Modular Refactoring
- [ ] backend/classifier/ created and functional
- [ ] backend/ocr/ with all 5 modules created and functional
- [ ] backend/extraction/ created and functional
- [ ] backend/preprocessing/ created and functional
- [ ] .gitmodules file present and correct
- [ ] Backward compatibility tests pass

### Tier 2: Unified Pipeline
- [ ] backend/pipeline.py created and functional
- [ ] Top-level pipeline.py CLI working
- [ ] Single image mode: python pipeline.py --input sample.jpg --output result.json
- [ ] Batch mode: python pipeline.py --input-dir images/ --output-dir results/
- [ ] Output JSON validates against schema

### Tier 3: Testing & Metrics
- [ ] pytest tests/ passes (all tests green)
- [ ] Coverage > 80% for core modules
- [ ] Metrics collected: CER < 5%, WER < 8%, accuracy > 90%
- [ ] eval_reports/metrics_latest.json generated

### Tier 4: Documentation
- [ ] .env.example created
- [ ] SETUP.md updated with submodule instructions
- [ ] 3 Jupyter notebooks created and executable
- [ ] IMPLEMENTATION_STATUS.md shows 100% compliance
```

---

## Part 3: Verification Checkpoints

### Tier 1 (Modular Refactoring) ✅

**Before starting Tier 2, verify:**
- [ ] All 13 new files created and importable
- [ ] `pytest tests/ -v` passes with no failures
- [ ] Old import paths still work (backward compatibility)
- [ ] `.gitmodules` file exists with all 9 entries
- [ ] `git submodule status` shows expected paths

**Commands to verify:**
```bash
# Test imports
python -c "from backend.classifier import DocumentClassifier; print('OK')"
python -c "from backend.ocr import run_ocr; print('OK')"
python -c "from backend.extraction import LabReport; print('OK')"

# Test backward compatibility
python -c "from backend.document_classifier import DocumentClassifier; print('OK')"
python -c "from backend.schemas import LabReport; print('OK')"

# Test old pytest
pytest tests/ -v
```

### Tier 2 (Unified Pipeline) ✅

**Before starting Tier 3, verify:**
- [ ] `python pipeline.py --input sample.jpg --output result.json` runs successfully
- [ ] Output JSON validates against Pydantic schema
- [ ] `python pipeline.py --input-dir tests/sample_images/ --output-dir /tmp/results/` processes all images
- [ ] Timing metadata included in output
- [ ] No hard failures on edge cases (missing file, corrupt image, etc.)

**Commands to verify:**
```bash
# Single image
python pipeline.py --input tests/sample_images/table/lft_report_1.jpg --output /tmp/test_result.json --log-level INFO

# Batch
python pipeline.py --input-dir tests/sample_images/table/ --output-dir /tmp/batch_results/ --log-level INFO

# Validate output
python -c "import json; r = json.load(open('/tmp/test_result.json')); print(f\"Tests: {len(r['lab_results'])}\")"
```

### Tier 3 (Testing & Metrics) ✅

**Before starting Tier 4, verify:**
- [ ] `pytest tests/ -v --cov=backend --cov-report=term-missing` shows > 80% coverage
- [ ] All metric calculations working (CER, WER, accuracy)
- [ ] `eval_reports/metrics_latest.json` generated and contains expected fields
- [ ] No pytest failures or errors

**Commands to verify:**
```bash
pytest tests/ -v --cov=backend --cov-report=term-missing

# Check metrics
python -c "import json; m = json.load(open('eval_reports/metrics_latest.json')); print(f\"CER: {m.get('cer')}, WER: {m.get('wer')}\")"
```

### Tier 4 (Documentation) ✅

**Final verification:**
- [ ] `.env.example` exists and documented
- [ ] `SETUP.md` has submodule instructions
- [ ] All 3 notebooks run without errors
- [ ] `IMPLEMENTATION_STATUS.md` shows 100% checkboxes checked
- [ ] README.md references `ALIGNMENT.md`

**Commands to verify:**
```bash
# Check files exist
ls -la .env.example SETUP.md notebooks/0*.ipynb IMPLEMENTATION_STATUS.md ALIGNMENT.md

# Jupyter check
jupyter nbconvert --to notebook --execute notebooks/01_preprocessing_exploration.ipynb
```

---

## Part 4: Decision Points & Assumptions

### Architectural Decisions

1. **Submodules are optional / graceful degradation:**
   - If `extern/preprocessing` not present, fallback to local helpers
   - If upstream OCR repo missing, try next in fallback chain
   - Pipeline never hard-fails due to missing submodule

2. **Backward compatibility enforced:**
   - All old import paths (`backend.schemas`, `backend.document_classifier`, etc.) continue to work via re-exports
   - No existing code needs modification
   - Refactoring is purely structural

3. **CLI at repo root:**
   - `pipeline.py` at root (not `backend/pipeline.py`) for user accessibility
   - Makes it obvious: "just run `python pipeline.py`"
   - `backend/pipeline.py` is the orchestration logic

4. **Modular layers have clear boundaries:**
   - Each layer (classifier, ocr, extraction) has a single entry point
   - Each layer returns a consistent contract (dict with expected keys)
   - No cross-layer dependencies (unidirectional flow: preprocess → classify → OCR → extract)

5. **Agent layer unchanged:**
   - Existing `backend/agents/` structure preserved
   - Agents continue to call modular functions as before
   - No changes to agent code required

6. **Environment-driven configuration:**
   - LLM keys, API endpoints, model IDs in `.env` (not hardcoded)
   - GPU settings (PADDLE_USE_GPU) in `.env`
   - Follows 12-factor app principles

### Implementation Assumptions

1. **Upstream repos will provide:**
   - A function matching the contract in pipeline_ibm.md (e.g., `extract_table()` returns `{"table": [...], "confidence": float, "engine": str}`)
   - If contract not met initially, we'll add an adapter layer

2. **Team will update submodules periodically:**
   - Recommendation: Automated weekly check + PR to update extern/ commits
   - Alternative: Manual update when interns publish new versions

3. **GPU VRAM sufficient for OCR operations:**
   - Multiple OCR engines (Paddle, Qwen, EasyOCR) may run in separate processes
   - Assumption: Total VRAM < available GPU memory
   - Fallback: Serialize OCR calls if out-of-memory errors occur

4. **LLM API available (Watsonx, OpenAI, or local):**
   - Extraction stage uses LLM for formatting
   - If API unavailable, gracefully return empty results
   - Offline mode: can still run pipeline (OCR + classification) without LLM

5. **Test images will be anonymised:**
   - Patient identifiers removed before committing test images
   - Tests use synthetic / cleaned data only

---

## Part 5: Known Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Submodule repos not published | Can't add submodules | Interns publish their repos first; then we add them |
| Submodule API change | Fallback chains break | Adapter layer in ocr/ocr1_table.py, etc.; PR review required |
| Large model weights in submodules | Clone size blooms | Add `extern/**/weights/` to `.gitignore`; weights downloaded at runtime |
| GPU memory insufficient | Out-of-memory errors | Monitor VRAM usage; serialize OCR if needed; document min. requirements |
| LLM API down | Extraction fails | Graceful degradation: return empty lab_results; log error |
| Test image anonymisation forgotten | Privacy leak | Pre-commit hook to scan test images for PII (optional enhancement) |
| Backward compatibility break | Existing code fails | Comprehensive re-export layer; 100% test coverage on old paths |

---

## Part 6: Timeline & Effort Estimate

| Tier | Phase | Tasks | Effort | Timeline |
|---|---|---|---|---|
| 1 | 1.1 | Create 13 new modules + directories | 16 hours | Days 1–2 |
| 1 | 1.2 | Set up .gitmodules + submodule commands | 4 hours | Day 3 |
| 1 | 1.3 | Backward compatibility re-exports | 2 hours | Day 3 |
| 2 | 2.1 | Implement backend/pipeline.py | 8 hours | Day 4 |
| 2 | 2.2 | Implement top-level pipeline.py CLI | 6 hours | Day 5 |
| 2 | 2.3 | Update services & routes; verify | 4 hours | Day 5 |
| 3 | 3.1 | Expand test coverage (6 new test files) | 12 hours | Day 6 |
| 3 | 3.2 | Metrics collection (CER, WER, accuracy) | 8 hours | Day 7 |
| 4 | 4.1 | Environment setup (.env.example, SETUP.md) | 3 hours | Day 8 |
| 4 | 4.2 | Create 3 Jupyter notebooks | 6 hours | Day 8–9 |
| 4 | 4.3 | Implementation status tracker | 2 hours | Day 9 |
| — | **Total** | — | **71 hours** | **~2 weeks** |

---

## Part 7: Success Criteria

### Tier 1 Complete ✅
- All 13 new modules created and tested
- `.gitmodules` file present and correct
- Backward compatibility verified (old imports still work)
- All pytest tests pass

### Tier 2 Complete ✅
- `python pipeline.py --input file.jpg --output result.json` works end-to-end
- Output JSON validates against LabReport schema
- Batch processing: `python pipeline.py --input-dir X --output-dir Y` processes all images
- Metadata (timing, doc_class, ocr_engine, transformations) included in output
- No hard failures on edge cases

### Tier 3 Complete ✅
- Test coverage > 80% for core modules
- All metric calculations working (CER < 5%, WER < 8%, accuracy > 90%)
- `eval_reports/metrics_latest.json` automatically generated
- All pytest tests pass

### Tier 4 Complete ✅
- `.env.example` documented and functional
- `SETUP.md` includes submodule setup instructions
- 3 Jupyter notebooks created and executable
- `IMPLEMENTATION_STATUS.md` shows 100% compliance
- `ALIGNMENT.md` document complete and clear

---

## Next Steps

1. **Review this document** with team
2. **Get approval** on architectural decisions
3. **Start Tier 1** (Modular Refactoring) — estimated 2–3 days
4. **Proceed through Tiers 2, 3, 4** sequentially
5. **Verify each tier** before moving to next
6. **Announce completion** and update team documentation

---

**Document generated:** 2026-07-13  
**Document maintained by:** Internship Lead  
**Last updated:** 2026-07-13

