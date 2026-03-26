"""
trainer_paths.py — Path constants for action_panel_tab when running inside Trainer.

Replaces Babel_v01a's self-referential path logic. All Trainer-relevant paths
are resolved relative to this file's location in tabs/action_panel_tab/.

Usage in Os_Toolkit.py / grep_flight_babel.py:
    try:
        from trainer_paths import TRAINER_PATHS as _TP
        TODOS_PATH  = _TP['todos']
        DATA_DIR    = _TP['data']
        PLANS_DIR   = _TP['plans']
        LOG_DIR     = _TP['log_dir']
        BUGS_PATH   = _TP['runtime_bugs']
    except ImportError:
        pass  # Running standalone outside Trainer — use own defaults
"""
from pathlib import Path

_ACTION_PANEL_ROOT = Path(__file__).parent          # tabs/action_panel_tab/
_TRAINER_DATA      = _ACTION_PANEL_ROOT.parent.parent  # Trainer/Data/

TRAINER_PATHS = {
    # Core data root
    "data":          str(_TRAINER_DATA),

    # Plans and todos
    "plans":         str(_TRAINER_DATA / "plans"),
    "todos":         str(_TRAINER_DATA / "plans" / "todos.json"),
    "checklist":     str(_TRAINER_DATA / "plans" / "checklist.json"),
    "runtime_bugs":  str(_TRAINER_DATA / "plans" / "runtime_bugs.json"),

    # Logs — action_panel writes to Trainer's DeBug/ dir
    "log_dir":       str(_TRAINER_DATA / "DeBug"),

    # Claude tasks sync target
    "claude_tasks":  str(Path.home() / ".claude" / "tasks"),

    # Babel action_panel self-reference (for internal tools that need it)
    "action_panel_root": str(_ACTION_PANEL_ROOT),
    "os_toolkit":    str(_ACTION_PANEL_ROOT / "Os_Toolkit.py"),
    "grep_flight":   str(_ACTION_PANEL_ROOT / "babel_data" / "inventory" /
                         "action_panel" / "grep_flight_v0_2b" / "grep_flight_babel.py"),
}

# Convenience: BABEL_ROOT for internal Babel tools that reference it
BABEL_ROOT = _ACTION_PANEL_ROOT
