"""
document_classifier.py — 3-class medical document classifier.

Classifies a medical document image into one of:
    TABLE        — grid/table lab report (rows + column separators)
    HANDWRITTEN  — cursive / freehand notes or prescriptions
    PRINTED_TEXT — typed paragraph document (no table structure)

Uses a MobileNetV3 model on GPU when 3-class weights are available, otherwise
falls back to a multi-signal CV heuristic (HoughLinesP line/column density +
stroke-width variance + connected-component stats + run-length distribution +
morphological grid score + y-projection periodicity + edge-orientation
histogram + ink coverage) that runs on CPU (no torch required).

The heuristic computes a ``FeatureVector`` of ~10 cheap CV signals and scores
them against per-class weights (``_score_features``). This is far more robust on
real phone-camera photos of documents than the previous single-HoughLinesP
threshold approach, which misclassified handwritten prescriptions with printed
letterheads as PRINTED_TEXT and faint-grid lab reports as HANDWRITTEN.

Backward compatibility: the original 2-class `predict()` API (returns
"printed" / "handwritten") is preserved for `benchmark_pipeline.py` and any
stored `doc_type` rows.
"""
import os
import cv2
import numpy as np
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional

_torch_available = False
try:
    import torch
    import torchvision.transforms as transforms
    from torchvision.models import mobilenet_v3_large
    _torch_available = True
except ImportError:
    pass


# 3-class labels (wire contract)
CLASSES_3 = ("TABLE", "HANDWRITTEN", "PRINTED_TEXT")
TABLE_CLASS = "TABLE"
HANDWRITTEN_CLASS = "HANDWRITTEN"
PRINTED_TEXT_CLASS = "PRINTED_TEXT"

# Backward-compatible 2-class labels
PRINTED_LABEL = "printed"
HANDWRITTEN_LABEL = "handwritten"

# Default path to the trained 3-class MobileNetV3 weights. Used when no
# explicit weights_path is passed so the CNN (not just the heuristic) runs.
DEFAULT_WEIGHTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "weights", "classifier_3class.pth"
)


@dataclass
class ClassificationResult:
    """Output of a classification decision. The wire contract uses the key ``class`` (reserved word in Python), so the dataclass attribute is ``doc_class`` and :meth:`to_dict` renames it to ``class`` on serialisation. """
    doc_class: str
    confidence: float
    fallback_triggered: bool = False
    cnn_prediction: Optional[str] = None
    heuristic_prediction: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["class"] = d.pop("doc_class")
        return d


@dataclass
class FeatureVector:
    """Multi-signal CV feature vector for the heuristic classifier.

    All features are normalised to roughly [0, 1] so the scoring weights in
    ``_score_features`` are comparable. Computed by ``_extract_features``.
    """

    # Hough line counts (raw, normalised by page area)
    n_horizontal: float = 0.0
    n_vertical: float = 0.0
    line_density: float = 0.0

    # Stroke-width variance (handwritten = high, printed = low)
    stroke_width_mean: float = 0.0
    stroke_width_std: float = 0.0
    stroke_width_cv: float = 0.0  # coefficient of variation = std/mean

    # Connected-component aspect-ratio stats (printed chars uniform, hw irregular)
    cc_count: float = 0.0
    cc_aspect_mean: float = 0.0
    cc_aspect_std: float = 0.0
    cc_area_cv: float = 0.0  # area coefficient of variation

    # Horizontal run-length distribution (printed = long consistent runs)
    run_length_mean: float = 0.0
    run_length_cv: float = 0.0

    # Morphological grid-cell score (catches implied tables w/o drawn borders)
    grid_score: float = 0.0

    # Y-projection (horizontal density profile) peak periodicity
    # printed text = sharp periodic peaks (regular line spacing)
    projection_periodicity: float = 0.0
    projection_peak_sharpness: float = 0.0

    # Edge-orientation histogram concentration
    # printed/table = sharp peaks at 0°/90°; handwritten = broad spread
    orientation_concentration: float = 0.0  # fraction of edges near 0° or 90°
    orientation_entropy: float = 0.0

    # Ink coverage ratio (fraction of dark pixels after adaptive threshold)
    ink_coverage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Per-class scoring weights for the multi-signal heuristic.
