"""
Backend Router for The Learning Engine

Policy-based backend selection that consumes hardware capabilities and bundle
metadata to recommend optimal runtime configuration for each Mode.

Part of Blueprint v2.0-2.1 (S6: Router - Read-Only Preview)

IMPORTANT: This is currently READ-ONLY preview mode. The router generates
recommendations but does NOT automatically apply them. User must manually
confirm before router controls model mounting.
"""

import json
from pathlib import Path
from typing import Optional


def route_request(bundle: dict, mode: str, capabilities: dict, override_backend: Optional[str] = None, backend_config: Optional[dict] = None) -> dict:
    """
    Generate runtime plan based on mode, capabilities, and bundle preferences.

    Args:
        bundle: Bundle dictionary from bundle_loader
        mode: Mode name ("standard", "fast", "smart", "think")
        capabilities: Hardware capabilities from capabilities.detect_capabilities()
        override_backend: Optional backend override ("ollama" or "llama_server")
        backend_config: Optional backend configuration dict (for Ollama/llama-server URLs)

    Returns:
        dict: Runtime plan with backend, endpoint, model_ref, params, and reason
        {
            "backend": "llama_server" | "ollama",
            "endpoint": "http://127.0.0.1:8001/v1" or "http://127.0.0.1:11434",
            "model_ref": "path/to/model.gguf" or "ollama:tag",
            "params": {
                "n_gpu_layers": 35,  # llama-server only
                "context": 4096,
                "format": "json"
            },
            "reason": "Explanation of routing decision",
            "fallback_available": bool,
            "fallback_backend": "ollama" | "llama_server" | None
        }
    """
    plan = {
        "backend": None,
        "endpoint": None,
        "model_ref": None,
        "params": {},
        "reason": "",
        "fallback_available": False,
        "fallback_backend": None
    }

    # Extract capabilities
    ram_available_gb = capabilities.get("ram", {}).get("available_gb", 0)
    gpus = capabilities.get("gpus", [])
    has_gpu = len(gpus) > 0
    vram_free_mb = gpus[0].get("vram_free_mb", 0) if has_gpu else 0
    vram_free_gb = vram_free_mb / 1024

    servers = capabilities.get("servers", {})
    llama_server_available = servers.get("llama_server", {}).get("available", False)
    ollama_available = servers.get("ollama", {}).get("available", False)

    # Get bundle variants and check available backends
    variants = bundle.get("variants", [])
    ollama_variant = None
    llama_variant = None
    ollama_gpu_compatible = None

    for v in variants:
        # Check available_backends (new system) or fall back to legacy backend field
        available_backends = v.get("available_backends", {})

        # Check Ollama availability
        ollama_info = available_backends.get("ollama", {})
        if ollama_info.get("available", False):
            ollama_variant = v
            ollama_gpu_compatible = ollama_info.get("gpu_compatible", None)
        elif v.get("backend") == "ollama" and not available_backends:
            # Legacy fallback
            ollama_variant = v

        # Check GGUF/llama-server availability
        gguf_info = available_backends.get("gguf", {})
        if gguf_info.get("available", False):
            llama_variant = v
        elif v.get("backend") == "llama_server" and not available_backends:
            # Legacy fallback
            llama_variant = v

    # Check if user forced a backend
    if override_backend:
        if override_backend == "ollama":
            if ollama_variant and ollama_available:
                return _build_ollama_plan(ollama_variant, bundle, "User override: Ollama selected", backend_config)
            else:
                reason = "Ollama variant not available"
                if llama_variant and llama_server_available:
                    reason += ", falling back to llama-server"
                    return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason)
                return _build_error_plan(f"Ollama override requested but {reason}")

        elif override_backend == "llama_server":
            if llama_variant and llama_server_available:
                return _build_llama_plan(llama_variant, bundle, capabilities, mode, "User override: llama-server selected")
            else:
                reason = "llama-server variant not available"
                if ollama_variant and ollama_available:
                    reason += ", falling back to Ollama"
                    return _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
                return _build_error_plan(f"llama-server override requested but {reason}")

    # Get bundle preference for this mode
    preferences = bundle.get("preferences", {})
    mode_key = f"{mode}_mode"
    mode_pref = preferences.get(mode_key, {})
    preferred_backend = mode_pref.get("backend", "auto")

    # If bundle has explicit preference, honor it
    if preferred_backend == "ollama":
        if ollama_variant and ollama_available:
            reason = f"{mode.capitalize()} mode preference: {mode_pref.get('reason', 'Bundle configured for Ollama')}"
            return _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
        elif llama_variant and llama_server_available:
            reason = f"{mode.capitalize()} mode: Ollama preferred but unavailable, using llama-server"
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason)
        else:
            return _build_error_plan(f"Bundle prefers Ollama for {mode} mode but no backend available")

    elif preferred_backend == "llama_server":
        if llama_variant and llama_server_available:
            reason = f"{mode.capitalize()} mode preference: {mode_pref.get('reason', 'Bundle configured for llama-server')}"
            n_gpu_layers = mode_pref.get("n_gpu_layers", 35)
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, n_gpu_layers)
        elif ollama_variant and ollama_available:
            reason = f"{mode.capitalize()} mode: llama-server preferred but unavailable, using Ollama"
            return _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
        else:
            return _build_error_plan(f"Bundle prefers llama-server for {mode} mode but no backend available")

    # Auto-routing based on mode and capabilities
    if mode == "fast":
        # Fast mode: prioritize low latency - use whatever has GPU, minimal layers

        # GPU available: use llama-server with minimal GPU layers (fastest startup)
        if has_gpu and llama_variant and llama_server_available:
            n_gpu_layers = 10  # Minimal GPU layers for fast startup
            reason = f"Fast mode: Using llama-server with minimal GPU layers (low latency)"
            plan = _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, n_gpu_layers)
            if ollama_variant and ollama_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "ollama"
            return plan

        # Ollama with GPU: use it
        elif ollama_variant and ollama_available and ollama_gpu_compatible == True:
            reason = "Fast mode: Using Ollama with GPU (low latency)"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            return plan

        # CPU-only: prefer Ollama (faster CPU inference)
        elif ollama_variant and ollama_available:
            reason = "Fast mode: Using Ollama (CPU-only, optimized for speed)"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            return plan

        # Fallback to llama-server CPU
        elif llama_variant and llama_server_available:
            reason = "Fast mode: Using llama-server (CPU-only)"
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, 0)

        else:
            return _build_error_plan("No backend available for fast mode")

    elif mode == "smart":
        # Smart mode: VRAM-aware, balanced performance
        # Choose backend based on what hardware can handle

        # GPU available with good VRAM: use llama-server with VRAM-appropriate layers
        if has_gpu and llama_variant and llama_server_available:
            if vram_free_gb >= 4:
                n_gpu_layers = 35  # High GPU usage
                reason = f"Smart mode: High VRAM ({vram_free_gb:.1f}GB), using max GPU layers"
            elif vram_free_gb >= 2:
                n_gpu_layers = 20  # Medium GPU usage
                reason = f"Smart mode: Medium VRAM ({vram_free_gb:.1f}GB), using balanced GPU layers"
            else:
                n_gpu_layers = 10  # Low GPU usage
                reason = f"Smart mode: Limited VRAM ({vram_free_gb:.1f}GB), using minimal GPU layers"

            plan = _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, n_gpu_layers)
            if ollama_variant and ollama_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "ollama"
            return plan

        # Ollama with GPU support
        elif ollama_variant and ollama_available and ollama_gpu_compatible == True:
            reason = "Smart mode: Using Ollama with GPU acceleration"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            return plan

        # CPU-only: prefer Ollama
        elif ollama_variant and ollama_available:
            reason = "Smart mode: Using Ollama (CPU-only, no GPU acceleration available)"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            return plan

        # Fallback to llama-server CPU
        elif llama_variant and llama_server_available:
            reason = "Smart mode: Using llama-server (CPU-only)"
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, 0)

        else:
            return _build_error_plan("No backend available for smart mode")

    elif mode == "think":
        # Think mode: maximize performance - choose best backend for hardware
        # Priority: GPU-accelerated backend > CPU-only backend

        # If GPU available, prefer llama-server (better GPU utilization)
        if has_gpu and llama_variant and llama_server_available:
            n_gpu_layers = 35  # Max GPU usage for Think mode
            reason = f"Think mode: Using llama-server with max GPU layers ({vram_free_gb:.1f}GB VRAM)"
            plan = _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, n_gpu_layers)
            if ollama_variant and ollama_available and ollama_gpu_compatible:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "ollama"
            return plan

        # If Ollama has GPU support, use it
        elif ollama_variant and ollama_available and ollama_gpu_compatible == True:
            reason = "Think mode: Using Ollama with GPU acceleration"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            if llama_variant and llama_server_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "llama_server"
            return plan

        # CPU-only: prefer Ollama (better CPU optimization)
        elif ollama_variant and ollama_available:
            reason = "Think mode: Using Ollama (CPU-only, no GPU detected)"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            if llama_variant and llama_server_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "llama_server"
            return plan

        # Fallback to llama-server CPU mode
        elif llama_variant and llama_server_available:
            reason = "Think mode: Using llama-server (CPU-only)"
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, 0)

        else:
            return _build_error_plan("No backend available for think mode")

    elif mode == "standard" or not mode:
        # Standard mode: balanced auto-routing based on hardware
        # Priority: Use GPU if available, otherwise CPU-optimized backend

        # GPU available: use llama-server with balanced GPU layers
        if has_gpu and llama_variant and llama_server_available:
            n_gpu_layers = 25  # Balanced GPU usage
            reason = f"Standard mode: GPU detected ({vram_free_gb:.1f}GB VRAM), using llama-server with balanced GPU layers"
            plan = _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, n_gpu_layers)
            if ollama_variant and ollama_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "ollama"
            return plan

        # Ollama with GPU support
        elif ollama_variant and ollama_available and ollama_gpu_compatible == True:
            reason = "Standard mode: Using Ollama with GPU acceleration"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            if llama_variant and llama_server_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "llama_server"
            return plan

        # CPU-only: prefer Ollama
        elif ollama_variant and ollama_available:
            reason = "Standard mode: Using Ollama (CPU-only, no GPU detected)"
            plan = _build_ollama_plan(ollama_variant, bundle, reason, backend_config)
            if llama_variant and llama_server_available:
                plan["fallback_available"] = True
                plan["fallback_backend"] = "llama_server"
            return plan
        elif llama_variant and llama_server_available:
            reason = "Standard mode: Using llama-server (CPU-only)"
            return _build_llama_plan(llama_variant, bundle, capabilities, mode, reason, 0)
        else:
            return _build_error_plan("No backend available for standard mode")

    else:
        return _build_error_plan(f"Unknown mode: {mode}")


