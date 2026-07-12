# MedVault — Agentic Pipeline Enhancement Plan
> **Codebase**: `pipeline_v1` | **Goal**: Align with `pipeline_ibm.md` architecture, introduce specialised AI agents, and make the pipeline production-grade.

---

## Section A — Goal Definition

### What Is Being Built or Changed?
The current `pipeline_v1` is a working but monolithic FastAPI + SQLite backend that routes medical document images through:
- Heuristic / MobileNetV3 document classifier (printed vs handwritten)
- PaddleOCR (printed) → Qwen2.5-VL (handwritten) dual-engine OCR
- Regex heuristic structured extraction from raw OCR text
- AI summary generation (Gemini / OpenAI / Ollama)

The `pipeline_ibm.md` specification describes a **4-stage architecture** (Preprocessing → 3-class Classification → OCR Routing → LLM JSON Extraction) plus a **Diagnosis Engine** using a medical knowledge base.

**What is being built:** A structured, agent-driven, modular pipeline that:
1. Adds a 3-class classifier (TABLE / HANDWRITTEN / PRINTED_TEXT)
2. Wraps OCR output in a validated Pydantic JSON schema matching the IBM spec
3. Replaces regex heuristics with an LLM-powered extraction agent
4. Introduces specialised agents for preprocessing, classification, OCR routing, extraction, diagnosis, and evaluation
5. Adds the missing TABLE OCR path (PaddleOCR PP-Structure)
6. Trains and integrates MobileNetV3 classifier weights
7. Modularises `main.py` (currently 2,093 lines) into proper service layers

### What Does "Done" Look Like?
- Any medical document image/PDF enters the system and exits as a validated JSON object matching the `LabReport` Pydantic schema from pipeline_ibm.md Section 6.4
- Document classifier reaches ≥ 85% accuracy on TABLE / HANDWRITTEN / PRINTED_TEXT
- CER < 5%, WER < 8%, Field Extraction Accuracy > 90%
- `main.py` is split into ≤ 6 focused modules; no file > 400 lines
- All 8 agents (listed in Section E) are functional, independently testable, with documented prompts
- A `/api/pipeline/run` endpoint chains all 4 stages and returns the IBM-spec JSON
- `pytest tests/` passes with ≥ 80% coverage on backend logic

### What Is Explicitly Out of Scope?
- Replacing SQLite with PostgreSQL
- HIPAA compliance audit
- Mobile app (frontend remains React/TypeScript)
- Rewriting in a different language or framework
- Deploying to cloud (all runs locally on RTX 5060)

---

## Section B — Tech Stack

### Existing Stack
| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI + Uvicorn | Python 3.12 |
| Database | SQLite (sync `sqlite3` + `medapp.db`) | WAL mode |
| OCR — Printed | PaddleOCR 2.8.1 (CPU fallback) | GPU blocked on Windows CUDA 13.3 |
| OCR — Handwritten | Qwen2.5-VL-3B-Instruct (4-bit in-process) | GPU ✅ RTX 5060 |
| Classification | MobileNetV3 heuristic fallback | No trained weights yet |
| Image Preprocessing | OpenCV + PIL (CLAHE, crop, normalize) | `image_processing.py` |
| Structured Extraction | Regex heuristics (`heuristics.py`) | `medical_rules.json` |
| Frontend | React + TypeScript + Vite | |
| Auth | PBKDF2 password hash + JWT | |
| AI Analysis | Gemini / OpenAI / Ollama (pluggable) | |

### New Additions
| Addition | Choice | Rationale |
|---|---|---|
| LLM Extraction Agent | IBM Granite 3.3 via Ollama `granite3.1-dense:8b` | IBM spec mandates Granite; Ollama local fallback |
| Schema Validation | Pydantic v2 `LabReport` model | Already partially present |
| 3-Class Classifier | MobileNetV3-Small fine-tuned | Extend existing `document_classifier.py` |
| TABLE OCR path | PaddleOCR PP-Structure | Add to `paddle_ocr_provider.py` |
| Agent Framework | LangGraph (OSS) | Graph-based DAG orchestration |
| Unit Normalizer | Custom Python module | SI unit standardisation |
| Hepatology KB | Python dict + JSON | From IBM spec Section 7 |
| Evaluation | `jiwer` (WER/CER) + `deepeval` (LLM eval) | OSS libraries |
| Structured Logging | `loguru` | Already in requirements |
| Testing | `pytest` + `pytest-asyncio` | |

---

## Section C — Skills to Add (From Internet)

These are **open-source libraries and tools** to install and integrate for production-grade agentic coding.

---

### Skill 1 — `langgraph` (Agent Orchestration)
```bash
pip install langgraph langchain langchain-community
```
**What it gives you:** A graph-based agent framework where each pipeline stage is a **node** (Agent). Edges define conditional routing.

