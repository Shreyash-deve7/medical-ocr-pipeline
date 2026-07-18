# PLAN: Create `goal.md` for Hepatology OCR Pipeline

---

## SECTION A — GOAL DEFINITION

### 1. What is being built or changed?
We are creating a new markdown document `goal.md` at the project root (`C:\Users\oliad\Desktop\intern-ocr-paddleocr-aditya\pipeline_v1\goal.md`). This file defines the core goals, end-to-end user workflows, system architecture, routing decisions (handwritten vs printed/tabular), and the critical environment/compilation constraints of the Hepatology OCR pipeline.

### 2. What does "done" look like?
A complete, well-structured `goal.md` file exists at the project root which:
- Outlines the main objective: having a time-efficient and accurate local pipeline.
- Explains the upload and doctor dashboard workflow (patient uploads → doctor dashboard → doctor views/receives → automatic classifier routing → OCR generation → raw OCR text delivery).
- Explains the routing logic: 
  - `HANDWRITTEN` reports are routed to **Qwen-2.5-VL**.
  - `PRINTED_TEXT` and `TABLE` reports are routed to **PaddleOCR**.
- Details the environment setup constraints:
  - Enforces Python 3.12 (strictly required due to Windows CPython 3.12 compatibility for the GPU-compiled `paddlepaddle_gpu-3.3.1-cp312` Baidu CDN wheel).
  - Explicitly states that DirectML and RapidOCR approaches are prohibited/out-of-scope.
  - Ensures all other parts of the setup link cleanly with this specific Python version.

### 3. What is explicitly out of scope?
- Making code modifications to the frontend or backend repositories.
- Installing, compiling, or modifying PaddlePaddle wheel packages or setting up the local environment.
- Modifying SQLite database files or schemas.
- Modifying actual Python files (`pipeline.py`, `backend/routes/*.py`).

---

## SECTION B — TECH STACK

- **Languages:** Python 3.12 (strictly required for GPU PaddlePaddle), Markdown.
- **Frameworks & Libraries:** PaddlePaddle (GPU 3.3.1 custom wheel for CUDA 12.x), Qwen2.5-VL (local Vision-Language model via llama.cpp or transformers), FastAPI backend, React/TypeScript frontend.
- **Touched Files:** Only `goal.md` at the root will be created.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Create `goal.md` in root
- **Objective:** Write and verify the `goal.md` file based on codebase specs and user guidelines.
- **Scope:** Root directory (`goal.md`).
- **Output:** `goal.md` file.
- **Connects to:** This is a documentation-only task and does not feed into subsequent active coding sessions.
- **Failure Surface:** 
  - Missing details about the Python 3.12 Paddle GPU wheel constraints.
  - Incorrectly documenting the routing logic (e.g. routing handwritten to Paddle or tables to Qwen).

---

## SECTION D — PROGRESS CHECKLIST

- [x] Session 1: Create `goal.md`
  - [x] Write `goal.md` with complete and accurate project constraints, routing rules, and user workflow.
  - [x] Verify `goal.md` is present at the root and formatted correctly.

