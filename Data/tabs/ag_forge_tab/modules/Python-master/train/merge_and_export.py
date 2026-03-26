#!/usr/bin/env python3
"""
Merge a base model with a LoRA adapter and export to GGUF.
"""

import torch
import os
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil

# Defer Unsloth import so we can provide a clear error if unavailable
def _get_unsloth_fast_model():
    try:
        from unsloth import FastLanguageModel  # type: ignore
        return FastLanguageModel
    except Exception:
        # Stay quiet and let the caller attempt a CPU + llama.cpp fallback.
        # This keeps the export fully local without implying network/GPU needs.
        return None

# Add project root to path to allow imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from Data.config import MODELS_DIR

def merge_and_export(base_model_path: str, adapter_path: str, output_dir: str, quantization_method: str = "q4_k_m") -> str:
    """Merges a LoRA adapter into a base model and exports to GGUF."""
    print(f"🚀 Starting merge and export process...")
    print(f"   - Base Model: {base_model_path}")
    print(f"   - Adapter: {adapter_path}")
    print(f"   - Output Dir: {output_dir}")
    print(f"   - Quantization: {quantization_method}")

    try:
        FastLanguageModel = _get_unsloth_fast_model()
        # Use Unsloth path only if module is present AND GPU is available
        if FastLanguageModel is None or not torch.cuda.is_available():
            print("[Export] Using CPU merge + llama.cpp converter (Unsloth/GPU not available).")
            return _cpu_merge_and_convert(base_model_path, adapter_path, output_dir, quantization_method)
        # Load the base model
        print("\nStep 1: Loading base model...")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model_path,
            load_in_4bit=False, # Must load in float16 or bfloat16 for merging
            torch_dtype=torch.float16,
        )
        print("✓ Base model loaded.")
        # Load and merge the LoRA adapter into the base
        print("\nStep 2: Loading + merging LoRA adapter...")
        try:
            from peft import PeftModel  # type: ignore
        except Exception as e:
            print("ERROR: peft package is required to merge LoRA adapters.")
            print(f"DETAILS: {e}")
            return None
        peft_model = PeftModel.from_pretrained(model, adapter_path)
        merged_model = peft_model.merge_and_unload()
        print("✓ Adapter merged into base model.")

        # Define output paths
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        gguf_filename = f"{Path(base_model_path).name}-merged-{Path(adapter_path).name}.{quantization_method}.gguf"
        gguf_path = output_path / gguf_filename

        # Save to GGUF
        print(f"\nStep 3: Saving to GGUF format at {gguf_path}...")
        # Prefer saving from the merged_model if it implements save_pretrained_gguf
        # Prefer saving merged model; use Unsloth helper to support HF/Unsloth types
        target = merged_model if merged_model is not None else model
        try:
            FastLanguageModel.save_pretrained_gguf(target, tokenizer, str(gguf_path), quantization_method=quantization_method)
        except Exception as se:
            print(f"[Export] Unsloth save_pretrained_gguf failed: {se}")
            print("[Export] Falling back to CPU merge + llama.cpp converter.")
            return _cpu_merge_and_convert(base_model_path, adapter_path, output_dir, quantization_method)
        print(f"✓ Successfully saved GGUF model!")
        # Emit machine-readable path for callers
        print(f"GGUF_PATH: {gguf_path}")

        # TODO: Add metadata writing step here

        print("\n✨ Process complete!")
        return str(gguf_path)

    except Exception as e:
        print(f"🔥 An error occurred: {e}")
        import traceback
        traceback.print_exc()
        return ""


