# Clone-Ad Skill

Recreate a video advertisement for a different product by analyzing an existing ad and generating a customized Seedance 2.0 video.

## Difference from Analyze-Video

- **analyze-video** → outputs reusable `.md` templates
- **clone-ad** → delivers a finished generated video customized for the user's product

## 12-Step Process

### Step 1: Gather Inputs
- Source video file path
- Product image or description
- Brand voice notes (or reference `MASTER_CONTEXT.md`)

### Step 2: Extract Frames and Audio
Use the shared `extract-frames.sh` script in the `scripts/` folder.

### Step 3: Transcribe Dialogue
Capture exact speech patterns, timing, and rhythm via Whisper.

### Step 4: Visual Analysis
Document:
- Beat structure with timestamps
- Camera work (angle, movement, distance)
- Edit style (cut frequency, transitions)
- Tone and energy arc
- Lighting approach
- Defining traits (what makes it immediately recognizable)

### Step 5: Present Summary
Show user a structured breakdown. Wait for approval before proceeding.

### Step 6: Decide Generation Mode
- **Single-clip:** Source video ≤ 15s
- **Multi-clip chaining:** Source video > 15s (see below)
- **i2v:** Image-to-video (product image as reference)
- **v2v:** Video-to-video (previous clip as reference)

### Step 7: Adapt for Product
- Rewrite dialogue preserving conversational patterns, line count, and energy arc
- Replace product-specific claims; match word count closely (±3 words)
- Read aloud to verify pacing fits target duration
- Update all product references

### Step 8: Confirm Dialogue
MANDATORY GATE — present adapted dialogue as numbered list with beat labels. Await explicit user confirmation.

### Step 9: Audio Decision
- Enable/disable audio
- Offer voice cloning option if applicable

### Step 10: Estimate Credits
- Reference `logs/arcads-api.jsonl` for historical rates
- Reference rate tables in `reference.md`
- Present credit breakdown. Await user confirmation.

### Step 11: Session Setup and Upload
1. Create project folder via `POST /v1/folders`
2. Create project via `POST /v1/projects`
3. Upload reference images/videos via presigned URLs

### Step 12: Generate and Present
1. Fire API calls
2. Poll status concurrently
3. Stitch multi-clip outputs if needed
4. Log all calls to `logs/arcads-api.jsonl`
5. Present results with URLs

## Multi-Clip Chaining Rules

For source videos > 15 seconds:
- Clip 1: **i2v mode** with product image reference
- Clips 2+: **v2v mode** chaining from previous clip's output
- Each clip ≤ 15 seconds
- Sequential generation (NOT parallel)
- Upload each completed clip fresh before using as reference

## Critical Technical Constraints

- `referenceImages` and `referenceVideos` are mutually exclusive in one request
- v2v with human faces triggers content checker rejection
- `audioEnabled: true` + `referenceImages` may fail — sanity probe first
- Prompt length: 100–260 words
- Forbidden words: "cinematic," "professional," "stunning," "8k," "studio," "perfect"
