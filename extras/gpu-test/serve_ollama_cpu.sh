#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ -f .env ]]; then source .env; fi
MODEL="${MODEL:-/home/commander/Desktop/Trainer/exports/gguf/Qwen2.5-0.5b-Instruct-merged-training_Tools_Qwen2.5-0.5b_20251009_201739.Q5_K_M.gguf}"
PORT="${PORT:-11435}"
NAME="${NAME:-gpu-test-local}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ERR: ollama CLI not found" >&2
  exit 1
fi
if [[ ! -f "$MODEL" ]]; then
  echo "ERR: MODEL not found at $MODEL" >&2
  exit 1
fi

export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_NO_GPU=1

TMPMF="ollama.Modelfile"
cat > "$TMPMF" <<EOF
FROM $MODEL
PARAMETER stop "</s>"
EOF

# Start server in background and keep it running
echo "Starting ollama serve on $OLLAMA_HOST (CPU only)"
ollama serve >/dev/null 2>&1 &
SRV_PID=$!
echo "PID: $SRV_PID"

# Wait for server
for i in {1..40}; do
  if ollama list >/dev/null 2>&1; then break; fi
  sleep 0.2
done

# Create model if missing
if ! ollama list | awk '{print $1}' | grep -qx "$NAME"; then
  ollama create "$NAME" -f "$TMPMF"
fi

echo "Model '$NAME' ready. Example: OLLAMA_HOST=$OLLAMA_HOST ollama run $NAME 'hello'"
wait $SRV_PID

