# Arcads API — Master Context

Auto-generated workspace context. Read this file at the start of every session before any substantive work.
Append a dated changelog entry after meaningful changes.

---

## Agent Workflow

1. Read this file at session start
2. Check `logs/arcads-api.jsonl` for credit usage history
3. Append dated changelog entries after meaningful changes
4. Offer to populate empty fields below with user input

---

## Brand & References

### Brand Voice
**Brand name:** [Not yet configured]
**Tone:** [Not yet configured]
**Audience:** [Not yet configured]
**Words to embrace:** [Not yet configured]
**Words to avoid:** [Not yet configured]

See `skills/arcads-external-api/prompting/brand-voice-starter.md` to populate this section.

### References Folder Structure

```
references/
├── influencers/     # AI character reference sheets
├── products/        # Product photos for generation
├── aesthetics/      # Mood boards and style references
```

---

## Universal Prompting Principles

### Realistic UGC Output
- **Camera imperfections:** grain, motion blur, soft focus, autofocus breathing
- **Skin realism:** visible pores, slight unevenness, minor undereye shadows — avoid medical descriptors
- **Character approval:** get user sign-off on still image before generating video
- **Human motion cues:** include at least 3–4 per prompt — eye contact shifts, head tilts, weight shifts, product adjustments

### Preventing "Frozen Mannequin" Results
Always include explicit motion language. Not "she holds the product" but "she shifts her grip slightly, label rotating toward camera as she speaks."

---

## API Learnings

### Authentication
```
Authorization: Basic <base64(ARCADS_API_KEY:)>
```
- `.env` values must use single quotes if they contain special characters

### Key Endpoints
| Action | Endpoint |
|--------|---------|
| Image generation | `POST /V2/images/generate` (uppercase V2) |
| Video generation | `POST /v2/videos/generate` |
| Asset polling | `GET /v1/assets/{id}` |
| Video polling | `GET /v1/videos/{videoId}` |
| File upload | `POST /v1/file-upload/get-presigned-url` |
| Products | `GET /v1/products` |
| Folders | `POST /v1/folders` |
| Projects | `POST /v1/projects` |
| Add to project | `POST /v1/assets/add-to-project` |

### Credit Cost Reference (2026)
| Model | Cost |
|-------|------|
| Grok Video | 0.027 credits/second |
| Sora 2 | 0.05 credits/second |
| Seedance 2.0 (i2v) | 0.06 credits/second |
| Seedance 2.0 (v2v) | 0.10 credits/second |
| Veo 3.1 | ~1.0 credit flat (~8s) |
| Nano Banana 2 | 0.03 credits/image |
| YouTube Thumbnail | ~24 credits post-multiplier |

---

## Successful Prompts Log

| Date | Model | Use Case | Key prompt elements | Notes |
|------|-------|---------|-------------------|-------|
| | | | | |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05-18 | Initial MASTER_CONTEXT.md created from template |
