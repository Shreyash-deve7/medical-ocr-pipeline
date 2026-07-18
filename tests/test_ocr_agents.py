"""
tests/test_ocr_agents.py — Session 3 validation (offline / fast).

Validates the OCR router + three OCR agents:
  - OCRResult contract (4 fields, to_dict)
  - run_ocr dispatches to the correct agent per doc_class (mocked agents)
  - dispatched results have confidence > 0 and processing_time_seconds >= 0
  - TABLE path prefers PP-Structure when available, falls back otherwise
  - html_to_table parses a PP-Structure HTML fragment into a 2D list
"""
import os
import sys
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.ocr_result import OCRResult
from agents import ocr_router_agent
from agents.ocr_router_agent import run_ocr, AGENT_FACTORIES
from agents.table_ocr_agent import TableOCRAgent, _group_lines_into_rows
from backend.ocr.providers.paddle_provider import html_to_table


# ── Fixtures ─────────────────────────────────────────────────────

def _gray_image(h=80, w=120):
    return np.ones((h, w, 3), dtype=np.uint8) * 255


# ── OCRResult contract ───────────────────────────────────────────

def test_ocr_result_fields_and_to_dict():
    r = OCRResult(raw_output="hello", engine="PaddleOCR-Basic", confidence=0.9, processing_time_seconds=1.23)
    assert r.raw_output == "hello"
    assert r.engine == "PaddleOCR-Basic"
    assert r.confidence == 0.9
    assert r.processing_time_seconds == 1.23
    d = r.to_dict()
    assert set(d) == {"raw_output", "engine", "confidence", "processing_time_seconds"}
    assert d["engine"] == "PaddleOCR-Basic"
    assert d["confidence"] == 0.9
    assert d["processing_time_seconds"] == 1.23


def test_ocr_result_2d_table_output():
    table = [["Test", "Value"], ["ALT", "78"]]
    r = OCRResult(raw_output=table, engine="PaddleOCR-PP-Structure", confidence=0.95, processing_time_seconds=0.5)
    assert isinstance(r.raw_output, list)
    assert r.to_dict()["raw_output"] == table


# ── Router dispatch (mocked agents) ──────────────────────────────

class _FakeAgent:
    def __init__(self, engine_name, conf=0.9):
        self._engine = engine_name
        self._conf = conf
        self.called = False

    def run(self, image):
        self.called = True
        return OCRResult(raw_output="x", engine=self._engine, confidence=self._conf,
                         processing_time_seconds=0.01)


@pytest.fixture
def patched_factories(monkeypatch):
    records = {}

    def _make(engine_name):
        def factory():
            inst = _FakeAgent(engine_name)
            records[engine_name] = inst
            return inst
        return factory

    fakes = {
        "TABLE": _make("PaddleOCR-PP-Structure"),
        "HANDWRITTEN": _make("Qwen2.5-VL"),
        "PRINTED_TEXT": _make("PaddleOCR-Basic"),
        "printed": _make("PaddleOCR-Basic"),
        "handwritten": _make("Qwen2.5-VL"),
    }
    monkeypatch.setattr(ocr_router_agent, "AGENT_FACTORIES", fakes)
    return records


def test_router_dispatches_table(patched_factories):
    res = run_ocr(_gray_image(), "TABLE")
    assert res.engine == "PaddleOCR-PP-Structure"
    assert patched_factories["PaddleOCR-PP-Structure"].called is True


def test_router_dispatches_handwritten(patched_factories):
    res = run_ocr(_gray_image(), "HANDWRITTEN")
    assert res.engine == "Qwen2.5-VL"
    assert patched_factories["Qwen2.5-VL"].called is True


def test_router_dispatches_printed(patched_factories):
    res = run_ocr(_gray_image(), "PRINTED_TEXT")
    assert res.engine == "PaddleOCR-Basic"
    assert patched_factories["PaddleOCR-Basic"].called is True


def test_router_accepts_legacy_classes(patched_factories):
    assert run_ocr(_gray_image(), "printed").engine == "PaddleOCR-Basic"
    assert run_ocr(_gray_image(), "handwritten").engine == "Qwen2.5-VL"


