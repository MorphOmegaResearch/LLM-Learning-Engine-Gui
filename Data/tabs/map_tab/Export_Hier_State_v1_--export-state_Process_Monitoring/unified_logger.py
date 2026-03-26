#!/usr/bin/env python3
"""
unified_logger.py - Unified Logging System for Process Monitoring Suite
All modules should use this for consistent logging to /logs directory
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Global Constants
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")

# Ensure logs directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ─────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────────────────────────────────────

_loggers = {}  # Cache of configured loggers
_current_log_file = None  # Track current log file for reference
_session_initialized = False

def initialize_session(session_name="session"):
    """
    Initialize a single log file for the entire application session.
    All subsequent calls to get_logger will use this file.
    """
    global _current_log_file, _session_initialized
    if _session_initialized:
        return _current_log_file
        
    # Check for custom destination in config
    custom_dest = ""
    try:
        import json
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(script_dir, "monitor_config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
            custom_dest = config.get('user_prefs', {}).get('logging', {}).get('custom_destination', "")
    except:
        pass

    if custom_dest and os.path.isdir(os.path.dirname(custom_dest)):
        _current_log_file = custom_dest
    else:
        log_filename = datetime.now().strftime(f"{session_name}_%Y%m%d_%H%M%S.log")
        _current_log_file = os.path.join(LOG_DIR, log_filename)
        
    _session_initialized = True
    
    # Root-level entry for the session
    with open(_current_log_file, 'a') as f:
        f.write(f"\n=== SESSION START: {datetime.now()} ===\n")
        
    return _current_log_file

def get_logger(module_name="app", console_output=True, level=None):
    """
    Get a configured logger for a module.
    If a session is initialized, it uses the session log file.
    """
    global _current_log_file

    # Return cached logger if already configured
    if module_name in _loggers:
        return _loggers[module_name]

    # Initialize session if not already done (fallback)
    if not _session_initialized:
        initialize_session()

    # Get level from config if not specified
    if level is None:
        try:
            import json
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_file = os.path.join(script_dir, "monitor_config.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                level_str = config.get('user_prefs', {}).get('logging', {}).get('levels', {}).get(module_name, 'INFO')
                level = getattr(logging, level_str.upper(), logging.INFO)
            else:
                level = logging.INFO
        except:
            level = logging.INFO

    # Create logger
    logger = logging.getLogger(module_name)
    logger.setLevel(level)

    # Clear any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Formatter for consistent output - module name is included in format
    formatter = logging.Formatter('%(asctime)s - [%(name)s] - %(levelname)s - %(message)s')

    # File handler - use the shared session log file
    file_handler = logging.FileHandler(_current_log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    # Console handler (optional)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    # Cache and return
    _loggers[module_name] = logger
    logger.info(f"Logger linked to session log → {_current_log_file}")

    return logger

def get_current_log_file():
    """Get the path to the current log file."""
    return _current_log_file

def setup_exception_handler(logger, enable_popup=False):
    """
    Setup global exception handler to log uncaught exceptions.
    
    Args:
        logger: Logger instance to use for exception logging
        enable_popup: Whether to show a tkinter error dialog
    """
    def handle_exception(exc_type, exc_value, exc_traceback):
        # Allow KeyboardInterrupt to exit cleanly
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Log the exception
        logger.critical("UNCAUGHT EXCEPTION", exc_info=(exc_type, exc_value, exc_traceback))

        # Show error dialog if requested
        if enable_popup:
            try:
                import tkinter as tk
                from tkinter import messagebox
                # Create hidden root if none exists
                try:
                    if not tk._default_root:
                        r = tk.Tk()
                        r.withdraw()
                except: pass
                
                log_file = get_current_log_file()
                messagebox.showerror("System Error", 
                                   f"An uncaught exception occurred:\n\n{exc_value}\n\n"
                                   f"Details logged to: {log_file}")
            except:
                pass

        # Print to stderr for visibility
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)

    sys.excepthook = handle_exception

# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

def log_startup(logger, app_name, version=None):
    """Log application startup with banner."""
    logger.info("=" * 70)
    logger.info(f"{app_name} - Started")
    if version:
        logger.info(f"Version: {version}")
    logger.info(f"Log Directory: {LOG_DIR}")
    logger.info(f"Python: {sys.version.split()[0]}")
    logger.info("=" * 70)

def log_shutdown(logger, app_name):
    """Log application shutdown."""
    logger.info("=" * 70)
    logger.info(f"{app_name} - Shutdown Complete")
    logger.info("=" * 70)

def get_recent_logs(module_prefix=None, limit=10):
    """
    Get list of recent log files.

    Args:
        module_prefix: Filter by module name (e.g., "gui", "monitor")
        limit: Maximum number of logs to return

    Returns:
        List of (filename, full_path) tuples, sorted by modification time (newest first)
    """
    if not os.path.exists(LOG_DIR):
        return []

    logs = []
    for filename in os.listdir(LOG_DIR):
        if not filename.endswith('.log'):
            continue
        if module_prefix and not filename.startswith(module_prefix):
            continue

        full_path = os.path.join(LOG_DIR, filename)
        mtime = os.path.getmtime(full_path)
        logs.append((filename, full_path, mtime))

    # Sort by modification time, newest first
    logs.sort(key=lambda x: x[2], reverse=True)

    return [(name, path) for name, path, _ in logs[:limit]]

# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test the logger
    test_logger = get_logger("test", console_output=True)
    log_startup(test_logger, "Unified Logger Test", "1.0")

    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    test_logger.error("Error message")

    print(f"\nCurrent log file: {get_current_log_file()}")
    print("\nRecent logs:")
    for name, path in get_recent_logs(limit=5):
        print(f"  {name}")

    log_shutdown(test_logger, "Unified Logger Test")
