"""
heuristics.py — Multi-signal CV heuristic for document classification.

Splits out from document_classifier.py so the feature extraction and scoring
logic is independently callable and testable without loading the CNN model.

Feature engineering notes (v2):
  The original 13 features saturated (clipped to ~1.0) and failed to
  separate HANDWRITTEN from PRINTED_TEXT: stroke_width_cv, cc_area_cv and
  ink_coverage were nearly identical across classes. v2 *un-saturates* those
  normalisers and adds two discriminative signals:

    * line_straightness — how well the ink rows align to perfectly horizontal
      baselines. Printed text is typeset (high); handwriting is wavy (low).
    * ink_irregularity  — entropy of the connected-component area
      distribution. Handwriting has many irregular blob sizes (high); printed
      fonts have near-uniform glyph sizes (low).

  The logistic-regression scorer (``score_features``) is retuned on the
  corrected full dataset via ``scripts/tune_weights.py``.
"""
import cv2
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict

# Per-class labels
TABLE_CLASS = "TABLE"
HANDWRITTEN_CLASS = "HANDWRITTEN"
PRINTED_TEXT_CLASS = "PRINTED_TEXT"

# Ink-coverage thresholds for non-text-image detection (ultrasound / blank pages).
_LOW_INK_THRESHOLD = 0.003
_HIGH_INK_THRESHOLD = 0.55


@dataclass
class FeatureVector:
    """
    Multi-signal CV feature vector for the heuristic classifier.

    All features are normalised to roughly [0, 1] so the scoring weights in
    ``_score_features`` are comparable.
    """

    # Hough line counts (raw, normalised by page area)
    n_horizontal: float = 0.0
    n_vertical: float = 0.0
    line_density: float = 0.0

    # Stroke-width variance (handwritten = high, printed = low)
    stroke_width_mean: float = 0.0
    stroke_width_std: float = 0.0
    stroke_width_cv: float = 0.0

    # Connected-component aspect-ratio stats
    cc_count: float = 0.0
    cc_aspect_mean: float = 0.0
    cc_aspect_std: float = 0.0
    cc_area_cv: float = 0.0

    # Horizontal run-length distribution
    run_length_mean: float = 0.0
    run_length_cv: float = 0.0

    # Morphological grid-cell score
    grid_score: float = 0.0

    # Y-projection periodicity
    projection_periodicity: float = 0.0
    projection_peak_sharpness: float = 0.0

    # Edge-orientation histogram concentration
    orientation_concentration: float = 0.0
    orientation_entropy: float = 0.0

    # Ink coverage ratio
    ink_coverage: float = 0.0

    # v2 discriminative signals
    line_straightness: float = 0.0
    ink_irregularity: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


# ── Feature order / scoring (retuned on the corrected dataset) ──────────────

_FEATURE_ORDER = (
    "n_horizontal", "n_vertical", "line_density",
    "stroke_width_cv", "cc_aspect_std", "cc_area_cv",
    "run_length_cv", "grid_score",
    "projection_periodicity", "projection_peak_sharpness",
    "orientation_concentration", "orientation_entropy",
    "ink_coverage",
    "line_straightness", "ink_irregularity",
)

# Training-set normalisation params (recomputed together with _W/_B).
# Retuned on the corrected full dataset via scripts/tune_weights.py (v2 features).
_FEATURE_MEAN = np.array([
    0.8489, 0.6280, 0.4659, 0.1375, 0.8322, 0.9700, 0.6375, 0.3269,
    0.3813, 0.3230, 0.5712, 0.9560, 0.3147, 0.0614, 0.0452,
])
_FEATURE_STD = np.array([
    0.2829, 0.3856, 0.2787, 0.0139, 0.2204, 0.3511, 0.1940, 0.4341,
    0.1390, 0.1166, 0.0866, 0.0412, 0.1079, 0.1210, 0.0359,
])

# Learned weights (normalised scale, one-vs-rest logistic regression).
# Retuned on the corrected full dataset (v2 features, class-balanced).
_W = np.array([
    [1.0306, -1.2971, -0.2862, 0.4091, -0.5470, 2.9670, 0.3017, -0.0547,
     -0.1351, -0.1007, 1.4332, 2.3038, -0.3396, -1.9015, -1.7317],
    [-0.0207, -0.1758, -0.3101, -0.4121, 0.9729, -1.9379, 0.3464, -0.2645,
     0.7990, -0.5540, -2.2045, 2.2885, 0.5553, 1.3681, -0.7066],
    [-0.1782, 1.4324, 0.0925, 0.1271, -0.2028, -1.7582, -0.4841, 0.1910,
     -0.5671, 0.1783, -0.4736, -1.8802, -0.7340, 0.7128, 0.5442],
])
_B = np.array([-1.0179, -3.8983, -0.9564])


