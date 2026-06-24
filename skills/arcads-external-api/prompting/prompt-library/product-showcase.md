# Product Showcase — AI Person with Product

Workflow for generating videos of AI characters demonstrating physical products.

## 5-Stage Process

### Stage 1: Information Gathering
Collect:
- Product images (preferably clean, neutral background)
- Product context (what it does, key features)
- Video intent (what should viewer feel/do)
- Person description (or existing character from `references/`)
- Engine preference (Nano Banana 2 or Pro)

### Stage 2: Prompt Composition
Create Nano Banana image prompt including:
- Person description (with skin realism cues)
- Product interaction context: "natural grip with fingertips" (prevents AI hand-pose errors)
- Where product is in frame
- Setting and lighting
- Camera angle

Include product photo as base reference.

### Stage 3: Still Image Generation
```
POST /V2/images/generate
{
  "productId": "uuid",
  "model": "nano-banana-2",
  "prompt": "...",
  "refImageAsBase64": "[base64 product photo]",
  "aspectRatio": "9:16"
}
```

QA: inspect hand positioning, product edges, proportions. Up to 2 retries.

**Tips for cleaner results:**
- Use product photos with neutral backgrounds
- Include "natural grip with fingertips" language for hand accuracy
- Save approved person descriptions for consistency across multiple shoots

### Stage 4: User Approval
HARD STOP — display QA-passed still and wait for explicit sign-off before video generation.

### Stage 5: Video Creation
1. Upload approved still via presigned URL
2. Generate video with Veo 3.1, Sora 2, or Kling 3.0
3. Video prompt should "reference the starting frame" and integrate:
   - Natural motion cues (3–4 minimum)
   - Dialogue incorporating product features
   - Marketing context from product brief

## Prompt Template (Nano Banana Stage)

```
[Age]-year-old [gender]. [Skin realism: visible pores, slight unevenness, minor undereye shadows].
Holding [product name] with natural grip, fingertips visible on packaging.
[How product is positioned: label facing camera / held at chest height / raised toward viewer].
Setting: [location]. Lighting: [quality, source, direction].
[Background: lived-in, not staged]. [Camera angle].
Composition: [e.g., waist-up frame, product in lower third].
Natural, unposed — feels like a candid moment.
```
