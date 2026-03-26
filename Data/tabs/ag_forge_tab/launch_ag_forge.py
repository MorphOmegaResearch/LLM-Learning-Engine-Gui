#!/usr/bin/env python3
"""
Ag Forge Unified Launcher
-------------------------
Launches the complete Agriculture Knowledge Suite:
1. AI Orchestrator (Background Service)
2. Quick Clip (Research & Tasking Interface)
3. Meta Learn Ag (Knowledge Base & Staging)

Handles unified startup and shutdown of all components.
"""

import subprocess
import sys
import time
import os
import signal
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox
import argparse
import datetime
import traceback

# Configuration
BASE_DIR = Path(__file__).parent.resolve()
DATA_ROOT = BASE_DIR / "knowledge_forge_data"
LOG_DIR = BASE_DIR / "logs"
MODULES_DIR = BASE_DIR / "modules"
CRASH_FILE = LOG_DIR / "crash_counter.txt"

# Ensure directories exist
DATA_ROOT.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Process handles
processes = []
session_config = None
session_token = None
DEBUG_MODE = False

def log(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] [{level}] {message}"
    print(formatted)
    
    # Write to master log
    try:
        with open(LOG_DIR / "master_launch.log", "a") as f:
            f.write(formatted + "\n")
    except Exception:
        pass # Fallback if logging fails

def show_crash_dialog(error_msg, trace):
    """Show a fallback GUI dialog for crashes"""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Ag Forge Critical Error",
            f"The application encountered a critical error and could not start.\n\nError: {error_msg}\n\nSee logs/master_launch.log for details."
        )
        # Optional: Save full trace to separate file
        with open(LOG_DIR / f"crash_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log", "w") as f:
            f.write(trace)
        root.destroy()
    except:
        # If Tkinter fails (e.g. no DISPLAY), fallback to stderr
        print(f"CRITICAL: Could not show error dialog.\n{trace}", file=sys.stderr)

def check_safe_mode():
    """Check crash counter and offer Safe Mode"""
    crashes = 0
    if CRASH_FILE.exists():
        try:
            crashes = int(CRASH_FILE.read_text().strip())
        except:
            pass
    
    if crashes >= 3:
        log("Detected repeated crashes. Entering Recovery Mode check...", "WARNING")
        try:
            root = tk.Tk()
            root.withdraw()
            choice = messagebox.askyesno(
                "Safe Mode",
                "Ag Forge has failed to start multiple times.\n\n"
                "Do you want to reset the configuration and try Safe Mode?\n"
                "(This will not delete your knowledge data)"
            )
            root.destroy()
            
            if choice:
                log("User accepted Safe Mode. Resetting config...", "INFO")
                # Backup config
                config_file = DATA_ROOT / "config.json"
                if config_file.exists():
                    config_file.rename(DATA_ROOT / "config.json.bak")
                
                # Reset crash counter
                CRASH_FILE.write_text("0")
                return True
        except:
            pass
            
    # Increment crash counter (will be cleared on successful launch)
    CRASH_FILE.write_text(str(crashes + 1))
    return False

def clear_crash_counter():
    """Reset crash counter on successful launch"""
    if CRASH_FILE.exists():
        CRASH_FILE.write_text("0")

def diagnose_environment():
    """Perform pre-flight checks from DISPLAY_debug.md"""
    log("Running Environment Diagnostics...", "DEBUG")
    
    # 1. Check DISPLAY
    display = os.environ.get("DISPLAY")
    if not display:
        log("CRITICAL: DISPLAY environment variable is not set!", "ERROR")
        log("  > Solution: export DISPLAY=:0", "HINT")
    else:
        log(f"DISPLAY: {display}", "DEBUG")

    # 2. Check Tkinter
    try:
        import tkinter
        log(f"Tkinter Version: {tkinter.TkVersion}", "DEBUG")
        root = tkinter.Tk()
        root.destroy()
        log("Tkinter GUI initialization test: PASSED", "DEBUG")
    except Exception as e:
        log(f"Tkinter GUI initialization test: FAILED ({e})", "ERROR")
        return False

    # 3. Check Modules Directory
    if not MODULES_DIR.exists():
        log(f"Modules directory missing: {MODULES_DIR}", "ERROR")
        return False

    return True

