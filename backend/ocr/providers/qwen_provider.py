"""
qwen_vl_provider.py — Handwritten OCR via Qwen2.5-VL on GPU.

Adapted from the main project's e2e_pipeline/backend/ocr/handwritten_server.py.
Runs the vision-language model in-process on the GPU (no separate microservice
required) so the whole pipeline executes on GPU. Falls back to an HTTP
microservice if `server_url` is provided in the config.

Default model: Qwen/Qwen2.5-VL-3B-Instruct (also supports the local GGUF build
via the e2e_pipeline/models directory when `model_path` is set).
"""
from __future__ import annotations

import base64
import threading
from pathlib import Path

import cv2
import numpy as np
import requests

# ── Lazy singleton Qwen-VL instance (GPU) ─────────────────────────────────────
_MODEL = None
_MODEL_LOCK = threading.Lock()

DEFAULT_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
PROMPT = (
    "Please transcribe all the text in this medical document. "
    "Provide ONLY the raw transcribed text. Do not add any introductory "
    "greetings, explanations, conversational filler, or formatting. "
    "If the document is empty or unreadable, output nothing."
)


def _load_model(model_id: str, device: str, torch_dtype, load_in_4bit: bool = True):
    from transformers import AutoProcessor
    try:
        from transformers import AutoModelForVision2Seq as _M
    except ImportError:
        from transformers import Qwen2_5_VLForConditionalGeneration as _M
    if load_in_4bit:
        from transformers import BitsAndBytesConfig
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch_dtype,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        processor = AutoProcessor.from_pretrained(model_id)
        model = _M.from_pretrained(
            model_id,
            quantization_config=quant_config,
            device_map="auto",
        )
    else:
        processor = AutoProcessor.from_pretrained(model_id)
        model = _M.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            device_map=device or "auto",
        )
    model.eval()
    return processor, model


def _get_model(model_id: str, device: str, torch_dtype, load_in_4bit: bool = True):
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                _MODEL = _load_model(model_id, device, torch_dtype, load_in_4bit)
    return _MODEL


def _encode_image_bytes(img: np.ndarray) -> bytes:
    """Resize to max 1024px and encode as JPEG bytes."""
    max_dim = 1024
    h, w = img.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    success, buf = cv2.imencode(".jpg", img)
    if not success:
        raise ValueError("Failed to encode image to JPEG.")
    return buf.tobytes()


