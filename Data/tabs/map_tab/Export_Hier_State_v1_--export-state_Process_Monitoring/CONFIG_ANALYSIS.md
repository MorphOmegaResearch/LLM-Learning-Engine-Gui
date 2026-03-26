# Configuration System Analysis & Expansion Proposal

**Date**: 2026-01-26
**Status**: Review & Planning Phase

---

## Current State Assessment

### ✅ **What's Working Well**

#### 1. **Modular Structure**
```json
{
    "integrity": {...},      // File hashing & verification
    "security": {...},       // Known APIs, suspicious keywords
    "user_prefs": {...}      // UI settings, themes, layouts
}
```
- Clean separation of concerns
- Easy to understand and navigate
- Extensible design

#### 2. **ConfigManager Class** (`process_organizer.py`)
- Centralized config loading/saving
- Integrity verification built-in
- Security baseline tracking
- Global singleton (`CM`) for easy access

#### 3. **Existing Config Coverage**
| Category | Settings | Usage |
|----------|----------|-------|
| **Integrity** | File hashes, verification timestamps | ✅ Active |
| **Security** | Known APIs, suspicious keywords | ✅ Active |
| **UI Themes** | Dark/Light/Monokai color schemes | ✅ Active |
| **Layout** | Panel widths, tooltip positions | ✅ Active |
| **Hier-View** | Syntax highlighting colors | ✅ Active |
| **Context Menu** | Custom right-click actions | ✅ Active |
| **Inspection** | Hover delays, indicator position | ✅ Active |
| **Brain Map** | Debug mode, rotation, edges | ✅ Active (NEW) |

### ❌ **Configuration Gaps**

#### 1. **Process Monitoring Settings**
**Missing:**
- Process filter rules (show/hide categories)
- CPU/Memory alert thresholds
- Process grouping preferences
- Auto-kill rules for suspicious processes
- Process priority overrides

**Current Workaround:** Hardcoded in `get_category()` function

#### 2. **Logging Configuration**
**Missing:**
- Log retention policy (days to keep)
- Log level per module (DEBUG, INFO, WARNING)
- Log rotation settings
- Automatic log cleanup
- Log export preferences

**Current Workaround:** Hardcoded in each module

#### 3. **Editor Settings**
**Missing:**
- Font family and size
- Tab width (spaces vs tabs)
- Auto-save interval
- Syntax highlighting themes
- Line wrap preferences
- Max file size to open

**Current Workaround:** Hardcoded defaults

#### 4. **Security Scan Configuration**
**Missing:**
- Scan depth (recursive levels)
- File type exclusions (.pyc, .log, etc.)
- Size limits for scanning
- Whitelist/blacklist paths
- Custom security rules
- Scan scheduling (cron-like)

**Current Workaround:** Command-line args only

#### 5. **Network/Process Communication**
**Missing:**
- Trusted local ports
- Network timeout settings
- Connection tracking preferences
- Communication logging level
- IPC detection rules

**Current Workaround:** Not configurable

#### 6. **Performance Settings**
**Missing:**
- Render FPS targets
- Update intervals per component
- Memory usage limits
- Artist count limits for brain map
- LOD (Level of Detail) thresholds

**Current Workaround:** Hardcoded in components

#### 7. **Keyboard Shortcuts**
**Missing:**
- Custom keybindings
- Action shortcuts (Ctrl+S, Ctrl+F, etc.)
- Tab navigation shortcuts

**Current Workaround:** Not implemented

#### 8. **Export/Import Settings**
**Missing:**
- Config import/export
- Profile management (dev, production, etc.)
- Backup/restore config
- Sync settings across machines

**Current Workaround:** Manual file copying

---

## Proposed Config Expansion

### Phase 1: Critical Settings (High Priority)

#### A. **Process Monitoring Config**
```json
{
    "process_monitor": {
        "filters": {
            "show_categories": ["MY SCRIPTS", "DEV TOOLS"],
            "hide_categories": [],
            "hide_system_idle": true,
            "min_cpu_threshold": 0.1,
            "min_mem_threshold": 0.1
        },
        "alerts": {
            "cpu_threshold": 80.0,
            "mem_threshold": 85.0,
            "enable_notifications": true,
            "alert_sound": false
        },
        "grouping": {
            "auto_group_children": true,
            "max_group_size": 50,
            "collapse_system_groups": true
        },
        "safety": {
            "enable_auto_kill": false,
            "kill_rules": [
                {
                    "name_pattern": "suspicious.*",
                    "cpu_threshold": 95,
                    "duration_seconds": 60
                }
            ]
        }
    }
}
```