def _build_ollama_plan(variant: dict, bundle: dict, reason: str, backend_config: Optional[dict] = None) -> dict:
    """Build runtime plan for Ollama backend."""
    tag = variant.get("tag", "unknown")
    params = variant.get("params", {})

    # Get Ollama URL from config or use default
    ollama_url = "http://127.0.0.1:11434"
    if backend_config:
        ollama_url = backend_config.get('ollama_base_url', ollama_url)

    return {
        "backend": "ollama",
        "endpoint": ollama_url,
        "model_ref": tag,
        "params": {
            "context": params.get("context", 4096),
            "num_ctx": params.get("num_ctx", 4096),
            **params
        },
        "reason": reason,
        "fallback_available": False,
        "fallback_backend": None
    }


def _build_llama_plan(variant: dict, bundle: dict, capabilities: dict, mode: str, reason: str, n_gpu_layers: Optional[int] = None) -> dict:
    """Build runtime plan for llama-server backend."""
    gguf_path = variant.get("gguf_path", "unknown")
    params = variant.get("params", {})

    # Use explicit n_gpu_layers if provided, otherwise use variant params
    if n_gpu_layers is None:
        n_gpu_layers = params.get("n_gpu_layers", 35)

    return {
        "backend": "llama_server",
        "endpoint": "http://127.0.0.1:8001/v1",
        "model_ref": gguf_path,
        "params": {
            "n_gpu_layers": n_gpu_layers,
            "context": params.get("context", 4096),
            "format": "json",
            **params
        },
        "reason": reason,
        "fallback_available": False,
        "fallback_backend": None
    }