**Use here:**
```python
# pipeline/agent_graph.py
from langgraph.graph import StateGraph, END
from typing import TypedDict

class PipelineState(TypedDict):
    image_path: str
    preprocessed_image: bytes
    doc_class: str         # TABLE | HANDWRITTEN | PRINTED_TEXT
    ocr_raw: str | list
    extracted_json: dict
    validation_errors: list
    diagnosis: dict

graph = StateGraph(PipelineState)
graph.add_node("preprocess", preprocess_agent)
graph.add_node("classify", classify_agent)
graph.add_node("ocr_route", ocr_router_agent)
graph.add_node("extract", extraction_agent)
graph.add_node("diagnose", diagnosis_agent)
graph.add_conditional_edges("classify", route_by_doc_class, {
    "TABLE":        "ocr_route",
    "HANDWRITTEN":  "ocr_route",
    "PRINTED_TEXT": "ocr_route",
})
graph.set_entry_point("preprocess")
pipeline = graph.compile()
```
- **Docs:** https://langchain-ai.github.io/langgraph/
- **GitHub:** https://github.com/langchain-ai/langgraph

---

### Skill 2 — `jiwer` (OCR Accuracy Evaluation)
```bash
pip install jiwer
```
**What it gives you:** CER and WER computation — primary OCR quality metrics in IBM spec Section 12.1.

```python
from jiwer import wer, cer
reference = "Alanine Aminotransferase 78 U/L"
hypothesis = ocr_output_text
print(f"WER: {wer(reference, hypothesis):.2%}")
print(f"CER: {cer(reference, hypothesis):.2%}")
```
- **GitHub:** https://github.com/jitsi/jiwer

---

### Skill 3 — `deskew` (Automatic Image Deskewing)
```bash
pip install deskew
```
**What it gives you:** Detect and correct skew angle from scanned documents — mandatory preprocessing in IBM spec Section 3.

```python
from deskew import determine_skew
angle = determine_skew(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
# Apply rotation correction
```
- **GitHub:** https://github.com/sbrunner/deskew

---

### Skill 4 — `deepeval` (LLM Output Quality Evaluation)
```bash
pip install deepeval
```
**What it gives you:** Automated evaluation of LLM extraction agent output — measures faithfulness, hallucination, field completeness.

```python
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric, HallucinationMetric
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(
    input=ocr_raw_text,
    actual_output=json.dumps(extracted_fields),
    expected_output=json.dumps(ground_truth),
    context=[ocr_raw_text],
)
evaluate([test_case], [AnswerRelevancyMetric(), HallucinationMetric()])
```
- **Docs:** https://docs.deepeval.com/
- **GitHub:** https://github.com/confident-ai/deepeval

---

### Skill 5 — `paddleocr` PP-Structure (Table OCR)
```bash
pip install paddleocr  # already installed — enable PP-Structure mode
```
**What it gives you:** PaddleOCR's table recovery module — the missing TABLE path in current code.

```python
from paddleocr import PPStructure

table_engine = PPStructure(show_log=False, image_orientation=True)
result = table_engine(cv2_image)
for region in result:
    if region['type'] == 'table':
        html_table = region['res']['html']
        # Parse HTML → 2D list
```
- **Docs:** https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/README.md

---

### Skill 6 — `pydantic-settings` (Type-safe Environment Config)
```bash
pip install pydantic-settings
```
**What it gives you:** Replaces bare `os.getenv()` calls scattered throughout `main.py` with a validated `Settings` class.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "dev-secret"
    llm_api_key: str = ""
    llm_model_id: str = "granite3.1-dense:8b"
    paddle_use_gpu: bool = False
    classifier_weights: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
```
- **Docs:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/

---

### Skill 7 — `sentence-transformers` (Semantic Test Name Matching)
```bash
pip install sentence-transformers
```
**What it gives you:** Replaces `difflib.get_close_matches` in `heuristics.py` with semantic similarity — dramatically improves fuzzy matching of OCR-corrupted test names like "AIanine" → "Alanine Aminotransferase".

```python
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")
test_names = list(HEPATOLOGY_TESTS.keys())
embeddings = model.encode(test_names)

def semantic_match(ocr_text: str) -> str:
    query_emb = model.encode(ocr_text)
    scores = util.cos_sim(query_emb, embeddings)[0]
    best_idx = scores.argmax().item()
    return test_names[best_idx] if scores[best_idx] > 0.6 else None
```
- **GitHub:** https://github.com/UKPLab/sentence-transformers

---

### Skill 8 — `beautifulsoup4` (HTML Table Parsing)
```bash
pip install beautifulsoup4 lxml
```
**What it gives you:** Robust HTML table parsing for PP-Structure output conversion to 2D list.

```python
from bs4 import BeautifulSoup

def html_to_table(html: str) -> list[list[str]]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        row = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        rows.append(row)
    return rows
```

---

### Skill 9 — `loguru` (Structured Pipeline Logging)
```bash
pip install loguru  # already in requirements — ensure consistent use
```
**Enhancement:** Add structured log context for every pipeline run.

```python
from loguru import logger

with logger.contextualize(report_id=report_id, stage="classification"):
    logger.info("Predicted doc_class={doc_class}", doc_class=doc_class)