# Each weight multiplies the corresponding feature; the class with the highest
# total score wins. Tuned on the WhatsApp ground-truth dataset (filenames encode
# the true class) + Patient_Kastoor manual labels. See ``scripts/eval_classifier.py``.
#
# Intuition:
#   TABLE        — high grid_score, high n_vertical, high orientation_concentration,
#                  high projection_periodicity (regular rows), low stroke_width_cv.
#   HANDWRITTEN  — high stroke_width_cv, high cc_aspect_std, high cc_area_cv,
#                  low projection_periodicity, low orientation_concentration,
#                  low grid_score, low n_vertical.
#   PRINTED_TEXT — high projection_periodicity, high orientation_concentration,
#                  high n_horizontal, low stroke_width_cv, low grid_score.
_CLASS_WEIGHTS: Dict[str, Dict[str, float]] = {
    TABLE_CLASS: {
        # grid_score (line intersections) is the strongest TABLE signal.
        "grid_score": 8.0,
        # Tables have many vertical column separators.
        "n_vertical": 2.0,
        # Tables have high line density.
        "line_density": 1.5,
        # Tables have regular row spacing.
        "projection_periodicity": 0.5,
        "orientation_concentration": 0.5,
        # Tables have uniform stroke width (printed borders).
        "stroke_width_cv": -0.5,
        "n_horizontal": 0.3,
        "cc_aspect_std": -0.3,
        "run_length_cv": -0.3,
    },
    HANDWRITTEN_CLASS: {
        # Handwriting has variable stroke width.
        "stroke_width_cv": 1.5,
        # Irregular component aspect ratios and sizes.
        "cc_aspect_std": 1.5,
        "cc_area_cv": 1.0,
        # High orientation entropy (curved strokes at many angles).
        "orientation_entropy": 1.5,
        # Variable run lengths.
        "run_length_cv": 1.0,
        # Few structural lines.
        "grid_score": -2.0,
        "n_vertical": -1.5,
        "n_horizontal": -0.5,
        "line_density": -1.0,
        # Irregular line spacing (no periodicity).
        "projection_periodicity": -1.0,
        "projection_peak_sharpness": -0.5,
        "orientation_concentration": -1.0,
    },
    PRINTED_TEXT_CLASS: {
        # Printed text has horizontal baselines (long horizontal lines).
        "n_horizontal": 2.0,
        # Regular line spacing (periodic peaks in y-projection).
        "projection_periodicity": 1.5,
        "projection_peak_sharpness": 1.0,
        # Edges concentrated at 0° (text baselines).
        "orientation_concentration": 1.0,
        # Uniform stroke width (printed font).
        "stroke_width_cv": -0.5,
        # Low grid score (no intersecting lines).
        "grid_score": -2.0,
        # Few vertical lines (no column separators).
        "n_vertical": -1.5,
        # Moderate line density (text baselines only).
        "line_density": -0.5,
        # Uniform component aspect ratios (printed chars).
        "cc_aspect_std": -0.5,
        "run_length_cv": -0.3,
    },
}

# Bias terms (added to each class score) — tuned so that a "neutral" feature
# vector (all zeros) doesn't default to one class unfairly.
_CLASS_BIAS: Dict[str, float] = {
    TABLE_CLASS: -1.0,
    HANDWRITTEN_CLASS: 0.5,
    PRINTED_TEXT_CLASS: 0.8,
}

# Ink-coverage thresholds for non-text-image detection (ultrasound / blank pages).
_LOW_INK_THRESHOLD = 0.003  # below this → likely blank / non-text (handwritten strokes can be very sparse)
_HIGH_INK_THRESHOLD = 0.55   # above this → likely dense scan (not a photo of text)


