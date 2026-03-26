#!/usr/bin/env python3
"""
config_schema.py - Configuration Schema Definition & Validation

Defines the complete schema for monitor_config.json and provides validation.
"""

import json
import logging
from typing import Any, Dict, List, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Schema Definition
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_SCHEMA = {
    "integrity": {
        "type": dict,
        "required": True,
        "fields": {
            "verified_hash": {"type": str, "required": False},
            "last_verified": {"type": str, "required": False},
            "file_hashes": {"type": dict, "required": False},
            "config_baseline": {"type": dict, "required": False}
        }
    },
    "security": {
        "type": dict,
        "required": True,
        "fields": {
            "known_apis": {"type": list, "required": True},
            "suspicious_keywords": {"type": list, "required": True},
            "allow": {"type": list, "required": False},
            "alias": {"type": list, "required": False},
            "server": {"type": list, "required": False}
        }
    },
    "user_prefs": {
        "type": dict,
        "required": True,
        "fields": {
            "theme": {"type": str, "required": True, "values": ["dark", "light", "monokai"]},
            "show_line_numbers": {"type": bool, "required": False},
            "refresh_rate": {"type": int, "required": False, "min": 100, "max": 10000},
            "window_geometry": {"type": str, "required": False},
            "ui_dim": {"type": dict, "required": False},
            "hier_colors": {"type": dict, "required": False},
            "context_menu_actions": {"type": list, "required": False},
            "inspection_config": {"type": dict, "required": False},
            "brain_map": {"type": dict, "required": False}
        }
    }
}

