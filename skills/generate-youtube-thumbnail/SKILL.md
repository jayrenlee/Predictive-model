# Generate YouTube Thumbnail Skill

Create high-CTR YouTube thumbnails using Arcads' Nano Banana 2 image API.

## Activation Triggers

Activate this skill when user requests:
- YouTube thumbnail creation
- A/B thumbnail testing
- Thumbnail variations featuring faces, brands, or products

## Requirements Before Starting

1. Reference images saved as actual files (not chat pastes) in:
   - `references/face/` — 5+ photos from varied angles (mandatory for face accuracy)
   - `references/logos/` — brand logo files
   - `references/products/` — product images
   - `references/examples/` — example thumbnails for style reference
   - `references/style/` — aesthetic references
2. `.env` credentials configured
3. Images exceed 1080px on longest side (smaller → 422 errors)

## 8-Step Workflow

### Step 1: Gather Requirements
- Channel/video topic
- Target audience
- Desired emotional response (curiosity / urgency / authority / entertainment)
- Face(s) to feature (if any)
- Brand elements required
- Number of variations needed

### Step 2: Verify References on Disk
Confirm all reference files exist at their paths before proceeding.

### Step 3: Estimate Costs
- Each generation: 24 credits post-multiplier
- 10 parallel jobs: ~1.5–2 minutes at ~$0.72 estimate

Present credit estimate. Await user approval.

### Step 4: Select Formula

Choose from 5 proven thumbnail formulas:
1. **Reaction face** — extreme facial expression with text overlay
2. **Before/after** — split composition showing transformation
3. **Point-and-look** — person pointing at or looking toward text/element
4. **Close-up authority** — tight face crop, direct eye contact, authoritative pose
5. **Product hero + face** — product prominently featured with creator's reaction

### Step 5: Compose Prompts with Likeness Block

When featuring a real face, include the likeness block:
```
[Face description from reference analysis]. Exact likeness preservation critical.
[Expression description matching formula].
[Composition: face position, text area position, product position if applicable].
[Background and lighting].
[Text overlay instructions — keep minimal; 3–5 words max].
Photorealistic. 16:9 YouTube thumbnail crop. High contrast, vibrant colors.
```

### Step 6: Execute Batch Generation

Use `scripts/generate-batch.sh` for parallel generation (10 at a time, staggered).

**Critical:** Upload fresh reference images for each API call — reusing uploaded file paths causes HTTP 500.

### Step 7: Review Outputs
- Check face accuracy
- Check text legibility
- Check emotional impact
- Check composition at small size (150px preview)

### Step 8: Disclose Credit Totals
Report actual credits charged (from API response `creditsCharged` field). Note: this is an estimate; present as such.

## Technical Constraints

- **Image size:** Must exceed 1080px on longest side — upscale with Lanczos before submission
- **Fresh uploads:** ALWAYS upload new presigned URLs per call — never reuse paths
- **Reference files:** Must be actual saved files; chat-pasted images are inaccessible to the API
- **Brand items:** Require actual asset files — text descriptions insufficient
- **Face references:** 5+ photos from varied angles for accurate character reproduction

## Performance Benchmarks

- ~30–60 seconds per image
- 10 parallel jobs: ~1.5–2 minutes total
