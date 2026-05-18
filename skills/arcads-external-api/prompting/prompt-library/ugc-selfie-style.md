# UGC Selfie-Style Video — Cross-Model Prompting Guide

How to prompt AI video models to generate authentic UGC. Core insight: **authenticity requires deliberate imperfection**.

## 4 Universal Principles

### 1. Smartphone Simulation
Specify iPhone optics, not cinematic terminology:
- "iPhone front camera, wide-angle, slight lens distortion at edges"
- Include: grain, autofocus breathing, slight edge distortion
- Avoid: "cinematic," "professional," "shallow depth of field"

### 2. "Accidental" Framing
- Awkward angles (slightly off-center, chin-up)
- Cluttered backgrounds
- Mediocre composition that mimics how real people film themselves

### 3. Natural Human Movement (Critical)
Include at least 3–4 motion cues per prompt:
- **Eye behavior:** "glances away, refocuses on lens, blinks naturally"
- **Head movement:** "slight nod when making point, head tilt"
- **Body shifts:** "shifts weight, leans in slightly"
- **Scene transitions:** "repositions phone between beats"

### 4. Negative Prompting
Explicitly exclude: "studio lighting, professional photography, cinematic, color graded, stabilization"

## Model-Specific Approaches

### Veo 3.1
- Scene/shot design with timestamps
- Prompts: 75–125 words
- Always end with: `No subtitles, no captions, no text overlays.`

```
[0s]: [Opening action]. Camera: [iPhone specs]. 
[2s]: [Second beat action with motion cue].
[5s]: [Third beat]. [Natural human movement description].
[7s]: [Close with product or CTA].
No subtitles, no captions, no text overlays.
```

### Sora 2
- Structured headers and second-by-second action beats

```
SETTING: [Specific room detail]
PERSON: [Description with imperfections]
0–3s: [Action + dialogue if any]
3–6s: [Action beat]
6–10s: [Action + dialogue]
STYLE: Natural phone video. [Flaw list]. No studio elements.
```

### Kling 3.0
- Physics-based descriptions
- Texture detail to avoid hand morphing and artificial movement

```
[Subject] in [real environment]. [Physical action with friction/weight language].
Hand: [specific grip description]. Eyes: [specific gaze behavior].
Skin: [texture markers]. Camera: [iPhone specs + imperfections].
Avoid: studio lighting, stabilization, professional photography.
```

## Instagram Reels Final Checklist

- [ ] 9:16 aspect ratio
- [ ] Strong 2-second hook (attention in first frames)
- [ ] Natural lighting terminology (not "studio" or "professional")
- [ ] Handheld camera indicators present
- [ ] Visible flaws specified (grain, motion blur, etc.)
- [ ] 3–4 human motion cues included
- [ ] Negative prompts for polish present
