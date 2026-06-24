# UGC Product Selfie — Nano Banana 2

Workflow for generating UGC-style selfie images combining AI influencers, products, and aesthetic references.

## Reference Requirements

Need 4–6 reference images:
1. **Character hero photo** (identity anchor) — at least 1
2. **Product image** — at least 1
3. **Style references** — 2–4 to establish visual tone

Upload all via presigned S3 URLs before generation.

## Prompt Structure

### Character Description (Required)
Include skin realism cues inline (not as afterthoughts):
```
[Age]-year-old [gender] with [hair]. Visible pores, slight unevenness in skin tone, 
minor undereye shadows, a hint of shine from natural oils. [Other distinguishing features].
```

### Product Context
```
Holding [product name] [how: in palm / to chest / raised toward camera]. 
[Specific grip: natural grip with fingertips]. [Where product is in frame].
```

### Setting
```
[Environment: bathroom mirror / outdoor wall / home interior].
[Lighting: natural window light / golden hour / soft overhead].
```

### Imperfection Block (Non-Negotiable — 4–5 elements)
```
Motion blur on edges, grain, slight overexposure near light source, soft focus on background, 
off-center framing, autofocus on [face/product].
This must look like an unedited frame pulled from a real iPhone selfie video, NOT a professional photo.
```

### Negative Cues
```
No retouching, no beauty filter, no studio lighting, not a professional photo.
```

## Generation Parameters

```json
{
  "model": "nano-banana-2",
  "aspectRatio": "9:16",
  "prompt": "..."
}
```

Generate 3 variations (default). Cost: 0.09 credits total (~$0.09).

## Video Integration

To animate an approved still:
- Use **Veo 3.1 with `startFrame`** to preserve character face, pose, and scene from frame one
- Include 3–4 human motion cues in the Veo prompt:
  - Eye contact shifts
  - Head tilts
  - Product adjustments
  - Weight shifts
- Default to 720p resolution for UGC-style content