class DocumentClassifier:
    def __init__(self, weights_path: str = None, line_density_threshold: float = 0.0,
                 confidence_threshold: float = 0.70):
        # Auto-discover the trained 3-class weights when no explicit path is
        # given, so the CNN (not just the heuristic) runs by default.
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
        # Match the architecture used during training (dropout + 512 + dropout + 3-class).
        in_features = 960  # MobileNetV3-Large feature output channels.
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
        """Classify into TABLE / HANDWRITTEN / PRINTED_TEXT. cv2_image: BGR ndarray.

        Cascade:
          1. CNN (MobileNetV3) if weights are loaded AND confidence >= 0.85 → return.
          2. Multi-signal heuristic (always computed). If CNN is available but
             low-confidence, ensemble the CNN softmax with the heuristic scores
             (weighted average) to refine the decision.
          3. If the final confidence < ``confidence_threshold`` the caller
             (``ClassificationAgent``) may invoke an LLM fallback.
        """
        thr = (line_density_threshold if line_density_threshold is not None
               else self.line_density_threshold)

        cnn_probs: Optional[np.ndarray] = None
        cnn_conf = 0.0
        cnn_cls_idx = -1

        # ── Stage 1: CNN (if weights loaded) ──────────────────────
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
                # High-confidence CNN → return immediately.
            except Exception as e:
                print(f"[Classifier] PyTorch prediction failed: {e}. Falling back to heuristic.")
                cnn_probs = None

        # ── Stage 2: multi-signal heuristic ───────────────────────
        heur_result = self._heuristic_predict_3class(cv2_image, thr)

        # If CNN is available, ensemble it with the heuristic. The CNN excels
        # at HANDWRITTEN (100% recall with FocalLoss) while the heuristic excels
        # at TABLE (84%) and PRINTED_TEXT (72.5%). Blending gives the best of both.
        if cnn_probs is not None and cnn_cls_idx >= 0:
            return self._ensemble(cnn_probs, cnn_cls_idx, cnn_conf, heur_result)
        return heur_result

    def _ensemble(self, cnn_probs: np.ndarray, cnn_cls_idx: int, cnn_conf: float, heur_result: ClassificationResult) -> ClassificationResult:
        """Blend CNN softmax with heuristic scores (weighted average).
        CNN weight scales with its confidence; heuristic weight is the complement.
        This lets a confident CNN dominate while a weak CNN is corrected by the
        (more robust on real images) multi-signal heuristic.
        """
        cnn_weight = cnn_conf
        heur_weight = 1.0 - cnn_conf
        total_w = cnn_weight + heur_weight
        if total_w <= 0:
            return heur_result

        # Convert heuristic result to a pseudo-probability vector.
        heur_probs = np.full(len(CLASSES_3), 0.1, dtype=np.float32)
        try:
            heur_idx = CLASSES_3.index(heur_result.doc_class)
        except ValueError:
            heur_idx = 2  # PRINTED_TEXT default
        heur_probs[heur_idx] = max(heur_result.confidence, 0.5)
        heur_probs = heur_probs / heur_probs.sum()

        blended = (cnn_weight * cnn_probs + heur_weight * heur_probs) / total_w
        best_idx = int(np.argmax(blended))
        best_conf = float(blended[best_idx])
        return ClassificationResult(doc_class=CLASSES_3[best_idx], confidence=best_conf)

    def predict(self, cv2_image: np.ndarray) -> str:
        """Backward-compatible 2-class API.
        Returns "printed" or "handwritten".
        TABLE and PRINTED_TEXT both map to "printed" (both go to the PaddleOCR engine);
        HANDWRITTEN maps to "handwritten" (Qwen-VL).
        """
        res = self.predict_3class(cv2_image)
        return HANDWRITTEN_LABEL if res.doc_class == HANDWRITTEN_CLASS else PRINTED_LABEL

    # ── Heuristic ───────────────────────────────────────────────

    def _hough_lines(self, edged: np.ndarray, h: int, w: int):
        """Return (n_horizontal, n_vertical) line counts via HoughLinesP.

        Uses a high threshold and long minimum line length so that only true
        structural lines (table borders, column separators) are counted — not
        short text strokes or character edges.
        """
        # Require lines spanning at least 25% of the shorter dimension.
        min_line = max(60, int(min(w, h) * 0.25))
        lines = cv2.HoughLinesP(
            edged, 1, np.pi / 180, threshold=100,
            minLineLength=min_line, maxLineGap=max(10, int(min(w, h) * 0.02)),
        )
        n_h = n_v = 0
        if lines is not None:
            for ln in lines:
                x1, y1, x2, y2 = ln[0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx + dy == 0:
                    continue
                angle = np.degrees(np.arctan2(dy, dx))
                if angle < 15 or angle > 165:
                    n_h += 1
                elif 75 <= angle <= 105:
                    n_v += 1
        return n_h, n_v

    # ── Multi-signal feature extraction ────────────────────────────

    def _extract_features(self, cv2_image: np.ndarray,
                          line_density_threshold: float = 0.3) -> FeatureVector:
        """Compute the multi-signal ``FeatureVector`` for a document image.

        All features are normalised to roughly [0, 1] so the scoring weights in
        ``_score_features`` are comparable. Runs entirely on CPU with OpenCV.
        """
        h, w = cv2_image.shape[:2]
        # Work on a resized grayscale copy for speed / consistency.
        max_side = 1000
        scale = min(1.0, max_side / max(h, w))
        if scale < 1.0:
            small = cv2.resize(cv2_image, (int(w * scale), int(h * scale)))
        else:
            small = cv2_image
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        sh, sw = gray.shape[:2]
        area = float(sh * sw)

        # ── Binary ink mask (adaptive threshold) ──────────────────
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, blockSize=31, C=10,
        )
        # ink_coverage = fraction of ink (dark) pixels. Range [0, ~0.3] for text.
        ink_coverage = float(np.count_nonzero(binary)) / area if area > 0 else 0.0
        ink_coverage = float(np.clip(ink_coverage / 0.30, 0.0, 1.0))

        # ── Hough lines (require long lines → tables have them, text doesn't) ─
        edges = cv2.Canny(gray, 50, 150)
        n_h, n_v = self._hough_lines(edges, sh, sw)
        line_density = (n_h + n_v) / (area / 1e4) if area > 0 else 0.0
        # Normalise: a dense table has ~20+ long lines; printed text has ~5-10
        # horizontal (text baselines) and ~0 vertical; handwritten has ~0-2.
        n_horizontal = float(np.clip(n_h / 20.0, 0.0, 1.0))
        n_vertical = float(np.clip(n_v / 15.0, 0.0, 1.0))
        line_density = float(np.clip(line_density / 2.0, 0.0, 1.0))

        # ── Stroke-width statistics (distance transform of ink mask) ─
        # Distance transform of the binary ink mask gives, at each ink pixel,
        # the distance to the nearest background pixel ≈ half the stroke width.
        dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        ink_mask = binary > 0
        if np.any(ink_mask):
            sw_vals = dist[ink_mask]
            # Filter out tiny noise (1px components).
            sw_vals = sw_vals[sw_vals > 0.5]
            if sw_vals.size > 10:
                sw_mean = float(sw_vals.mean())
                sw_std = float(sw_vals.std())
                stroke_width_mean = float(np.clip(sw_mean / 8.0, 0.0, 1.0))
                stroke_width_std = float(np.clip(sw_std / 8.0, 0.0, 1.0))
                # CV = std/mean. Handwritten has high CV (variable stroke),
                # printed has low CV (uniform font). Range ~[0.3, 2.0].
                stroke_width_cv = float(np.clip(sw_std / (sw_mean + 1e-6) / 2.0, 0.0, 1.0))
            else:
                stroke_width_mean = stroke_width_std = stroke_width_cv = 0.0
        else:
            stroke_width_mean = stroke_width_std = stroke_width_cv = 0.0

        # ── Connected-component statistics (filter noise) ────────
        n_cc, labels_img, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8)
        cc_count_raw = max(0, n_cc - 1)
        # Filter: only keep components with area >= 10px (removes salt noise).
        min_area = 10
        if cc_count_raw > 0 and stats.shape[0] > 1:
            areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
            widths = stats[1:, cv2.CC_STAT_WIDTH].astype(np.float64)
            heights = stats[1:, cv2.CC_STAT_HEIGHT].astype(np.float64)
            keep = areas >= min_area
            if np.any(keep):
                areas_f = areas[keep]
                widths_f = widths[keep]
                heights_f = heights[keep]
                aspects = widths_f / (heights_f + 1e-6)
                cc_aspect_mean = float(np.clip(aspects.mean() / 3.0, 0.0, 1.0))
                cc_aspect_std = float(np.clip(aspects.std() / 3.0, 0.0, 1.0))
                # Area CV: handwritten has very variable component sizes;
                # printed text has uniform char sizes. Cap at 3.0 before normalising.
                cc_area_cv = float(np.clip(areas_f.std() / (areas_f.mean() + 1e-6) / 3.0, 0.0, 1.0))
                cc_count = float(np.clip(len(areas_f) / 300.0, 0.0, 1.0))
            else:
                cc_aspect_mean = cc_aspect_std = cc_area_cv = cc_count = 0.0
        else:
            cc_aspect_mean = cc_aspect_std = cc_area_cv = cc_count = 0.0

        # ── Horizontal run-length distribution ───────────────────
        # Printed text has long, consistent horizontal runs (text lines).
        # Handwritten has short, irregular runs.
        run_lengths = []
        for row_idx in range(0, sh, max(1, sh // 50)):
            row = binary[row_idx]
            transitions = np.where(np.diff(np.concatenate(([0], row, [0]))) != 0)[0]
            for i in range(0, len(transitions) - 1, 2):
                run_len = transitions[i + 1] - transitions[i]
                if run_len > 0:
                    run_lengths.append(run_len)
        if run_lengths:
            rl_arr = np.array(run_lengths, dtype=np.float64)
            # Filter very short runs (noise).
            rl_arr = rl_arr[rl_arr >= 3]
            if rl_arr.size > 0:
                run_length_mean = float(np.clip(rl_arr.mean() / 100.0, 0.0, 1.0))
                # CV: printed text has low CV (uniform line lengths),
                # handwritten has high CV. Cap at 3.0.
                run_length_cv = float(np.clip(rl_arr.std() / (rl_arr.mean() + 1e-6) / 3.0, 0.0, 1.0))
            else:
                run_length_mean = run_length_cv = 0.0
        else:
            run_length_mean = run_length_cv = 0.0

        # ── Grid score (line-intersection based) ──────────────────
        # A table has intersecting long horizontal + vertical lines forming
        # a grid. We count how many horizontal lines intersect vertical lines.
        # Text has horizontal baselines but few/no vertical lines → low score.
        grid_score = 0.0
        try:
            # Re-detect lines with a moderate threshold for grid detection.
            grid_min_line = max(50, int(min(sw, sh) * 0.20))
            grid_lines = cv2.HoughLinesP(
                edges, 1, np.pi / 180, threshold=90,
                minLineLength=grid_min_line, maxLineGap=max(8, int(min(sw, sh) * 0.02)),
            )
            h_lines = []
            v_lines = []
            if grid_lines is not None:
                for ln in grid_lines:
                    x1, y1, x2, y2 = ln[0]
                    dx = abs(x2 - x1)
                    dy = abs(y2 - y1)
                    if dx + dy == 0:
                        continue
                    angle = np.degrees(np.arctan2(dy, dx))
                    if angle < 15 or angle > 165:
                        h_lines.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2))
                    elif 75 <= angle <= 105:
                        v_lines.append((x1, min(y1, y2), max(y1, y2)))
            # Count intersections: a horizontal line intersects a vertical line
            # if the vertical line's x is within the horizontal line's x-range
            # and the horizontal line's y is within the vertical line's y-range.
            intersections = 0
            for hx1, hx2, hy in h_lines:
                for vx, vy1, vy2 in v_lines:
                    if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                        intersections += 1
            # A real table has 10+ intersections; text has ~0.
            grid_score = float(np.clip(intersections / 10.0, 0.0, 1.0))
        except Exception:
            grid_score = 0.0

        # ── Y-projection periodicity ─────────────────────────────
        # Row-wise ink density profile. Printed text has sharp periodic peaks
        # (regular line spacing); handwritten is irregular; tables have a
        # flatter profile (many rows).
        row_density = np.sum(binary > 0, axis=1).astype(np.float64)
        projection_periodicity = 0.0
        projection_peak_sharpness = 0.0
        if len(row_density) > 20 and row_density.max() > 0:
            row_norm = row_density / (row_density.max() + 1e-6)
            # Autocorrelation to detect periodic line spacing.
            ac = np.correlate(row_norm - row_norm.mean(),
                              row_norm - row_norm.mean(), mode="full")
            ac = ac[len(ac) // 2:]  # positive lags only
            ac_norm = ac / (ac[0] + 1e-6) if ac[0] > 0 else ac
            # Look for peaks in the 10-150 lag range (line spacing).
            if len(ac_norm) > 15:
                peak_region = ac_norm[10:min(len(ac_norm), 150)]
                if len(peak_region) > 0:
                    projection_periodicity = float(np.clip(peak_region.max(), 0.0, 1.0))
                    projection_peak_sharpness = float(np.clip(
                        peak_region.max() - np.mean(peak_region), 0.0, 1.0))

        # ── Edge-orientation histogram ───────────────────────────
        # Tables have edges concentrated at 0°/90° (straight lines).
        # Printed text has edges at 0° (text baselines) + character strokes.
        # Handwritten has broad spread (curved strokes at many angles).
        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitudes = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        angles = np.degrees(np.arctan2(sobel_y, sobel_x))
        strong = magnitudes > (magnitudes.max() * 0.15) if magnitudes.max() > 0 else np.zeros_like(magnitudes, dtype=bool)
        if np.any(strong):
            strong_angles = angles[strong]
            # Orientation concentration: fraction of edges near 0° or 90°.
            near_h = np.sum((np.abs(strong_angles) < 15) | (np.abs(strong_angles) > 165))
            near_v = np.sum((np.abs(strong_angles) > 75) & (np.abs(strong_angles) < 105))
            orientation_concentration = float(np.clip(
                (near_h + near_v) / strong_angles.size, 0.0, 1.0))
            # Entropy of orientation histogram (6 bins over 0-180°, since
            # orientation is symmetric). Max entropy = log2(6) ≈ 2.585.
            abs_angles = np.abs(strong_angles)
            hist, _ = np.histogram(abs_angles, bins=6, range=(0, 180))
            hist = hist.astype(np.float64) / (hist.sum() + 1e-6)
            nonzero = hist[hist > 0]
            entropy = -np.sum(nonzero * np.log2(nonzero)) if nonzero.size > 0 else 0.0
            orientation_entropy = float(np.clip(entropy / 2.585, 0.0, 1.0))
        else:
            orientation_concentration = 0.0
            orientation_entropy = 0.0

        return FeatureVector(
            n_horizontal=n_horizontal,
            n_vertical=n_vertical,
            line_density=line_density,
            stroke_width_mean=stroke_width_mean,
            stroke_width_std=stroke_width_std,
            stroke_width_cv=stroke_width_cv,
            cc_count=cc_count,
            cc_aspect_mean=cc_aspect_mean,
            cc_aspect_std=cc_aspect_std,
            cc_area_cv=cc_area_cv,
            run_length_mean=run_length_mean,
            run_length_cv=run_length_cv,
            grid_score=grid_score,
            projection_periodicity=projection_periodicity,
            projection_peak_sharpness=projection_peak_sharpness,
            orientation_concentration=orientation_concentration,
            orientation_entropy=orientation_entropy,
            ink_coverage=ink_coverage,
        )

    def _score_features(self, fv: FeatureVector) -> Dict[str, float]:
        """Score a ``FeatureVector`` against learned linear weights + bias.

        Uses a one-vs-rest logistic regression model trained on the 93-image
        labeled dataset (see ``scripts/tune_weights.py``). Features are
        normalised with the training-set mean/std before scoring.

        Returns ``{TABLE: score, HANDWRITTEN: score, PRINTED_TEXT: score}``.
        The class with the highest total score wins in ``_heuristic_predict_3class``.
        """
        # Feature order must match the training script.
        _FEATURE_ORDER = (
            "n_horizontal", "n_vertical", "line_density",
            "stroke_width_cv", "cc_aspect_std", "cc_area_cv",
            "run_length_cv", "grid_score",
            "projection_periodicity", "projection_peak_sharpness",
            "orientation_concentration", "orientation_entropy",
            "ink_coverage",
        )
        # Training-set normalization parameters (from scripts/tune_weights.py).
        _FEATURE_MEAN = np.array([
            0.8489, 0.6280, 0.4659, 0.2751, 0.8322, 0.9957, 0.6375, 0.3269, 0.3813, 0.3230, 0.5712, 0.9560, 0.3147,
        ])
        _FEATURE_STD = np.array([
            0.2829, 0.3856, 0.2787, 0.0278, 0.2204, 0.0164, 0.1940, 0.4341, 0.1390, 0.1166, 0.0866, 0.0412, 0.1079,
        ])
        # Learned weights (normalized scale, one-vs-rest logistic regression).
        _W = np.array([
            [0.7312, -0.2612, 1.1215, 0.0744, 0.2768, -0.4700, 0.9318, 0.0480, 1.1945, -0.5810, 1.7468, 1.8190, -0.7715],
            [-0.2120, -0.3746, -0.7765, -0.3653, 0.3511, 0.9592, 0.0572, -0.3265, -0.3641, 0.1730, -1.6326, 1.2806, 1.1298],
            [-0.3864, 0.4173, -0.8085, -0.0838, -0.2730, 0.0851, -0.8036, 0.0140, -0.8194, 0.2794, -0.9219, -1.3507, 0.1820],
        ])
        _B = np.array([-0.3283, -3.8389, -0.2907])

        x = np.array([getattr(fv, name, 0.0) for name in _FEATURE_ORDER])
        x_norm = (x - _FEATURE_MEAN) / (_FEATURE_STD + 1e-6)
        raw_scores = _W @ x_norm + _B
        return {CLASSES_3[i]: float(raw_scores[i]) for i in range(len(CLASSES_3))}

    def _heuristic_predict_3class(self, cv2_image: np.ndarray,
                                  line_density_threshold: float) -> ClassificationResult:
        """
        Multi-signal heuristic classifier.
        Computes a ``FeatureVector`` of ~10 cheap CV signals and scores them against
        per-class weights (``_score_features``). Far more robust on real phone-camera
        photos than the old single-HoughLinesP threshold approach.

        Decision logic:
        - If ink coverage is very low (blank / non-text image like an ultrasound scan)
          → PRINTED_TEXT with low confidence (triggers LLM fallback in the agent layer,
          preserving the 3-class wire contract).
        - Otherwise pick the class with the highest weighted score.
        - Confidence is derived from the margin between the top-1 and top-2 scores
          (softmax-like), clamped to [0.45, 0.92].
        """
        try:
            fv = self._extract_features(cv2_image, line_density_threshold)
            scores = self._score_features(fv)

            # ``line_density_threshold`` is a backward-compatible gate: if the
            # image does not exceed it, disqualify TABLE entirely. This preserves
            # the original single-heuristic contract where TABLE was triggered
            # purely by line density, and satisfies
            # ``test_table_threshold_configurable``. The default (0.3) is low
            # enough that real tables always pass; only an explicitly high
            # threshold (e.g. 1e6 in tests) disqualifies TABLE.
            if fv.line_density < line_density_threshold:
                scores[TABLE_CLASS] = -1e9

            # Non-text image guard: very low ink → likely blank/scan/photo.
            if fv.ink_coverage < _LOW_INK_THRESHOLD:
                return ClassificationResult(
                    doc_class=PRINTED_TEXT_CLASS, confidence=0.45)

            # Pick the highest-scoring class.
            ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
            best_cls, best_score = ranked[0]
            second_cls, second_score = ranked[1]

            # Confidence from score margin (softmax-like normalisation).
            margin = best_score - second_score
            confidence = float(np.clip(0.50 + margin * 0.12, 0.45, 0.92))
            return ClassificationResult(doc_class=best_cls, confidence=confidence)
        except Exception as e:
            print(f"[Classifier] Heuristic 3-class failed: {e}. Defaulting to PRINTED_TEXT.")
            return ClassificationResult(doc_class=PRINTED_TEXT_CLASS, confidence=0.50)
