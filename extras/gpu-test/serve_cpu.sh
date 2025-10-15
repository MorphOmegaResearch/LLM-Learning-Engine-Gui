#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .env ]]; then source .env; fi

BIN="${BIN_SERVER:-bin/server}"
MODEL="${MODEL:-models/qwen2.5-0.5b.Q4_K.gguf}"
PORT="${PORT:-8095}"
CTX="${CTX:-256}"

if [[ ! -x "$BIN" ]]; then
  echo "ERR: llama.cpp server not found/executable at $BIN" >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERR: model GGUF not found at $MODEL" >&2
  exit 1
fi

export CUDA_VISIBLE_DEVICES=""

echo "Starting CPU server on port $PORT (ctx=$CTX)"
exec "$BIN" -m "$MODEL" --port "$PORT" --ctx-size "$CTX" --n-gpu-layers 0 "$@"

