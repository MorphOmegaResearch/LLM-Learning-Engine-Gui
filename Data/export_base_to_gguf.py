#!/usr/bin/env python3
"""
Export a base (PyTorch) model to GGUF for inference (no adapter merge).
"""
import os
import sys
import argparse
from pathlib import Path

import torch

# Force offline + CPU only for robustness
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
torch.set_grad_enabled(False)

def export_base_to_gguf(base_model_path: str, output_dir: str, quantization_method: str = "q4_k_m") -> str:
    print(f"🚀 Export base to GGUF\n - Base: {base_model_path}\n - Quant: {quantization_method}")
    # Try Unsloth if installed; otherwise fall back to llama.cpp converter
    use_unsloth = True
    try:
        from unsloth import FastLanguageModel  # type: ignore
    except Exception:
        use_unsloth = False
        print("[Info] Unsloth not installed; will use llama.cpp converter fallback.")

    if use_unsloth:
        try:
            # Load on CPU with a safe dtype to avoid CUDA paths
            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=base_model_path,
                load_in_4bit=False,
                torch_dtype=torch.float32,
                device_map={"": "cpu"},
            )
            out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
            base_name = Path(base_model_path).name
            gguf_path = out_dir / f"{base_name}.{quantization_method}.gguf"
            print(f"Saving GGUF: {gguf_path}")
            # Unsloth provides save_pretrained_gguf; this works on CPU too
            model.save_pretrained_gguf(str(gguf_path), tokenizer, quantization_method=quantization_method)
            print("✓ Export complete")
            return str(gguf_path)
        except Exception as e:
            print(f"🔥 Unsloth path failed: {e}")
            import traceback; traceback.print_exc()

    print("[Fallback] Trying llama.cpp converter via safe wrapper (CPU-only)…")
    # CPU-only fallback using llama.cpp converter
    try:
        # Locate converter
        candidates = [
            Path.home() / "Desktop" / "llama.cpp" / "convert_hf_to_gguf.py",
            Path.cwd() / "llama.cpp" / "convert_hf_to_gguf.py",
            Path(__file__).parent.parent / "llama.cpp" / "convert_hf_to_gguf.py",
        ]
        converter = None
        for p in candidates:
            if p.exists():
                converter = p; break
        if not converter:
            print("ERROR: llama.cpp convert_hf_to_gguf.py not found. Install llama.cpp or place the script locally.")
            return ""
        # Prefer using the original converter location so its gguf-py is discoverable
        out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
        base_name = Path(base_model_path).name
        desired_quant = (quantization_method or "Q5_K_M").upper()
        if not desired_quant.startswith('Q'):
            desired_quant = 'Q5_K_M'
        gguf_path = out_dir / f"{base_name}.{desired_quant}.gguf"
        safe_wrapper = Path(__file__).parent / 'tools' / 'safe_convert_hf_to_gguf.py'
        cmd = [
            sys.executable, str(safe_wrapper),
            '--converter', str(converter),
            str(base_model_path),
            '--outtype', desired_quant,
            '--outfile', str(gguf_path),
        ]
        print("[Fallback] Running:", " ".join(cmd))
        import subprocess
        env = os.environ.copy()
        env['HF_HUB_OFFLINE'] = '1'
        env['HUGGINGFACE_OFFLINE'] = '1'
        proc = subprocess.run(cmd, env=env)
        if proc.returncode == 0 and gguf_path.exists():
            print("✓ Fallback export complete")
            return str(gguf_path)
        print("ERROR: llama.cpp conversion failed.")
        return ""
    except Exception as e2:
        print(f"🔥 Fallback failed: {e2}")
        import traceback; traceback.print_exc()
        return ""

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--output", default=str(Path(__file__).parent / "exports" / "gguf"))
    p.add_argument("--quant", default="q4_k_m")
    args = p.parse_args()
    out = export_base_to_gguf(args.base, args.output, args.quant)
    # Exit non-zero if export failed so caller can handle fallback/prompt
    sys.exit(0 if out else 1)
