#!/usr/bin/env bash
# Latency benchmark — run on GPU box after setup.sh completes.
# Measures Whisper ASR, Ollama LLM, and TTS independently.
# Decision criteria from brief §9: pick Whisper model size + TTS backend here.

set -euo pipefail

WHISPER_URL="${WHISPER_URL:-http://localhost:8001}"
OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
TTS_URL="${TTS_URL:-http://localhost:8002}"

RUNS=3

avg_ms() {
  local total=0
  for t in "$@"; do total=$((total + t)); done
  echo $((total / $#))
}

echo "=== Viox GPU Box Latency Benchmark ==="
echo ""

# ── Whisper ───────────────────────────────────────────────────────────────────
echo "1. Whisper ASR"
# Generate a 3-second silent wav as dummy audio
python3 - <<'PY'
import wave, struct, os
fname = "/tmp/bench_audio.wav"
with wave.open(fname, "w") as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
    f.writeframes(struct.pack("<" + "h"*48000, *([0]*48000)))
print(f"  Test audio: {fname}")
PY

WHISPER_TIMES=()
for i in $(seq 1 $RUNS); do
  T=$( { time curl -sf -X POST "$WHISPER_URL/transcribe" \
    -F "file=@/tmp/bench_audio.wav;type=audio/wav" > /dev/null; } 2>&1 \
    | grep real | awk '{print $2}' | sed 's/m//;s/s//' \
    | awk '{printf "%d", $1*60000 + $2*1000}')
  WHISPER_TIMES+=("$T")
  echo "  run $i: ${T}ms"
done
echo "  avg: $(avg_ms "${WHISPER_TIMES[@]}")ms"
echo ""

# ── Ollama LLM ────────────────────────────────────────────────────────────────
echo "2. Ollama LLM (first-token latency, ~20-word prompt)"
PROMPT="You are a banking assistant. The customer asks: what is my account balance? Reply in one sentence."
OLLAMA_TIMES=()
for i in $(seq 1 $RUNS); do
  T0=$(date +%s%3N)
  curl -sf -X POST "$OLLAMA_URL/api/generate" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"llama3.1:8b-instruct-q4_K_M\",\"prompt\":\"$PROMPT\",\"stream\":false}" \
    > /tmp/ollama_resp.json
  T1=$(date +%s%3N)
  MS=$((T1 - T0))
  OLLAMA_TIMES+=("$MS")
  TOKENS=$(python3 -c "import json; d=json.load(open('/tmp/ollama_resp.json')); print(d.get('eval_count',0))")
  echo "  run $i: ${MS}ms  (${TOKENS} tokens)"
done
echo "  avg: $(avg_ms "${OLLAMA_TIMES[@]}")ms"
echo ""

# ── TTS ───────────────────────────────────────────────────────────────────────
echo "3. Kokoro TTS (~15-word sentence)"
TEXT="Your account balance is twelve thousand three hundred and forty five ringgit."
TTS_TIMES=()
for i in $(seq 1 $RUNS); do
  T0=$(date +%s%3N)
  curl -sf -X POST "$TTS_URL/synthesize" \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"$TEXT\"}" > /tmp/bench_out.wav
  T1=$(date +%s%3N)
  MS=$((T1 - T0))
  TTS_TIMES+=("$MS")
  SIZE=$(wc -c < /tmp/bench_out.wav)
  echo "  run $i: ${MS}ms  (${SIZE} bytes WAV)"
done
echo "  avg: $(avg_ms "${TTS_TIMES[@]}")ms"
echo ""

echo "=== Summary ==="
echo "  Whisper avg : $(avg_ms "${WHISPER_TIMES[@]}")ms"
echo "  Ollama avg  : $(avg_ms "${OLLAMA_TIMES[@]}")ms"
echo "  TTS avg     : $(avg_ms "${TTS_TIMES[@]}")ms"
echo "  Total avg   : $(($(avg_ms "${WHISPER_TIMES[@]}") + $(avg_ms "${OLLAMA_TIMES[@]}") + $(avg_ms "${TTS_TIMES[@]}")))ms"
echo ""
echo "Target: Whisper <800ms, LLM <2000ms, TTS <500ms — total <3.5s per turn"
echo "If Whisper 'small' is >800ms, re-run with WHISPER_MODEL=base (set in .env on GPU box)"
