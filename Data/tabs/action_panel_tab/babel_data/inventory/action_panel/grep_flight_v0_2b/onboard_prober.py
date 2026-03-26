#!/usr/bin/env python3
"""
Onboard Prober - Deep Logic & Argument Sensor with Orchestration
----------------------------------------------------------------
Generates a 'Diff-Blueprint' manifest. Uses hash-caching to avoid
redundant scanning of versions.
"""

import os
import sys
import re
import ast
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

class OnboardProber:
    """Sensor for deep AST analysis of a single Python file with Access Chain awareness"""
    
    def __init__(self, target_path: str):
        self.target_path = Path(target_path).resolve()
        self.manifest = {
            "timestamp": datetime.now().isoformat(),
            "target": str(self.target_path),
            "file_hash": self._get_file_hash(),
            "cli_schema": {},
            "access_chain": {
                "position": "unknown", # Tab, Action, Sub-module, Utility
                "parent_gui": None,
                "access_depth": 0
            },
            "capabilities": {
                "is_functional": False, # Has CLI/IO
                "traits": [], # Health Diagnosis, Intelligence, Communication
                "health_blueprint": 1.0 # 0.0 to 1.0
            },
            "plumbing": {
                "logs": [],
                "variable_strings": [],
                "function_chains": [],
                "ui_components": []
            },
            "dependencies": []
        }

    def _get_file_hash(self):
        """Generate MD5 hash to detect changes"""
        try:
            with open(self.target_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None

    def probe(self):
        """Run all sensors on the target script"""
        if not self.target_path.exists() or self.target_path.suffix != '.py':
            return {"error": "Invalid target. Must be a .py file."}

        # 1. Harvest CLI Arguments
        self._probe_argparse()

        # 2. Harvest Logic Plumbing (AST Analysis)
        self._probe_logic_structure()
        
        # 3. Resolve Access Chain Position
        self._probe_access_chain()
        
        # 4. Final Capability Score
        self._resolve_capabilities()

        return self.manifest

    def _probe_argparse(self):
        """Sensor: Capture --help output with GUI suppression"""
        try:
            # Set environment to suppress GUI
            env = os.environ.copy()
            env["DISPLAY"] = ""
            
            result = subprocess.run(
                [sys.executable, str(self.target_path), '--help'],
                capture_output=True,
                text=True,
                timeout=2, 
                env=env
            )
            if result.returncode == 0:
                self.manifest["cli_schema"] = self._parse_help_text(result.stdout)
                self.manifest["capabilities"]["is_functional"] = True
            else:
                output = result.stdout or result.stderr
                if "usage:" in output:
                    self.manifest["cli_schema"] = self._parse_help_text(output)
                    self.manifest["capabilities"]["is_functional"] = True
        except:
            pass

    def _probe_access_chain(self):
        """Identify position relative to main GUIs (uni_launch / grep_flight)"""
        path_str = str(self.target_path)
        
        # Heuristics based on project structure
        if "launcher" in path_str or "uni_launch" in path_str:
            self.manifest["access_chain"]["position"] = "Launcher/Root"
            self.manifest["access_chain"]["access_depth"] = 0
        elif "action_panel" in path_str or "grep_flight" in path_str:
            self.manifest["access_chain"]["position"] = "Action Panel"
            self.manifest["access_chain"]["access_depth"] = 1
        elif "/tabs/" in path_str:
            self.manifest["access_chain"]["position"] = "Tab Component"
            self.manifest["access_chain"]["access_depth"] = 2
        elif "/modules/" in path_str:
            self.manifest["access_chain"]["position"] = "Module Script"
            self.manifest["access_chain"]["access_depth"] = 3
        else:
            self.manifest["access_chain"]["position"] = "Nested Utility"
            self.manifest["access_chain"]["access_depth"] = 4

    def _resolve_capabilities(self):
        """Map traits and score health based on plumbing and imports"""
        traits = []
        plumbing = self.manifest["plumbing"]
        deps = self.manifest["dependencies"]
        
        # Trait Mapping
        if any(x in deps for x in ["pfc", "pylint", "ruff", "pyflakes"]):
            traits.append("Health Diagnosis")
        if any(x in deps for x in ["ollama", "anthropic", "google.generativeai"]):
            traits.append("Intelligence/AI")
        if any(x in deps for x in ["tkinter", "ttk"]):
            traits.append("UI/UX")
        if "pyperclip" in deps or any("chat" in s.lower() for s in plumbing["variable_strings"]):
            traits.append("Communication/Interaction")
            
        self.manifest["capabilities"]["traits"] = list(set(traits))
        
        # Health Blueprint Scoring (Experimental)
        score = 1.0
        # Penalty for syntax error during probe (already handled by ast.parse)
        if "error" in plumbing: score -= 0.5
        # Penalty for missing CLI in utility scripts
        if not self.manifest["capabilities"]["is_functional"] and self.manifest["access_chain"]["position"] == "Nested Utility":
            score -= 0.2
            
        self.manifest["capabilities"]["health_blueprint"] = max(0.0, score)

    def _parse_help_text(self, text: str) -> Dict:
        """Helper: Extract flags and descriptions using Regex"""
        schema = {"description": "", "flags": []}
        desc_match = re.search(r'(?:usage:.*\n\n)(.+?)(?:\n\noptions:|optional arguments:)', text, re.DOTALL)
        if desc_match:
            schema["description"] = desc_match.group(1).strip()

        arg_pattern = r'  (-[\w-]+)(?:, (--[\w-]+))?(?: (\w+))?\s+(.+?)(?=\n  -|$)'
        for match in re.finditer(arg_pattern, text, re.DOTALL):
            short, long, param, desc = match.groups()
            schema["flags"].append({
                "short": short,
                "long": long,
                "param": param,
                "description": desc.replace('\n', ' ').strip()
            })
        return schema

    def _probe_logic_structure(self):
        """Sensor: Deep AST dive for Logs, Strings, and Calls"""
        try:
            with open(self.target_path, "r") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                # 1. Capture Function Chains
                if isinstance(node, ast.FunctionDef):
                    self.manifest["plumbing"]["function_chains"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })

                # 2. Capture Data Piping (Logs/Prints)
                if isinstance(node, ast.Call):
                    call_name = self._get_call_name(node.func)
                    
                    if call_name and any(x in call_name.lower() for x in ["log", "print", "notify", "debug"]):
                        self.manifest["plumbing"]["logs"].append({
                            "call": call_name,
                            "line": node.lineno
                        })
                    
                    if call_name and any(x in call_name for x in ["Notebook", "add", "Menu", "add_command", "add_cascade", "add_tab"]):
                        label = ""
                        for keyword in node.keywords:
                            if keyword.arg in ["text", "label"]:
                                if isinstance(keyword.value, ast.Constant):
                                    label = str(keyword.value.value)
                                elif isinstance(keyword.value, ast.Str): # Support older python
                                    label = keyword.value.s
                        
                        self.manifest["plumbing"]["ui_components"].append({
                            "type": call_name,
                            "label": label,
                            "line": node.lineno
                        })

                # 3. Capture Variable Strings (Paths/Config)
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if len(node.value) > 5 and any(x in node.value for x in ["/", "\\", "http", ".json", ".py", ".log"]):
                        self.manifest["plumbing"]["variable_strings"].append({
                            "value": node.value,
                            "line": node.lineno
                        })

                # 4. Capture Imports (Dependencies)
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        self.manifest["dependencies"].append(alias.name)

                # 5. Capture Morph Context
                if "morph_context" not in self.manifest:
                    self.manifest["morph_context"] = {"features": [], "integrations": []}
                
                if isinstance(node, ast.ClassDef):
                    if node.name in ["ChangeTask", "GUIElement", "Snapshot"]:
                        self.manifest["morph_context"]["features"].append(node.name)
                
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        name = alias.name
                        if "guillm" in name or "morph" in name:
                            self.manifest["morph_context"]["integrations"].append("Morph Engine")
                        if "uni_launch" in name or "launcher" in name:
                            self.manifest["morph_context"]["integrations"].append("Universal Launcher")

        except Exception as e:
            self.manifest["plumbing"]["error"] = f"AST probe failed: {e}"

    def _get_call_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            name = self._get_call_name(node.value)
            return f"{name}.{node.attr}"
        return "unknown"

