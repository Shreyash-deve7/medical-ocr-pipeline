# MedVault Hepatology OCR Pipeline — Project Goal & Architecture

This document defines the core goals, workflow requirements, routing rules, and strict environment constraints for the MedVault Hepatology OCR pipeline.

---

## 🎯 1. Core Goal
To establish a **time-efficient, accurate, and fully local** optical character recognition (OCR) and analysis pipeline. The pipeline must operate completely offline or within a localized server environment to process patient-uploaded medical lab report images, classify them dynamically, extract raw text using specialized engines, and present the raw text on the doctor's dashboard.

---

## 🔄 2. End-to-End Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    actor Doctor
    participant System as FastAPI Backend
    participant Classifier as MobileNetV3 + Heuristics
    participant Router as OCR Router (AutoOCRProvider)
    participant Qwen as Qwen2.5-VL (Local VRAM)
    participant Paddle as PaddleOCR (Local GPU)
    database DB as SQLite Database

    Patient->>System: Upload medical report image (JPEG/PNG/PDF)
    Note over System: File saved to uploads/ & default status set to 'processing'
    System-->>Patient: Upload confirmation (JSON with report_id)
    
    Note over System: Automatic OCR runs in a daemon thread
    System->>Classifier: Pass preprocessed image array
    Classifier-->>System: Return class (HANDWRITTEN / PRINTED_TEXT / TABLE)
    
    alt Class is HANDWRITTEN
        System->>Router: Route to Qwen2.5-VL
        Router->>Qwen: Extract text using 4-bit vision-language model
        Qwen-->>Router: Return extracted handwritten text
    else Class is PRINTED_TEXT or TABLE
        System->>Router: Route to PaddleOCR
        Router->>Paddle: Extract text using GPU-accelerated PaddlePaddle
        Paddle-->>Router: Return extracted printed/tabular text
    end

    Router-->>System: Return raw OCR text
    System->>DB: Update report record (status='done', ocr_text, doc_type, duration)
    
    Doctor->>System: Fetch patient details & shared reports
    System->>DB: Query reports for the patient
    DB-->>System: Return report records including ocr_text
    System-->>Doctor: Display on Doctor Dashboard (with raw OCR text)
```

1. **Patient Upload:** The patient uploads an image (or PDF) of their medical/hepatology lab report via the Patient Portal.
2. **Dashboard Receipt:** The uploaded file is stored locally, metadata is written to the SQLite database, and the report appears on the Doctor's Dashboard.
3. **Background Classification & Routing:**
   * A MobileNetV3-based CNN and heuristic ensemble classifier automatically identifies the document type.
   * **Handwritten Reports** are routed to **Qwen-2.5-VL** (local 4-bit Vision-Language Model).
   * **Printed / Tabular Reports** are routed to **PaddleOCR** (local PP-Structure & Text Recognition).
4. **Text Extraction & Delivery:**
   * The selected local engine extracts the raw OCR text.
   * The text is persisted in the SQLite database under the `ocr_text` field.
   * The doctor retrieves the patient's reports and gets immediate access to the raw OCR text.

---

## 🛠️ 3. Tech Stack & Critical Constraints

### ⚠️ Strict Python 3.12 & GPU Paddle Setup (Non-Negotiable)

To ensure the pipeline operates on local GPU hardware without encountering driver compatibility issues, the environment must be configured as follows:

* **Python Version:** **CPython 3.12.x exactly**.
  * **Why:** The specific PaddlePaddle GPU wheel configured to support the RTX 5060 (Blackwell `sm_120`) architecture on Windows is only published and compatible with CPython 3.12:
    `paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl`
  * Using any other Python version (such as 3.11, 3.13, or 3.14) will cause dependency conflicts, failed wheel installations, and block GPU access.
* **PaddlePaddle GPU Wheel:**
  * Must be installed directly from the Baidu CDN stable channel:
    `https://paddle-whl.bj.bcebos.com/stable/cu129/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl`
* **Forbidden Approaches:**
  * **DirectML** is explicitly forbidden.
  * **RapidOCR** is explicitly forbidden.
  * All downstream setups (including virtual environments, FastAPI server, Qwen-VL wrapper services, and other backend tasks) must link with and run under this Python 3.12 environment setup.

### Model Routing Details

| Document Class | Primary OCR Engine | Target Execution |
|---|---|---|
| **HANDWRITTEN** | Qwen2.5-VL | GPU (with `bitsandbytes` 4-bit quantization config) |
| **PRINTED_TEXT** | PaddleOCR | GPU (using the custom CUDA 12.9 PaddlePaddle wheel) |
| **TABLE** | PaddleOCR (PP-Structure) | GPU (using the custom CUDA 12.9 PaddlePaddle wheel) |

---

## 📂 4. Reference Implementation Files

* Centralized Pipeline Orchestrator: [pipeline.py](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/backend/pipeline.py)
* Automatic Background Task: [pipeline_service.py](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/backend/services/pipeline_service.py#L32-L76)
* Database Schema & SQLite access: [database.py](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/backend/database.py)
* Environment Installer script: [setup_env.ps1](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/setup_env.ps1)
* Setup Guide and Version Constraints: [SETUP.md](file:///C:/Users/oliad/Desktop/intern-ocr-paddleocr-aditya/pipeline_v1/SETUP.md)
