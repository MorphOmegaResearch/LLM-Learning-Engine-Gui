#!/usr/bin/env python3
"""
Cross-platform bootstrap for OpenCode Trainer

Features:
- Creates a virtual environment in .venv
- Installs requirements.txt
- Launches the UI (Data/interactive_ui.py), with fallback to Data/interactive_trainer_gui_NEW.py

Usage:
  python scripts/bootstrap.py              # create venv, install, launch UI
  python scripts/bootstrap.py --no-launch  # create venv, install only
  python scripts/bootstrap.py --ui new     # force launch NEW UI file
  python scripts/bootstrap.py --ui old     # force launch OLD UI file
"""
import os
import sys
import subprocess
import shutil
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
PY_EXE = None

def find_python() -> str:
    # Prefer current interpreter
    return sys.executable or shutil.which("python3") or shutil.which("python")

def run(cmd, cwd=None, env=None):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd or str(ROOT), env=env)

def ensure_venv():
    if not VENV_DIR.exists():
        print("Creating virtual environment:", VENV_DIR)
        venv.EnvBuilder(with_pip=True, clear=False, upgrade=False).create(str(VENV_DIR))
    # pick venv python
    if os.name == 'nt':
        pe = VENV_DIR / 'Scripts' / 'python.exe'
    else:
        pe = VENV_DIR / 'bin' / 'python'
    return str(pe)

def pip_install(py, *pkgs):
    run([py, "-m", "pip", "install", "-U", "pip", "wheel"])  # upgrade basics
    run([py, "-m", "pip", "install", "-r", "requirements.txt"]) if Path("requirements.txt").exists() else None
    if pkgs:
        run([py, "-m", "pip", "install", *pkgs])

def launch_ui(py, ui_mode: str | None):
    # Decide which UI to launch
    ui_new = ROOT / 'Data' / 'interactive_trainer_gui_NEW.py'
    ui_old = ROOT / 'Data' / 'interactive_ui.py'
    if ui_mode == 'new' and ui_new.exists():
        target = ui_new
    elif ui_mode == 'old' and ui_old.exists():
        target = ui_old
    else:
        target = ui_old if ui_old.exists() else ui_new
    if not target.exists():
        print("No UI script found to launch.")
        return
    run([py, str(target)])

def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-launch", action="store_true", help="Do not launch the UI after setup")
    ap.add_argument("--ui", choices=["new", "old"], default=None, help="Force which UI script to launch")
    args = ap.parse_args(argv)

    base_py = find_python()
    if not base_py:
        print("Python not found. Please install Python 3.10+ and re-run.")
        sys.exit(1)

    vpy = ensure_venv()
    pip_install(vpy)

    if not args.no_launch:
        launch_ui(vpy, args.ui)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except subprocess.CalledProcessError as e:
        print(f"Bootstrap failed: {e}")
        sys.exit(e.returncode or 1)