def set_data_permissions(read_only=True):
    """Recursively set permissions for data directory (Linux/Unix only)"""
    if sys.platform == "win32": return
    
    dir_mode = 0o500 if read_only else 0o700
    file_mode = 0o400 if read_only else 0o600
    
    log(f"Setting data permissions to {'Read-Only' if read_only else 'Read-Write'}...", "DEBUG")
    
    # We walk bottom-up for locking (files then dirs) and top-down for unlocking
    if read_only:
        for root, dirs, files in os.walk(DATA_ROOT, topdown=False):
            for f in files:
                try: os.chmod(os.path.join(root, f), file_mode)
                except: pass
            os.chmod(root, dir_mode)
    else:
        # Unlocking must be top-down so we can enter directories to unlock files
        os.chmod(DATA_ROOT, dir_mode)
        for root, dirs, files in os.walk(DATA_ROOT):
            for d in dirs:
                try: os.chmod(os.path.join(root, d), dir_mode)
                except: pass
            for f in files:
                try: os.chmod(os.path.join(root, f), file_mode)
                except: pass

def get_screen_geometry():
    """Get screen dimensions using a temporary Tk root"""
    try:
        root = tk.Tk()
        root.withdraw()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception as e:
        log(f"Failed to detect screen geometry: {e}", "WARNING")
        return 1920, 1080  # Fallback

def launch_component(name, command, log_file):
    """Launch a component as a subprocess"""
    log(f"Starting {name}...", "INFO")
    try:
        # Ensure python runs unbuffered
        if command[0].endswith('python') or command[0].endswith('python3'):
            if '-u' not in command:
                command.insert(1, '-u')

        if DEBUG_MODE:
            # In Debug mode, stream directly to the parent console
            proc = subprocess.Popen(
                command,
                cwd=BASE_DIR,
                stdout=sys.stdout,  # Stream to console
                stderr=sys.stderr,  # Stream to console
                preexec_fn=os.setsid
            )
            # We don't have file handles to close later, so use None
            processes.append((name, proc, None, None))
        else:
            # Production mode: log to files
            out_path = str(log_file).replace('.log', '.out.log')
            err_path = str(log_file).replace('.log', '.err.log')
            
            stdout_f = open(out_path, "w")
            stderr_f = open(err_path, "w")
            
            proc = subprocess.Popen(
                command,
                cwd=BASE_DIR,
                stdout=stdout_f,
                stderr=stderr_f,
                preexec_fn=os.setsid
            )
            processes.append((name, proc, stdout_f, stderr_f))
            
        log(f"{name} started (PID: {proc.pid})", "INFO")
        return proc
    except Exception as e:
        log(f"Failed to start {name}: {e}", "ERROR")
        return None

def cleanup():
    """Terminate all launched processes"""
    log("Shutting down components...", "INFO")
    for name, proc, out_f, err_f in reversed(processes):
        if proc.poll() is None:  # If still running
            log(f"Stopping {name}...", "DEBUG")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
            except Exception as e:
                log(f"Error stopping {name}: {e}", "ERROR")
        
        # Close file handles if they exist
        if out_f: out_f.close()
        if err_f: err_f.close()
    
    # Lock data after processes stop
    set_data_permissions(read_only=True)
    log("Shutdown complete.", "INFO")

def on_auth_success(config, token=None):
    global session_config, session_token
    session_config = config
    session_token = token or "dev_token"
    # Unlock data once authenticated
    set_data_permissions(read_only=False)

