"""
Simple VAD: accumulates 16 kHz mono PCM frames from LiveKit, uses
webrtcvad to detect speech/silence, yields complete utterances when
a configurable silence gap follows speech.
"""

import collections
import webrtcvad
import numpy as np

# webrtcvad operates on 10/20/30 ms frames at 8/16/32/48 kHz
FRAME_MS = 20          # 20 ms frames
SAMPLE_RATE = 16000    # Whisper prefers 16 kHz
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 320 samples

SPEECH_PAD_MS = 300    # keep N ms before speech start
SILENCE_TRIGGER_MS = 700  # end utterance after this much silence


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int = 2):
        self._vad = webrtcvad.Vad(aggressiveness)
        self._ring = collections.deque(
            maxlen=SPEECH_PAD_MS // FRAME_MS
        )
        self._triggered = False
        self._voiced: list[np.ndarray] = []
        self._silence_frames = 0
        self._silence_trigger = SILENCE_TRIGGER_MS // FRAME_MS

    def feed(self, frame: np.ndarray) -> np.ndarray | None:
        """
        Feed one 320-sample frame (int16, 16 kHz mono).
        Returns complete utterance PCM array when speech ends, else None.
        """
        raw = frame.astype(np.int16).tobytes()
        is_speech = self._vad.is_speech(raw, SAMPLE_RATE)

        if not self._triggered:
            self._ring.append(frame)
            if is_speech:
                self._triggered = True
                self._voiced = list(self._ring)
                self._ring.clear()
                self._silence_frames = 0
        else:
            self._voiced.append(frame)
            if is_speech:
                self._silence_frames = 0
            else:
                self._silence_frames += 1
                if self._silence_frames >= self._silence_trigger:
                    utterance = np.concatenate(self._voiced)
                    self._triggered = False
                    self._voiced = []
                    self._silence_frames = 0
                    return utterance

        return None
