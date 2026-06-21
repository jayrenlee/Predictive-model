# Twilio + LiveKit SIP Setup (Phase 5)

## Overview

```
Inbound call → Twilio number → Twilio SIP trunk → LiveKit SIP server → LiveKit room → agent.py worker
```

---

## 1. LiveKit Cloud (free tier) — quickest path for demo

1. Sign up at https://cloud.livekit.io — the free tier supports enough concurrent rooms for testing.
2. Note your **URL** (`wss://your-project.livekit.cloud`), **API Key**, and **API Secret**.
3. Add these to `voice-agent/.env`:
   ```
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=APIxxxxxx
   LIVEKIT_API_SECRET=your-secret
   ```

### Enable SIP on LiveKit Cloud

In the LiveKit Cloud dashboard → **SIP** → **Enable SIP**.  
You'll get a SIP URI in the form: `sip.livekit.cloud`

---

## 2. Buy a Twilio phone number

```bash
# Install Twilio CLI first: https://www.twilio.com/docs/twilio-cli/quickstart
twilio login

# Buy a US number (cheapest, works globally for demo)
twilio api:core:incoming-phone-numbers:create \
  --area-code 415 \
  --voice-method POST

# Note the number SID and phone number (+1415xxxxxxx)
```

---

## 3. Create a Twilio SIP Trunk → LiveKit

```bash
# Create a trunk
twilio api:core:trunking:v1:trunks:create \
  --friendly-name "Viox Banking Demo"

# Note the Trunk SID (TKxxxx)
TRUNK_SID=TKxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Add LiveKit as the origination URI
twilio api:core:trunking:v1:trunks:origination-urls:create \
  --trunk-sid $TRUNK_SID \
  --friendly-name "LiveKit SIP" \
  --sip-url "sip:your-project.sip.livekit.cloud" \
  --priority 10 \
  --weight 100 \
  --enabled true

# Assign your number to the trunk
twilio api:core:trunking:v1:trunks:phone-numbers:create \
  --trunk-sid $TRUNK_SID \
  --phone-number-sid PNxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 4. LiveKit SIP Inbound Trunk configuration

In LiveKit Cloud dashboard → **SIP** → **Inbound Trunks** → **Create**:

| Field | Value |
|---|---|
| Name | Viox Banking Demo |
| Allowed Sources | Add Twilio's signaling IPs (see Twilio docs: `54.172.60.0/23` etc.) |
| Username | viox |
| Password | (set a strong password, note it) |

Or via LiveKit CLI:
```bash
lk sip inbound create \
  --allowed-addresses 54.172.60.0/23,54.244.51.0/24 \
  --number "+14155551234" \
  --name "Viox Banking"
```

---

## 5. LiveKit Dispatch Rule

Configure LiveKit to route inbound SIP calls to your agent worker:

```bash
lk sip dispatch create \
  --type individual-dispatch \
  --room-prefix "banking-" \
  --agent-name "viox-banking-agent"
```

This creates a new LiveKit room per call and dispatches to the agent matching the name.

---

## 6. Start the agent worker (on MacBook Air)

```bash
cd voice-agent/livekit-agent
pip install -r requirements.txt

LIVEKIT_URL=wss://your-project.livekit.cloud \
LIVEKIT_API_KEY=APIxxxxxx \
LIVEKIT_API_SECRET=your-secret \
BACKEND_URL=http://localhost:3000 \
WHISPER_URL=http://<gpu-box-ip>:8001 \
TTS_URL=http://<gpu-box-ip>:8002 \
python agent.py
```

The worker connects to LiveKit and waits for dispatch jobs.

---

## 7. Test the full pipeline

1. Start GPU box services: `ssh gpu-box 'cd /opt/viox && ./setup.sh'`
2. Start Node.js backend: `cd voice-agent && npm run dev`
3. Start LiveKit agent: (step 6 above)
4. Call your Twilio number
5. Enter your OTP on the keypad when prompted
6. Ask: "What's my balance?"

---

## Open decisions from brief §9

| Decision | Recommendation | When to decide |
|---|---|---|
| Whisper model size (base vs small) | Run `benchmark.sh` on GPU box first | Before Phase 5 call test |
| Kokoro vs Piper TTS | Kokoro sounds better; use Piper only if Kokoro latency >500ms | During benchmarking |
| LiveKit Cloud vs self-hosted | Cloud free tier is sufficient for solo demo volume | Revisit if >10 concurrent calls needed |
| Twilio number region | US number (+1) — cheaper, no KYC for demo purposes | When buying number |
