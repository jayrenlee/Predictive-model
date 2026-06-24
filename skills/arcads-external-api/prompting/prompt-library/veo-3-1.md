# Veo 3.1 Prompting Guide

## API Route

- **Endpoint:** `POST /v2/videos/generate` with `"model": "veo-3.1"`
- Reference: Google Cloud official Veo prompting guide

## Key Requirements

Describe three essential elements:
1. The opening scene
2. How action unfolds across frames
3. Stylistic choices

**Critical:** Always conclude prompts with: `No subtitles, no captions, no text overlays.`

## Prompt Template

```
[Opening shot]. [Temporal progression over 8 seconds]. Setting: [Location details]. 
Camera: [Technique and movement]. Style: [Visual aesthetic]. Lighting: [Quality and source]. 
[Optional dialogue or audio cues]. No subtitles, no captions, no text overlays.
```

## Example

"Woman on sunlit rooftop looks out over city skyline. Over 8 seconds she turns to camera, smiles, and holds up product. Camera: handheld slow push-in. Style: warm lifestyle documentary. Lighting: golden hour, soft directional. No subtitles, no captions, no text overlays."

## Veo 3.1 Modes

| Mode | When to use | Parameter |
|------|------------|-----------|
| `startFrame` | Animate a specific person/scene from a still | `startFrame: base64` |
| `referenceImages` | Apply a visual style from reference images | `referenceImages: [...]` |

**Never combine both** — pick one or neither.

## Required JSON Parameters

```json
{
  "productId": "uuid",
  "prompt": "...",
  "resolution": "720p",
  "aspectRatio": "9:16"
}
```

Duration: auto-determined (~8 seconds typical), costs ~1.0 credit flat.