def _hough_lines(edged: np.ndarray, h: int, w: int):
    """Return (n_horizontal, n_vertical) line counts via HoughLinesP."""
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


def compute_features(cv2_image: np.ndarray,
                      line_density_threshold: float = 0.3) -> FeatureVector:
    """
    Compute the multi-signal ``FeatureVector`` for a document image.
    Runs entirely on CPU with OpenCV.
    """
    h, w = cv2_image.shape[:2]
    max_side = 1000
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        small = cv2.resize(cv2_image, (int(w * scale), int(h * scale)))
    else:
        small = cv2_image
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sh, sw = gray.shape[:2]
    area = float(sh * sw)

    # Binary ink mask
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=31, C=10,
    )
    ink_coverage = float(np.count_nonzero(binary)) / area if area > 0 else 0.0
    ink_coverage = float(np.clip(ink_coverage / 0.30, 0.0, 1.0))

    # Hough lines
    edges = cv2.Canny(gray, 50, 150)
    n_h, n_v = _hough_lines(edges, sh, sw)
    line_density = (n_h + n_v) / (area / 1e4) if area > 0 else 0.0
    n_horizontal = float(np.clip(n_h / 20.0, 0.0, 1.0))
    n_vertical = float(np.clip(n_v / 15.0, 0.0, 1.0))
    line_density = float(np.clip(line_density / 2.0, 0.0, 1.0))

    # Stroke-width statistics (UN-SATURATED in v2: cap raised so genuine
    # variation between printed (uniform) and handwritten (variable) shows).
    dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
    ink_mask = binary > 0
    stroke_width_mean = stroke_width_std = stroke_width_cv = 0.0
    if np.any(ink_mask):
        sw_vals = dist[ink_mask]
        sw_vals = sw_vals[sw_vals > 0.5]
        if sw_vals.size > 10:
            sw_mean = float(sw_vals.mean())
            sw_std = float(sw_vals.std())
            stroke_width_mean = float(np.clip(sw_mean / 8.0, 0.0, 1.0))
            stroke_width_std = float(np.clip(sw_std / 8.0, 0.0, 1.0))
            # v2: divide by 4 (was 2) and allow up to 1.5 so CV is not pinned.
            stroke_width_cv = float(np.clip(
                sw_std / (sw_mean + 1e-6) / 4.0, 0.0, 1.5))

    # Connected-component statistics
    n_cc, labels_img, stats, centroids = cv2.connectedComponentsWithStats(
        binary, connectivity=8)
    cc_count_raw = max(0, n_cc - 1)
    min_area = 10
    cc_aspect_mean = cc_aspect_std = cc_area_cv = cc_count = 0.0
    cc_areas = np.array([], dtype=np.float64)
    if cc_count_raw > 0 and stats.shape[0] > 1:
        areas = stats[1:, cv2.CC_STAT_AREA].astype(np.float64)
        widths = stats[1:, cv2.CC_STAT_WIDTH].astype(np.float64)
        heights = stats[1:, cv2.CC_STAT_HEIGHT].astype(np.float64)
        keep = areas >= min_area
        if np.any(keep):
            areas_f = areas[keep]
            widths_f = widths[keep]
            heights_f = heights[keep]
            cc_areas = areas_f
            aspects = widths_f / (heights_f + 1e-6)
            cc_aspect_mean = float(np.clip(aspects.mean() / 3.0, 0.0, 1.0))
            cc_aspect_std = float(np.clip(aspects.std() / 3.0, 0.0, 1.0))
            # v2: divide by 6 (was 3) so area CV is not pinned at 1.0.
            cc_area_cv = float(np.clip(
                areas_f.std() / (areas_f.mean() + 1e-6) / 6.0, 0.0, 1.5))
            cc_count = float(np.clip(len(areas_f) / 300.0, 0.0, 1.0))

    # Horizontal run-length distribution
    run_lengths = []
    for row_idx in range(0, sh, max(1, sh // 50)):
        row = binary[row_idx]
        transitions = np.where(np.diff(np.concatenate(([0], row, [0]))) != 0)[0]
        for i in range(0, len(transitions) - 1, 2):
            run_len = transitions[i + 1] - transitions[i]
            if run_len > 0:
                run_lengths.append(run_len)
    run_length_mean = run_length_cv = 0.0
    if run_lengths:
        rl_arr = np.array(run_lengths, dtype=np.float64)
        rl_arr = rl_arr[rl_arr >= 3]
        if rl_arr.size > 0:
            run_length_mean = float(np.clip(rl_arr.mean() / 100.0, 0.0, 1.0))
            run_length_cv = float(np.clip(
                rl_arr.std() / (rl_arr.mean() + 1e-6) / 3.0, 0.0, 1.0))

    # Grid score
    grid_score = 0.0
    try:
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
        intersections = 0
        for hx1, hx2, hy in h_lines:
            for vx, vy1, vy2 in v_lines:
                if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                    intersections += 1
        grid_score = float(np.clip(intersections / 10.0, 0.0, 1.0))
    except Exception:
        grid_score = 0.0

    # Y-projection periodicity + line straightness
    row_density = np.sum(binary > 0, axis=1).astype(np.float64)
    projection_periodicity = 0.0
    projection_peak_sharpness = 0.0
    line_straightness = 0.0
    if len(row_density) > 20 and row_density.max() > 0:
        # line straightness: fit each ink row's horizontal centroid and measure how
        # little it deviates from a constant (printed = tiny deviation).
        cols = np.arange(sw, dtype=np.float64)
        row_centroid = np.full(sh, np.nan)
        for y in range(sh):
            if row_density[y] > 0:
                xs = cols[binary[y] > 0]
                row_centroid[y] = xs.mean()
        valid = ~np.isnan(row_centroid)
        if valid.sum() > 5:
            rc = row_centroid[valid]
            rc_std = rc.std() / (sw + 1e-6)
            line_straightness = float(np.clip(1.0 - rc_std / 0.15, 0.0, 1.0))
        row_norm = row_density / (row_density.max() + 1e-6)
        ac = np.correlate(row_norm - row_norm.mean(),
                          row_norm - row_norm.mean(), mode="full")
        ac = ac[len(ac) // 2:]
        ac_norm = ac / (ac[0] + 1e-6) if ac[0] > 0 else ac
        if len(ac_norm) > 15:
            peak_region = ac_norm[10:min(len(ac_norm), 150)]
            if len(peak_region) > 0:
                projection_periodicity = float(np.clip(peak_region.max(), 0.0, 1.0))
                projection_peak_sharpness = float(np.clip(
                    peak_region.max() - np.mean(peak_region), 0.0, 1.0))

    # Edge-orientation histogram
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    magnitudes = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
    angles = np.degrees(np.arctan2(sobel_y, sobel_x))
    strong = magnitudes > (magnitudes.max() * 0.15) if magnitudes.max() > 0 else np.zeros_like(magnitudes, dtype=bool)
    orientation_concentration = 0.0
    orientation_entropy = 0.0
    if np.any(strong):
        strong_angles = angles[strong]
        near_h = np.sum((np.abs(strong_angles) < 15) | (np.abs(strong_angles) > 165))
        near_v = np.sum((np.abs(strong_angles) > 75) & (np.abs(strong_angles) < 105))
        orientation_concentration = float(np.clip(
            (near_h + near_v) / strong_angles.size, 0.0, 1.0))
        abs_angles = np.abs(strong_angles)
        hist, _ = np.histogram(abs_angles, bins=6, range=(0, 180))
        hist = hist.astype(np.float64) / (hist.sum() + 1e-6)
        nonzero = hist[hist > 0]
        entropy = -np.sum(nonzero * np.log2(nonzero)) if nonzero.size > 0 else 0.0
        orientation_entropy = float(np.clip(entropy / 2.585, 0.0, 1.0))
    else:
        orientation_concentration = 0.0
        orientation_entropy = 0.0

    # v2 ink irregularity: entropy of the CC area distribution (handwritten high).
    ink_irregularity = 0.0
    if cc_areas.size > 5:
        ah, _ = np.histogram(cc_areas, bins=12)
        ah = ah.astype(np.float64)
        ah = ah[ah > 0] / (ah.sum() + 1e-6)
        a_ent = -np.sum(ah * np.log2(ah))
        ink_irregularity = float(np.clip(a_ent / np.log2(12), 0.0, 1.0))

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
        line_straightness=line_straightness,
        ink_irregularity=ink_irregularity,
    )


def score_features(fv: FeatureVector) -> Dict[str, float]:
    """
    Score a ``FeatureVector`` against learned linear weights + bias.

    Returns ``{TABLE: score, HANDWRITTEN: score, PRINTED_TEXT: score}``.
    The class with the highest total score wins. Retune via
    ``scripts/tune_weights.py`` whenever compute_features changes.
    """
    x = np.array([getattr(fv, name, 0.0) for name in _FEATURE_ORDER])
    x_norm = (x - _FEATURE_MEAN) / (_FEATURE_STD + 1e-6)
    raw_scores = _W @ x_norm + _B
    CLASSES_3 = (TABLE_CLASS, HANDWRITTEN_CLASS, PRINTED_TEXT_CLASS)
    return {CLASSES_3[i]: float(raw_scores[i]) for i in range(len(CLASSES_3))}
