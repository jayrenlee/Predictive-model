"""
Viox Banking Voice Agent — LiveKit worker.

Flow per call:
  1. SIP call arrives → LiveKit dispatches job to this worker
  2. Agent greets caller, enters DTMF-collection mode for OTP
  3. DTMF digits accumulate silently (never spoken, never seen by LLM)
  4. After 6 digits: POST /api/otp/verify to Node.js backend
     - On success → verified, enter voice conversation loop
     - On failure → announce remaining attempts or terminate
  5. Voice loop: VAD detects utterance → Whisper → Node.js orchestrator → TTS → play back
  6. Audit trail written by the Node.js backend on every action

Start: python -m livekit.agents.cli start --url $LIVEKIT_URL --api-key $LIVEKIT_API_KEY \
         --api-secret $LIVEKIT_API_SECRET agent:entrypoint
"""

import asyncio
import os
import logging
import time
import io
import aiohttp
import numpy as np
import soundfile as sf

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli, JobProcess
from livekit.agents.voice_assistant import AssistantCallContext

from audio_utils import pcm_to_wav_bytes, wav_bytes_to_pcm, frames_to_livekit, resample_pcm
from vad import VoiceActivityDetector, SAMPLE_RATE as VAD_RATE, FRAME_SAMPLES

load_dotenv()

log = logging.getLogger("viox.agent")
logging.basicConfig(level=logging.INFO)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3000")
WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:8001")
TTS_URL = os.getenv("TTS_URL", "http://localhost:8002")

OTP_DIGITS = 6
LIVEKIT_SAMPLE_RATE = 48000
LIVEKIT_CHANNELS = 1


# ── TTS helper ────────────────────────────────────────────────────────────────

async def synthesize_and_publish(
    text: str,
    audio_source: rtc.AudioSource,
    session: aiohttp.ClientSession,
    stop_event: asyncio.Event,
) -> float:
    """Synthesize text → WAV → push PCM frames into LiveKit. Returns duration in seconds."""
    t0 = time.perf_counter()
    async with session.post(f"{TTS_URL}/synthesize", json={"text": text}) as resp:
        resp.raise_for_status()
        wav_bytes = await resp.read()

    pcm, sr = wav_bytes_to_pcm(wav_bytes)
    frames = frames_to_livekit(pcm, sr)

    for frame_pcm in frames:
        if stop_event.is_set():
            break
        audio_frame = rtc.AudioFrame(
            data=frame_pcm.tobytes(),
            sample_rate=LIVEKIT_SAMPLE_RATE,
            num_channels=LIVEKIT_CHANNELS,
            samples_per_channel=len(frame_pcm),
        )
        await audio_source.capture_frame(audio_frame)
        # 10 ms pacing
        await asyncio.sleep(0.009)

    return time.perf_counter() - t0


# ── OTP verification ──────────────────────────────────────────────────────────

async def verify_otp(
    session: aiohttp.ClientSession, session_id: str, code: str
) -> dict:
    async with session.post(
        f"{BACKEND_URL}/api/otp/verify",
        json={"sessionId": session_id, "code": code},
    ) as resp:
        return await resp.json()


# ── Whisper transcription ─────────────────────────────────────────────────────

async def transcribe(session: aiohttp.ClientSession, pcm_16k: np.ndarray) -> str:
    wav_bytes = pcm_to_wav_bytes(pcm_16k.astype(np.int16), VAD_RATE)
    form = aiohttp.FormData()
    form.add_field("file", wav_bytes, filename="audio.wav", content_type="audio/wav")
    async with session.post(f"{WHISPER_URL}/transcribe", data=form) as resp:
        resp.raise_for_status()
        data = await resp.json()
    return data.get("text", "").strip()


# ── Orchestrator (Node.js LangGraph backend) ──────────────────────────────────

async def ask_orchestrator(
    session: aiohttp.ClientSession,
    session_id: str,
    account_id: str,
    text: str,
) -> str:
    async with session.post(
        f"{BACKEND_URL}/api/agent/turn",
        json={"sessionId": session_id, "accountId": account_id, "userInput": text},
    ) as resp:
        resp.raise_for_status()
        data = await resp.json()
    return data.get("response", "I'm sorry, I couldn't process that request.")


# ── Main agent entrypoint ─────────────────────────────────────────────────────

