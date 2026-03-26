import json
import os
import shutil
import subprocess
import sys
import hashlib
import ast
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Resolve path to taxonomy.py
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    modules_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if modules_dir not in sys.path:
        sys.path.insert(0, modules_dir)
    from taxonomy import infer_system_type, map_system_type_to_hierarchy
    TAXONOMY_AVAILABLE = True
except ImportError:
    TAXONOMY_AVAILABLE = False

class VersionManager:
    """Refactored Version Manager: Tracks modules as first-class entities with taxonomy-aware profiling."""

    def __init__(self, stable_json_path: str):
        self.stable_json_path = Path(stable_json_path)
        self.config = self._load_config()
        self.project_root = self.stable_json_path.parent
        self.backup_manifest_path = Path(__file__).parent / "backup_manifest.json"
        self.sync_modules_from_disk()

    def _load_config(self) -> Dict[str, Any]:
        """Load the stable.json configuration, ensuring all sections exist."""
        if not self.stable_json_path.exists():
            config = {
                "current_stable_version": "",
                "versions": {},
                "modules": {},
                "component_taxonomy": {}
            }
        else:
            try:
                with open(self.stable_json_path, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error loading stable.json: {e}")
                config = {}

        # Ensure all keys exist
        config.setdefault("versions", {})
        config.setdefault("modules", {})
        config.setdefault("component_taxonomy", {})
        return config

    def sync_modules_from_disk(self):
        """
        Scans /modules and nested scripts.
        Updates stable.json with taxonomized module profiles.
        """
        modules_root = self.project_root / "modules"
        if not modules_root.exists():
            return

        changed = False
        
        # 1. Recursive scan of modules
        for py_file in modules_root.rglob("*.py"):
            if "__pycache__" in str(py_file): continue
            
            rel_path = str(py_file.relative_to(self.project_root))
            mod_name = py_file.stem
            
            # Taxonomy Check
            if TAXONOMY_AVAILABLE:
                stype = infer_system_type(rel_path)
                parent, sub, group = map_system_type_to_hierarchy(stype, file_path=rel_path)
            else:
                stype, parent, sub, group = ("Unknown", "Core", "Uncategorized", "Scripts")

            # Component Type Differentiation (Tab, Panel, UI, etc.)
            comp_type, features = self._differentiate_component(py_file)
            
            # Check for existing entry
            if rel_path not in self.config["modules"]:
                self.config["modules"][rel_path] = {
                    "name": mod_name,
                    "type": comp_type,
                    "taxonomy": {
                        "system_type": stype,
                        "hierarchy": [parent, sub, group]
                    },
                    "features": features,
                    "status": "Stable",
                    "health": 100,
                    "last_scanned": datetime.now().isoformat()
                }
                changed = True
            else:
                # Update dynamic metadata
                entry = self.config["modules"][rel_path]
                entry["features"] = features
                entry["taxonomy"]["system_type"] = stype
                entry["taxonomy"]["hierarchy"] = [parent, sub, group]
                entry["last_scanned"] = datetime.now().isoformat()

        if changed:
            self.save_config()

    def _differentiate_component(self, file_path: Path) -> Tuple[str, List[str]]:
        """Analyze code to determine if it's a Tab, Panel, Menu, or CLI module."""
        comp_type = "Script"
        features = []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                tree = ast.parse(content)
                
            # Heuristics
            lower_content = content.lower()
            if "notebook.add" in content or "add_tab" in lower_content:
                comp_type = "Tab/UI"
            elif "action_panel" in lower_content or "workflow_actions" in lower_content:
                comp_type = "Action Panel"
            elif "tk.menu" in content or "add_command" in content:
                comp_type = "Menu/UX"
            elif "argparse" in content:
                comp_type = "CLI Module"
                
            # Extract high-level features (classes and primary functions)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    features.append(f"Class:{node.name}")
                elif isinstance(node, ast.FunctionDef) and not node.name.startswith('_'):
                    features.append(f"Func:{node.name}")
                    
        except:
            pass
            
        return comp_type, features

    def get_backup_history(self, rel_path: str) -> List[Dict]:
        """Retrieve restoration points and diff history for a module item."""
        if not self.backup_manifest_path.exists():
            return []
            
        try:
            with open(self.backup_manifest_path, 'r') as f:
                manifest = json.load(f)
            
            abs_path = str((self.project_root / rel_path).absolute())
            return manifest.get(abs_path, [])
        except:
            return []

    def restore_item(self, rel_path: str, backup_index: int = -1) -> bool:
        """100% copy-restore of a specific item from manifest list."""
        history = self.get_backup_history(rel_path)
        if not history: return False
        
        backup_item = history[backup_index]
        src = Path(backup_item["backup_path"])
        dst = self.project_root / rel_path
        
        if src.exists():
            try:
                # Create 'Bug' marked copy of CURRENT before overwriting (Safety)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safety_copy = dst.parent / f"{dst.stem}_EmergencyRestore_{timestamp}{dst.suffix}"
                shutil.copy2(dst, safety_copy)
                
                # Restore
                shutil.copy2(src, dst)
                return True
            except Exception as e:
                print(f"Restore failed: {e}")
        return False

    def save_config(self):
        """Save the current configuration to stable.json."""
        try:
            with open(self.stable_json_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving stable.json: {e}")

    def get_modules_by_taxonomy(self, parent_cat: str) -> List[str]:
        """Filter tracked modules by taxonomy parent."""
        results = []
        for path, data in self.config.get("modules", {}).items():
            if data["taxonomy"]["hierarchy"][0] == parent_cat:
                results.append(path)
        return results

    def run_pfc_for_version(self, version_name: str):
        """Placeholder for running a Pre-Flight Check on a version."""
        return {"status": "PFC Ready", "details": "Taxonomy-aware check active."}

    def get_backup_path(self) -> Path:
        """Get the unified backup storage path."""
        return self.project_root / "data" / "backups"