**Usage:**
```python
proc_cfg = CM.config['process_monitor']
if proc.cpu_percent() > proc_cfg['alerts']['cpu_threshold']:
    alert_user()
```

#### B. **Logging Config**
```json
{
    "logging": {
        "retention_days": 30,
        "max_log_size_mb": 100,
        "auto_cleanup": true,
        "levels": {
            "gui": "INFO",
            "monitor": "INFO",
            "scanner": "WARNING",
            "brain_viz": "DEBUG"
        },
        "rotation": {
            "enabled": true,
            "when": "midnight",
            "backup_count": 7
        },
        "export": {
            "auto_export": false,
            "export_path": "./log_exports",
            "format": "json"
        }
    }
}
```

**Usage:**
```python
from unified_logger import get_logger
log_cfg = CM.config['logging']
logger = get_logger("module", level=log_cfg['levels'].get('module', 'INFO'))
```

#### C. **Editor Config**
```json
{
    "editor": {
        "font": {
            "family": "Monospace",
            "size": 11,
            "weight": "normal"
        },
        "behavior": {
            "tab_width": 4,
            "use_spaces": true,
            "auto_indent": true,
            "line_wrap": false,
            "auto_save": false,
            "auto_save_interval": 30
        },
        "limits": {
            "max_file_size_mb": 10,
            "warn_large_files": true,
            "large_file_threshold_mb": 5
        },
        "syntax": {
            "theme": "vscode_dark",
            "enable_highlighting": true
        }
    }
}
```

### Phase 2: Enhanced Features (Medium Priority)

#### D. **Security Scan Config**
```json
{
    "security_scan": {
        "depth": {
            "max_recursive_depth": 10,
            "follow_symlinks": false
        },
        "exclusions": {
            "file_patterns": ["*.pyc", "*.log", "*.swp", "__pycache__"],
            "directories": ["node_modules", ".git", "venv", ".venv"],
            "size_limit_mb": 50
        },
        "whitelist_paths": [
            "/usr/lib",
            "/opt/python"
        ],
        "custom_rules": [
            {
                "name": "Check for crypto miners",
                "pattern": "(stratum|mining|hashrate)",
                "severity": "high"
            }
        ],
        "scheduling": {
            "enabled": false,
            "cron": "0 2 * * *",
            "scan_on_startup": true
        }
    }
}
```

#### E. **Network/Communication Config**
```json
{
    "network": {
        "trusted_ports": [22, 80, 443, 5432, 27017],
        "timeouts": {
            "connection_timeout": 5.0,
            "read_timeout": 10.0
        },
        "tracking": {
            "log_all_connections": false,
            "log_suspicious_only": true,
            "detect_port_scanning": true
        },
        "ipc": {
            "detect_shared_memory": true,
            "detect_unix_sockets": true,
            "log_ipc_events": true
        }
    }
}
```

#### F. **Performance Config**
```json
{
    "performance": {
        "brain_map": {
            "target_fps": 30,
            "max_artists": 150,
            "lod_enabled": true,
            "lod_thresholds": {
                "low": 200,
                "medium": 100,
                "high": 50
            }
        },
        "process_monitor": {
            "update_interval_ms": 2000,
            "batch_size": 100
        },
        "memory": {
            "max_usage_mb": 500,
            "warn_at_mb": 400,
            "gc_aggressive": false
        }
    }
}
```

### Phase 3: Power User Features (Low Priority)

#### G. **Keyboard Shortcuts Config**
```json
{
    "keybindings": {
        "global": {
            "save_file": "Ctrl+S",
            "find": "Ctrl+F",
            "quit": "Ctrl+Q",
            "toggle_monitor": "Ctrl+M"
        },
        "editor": {
            "comment_line": "Ctrl+/",
            "duplicate_line": "Ctrl+D",
            "goto_line": "Ctrl+G"
        },
        "brain_map": {
            "toggle_rotation": "R",
            "refresh_data": "F5",
            "toggle_edges": "E"
        }
    }
}
```

#### H. **Profile Management**
```json
{
    "profiles": {
        "active": "development",
        "available": {
            "development": {
                "logging": "DEBUG",
                "performance": "balanced"
            },
            "production": {
                "logging": "WARNING",
                "performance": "optimized"
            },
            "security_audit": {
                "logging": "INFO",
                "scan_depth": "maximum"
            }
        }
    }
}
```

---

## Implementation Plan

### Step 1: Config Schema Definition
Create `config_schema.py`:
```python
CONFIG_SCHEMA = {
    "process_monitor": {
        "filters": {...},
        "alerts": {...},
        ...
    },
    ...
}

def validate_config(config):
    """Validate config against schema"""
    pass

def apply_defaults(config):
    """Fill in missing values with defaults"""
    pass
```