class QwenVLProvider:
    """
    MedVault OCRProvider backed by Qwen2.5-VL for handwritten reports.

    Config keys (all optional):
        model_id    (str,  default "Qwen/Qwen2.5-VL-3B-Instruct")
        device      (str,  default "cuda" if available else "cpu")
        torch_dtype (str,  default "bfloat16")
        server_url  (str,  optional — route to a running Qwen-VL microservice instead)
        max_pixels  (int,  default 128*28*28)
    """

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, device: str = None,
                 torch_dtype: str = "bfloat16", server_url: str = "",
                 max_pixels: int = 128 * 28 * 28, load_in_4bit: bool = True):
        self.model_id = model_id
        # When a microservice URL is supplied we route over HTTP, so local CUDA
        # is not required (the backend itself may run on a CPU-only venv while
        # the GPU microservice lives in a separate CUDA process).
        if not device:
            if not _cuda_available() and not server_url:
                raise RuntimeError(
                    "Qwen2.5-VL OCR requires a CUDA GPU (or a server_url pointing "
                    "at a GPU microservice); CPU fallback is disabled. Ensure torch is "
                    "installed with CUDA support, or set server_url."
                )
            self.device = "cuda" if _cuda_available() else "cpu"
        else:
            self.device = device
        self.torch_dtype_name = torch_dtype
        self.server_url = server_url
        self.max_pixels = max_pixels
        self.load_in_4bit = load_in_4bit

    def extract_text(self, filepath: str, filetype: str) -> str:
        """Transcribe a handwritten report image (or first PDF page) via Qwen-VL."""
        img = _load_cv2(filepath, filetype)
        if self.server_url:
            return self._extract_via_server(img)
        return self._extract_in_process(img)

    def extract_structured(self, filepath: str, filetype: str) -> list[dict]:
        """Extract structured test results (name, value, reference range) from handwritten report."""
        img = _load_cv2(filepath, filetype)
        
        structured_prompt = (
            "Extract all lab test results from this handwritten medical document. "
            "Return ONLY a JSON array of objects with these fields: "
            'test_name (string), value (string), unit (string), reference_range (string), '
            'flag (string - "H"/"L"/"N"/""). '
            "If a field is missing, use empty string. "
            "Example: [{\"test_name\": \"Hemoglobin\", \"value\": \"14.2\", \"unit\": \"g/dL\", "
            "\"reference_range\": \"13.0-17.0\", \"flag\": \"N\"}]"
        )
        
        if self.server_url:
            return self._extract_structured_via_server(img, structured_prompt)
        return self._extract_structured_in_process(img, structured_prompt)

    # ── Structured extraction (in-process) ──────────────────────────────────────
    def _extract_structured_in_process(self, img: np.ndarray, prompt: str) -> list[dict]:
        import torch
        import json
        import re
        from qwen_vl_utils import process_vision_info

        dtype = getattr(torch, self.torch_dtype_name, torch.bfloat16)
        processor, model = _get_model(self.model_id, self.device, dtype, self.load_in_4bit)

        pil_img = _cv2_to_pil(img)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_img, "max_pixels": self.max_pixels},
                {"type": "text", "text": prompt},
            ],
        }]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                           padding=True, return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=2048)
        trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        out_text = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0].strip()
        
        # Parse JSON response
        try:
            json_match = re.search(r'\[.*\]', out_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(out_text)
        except (json.JSONDecodeError, AttributeError):
            return []

    # ── Structured extraction (via server) ──────────────────────────────────────
    def _extract_structured_via_server(self, img: np.ndarray, prompt: str) -> list[dict]:
        import json
        import re
        image_bytes = _encode_image_bytes(img)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }]
        }
        resp = requests.post(self.server_url, json=payload, timeout=600)
        if resp.status_code != 200:
            raise RuntimeError(f"Qwen-VL microservice returned {resp.status_code}: {resp.text}")
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            out_text = choices[0].get("message", {}).get("content", "").strip()
        else:
            out_text = data.get("text", "")
        self._guard_vision_error(out_text)

        try:
            json_match = re.search(r'\[.*\]', out_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(out_text)
        except (json.JSONDecodeError, AttributeError):
            return []


# ── Helpers ───────────────────────────────────────────────────────────────────
    def _extract_in_process(self, img: np.ndarray) -> str:
        import torch
        from qwen_vl_utils import process_vision_info

        dtype = getattr(torch, self.torch_dtype_name, torch.bfloat16)
        processor, model = _get_model(self.model_id, self.device, dtype, self.load_in_4bit)

        pil_img = _cv2_to_pil(img)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_img, "max_pixels": self.max_pixels},
                {"type": "text", "text": PROMPT},
            ],
        }]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, videos=video_inputs,
                           padding=True, return_tensors="pt").to(self.device)

        with torch.no_grad():
            generated_ids = model.generate(**inputs, max_new_tokens=1024)
        trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
        return processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0].strip()

    # ── Optional microservice routing ─────────────────────────────────────────
    def _extract_via_server(self, img: np.ndarray) -> str:
        image_bytes = _encode_image_bytes(img)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": PROMPT},
                ],
            }]
        }
        resp = requests.post(self.server_url, json=payload, timeout=600)
        if resp.status_code != 200:
            raise RuntimeError(f"Qwen-VL microservice returned {resp.status_code}: {resp.text}")
        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            out_text = choices[0].get("message", {}).get("content", "").strip()
        else:
            out_text = data.get("text", "")
        self._guard_vision_error(out_text)
        return out_text

    @staticmethod
    def _guard_vision_error(text: str) -> None:
        lowered = (text or "").lower()
        if "does not support image" in lowered or "not a multimodal" in lowered or "multimodal" in lowered and "support" in lowered:
            raise RuntimeError(
                "The configured Qwen-VL endpoint is a TEXT-ONLY model and cannot read "
                "images. Point it at a vision-capable model (e.g. Qwen2.5-VL), or unset "
                "QWEN_VL_SERVER_URL to use the in-process torch Qwen-VL provider."
            )


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _load_cv2(filepath: str, filetype: str) -> np.ndarray:
    # Use the preprocessing pipeline for better OCR accuracy
    from image_processing import preprocess_image
    return preprocess_image(filepath)


def _cv2_to_pil(img: np.ndarray):
    from PIL import Image
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _exif_transpose(filepath: str):
    from PIL import Image, ImageOps
    pil = Image.open(filepath)
    return ImageOps.exif_transpose(pil)