# Default configuration values
DEFAULT_CONFIG = {
    "integrity": {
        "verified_hash": "",
        "last_verified": "",
        "file_hashes": {},
        "config_baseline": {
            "known_apis": [],
            "allow": [],
            "alias": [],
            "server": []
        }
    },
    "security": {
        "known_apis": [
            "api.openai.com",
            "anthropic.com",
            "googleapis.com",
            "github.com",
            "localhost",
            "127.0.0.1"
        ],
        "suspicious_keywords": [
            "telemetry",
            "analytics",
            "tracking",
            "eval(",
            "exec(",
            "base64.b64decode"
        ],
        "allow": [],
        "alias": [],
        "server": []
    },
    "user_prefs": {
        "theme": "dark",
        "show_line_numbers": True,
        "refresh_rate": 2000,
        "window_geometry": "1280x800",
        "ui_dim": {
            "left_panel": 250,
            "right_panel": 320,
            "menu_est_width": 140,
            "menu_est_height": 150,
            "standard_offset": 10,
            "sticky_gap": 5
        },
        "hier_colors": {
            "Import": "#c586c0",
            "Class": "#ffd93d",
            "Function": "#6bcb77",
            "Method": "#4d96ff",
            "Variable": "#9cdcfe",
            "String/IP": "#ce9178",
            "File": "#ffffff"
        },
        "context_menu_actions": [
            {"label": "Route to Editor", "action": "route_to_editor"},
            {"label": "Route to Hier-View", "action": "route_to_hier"},
            {"label": "Deep Inspect", "action": "inspect_current_file"},
            {"label": "Quick Scan", "action": "run_security_scan"},
            {"label": "Export Context", "action": "export_entity_context"}
        ],
        "inspection_config": {
            "auto_open": True,
            "show_all_strings": False,
            "highlight_risks": True,
            "hover_delay": 500,
            "enable_hover": True,
            "indicator_pos": "right",
            "sticky_bind_selection": True
        },
        "brain_map": {
            "enable_debug": False,
            "auto_rotate": False,
            "show_edges": True,
            "show_labels": True,
            "update_interval_ms": 2000,
            "show_fps_overlay": False
        },
        "process_monitor": {
            "filters": {
                "show_categories": [],  # Empty = show all
                "hide_categories": [],
                "hide_system_idle": True,
                "min_cpu_threshold": 0.1,
                "min_mem_threshold": 0.1
            },
            "alerts": {
                "cpu_threshold": 80.0,
                "mem_threshold": 85.0,
                "enable_notifications": False,
                "alert_sound": False
            },
            "grouping": {
                "auto_group_children": True,
                "max_group_size": 50,
                "collapse_system_groups": True
            },
            "safety": {
                "enable_auto_kill": False,
                "kill_rules": []
            }
        },
        "logging": {
            "retention_days": 30,
            "max_log_size_mb": 100,
            "auto_cleanup": True,
            "levels": {
                "gui": "INFO",
                "popup": "INFO",
                "monitor": "INFO",
                "scanner": "WARNING",
                "brain_viz": "INFO"
            },
            "rotation": {
                "enabled": True,
                "when": "midnight",
                "backup_count": 7
            }
        },
        "editor": {
            "font": {
                "family": "Monospace",
                "size": 11,
                "weight": "normal"
            },
            "behavior": {
                "tab_width": 4,
                "use_spaces": True,
                "auto_indent": True,
                "line_wrap": False,
                "auto_save": False,
                "auto_save_interval": 30
            },
            "limits": {
                "max_file_size_mb": 10,
                "warn_large_files": True,
                "large_file_threshold_mb": 5
            },
            "syntax": {
                "theme": "vscode_dark",
                "enable_highlighting": True
            }
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Validation Functions
# ─────────────────────────────────────────────────────────────────────────────

def validate_config(config: Dict[str, Any], schema: Dict[str, Any] = None) -> Tuple[bool, List[str]]:
    """
    Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate
        schema: Schema to validate against (default: CONFIG_SCHEMA)

    Returns:
        Tuple of (is_valid, error_messages)
    """
    if schema is None:
        schema = CONFIG_SCHEMA

    errors = []

    # Check required top-level sections
    for section_name, section_schema in schema.items():
        if section_schema.get("required", False) and section_name not in config:
            errors.append(f"Missing required section: {section_name}")
            continue

        if section_name not in config:
            continue

        section_data = config[section_name]

        # Type check
        expected_type = section_schema.get("type")
        if expected_type and not isinstance(section_data, expected_type):
            errors.append(f"Section '{section_name}' should be {expected_type.__name__}, got {type(section_data).__name__}")
            continue

        # Validate fields if present
        if "fields" in section_schema and isinstance(section_data, dict):
            for field_name, field_schema in section_schema["fields"].items():
                if field_schema.get("required", False) and field_name not in section_data:
                    errors.append(f"Missing required field: {section_name}.{field_name}")
                    continue

                if field_name not in section_data:
                    continue

                field_value = section_data[field_name]

                # Type check
                expected_type = field_schema.get("type")
                if expected_type and not isinstance(field_value, expected_type):
                    errors.append(f"Field '{section_name}.{field_name}' should be {expected_type.__name__}, got {type(field_value).__name__}")

                # Value constraints
                if "values" in field_schema and field_value not in field_schema["values"]:
                    errors.append(f"Field '{section_name}.{field_name}' must be one of {field_schema['values']}, got '{field_value}'")

                # Range constraints
                if "min" in field_schema and isinstance(field_value, (int, float)) and field_value < field_schema["min"]:
                    errors.append(f"Field '{section_name}.{field_name}' must be >= {field_schema['min']}, got {field_value}")

                if "max" in field_schema and isinstance(field_value, (int, float)) and field_value > field_schema["max"]:
                    errors.append(f"Field '{section_name}.{field_name}' must be <= {field_schema['max']}, got {field_value}")

    return (len(errors) == 0, errors)


def apply_defaults(config: Dict[str, Any], defaults: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Apply default values to config for missing keys.

    Args:
        config: Configuration dictionary
        defaults: Default values (default: DEFAULT_CONFIG)

    Returns:
        Config with defaults applied
    """
    if defaults is None:
        defaults = DEFAULT_CONFIG

    result = config.copy()

    for key, default_value in defaults.items():
        if key not in result:
            result[key] = default_value
        elif isinstance(default_value, dict) and isinstance(result[key], dict):
            # Recursively apply defaults for nested dicts
            result[key] = apply_defaults(result[key], default_value)

    return result


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get config value by dot notation path.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path (e.g., "user_prefs.process_monitor.filters.hide_system_idle")
        default: Default value if key not found

    Returns:
        Config value or default

    Example:
        >>> get_config_value(config, "user_prefs.theme")
        "dark"
    """
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


def set_config_value(config: Dict[str, Any], key_path: str, value: Any) -> Dict[str, Any]:
    """
    Set config value by dot notation path.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated key path
        value: Value to set

    Returns:
        Modified config

    Example:
        >>> set_config_value(config, "user_prefs.theme", "light")
    """
    keys = key_path.split(".")
    current = config

    for i, key in enumerate(keys[:-1]):
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value
    return config


# ─────────────────────────────────────────────────────────────────────────────
# Testing & CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Config Schema Validator")
    parser.add_argument("config_file", nargs="?", default="monitor_config.json",
                       help="Config file to validate")
    parser.add_argument("--generate-defaults", action="store_true",
                       help="Generate default config file")
    parser.add_argument("--output", "-o", help="Output file for generated config")

    args = parser.parse_args()

    if args.generate_defaults:
        output_file = args.output or "monitor_config_defaults.json"
        with open(output_file, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        print(f"✓ Generated default config: {output_file}")
        sys.exit(0)

    # Validate config file
    try:
        with open(args.config_file, 'r') as f:
            config = json.load(f)

        is_valid, errors = validate_config(config)

        if is_valid:
            print(f"✓ Config file '{args.config_file}' is valid!")

            # Apply defaults and show what's missing
            config_with_defaults = apply_defaults(config)
            missing_keys = []

            def find_missing(original, with_defaults, prefix=""):
                for key in with_defaults:
                    full_key = f"{prefix}.{key}" if prefix else key
                    if key not in original:
                        missing_keys.append(full_key)
                    elif isinstance(with_defaults[key], dict) and isinstance(original.get(key), dict):
                        find_missing(original[key], with_defaults[key], full_key)

            find_missing(config, DEFAULT_CONFIG)

            if missing_keys:
                print(f"\nℹ️  {len(missing_keys)} optional keys using defaults:")
                for key in missing_keys[:10]:  # Show first 10
                    print(f"  - {key}")
                if len(missing_keys) > 10:
                    print(f"  ... and {len(missing_keys) - 10} more")
        else:
            print(f"✗ Config file '{args.config_file}' has errors:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)

    except FileNotFoundError:
        print(f"✗ Config file not found: {args.config_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        sys.exit(1)
