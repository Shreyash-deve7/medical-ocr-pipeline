"""
image_processing.py — Preprocessing helpers for the dual-OCR pipeline.

Ported from the main project's e2e_pipeline/backend/utils/image_processing.py.
Crops/warps the document, enhances contrast (CLAHE), and normalizes DPI.
"""
import os
import io
import cv2
import numpy as np
from PIL import Image, ImageOps
from loguru import logger

try:
    from deskew import determine_skew
except Exception:  # pragma: no cover - deskew is an optional dependency
    determine_skew = None


def order_points(pts):
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1],
    ], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, M, (maxWidth, maxHeight))


def detect_and_crop_document(image):
    h, w = image.shape[:2]
    image_area = h * w
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(c) > 0.10 * image_area:
            try:
                pts = approx.reshape(4, 2)
                return four_point_transform(image, pts)
            except Exception:
                pass
    if contours and cv2.contourArea(contours[0]) > 0.15 * image_area:
        x, y, w_box, h_box = cv2.boundingRect(contours[0])
        x = max(0, x)
        y = max(0, y)
        w_box = min(w - x, w_box)
        h_box = min(h - y, h_box)
        return image[y:y + h_box, x:x + w_box]
    return image


def enhance_contrast(image):
    if len(image.shape) == 3 and image.shape[2] == 3:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(image)


def normalize_dpi(image, target_max_dim=1600):
    h, w = image.shape[:2]
    max_dim = max(h, w)
    if max_dim > target_max_dim:
        scale = target_max_dim / max_dim
        return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return image


def _opencv_skew_angle(gray):
    """Fallback skew-angle detection via HoughLines (degrees)."""
    if gray.dtype != np.uint8:
        gray = gray.astype(np.uint8)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=min(gray.shape) * 0.3, maxLineGap=10,
    )
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx, dy = x2 - x1, y2 - y1
        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            continue
        angle = np.degrees(np.arctan2(dy, dx))
        angles.append(angle)
    if not angles:
        return 0.0
    median = np.median(angles)
    # Normalise to [-45, 45] around the nearest horizontal/vertical axis
    if median > 45:
        median -= 90
    elif median < -45:
        median += 90
    return float(median)


def _rotate_image(image, angle):
    if abs(angle) < 1e-3:
        return image
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rot = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos, sin = np.abs(rot[0, 0]), np.abs(rot[0, 1])
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    rot[0, 2] += (new_w / 2) - center[0]
    rot[1, 2] += (new_h / 2) - center[1]
    return cv2.warpAffine(
        image, rot, (new_w, new_h),
        flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
    )


def deskew(image, max_angle=10.0, min_angle=-10.0):
    """Correct skew using the `deskew` library, falling back to OpenCV HoughLines.

    Returns a rotation-corrected BGR ndarray.
    """
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    angle = None
    if determine_skew is not None:
        try:
            angle = determine_skew(
                gray, min_angle=min_angle, max_angle=max_angle,
                angle_pm_90=False, sigma=3.0,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("deskew.determine_skew failed, using OpenCV fallback: {}", exc)
            angle = None

    if angle is None:
        angle = _opencv_skew_angle(gray)

    if angle is None or abs(angle) < 1e-3:
        return image
    if angle < min_angle or angle > max_angle:
        logger.debug("Skew angle {:.2f} out of range, skipping rotation", angle)
        return image
    return _rotate_image(image, float(angle))


def denoise(image, median_ksize=3, gaussian_ksize=(3, 3)):
    """Remove salt-and-pepper and low-frequency noise.

    Median filter first (kills impulse noise), then a light Gaussian blur.
    """
    if median_ksize and median_ksize % 2 == 1:
        image = cv2.medianBlur(image, median_ksize)
    if gaussian_ksize:
        image = cv2.GaussianBlur(image, gaussian_ksize, 0)
    return image


def binarise(image, block_size=11, c=2):
    """Adaptive Otsu binarisation → uint8 binary image (black text on white)."""
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    gray = cv2.medianBlur(gray, 3)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Ensure black text on white background
    if np.mean(binary) > 127:
        binary = cv2.bitwise_not(binary)
    return binary


def quality_metrics(image):
    """Compute OCR-relevant quality metrics for a BGR ndarray.

    Returns a dict with: sharpness_laplacian_var, contrast_rms,
    skew_angle_degrees, resolution_dpi (estimate), snr.
    """
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    gray = gray.astype(np.float32)

    sharpness = float(cv2.Laplacian(gray.astype(np.uint8), cv2.CV_64F).var())
    contrast = float(np.sqrt(np.mean((gray - gray.mean()) ** 2)))
    skew = _opencv_skew_angle(gray)

    h, w = gray.shape[:2]
    # Estimate DPI assuming a typical printed page width of ~8.27in (A4)
    resolution_dpi = int(round(w / 8.27)) if w > 0 else 0

    mean, std = float(gray.mean()), float(gray.std())
    snr = float(std / mean) if mean > 0 else 0.0

    return {
        "sharpness_laplacian_var": round(sharpness, 2),
        "contrast_rms": round(contrast, 2),
        "skew_angle_degrees": round(skew, 3),
        "resolution_dpi": resolution_dpi,
        "snr": round(snr, 4),
    }


def preprocess_image(image_input, target_max_dim=1600, do_deskew=True, do_denoise=True):
    """
    End-to-end preprocessing. image_input: file path, bytes, or numpy array.
    Returns a BGR ndarray (backward-compatible with existing callers).

    Pipeline: load (EXIF-aware) -> deskew -> crop -> denoise -> CLAHE -> normalize.
    """
    if isinstance(image_input, str):
        if not os.path.exists(image_input):
            raise FileNotFoundError(f"Image file not found: {image_input}")
        pil_img = ImageOps.exif_transpose(Image.open(image_input))
        image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, bytes):
        pil_img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_input)))
        image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        image = image_input.copy()
    else:
        raise ValueError("Invalid image input type. Must be file path, bytes, or numpy array.")
    if image is None:
        raise ValueError("Failed to load/decode image.")
    if do_deskew:
        image = deskew(image)
    cropped = detect_and_crop_document(image)
    if do_denoise:
        cropped = denoise(cropped)
    enhanced = enhance_contrast(cropped)
    return normalize_dpi(enhanced, target_max_dim)