```

---

### Skill 10 — `datamodel-code-generator` (JSON Schema → TypeScript Types)
```bash
pip install datamodel-code-generator
```
**What it gives you:** Generates TypeScript types from Pydantic schemas so frontend stays in sync with backend automatically.

```bash
datamodel-codegen --input backend/schemas.py --output frontend/src/types/pipeline.ts --output-model-type typescript
```
- **GitHub:** https://github.com/koxudaxi/datamodel-code-generator

---

## Section D — Current Codebase Analysis

### Architecture Gap Map (Current vs IBM Spec)

| IBM Spec Stage | IBM Spec Component | Current State | Gap |
|---|---|---|---|
| Stage 1 | Preprocessing (deskew, CLAHE, binarise, resize) | `image_processing.py` — CLAHE ✅, crop ✅, normalize ✅ | ❌ No deskew, no noise filter, no binarisation |
| Stage 2 | 3-class classifier (TABLE/HANDWRITTEN/PRINTED_TEXT) | `document_classifier.py` — only 2 classes | ❌ Missing TABLE class, no confidence thresholding |
| Stage 3 | OCR 1 — TABLE via PaddleOCR PP-Structure | Basic PaddleOCR only | ❌ PP-Structure not enabled |
| Stage 3 | OCR 2 — Handwritten via Qwen-VL | `qwen_vl_provider.py` ✅ | ✅ Working |
| Stage 3 | OCR 3 — Printed text fallback | PaddleOCR basic text mode | ⚠️ No EasyOCR/Tesseract fallback chain |
| Stage 4 | LLM JSON Extraction with Pydantic schema | `heuristics.py` regex only | ❌ No LLM extraction agent, no LabReport schema |
| Diagnosis | Medical knowledge base + flagging | Partial HIGH/LOW via simple comparison | ❌ No formal KB, no clinical significance |
| Evaluation | CER/WER/Field Accuracy metrics | `benchmark_pipeline.py` ✅ exists | ⚠️ Not integrated into CI, no jiwer |
| API | `/pipeline/run` unified endpoint | Embedded in `analyze_report()` | ❌ No dedicated pipeline endpoint |
| Config | Centralised settings | `os.getenv()` scattered in `main.py` | ❌ No pydantic-settings |
| Modularisation | Service layers (routes/, services/, schemas/) | All 2,093 lines in `main.py` | ❌ Monolithic |

### Key Bugs / Technical Debt (from `memory.md`)

| Issue | Impact | Fix Session |
|---|---|---|
| Classifier heuristic misclassifies printed as handwritten | Routes wrong OCR engine | Session 2 |
| No MobileNetV3 weights trained | Classifier always heuristic | Session 2 |
| `µ` encoding broken in structured output | Lab values malformed | Session 4 |
| `main.py` is 2,093 lines (monolith) | Unmanageable, hard to test | Session 6 |
| No deskew in preprocessing | Skewed scans fail OCR | Session 1 |
| No TABLE class → docs go to wrong OCR | Columns merged/broken | Session 3 |
| LLM extraction missing → regex misses fields | Low field completeness | Session 4 |

---

## Section E — Agent Architecture

The pipeline is structured as **8 specialised agents**, each with a single responsibility.

### Agent Map

```
INPUT IMAGE
    │
    ▼
[1] PreprocessingAgent      ← deskew, denoise, CLAHE, binarise, quality metrics
    │
    ▼
[2] ClassificationAgent     ← MobileNetV3 + heuristic + LLM fallback
    │
    ├─── TABLE ──────────► [3a] TableOCRAgent      ← PaddleOCR PP-Structure
    ├─── HANDWRITTEN ────► [3b] HandwrittenOCRAgent ← Qwen2.5-VL-3B-4bit
    └─── PRINTED_TEXT ───► [3c] PrintedOCRAgent     ← PaddleOCR → Tesseract
                               │
                               ▼
                           [4] ExtractionAgent      ← Granite/Ollama LLM
                               │
                               ▼
                           [5] ValidationAgent      ← Pydantic LabReport
                               │
                               ▼
                           [6] DiagnosisAgent       ← Hepatology KB + LLM
                               │
                               ▼
                           [7] EvaluationAgent      ← jiwer + deepeval
                               │
                               ▼
                           [8] SummaryAgent         ← Doctor/Patient summary
                               │
                               ▼
                        VALIDATED JSON OUTPUT
```

---

### Agent 1 — PreprocessingAgent

**File:** `backend/agents/preprocessing_agent.py`

**Responsibility:** Receive raw image bytes/path, return preprocessed BGR ndarray + quality metrics.

**System Prompt (LLM self-critique mode, optional):**
```
You are an image quality auditor for medical document OCR.

Given the following quality metrics about a preprocessed medical document image:
- sharpness_laplacian_var: {sharpness}
- contrast_rms: {contrast}
- skew_angle_degrees: {skew}
- resolution_dpi: {dpi}

Determine if the image quality is ACCEPTABLE for OCR.
If NOT acceptable, list exactly which preprocessing steps failed and why.
Respond ONLY with valid JSON:
{
  "acceptable": true | false,
  "issues": ["<issue1>", "<issue2>"],
  "recommended_steps": ["deskew", "clahe", "denoise", "binarise"]
}
```

**Python Interface:**
```python
class PreprocessingAgent:
    def run(self, image_path: str) -> PreprocessingResult:
        # 1. Load image (EXIF-aware)
        # 2. Deskew (deskew library)
        # 3. Detect & crop document
        # 4. CLAHE contrast enhancement
        # 5. Denoise (Gaussian + median filter)
        # 6. Binarise (Otsu adaptive threshold)
        # 7. Normalise DPI to 300 DPI equivalent
        # 8. Compute quality metrics
        return PreprocessingResult(
            image=preprocessed_ndarray,
            quality_metrics=metrics,
            transformations_applied=["deskew", "clahe", "binarise"],
        )
