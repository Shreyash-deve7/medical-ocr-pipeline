# PLAN_alignment_implementation.md

## SECTION A — GOAL DEFINITION

The goal of this task is to implement the architectural changes specified in the `ALIGNMENT.md` document, transitioning the existing medical OCR codebase from a monolithic structure to a highly modular, multi-tier architecture. 

**What does "done" look like?**
Success is achieved when:
1. The backend is refactored into distinct, isolated modules (`classifier`, `ocr`, `extraction`, `preprocessing`) while maintaining full backward compatibility with existing imports.
2. Git submodules are properly configured to pull in external repositories for various OCR and preprocessing stages.
3. A unified, standalone CLI (`pipeline.py`) exists at the repository root, allowing users to run the pipeline on single images or in batch mode without starting the FastAPI server.
4. Comprehensive test coverage is added, and evaluation metrics (Character Error Rate, Word Error Rate, etc.) are fully implemented using libraries like `jiwer`.
5. Documentation, environment configuration templates, and exploratory Jupyter notebooks are provided.

**What is explicitly out of scope?**
- Fully implementing the LLM integration for the extraction stage (we will strictly use the placeholder `_call_llm` structure defined in the `ALIGNMENT.md` document).
- Fixing the upstream intern repositories if they are broken or missing. We will configure the submodules with the provided URLs and handle failures gracefully.

---

## SECTION B — TECH STACK

- **Languages/Frameworks**: Python, FastAPI
- **Libraries**: `loguru` (logging), `pytest` (testing), `jiwer` (CER/WER evaluation metrics), `pydantic` (validation)
- **Tools**: Git (for submodule management)
- **Architecture**: Modular Python packages with explicit entry points and fallback routing patterns.

*Tech Decision Notes:* 
- We will use `jiwer` for calculating actual metric implementations for CER and WER, rather than just stubbing them out.
- The LLM formatting stage will use the placeholder implementation as requested.
- Submodules will point to the exact URLs in `ALIGNMENT.md`, and missing repos will be handled via graceful fallbacks in the OCR router.

---

## SECTION C — SESSION MODULARIZATION

### Session 1: Modular Refactoring
- **OBJECTIVE**: Restructure the backend codebase into distinct, logical modules.
- **SCOPE**: `backend/classifier/`, `backend/ocr/`, `backend/extraction/`, `backend/preprocessing/`, and updating old files to act as re-exports.
- **OUTPUT**: New directory structures containing `__init__.py` and modularized code (e.g., `router.py`, `formatter.py`). Old import paths (`backend.schemas`, `backend.document_classifier`) will continue to function via re-exports.
- **CONNECTS TO**: Provides the foundational architecture that Session 2 (Submodules) and Session 3 (CLI) will build upon. If backward compatibility is broken here, the existing FastAPI server will fail.
- **FAILURE SURFACE**: Breaking existing imports, cyclic imports, or losing logic during file moves.

### Session 2B: Local OCR Implementations & VRAM Management
- **OBJECTIVE**: Manually implement the OCR engine wrappers within the repository to replace external submodules, ensuring safe VRAM management.
- **SCOPE**: `backend/gpu_manager.py`, `backend/ocr/providers/`, `backend/ocr/ocr1_table.py`, `backend/ocr/ocr2_handwritten.py`, `backend/ocr/ocr3_printed.py`.
- **OUTPUT**: Eager loading restricted to PaddleOCR and Qwen-VL. New `providers/` directory with `paddle_provider.py`, `qwen_provider.py`, and `surya_provider.py` (with forced batch_size=1). Routers updated to point to these local integrations.
- **CONNECTS TO**: Replaces the Git submodule dependency from the original plan. Establishes the functional OCR pipeline needed for testing in Session 4.
- **FAILURE SURFACE**: VRAM spikes during fallback operations, or failing to load Qwen in 4-bit precision.

### Session 3: Unified Pipeline CLI
- **OBJECTIVE**: Create a top-level CLI for end-users and orchestrate the full DAG.
- **SCOPE**: `backend/pipeline.py` (orchestration), root `pipeline.py` (CLI), `backend/services/pipeline_service.py`, `backend/services/ocr_service.py`.
- **OUTPUT**: A functional `python pipeline.py` command supporting `--input`, `--output`, `--input-dir`, and `--output-dir` arguments.
- **CONNECTS TO**: Testing and benchmarking in Session 4 will invoke this unified pipeline orchestration logic.
- **FAILURE SURFACE**: Misalignment between the new `run_pipeline` orchestration and the existing FastAPI service logic.

### Session 3.5: Environment Standardization (Python 3.12 + Paddle CUDA 12.9)
- **OBJECTIVE**: Enforce a strict Python 3.12 environment using `uv` to ensure the correct Baidu PaddlePaddle CUDA 12.9 wheel is installed for RTX 5060 support.
- **SCOPE**: `setup_env.ps1` (new script), `backend/requirements.txt`.
- **OUTPUT**: An automated script that creates a Python 3.12 virtual environment and installs exactly `paddlepaddle_gpu-3.3.1-cp312-cp312-win_amd64.whl` and dependencies.
- **CONNECTS TO**: Resolves the Python 3.14.3 incompatibility blocking the OCR stage in Session 3, allowing end-to-end testing in Session 4.
- **FAILURE SURFACE**: Network issues downloading the wheel from Baidu, or missing `uv` executable.

