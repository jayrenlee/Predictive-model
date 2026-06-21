"""
Whisper transcription service — runs on GPU box.
Endpoint: POST /transcribe  (multipart: file=<wav/webm audio>)
Returns:  { "text": "...", "language": "en", "duration_ms": 123 }

Start: uvicorn whisper_server:app --host 0.0.0.0 --port 8001
"""

import io
import time
import tempfile
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

app = FastAPI(title="Viox Whisper ASR")

# Adjust model_size via env var after benchmarking on your GPU box.
# "base" is fastest (~0.3s on RTX 4090); "small" is more accurate (~0.6s).
# Decision from brief §9: pick after benchmarking — start with "small".
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
DEVICE = os.getenv("WHISPER_DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE", "float16")

print(f"Loading Whisper {MODEL_SIZE} on {DEVICE} ({COMPUTE_TYPE})...")
model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
print("Whisper ready.")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_SIZE, "device": DEVICE}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        t0 = time.perf_counter()
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            language="en",
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        return JSONResponse({
            "text": text,
            "language": info.language,
            "language_probability": round(info.language_probability, 3),
            "duration_ms": elapsed_ms,
        })
    finally:
        os.unlink(tmp_path)