```

---

### Agent 2 — ClassificationAgent

**File:** `backend/agents/classification_agent.py`

**Responsibility:** Classify preprocessed image into TABLE / HANDWRITTEN / PRINTED_TEXT with confidence score.

**System Prompt (LLM fallback when CNN confidence < 0.70):**
```
You are a medical document type classifier.

You will be shown a base64-encoded image of a medical document.
Classify it into exactly ONE of these categories:

TABLE — A printed lab report with a grid/table structure, rows for test names
        and columns for values/reference ranges.
HANDWRITTEN — A document with cursive or freehand text, such as doctor's notes
              or handwritten prescriptions.
PRINTED_TEXT — A computer-generated typed document with paragraphs, no table
               structure — e.g. radiology report, discharge summary.

Respond ONLY with valid JSON:
{
  "predicted_class": "TABLE" | "HANDWRITTEN" | "PRINTED_TEXT",
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence"
}
```

**Python Interface:**
```python
class ClassificationAgent:
    def __init__(self, weights_path: str = None, llm_fallback: bool = True):
        self.cnn = DocumentClassifier(weights_path)
        self.llm_fallback = llm_fallback

    def run(self, preprocessed_image: np.ndarray) -> ClassificationResult:
        result = self.cnn.predict_3class(preprocessed_image)
        if result.confidence < 0.70 and self.llm_fallback:
            result = self._llm_classify(preprocessed_image)
        return result
```

---

### Agent 3a — TableOCRAgent

**File:** `backend/agents/table_ocr_agent.py`

**Responsibility:** Extract 2D table structure from TABLE-class documents via PaddleOCR PP-Structure.

**System Prompt:** None (purely algorithmic).

**Python Interface:**
```python
class TableOCRAgent:
    def run(self, image: np.ndarray) -> OCRResult:
        # Primary: PaddleOCR PP-Structure
        table_result = PPStructure()(image)
        rows = html_to_table(table_result[0]['res']['html'])
        if confidence >= 0.75:
            return OCRResult(raw_output=rows, engine="PaddleOCR-PP-Structure", confidence=confidence)
        # Fallback: basic PaddleOCR + heuristic row grouping
        lines = PaddleOCRProvider().extract_text_lines(image)
        rows = group_ocr_into_lines(lines)
        return OCRResult(raw_output=rows, engine="PaddleOCR-Basic-Fallback", confidence=0.5)
```

---

### Agent 3b — HandwrittenOCRAgent

**File:** `backend/agents/handwritten_ocr_agent.py`

**Responsibility:** Transcribe handwritten medical text using Qwen2.5-VL.

**System Prompt (embedded in provider):**
```
Please transcribe all the handwritten text in this medical document.
Provide ONLY the raw transcribed text. Preserve:
- Line breaks as they appear in the document
- Numbers and units exactly as written (do not interpret µ as u)
- Medical abbreviations verbatim

Do not add greetings, explanations, or formatting markup.
If you cannot read a word, write [illegible].
If there is no handwriting, output nothing.
```

---

### Agent 3c — PrintedOCRAgent

**File:** `backend/agents/printed_ocr_agent.py`

**Responsibility:** Extract text from printed typed documents using a fallback chain.

**System Prompt:** None (algorithmic fallback chain).

**Python Interface:**
```python
class PrintedOCRAgent:
    def run(self, image: np.ndarray) -> OCRResult:
        for fn, engine_name in [
            (paddle_extract, "PaddleOCR-Basic"),
            (easyocr_extract, "EasyOCR"),
            (tesseract_extract, "Tesseract-5"),
        ]:
            try:
                text = fn(image)
                if text.strip():
                    return OCRResult(raw_output=text, engine=engine_name)
            except Exception:
                continue
        return OCRResult(raw_output="", engine="none", confidence=0.0)
```

---

### Agent 4 — ExtractionAgent

**File:** `backend/agents/extraction_agent.py`

**Responsibility:** Convert raw OCR output → validated LabReport JSON using LLM.

**System Prompt:**
```
You are a medical data extraction assistant specialised in Hepatology lab reports.

Given the raw OCR text below, extract ALL laboratory test results and return ONLY
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

RULES:
- Units: use U/L for enzymes (ALT, AST, ALP, GGT); g/dL for Hb/Albumin;
  mg/dL for Bilirubin/Creatinine; µmol/L for Ammonia; seconds for PT; INR is unitless
- If a value is absent in the text, use null. Do NOT invent values.
- CRITICAL_HIGH if value > 3× upper reference limit
- CRITICAL_LOW if value < 0.5× lower reference limit
- For TABLE input: first row is headers; subsequent rows are data
- For HANDWRITTEN/PRINTED input: parse line-by-line for test/value/unit patterns
- Output ONLY valid JSON — no markdown fences, no preamble, no explanation

RAW OCR OUTPUT:
{ocr_raw_text}
```

**Python Interface:**
```python
class ExtractionAgent:
    def __init__(self, llm_client):
        self.llm = llm_client  # GraniteClient | OllamaClient | OpenAIClient

    def run(self, ocr_result: OCRResult) -> ExtractionResult:
        formatted_input = self._format_input(ocr_result)
        raw_json_str = self.llm.complete(EXTRACTION_SYSTEM_PROMPT, formatted_input)
        lab_results = json.loads(raw_json_str)
        return ExtractionResult(lab_results=lab_results, raw_llm_output=raw_json_str)
    
    def retry(self, ocr_result, prev_result, validation_errors) -> ExtractionResult:
        # Use validation retry prompt
        ...