def _build_error_plan(reason: str) -> dict:
    """Build error plan when routing fails."""
    return {
        "backend": None,
        "endpoint": None,
        "model_ref": None,
        "params": {},
        "reason": f"ERROR: {reason}",
        "fallback_available": False,
        "fallback_backend": None
    }


def get_routing_summary(plan: dict) -> str:
    """
    Get human-readable summary of routing plan.

    Args:
        plan: Routing plan from route_request()

    Returns:
        str: Multi-line summary string
    """
    if plan.get("backend") is None:
        return f"⚠️ Routing Failed\n{plan.get('reason', 'Unknown error')}"

    lines = []
    backend = plan.get("backend", "unknown")
    model_ref = plan.get("model_ref", "unknown")

    if backend == "ollama":
        lines.append(f"✓ Ollama: {model_ref}")
    elif backend == "llama_server":
        model_name = Path(model_ref).name if model_ref != "unknown" else "unknown"
        n_gpu = plan.get("params", {}).get("n_gpu_layers", 0)
        lines.append(f"✓ llama-server: {model_name}")
        lines.append(f"  GPU Layers: {n_gpu}")

    lines.append(f"  Endpoint: {plan.get('endpoint', 'unknown')}")
    lines.append(f"  Context: {plan.get('params', {}).get('context', 4096)}")
    lines.append(f"  Reason: {plan.get('reason', 'No reason provided')}")

    if plan.get("fallback_available"):
        lines.append(f"  Fallback: {plan.get('fallback_backend', 'unknown')} available")

    return "\n".join(lines)


if __name__ == "__main__":
    # CLI testing with mock data
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from tabs.custom_code_tab import capabilities
    from registry import bundle_loader

    print("=== Router Testing (Mock Data) ===\n")

    # Create mock bundle
    mock_bundle = {
        "bundle_ulid": "01MOCK123456",
        "name": "Test Model",
        "variants": [
            {
                "backend": "ollama",
                "tag": "test:model",
                "params": {"context": 4096}
            },
            {
                "backend": "llama_server",
                "gguf_path": "/path/to/model.gguf",
                "quant": "q4_k_m",
                "params": {"n_gpu_layers": 35, "context": 4096}
            }
        ],
        "preferences": {
            "fast_mode": {
                "backend": "llama_server",
                "n_gpu_layers": 10,
                "reason": "Low GPU layers for speed"
            },
            "think_mode": {
                "backend": "ollama",
                "reason": "Full context analysis"
            }
        }
    }

    # Get real capabilities
    caps = capabilities.detect_capabilities()

    # Test routing for each mode
    for mode in ["fast", "smart", "think", "standard"]:
        print(f"--- {mode.upper()} MODE ---")
        plan = route_request(mock_bundle, mode, caps)
        print(get_routing_summary(plan))
        print()
