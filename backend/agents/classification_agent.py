"""
classification_agent.py — Agent 2 of the MedVault agentic pipeline.

Combines a MobileNetV3 CNN (when 3-class weights are available) with a CV
heuristic, and optionally an LLM fallback that triggers when the CNN/heuristic
confidence is below ``confidence_threshold`` (default 0.70).

Output contract:
    ClassificationResult(doc_class="TABLE"|"HANDWRITTEN"|"PRINTED_TEXT",
                         confidence, fallback_triggered)
"""
import base64
import json
import re
from typing import Optional

import numpy as np
from loguru import logger

from document_classifier import (
    DocumentClassifier,
    ClassificationResult,
    CLASSES_3,
    DEFAULT_WEIGHTS_PATH,
)


CLASSIFICATION_FALLBACK_PROMPT = """You are a medical document type classifier.

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
"""


class ClassificationAgent:
    """Agent 2 — classify a preprocessed image into one of three document types."""

    def __init__(self, weights_path: str = None, llm_fallback: bool = True,
                 confidence_threshold: float = 0.70, line_density_threshold: float = 0.3,
                 llm_client=None):
        """
        :param weights_path: optional path to 3-class MobileNetV3 weights.
            Defaults to ``DEFAULT_WEIGHTS_PATH`` (backend/weights/classifier_3class.pth)
            when available so the CNN runs by default.
        :param llm_fallback: enable LLM fallback when confidence < threshold.
        :param confidence_threshold: below this, the LLM fallback is invoked.
        :param line_density_threshold: passed to the heuristic TABLE detector.
        :param llm_client: pluggable LLM client exposing
            ``complete(prompt: str, image_b64: str) -> str``. If ``None`` the
            fallback is skipped (heuristic result returned as-is).
        """
        if weights_path is None:
            weights_path = DEFAULT_WEIGHTS_PATH
        self.cnn = DocumentClassifier(
            weights_path=weights_path,
            line_density_threshold=line_density_threshold,
            confidence_threshold=confidence_threshold,
        )
        self.llm_fallback = llm_fallback
        self.confidence_threshold = float(confidence_threshold)
        self.llm_client = llm_client

    def run(self, preprocessed_image: np.ndarray) -> ClassificationResult:
        """Classify a preprocessed (BGR) ndarray; trigger LLM fallback if unsure."""
        result = self.cnn.predict_3class(preprocessed_image)

        if result.confidence < self.confidence_threshold and self.llm_fallback:
            try:
                fb = self._llm_classify(preprocessed_image)
                if fb is not None:
                    logger.info("LLM fallback classification: {}", fb.doc_class)
                    return fb
            except Exception as e:
                logger.warning("LLM classification fallback failed: {}", e)

        return result

    def _llm_classify(self, image: np.ndarray) -> Optional[ClassificationResult]:
        if self.llm_client is None:
            return None
        b64 = _encode_image(image)
        response = self.llm_client.complete(CLASSIFICATION_FALLBACK_PROMPT, b64)
        return _parse_llm_response(response)

    @staticmethod
    def build_prompt() -> str:
        """Return the canonical LLM fallback prompt (useful for testing)."""
        return CLASSIFICATION_FALLBACK_PROMPT


def _encode_image(image: np.ndarray) -> str:
    ok, buf = cv2_imencode(image)
    if not ok:
        raise ValueError("Failed to encode image for LLM classification")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _parse_llm_response(text: str) -> ClassificationResult:
    """Parse an LLM JSON response into a ClassificationResult (fallback)."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            raise ValueError("LLM classification response contained no JSON object")
        data = json.loads(m.group(0))

    cls = data.get("predicted_class") or data.get("class")
    if cls not in CLASSES_3:
        raise ValueError(f"LLM returned invalid class: {cls!r}")
    conf = float(data.get("confidence", 0.7))
    return ClassificationResult(doc_class=cls, confidence=conf, fallback_triggered=True)


def cv2_imencode(image: np.ndarray):
    import cv2
    return cv2.imencode(".png", image)
