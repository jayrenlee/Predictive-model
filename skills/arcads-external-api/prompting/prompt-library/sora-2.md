# Sora 2 Prompting Guide

## API Route

- **Endpoint:** `POST /v2/videos/generate` with `"model": "sora-2"`
- Reference: OpenAI Sora 2 official prompting guide

## Pre-Prompt Checklist

- [ ] Subject & Setting: clear subject and setting; camera behavior described (not just "cinematic")
- [ ] Motion Details: specify what moves versus what remains static
- [ ] Visual Elements: explicitly state lighting and style choices
- [ ] Reference Images: if using `refImageAsBase64`, clarify how motion should interact with that base

## Prompt Template

```
[Hook]. [Subject] in [Setting]. Camera: [Movement]. Lighting: [Type]. 
Style: [Aesthetic]. Audio mood: [Tone]. End on [Final Image].
```

## Example

"Woman holds vitamin bottle to camera, direct eye contact. Bright bathroom, morning light. Camera: slow push-in, shallow depth of field. Lighting: warm, trustworthy. Style: authentic home video. Audio: soft upbeat ambient. End on product label close-up."

## Required JSON Parameters

```json
{
  "productId": "uuid",
  "prompt": "...",
  "aspectRatio": "9:16",
  "duration": 15
}
```

Duration options: 4–20 seconds (enum values — confirm exact supported values from reference.md).