def start_suite():
    # Calculate layouts
    screen_width, screen_height = get_screen_geometry()
    
    # Simple split: Meta Learn gets left 60%, Quick Clip gets right 40%
    usable_height = screen_height - 100
    meta_width = int(screen_width * 0.6)
    clip_width = int(screen_width * 0.4) - 20
    
    meta_geo = f"{meta_width}x{usable_height}+0+0"
    clip_geo = f"{clip_width}x{usable_height}+{meta_width}+0"
    
    # Local Data Paths
    orchestrator_data = DATA_ROOT / "orchestrator_context"
    
    # 1. AI Orchestrator
    launch_component(
        "AI Orchestrator",
        [sys.executable, str(MODULES_DIR / "ai_orchestrator.py"), 
         "--no-gui", "--base-dir", str(orchestrator_data),
         "--session-token", session_token],
        LOG_DIR / "orchestrator.log"
    )
    
    time.sleep(2)

    # 2. Meta Learn Agriculture
    launch_component(
        "Meta Learn Ag",
        [sys.executable, str(MODULES_DIR / "meta_learn_agriculture.py"), 
         "--geometry", meta_geo, "--base-dir", str(DATA_ROOT),
         "--session-token", session_token],
        LOG_DIR / "meta_learn.log"
    )

    # 3. Quick Clip
    launch_component(
        "Quick Clip",
        [sys.executable, str(MODULES_DIR / "quick_clip/clip.py"), 
         "--geometry", clip_geo],
        LOG_DIR / "quick_clip.log"
    )

    log("All components launched.", "INFO")
    
    # If we got here, launch was likely successful (components started)
    # We clear the crash counter after a short delay to ensure stability
    threading.Timer(10.0, clear_crash_counter).start()

def main():
    try:
        # Import moved inside try/catch to catch import errors
        from modules.onboarding import OnboardingGUI, LoginGUI
        
        parser = argparse.ArgumentParser(description="Ag Forge Launcher")
        parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
        parser.add_argument("--analyze", action="store_true", help="Run Tkinter Project Analyzer before launch")
        args = parser.parse_args()
        
        global DEBUG_MODE
        DEBUG_MODE = args.debug

        # --- Safe Mode Check ---
        check_safe_mode()

        if args.analyze:
            log("Running Tkinter Project Analyzer...", "INFO")
            try:
                from modules.dev_tools.tkinter_analyzer import TkinterAnalyzer
                analyzer = TkinterAnalyzer()
                analysis = analyzer.select_project(str(BASE_DIR))
                log(f"Analysis complete. Found {analysis.stats.get('total_issues')} issues ({analysis.stats.get('tk_specific')} Tkinter-specific).", "INFO")
                if analysis.stats.get('tk_specific') > 0:
                    log("Check logs/analysis_report.txt for details.", "WARNING")
                    with open(LOG_DIR / "analysis_report.txt", "w") as f:
                        f.write("TKINTER ANALYSIS REPORT\n" + "="*23 + "\n")
                        for issue in analysis.tk_specific_issues:
                            f.write(f"[{issue.severity.upper()}] {issue.file}:{issue.line} - {issue.code}: {issue.message}\n")
            except Exception as e:
                log(f"Analysis failed: {e}", "ERROR")

        if DEBUG_MODE:
            if not diagnose_environment():
                log("Environment check failed. Aborting launch.", "CRITICAL")
                sys.exit(1)

        config_file = DATA_ROOT / "config.json"
        
        if not config_file.exists():
            log("No configuration found. Starting onboarding...", "INFO")
            onboarding = OnboardingGUI(DATA_ROOT, on_auth_success)
            onboarding.run()
        else:
            log("Existing configuration found. Starting login...", "INFO")
            login = LoginGUI(DATA_ROOT, on_auth_success)
            login.run()

        if session_config:
            start_suite()
            try:
                while True:
                    all_dead = True
                    for name, proc, _, _ in processes:
                        status = proc.poll()
                        if status is None:
                            all_dead = False
                        elif name == "Meta Learn Ag":
                            if status != 0:
                                log(f"Meta Learn Ag crashed with exit code {status}", "ERROR")
                                # Read stderr
                                if (LOG_DIR / "meta_learn.err.log").exists():
                                    with open(LOG_DIR / "meta_learn.err.log", "r") as f:
                                        log(f"Last Error: {f.read()}", "ERROR")
                            log("Main application closed. Exiting...", "INFO")
                            raise KeyboardInterrupt
                    if all_dead: break
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                cleanup()
        else:
            log("Authentication cancelled or failed. Exiting.", "WARNING")
            
    except Exception as e:
        # GLOBAL CRASH HANDLER
        trace = traceback.format_exc()
        log(f"CRITICAL LAUNCHER CRASH: {e}", "CRITICAL")
        log(trace, "CRITICAL")
        show_crash_dialog(str(e), trace)
        sys.exit(1)

if __name__ == "__main__":
    main()