def _cpu_merge_and_convert(base_model_path: str, adapter_path: str, output_dir: str, quant: str) -> str:
    """
    CPU-only fallback: merge LoRA into base with PEFT, save HF format, then convert to GGUF via llama.cpp.
    Requires: peft, transformers, and llama.cpp convert_hf_to_gguf.py present locally.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    try:
        print("\n[Fallback] Loading base + tokenizer (CPU, float32)...")
        tok = AutoTokenizer.from_pretrained(base_model_path, local_files_only=True)
        mdl = AutoModelForCausalLM.from_pretrained(base_model_path, torch_dtype=torch.float32, device_map="cpu", low_cpu_mem_usage=False, local_files_only=True)
        print("[Fallback] Base loaded.")
        print("[Fallback] Loading adapter via PEFT and merging...")
        from peft import PeftModel
        peft_model = PeftModel.from_pretrained(mdl, adapter_path)
        merged = peft_model.merge_and_unload()
        print("[Fallback] Adapter merged.")

        # Save merged HF model to a temp dir (choose a location with enough space)
        def _pick_tmp_parent() -> Path:
            candidates = [Path(tempfile.gettempdir()), Path(output_dir), Path(output_dir).parent]
            need = 3 * 1024 * 1024 * 1024  # ~3 GB
            # User override via env
            override = os.getenv('GGUF_TMP_DIR') or os.getenv('OPENCODE_TMP_DIR')
            if override:
                candidates.insert(0, Path(override))
            for c in candidates:
                try:
                    c.mkdir(parents=True, exist_ok=True)
                    usage = shutil.disk_usage(str(c))
                    if usage.free >= need:
                        return c
                except Exception:
                    continue
            return Path(tempfile.gettempdir())

        tmp_parent = _pick_tmp_parent()
        tmpdir = Path(tempfile.mkdtemp(prefix="merged_hf_", dir=str(tmp_parent)))
        print(f"[Fallback] Saving merged HF model to: {tmpdir}")
        merged.save_pretrained(tmpdir)
        tok.save_pretrained(tmpdir)

        # Locate llama.cpp converter
        candidates = [
            Path.home() / "Desktop" / "llama.cpp" / "convert_hf_to_gguf.py",
            Path.cwd() / "llama.cpp" / "convert_hf_to_gguf.py",
        ]
        converter = None
        for p in candidates:
            if p.exists():
                converter = p
                break
        if not converter:
            print("ERROR: llama.cpp convert_hf_to_gguf.py not found. Install llama.cpp or place the script locally.")
            return ""

        # Attempt to locate quantize binary for 2-step fallback
        quantize_candidates = [
            Path.home() / "Desktop" / "llama.cpp" / "quantize",
            Path.cwd() / "llama.cpp" / "quantize",
        ]
        quantize_bin = None
        for qp in quantize_candidates:
            if qp.exists() and qp.is_file():
                quantize_bin = qp
                break

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        desired_quant = (quant or "").upper() if quant else "Q5_K_M"
        if not desired_quant.startswith("Q"):
            desired_quant = "Q5_K_M"
        out_name = f"{Path(base_model_path).name}-merged-{Path(adapter_path).name}.{desired_quant}.gguf"
        out_path = out_dir / out_name
        print(f"[Fallback] Converting to GGUF using: {converter}")
        # Use safety wrapper to avoid converter's optional deps issues
        safe_wrapper = Path(__file__).parent / 'tools' / 'safe_convert_hf_to_gguf.py'
        cmd = [
            sys.executable,
            str(safe_wrapper),
            "--converter", str(converter),
            str(tmpdir),
            "--outtype", desired_quant,
            "--outfile", str(out_path),
        ]
        print("[Fallback] Running:", " ".join(cmd))
        env = os.environ.copy()
        env["HF_HUB_OFFLINE"] = "1"
        env["HUGGINGFACE_OFFLINE"] = "1"
        # Provide a stub for mistral_common to satisfy converter import paths
        stub_root = Path(tempfile.mkdtemp(prefix="stub_mc_"))
        try:
            pkg_dir = stub_root / 'mistral_common' / 'tokens' / 'tokenizers'
            pkg_dir.mkdir(parents=True, exist_ok=True)
            (stub_root / 'mistral_common' / '__init__.py').write_text('')
            (stub_root / 'mistral_common' / 'tokens' / '__init__.py').write_text('')
            (stub_root / 'mistral_common' / 'tokens' / 'tokenizers' / '__init__.py').write_text('')
            (stub_root / 'mistral_common' / 'tokens' / 'tokenizers' / 'base.py').write_text('class TokenizerVersion:\n    pass\n')
            # Newer converters import multimodal constants; provide safe defaults
            (stub_root / 'mistral_common' / 'tokens' / 'tokenizers' / 'multimodal.py').write_text('DATASET_MEAN=[0.0,0.0,0.0]\nDATASET_STD=[1.0,1.0,1.0]\n')
        except Exception:
            pass
        env["PYTHONPATH"] = f"{str(stub_root)}:{env.get('PYTHONPATH','')}"
        proc = subprocess.run(cmd, text=True, capture_output=True, env=env)
        if proc.returncode != 0:
            print("ERROR: llama.cpp conversion failed:")
            print(proc.stdout)
            print(proc.stderr)
            # Try 2-step: F16 conversion then quantize if binary present
            try:
                f16_path = out_dir / f"{Path(base_model_path).name}-merged-{Path(adapter_path).name}.F16.gguf"
                cmd2 = [sys.executable, str(safe_wrapper), "--converter", str(converter), str(tmpdir), "--outtype", "F16", "--outfile", str(f16_path)]
                print("[Fallback] Retrying as F16 then quantize:", " ".join(cmd2))
                proc2 = subprocess.run(cmd2, text=True, capture_output=True, env=env)
                if proc2.returncode == 0 and quantize_bin and quantize_bin.exists():
                    qcmd = [str(quantize_bin), "--help"]
                    print("[Fallback] Getting quantize help:", " ".join(qcmd))
                    proc_help = subprocess.run(qcmd, text=True, capture_output=True)
                    print(proc_help.stdout)
                    print(proc_help.stderr)

                    qcmd = [str(quantize_bin), str(f16_path), str(out_path), desired_quant]
                    print("[Fallback] Quantizing:", " ".join(qcmd))
                    proc3 = subprocess.run(qcmd, text=True, capture_output=True)
                    if proc3.returncode == 0 and out_path.exists():
                        print("[Fallback] Conversion + quantization succeeded.")
                        print(f"GGUF_PATH: {out_path}")
                        return str(out_path)
                    else:
                        print("ERROR: quantize failed:")
                        print(proc3.stdout)
                        print(proc3.stderr)
                        print(proc3.stdout)
                        print(proc3.stderr)
                # Fall back to F16 output if produced
                if (outp := (str(f16_path) if f16_path.exists() else "")):
                    print(f"Using F16 GGUF instead: {outp}")
                    print(f"GGUF_PATH: {outp}")
                    return outp
            except Exception as e2:
                print(f"ERROR: 2-step fallback failed: {e2}")
            return ""
        print("[Fallback] Conversion succeeded.")
        print(f"GGUF_PATH: {out_path}")
        return str(out_path)
    except Exception as e:
        print(f"🔥 Fallback path failed: {e}")
        import traceback
        traceback.print_exc()
        return ""
    finally:
        # Best-effort clean up temporary folders
        try:
            if 'tmpdir' in locals() and Path(tmpdir).exists():
                shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Merge LoRA adapter and export to GGUF.")
    parser.add_argument("--base", type=str, required=True, help="Path to the base model directory.")
    parser.add_argument("--adapter", type=str, required=True, help="Path to the LoRA adapter directory.")
    parser.add_argument("--output", type=str, default=str(MODELS_DIR.parent / "exports" / "gguf"), help="Directory to save the GGUF file.")
    parser.add_argument("--quant", type=str, default="q4_k_m", help="Quantization method (e.g., q4_k_m, q5_k_m, q8_0).")

    args = parser.parse_args()

    out = merge_and_export(args.base, args.adapter, args.output, args.quant)
    if not out:
        sys.exit(2)
