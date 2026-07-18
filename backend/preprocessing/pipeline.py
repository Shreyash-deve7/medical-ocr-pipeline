"""
pipeline.py — Master preprocessing pipeline.

Imports from extern/preprocessing if available; falls back to local helpers.
"""
import cv2
import numpy as np
from typing import Dict, Any

from loguru import logger


def preprocess(image_path: str) -> Dict[str, Any]:
    """
    Master preprocessing pipeline.

    Tries to import from extern/preprocessing submodule first; falls back to
    local helpers (image_processing.py) if the submodule is not available.

    Args:
        image_path: Path to the input image file.

    Returns:
        {
            "preprocessed_image": np.ndarray,
            "transformations_applied": list[str],
            "quality_metrics_before": dict,
            "quality_metrics_after": dict
        }
    """
    # Try extern/preprocessing submodule first
    try:
        from preprocessing.pipeline import preprocess as extern_preprocess
        result = extern_preprocess(image_path)
        logger.info(f"Used extern preprocessing; transformations: {result.get('transformations_applied', [])}")
        return result
    except ImportError:
        logger.warning("extern/preprocessing not available; using fallback local preprocessing")

    # Fallback: local preprocessing helpers
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    transformations = []

    # Crop document
    try:
        from backend.image_processing import detect_and_crop_document
        cropped = detect_and_crop_document(image)
        if cropped is not None and cropped.size > 0:
            image = cropped
            transformations.append("document_crop")
    except Exception as e:
        logger.warning(f"Document crop failed: {e}")

    # Enhance contrast
    try:
        from backend.image_processing import enhance_contrast
        image = enhance_contrast(image)
        transformations.append("contrast_enhancement")
    except Exception as e:
        logger.warning(f"Contrast enhancement failed: {e}")

    # Normalize DPI
    try:
        from backend.image_processing import normalize_dpi
        image = normalize_dpi(image)
        transformations.append("dpi_normalization")
    except Exception as e:
        logger.warning(f"DPI normalization failed: {e}")

    return {
        "preprocessed_image": image,
        "transformations_applied": transformations,
        "quality_metrics_before": {},
        "quality_metrics_after": {}
    }