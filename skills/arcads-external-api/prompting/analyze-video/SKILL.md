# Analyze Video — Style Template Generator

Reverse-engineer video styles into reusable Seedance 2.0 prompting templates.

## When to Use

User provides a reference video they want to replicate in style (not content).

## 7-Step Workflow

### Step 1: Extract Frames & Audio
```bash
# Extract 8–20 frames depending on video duration
ffmpeg -i input.mp4 -vf "fps=1" frames/frame_%04d.jpg

# Extract audio for transcription
ffmpeg -i input.mp4 -vn -acodec mp3 audio.mp3
```

### Step 2: Transcribe Dialogue
Use whisper or equivalent to capture exact speech patterns and pacing:
```bash
whisper audio.mp3 --output_format txt
```

### Step 3: Study Reference Templates
Read the matching style template(s) from `../prompt-library/` to understand required structural depth:
- UGC → `seedance-2-ugc.md`
- Premium → `seedance-2-premium-reveal.md`
- Feature → `seedance-2-feature-walkthrough.md`

### Step 4: Analyze Extracted Frames

Document across 7 dimensions:

1. **Structure/Pacing:** How many beats? How long each? Jump cuts or continuous?
2. **Camera/Framing:** Angle, distance, movement, stability
3. **Edit Style:** Cut frequency, transition type, visual rhythm
4. **Dialogue:** Word count, speech rhythm, emotional arc, key phrases
5. **Tone:** Energy level, personality, formality
6. **Lighting:** Quality, direction, sources, naturalness
7. **Distinguishing Traits:** What makes this style immediately recognizable

### Step 5: Build the Template

Create a reusable markdown template including:
- **Definition:** What makes this style distinctive (2–3 sentences)
- **Layer-by-layer patterns** with `{{VARIABLES}}`
- **Option banks:** Curated choices fitting the style (not open-ended blanks)
  - Bad: "Any lighting"
  - Good: "natural window light / golden hour balcony / overhead kitchen"
- **Beat structure:** Source pacing mapped to 15-second Seedance 2.0 format
- **Multi-clip strategy** (if source > 15s): how to split narrative across clips
- **Tone & pacing guide** with speech patterns and energy calibration
- **Technical specs:** Lighting, camera quality, audio authenticity
- **Complete template block** ready for copy-paste prompt generation
- **Example prompts** using DIFFERENT products/people/settings than source

### Step 6: Save to Prompt Library
Save as `../prompt-library/seedance-2-{style-name}.md` with adaptation checklist.

### Step 7: Submit via API
Test with a validation prompt before delivering the final template.

## Critical Constraint

Seedance 2.0 maximum: **15 seconds per clip**. Source videos are often 30–60 seconds.
Template must distill essence into 15-second output:
- Maximum 3 beats
- 2–3 dialogue lines
- For longer styles: multi-clip strategy (each 15s clip stands alone)

## Template Variable Quality Standard

Variables must be meaningful choices tied to this specific style:
- "Any lighting" = useless
- "natural window light / golden hour balcony / overhead kitchen" = good

Variables should preserve:
- Voice patterns
- Dialogue rules
- Platform compliance (100–260 word prompts, forbidden words, explicit motion, product image syntax)
