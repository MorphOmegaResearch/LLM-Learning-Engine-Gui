#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Load overrides if present
if [[ -f .env ]]; then source .env; fi

BIN="${BIN:-bin/main}"
MODEL="${MODEL:-models/qwen2.5-0.5b.Q4_K.gguf}"
CTX="${CTX:-256}"
LAYERS="${LAYERS:-4}"

if [[ ! -x "$BIN" ]]; then
  echo "ERR: llama.cpp main not found/executable at $BIN" >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERR: model GGUF not found at $MODEL" >&2
  exit 1
fi

# For Vulkan builds no special env is needed; if CUDA build is present and flaky, prefer Vulkan binary.
# Start with minimal GPU layers; increase if stable.
exec "$BIN" -m "$MODEL" --ctx-size "$CTX" --n-gpu-layers "$LAYERS" "$@"

