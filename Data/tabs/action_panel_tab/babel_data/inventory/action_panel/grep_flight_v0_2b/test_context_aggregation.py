#!/usr/bin/env python3
"""
MOCK TEST: Morph Effect Context Aggregation
Simulates the [Toggle Context] call from grep_flight_v2.py
"""

import os
import sys
import json
from pathlib import Path

def mock_test():
    # Setup Paths
    current_dir = Path(__file__).parent
    v_root = current_dir.parents[3]
    repo_root = v_root
    
    # 1. Simulate the BottomPanel State
    class MockConfig:
        WORKFLOW_COLORS = {}
        BG_COLOR = "#1a1a1a"

    class MockPanel:
        def __init__(self):
            self.version_root = v_root
            self.repo_root = repo_root
            self.config = MockConfig()
            
            # Simulated target
            from tkinter import StringVar
            # We can't easily use real StringVar without a root, so we mock .get()
            class MockVar:
                def __init__(self, val):
                    self.val = val
                def get(self):
                    return self.val
            
            self.target_var = MockVar(str(v_root / "modules" / "morph" / "guillm.py"))
            self.pattern_var = MockVar("")
            self.last_tool_context = {"action": "Preflight", "status": "PASS"}
            
            # Load VersionManager for real data
            sys.path.insert(0, str(current_dir))
            from version_manager import VersionManager
            self.version_manager = VersionManager(str(v_root / "stable.json"))

        # Re-importing the actual method logic for testing
        def gather_context(self):
            # This is a copy of the logic from grep_flight_v2.py
            context_parts = []
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            target = self.target_var.get()
            
            context_parts.append("=== 5xW EVENT CLASSIFICATION ===")
            context_parts.append(f"What: Mock Context Test")
            context_parts.append(f"When: {timestamp}")
            context_parts.append(f"Where: {target}")
            context_parts.append(f"How: Automated Test Script")
            context_parts.append("")

            # 2. Module Metadata
            if target and os.path.exists(target):
                context_parts.append(f"--- Targeted File: {os.path.basename(target)} ---")
                rel_path = str(Path(target).relative_to(self.repo_root))
                if rel_path in self.version_manager.config.get("modules", {}):
                    mod_data = self.version_manager.config["modules"][rel_path]
                    context_parts.append(f"Taxonomy: {' > '.join(mod_data.get('taxonomy', {}).get('hierarchy', []))}")
                    context_parts.append(f"Features: {', '.join(mod_data.get('features', []))[:200]}...")
            
            return "\n".join(context_parts)

    panel = MockPanel()
    payload = panel.gather_context()
    
    print("\n--- AGGREGATED CONTEXT PAYLOAD ---")
    print(payload)
    print("----------------------------------\n")
    
    with open("mock_context_output.log", "w") as f:
        f.write(payload)
    print("✓ Payload saved to mock_context_output.log")

if __name__ == "__main__":
    mock_test()
