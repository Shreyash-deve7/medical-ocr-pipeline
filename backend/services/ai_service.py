"""backend/services/ai_service.py — pluggable AI analysis layer (Session 6).

Extracted verbatim from ``main.py``:
  - ``AIProvider`` ABC + Gemini / OpenAI / Ollama / Custom implementations
  - ``AI_ENGINES`` registry + ``build_ai``
  - ``MEDICAL_PROMPT`` and ``_extract_images`` (used by the analyze route)

Provider SDK / httpx imports stay lazy inside ``analyze`` exactly as before.
"""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from fastapi import HTTPException


class AIProvider(ABC):
    @abstractmethod
    def analyze(self, prompt: str, text: str, images: list[bytes]) -> str: ...


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
    def analyze(self, prompt: str, text: str, images: list[bytes]) -> str:  # pragma: no cover - network
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        parts: list = [prompt]
        if text:
            parts.append(f"\n\nExtracted text:\n{text}")
        for img in images[:5]:
            parts.append({"mime_type": "image/png", "data": img})
        return model.generate_content(parts).text


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model_name = model
        self.base_url = base_url
    def analyze(self, prompt: str, text: str, images: list[bytes]) -> str:  # pragma: no cover - network
        import httpx
        content: list[dict] = [{"type": "text", "text": prompt}]
        if text:
            content.append({"type": "text", "text": f"\nExtracted text:\n{text}"})
        for img in images[:5]:
            b64 = base64.b64encode(img).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model_name, "messages": [{"role": "user", "content": content}], "max_tokens": 4096},
            timeout=120,
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"OpenAI API error {resp.status_code}")
        return resp.json()["choices"][0]["message"]["content"]


class OllamaProvider(AIProvider):
    def __init__(self, model: str = "llava", base_url: str = "http://localhost:11434"):
        self.model_name = model
        self.base_url = base_url
    def analyze(self, prompt: str, text: str, images: list[bytes]) -> str:  # pragma: no cover - network
        import httpx
        full_prompt = prompt + (f"\n\nExtracted text:\n{text}" if text else "")
        payload: dict = {"model": self.model_name, "prompt": full_prompt, "stream": False}
        if images:
            payload["images"] = [base64.b64encode(img).decode() for img in images[:3]]
        resp = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=180)
        if resp.status_code != 200:
            raise HTTPException(502, f"Ollama error {resp.status_code}")
        return resp.json()["response"]


class CustomAIProvider(AIProvider):
    def __init__(self, endpoint: str, api_key: str = "", model: str = "", headers: Optional[dict] = None):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model_name = model
        self.headers = headers or {}
    def analyze(self, prompt: str, text: str, images: list[bytes]) -> str:  # pragma: no cover - network
        import httpx
        content: list[dict] = [{"type": "text", "text": prompt}]
        if text:
            content.append({"type": "text", "text": f"\nExtracted text:\n{text}"})
        for img in images[:5]:
            b64 = base64.b64encode(img).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        h = {**self.headers, "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        body: dict = {"messages": [{"role": "user", "content": content}], "max_tokens": 4096}
        if self.model_name:
            body["model"] = self.model_name
        resp = httpx.post(self.endpoint, headers=h, json=body, timeout=120)
        if resp.status_code != 200:
            raise HTTPException(502, f"Custom AI error {resp.status_code}")
        data = resp.json()
        if "choices" in data:
            return data["choices"][0]["message"]["content"]
        return data.get("response", data.get("text", str(data)))


AI_ENGINES = {
    "gemini": lambda cfg: GeminiProvider(api_key=cfg["api_key"], model=cfg.get("model", "gemini-2.0-flash")),
    "openai": lambda cfg: OpenAIProvider(api_key=cfg["api_key"], model=cfg.get("model", "gpt-4o"), base_url=cfg.get("base_url", "https://api.openai.com/v1")),
    "ollama": lambda cfg: OllamaProvider(model=cfg.get("model", "llava"), base_url=cfg.get("base_url", "http://localhost:11434")),
    "custom_openai": lambda cfg: CustomAIProvider(endpoint=cfg["endpoint"], api_key=cfg.get("api_key", ""), model=cfg.get("model", ""), headers=cfg.get("headers")),
}


def build_ai(engine: str, config: dict) -> AIProvider:
    factory = AI_ENGINES.get(engine)
    if not factory:
        raise HTTPException(400, f"Unknown AI engine: {engine}")
    return factory(config)


def _extract_images(filepath: str, filetype: str) -> list[bytes]:
    if filetype == "image":
        return [Path(filepath).read_bytes()]
    import fitz  # PyMuPDF
    doc = fitz.open(filepath)
    images = [page.get_pixmap(dpi=200).tobytes("png") for page in doc]
    doc.close()
    return images


MEDICAL_PROMPT = (
    "You are a medical document analyst. Analyze this medical report thoroughly.\n"
    "1. Extract ALL text (OCR if needed).\n"
    "2. Identify the type of report (blood test, X-ray, MRI, prescription, etc.).\n"
    "3. List all findings, values, and observations.\n"
    "4. Flag any abnormal values or concerning findings.\n"
    "5. Provide a brief summary for the doctor.\n\n"
    "Format your response as:\n"
    "## Extracted Text\n<full text>\n\n"
    "## Report Type\n<type>\n\n"
    "## Key Findings\n<findings>\n\n"
    "## Abnormal Values\n<abnormals>\n\n"
    "## Summary\n<summary>"
)
