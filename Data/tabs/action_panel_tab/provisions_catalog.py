"""
provisions_catalog.py — Standalone scanner for Trainer/Provisions/ bundled packages.

Callable by Os_Toolkit.profile_entity() and onboarder.ToolDiscoverer.
Writes catalog to babel_data/inventory/provisions_catalog.json.

Usage:
    python3 provisions_catalog.py --scan     # Write catalog JSON
    python3 provisions_catalog.py --list     # Print table to stdout
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Optional

# ── Paths ──────────────────────────────────────────────────────────────────
_HERE          = Path(__file__).resolve().parent          # action_panel_tab/
PROVISIONS_DIR = _HERE.parents[2] / "Provisions"          # Trainer/Provisions/
CATALOG_OUT    = _HERE / "babel_data" / "inventory" / "provisions_catalog.json"

# Regex: name-version-... where version starts with a digit
_WHL_RE = re.compile(r'^([A-Za-z0-9][A-Za-z0-9_.\-]*?)-(\d[^-]*)')


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_name_version(filename: str):
    """
    Extract (normalized_name, version) from a wheel or sdist filename.
    Examples:
      ollama-0.6.1-py3-none-any.whl          → ('ollama', '0.6.1')
      pydantic_core-2.41.5-cp310-....whl     → ('pydantic_core', '2.41.5')
      llama_cpp_python-0.3.16.tar.gz         → ('llama_cpp_python', '0.3.16')
      markupsafe-3.0.3-cp310-....whl         → ('markupsafe', '3.0.3')
    """
    # Strip known extensions first
    stem = filename
    for ext in ('.whl', '.tar.gz', '.zip'):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break

    m = _WHL_RE.match(stem)
    if m:
        name = m.group(1).replace('-', '_').lower()
        version = m.group(2)
        return name, version

    # Fallback: return the stem as-is
    return stem.lower(), '?'


def _check_installed(name: str) -> Optional[str]:
    """
    Return the installed version string if the package is importable,
    else None.  Uses importlib.metadata (stdlib ≥3.8).
    """
    try:
        import importlib.metadata as _im
        # Try exact name and common normalizations
        for candidate in (name, name.replace('_', '-'), name.replace('-', '_')):
            try:
                return _im.version(candidate)
            except _im.PackageNotFoundError:
                continue
    except ImportError:
        pass
    return None


def _kind(filename: str) -> str:
    f = filename.lower()
    if f.endswith('.whl'):
        return 'whl'
    if f.endswith('.tar.gz'):
        return 'sdist'
    return 'zip'


# ── Public API ─────────────────────────────────────────────────────────────

def scan_provisions(provisions_dir: Path = PROVISIONS_DIR) -> List[dict]:
    """
    Scan provisions_dir and return a list of package dicts.
    Skips directories and non-package files (e.g. *.zip bundles that aren't
    Python packages — Models_patch_bundle.zip is kept as kind='zip').
    """
    if not provisions_dir.exists():
        return []

    entries = []
    for f in sorted(provisions_dir.iterdir()):
        if f.is_dir():
            continue
        if not any(f.name.lower().endswith(ext) for ext in ('.whl', '.tar.gz', '.zip')):
            continue

        name, version = _parse_name_version(f.name)
        installed_ver = _check_installed(name)

        entries.append({
            "name": name,
            "version": version,
            "filename": f.name,
            "path": str(f),
            "kind": _kind(f.name),
            "scope": "internal_bundle",
            "install_status": "installed" if installed_ver else "bundled",
            "installed_version": installed_ver,
        })

    return entries


def load_catalog(catalog_path: Path = CATALOG_OUT) -> List[dict]:
    """Load and return the cached catalog, or [] if not present."""
    if catalog_path.exists():
        try:
            return json.loads(catalog_path.read_text(encoding='utf-8')).get('packages', [])
        except Exception:
            pass
    return []


def write_catalog(entries: List[dict], catalog_path: Path = CATALOG_OUT) -> None:
    """Write entries to the catalog JSON file."""
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(
        json.dumps({"packages": entries, "_provisions_dir": str(PROVISIONS_DIR)},
                   indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


def lookup(name: str, catalog_path: Path = CATALOG_OUT) -> Optional[dict]:
    """
    Return the first catalog entry whose name matches (case-insensitive exact or prefix).
    Returns None if no match.
    """
    name_lower = name.lower().replace('-', '_')
    for pkg in load_catalog(catalog_path):
        pname = pkg.get('name', '').lower().replace('-', '_')
        if pname == name_lower or pname.startswith(name_lower):
            return pkg
    return None


# ── CLI entry-point ────────────────────────────────────────────────────────

def _cmd_scan():
    print(f"Scanning: {PROVISIONS_DIR}")
    entries = scan_provisions()
    write_catalog(entries)
    print(f"Wrote {len(entries)} packages → {CATALOG_OUT}")
    for e in entries:
        status = f"[installed {e['installed_version']}]" if e['install_status'] == 'installed' else "[bundled]"
        print(f"  {e['name']}=={e['version']}  {status}  ({e['filename']})")


def _cmd_list():
    entries = load_catalog()
    if not entries:
        print("No catalog found. Run: python3 provisions_catalog.py --scan")
        return
    print(f"{'Name':<30} {'Version':<12} {'Status':<12} {'File'}")
    print("-" * 80)
    for e in entries:
        status = f"installed({e['installed_version']})" if e['install_status'] == 'installed' else 'bundled'
        print(f"{e['name']:<30} {e['version']:<12} {status:<20} {e['filename']}")


if __name__ == '__main__':
    if '--scan' in sys.argv:
        _cmd_scan()
    elif '--list' in sys.argv:
        _cmd_list()
    else:
        print("Usage: python3 provisions_catalog.py --scan | --list")
        sys.exit(1)
