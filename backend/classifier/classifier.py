"""
classifier.py — 3-class medical document classifier.

Modularised from document_classifier.py. The DocumentClassifier class
preserves the original API for backward compatibility.
"""
import os
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from .heuristics import (
    compute_features,
    score_features,
    FeatureVector,
    TABLE_CLASS,
    HANDWRITTEN_CLASS,
    PRINTED_TEXT_CLASS,
)

_torch_available = False
try:
    import torch
    import torchvision.transforms as transforms
    from torchvision.models import mobilenet_v3_large
    _torch_available = True
except ImportError:
    pass


# 3-class labels (wire contract)
CLASSES_3 = (TABLE_CLASS, HANDWRITTEN_CLASS, PRINTED_TEXT_CLASS)

# Backward-compatible 2-class labels
PRINTED_LABEL = "printed"
HANDWRITTEN_LABEL = "handwritten"

# Default path to the trained 3-class MobileNetV3 weights
DEFAULT_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "weights", "classifier_3class.pth"
)


@dataclass
class ClassificationResult:
    """
    Output of a classification decision.
    The wire contract uses the key ``class`` (reserved word in Python), so the
    dataclass attribute is ``doc_class`` and :meth:`to_dict` renames it to
    ``class`` on serialisation.
    """
    doc_class: str
    confidence: float
    fallback_triggered: bool = False
    cnn_prediction: Optional[str] = None
    heuristic_prediction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["class"] = d.pop("doc_class")
        return d


