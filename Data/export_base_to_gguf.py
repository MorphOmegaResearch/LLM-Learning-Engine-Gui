#!/usr/bin/env python3
"""
Export a base (PyTorch) model to GGUF for inference (no adapter merge).
"""
import os
import sys
import argparse
from pathlib import Path

import torch
from unsloth import FastLanguageModel

def export_base_to_gguf(base_model_path: str, output_dir: str, quantization_method: str = "q4_k_m") -> str:
    print(f"🚀 Export base to GGUF\n - Base: {base_model_path}\n - Quant: {quantization_method}")
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model_path,
            load_in_4bit=False,
            torch_dtype=torch.float16,
        )
        out_dir = Path(output_dir); out_dir.mkdir(parents=True, exist_ok=True)
        base_name = Path(base_model_path).name
        gguf_path = out_dir / f"{base_name}.{quantization_method}.gguf"
        print(f"Saving GGUF: {gguf_path}")
        model.save_pretrained_gguf(str(gguf_path), tokenizer, quantization_method=quantization_method)
        print("✓ Export complete")
        return str(gguf_path)
    except Exception as e:
        print(f"🔥 Export failed: {e}")
        import traceback; traceback.print_exc()
        return ""

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--output", default=str(Path(__file__).parent / "exports" / "gguf"))
    p.add_argument("--quant", default="q4_k_m")
    args = p.parse_args()
    export_base_to_gguf(args.base, args.output, args.quant)

