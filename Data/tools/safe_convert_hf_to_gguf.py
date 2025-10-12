#!/usr/bin/env python3
"""
Wrapper around llama.cpp's convert_hf_to_gguf.py that provides missing
"mistral_common" modules when they are not installed. This keeps conversion
of LLaMA-family models (e.g., Qwen) working locally without extra deps.

Usage:
  python3 safe_convert_hf_to_gguf.py --converter /path/to/convert_hf_to_gguf.py \
      <hf_model_dir> --outtype Q5_K_M --outfile out.gguf

Exits 0 on success; 2 on failure.
"""
import argparse
import runpy
import sys
import types
import importlib.machinery as _mach


def _stub_mistral_common():
    # Build a minimal module tree to satisfy imports used by some converter
    # versions. These are not used for Qwen/LLaMA conversion paths.
    root = types.ModuleType('mistral_common')
    tokens = types.ModuleType('mistral_common.tokens')
    tokenizers = types.ModuleType('mistral_common.tokens.tokenizers')
    base = types.ModuleType('mistral_common.tokens.tokenizers.base')
    multimodal = types.ModuleType('mistral_common.tokens.tokenizers.multimodal')
    tekken = types.ModuleType('mistral_common.tokens.tokenizers.tekken')
    sentencepiece = types.ModuleType('mistral_common.tokens.tokenizers.sentencepiece')

    class TokenizerVersion:  # noqa: N801
        pass

    base.TokenizerVersion = TokenizerVersion
    multimodal.DATASET_MEAN = [0.0, 0.0, 0.0]
    multimodal.DATASET_STD = [1.0, 1.0, 1.0]
    class Tekkenizer:  # noqa: N801
        pass
    tekken.Tekkenizer = Tekkenizer
    class SentencePieceTokenizer:
        pass
    sentencepiece.SentencePieceTokenizer = SentencePieceTokenizer

    # Provide valid ModuleSpec to satisfy importlib.util.find_spec checks
    root.__spec__ = _mach.ModuleSpec('mistral_common', loader=None)
    tokens.__spec__ = _mach.ModuleSpec('mistral_common.tokens', loader=None)
    tokenizers.__spec__ = _mach.ModuleSpec('mistral_common.tokens.tokenizers', loader=None)
    base.__spec__ = _mach.ModuleSpec('mistral_common.tokens.tokenizers.base', loader=None)
    multimodal.__spec__ = _mach.ModuleSpec('mistral_common.tokens.tokenizers.multimodal', loader=None)
    tekken.__spec__ = _mach.ModuleSpec('mistral_common.tokens.tokenizers.tekken', loader=None)
    sentencepiece.__spec__ = _mach.ModuleSpec('mistral_common.tokens.tokenizers.sentencepiece', loader=None)

    # Mark tokenizers as a package to allow submodule imports
    tokens.__path__ = []
    tokenizers.__path__ = []

    sys.modules['mistral_common'] = root
    sys.modules['mistral_common.tokens'] = tokens
    sys.modules['mistral_common.tokens.tokenizers'] = tokenizers
    sys.modules['mistral_common.tokens.tokenizers.base'] = base
    sys.modules['mistral_common.tokens.tokenizers.multimodal'] = multimodal
    sys.modules['mistral_common.tokens.tokenizers.tekken'] = tekken
    sys.modules['mistral_common.tokens.tokenizers.sentencepiece'] = sentencepiece


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--converter', required=True, help='Path to llama.cpp convert_hf_to_gguf.py')
    p.add_argument('hf_model_dir')
    p.add_argument('--outtype', required=True)
    p.add_argument('--outfile', required=True)
    args, rest = p.parse_known_args()

    # Ensure required stubs are present
    _stub_mistral_common()

    # convert_hf_to_gguf.py supported types
    converter_supported_quants = ["f32", "f16", "bf16", "q8_0", "tq1_0", "tq2_0", "auto"]
    outtype_for_converter = args.outtype if args.outtype in converter_supported_quants else "f16"

    # Prepare argv for the converter
    argv_backup = sys.argv[:]
    sys.argv = [args.converter, args.hf_model_dir, '--outtype', outtype_for_converter, '--outfile', args.outfile] + rest
    try:
        runpy.run_path(args.converter, run_name='__main__')
        sys.exit(0)
    except SystemExit as e:
        # Propagate converter exit codes
        code = int(e.code) if isinstance(e.code, int) else 2
        sys.exit(code)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        sys.argv = argv_backup


if __name__ == '__main__':
    main()
