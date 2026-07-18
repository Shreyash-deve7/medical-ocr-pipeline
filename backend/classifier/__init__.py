"""
backend.classifier — Modular 3-class document classifier.

Exports:
    DocumentClassifier, ClassificationResult, FeatureVector
    DEFAULT_WEIGHTS_PATH, CLASSES_3
    TABLE_CLASS, HANDWRITTEN_CLASS, PRINTED_TEXT_CLASS
    compute_features, score_features
"""
from .classifier import (
    DocumentClassifier,
    ClassificationResult,
    DEFAULT_WEIGHTS_PATH,
    CLASSES_3,
    TABLE_CLASS,
    HANDWRITTEN_CLASS,
    PRINTED_TEXT_CLASS,
    PRINTED_LABEL,
    HANDWRITTEN_LABEL,
)
from .heuristics import (
    compute_features,
    score_features,
    FeatureVector,
    TABLE_CLASS as _HC_TABLE,
    HANDWRITTEN_CLASS as _HC_HW,
    PRINTED_TEXT_CLASS as _HC_PRINTED,
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