#!/usr/bin/env bash
# GPU box first-time setup — RunPod / Vast.ai (Ubuntu 22.04, CUDA 12+)
# Run once after provisioning. Re-running is safe (idempotent where possible).
# Estimated cost: ~$0.50-0.90/hr on RTX 4090 (RunPod spot / Vast.ai)

set -euo pipefail

echo "=== Viox Banking Voice Agent — GPU Box Setup ==="
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'not detected')"

# ── 1. System packages ────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y -q curl wget git ffmpeg python3.11 python3-pip python3.11-venv

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
  echo "[Ollama] Installing..."
  curl -fsSL https://ollama.com/install.sh | sh
fi
echo "[Ollama] Starting daemon..."
nohup ollama serve > /tmp/ollama.log 2>&1 &
sleep 3

echo "[Ollama] Pulling Llama 3.1 8B Q4_K_M..."
ollama pull llama3.1:8b-instruct-q4_K_M
echo "[Ollama] Model ready."

# ── 3. Python venv for ASR + TTS services ────────────────────────────────────
VENV=/opt/viox-ai
python3.11 -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$(dirname "$0")/requirements.txt"

# ── 4. Start Whisper service ──────────────────────────────────────────────────
echo "[Whisper] Starting on port 8001..."
nohup uvicorn whisper_server:app \
  --app-dir "$(dirname "$0")" \
  --host 0.0.0.0 --port 8001 \
  > /tmp/whisper.log 2>&1 &
sleep 5
curl -sf http://localhost:8001/health && echo " — Whisper OK"

# ── 5. Start TTS service ──────────────────────────────────────────────────────
echo "[TTS] Starting on port 8002..."
nohup uvicorn tts_server:app \
  --app-dir "$(dirname "$0")" \
  --host 0.0.0.0 --port 8002 \
  > /tmp/tts.log 2>&1 &
sleep 8
curl -sf http://localhost:8002/health && echo " — TTS OK"

# ── 6. Verify Ollama ──────────────────────────────────────────────────────────
curl -sf http://localhost:11434/api/tags | python3 -c "import sys,json; m=json.load(sys.stdin)['models']; print(f' — Ollama OK ({len(m)} model(s) loaded)')"

echo ""
echo "=== All GPU services running ==="
echo "  Whisper ASR : http://$(curl -sf ifconfig.me 2>/dev/null || echo '<box-ip>'):8001"
echo "  Kokoro TTS  : http://$(curl -sf ifconfig.me 2>/dev/null || echo '<box-ip>'):8002"
echo "  Ollama LLM  : http://$(curl -sf ifconfig.me 2>/dev/null || echo '<box-ip>'):11434"
echo ""
echo "  Set these in voice-agent/.env as WHISPER_URL, TTS_URL, OLLAMA_URL"