async def entrypoint(ctx: JobContext):
    log.info("Agent job started — room: %s", ctx.room.name)

    await ctx.connect(auto_subscribe=rtc.AutoSubscribe.AUDIO_ONLY)

    # Wait for the SIP participant (caller) to join
    participant = await ctx.wait_for_participant()
    caller_identity = participant.identity
    log.info("Caller joined: %s", caller_identity)

    # Resolve account from caller phone number (passed as participant identity by Twilio/LiveKit SIP)
    # Identity format from Twilio SIP: "sip:+60123456789@..."
    phone = caller_identity.split(":")[1].split("@")[0] if ":" in caller_identity else caller_identity

    async with aiohttp.ClientSession() as http:
        # Resolve account
        async with http.post(
            f"{BACKEND_URL}/api/otp/generate", json={"phoneNumber": phone}
        ) as resp:
            if resp.status != 200:
                log.warning("No account for %s — disconnecting", phone)
                await ctx.room.disconnect()
                return
            init = await resp.json()

        session_id: str = init["sessionId"]
        account_id: str = init["accountId"]
        log.info("Account resolved: %s session: %s", account_id, session_id)

        # Publish audio source (agent → caller)
        audio_source = rtc.AudioSource(LIVEKIT_SAMPLE_RATE, LIVEKIT_CHANNELS)
        track = rtc.LocalAudioTrack.create_audio_track("agent-audio", audio_source)
        await ctx.room.local_participant.publish_track(track)

        barge_in = asyncio.Event()

        async def speak(text: str):
            barge_in.clear()
            await synthesize_and_publish(text, audio_source, http, barge_in)

        # ── Phase 4: DTMF OTP collection ─────────────────────────────────────
        await speak(
            "Welcome to Viox Bank. For your security, please enter your "
            "six-digit one-time code on your keypad now."
        )

        dtmf_buffer = ""
        dtmf_event = asyncio.Event()
        verified = False
        attempts_left = 3

        @ctx.room.on("sip_dtmf_received")
        def on_dtmf(dtmf_event_data):
            nonlocal dtmf_buffer
            digit = str(dtmf_event_data.digit)
            if digit.isdigit():
                dtmf_buffer += digit
                log.debug("DTMF digit received (buffer len=%d)", len(dtmf_buffer))
                if len(dtmf_buffer) >= OTP_DIGITS:
                    dtmf_event.set()

        # Wait up to 90s for 6 digits
        try:
            await asyncio.wait_for(dtmf_event.wait(), timeout=90.0)
        except asyncio.TimeoutError:
            await speak("I didn't receive your code. Please call back and try again. Goodbye.")
            await ctx.room.disconnect()
            return

        # Verify collected OTP
        code_entered = dtmf_buffer[:OTP_DIGITS]
        result = await verify_otp(http, session_id, code_entered)

        if result.get("verified"):
            verified = True
            await speak("Thank you. Your identity has been verified. How can I help you today?")
        else:
            reason = result.get("reason", "invalid_code")
            if reason == "invalid_code":
                attempts_left = result.get("attemptsLeft", 0)
                if attempts_left <= 0:
                    await speak("Too many incorrect attempts. For your security, this session has ended. Goodbye.")
                    await ctx.room.disconnect()
                    return
                else:
                    await speak(
                        f"That code was incorrect. You have {attempts_left} attempt{'s' if attempts_left > 1 else ''} remaining. "
                        "Please enter your six-digit code now."
                    )
                    # Allow one more attempt (retry loop omitted for brevity; extend for production)
            elif reason == "expired":
                await speak("Your code has expired. Please call back to receive a new code. Goodbye.")
                await ctx.room.disconnect()
                return
            else:
                await speak("Verification failed. Please call back. Goodbye.")
                await ctx.room.disconnect()
                return

        if not verified:
            return

        # ── Phase 5: voice conversation loop ─────────────────────────────────
        vad = VoiceActivityDetector(aggressiveness=2)
        pcm_ring: list[np.ndarray] = []

        # Find and subscribe to caller's audio track
        audio_stream: rtc.AudioStream | None = None
        for pub in participant.track_publications.values():
            if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                audio_stream = rtc.AudioStream(pub.track)
                break

        if audio_stream is None:
            log.error("No audio track from caller — aborting")
            await ctx.room.disconnect()
            return

        log.info("Starting voice conversation loop")

        async def voice_loop():
            async for event in audio_stream:
                if not isinstance(event, rtc.AudioFrameEvent):
                    continue

                frame = event.frame
                # Convert LiveKit frame (48 kHz) to 16 kHz mono for VAD/Whisper
                raw = np.frombuffer(frame.data, dtype=np.int16)
                if frame.num_channels > 1:
                    raw = raw.reshape(-1, frame.num_channels).mean(axis=1).astype(np.int16)
                pcm_16k = resample_pcm(raw, frame.sample_rate, VAD_RATE)

                # Feed VAD in FRAME_SAMPLES-sized chunks
                for i in range(0, len(pcm_16k) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
                    utterance = vad.feed(pcm_16k[i : i + FRAME_SAMPLES])
                    if utterance is not None:
                        # Signal barge-in to stop any ongoing TTS
                        barge_in.set()

                        t_start = time.perf_counter()
                        transcript = await transcribe(http, utterance)
                        t_asr = time.perf_counter()
                        log.info("ASR [%.0fms]: %s", (t_asr - t_start) * 1000, transcript)

                        if not transcript:
                            continue

                        response_text = await ask_orchestrator(
                            http, session_id, account_id, transcript
                        )
                        t_llm = time.perf_counter()
                        log.info("LLM [%.0fms]: %s", (t_llm - t_asr) * 1000, response_text[:80])

                        tts_dur = await synthesize_and_publish(
                            response_text, audio_source, http, barge_in
                        )
                        t_tts = time.perf_counter()
                        log.info(
                            "TTS [%.0fms] | Total turn: %.0fms",
                            tts_dur * 1000,
                            (t_tts - t_start) * 1000,
                        )

        try:
            await asyncio.wait_for(voice_loop(), timeout=600.0)  # 10-min max call
        except asyncio.TimeoutError:
            await speak("This session has reached the maximum call duration. Goodbye.")
        finally:
            log.info("Session %s ended", session_id)
            await ctx.room.disconnect()


def prewarm(proc: JobProcess):
    """Called once before jobs start — use for model preloading if needed."""
    pass


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