def test_router_unknown_class_raises(patched_factories):
    with pytest.raises(ValueError):
        run_ocr(_gray_image(), "LETTER")


def test_dispatched_result_has_valid_metrics(patched_factories):
    for cls in ("TABLE", "HANDWRITTEN", "PRINTED_TEXT"):
        res = run_ocr(_gray_image(), cls)
        assert res.confidence > 0
        assert res.processing_time_seconds >= 0


# ── TABLE agent: PP-Structure preferred when available ──────────

class _FakePPProvider:
    def __init__(self, rows, raise_on_call=False):
        self._rows = rows
        self._raise = raise_on_call
        self.called = False

    def extract_table_pp_structure(self, filepath, filetype):
        self.called = True
        if self._raise:
            raise RuntimeError("model not ready")
        return self._rows

    def table_confidence(self, rows):
        if not rows:
            return 0.0
        total = sum(len(r) for r in rows)
        non_empty = sum(1 for r in rows for c in r if str(c).strip())
        return round(non_empty / total, 4) if total else 0.0


def test_table_agent_prefers_pp_structure():
    rows = [["Test", "Value"], ["ALT", "78"], ["AST", "65"]]
    agent = TableOCRAgent(pp_provider=_FakePPProvider(rows))
    res = agent.run(_gray_image())
    assert res.engine == "PaddleOCR-PP-Structure"
    assert res.raw_output == rows
    assert res.confidence >= 0.75


def test_table_agent_falls_back_when_pp_structure_empty(monkeypatch):
    empty_provider = _FakePPProvider([])
    # Monkeypatch the basic-OCR fallback so no real PaddleOCR runs.
    fake_lines = [
        {"text": "ALT", "confidence": 0.9, "bbox": [[10, 10], [60, 10], [60, 30], [10, 30]]},
        {"text": "78", "confidence": 0.88, "bbox": [[70, 10], [110, 10], [110, 30], [70, 30]]},
    ]
    monkeypatch.setattr(
        "backend.ocr.providers.paddle_provider.run_paddle_ocr_on_document",
        lambda *a, **k: fake_lines,
    )
    agent = TableOCRAgent(pp_provider=empty_provider)
    res = agent.run(_gray_image())
    assert res.engine == "PaddleOCR-Basic-Fallback"
    assert empty_provider.called is True
    # Two tokens on the same y -> one row of 2 cells.
    assert res.raw_output == [["ALT", "78"]]


def test_table_agent_falls_back_on_pp_structure_error(monkeypatch):
    err_provider = _FakePPProvider(None, raise_on_call=True)
    monkeypatch.setattr(
        "backend.ocr.providers.paddle_provider.run_paddle_ocr_on_document",
        lambda *a, **k: [],
    )
    agent = TableOCRAgent(pp_provider=err_provider)
    res = agent.run(_gray_image())
    assert res.engine == "PaddleOCR-Basic-Fallback"
    assert res.raw_output == []


# ── Row grouping heuristic ───────────────────────────────────────

def test_group_lines_into_rows():
    lines = [
        {"text": "A", "bbox": [[0, 10], [10, 10], [10, 20], [0, 20]]},
        {"text": "B", "bbox": [[0, 12], [10, 12], [10, 22], [0, 22]]},
        {"text": "C", "bbox": [[0, 200], [10, 200], [10, 210], [0, 210]]},
    ]
    rows = _group_lines_into_rows(lines)
    assert rows == [["A", "B"], ["C"]]


# ── html_to_table parsing ────────────────────────────────────────

def test_html_to_table_parses_fragment():
    html = (
        "<html><body><table>"
        "<tr><th>Test</th><th>Value</th></tr>"
        "<tr><td>ALT</td><td>78</td></tr>"
        "</table></body></html>"
    )
    table = html_to_table(html)
    assert table == [["Test", "Value"], ["ALT", "78"]]


def test_html_to_table_empty_on_no_table():
    assert html_to_table("<div>no table here</div>") == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
