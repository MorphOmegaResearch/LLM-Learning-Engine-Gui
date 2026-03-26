#!/usr/bin/env python3
"""
Onboard Translator - Transformation Layer
-----------------------------------------
Translates raw prober manifests into draft Grep Flight Action buttons
with intelligent plumbing links.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Resolve path to taxonomy.py (should be in parent modules/ dir)
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    modules_dir = os.path.abspath(os.path.join(current_dir, '..', '..'))
    if modules_dir not in sys.path:
        sys.path.insert(0, modules_dir)
    from taxonomy import infer_system_type, map_system_type_to_hierarchy
    TAXONOMY_AVAILABLE = True
except ImportError:
    TAXONOMY_AVAILABLE = False

class OnboardTranslator:
    def __init__(self, cache_path: str):
        self.cache_path = Path(cache_path)
        self.repo_root = self.cache_path.parents[1]
        with open(self.cache_path, 'r') as f:
            self.cache = json.load(f)
            
        # Load event data for context enrichment
        self.event_data = self._load_event_data()

    def _load_event_data(self):
        """Load history from logs and backup manifests"""
        events = {"backups": {}, "logs": []}
        try:
            # 1. Backup Manifest
            manifest_path = self.cache_path.parent.parent / "modules" / "action_panel" / "grep_flight_v0_2b" / "backup_manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    events["backups"] = json.load(f)
            
            # 2. Log JSON
            log_path = manifest_path.parent / "log.json"
            if log_path.exists():
                with open(log_path, 'r') as f:
                    events["logs"] = json.load(f)
        except:
            pass
        return events

    def translate_all(self):
        draft_profiles = {}
        
        for file_path, data in self.cache.get("scanned_files", {}).items():
            version = data.get("version", "Unknown")
            manifest = data.get("manifest", {})
            file_name = Path(file_path).name
            
            # 1. Taxonomy Inference
            if TAXONOMY_AVAILABLE:
                system_type = infer_system_type(file_path)
                parent, sub, group = map_system_type_to_hierarchy(system_type, file_path=file_path)
                taxonomy = {"parent": parent, "sub": sub, "group": group, "type": system_type}
            else:
                taxonomy = {"parent": "Core Systems", "sub": "Uncategorized", "group": "Scripts", "type": "Unknown"}

            # 2. Access Chain & Functional Assessment
            access = manifest.get("access_chain", {"position": "unknown", "access_depth": 4})
            caps = manifest.get("capabilities", {"is_functional": False, "traits": [], "health_blueprint": 1.0})
            
            # Functional System vs Capability logic
            system_traits = {
                "position": access["position"],
                "depth": access["access_depth"],
                "is_functional": caps["is_functional"],
                "ui_components": len(manifest.get("plumbing", {}).get("ui_components", []))
            }

            # 3. Event Enrichment
            backups = self.event_data["backups"].get(str(Path(file_path).absolute()), [])
            usage_count = len([l for l in self.event_data["logs"] if l.get("target") == file_path])
            
            actions = self._generate_actions(manifest, taxonomy, caps)
            if actions:
                draft_profiles[f"{version}_{file_name}"] = {
                    "source_file": file_path,
                    "version": version,
                    "taxonomy": taxonomy,
                    "system_profile": system_traits,
                    "capabilities": caps["traits"],
                    "health_score": caps["health_blueprint"],
                    "event_stats": {
                        "backup_count": len(backups),
                        "usage_count": usage_count,
                        "last_backup": backups[-1]["timestamp"] if backups else None
                    },
                    "draft_actions": actions
                }
        
        return draft_profiles

    def _generate_actions(self, manifest, taxonomy, capabilities):
        actions = []
        cli_schema = manifest.get("cli_schema", {})
        plumbing = manifest.get("plumbing", {})
        
        # Determine Tab Affinity from Taxonomy
        affinity_map = {
            "UI & UX": "UI Main",
            "System Health": "Debug",
            "Intelligence": "Intelligence",
            "Planning & Workflow": "Tasks",
            "Tools & Arsenal": "Grep",
            "Version Control": "Inventory",
            "System Launch": "Morph",
            "Communication": "Chat"
        }
        affinity_tab = affinity_map.get(taxonomy["parent"], "Grep")

        # Preferred log/output
        preferred_log = "print"
        for log_call in plumbing.get("logs", []):
            if "traceback" in log_call["call"] or "engine.log" in log_call["call"]:
                preferred_log = log_call["call"]
                break

        for flag in cli_schema.get("flags", []):
            if flag["short"] == "-h": continue
            
            action_name = flag["long"] or flag["short"]
            clean_name = action_name.replace("--", "").replace("-", " ").title()
            
            # Capability Context Injection
            expects = flag["description"][:100]
            if not expects:
                traits = ", ".join(capabilities.get("traits", []))
                expects = f"Execute {traits} workflow"

            action = {
                "name": f"[Auto] {clean_name}",
                "type": "script",
                "command": manifest.get("target"),
                "args": f"{action_name}",
                "target_mode": "auto" if not flag["param"] else "manual",
                "output_to": "results" if "traceback" not in action_name else "traceback",
                "expectations": expects,
                "affinity_tab": affinity_tab,
                "taxonomy": taxonomy,
                "plumbing_ref": {
                    "log_pipe": preferred_log,
                    "logic_anchor": self._find_relevant_function(action_name, plumbing)
                }
            }
            actions.append(action)
            
        return actions

    def _find_relevant_function(self, flag_name, plumbing):
        """Link a flag to a function discovered in the AST"""
        clean_flag = flag_name.replace("--", "").replace("-", "_")
        for func in plumbing.get("function_chains", []):
            if clean_flag in func["name"]:
                return func["name"]
        return "main"

if __name__ == "__main__":
    cache_path = "/home/commander/3_Inventory/Warrior_Flow/.docv2_workspace/prober_cache.json"
    translator = OnboardTranslator(cache_path)
    drafts = translator.translate_all()
    
    out_path = Path(cache_path).parent / "draft_onboarding_actions.json"
    with open(out_path, "w") as f:
        json.dump(drafts, f, indent=4)
        
    print(f"✓ Soft-Test complete. Draft actions generated at: {out_path}")
