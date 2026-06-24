# Nano Banana Image Generation Guide

## API Basics

- **Endpoint:** `POST /V2/images/generate` (uppercase V2)
- **Polling:** `GET /v1/assets/{id}` until status = `generated`
- **Generation time:** ~35 seconds

## Model Options

| Model field | When to use |
|------------|-------------|
| `nano-banana-2` | Default for all use cases |
| `nano-banana` | Only when user explicitly requests Pro |

Ask users once at session start whether they prefer Pro.

## Required Request Fields

```json
{
  "productId": "uuid",
  "prompt": "...",
  "model": "nano-banana-2",
  "aspectRatio": "9:16"
}
```

Aspect ratios: `1:1`, `16:9`, or `9:16`

Optional: reference images, project assignment

## Prompt Structure

```
{{SUBJECT}}. Style: {{STYLE}}. Composition: {{COMPOSITION}}. Lighting: {{LIGHT}}. Background: {{BG}}. Avoid: {{AVOID}}.
```

- Style options: `photoreal`, `illustration`, `product hero`
- Avoid requesting text on images unless your pipeline handles legible rendering

## Quality Assurance Requirements

Inspect every generated image for:
- Hand/finger counts
- Limb duplication
- Facial distortions
- Object artifacts
- Rendering issues

Maximum 3 total generations per deliverable (initial + 2 retries). Each generation is a separate charge.