class DocumentClassifier:
    def __init__(self, weights_path: str = None, line_density_threshold: float = 0.0,
                 confidence_threshold: float = 0.70):
        if weights_path is None and os.path.exists(DEFAULT_WEIGHTS_PATH):
            weights_path = DEFAULT_WEIGHTS_PATH
        self.weights_path = weights_path
        self.line_density_threshold = float(line_density_threshold)
        self.confidence_threshold = float(confidence_threshold)
        self.device = "cuda" if (_torch_available and torch.cuda.is_available()) else "cpu"
        self.model = None
        self.transform = None
        self.num_classes = 3

        if _torch_available:
            self._init_pytorch_model()
        else:
            print("[Classifier] PyTorch not available, running in heuristic fallback mode.")

    def _init_pytorch_model(self):
        self.model = mobilenet_v3_large(weights=None)
        in_features = 960
        self.model.classifier = torch.nn.Sequential(
            torch.nn.Dropout(p=0.5),
            torch.nn.Linear(in_features, 512),
            torch.nn.ReLU(inplace=True),
            torch.nn.Dropout(p=0.3),
            torch.nn.Linear(512, self.num_classes),
        )

        if self.weights_path and os.path.exists(self.weights_path):
            try:
                self.model.load_state_dict(
                    torch.load(self.weights_path, map_location=self.device))
                print(f"[Classifier] Loaded custom 3-class weights from {self.weights_path}")
            except Exception as e:
                print(f"[Classifier] Failed to load weights from {self.weights_path}: {e}. "
                      "Running untrained (heuristic).")
        else:
            print("[Classifier] No weights file found/provided. Running in heuristic/scaffold mode.")

        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    # ── Public API ──────────────────────────────────────────────

    def predict_3class(self, cv2_image: np.ndarray,
                       line_density_threshold: float = None) -> ClassificationResult:
        """
        Classify into TABLE / HANDWRITTEN / PRINTED_TEXT.

        Cascade:
          1. CNN (MobileNetV3) if weights are loaded AND confidence >= 0.85 → return.
          2. Multi-signal heuristic (always computed). If CNN is available but
             low-confidence, ensemble the CNN softmax with the heuristic scores.
          3. If the final confidence < ``confidence_threshold`` the caller
             may invoke an LLM fallback.
        """
        thr = (line_density_threshold if line_density_threshold is not None
               else self.line_density_threshold)

        cnn_probs: Optional[np.ndarray] = None
        cnn_conf = 0.0
        cnn_cls_idx = -1

        # Stage 1: CNN
        if (_torch_available and self.model is not None
                and self.weights_path and os.path.exists(self.weights_path)):
            try:
                rgb_image = cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB)
                tensor = self.transform(rgb_image).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    outputs = self.model(tensor)
                    probs = torch.softmax(outputs, 1)
                    cnn_conf, cnn_pred = torch.max(probs, 1)
                cnn_probs = probs.cpu().numpy().flatten()
                cnn_cls_idx = int(cnn_pred.item())
                cnn_conf = float(cnn_conf.item())
            except Exception as e:
                print(f"[Classifier] PyTorch prediction failed: {e}. Falling back to heuristic.")
                cnn_probs = None

        # Stage 2: multi-signal heuristic
        heur_result = self._heuristic_predict_3class(cv2_image, thr)

        # Ensemble CNN with heuristic
        if cnn_probs is not None and cnn_cls_idx >= 0:
            return self._ensemble(cnn_probs, cnn_cls_idx, cnn_conf, heur_result)
        return heur_result

    def _ensemble(self, cnn_probs: np.ndarray, cnn_cls_idx: int, cnn_conf: float,
                  heur_result: ClassificationResult) -> ClassificationResult:
        """Heuristic-dominant fusion with a confidence-gated CNN assist.

        The multi-signal heuristic is the strong leg on real phone-camera
        medical documents (it reaches ~78% accuracy on this dataset, vs the
        CNN's ~71%). The original blend weighted the CNN by *its own*
        confidence, so a merely-0.6-confident CNN could override a
        0.92-confident heuristic. Here the heuristic is weighted by *its
        own* confidence, so a confident heuristic dominates; the CNN only
        contributes when the heuristic is itself unsure. Final confidence is
        taken as the heuristic's (calibrated) confidence when it wins, so a
        high-confidence heuristic never spuriously triggers the LLM fallback.
        """
        h_cls = heur_result.doc_class
        h_conf = float(heur_result.confidence)

        # Confident heuristic -> trust it outright (the strong leg).
        if h_conf >= 0.70:
            return heur_result

        # Heuristic unsure: weight the CNN by ITS confidence, heuristic by
        # ITS (lower) confidence. This lets a confident CNN correct an
        # unsure heuristic without the inverse corruption.
        heur_weight = h_conf
        cnn_weight = (1.0 - h_conf) * cnn_conf
        total_w = heur_weight + cnn_weight
        if total_w <= 0:
            return heur_result

        heur_probs = np.full(len(CLASSES_3), 0.1, dtype=np.float32)
        try:
            heur_idx = CLASSES_3.index(h_cls)
        except ValueError:
            heur_idx = 2
        heur_probs[heur_idx] = max(h_conf, 0.5)
        heur_probs = heur_probs / heur_probs.sum()

        blended = (cnn_weight * cnn_probs + heur_weight * heur_probs) / total_w
        best_idx = int(np.argmax(blended))
        best_conf = float(blended[best_idx])
        # Floor confidence at the heuristic's so the result is never *more*
        # confident than either signal justifies.
        best_conf = min(best_conf, max(h_conf, cnn_conf))
        return ClassificationResult(doc_class=CLASSES_3[best_idx], confidence=best_conf)

    def predict(self, cv2_image: np.ndarray) -> str:
        """
        Backward-compatible 2-class API.
        Returns "printed" or "handwritten".
        """
        res = self.predict_3class(cv2_image)
        return HANDWRITTEN_LABEL if res.doc_class == HANDWRITTEN_CLASS else PRINTED_LABEL

    # ── Heuristic ───────────────────────────────────────────────

    def _heuristic_predict_3class(self, cv2_image: np.ndarray,
                                   line_density_threshold: float) -> ClassificationResult:
        """
        Multi-signal heuristic classifier.
        """
        from .heuristics import _LOW_INK_THRESHOLD

        try:
            fv = compute_features(cv2_image, line_density_threshold)
            scores = score_features(fv)

            # Configurable TABLE gate (backward-compat): an impossibly
            # high threshold disqualifies TABLE entirely.
            if fv.line_density < line_density_threshold:
                scores[TABLE_CLASS] = -1e9

            if fv.ink_coverage < _LOW_INK_THRESHOLD:
                return ClassificationResult(doc_class=PRINTED_TEXT_CLASS, confidence=0.45)

            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            best_cls, best_score = ranked[0]
            second_cls, second_score = ranked[1]

            margin = best_score - second_score
            confidence = float(np.clip(0.50 + margin * 0.12, 0.45, 0.92))
            return ClassificationResult(doc_class=best_cls, confidence=confidence)
        except Exception as e:
            print(f"[Classifier] Heuristic 3-class failed: {e}. Defaulting to PRINTED_TEXT.")
            return ClassificationResult(doc_class=PRINTED_TEXT_CLASS, confidence=0.50)

    # ── Feature API (delegates to module-level heuristics) ──────────
    # Kept as methods so scripts/tune_weights.py, scripts/diagnose_features.py
    # and tests can call ``cls._extract_features`` / ``cls._score_features``.

    def _extract_features(self, cv2_image: np.ndarray,
                        line_density_threshold: float = 0.3):
        return compute_features(cv2_image, line_density_threshold)

    def _score_features(self, fv) -> Dict[str, float]:
        return score_features(fv)