```

---

### Agent 5 — ValidationAgent

**File:** `backend/agents/validation_agent.py`

**Responsibility:** Validate extracted JSON against Pydantic `LabReport` schema; retry on failure.

**System Prompt (retry guidance when validation fails):**
```
The previous extraction attempt failed Pydantic validation with these errors:
{validation_errors}

The raw OCR input was:
{ocr_raw_text}

The failed JSON output was:
{failed_json}

Fix ONLY the fields listed in the validation errors. Do not change fields that were valid.
Return ONLY the corrected JSON with no preamble or markdown.
```

**Python Interface:**
```python
class ValidationAgent:
    MAX_RETRIES = 2

    def run(self, extraction_result, ocr_result, extraction_agent) -> LabReport:
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return LabReport(**extraction_result.data)
            except ValidationError as e:
                if attempt == self.MAX_RETRIES:
                    raise
                extraction_result = extraction_agent.retry(
                    ocr_result, extraction_result, e.errors()
                )
```

---

### Agent 6 — DiagnosisAgent

**File:** `backend/agents/diagnosis_agent.py`

**Responsibility:** Apply Hepatology KB rules to flag abnormal values and generate clinical pattern narratives.

**System Prompt:**
```
You are a hepatology clinical decision support assistant.

Below are validated lab results from a patient's liver function test. You have access
to AASLD reference ranges and Sherlock's Diseases of the Liver terminology.

LAB RESULTS (validated JSON):
{lab_results_json}

Your task:
1. Identify ALL abnormal values (HIGH, LOW, CRITICAL_HIGH, CRITICAL_LOW)
2. Group related abnormalities into clinical patterns (e.g., "Hepatocellular injury pattern")
3. List possible differentials based ONLY on the lab values
   (do NOT diagnose — state possibilities only)
4. Flag values requiring URGENT attention (CRITICAL range)
5. Suggest follow-up tests if patterns are ambiguous

Respond ONLY with valid JSON:
{
  "clinical_patterns": [
    {"pattern": "...", "supporting_tests": [...], "description": "..."}
  ],
  "abnormal_values": [
    {"test": "...", "value": ..., "flag": "...", "note": "..."}
  ],
  "urgent_flags": ["..."],
  "suggested_followup": ["..."],
  "summary_for_doctor": "2-3 sentence plain English summary"
}

IMPORTANT: This is a clinical DECISION SUPPORT tool only.
Do NOT make a final diagnosis. Do NOT suggest specific treatments.
```

---

### Agent 7 — EvaluationAgent

**File:** `backend/agents/evaluation_agent.py`

**Responsibility:** Compute OCR accuracy metrics and LLM extraction quality against ground truth.

**System Prompt:** None (algorithmic: jiwer + deepeval).

**Python Interface:**
```python
class EvaluationAgent:
    def run(self, ocr_output, ground_truth_text,
            extracted_json, ground_truth_json) -> EvaluationReport:
        return EvaluationReport(
            cer=cer(ground_truth_text, ocr_output),
            wer=wer(ground_truth_text, ocr_output),
            field_accuracy=self._field_accuracy(extracted_json, ground_truth_json),
            hallucination_score=self._deepeval_score(extracted_json, ground_truth_text),
        )
```

---

### Agent 8 — SummaryAgent

**File:** `backend/agents/summary_agent.py`

**Responsibility:** Generate doctor-facing or patient-facing summary from DiagnosisResult.

**System Prompt (Doctor-facing):**
```
You are assisting a licensed medical professional reviewing a patient's lab report.
Do NOT make diagnoses. Do NOT suggest treatments.

Your role:
- Summarize the key findings in 3-5 sentences
- List values outside normal reference ranges with their clinical significance
- Highlight any CRITICAL values requiring immediate attention
- Provide 3 concise discussion points for the doctor-patient conversation

Format ONLY as valid JSON — no markdown fences:
{
  "summary": "...",
  "flags": [{"field": "...", "value": ..., "normal_range": "...", "note": "..."}],
  "critical_alerts": ["..."],
  "discussion_points": ["..."]
}

MEDICAL DATA:
{diagnosis_json}
```

**System Prompt (Patient-facing, simplified):**
```
You are a friendly medical report assistant explaining lab results to a patient.
The patient has no medical background. Use plain English.
Do NOT use jargon without explaining it.
Do NOT make diagnoses or suggest treatments.
Always include: "Your doctor will review these results and discuss them with you."

MEDICAL DATA:
{diagnosis_json}

