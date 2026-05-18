# Influencer Recreation from Reference Image

Structured workflow for recreating a person's likeness in AI-generated content using Arcads.

## Mandatory 6-Step Process

### Step 1: Image Analysis
Systematically examine and document:
- Facial features: face shape, eyes, nose, lips, jawline
- Hair: color, length, style, texture
- Makeup: style and colors (if applicable)
- Body: build, proportions
- Clothing: style, fit, colors
- Lighting: quality, direction, color temperature
- Overall aesthetic: mood, energy

### Step 2: Prompt Writing
Craft 80–150 word description using specific visual language:
- Describe "lighting as physics" (not just "warm lighting" but "diffused window light from the left creating a soft shadow under the jaw")
- Include texture details for realism
- Avoid using real names or celebrity identifiers

### Step 3: User Approval
Present your analysis and proposed prompt. Wait for feedback. Revise if needed.

### Step 4: Still Image Generation
```
POST /V2/images/generate
{
  "productId": "uuid",
  "model": "nano-banana-2",
  "prompt": "...",
  "refImageAsBase64": "[base64 encoded reference photo]",
  "aspectRatio": "9:16"
}
```
Poll `GET /v1/assets/{id}` until `generated`.

### Step 5: Still Approval
Show result to user. HARD STOP — do not generate video without explicit sign-off.
QA loop: inspect + up to 2 retries if defects found.

### Step 6: Video Generation
Only after still approval:
1. Upload approved still via presigned URL pipeline
2. Generate video using Veo 3.1 (`startFrame`) or Sora 2

## Prompt Guidelines

- Use specific visual language (not vague descriptors)
- Describe lighting as physics — direction, quality, temperature
- Include texture details: pore visibility, hair strand behavior, fabric weight
- Avoid real names or celebrity identifiers

## Consistency

Save approved prompts in `MASTER_CONTEXT.md` to enable reuse across future sessions without re-analysis.
