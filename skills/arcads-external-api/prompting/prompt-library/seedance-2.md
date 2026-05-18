# Seedance 2.0 Model Guide

## Core API Details

- **Endpoint:** `POST /v2/videos/generate` with `"model": "seedance-2.0"`
- **Polling:** `GET /v1/assets/{id}` — statuses: `pending` → `generated` / `failed`
- **Duration:** 4–15 seconds (continuous range, not preset values)

## Key Parameters

Required:
```json
{
  "model": "seedance-2.0",
  "productId": "uuid",
  "prompt": "..."
}
```

Optional:
- `aspectRatio`: `"9:16"` (default)
- `resolution`: `"720p"` (default)
- `referenceImages`: up to 3 (mutually exclusive with `referenceVideos`)
- `referenceVideos`: up to 3 (mutually exclusive with `referenceImages`)
- `referenceAudio`: up to 3

## Prompt Strategy

Structure: **Subject + Action + Camera + Style + Constraints**

- Optimal word count: 100–260 words
- Use explicit motion language: "slowly," "deliberately," "deliberately eases" — not "moves"
- For multi-beat sequences, add timestamps to clarify pacing
- Reference images embed via `@(img1)` tokens in prompt text, paired with uploaded file paths

## Forbidden Words

Do NOT use in prompts: `cinematic`, `professional`, `stunning`, `8k`, `studio`, `perfect`

## Critical Constraints

- `referenceImages` and `referenceVideos` are mutually exclusive in the same request
- Product consistency requires explicit instructions to prevent visual drift

## Style Templates

See dedicated files for:
- `seedance-2-ugc.md` — authentic UGC testimonials
- `seedance-2-feature-walkthrough.md` — product feature demos
- `seedance-2-premium-reveal.md` — dramatic product launches
- `seedance-2-product-hero.md` — product-only hero shots
- `seedance-2-studio-lookbook.md` — polished brand film style

## Pre-Submission Checklist

- [ ] Word count 100–260
- [ ] Duration fits 4–15s
- [ ] Motion is explicit (no vague terms)
- [ ] Style anchors are present
- [ ] No forbidden words
- [ ] Reference constraint respected (images OR videos, not both)
