"""
Hardware Capability Detector for The Learning Engine

Detects system hardware capabilities (RAM, VRAM, GPU, servers) and caches
results for use by the Router module. Read-only operations with graceful fallback.

Part of Blueprint v2.0-2.1 (S4: Capability Detector)
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Try to import psutil, graceful fallback if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("WARNING: psutil not available, RAM detection will be limited")

# Cache settings
CACHE_FILE = Path(__file__).parent.parent.parent / "capabilities" / "node.json"
CACHE_VALIDITY_SECONDS = 300  # 5 minutes


def _get_cpu_info() -> dict:
    """
    Detect CPU information.

    Returns:
        dict: {"cores": int, "threads": int, "model": str}
    """
    import os

    cpu_info = {
        "cores": os.cpu_count() or 0,
        "threads": os.cpu_count() or 0,  # Same as cores for now
        "model": "Unknown CPU"
    }

    # Try to get CPU model from /proc/cpuinfo
    try:
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            cpuinfo_text = cpuinfo_path.read_text()
            for line in cpuinfo_text.split('\n'):
                if line.startswith("model name"):
                    cpu_info["model"] = line.split(":", 1)[1].strip()
                    break
    except Exception:
        pass

    return cpu_info


def _get_ram_info() -> dict:
    """
    Detect system RAM using psutil.

    Returns:
        dict: {"total_gb": float, "available_gb": float, "used_percent": float}
    """
    if not PSUTIL_AVAILABLE:
        return {
            "total_gb": 0.0,
            "available_gb": 0.0,
            "used_percent": 0.0,
            "error": "psutil not available"
        }

    try:
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_percent": round(mem.percent, 1)
        }
    except Exception as e:
        return {
            "total_gb": 0.0,
            "available_gb": 0.0,
            "used_percent": 0.0,
            "error": str(e)
        }


def _get_gpu_info() -> list[dict]:
    """
    Detect NVIDIA GPU information using nvidia-smi.
    Gracefully falls back if NVIDIA drivers not available.

    Returns:
        list[dict]: List of GPU info dicts, empty list if no GPUs or detection fails
    """
    gpus = []

    # Try nvidia-smi first
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.total,memory.free,memory.used,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 6:
                        try:
                            gpus.append({
                                "id": int(parts[0]),
                                "name": parts[1],
                                "vram_total_mb": int(float(parts[2])),
                                "vram_free_mb": int(float(parts[3])),
                                "vram_used_mb": int(float(parts[4])),
                                "driver_version": parts[5],
                                "detection_method": "nvidia-smi",
                                "vendor": "nvidia",
                                "ollama_compatible": True  # NVIDIA GPUs work with Ollama
                            })
                        except (ValueError, IndexError):
                            pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # nvidia-smi not available or timeout
        pass
    except Exception as e:
        print(f"GPU detection error: {e}")

    # If nvidia-smi failed, try reading /proc/driver/nvidia
    if not gpus:
        try:
            nvidia_dir = Path("/proc/driver/nvidia/gpus")
            if nvidia_dir.exists():
                for gpu_dir in nvidia_dir.iterdir():
                    if gpu_dir.is_dir():
                        info_file = gpu_dir / "information"
                        if info_file.exists():
                            info_text = info_file.read_text()
                            # Parse basic info from /proc
                            gpu_info = {
                                "id": len(gpus),
                                "name": "Unknown NVIDIA GPU",
                                "detection_method": "proc_fs",
                                "vendor": "nvidia",
                                "ollama_compatible": True  # NVIDIA GPUs work with Ollama
                            }
                            for line in info_text.split('\n'):
                                if "Model:" in line:
                                    gpu_info["name"] = line.split(":", 1)[1].strip()
                            gpus.append(gpu_info)
        except Exception as e:
            print(f"Fallback GPU detection error: {e}")

    # If NVIDIA detection failed, try AMD GPU detection
    if not gpus:
        gpus.extend(_get_amd_gpu_info())

    return gpus


def _get_amd_gpu_info() -> list[dict]:
    """
    Detect AMD GPU information using rocm-smi or sysfs.
    Gracefully falls back if AMD drivers not available.

    Returns:
        list[dict]: List of GPU info dicts, empty list if no GPUs or detection fails
    """
    gpus = []

    # Try rocm-smi first (if ROCm is installed)
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                # Parse ROCm output
                for card_id, card_data in data.items():
                    if isinstance(card_data, dict):
                        vram_total = card_data.get("VRAM Total Memory (B)", 0)
                        vram_used = card_data.get("VRAM Total Used Memory (B)", 0)
                        # Check if ROCm is available (indicates Ollama GPU support)
                        ollama_gpu_capable = True  # If rocm-smi works, ROCm is installed
                        gpus.append({
                            "id": int(card_id.replace("card", "")),
                            "name": f"AMD GPU {card_id}",
                            "vram_total_mb": int(vram_total / (1024 * 1024)),
                            "vram_free_mb": int((vram_total - vram_used) / (1024 * 1024)),
                            "vram_used_mb": int(vram_used / (1024 * 1024)),
                            "detection_method": "rocm-smi",
                            "vendor": "amd",
                            "ollama_compatible": ollama_gpu_capable  # AMD GPU with ROCm
                        })
            except (json.JSONDecodeError, ValueError):
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # rocm-smi not available
        pass
    except Exception as e:
        print(f"AMD GPU detection (rocm-smi) error: {e}")

    # If rocm-smi failed, try reading sysfs
    if not gpus:
        try:
            drm_path = Path("/sys/class/drm")
            if drm_path.exists():
                for card_dir in sorted(drm_path.glob("card*")):
                    # Skip render nodes
                    if "render" in card_dir.name:
                        continue

                    device_path = card_dir / "device"
                    if not device_path.exists():
                        continue

                    # Check if it's an AMD GPU
                    vendor_file = device_path / "vendor"
                    if vendor_file.exists():
                        vendor_id = vendor_file.read_text().strip()
                        # AMD vendor ID is 0x1002
                        if vendor_id != "0x1002":
                            continue

                    # Try to get GPU name from device
                    gpu_name = "AMD GPU"
                    device_file = device_path / "device"
                    if device_file.exists() and device_file.is_file():
                        device_id = device_file.read_text().strip()
                        # Simple device ID mapping (can be expanded)
                        amd_devices = {
                            "0x73df": "AMD Radeon RX 6700 XT",
                            "0x73ff": "AMD Radeon RX 6600 XT",
                            "0x731f": "AMD Radeon RX 6800 XT",
                            # Add more as needed
                        }
                        gpu_name = amd_devices.get(device_id, f"AMD GPU {device_id}")

                    # Try to read VRAM info
                    vram_total_mb = 0
                    vram_used_mb = 0

                    mem_info_file = device_path / "mem_info_vram_total"
                    if mem_info_file.exists():
                        try:
                            vram_total_mb = int(mem_info_file.read_text().strip()) // (1024 * 1024)
                        except (ValueError, OSError):
                            pass

                    mem_used_file = device_path / "mem_info_vram_used"
                    if mem_used_file.exists():
                        try:
                            vram_used_mb = int(mem_used_file.read_text().strip()) // (1024 * 1024)
                        except (ValueError, OSError):
                            pass

                    # If we got at least basic info, add this GPU
                    if vram_total_mb > 0:
                        # AMD GPU detected via sysfs - assume CPU-only for Ollama (no ROCm)
                        gpus.append({
                            "id": len(gpus),
                            "name": gpu_name,
                            "vram_total_mb": vram_total_mb,
                            "vram_free_mb": max(0, vram_total_mb - vram_used_mb),
                            "vram_used_mb": vram_used_mb,
                            "detection_method": "sysfs",
                            "vendor": "amd",
                            "ollama_compatible": False  # No ROCm detected (sysfs fallback)
                        })
        except Exception as e:
            print(f"AMD GPU detection (sysfs) error: {e}")

    return gpus


def _check_server_health(host: str, port: int, endpoint: str, name: str) -> dict:
    """
    Check if a server is responding at the given endpoint.

    Args:
        host: Server hostname
        port: Server port
        endpoint: HTTP endpoint to check
        name: Server name for logging

    Returns:
        dict: {"available": bool, "endpoint": str, "models": list, "error": str}
    """
    import urllib.request
    import urllib.error

    url = f"http://{host}:{port}{endpoint}"
    result = {
        "available": False,
        "endpoint": url,
        "models": [],
        "error": None
    }

    try:
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'OpenCode-Capabilities/1.0')

        with urllib.request.urlopen(req, timeout=2) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                result["available"] = True

                # Extract model list based on server type
                if name == "llama_server":
                    # llama-server returns {"data": [{"id": "model"}]}
                    if "data" in data and isinstance(data["data"], list):
                        result["models"] = [m.get("id", "") for m in data["data"]]
                elif name == "ollama":
                    # Ollama returns {"models": [{"name": "tag"}]}
                    if "models" in data and isinstance(data["models"], list):
                        result["models"] = [m.get("name", "") for m in data["models"]]

    except urllib.error.URLError as e:
        result["error"] = f"Connection failed: {e.reason}"
    except json.JSONDecodeError:
        result["error"] = "Invalid JSON response"
    except Exception as e:
        result["error"] = str(e)

    return result


def _get_disk_space() -> dict:
    """
    Get free disk space in key directories.

    Returns:
        dict: {"total_gb": float, "free_gb": float, "used_percent": float}
    """
    if not PSUTIL_AVAILABLE:
        return {
            "total_gb": 0.0,
            "free_gb": 0.0,
            "used_percent": 0.0,
            "error": "psutil not available"
        }

    try:
        # Check disk space for the Data directory
        data_dir = Path(__file__).parent.parent.parent
        usage = psutil.disk_usage(str(data_dir))

        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "used_percent": round(usage.percent, 1),
            "path": str(data_dir)
        }
    except Exception as e:
        return {
            "total_gb": 0.0,
            "free_gb": 0.0,
            "used_percent": 0.0,
            "error": str(e)
        }


def detect_capabilities(force_refresh: bool = False) -> dict:
    """
    Detect system capabilities and cache results.

    Args:
        force_refresh: If True, bypass cache and run fresh detection

    Returns:
        dict: Capability information including RAM, GPU, servers, disk
    """
    # Check cache first
    if not force_refresh and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            cache_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01T00:00:00"))
            age_seconds = (datetime.now() - cache_time).total_seconds()

            if age_seconds < CACHE_VALIDITY_SECONDS:
                return cached
        except Exception as e:
            print(f"Cache read error: {e}")

    # Run fresh detection
    capabilities = {
        "timestamp": datetime.now().isoformat(),
        "cpu": _get_cpu_info(),
        "ram": _get_ram_info(),
        "gpus": _get_gpu_info(),
        "servers": {
            "llama_server": _check_server_health("127.0.0.1", 8001, "/v1/models", "llama_server"),
            "ollama": _check_server_health("127.0.0.1", 11434, "/api/tags", "ollama")
        },
        "disk": _get_disk_space(),
        "psutil_available": PSUTIL_AVAILABLE
    }

    # Write to cache
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(capabilities, indent=2))
    except Exception as e:
        print(f"Cache write error: {e}")

    return capabilities


def get_cached_capabilities() -> Optional[dict]:
    """
    Get cached capabilities without running detection.

    Returns:
        dict | None: Cached capabilities or None if cache invalid/missing
    """
    if CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text())
            cache_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01T00:00:00"))
            age_seconds = (datetime.now() - cache_time).total_seconds()

            if age_seconds < CACHE_VALIDITY_SECONDS:
                return cached
        except Exception:
            pass

    return None


def get_summary() -> str:
    """
    Get human-readable summary of system capabilities.

    Returns:
        str: Multi-line summary string
    """
    caps = detect_capabilities()

    lines = []
    lines.append("=== System Capabilities ===")

    # RAM
    ram = caps.get("ram", {})
    if "error" not in ram:
        lines.append(f"RAM: {ram.get('available_gb', 0):.1f}GB / {ram.get('total_gb', 0):.1f}GB available ({100-ram.get('used_percent', 0):.0f}% free)")
    else:
        lines.append(f"RAM: Detection failed ({ram.get('error', 'unknown')})")

    # GPU
    gpus = caps.get("gpus", [])
    if gpus:
        lines.append(f"GPUs: {len(gpus)} detected")
        for gpu in gpus:
            vram_info = ""
            if "vram_free_mb" in gpu and "vram_total_mb" in gpu:
                vram_info = f" ({gpu['vram_free_mb']/1024:.1f}GB / {gpu['vram_total_mb']/1024:.1f}GB free)"
            lines.append(f"  - GPU {gpu['id']}: {gpu.get('name', 'Unknown')}{vram_info}")
    else:
        lines.append("GPUs: None detected (CPU-only mode)")

    # Servers
    servers = caps.get("servers", {})
    llama = servers.get("llama_server", {})
    ollama = servers.get("ollama", {})

    llama_status = "✓ Online" if llama.get("available") else f"✗ Offline ({llama.get('error', 'unknown')})"
    ollama_status = "✓ Online" if ollama.get("available") else f"✗ Offline ({ollama.get('error', 'unknown')})"

    lines.append(f"llama-server: {llama_status}")
    if llama.get("models"):
        lines.append(f"  Models: {', '.join(llama['models'][:3])}")

    lines.append(f"Ollama: {ollama_status}")
    if ollama.get("models"):
        lines.append(f"  Models: {', '.join(ollama['models'][:3])}")

    # Disk
    disk = caps.get("disk", {})
    if "error" not in disk:
        lines.append(f"Disk: {disk.get('free_gb', 0):.1f}GB / {disk.get('total_gb', 0):.1f}GB free")

    return "\n".join(lines)


if __name__ == "__main__":
    # CLI testing
    print(get_summary())
    print(f"\nFull capabilities cached to: {CACHE_FILE}")
