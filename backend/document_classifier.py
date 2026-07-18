"""
document_classifier.py — Backward-compatibility re-export.

The 3-class classifier now lives in ``backend.classifier``. Import from
there directly::

    from backend.classifier import DocumentClassifier

This module only re-exports the public names so existing import paths
(``classification_agent.py``, ``ocr_service.py``, ``tune_weights.py``,
``diagnose_features.py``, the test-suite) keep working.
"""
from backend.classifier import (
    DocumentClassifier,
    ClassificationResult,
    DEFAULT_WEIGHTS_PATH,
    CLASSES_3,
    TABLE_CLASS,
    HANDWRITTEN_CLASS,
    PRINTED_TEXT_CLASS,
    PRINTED_LABEL,
    HANDWRITTEN_LABEL,
    compute_features,
    score_features,
    FeatureVector,
)

__all__ = [
    "DocumentClassifier",
    "ClassificationResult",
    "DEFAULT_WEIGHTS_PATH",
    "CLASSES_3",
    "TABLE_CLASS",
    "HANDWRITTEN_CLASS",
    "PRINTED_TEXT_CLASS",
    "PRINTED_LABEL",
    "HANDWRITTEN_LABEL",
    "compute_features",
    "score_features",
    "FeatureVector",
]