### Step 2: Expand ConfigManager
Add to `process_organizer.py`:
```python
class ConfigManager:
    def get(self, key_path, default=None):
        """Get config value by dot notation: CM.get('process_monitor.filters.hide_system_idle')"""
        pass

    def set(self, key_path, value):
        """Set config value by dot notation"""
        pass

    def reset_to_defaults(self, section=None):
        """Reset config section to defaults"""
        pass

    def export_config(self, filepath):
        """Export config to file"""
        pass

    def import_config(self, filepath, merge=True):
        """Import config from file"""
        pass
```

### Step 3: Config UI Enhancements
Expand `shared_gui.py` config tabs:
- Process Monitor Settings
- Logging Preferences
- Editor Settings
- Security Rules
- Performance Tuning
- Keybindings
- Profile Manager

### Step 4: Live Config Reload
Add hot-reload capability:
```python
def watch_config_file():
    """Watch for config file changes and reload"""
    pass
```

### Step 5: Config Validation
- Schema validation on load
- Type checking
- Range validation
- Dependency checking (e.g., can't disable X if Y is enabled)

---

## Backwards Compatibility

### Migration Strategy
1. **Version tracking**: Add `config_version: 2` field
2. **Auto-migration**: Detect old format, convert to new
3. **Fallback**: Use defaults for missing keys
4. **Warning**: Log when using deprecated config format

### Example Migration:
```python
def migrate_config_v1_to_v2(config):
    if 'config_version' not in config or config['config_version'] < 2:
        # Add new sections with defaults
        config['process_monitor'] = DEFAULT_PROCESS_MONITOR
        config['logging'] = DEFAULT_LOGGING
        config['config_version'] = 2
        logging.info("Config migrated from v1 to v2")
    return config
```

---

## Config Utilities to Build

### 1. **Config Diff Tool**
```bash
python3 config_diff.py old_config.json new_config.json
```
Output: Shows what changed

### 2. **Config Validator**
```bash
python3 validate_config.py monitor_config.json
```
Output: Validates against schema, shows errors

### 3. **Config Generator**
```bash
python3 generate_config.py --template development > monitor_config.json
```
Output: Generates config from template

### 4. **Config Explorer**
```bash
python3 explore_config.py monitor_config.json
# Interactive TUI to browse/edit config
```

### 5. **Config Backup Manager**
```bash
python3 backup_config.py --create  # Creates timestamped backup
python3 backup_config.py --restore backup_20260126.json
python3 backup_config.py --list    # Shows all backups
```

---

## Priority Recommendations

### Implement First (This Week):
1. ✅ **Process Monitor Config** - Most requested, high impact
2. ✅ **Logging Config** - Essential for debugging
3. ✅ **Editor Config** - Improves UX significantly

### Implement Second (Next Week):
4. **Security Scan Config** - Enhances security features
5. **Performance Config** - Optimize brain map
6. **Config Utilities** - Validator, backup tool

### Implement Third (Future):
7. **Keyboard Shortcuts** - Power user feature
8. **Profile Management** - Advanced workflow
9. **Config UI Expansion** - GUI for all settings

---

## Testing Strategy

### Unit Tests
```python
def test_config_loading():
    cm = ConfigManager()
    assert cm.get('process_monitor.filters.hide_system_idle') == True

def test_config_validation():
    assert validate_config(invalid_config) == False

def test_config_migration():
    old = load_config_v1()
    new = migrate_config_v1_to_v2(old)
    assert new['config_version'] == 2
```

### Integration Tests
- Load config → Apply to GUI → Verify behavior
- Change config → Save → Reload → Verify persistence
- Import config → Merge → Verify no data loss

---

## Documentation Needs

1. **CONFIG_GUIDE.md** - Complete reference for all settings
2. **CONFIG_EXAMPLES.md** - Common configurations
3. **CONFIG_MIGRATION.md** - How to upgrade configs
4. **API_REFERENCE.md** - ConfigManager API docs

---

## Summary

**Current Config System**: ⭐⭐⭐⭐ (4/5)
- Good foundation
- Clean structure
- Working well for basic needs

**After Expansion**: ⭐⭐⭐⭐⭐ (5/5)
- Comprehensive coverage
- Power user features
- Professional-grade tooling

**Estimated Effort**:
- Phase 1: 8-12 hours
- Phase 2: 6-8 hours
- Phase 3: 4-6 hours
- **Total**: 18-26 hours

**ROI**: Very High
- Reduces hardcoded values
- Improves maintainability
- Enhances user experience
- Enables advanced workflows
