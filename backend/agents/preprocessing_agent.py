"""
preprocessing_agent.py — Agent 1 of the MedVault agentic pipeline.

Wraps the image_processing helpers into a single PreprocessingAgent that loads a
raw medical-document image, applies a deterministic preprocessing chain
(deskew -> crop -> denoise -> CLAHE -> normalize), and returns a structured
PreprocessingResult containing the transformed image plus quality metrics
captured before/after so downstream stages (and evaluation) can measure impact.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Union

import numpy as np
from loguru import logger

from image_processing import (
    deskew,
    denoise,
    enhance_contrast,
    detect_and_crop_document,
    normalize_dpi,
    quality_metrics,
    preprocess_image,
)


@dataclass
class PreprocessingResult:
    """Output of the PreprocessingAgent."""
    preprocessed_image: np.ndarray
    transformations_applied: List[str] = field(default_factory=list)
    quality_metrics_before: Dict[str, Any] = field(default_factory=dict)
    quality_metrics_after: Dict[str, Any] = field(default_factory=dict)
    image_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for logging/JSON (image excluded to keep it light)."""
        d = asdict(self)
        d.pop("preprocessed_image", None)
        return d


class PreprocessingAgent:
    """Agent 1 — receive a raw image, return a preprocessed BGR ndarray + metrics."""

    def __init__(self, target_max_dim: int = 1600, do_deskew: bool = True,
                 do_denoise: bool = True):
        self.target_max_dim = target_max_dim
        self.do_deskew = do_deskew
        self.do_denoise = do_denoise

    def run(self, image_input: Union[str, bytes, np.ndarray]) -> PreprocessingResult:
        image_path = image_input if isinstance(image_input, str) else ""

        # Load + capture baseline metrics
        raw = self._load(image_input)
        metrics_before = quality_metrics(raw)

        transformations: List[str] = []
        image = raw

        if self.do_deskew:
            deskewed = deskew(image)
            if not np.array_equal(deskewed, image):
                transformations.append("deskew")
            image = deskewed

        cropped = detect_and_crop_document(image)
        if not np.array_equal(cropped, image):
            transformations.append("crop")
        image = cropped

        if self.do_denoise:
            image = denoise(image)
            transformations.append("denoise")

        enhanced = enhance_contrast(image)
        transformations.append("clahe")
        image = enhanced

        image = normalize_dpi(image, self.target_max_dim)
        transformations.append("normalize_dpi")

        metrics_after = quality_metrics(image)

        result = PreprocessingResult(
            preprocessed_image=image,
            transformations_applied=transformations,
            quality_metrics_before=metrics_before,
            quality_metrics_after=metrics_after,
            image_path=image_path,
        )
        logger.info(
            "PreprocessingAgent applied {} -> skew {:.2f}->{:.2f} deg, contrast {:.2f}->{:.2f}",
            transformations,
            metrics_before["skew_angle_degrees"],
            metrics_after["skew_angle_degrees"],
            metrics_before["contrast_rms"],
            metrics_after["contrast_rms"],
        )
        return result

    @staticmethod
    def _load(image_input: Union[str, bytes, np.ndarray]) -> np.ndarray:
        import os
        import io
        from PIL import Image, ImageOps
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Image file not found: {image_input}")
            arr = np.array(ImageOps.exif_transpose(Image.open(image_input)))
            return cv2_bgr(arr)
        if isinstance(image_input, bytes):
            arr = np.array(ImageOps.exif_transpose(Image.open(io.BytesIO(image_input))))
            return cv2_bgr(arr)
        if isinstance(image_input, np.ndarray):
            return image_input.copy()
        raise ValueError("Invalid image input type. Must be file path, bytes, or numpy array.")


def cv2_bgr(rgb_array: np.ndarray) -> np.ndarray:
    import cv2
    if rgb_array.ndim == 2:
        return rgb_array
    return cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)


def preprocess(image_input: Union[str, bytes, np.ndarray]) -> PreprocessingResult:
    """Convenience wrapper: image -> PreprocessingResult (reference Session 1 output)."""
    return PreprocessingAgent().run(image_input)
