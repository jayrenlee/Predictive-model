#!/usr/bin/env bash
# Batch YouTube thumbnail generator using Arcads Nano Banana 2
# Usage: bash scripts/generate-batch.sh
# Requires: .env with ARCADS_API_KEY, imagemagick (convert), curl, jq

set -euo pipefail

# Load credentials
if [[ ! -f ".env" ]]; then
  echo "Error: .env file not found. Run scripts/setup.sh first." >&2
  exit 1
fi
source .env

if [[ -z "${ARCADS_API_KEY:-}" ]]; then
  echo "Error: ARCADS_API_KEY not set in .env" >&2
  exit 1
fi

BASE_URL="${ARCADS_BASE_URL:-https://external-api.arcads.ai}"
AUTH_HEADER="Authorization: Basic $(echo -n "${ARCADS_API_KEY}:" | base64 -w0)"

# ─── CONFIGURE THESE ─────────────────────────────────────────────────────────
PRODUCT_ID="YOUR_PRODUCT_ID_HERE"     # Get from GET /v1/products

# Reference image paths (5+ face references for accuracy)
REF_BASE="references/face"
COMMON_REFS=(
  "${REF_BASE}/01-front.jpg"
  "${REF_BASE}/02-angle.jpg"
  "${REF_BASE}/03-side.jpg"
)

# Thumbnail prompts to generate
PROMPTS=(
  "PROMPT_1_HERE"
  "PROMPT_2_HERE"
  "PROMPT_3_HERE"
)
# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_DIR="output/thumbnails-$(date +%Y%m%d-%H%M%S)"
mkdir -p "${OUTPUT_DIR}"

upscale_image() {
  local src="$1"
  local dst="$2"
  local min_size=1080
  local w h longer

  w=$(identify -format "%w" "$src")
  h=$(identify -format "%h" "$src")
  longer=$(( w > h ? w : h ))

  if (( longer < min_size )); then
    local scale
    scale=$(echo "scale=4; ${min_size} / ${longer}" | bc)
    convert "$src" -filter Lanczos -resize "${scale}x${scale}%" -colorspace RGB -type TrueColor JPEG:"$dst"
  else
    convert "$src" -colorspace RGB -type TrueColor JPEG:"$dst"
  fi
}

get_presigned_url() {
  local file_path="$1"
  local ext="${file_path##*.}"
  local file_type

  case "${ext,,}" in
    jpg|jpeg) file_type="image/jpeg" ;;
    png)      file_type="image/png"  ;;
    webp)     file_type="image/webp" ;;
    *)        file_type="image/jpeg" ;;
  esac

  curl -sf -X POST "${BASE_URL}/v1/file-upload/get-presigned-url" \
    -H "${AUTH_HEADER}" \
    -H "Content-Type: application/json" \
    -d "{\"fileType\": \"${file_type}\"}"
}

upload_file() {
  local local_path="$1"
  local presigned_url="$2"
  curl -sf -X PUT "${presigned_url}" \
    -H "Content-Type: image/jpeg" \
    --data-binary "@${local_path}" > /dev/null
}

poll_asset() {
  local asset_id="$1"
  local max_wait=300
  local elapsed=0

  while (( elapsed < max_wait )); do
    local response
    response=$(curl -sf "${BASE_URL}/v1/assets/${asset_id}" -H "${AUTH_HEADER}")
    local status
    status=$(echo "$response" | jq -r '.data.status // .status // "unknown"')

    if [[ "$status" == "generated" ]]; then
      echo "$response"
      return 0
    elif [[ "$status" == "failed" ]]; then
      echo "Asset ${asset_id} failed" >&2
      return 1
    fi

    sleep 5
    (( elapsed += 5 ))
  done

  echo "Timeout waiting for asset ${asset_id}" >&2
  return 1
}

