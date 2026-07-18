"""Minimal FastAPI app placeholder for the MedVault Hepatology OCR pipeline."""

from fastapi import FastAPI

app = FastAPI(title="MedVault Hepatology OCR Pipeline")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
