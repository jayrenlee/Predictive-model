# Character Sheet Generation

Creates a 10-image AI influencer reference set from a text description.

## Process (Do Not Skip Steps)

1. **User describes** influencer in plain English
2. **Agent expands** into detailed visual prompt with specific attributes:
   - Age, hair color/style/length
   - Skin tone and texture
   - Eye color and shape
   - Build and height
   - Makeup style (if any)
   - Clothing (default: fitted white t-shirt)
3. **User reviews** expanded prompt — wait for approval before continuing
4. **Generate hero image** — full-body front view, white studio background
5. **User approves hero** — HARD STOP; do not proceed without explicit sign-off
6. **Generate 9 angle variations** using hero as `refImageAsBase64`:
   - 01-hero-front (already done)
   - 02-three-quarter-right
   - 03-profile-right
   - 04-three-quarter-left
   - 05-profile-left
   - 06-front-closeup-face
   - 07-over-shoulder-back
   - 08-looking-down
   - 09-looking-up
   - 10-above-angle
7. **QA all 10 images** for consistency and anatomy
8. **Save to folder** using naming convention below

## Prompt Requirements

- **Background:** White studio background throughout
- **Style:** Photorealistic with visible texture details (individual hair strands catching light)
- **Constraints:** No celebrity names or real people references
- **Clothing:** Simple, neutral (default: fitted white t-shirt) to focus on character

## Folder Structure

```
references/influencers/{name}-{hair_color}-{hair_style}-{feature}-{eye_color}-{skin_tone}/
```

Example: `references/influencers/emma-redhead-wavy-freckles-green-eyes-fair/`

Files numbered: `01-hero-front.jpg` through `10-above-angle.jpg`

## Credit Cost

- 10 generations × 0.03 credits = **0.30 credits total**
- Plus 0.03 per QA retry

## Reuse Value

Once saved, the character sheet supports:
- Product showcases
- Video generation (use hero as `startFrame` for Veo 3.1)
- UGC content
- Influencer recreation workflows
