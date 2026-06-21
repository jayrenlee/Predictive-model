"""Audio utility helpers shared by the agent."""

import io
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd


def resample_pcm(pcm: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample integer PCM array from src_rate to dst_rate."""
    if src_rate == dst_rate:
        return pcm
    g = gcd(src_rate, dst_rate)
    up, down = dst_rate // g, src_rate // g
    return resample_poly(pcm.astype(np.float32), up, down).astype(np.int16)


def pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int) -> bytes:
    """Convert int16 mono PCM array to WAV bytes."""
    buf = io.BytesIO()
    sf.write(buf, pcm, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def wav_bytes_to_pcm(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Load WAV bytes → (int16 mono PCM array, sample_rate)."""
    buf = io.BytesIO(wav_bytes)
    audio, sr = sf.read(buf, dtype="int16", always_2d=False)
    if audio.ndim == 2:
        audio = audio.mean(axis=1).astype(np.int16)
    return audio, sr


def frames_to_livekit(pcm: np.ndarray, src_rate: int) -> list[np.ndarray]:
    """
    Resample PCM to 48 kHz and split into 10 ms frames (480 samples each)
    for LiveKit's AudioFrame publisher.
    """
    pcm_48k = resample_pcm(pcm, src_rate, 48000)
    frame_size = 480  # 10 ms @ 48 kHz
    frames = []
    for i in range(0, len(pcm_48k) - frame_size + 1, frame_size):
        frames.append(pcm_48k[i : i + frame_size])
    return frames