Respond in 3-4 plain sentences. No JSON. No bullet lists.
```

---

## Section F — Modularised Sessions

### Session 1: Preprocessing Pipeline Enhancement
**Objective:** Extend `image_processing.py` to match IBM spec Section 3.

**Scope:**
- `backend/image_processing.py` — add `deskew()`, `denoise()`, `binarise()`, `quality_metrics()`
- `backend/agents/preprocessing_agent.py` — new file
- `requirements.txt` — add `deskew>=1.5.0`

**Output:** `preprocess(image_path) -> PreprocessingResult` with `{preprocessed_image, transformations_applied, quality_metrics_before, quality_metrics_after}`.

**Connects To:** Session 2 (ClassificationAgent receives `preprocessed_image`). If preprocessing returns wrong dimensions, Session 2's CNN receives corrupted input.

**Failure Surface:**
- `deskew` library gives wrong angle on dark backgrounds → fallback to OpenCV HoughLines-based deskew
- CLAHE over-enhances high-contrast images → pre-check `contrast_rms` metric
- EXIF rotation not handled → already using `ImageOps.exif_transpose` ✅

---

### Session 2: 3-Class Classifier (TABLE / HANDWRITTEN / PRINTED_TEXT)
**Objective:** Upgrade from binary to 3-class classification with confidence thresholding.

**Scope:**
- `backend/document_classifier.py` — add TABLE detection via HoughLinesP line density; rename classes
- `backend/agents/classification_agent.py` — new file, CNN + heuristic + LLM fallback
- `backend/main.py` — update `AutoOCRProvider._route()` for 3-class routing
- `tests/test_classifier.py` — new test file

**Output:** `ClassificationResult(class="TABLE"|"HANDWRITTEN"|"PRINTED_TEXT", confidence, fallback_triggered)`.

**Connects To:** Session 3 (OCR routing driven by `doc_class`). Wrong classification sends documents to wrong OCR engine — all downstream extraction fails.

**Failure Surface:**
- TABLE heuristic fires on printed text with many horizontal lines → tune `line_density_threshold`; add column detection
- Confidence < 0.70 → LLM fallback adds ~2s latency → cache LLM client as singleton

---

### Session 3: TABLE OCR Path via PP-Structure + OCR Router Agent
**Objective:** Enable PaddleOCR PP-Structure for TABLE class; create unified OCR Router.

**Scope:**
- `backend/agents/table_ocr_agent.py` — new file (PP-Structure primary + basic fallback)
- `backend/agents/handwritten_ocr_agent.py` — new file (wraps `qwen_vl_provider.py`)
- `backend/agents/printed_ocr_agent.py` — new file (PaddleOCR → Tesseract chain)
- `backend/agents/ocr_router_agent.py` — new file, `run_ocr(image, doc_class) -> OCRResult`
- `backend/paddle_ocr_provider.py` — add `extract_table_pp_structure()` method

**Output:** `OCRResult(raw_output, engine, confidence, processing_time_seconds)`

**Connects To:** Session 4 (ExtractionAgent receives `OCRResult`). If `raw_output` is empty, LLM prompt produces null results.

**Failure Surface:**
- PP-Structure requires model download on first run → add `warmup()` call at lifespan startup
- HTML table parsing fragile → use `beautifulsoup4 + lxml`
- PaddleOCR GPU still blocked on Windows CUDA 13.3 → CPU mode confirmed working ✅

---

### Session 4: LLM Extraction Agent + Pydantic LabReport Schema
**Objective:** Replace `heuristics.py` regex extraction with LLM-powered `ExtractionAgent` + `ValidationAgent`.

**Scope:**
- `backend/agents/extraction_agent.py` — new file (Agent 4)
- `backend/agents/validation_agent.py` — new file (Agent 5) with 2-retry logic
- `backend/schemas.py` — new file: `LabReport`, `LabResult`, `ReferenceRange` Pydantic models
- `backend/hepatology_kb.py` — new file, reference ranges from IBM spec Section 7
- `backend/unit_normaliser.py` — new file, SI unit mapping + µ encoding fix
- `requirements.txt` — add `sentence-transformers`, `deepeval`

**Output:** `LabReport` Pydantic model instance with all fields validated.

**Connects To:** Session 5 (DiagnosisAgent receives `LabReport`). Empty `lab_results` → diagnosis produces no output.

**Failure Surface:**
- LLM returns invalid JSON → catch `json.JSONDecodeError` + retry with validation prompt
- LLM hallucinates values → add `HallucinationMetric` via `deepeval`
- Granite/Ollama not available → graceful degradation to heuristic extraction with `WARNING` flag

---

### Session 5: Diagnosis Agent + Hepatology Knowledge Base
**Objective:** Build `DiagnosisAgent` with structured Hepatology KB and LLM clinical pattern recognition.

**Scope:**
- `backend/agents/diagnosis_agent.py` — new file (Agent 6)
- `backend/hepatology_kb.py` — extend with AASLD reference ranges and clinical pattern rules
- `backend/agents/summary_agent.py` — extract and formalise existing summary logic from `main.py`

**Output:** `DiagnosisResult(clinical_patterns, abnormal_values, urgent_flags, suggested_followup, llm_narrative)`

**Connects To:** Session 6 (API layer serves `DiagnosisResult` to frontend). If `urgent_flags` not persisted to DB, doctor dashboard won't show alerts.

**Failure Surface:**
- LLM adds unsolicited diagnoses → system prompt explicitly prohibits this; add output guard regex
- Summary token cap too short for complex cases → make cap configurable via `Settings`
- KB has wrong reference ranges → all values cross-checked against IBM spec Section 7 + AASLD

---

### Session 6: Backend Modularisation (Split main.py)
**Objective:** Break `main.py` (2,093 lines) into proper service layers. Pure structural refactoring — no behaviour changes.

**Target Structure:**
```
backend/
├── main.py              ← FastAPI app, lifespan, middleware only (~150 lines)
├── config.py            ← pydantic-settings Settings class
├── database.py          ← SQLite helpers, init_db(), _migrate_reports_schema()
├── auth.py              ← JWT create/decode, _hash_pw, _verify_pw
├── schemas.py           ← Pydantic request/response models + LabReport
├── routes/
│   ├── auth_routes.py
│   ├── patient_routes.py
│   ├── doctor_routes.py
│   ├── reports_routes.py
│   └── admin_routes.py
├── services/
│   ├── ocr_service.py
│   ├── ai_service.py
│   └── pipeline_service.py
└── agents/              ← (from Sessions 1-5)
```

**Output:** All existing endpoints work identically. `pytest tests/` passes. No 500 errors.

**Connects To:** Session 7 (test suite runs against modularised code). If imports break during refactor, tests catch it immediately.

**Failure Surface:**
- Circular imports between `main.py` ↔ `database.py` ↔ `routes/` → use dependency injection pattern
- SQLite connection not shared → use `get_db()` factory pattern (already exists) ✅

---

### Session 7: Test Suite + Evaluation Pipeline
**Objective:** Write comprehensive `pytest` test suite covering all agents. Integrate `jiwer` for OCR metrics.

**Scope:**
- `tests/test_preprocessing.py` — PSNR improvement, deskew accuracy, output shape
- `tests/test_classifier.py` — 3-class accuracy ≥ 85%
- `tests/test_ocr_agents.py` — correct engine per class, confidence > 0
- `tests/test_extraction_agent.py` — Pydantic validation passes, no hallucinations
- `tests/test_pipeline_e2e.py` — full pipeline from image path → LabReport JSON
- `tests/sample_images/` — anonymised TABLE, HANDWRITTEN, PRINTED_TEXT samples (5 each)
- `backend/agents/evaluation_agent.py` — jiwer integration, `/api/pipeline/evaluate` endpoint

**Output:** `pytest tests/ -v` passes with ≥ 80% coverage.

**Connects To:** Session 8 (tests must pass before `/api/pipeline/run` goes live).

**Failure Surface:**
- No ground-truth annotations → start with `benchmark_results.json` (already exists) ✅
- `deepeval` requires OpenAI by default → configure to use local Ollama as judge

---

### Session 8: Unified `/api/pipeline/run` Endpoint + LangGraph DAG
**Objective:** Wire all 8 agents into a LangGraph DAG accessible via a single REST endpoint.

**Scope:**
- `backend/pipeline/agent_graph.py` — LangGraph `StateGraph` definition
- `backend/routes/reports_routes.py` — add `POST /api/pipeline/run` endpoint
- `backend/services/pipeline_service.py` — `run_pipeline(image_path, patient_id) -> PipelineResult`
- `frontend/src/api.ts` — add `runPipeline()` function
- `frontend/src/pages/DoctorPortal.tsx` — display full `PipelineResult`
- Structured logging: `report_id` context bound at pipeline entry

**Output:**
```json
POST /api/pipeline/run -> {
  "report_id": "...",
  "doc_class": "TABLE",
  "ocr_engine": "PaddleOCR-PP-Structure",
  "lab_report": { ...LabReport schema... },
  "diagnosis": { ...DiagnosisResult... },
  "pipeline_metadata": {
    "preprocessing_transformations": ["deskew", "clahe"],
    "processing_duration_ms": 3240,
    "schema_version": "1.0"
  }
}
```

**Connects To:** This is the terminal session. All previous sessions are prerequisites.

**Failure Surface:**
- LangGraph node timeout → set per-node timeout 8s (OCR budget) + 30s total
- State object too large → pass `image_path` (not `image_bytes`) through graph state
- Frontend TypeScript types out of sync → use `datamodel-code-generator` (Skill 10)

---

## Section G — Progress Checklist

- [ ] **Session 1: Preprocessing Pipeline Enhancement**
  - [ ] `deskew` library installed and integrated into `image_processing.py`
  - [ ] `denoise()` function added (Gaussian + median filter)
  - [ ] `binarise()` function added (Otsu adaptive threshold)
  - [ ] `quality_metrics()` returns sharpness, contrast, SNR, skew angle, DPI
  - [ ] `backend/agents/preprocessing_agent.py` created and returns `PreprocessingResult`
  - [ ] Unit test: preprocessed image has lower skew angle than input
  - [ ] Unit test: CLAHE improves `contrast_rms` by at least 10%

- [ ] **Session 2: 3-Class Classifier**
  - [ ] `document_classifier.py` updated to return TABLE / HANDWRITTEN / PRINTED_TEXT
  - [ ] HoughLinesP TABLE detection added with configurable `line_density_threshold`
  - [ ] Confidence thresholding: < 0.70 triggers LLM fallback
  - [ ] `backend/agents/classification_agent.py` created
  - [ ] `AutoOCRProvider._route()` updated for 3-class routing
  - [ ] Unit test: 3-class accuracy ≥ 85% on 15-image test set (5 per class)
  - [ ] LLM fallback prompt tested and produces valid JSON response

- [ ] **Session 3: TABLE OCR Path + OCR Router**
  - [ ] `PaddleOCRProvider.extract_table_pp_structure()` implemented
  - [ ] `backend/agents/table_ocr_agent.py` created (PP-Structure primary + fallback)
  - [ ] `backend/agents/handwritten_ocr_agent.py` created (wraps Qwen-VL)
  - [ ] `backend/agents/printed_ocr_agent.py` created (PaddleOCR → Tesseract chain)
  - [ ] `backend/agents/ocr_router_agent.py` created
  - [ ] `OCRResult` schema defined: `raw_output`, `engine`, `confidence`, `processing_time_seconds`
  - [ ] Unit test: TABLE image routes to PP-Structure engine
  - [ ] Unit test: HANDWRITTEN image routes to Qwen-VL engine

- [ ] **Session 4: LLM Extraction + Pydantic Schema**
  - [ ] `backend/schemas.py` created: `LabResult`, `ReferenceRange`, `LabReport` Pydantic models
  - [ ] `backend/hepatology_kb.py` created with all IBM spec Section 7 reference ranges
  - [ ] `backend/unit_normaliser.py` created — µ encoding fixed, SI unit mapping complete
  - [ ] `backend/agents/extraction_agent.py` created with extraction system prompt
  - [ ] `backend/agents/validation_agent.py` created with 2-retry logic
  - [ ] `sentence-transformers` integrated into test name matching
  - [ ] Unit test: extraction on known OCR text produces correct `LabReport` JSON
  - [ ] Unit test: Pydantic validation rejects malformed JSON and retries successfully
  - [ ] `deepeval` hallucination check passes on benchmark samples

- [ ] **Session 5: Diagnosis Agent + Summary Agent**
  - [ ] `backend/agents/diagnosis_agent.py` created with Hepatology KB rule engine
  - [ ] LLM diagnosis prompt verified — no diagnoses, only pattern recognition
  - [ ] `backend/agents/summary_agent.py` extracted from `main.py` and formalised
  - [ ] Doctor-facing and patient-facing prompts both implemented and tested
  - [ ] Unit test: CRITICAL_HIGH ALT (> 168 U/L = 3× upper limit) triggers `urgent_flags`
  - [ ] Unit test: DiagnosisResult JSON is valid and contains `clinical_patterns`

- [ ] **Session 6: Backend Modularisation**
  - [ ] `backend/config.py` created with `pydantic-settings` `Settings` class
  - [ ] `backend/database.py` created with `get_db()`, `init_db()`, `_migrate_reports_schema()`
  - [ ] `backend/auth.py` created with JWT and password helpers
  - [ ] `backend/routes/` directory created with 5 route files
  - [ ] `backend/services/` directory created with 3 service files
  - [ ] `backend/main.py` reduced to ≤ 200 lines
  - [ ] All existing API endpoints respond identically (no regressions)
  - [ ] `pytest tests/` passes with 0 failures after refactor

- [ ] **Session 7: Test Suite + Evaluation**
  - [ ] `tests/test_preprocessing.py` — minimum 3 tests passing
  - [ ] `tests/test_classifier.py` — 3-class accuracy ≥ 85%
  - [ ] `tests/test_ocr_agents.py` — routing tests passing
  - [ ] `tests/test_extraction_agent.py` — Pydantic validation test passing
  - [ ] `tests/test_pipeline_e2e.py` — end-to-end test passing
  - [ ] `tests/sample_images/` — 5 anonymised images per class committed
  - [ ] `jiwer` integrated: CER < 5% on benchmark samples
  - [ ] `/api/pipeline/evaluate` endpoint returns evaluation JSON
  - [ ] `pytest --cov=backend tests/` ≥ 80% coverage

- [ ] **Session 8: Unified Pipeline Endpoint + LangGraph**
  - [ ] `backend/pipeline/agent_graph.py` — LangGraph DAG compiled without errors
  - [ ] `POST /api/pipeline/run` returns full PipelineResult JSON
  - [ ] Structured logging: every pipeline run logs `report_id`, `doc_class`, `duration_ms`
  - [ ] Frontend `api.ts` `runPipeline()` function added
  - [ ] Frontend DoctorPortal displays full pipeline results (doc_class, engine, lab results, diagnosis)
  - [ ] End-to-end test: upload Patient_Kastoor image → receive validated LabReport JSON
  - [ ] Per-node timeout enforced (8s OCR, 30s total)
  - [ ] All 8 agents independently testable in isolation
  - [ ] `benchmark_pipeline.py` updated to use new pipeline endpoint

---

## Section H — Quick Install Reference

```bash
# Activate venv first
cd pipeline_v1
.venv\Scripts\activate

# New dependencies
pip install langgraph langchain langchain-community
pip install jiwer
pip install deskew
pip install deepeval
pip install sentence-transformers
pip install pydantic-settings
pip install beautifulsoup4 lxml
pip install datamodel-code-generator

# Verify existing
pip install loguru pydantic>=2.7.0 httpx pymupdf
```

---

## Section I — New Environment Variables

```bash
# Add to .env
LLM_BACKEND=ollama
LLM_API_KEY=
LLM_API_ENDPOINT=http://localhost:11434/api/generate
LLM_MODEL_ID=granite3.1-dense:8b

CLASSIFIER_WEIGHTS=backend/models/classifier_3class.pth
CLASSIFIER_CONFIDENCE_THRESHOLD=0.70

PADDLE_USE_GPU=0
PADDLE_LANG=en
QWEN_VL_SERVER_URL=

ENABLE_EVALUATION=false
PIPELINE_OCR_TIMEOUT_SEC=8
PIPELINE_TOTAL_TIMEOUT_SEC=30
```

---

*Plan v1.0 — Generated 2026-07-11 | MedVault Medical OCR Pipeline*