class ProberOrchestrator:
    """Manages multi-version scans and caching with sequential directory stepping"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.cache_path = self.project_root / ".docv2_workspace" / "prober_cache.json"
        self.stable_json = self.project_root / "stable.json"
        self.cache = self._load_cache()
        self.cache.setdefault("directories", {}) # New dir-level cache
        self.ignore_patterns = ["__pycache__", ".git", ".ruff_cache", "venv", ".docv2_workspace", "Python-master", "web_programming"]

    def _load_cache(self) -> Dict:
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r') as f:
                    return json.load(f)
            except: pass
        return {"scanned_files": {}, "directories": {}}

    def _save_cache(self):
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(self.cache, f, indent=4)

    def scan_version(self, version_name: str):
        """Perform a sequential, recursive scan of a specific version directory"""
        if not self.stable_json.exists():
            print(f"Error: stable.json missing at {self.stable_json}")
            return

        with open(self.stable_json, 'r') as f:
            stable_config = json.load(f)

        version_data = stable_config.get("versions", {}).get(version_name) or \
                       stable_config.get("grep_flight_versions", {}).get(version_name)
            
        if not version_data:
            print(f"Version {version_name} not found in configuration.")
            return

        version_path = self.project_root / version_data["path"]
        if not version_path.exists():
            print(f"  [ERROR] Path not found: {version_path}")
            return

        print(f"\n[ORCHESTRATOR] Entering Version Loop: {version_name}")
        print(f"  Root: {version_path}")
        
        self._step_through_directory(version_path, version_name)

    def _step_through_directory(self, current_dir: Path, version_name: str):
        """Recursive directory stepper with deterministic sequencing and Pruning"""
        
        # 1. Get and sort directory contents
        try:
            items = sorted(list(current_dir.iterdir()))
            stats = current_dir.stat()
            current_mtime = stats.st_mtime
            file_count = len([i for i in items if i.is_file()])
            
            # Pruning Logic: Check if directory itself changed
            dir_key = str(current_dir)
            cached_dir = self.cache["directories"].get(dir_key)
            
            # Note: We don't prune at the top level of the scan to ensure version association is updated
            # but we can prune sub-folders if their contents are identical.

            # Update dir cache
            self.cache["directories"][dir_key] = {
                "mtime": current_mtime,
                "file_count": file_count,
                "last_scanned": datetime.now().isoformat()
            }

        except PermissionError:
            print(f"  [SKIP] Permission Denied: {current_dir}")
            return

        # 2. Process Files in this directory first
        for item in items:
            if item.is_file() and item.suffix == '.py':
                if not any(p in str(item) for p in self.ignore_patterns):
                    self._process_file(item, version_name)

        # 3. Step into Sub-directories
        for item in items:
            if item.is_dir():
                # Check ignore list
                if item.name in self.ignore_patterns:
                    continue
                
                # Check if sub-dir mtime changed (Recursive Pruning)
                try:
                    sub_stats = item.stat()
                    sub_mtime = sub_stats.st_mtime
                    sub_items = list(item.iterdir())
                    sub_file_count = len([i for i in sub_items if i.is_file()])
                    
                    cached_sub = self.cache["directories"].get(str(item))
                    if cached_sub and cached_sub.get("mtime") == sub_mtime and cached_sub.get("file_count") == sub_file_count:
                        # Directory contents likely identical. 
                        # We still need to ensure files in this dir are linked to the current version in cache.
                        # For absolute optimization, we'd skip, but for now we dive once per version.
                        pass 
                except: pass

                print(f"  [STEP] Entering Directory: {item.relative_to(self.project_root)}")
                self._step_through_directory(item, version_name)

    def _process_file(self, path: Path, version: str):
        """Process file with Triple-Check validation (Size, Mtime, Hash) and Cross-Path Content Awareness"""
        try:
            stats = path.stat()
            current_size = stats.st_size
            current_mtime = stats.st_mtime
        except Exception as e:
            print(f"  [ERROR] Could not access {path.name}: {e}")
            return

        # 1. Quick Path-Specific Metadata Check
        cached = self.cache["scanned_files"].get(str(path))
        if cached:
            if cached.get("size") == current_size and cached.get("mtime") == current_mtime:
                return

        # 2. Deep Hash Check (Content Identity)
        try:
            with open(path, "rb") as f:
                current_hash = hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            print(f"  [ERROR] Could not hash {path.name}: {e}")
            return

        # 3. Cross-Path Content Check (Has this EXACT content been probed elsewhere?)
        if not cached or cached.get("hash") != current_hash:
            for cached_path, data in self.cache["scanned_files"].items():
                if data.get("hash") == current_hash:
                    # Found identical content probed at a different path!
                    # Inherit the manifest to avoid re-probing
                    self.cache["scanned_files"][str(path)] = {
                        "hash": current_hash,
                        "size": current_size,
                        "mtime": current_mtime,
                        "version": version,
                        "last_scanned": datetime.now().isoformat(),
                        "manifest": data["manifest"]
                    }
                    self._save_cache()
                    # print(f"    [LINK] {path.name} (Content match with {Path(cached_path).name})")
                    return

        if cached and cached.get("hash") == current_hash:
            # Content is same, but metadata (mtime) was updated
            self.cache["scanned_files"][str(path)].update({
                "size": current_size,
                "mtime": current_mtime
            })
            self._save_cache()
            return

        # 4. Full Probe (Actually new or changed content)
        print(f"    [PROBE] {path.name} (New or modified content detected)")
        prober = OnboardProber(str(path))
        manifest = prober.probe()
        
        self.cache["scanned_files"][str(path)] = {
            "hash": current_hash,
            "size": current_size,
            "mtime": current_mtime,
            "version": version,
            "last_scanned": datetime.now().isoformat(),
            "manifest": manifest
        }
        self._save_cache()

    def _get_md5(self, path):
        import hashlib
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Onboard Prober Orchestrator")
    parser.add_argument("--all", action="store_true", help="Scan all versions in stable.json")
    parser.add_argument("--versions", nargs="+", help="Specific version names to scan")
    parser.add_argument("--list", action="store_true", help="List available versions in stable.json")
    args = parser.parse_args()

    orchestrator = ProberOrchestrator("/home/commander/3_Inventory/Warrior_Flow")
    
    # Auto-detect all versions in stable.json
    with open(orchestrator.stable_json, 'r') as f:
        stable_data = json.load(f)
        
    if args.list:
        print("\nAvailable Versions:")
        for v in stable_data.get("versions", {}): print(f"  - {v}")
        print("\nGrep Flight Versions:")
        for v in stable_data.get("grep_flight_versions", {}): print(f"  - {v}")
        sys.exit(0)

    if args.all:
        # Scan standard versions
        versions = stable_data.get("versions", {})
        for v_name, v_info in versions.items():
            if v_info.get("status") != "Missing":
                orchestrator.scan_version(v_name)
                
        # Scan grep_flight versions
        gf_versions = stable_data.get("grep_flight_versions", {})
        for v_name in gf_versions:
            orchestrator.scan_version(v_name)
    elif args.versions:
        for v_name in args.versions:
            orchestrator.scan_version(v_name)
    else:
        # Default: current stable and current grep_flight
        current = stable_data.get("current_stable_version")
        current_gf = stable_data.get("current_grep_flight_version")
        
        if current:
            orchestrator.scan_version(current)
        if current_gf:
            orchestrator.scan_version(current_gf)
        
        if not current and not current_gf:
            print("No current version set. Use --all or --versions.")
    
    print("\n[COMPLETE] Prober Manifest Cache updated in .docv2_workspace/prober_cache.json")