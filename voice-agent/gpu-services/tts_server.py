"""
TTS synthesis service — runs on GPU box.
Endpoint: POST /synthesize  (JSON: { "text": "...", "voice": "af_heart" })
Returns:  audio/wav binary

Kokoro is the default (better quality). Piper is the CPU-friendly fallback
if Kokoro proves too slow — see BENCHMARK.md for decision criteria.

Start: uvicorn tts_server:app --host 0.0.0.0 --port 8002
"""

import io
import os
import time
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import soundfile as sf

app = FastAPI(title="Viox Kokoro TTS")

VOICE = os.getenv("TTS_VOICE", "af_heart")    # Kokoro voice name
SPEED = float(os.getenv("TTS_SPEED", "1.0"))
SAMPLE_RATE = 24000                            # Kokoro outputs 24 kHz

print("Loading Kokoro TTS pipeline...")
try:
    from kokoro import KPipeline
    pipeline = KPipeline(lang_code="a")        # 'a' = American English
    USE_KOKORO = True
    print("Kokoro ready.")
except Exception as e:
    print(f"Kokoro unavailable ({e}), falling back to silent stub. Install Kokoro on GPU box.")
    USE_KOKORO = False


class SynthRequest(BaseModel):
    text: str
    voice: str = VOICE
    speed: float = SPEED


@app.get("/health")
def health():
    return {"status": "ok", "backend": "kokoro" if USE_KOKORO else "stub", "voice": VOICE}


@app.post("/synthesize", response_class=Response)
async def synthesize(req: SynthRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")

    t0 = time.perf_counter()

    if USE_KOKORO:
        audio_chunks = []
        for _, _, audio in pipeline(req.text, voice=req.voice, speed=req.speed, split_pattern=r"\n+"):
            audio_chunks.append(audio)
        audio_np = np.concatenate(audio_chunks) if audio_chunks else np.zeros(SAMPLE_RATE, dtype=np.float32)
    else:
        # 1-second silent placeholder for local dev without Kokoro installed
        audio_np = np.zeros(SAMPLE_RATE, dtype=np.float32)

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    buf = io.BytesIO()
    sf.write(buf, audio_np, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    wav_bytes = buf.getvalue()

    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-Synthesis-Ms": str(elapsed_ms), "X-Chars": str(len(req.text))},
    )
