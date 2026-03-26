#!/usr/bin/env python3
"""
Regenerate orchestrator tool schema configs based on tool_permissions.json
Matches tool_permissions.json exactly to type_catalog_v2.json orchestrator requirements
"""

import json
import sys
from pathlib import Path

# Get directory paths
current_dir = Path(__file__).parent
tool_schemas_path = current_dir.parent / "tool_schemas.py"
tool_permissions_path = current_dir.parent.parent.parent / "tool_permissions.json"

# Load tool permissions
with open(tool_permissions_path, 'r') as f:
    tool_permissions = json.load(f)

# Get orchestrator permissions per class from tool_permissions.json
orchestrator_perms = tool_permissions["type_permissions"]["orchestrator"]

# Load TOOL_SCHEMAS from tool_schemas.py (parse Python dict)
import importlib.util
spec = importlib.util.spec_from_file_location("tool_schemas", tool_schemas_path)
tool_schemas_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_schemas_module)
TOOL_SCHEMAS = tool_schemas_module.TOOL_SCHEMAS

# Generate schema configs for each class
classes = ["novice", "skilled", "adept", "expert", "master", "grand_master"]

for class_level in classes:
    if class_level not in orchestrator_perms:
        print(f"Warning: {class_level} not in tool_permissions.json orchestrator section")
        continue

    # Get enabled tools for this class
    enabled_tools_list = orchestrator_perms[class_level]

    # Build enabled_tools dict and tools array
    enabled_tools = {}
    tools = []

    for tool_name in enabled_tools_list:
        # Check if it's the wildcard "*" (master level)
        if tool_name == "*":
            enabled_tools["all"] = True
            # Add a meta-tool entry
            if "all" in TOOL_SCHEMAS:
                tools.append(TOOL_SCHEMAS["all"])
            continue

        # Mark as enabled
        enabled_tools[tool_name] = True

        # Add schema if available
        if tool_name in TOOL_SCHEMAS:
            tools.append(TOOL_SCHEMAS[tool_name])
        else:
            print(f"Warning: {tool_name} not found in TOOL_SCHEMAS")

    # Build the config
    config = {
        "description": f"Tool schema for Orchestrator {class_level}",
        "type": "orchestrator",
        "class": class_level,
        "enabled_tools": enabled_tools,
        "tools": tools
    }

    # Write to file
    output_path = current_dir / f"orchestrator_{class_level}.json"
    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Generated: {output_path.name} ({len(tools)} tools)")

print("\nOrchestrator schema configs regenerated successfully!")
