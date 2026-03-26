#!/usr/bin/env python3
"""Sync onboarder's consolidated menu to grep_flight's custom tools"""
import json
import os
from pathlib import Path

def sync_tools():
    # Load onboarder catalog
    # Assuming this script is in babel_data/inventory/
    # consolidated_menu.json is in the same directory
    menu_path = Path(__file__).parent / 'consolidated_menu.json'
    
    if not menu_path.exists():
        print(f"[!] No consolidated_menu.json found at {menu_path}")
        print("    Run: ./babel catalog (or python3 Os_Toolkit.py actions --run catalog)")
        return

    try:
        with open(menu_path, 'r') as f:
            menu = json.load(f)
    except Exception as e:
        print(f"[!] Error loading catalog: {e}")
        return

    # Convert to grep_flight format
    custom_tools = {
        "tool_profiles": {},
        "debug_scripts": [],
        "tool_suites": [],
        "source": "babel_onboarder",
        "version": "v01a"
    }

    count = 0
    for tool in menu.get('tools', []):
        path = tool.get('path', tool.get('command', ''))
        if not path:
            continue
        
        # Ensure path is absolute or resolve it
        # But grep_flight might expect paths relative or absolute. Absolute is safer.
        # tools in consolidated_menu should have absolute paths usually
        
        # Build args string
        args = tool.get('default_args', '')
        if 'cli_args' in tool and tool['cli_args']:
            args_list = tool['cli_args']
            if isinstance(args_list, list):
                args = ' '.join(args_list)
            else:
                args = str(args_list)

        custom_tools['tool_profiles'][path] = args
        custom_tools['debug_scripts'].append(path)

        if tool.get('type') == 'suite' or tool.get('category') == 'suite':
            custom_tools['tool_suites'].append(path)
        
        count += 1

    # Save to grep_flight config
    # Config location: ~/.babel/grep_flight_custom_tools.json
    config_dir = Path.home() / '.babel'
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_path = config_dir / 'grep_flight_custom_tools.json'

    try:
        with open(config_path, 'w') as f:
            json.dump(custom_tools, f, indent=2)
        print(f"[+] Synced {count} tools to grep_flight config")
        print(f"[+] Config: {config_path}")
    except Exception as e:
        print(f"[!] Error saving config: {e}")

if __name__ == '__main__':
    sync_tools()