# Arcads External API Reference

## Core Authentication & Access

HTTP Basic authentication using your API key as the username with an empty password.
- Store key in `ARCADS_API_KEY` environment variable
- Never commit to version control
- Base endpoint: `https://external-api.arcads.ai`
- Can be overridden via `ARCADS_BASE_URL`

## Video Generation — Unified v2 Endpoint

All video models route through: `POST /v2/videos/generate`

Supported models via `model` field:
- `sora-2`
- `sora-2-pro`
- `veo-3.1`
- `kling-2.6`
- `kling-3.0`
- `grok-video`
- `seedance-2.0`

Each uses the `CreateVideoDto` request body.

## Image Generation

Still images: `POST /V2/images/generate` (note uppercase V2)

Primary model: Nano Banana
- `nano-banana-2` (default)
- `nano-banana` (Pro)

Response includes presigned S3 URL once asset reaches `generated` status.

## Pricing & Performance (2026-04-09 Snapshot)

| Model | Credits/second | Generation speed | Audio |
|-------|---------------|-----------------|-------|
| Grok Video | 0.027 | ~5s for 3s video | Silent only |
| Sora 2 | 0.05 | — | Speech supported |
| Seedance 2.0 (i2v) | 0.06 | — | Audio ref supported |
| Seedance 2.0 (v2v) | 0.1 | — | Audio ref supported |
| Veo 3.1 | ~0.125 | ~8s auto-duration | ~1.0 credit flat |
| Nano Banana 2 | 0.03/image | ~35s | N/A |

## Known Issues & Workarounds

**Image-input regression:** Most models fail when using image references via v2 endpoint. Only Kling 3.0 with `startFrame` and Seedance 2.0 with `referenceImages` work reliably for image-to-video.

**Seedance 2.0 constraints:**
- Cannot mix `referenceVideos` and `referenceImages` in the same request
- Multiple reference videos (2+) return HTTP 500; use single references or chain sequential calls

**Kling 3.0 `endFrame` broken:** Do not use `endFrame` alone (triggers billed failure) or combined with `startFrame` (returns 500).

## Polling & Asset Delivery

- Videos: `GET /v1/videos/{videoId}` — includes `videoUrl`, `videoStatus`
- Other assets: `GET /v1/assets/{id}` — statuses: `created` → `pending` → `generated` or `failed`
- Check `creditsCharged` in response data

## File Uploads

Use `POST /v1/file-upload/get-presigned-url` with `fileType` field (not `contentType`) to receive presigned S3 URL and `filePath`.

Supported types:
- Images: JPEG, PNG, WebP, HEIC
- Videos: MP4, MOV, WebM
- Audio: MP3, WAV, AAC, FLAC

## Project Organization

1. Create folders: `POST /v1/folders`
2. Create projects inside: `POST /v1/projects`
3. Assign assets: `POST /v1/assets/add-to-project`

## Error Handling

| Code | Meaning |
|------|---------|
| 401/403 | Authentication failure |
| 404 | Resource doesn't exist |
| 422 | Validation or content moderation block |
| 500 | Retry; some failures (Seedance 2.0 content checks) may not refund credits |

## Log Format

Append to `logs/arcads-api.jsonl` after every API call:

```json
{
  "timestamp": "ISO-8601",
  "model": "model-name",
  "endpoint": "/v2/videos/generate",
  "productId": "uuid",
  "projectId": "uuid",
  "assetId": "uuid",
  "creditsCharged": 1.0,
  "generationSeconds": 42,
  "status": "generated",
  "url": "https://..."
}
```
