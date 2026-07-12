"""
qwen_vl_server.py - Qwen2.5-VL handwritten OCR microservice (GPU)
=================================================================
Runs as a SEPARATE process from the main PaddleOCR server so the two GPU
stacks never share one process (Hard Rule #2: never two GPU models at once).

Pure native torch CUDA (no DirectML / RapidOCR). Requires a CUDA 12.8+ torch
build for Blackwell (RTX 5060, sm_120) - see pipeline_v1/backend/requirements.txt.

Mirrors e2e_pipeline/backend/ocr/handwritten_server.py but loads on GPU.

Run with:
    ..\\venv\\Scripts\\python.exe qwen_vl_server.py
    (listens on http://127.0.0.1:8002)
"""
import os
import sys
import io
import gc
import torch
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration as AutoModelForVision2Seq

app = FastAPI(title="Qwen-VL Handwritten OCR microservice (GPU)")

MODEL_ID = os.environ.get("QWEN_MODEL_ID", "Qwen/Qwen2.5-VL-3B-Instruct")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# NOTE: 4-bit (bitsandbytes) and torch.compile were tested on this RTX 5060
# (Blackwell, sm_120) and were SLOWER (4-bit ~7x, compile hung) than plain bf16.
# They are kept as opt-in env flags but default OFF to the proven-fast path.
LOAD_IN_4BIT = os.environ.get("QWEN_4BIT", "0") != "0"
USE_COMPILE = os.environ.get("QWEN_COMPILE", "0") != "0"

# Load Qwen2.5-VL on the GPU.
# 4-bit (bitsandbytes) roughly halves weight memory traffic -> ~2x faster decode,
# which is the dominant cost for handwritten OCR on an 8GB laptop GPU.
print(f"[QwenVL] Loading {MODEL_ID} on {DEVICE} "
      f"(4bit={LOAD_IN_4BIT}, compile={USE_COMPILE})...")
processor = AutoProcessor.from_pretrained(MODEL_ID)

load_kwargs = dict(
    attn_implementation="sdpa",   # torch's fused/memory-efficient attention (no flash-attn needed)
    device_map=DEVICE,
)
if LOAD_IN_4BIT:
    try:
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    except Exception as e:
        print(f"[QwenVL] 4-bit unavailable ({e}); falling back to bf16.")
        LOAD_IN_4BIT = False
        load_kwargs["torch_dtype"] = torch.bfloat16

model = AutoModelForVision2Seq.from_pretrained(MODEL_ID, **load_kwargs)
model.eval()

if USE_COMPILE and DEVICE == "cuda":
    try:
        model = torch.compile(model, mode="reduce-overhead")
        print("[QwenVL] torch.compile enabled.")
    except Exception as e:
        print(f"[QwenVL] torch.compile skipped ({e}).")

if DEVICE == "cuda":
    print(f"[QwenVL] GPU: {torch.cuda.get_device_name(0)} "
          f"cap={torch.cuda.get_device_capability(0)}")
print("[QwenVL] Model ready.")

PROMPT = (
    "Please transcribe all the handwritten text in this medical document. "
    "Provide ONLY the raw transcribed text. Do not add any introductory "
    "greetings, explanations, conversational filler, or formatting. "
    "If there is no handwriting or if you cannot read it, output nothing."
)


def _run_ocr(pil_img: Image.Image) -> str:
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": pil_img, "max_pixels": 128 * 28 * 28},
            {"type": "text", "text": PROMPT},
        ],
    }]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    try:
        from qwen_vl_utils import process_vision_info
        image_inputs, video_inputs = process_vision_info(messages)
    except ImportError:
        image_inputs, video_inputs = [pil_img], None

    inputs = processor(
        text=[text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt",
    ).to(DEVICE)

    max_new_tokens = int(os.environ.get("QWEN_MAX_TOKENS", "768"))
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=max_new_tokens)
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated_ids)]
    out_text = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0].strip()
    gc.collect()
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    return out_text


@app.post("/ocr")
async def run_ocr(request: Request, file: UploadFile = None):
    try:
        image_bytes = None
        if "application/json" in request.headers.get("content-type", ""):
            body = await request.json()
            for msg in body.get("messages", []):
                for item in msg.get("content", []):
                    if item.get("type") == "image_url":
                        url = item["image_url"]["url"]
                        b64 = url.split(",", 1)[1] if "," in url else url
                        import base64
                        image_bytes = base64.b64decode(b64)
                        break
        else:
            if file is None:
                form = await request.form()
                file = form.get("file")
            if file is not None:
                image_bytes = await file.read()

        if image_bytes is None:
            return JSONResponse(status_code=400,
                                content={"error": "No image provided"})

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return {"text": _run_ocr(pil_img)}
    except Exception as e:
        print(f"[QwenVL] Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible endpoint used by AutoOCRProvider (main.py) to route
    handwritten documents to this GPU microservice. Accepts the standard
    chat-completions JSON body with an image_url content part.
    """
    try:
        body = await request.json()
        image_bytes = None
        for msg in body.get("messages", []):
            for item in msg.get("content", []):
                if item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    b64 = url.split(",", 1)[1] if "," in url else url
                    import base64
                    image_bytes = base64.b64decode(b64)
                    break

        if image_bytes is None:
            return JSONResponse(status_code=400,
                                content={"error": "No image provided in messages"})

        pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        text = _run_ocr(pil_img)
        return {
            "choices": [{
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }],
            "text": text,
        }
    except Exception as e:
        print(f"[QwenVL] /v1/chat/completions error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
def health():
    return {"status": "ok", "device": DEVICE,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
