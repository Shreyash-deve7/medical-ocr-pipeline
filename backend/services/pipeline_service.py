"""backend/services/pipeline_service.py — OCR orchestration + unified pipeline (Session 6/8).

Houses:

  * ``process_report_automatic`` (extracted verbatim from ``main.py``) — the
    background task kicked off after a patient upload. It orchestrates the OCR
    router (``AutoOCRProvider``) and persists text / structured results / timing
    to the DB via the shared ``get_db()`` factory.

  * ``run_pipeline`` + ``PipelineResult`` + ``PipelineGraph`` (Session 8) — the
    unified DAG entry that orchestrates the full agent chain
    (preprocess -> classify -> OCR router -> extract -> validate -> diagnose ->
    [summary] -> [evaluate]) and returns a single ``PipelineResult``.

The Session 8 orchestrator is deliberately **dependency-free** (no ``langgraph``
/ ``langchain``): ``PipelineGraph`` mirrors LangGraph's node/edge/shared-state
model with a tiny topo-order runner so it runs 100% offline (LLM-free /
network-free / GPU-free) and can be swapped for a real ``StateGraph`` later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from database import get_db, _migrate_reports_schema
from services.ocr_service import AutoOCRProvider
from loguru import logger


def process_report_automatic(report_id: str):
    """
    Auto-run the OCR router (printed->Paddle, handwritten->Qwen) for a report,
    storing text, structured results, doc_type, engine and timing in the DB.
    Designed to run as a background task right after patient upload.
    Uses the default OCR provider from the database if configured.
    """
    from datetime import datetime as _dt
    conn = get_db()
    _migrate_reports_schema(conn)  # ensure status/analyzed/etc. columns exist
    row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        conn.close()
        return
    filepath = row["filepath"]
    filetype = row["filetype"]

    ocr = AutoOCRProvider()

    started = _dt.now(timezone.utc)
    conn.execute(
        "UPDATE reports SET status='processing', ocr_started_at=? WHERE id=?",
        (started.isoformat(), report_id),
    )
    conn.commit()
    try:
        ocr_text = ocr.extract_text(filepath, filetype)
        structured = ocr.extract_structured(filepath, filetype) if hasattr(ocr, "extract_structured") else []
        completed = _dt.now(timezone.utc)
        duration = int((completed - started).total_seconds() * 1000)
        doc_type = getattr(ocr, "last_doc_type", "printed")
        ocr_engine = type(ocr).__name__
        conn.execute(
            "UPDATE reports SET ocr_text=?, structured_results=?, doc_type=?, ocr_engine=?, "
            "ocr_completed_at=?, processing_duration_ms=?, status='done', analyzed=1 WHERE id=?",
            (ocr_text, json.dumps(structured, ensure_ascii=False), doc_type,
             ocr_engine, completed.isoformat(), duration, report_id),
        )
        conn.commit()
    except Exception as e:
        conn.execute("UPDATE reports SET status='failed', error=? WHERE id=?", (str(e), report_id))
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Session 8 — unified ``run_pipeline`` DAG entry
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """
    Single structured result of the full agentic pipeline.

    Every payload field is JSON-serialisable; the large ndarray images are
    *not* stored (mirrors ``PreprocessingResult.to_dict``). ``evaluation`` and
    ``summary`` are optional and only populated when requested.
    """

    preprocessing: Dict[str, Any] = field(default_factory=dict)
    classification: Dict[str, Any] = field(default_factory=dict)
    ocr: Dict[str, Any] = field(default_factory=dict)
    lab_report: Dict[str, Any] = field(default_factory=dict)
    diagnosis: Dict[str, Any] = field(default_factory=dict)
    summary: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "preprocessing": self.preprocessing,
            "classification": self.classification,
            "ocr": self.ocr,
            "lab_report": self.lab_report,
            "diagnosis": self.diagnosis,
            "summary": self.summary,
            "evaluation": self.evaluation,
            "metadata": self.metadata,
        }


class PipelineGraph:
    """
    Minimal, dependency-free DAG runner (LangGraph-style node/edge/state model).

    Each node is a ``callable(state: dict) -> Optional[dict]``; its return value
    is merged back into the shared ``state`` dict. Edges define ordering; the
    graph is executed in topological order (Kahn's algorithm) so a node only
    runs after every node it depends on. This keeps the orchestration offline
    and trivially swappable for a real ``langgraph.StateGraph`` later.
    """

    def __init__(self) -> None:
        self._nodes: Dict[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = {}
        self._edges: List[tuple] = []
        self._inputs: List[str] = []  # nodes with no inbound edges

    def add_node(self, name: str, fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]) -> "PipelineGraph":
        self._nodes[name] = fn
        return self

    def add_edge(self, src: str, dst: str) -> "PipelineGraph":
        if src not in self._nodes or dst not in self._nodes:
            raise ValueError(f"edge references unknown node: {src} -> {dst}")
        self._edges.append((src, dst))
        return self

    def run(self, initial_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state: Dict[str, Any] = dict(initial_state or {})
        # Topological sort (Kahn's algorithm).
        from collections import deque

        indeg = {n: 0 for n in self._nodes}
        adj: Dict[str, List[str]] = {n: [] for n in self._nodes}
        for src, dst in self._edges:
            adj[src].append(dst)
            indeg[dst] += 1
        queue = deque(n for n, d in indeg.items() if d == 0)
        visited = 0
        while queue:
            name = queue.popleft()
            fn = self._nodes[name]
            try:
                update = fn(state)
            except Exception as e:  # node failure must not crash the run
                state.setdefault("errors", {})[name] = str(e)
                update = None
            if isinstance(update, dict):
                state.update(update)
            indeg[name] = -1
            visited += 1
            for nxt in adj[name]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    queue.append(nxt)
        if visited != len(self._nodes):
            state.setdefault("metadata", {})["dag_warning"] = "cycle detected; some nodes skipped"
        return state


def _build_default_graph() -> PipelineGraph:
    """Construct the canonical 6(+2 optional) stage DAG in execution order."""
    g = PipelineGraph()

    def n_preprocess(state):
        from agents.preprocessing_agent import PreprocessingAgent
        result = PreprocessingAgent().run(state["image_input"])
        state["preprocessed_image"] = result.preprocessed_image
        return {"preprocessing": result.to_dict()}

    def n_classify(state):
        from document_classifier import ClassificationResult
        from agents.classification_agent import ClassificationAgent
        cls = ClassificationAgent(llm_client=state.get("llm_client")).run(
            state["preprocessed_image"]
        )
        state["doc_class"] = cls.doc_class
        return {"classification": cls.to_dict() if hasattr(cls, "to_dict") else {
            "class": getattr(cls, "doc_class", "UNKNOWN"),
            "confidence": getattr(cls, "confidence", 0.0),
            "fallback_triggered": getattr(cls, "fallback_triggered", False),
        }}

    def n_ocr(state):
        from agents.ocr_router_agent import run_ocr
        doc_class = state.get("doc_class")
        try:
            ocr = run_ocr(state["preprocessed_image"], doc_class)
        except Exception as e:  # noqa: BLE001 - fall back to PaddleOCR on vision failure
            # Handwritten OCR (Qwen-VL) fails when the vision model is
            # misconfigured / text-only / unavailable. Re-run with PRINTED_TEXT
            # (PaddleOCR) so the pipeline still yields a usable result.
            if doc_class in ("HANDWRITTEN", "handwritten"):
                logger.warning("Handwritten OCR failed ({}); falling back to PaddleOCR", e)
                ocr = run_ocr(state["preprocessed_image"], "PRINTED_TEXT")
            else:
                raise
        state["ocr_obj"] = ocr
        return {"ocr": ocr.to_dict() if hasattr(ocr, "to_dict") else {}}

    def n_extract(state):
        from agents.extraction_agent import ExtractionAgent
        ext = ExtractionAgent(llm_client=state.get("llm_client")).run(state["ocr_obj"])
        state["extraction_obj"] = ext
        return {"extraction": ext.to_dict()}

    def n_validate(state):
        from agents.validation_agent import ValidationAgent
        from agents.extraction_agent import ExtractionAgent
        lab = ValidationAgent().run(
            state["extraction_obj"], state["ocr_obj"], ExtractionAgent(llm_client=state.get("llm_client"))
        )
        state["lab_report_obj"] = lab
        return {"lab_report": lab.model_dump()}

    def n_diagnose(state):
        from agents.diagnosis_agent import DiagnosisAgent
        dx = DiagnosisAgent(llm_client=state.get("diagnosis_client")).run(state["lab_report_obj"])
        state["diagnosis_obj"] = dx
        return {"diagnosis": dx.model_dump()}

    def n_summary(state):
        from agents.summary_agent import SummaryAgent
        summary = SummaryAgent(llm_client=state.get("llm_client")).run(
            state["diagnosis_obj"], mode="doctor"
        )
        return {"summary": summary.model_dump()}

    def n_evaluate(state):
        from agents.evaluation_agent import EvaluationAgent
        agent = EvaluationAgent()
        report = _merge_agent7_evaluation(agent)
        return {"evaluation": report.to_dict() if report is not None else None}

    g.add_node("preprocess", n_preprocess)
    g.add_node("classify", n_classify)
    g.add_node("ocr", n_ocr)
    g.add_node("extract", n_extract)
    g.add_node("validate", n_validate)
    g.add_node("diagnose", n_diagnose)
    g.add_node("summary", n_summary)
    g.add_node("evaluate", n_evaluate)

    g.add_edge("preprocess", "classify")
    g.add_edge("classify", "ocr")
    g.add_edge("ocr", "extract")
    g.add_edge("extract", "validate")
    g.add_edge("validate", "diagnose")
    g.add_edge("diagnose", "summary")
    g.add_edge("diagnose", "evaluate")
    return g


def _merge_agent7_evaluation(agent) -> Optional[Any]:
    """
    Merge Agent 7 (EvaluationAgent) results into the pipeline result.

    Agent 7 has no ground truth for an arbitrary uploaded image, so we reuse its
    existing dataset evaluation over the synthetic ``tests/sample_images``
    fixtures (the same ground truth the ``/api/pipeline/evaluate`` endpoint
    uses). Returns an ``EvaluationReport`` or ``None`` when fixtures are absent
    (so the pipeline never fails just because evaluation data is missing).
    """
    import os
    from pathlib import Path

    sample_dir = Path(__file__).resolve().parent.parent.parent / "tests" / "sample_images"
    gt_path = sample_dir / "ground_truth.json"
    if not gt_path.exists():
        return None
    try:
        gt = json.loads(gt_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    # OCR is faked by the caller (monkeypatched AGENT_FACTORIES) in tests, so
    # this stays offline / GPU-free.
    return agent.evaluate_ocr_dataset(str(sample_dir), gt)


def run_pipeline(
    image_input: Any,
    *,
    llm_client: Optional[Any] = None,
    diagnosis_client: Optional[Any] = None,
    evaluate: bool = False,
    summary: bool = False,
    use_graph: bool = True,
    graph: Optional[PipelineGraph] = None,
) -> PipelineResult:
    """
    Run the full agentic DAG over ``image_input`` and return a ``PipelineResult``.

    :param image_input: file path (str), raw image bytes, or an ``np.ndarray``.
    :param llm_client: pluggable LLM client for extraction/classification/summary.
        ``None`` → heuristic / rule-based offline path.
    :param diagnosis_client: separate LLM client for the diagnosis agent.
    :param evaluate: if True, merge Agent 7 evaluation metrics into the result.
    :param summary: if True, attach a doctor-facing structured summary.
    :param use_graph: if True, orchestrate via ``PipelineGraph``; else run the
        same stages sequentially (both paths are exercised by tests).
    :param graph: optional pre-built :class:`PipelineGraph` (e.g. for tests).
    :returns: :class:`PipelineResult` (never raises for bad image / OCR errors —
        failures are recorded under ``metadata["errors"]``).
    """
    started = datetime.now(timezone.utc)
    state: Dict[str, Any] = {
        "image_input": image_input,
        "llm_client": llm_client,
        "diagnosis_client": diagnosis_client,
    }

    if graph is None:
        graph = _build_default_graph()
        # Drop optional stages when not requested.
        if not summary:
            graph._nodes.pop("summary", None)
            graph._edges = [e for e in graph._edges if e[1] != "summary"]
        if not evaluate:
            graph._nodes.pop("evaluate", None)
            graph._edges = [e for e in graph._edges if e[1] != "evaluate"]

    if use_graph and graph is not None:
        final = graph.run(state)
    else:
        final = _run_sequential(state, summary=summary, evaluate=evaluate)

    completed = datetime.now(timezone.utc)
    metadata = final.get("metadata", {}) or {}
    metadata.update({
        "use_graph": use_graph,
        "evaluate": evaluate,
        "summary": summary,
        "duration_ms": int((completed - started).total_seconds() * 1000),
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
    })
    if "errors" in final:
        metadata["errors"] = final["errors"]

    return PipelineResult(
        preprocessing=final.get("preprocessing", {}),
        classification=final.get("classification", {}),
        ocr=final.get("ocr", {}),
        lab_report=final.get("lab_report", {}),
        diagnosis=final.get("diagnosis", {}),
        summary=final.get("summary"),
        evaluation=final.get("evaluation"),
        metadata=metadata,
    )


def _run_sequential(state: Dict[str, Any], *, summary: bool, evaluate: bool) -> Dict[str, Any]:
    """Fallback sequential runner mirroring the graph node chain."""
    from agents.preprocessing_agent import PreprocessingAgent
    from agents.classification_agent import ClassificationAgent
    from agents.ocr_router_agent import run_ocr
    from agents.extraction_agent import ExtractionAgent
    from agents.validation_agent import ValidationAgent
    from agents.diagnosis_agent import DiagnosisAgent
    from agents.summary_agent import SummaryAgent

    errors: Dict[str, Any] = {}

    try:
        pre = PreprocessingAgent().run(state["image_input"])
        state["preprocessed_image"] = pre.preprocessed_image
        preprocessing = pre.to_dict()
    except Exception as e:
        errors["preprocess"] = str(e)
        return {"metadata": {"errors": errors}}

    try:
        cls = ClassificationAgent(llm_client=state.get("llm_client")).run(state["preprocessed_image"])
        state["doc_class"] = cls.doc_class
        classification = cls.to_dict() if hasattr(cls, "to_dict") else {
            "class": getattr(cls, "doc_class", "UNKNOWN")}
    except Exception as e:
        errors["classify"] = str(e)
        return {"preprocessing": preprocessing, "metadata": {"errors": errors}}

    try:
        ocr = run_ocr(state["preprocessed_image"], state["doc_class"])
        state["ocr_obj"] = ocr
    except Exception as e:
        # Handwritten OCR (Qwen-VL) failed (text-only/misconfigured model):
        # fall back to PaddleOCR (printed path) instead of aborting the run.
        if state.get("doc_class") in ("HANDWRITTEN", "handwritten"):
            logger.warning("Handwritten OCR failed ({}); falling back to PaddleOCR", e)
            try:
                ocr = run_ocr(state["preprocessed_image"], "PRINTED_TEXT")
                state["ocr_obj"] = ocr
            except Exception as e2:
                errors["ocr"] = str(e2)
                return {"preprocessing": preprocessing, "classification": classification,
                        "metadata": {"errors": errors}}
        else:
            errors["ocr"] = str(e)
            return {"preprocessing": preprocessing, "classification": classification,
                    "metadata": {"errors": errors}}

    try:
        ext = ExtractionAgent(llm_client=state.get("llm_client")).run(state["ocr_obj"])
        state["extraction_obj"] = ext
        lab = ValidationAgent().run(ext, state["ocr_obj"],
                                    ExtractionAgent(llm_client=state.get("llm_client")))
        state["lab_report_obj"] = lab
    except Exception as e:
        errors["extract_validate"] = str(e)
        return {"preprocessing": preprocessing, "classification": classification,
                "metadata": {"errors": errors}}

    try:
        dx = DiagnosisAgent(llm_client=state.get("diagnosis_client")).run(state["lab_report_obj"])
        state["diagnosis_obj"] = dx
        diagnosis = dx.model_dump()
    except Exception as e:
        errors["diagnose"] = str(e)
        diagnosis = {}

    result: Dict[str, Any] = {
        "preprocessing": preprocessing,
        "classification": classification,
        "ocr": state.get("ocr_obj").to_dict() if state.get("ocr_obj") and hasattr(state["ocr_obj"], "to_dict") else {},
        "lab_report": state.get("lab_report_obj").model_dump() if state.get("lab_report_obj") else {},
        "diagnosis": diagnosis,
    }
    if summary:
        try:
            sm = SummaryAgent(llm_client=state.get("llm_client")).run(
                state["diagnosis_obj"], mode="doctor")
            result["summary"] = sm.model_dump()
        except Exception as e:
            errors["summary"] = str(e)
    if evaluate:
        try:
            from agents.evaluation_agent import EvaluationAgent
            report = _merge_agent7_evaluation(EvaluationAgent())
            result["evaluation"] = report.to_dict() if report is not None else None
        except Exception as e:
            errors["evaluate"] = str(e)
    result["metadata"] = {"errors": errors} if errors else {}
    return result
