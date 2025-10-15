GPU Test Harness (Side-by-Side, No System Changes)

Goal
- Safely test tiny models with CPU and optional partial GPU offload without touching your working app, drivers, PATH, or configs.

Design
- Self-contained folder: separate binaries, model copy, and unique server port.
- CPU-first scripts; optional Vulkan partial offload scripts if you have a Vulkan-enabled llama.cpp build.
- No global installs; nothing writes outside this folder.

Folder layout
- bin/               # place portable llama.cpp binaries here (main, server)
- models/            # copy a tiny GGUF here (e.g., qwen2.5-0.5b.Q4_K.gguf)
- run_cpu.sh         # one-off prompt on CPU only
- run_gpu_vulkan.sh  # one-off prompt with minimal GPU offload (Vulkan build)
- serve_cpu.sh       # start server on port 8095 (CPU)
- serve_gpu_vulkan.sh# start server on port 8095 (Vulkan partial GPU)
- .env.example       # optional overrides (MODEL, PORT, LAYERS, CTX)

Prereqs
1) Copy binaries into bin/ (portable builds):
   - bin/main   (llama.cpp main)
   - bin/server (llama.cpp server)
   Prefer a Vulkan build for old/iffy GPUs; CPU build works for sanity.
2) Copy a tiny GGUF into models/: qwen2.5-0.5b.Q4_K.gguf (or similar).

Commands (safe)
- CPU sanity (one-off):
  ./run_cpu.sh -p "hello world"

- Minimal Vulkan offload (one-off):
  ./run_gpu_vulkan.sh -p "hello world"  # defaults to 4 GPU layers

- CPU server (separate port, does not affect your app):
  ./serve_cpu.sh

- Vulkan server (partial GPU offload):
  ./serve_gpu_vulkan.sh

Notes
- Models are loaded read-only from ./models; your main app is untouched.
- Server listens on 8095 by default; keep your app pointed at its own CPU path.
- If Vulkan is unstable: reduce LAYERS in .env or use CPU scripts.

Overrides
- Copy .env.example to .env and edit:
  MODEL=models/qwen2.5-0.5b.Q4_K.gguf
  PORT=8095
  LAYERS=4
  CTX=256

Rollback
- Stop the test scripts; delete extras/gpu-test/ if you’re done. No system changes.