### Session 4: Testing & Metrics
- **OBJECTIVE**: Expand test coverage and implement quantitative evaluation metrics.
- **SCOPE**: `tests/test_*.py` files, `evaluation/metrics.py`, `evaluation/benchmark.py`.
- **OUTPUT**: A comprehensive test suite passing successfully, and a script to generate `eval_reports/metrics_latest.json` with actual CER/WER metrics via `jiwer`.
- **CONNECTS TO**: Validates the reliability of the entire system for documentation in Session 5.
- **FAILURE SURFACE**: Tests failing due to mocked dependencies, or metric calculations crashing on edge-case OCR outputs.

### Session 5: Documentation & Notebooks
- **OBJECTIVE**: Finalize environment configuration, setup instructions, and exploratory notebooks.
- **SCOPE**: `.env.example`, `SETUP.md`, `notebooks/01_preprocessing_exploration.ipynb`, `notebooks/02_classifier_training.ipynb`, `notebooks/03_extraction_evaluation.ipynb`, `IMPLEMENTATION_STATUS.md`.
- **OUTPUT**: Completed documentation files and functional Jupyter notebooks demonstrating pipeline stages.
- **CONNECTS TO**: Project completion and handover.
- **FAILURE SURFACE**: Notebooks failing to execute due to missing pip dependencies in the environment.

---

## SECTION D — PROGRESS CHECKLIST

- [x] Session 1: Modular Refactoring
  - [x] Create `backend/classifier/` module and migrate logic.
  - [x] Create `backend/ocr/` module, including `router.py`, `ocr1_table.py`, `ocr2_handwritten.py`, `ocr3_printed.py`.
  - [x] Create `backend/extraction/` module, including `schema.py`, `unit_normaliser.py`, `reference_ranges.py`, and `formatter.py` (with LLM placeholder).
  - [x] Create `backend/preprocessing/` module and `pipeline.py`.
  - [x] Add backward compatibility re-exports to existing backend files.
  - [x] Verified output: Existing FastAPI server and unit tests run without import errors.
- [x] Session 2B: Local OCR Implementations
  - [x] Verify `backend/gpu_manager.py` only eager loads `PaddleOCR` and `Qwen2.5-VL`.
  - [x] Create `backend/ocr/providers/` directory.
  - [x] Move `paddle_ocr_provider.py` and `qwen_vl_provider.py` into the `providers/` directory.
  - [x] Create `backend/ocr/providers/surya_provider.py` with strict `DETECTOR_BATCH_SIZE=1` env var setup.
  - [x] Update routers (`ocr1_table.py`, `ocr2_handwritten.py`, `ocr3_printed.py`) to use the new local providers (Printed uses PaddleOCR).
  - [x] Verified output: Unit tests for new providers pass and VRAM remains stable under 6GB on startup.
- [x] Session 3: Unified Pipeline CLI
  - [x] Implement `backend/pipeline.py` (orchestrating the full DAG).
  - [x] Create root `pipeline.py` CLI script.
  - [x] Update `backend/services/pipeline_service.py` to consume the new `run_pipeline`.
  - [x] Verified output: `python pipeline.py --input <test-image> --output result.json` executes successfully.
- [x] Session 3.5: Environment Standardization
- [x] Create `setup_env.ps1` that uses `uv` to create a Python 3.12 `.venv` and install the specific Baidu paddle wheel + requirements.
- [x] Update `backend/requirements.txt` to clearly state Python 3.12 is explicitly required by the Paddle wheel.
- [x] Verified output: `.\setup_env.ps1` runs cleanly, and `pipeline.py` completes the OCR stage without OOM or compatibility errors.
- [x] Session 4: Testing & Metrics
  - [x] Write module-specific tests (`test_classifier_module.py`, `test_ocr_router.py`, etc.).
  - [x] Write end-to-end test `test_pipeline_e2e_ibm_spec.py`.
  - [x] Implement `evaluation/metrics.py` (CER, WER using jiwer, accuracy).
  - [x] Implement `evaluation/benchmark.py` to generate `eval_reports/metrics_latest.json`.
  - [x] Verified output: `pytest tests/` passes, and the metrics JSON report is correctly generated.
- [x] Session 5: Documentation & Notebooks
  - [x] Create `.env.example` and update `SETUP.md`.
  - [x] Create `notebooks/01_preprocessing_exploration.ipynb`.
  - [x] Create `notebooks/02_classifier_training.ipynb`.
  - [x] Create `notebooks/03_extraction_evaluation.ipynb`.
  - [x] Create `IMPLEMENTATION_STATUS.md` with a 100% compliance checklist.
  - [x] Verified output: Notebooks can be executed start-to-finish without errors.