generate_thumbnail() {
  local idx="$1"
  local prompt="$2"
  local attempt=0

  while (( attempt < 2 )); do
    echo "[${idx}] Uploading references (attempt $((attempt+1)))..."

    # Upscale + upload reference images fresh for this call
    local ref_file_paths=()
    for ref in "${COMMON_REFS[@]}"; do
      if [[ ! -f "$ref" ]]; then
        echo "Warning: reference not found: $ref" >&2
        continue
      fi
      local tmp_ref
      tmp_ref=$(mktemp /tmp/arcads-ref-XXXXXX.jpg)
      upscale_image "$ref" "$tmp_ref"

      local presign_response
      presign_response=$(get_presigned_url "$ref")
      local presigned_url file_path
      presigned_url=$(echo "$presign_response" | jq -r '.url // .presignedUrl')
      file_path=$(echo "$presign_response" | jq -r '.filePath // .key')

      upload_file "$tmp_ref" "$presigned_url"
      rm -f "$tmp_ref"
      ref_file_paths+=("$file_path")
    done

    echo "[${idx}] Generating thumbnail..."

    # Build referenceImages JSON array
    local ref_json
    ref_json=$(printf '%s\n' "${ref_file_paths[@]}" | jq -R . | jq -sc .)

    local payload
    payload=$(jq -n \
      --arg productId "$PRODUCT_ID" \
      --arg prompt "$prompt" \
      --argjson refs "$ref_json" \
      '{
        "productId": $productId,
        "model": "nano-banana-2",
        "aspectRatio": "16:9",
        "prompt": $prompt,
        "referenceImages": $refs
      }')

    local gen_response
    gen_response=$(curl -sf -X POST "${BASE_URL}/V2/images/generate" \
      -H "${AUTH_HEADER}" \
      -H "Content-Type: application/json" \
      -d "$payload") || {
      echo "[${idx}] Generation request failed" >&2
      (( attempt++ ))
      sleep 15
      continue
    }

    local asset_id
    asset_id=$(echo "$gen_response" | jq -r '.data.id // .id')

    if [[ -z "$asset_id" || "$asset_id" == "null" ]]; then
      echo "[${idx}] No asset ID in response" >&2
      (( attempt++ ))
      sleep 15
      continue
    fi

    echo "[${idx}] Polling asset ${asset_id}..."
    local final_response
    final_response=$(poll_asset "$asset_id") || {
      echo "[${idx}] Poll failed" >&2
      (( attempt++ ))
      sleep 15
      continue
    }

    local url credits
    url=$(echo "$final_response" | jq -r '.data.url // .url // ""')
    credits=$(echo "$final_response" | jq -r '.data.creditsCharged // 0')

    echo "[${idx}] Done. Credits: ${credits}. URL: ${url}"
    echo "$final_response" > "${OUTPUT_DIR}/asset-${idx}-metadata.json"

    # Log to arcads-api.jsonl
    jq -n \
      --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg assetId "$asset_id" \
      --arg url "$url" \
      --arg credits "$credits" \
      --arg productId "$PRODUCT_ID" \
      '{
        "timestamp": $ts,
        "model": "nano-banana-2",
        "endpoint": "/V2/images/generate",
        "productId": $productId,
        "assetId": $assetId,
        "creditsCharged": ($credits | tonumber),
        "status": "generated",
        "url": $url,
        "useCase": "youtube-thumbnail"
      }' >> logs/arcads-api.jsonl

    return 0
  done

  echo "[${idx}] Failed after 2 attempts" >&2
  return 1
}

# Generate all thumbnails with staggered start times
echo "Starting batch generation of ${#PROMPTS[@]} thumbnails..."
mkdir -p logs

pids=()
for i in "${!PROMPTS[@]}"; do
  sleep $(( i * 2 ))  # stagger by 2s to avoid endpoint conflicts
  generate_thumbnail "$i" "${PROMPTS[$i]}" &
  pids+=($!)
done

# Wait for all background jobs
failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || (( failed++ ))
done

echo "Batch complete. Output: ${OUTPUT_DIR}/"
if (( failed > 0 )); then
  echo "Warning: ${failed} thumbnail(s) failed." >&2
fi
