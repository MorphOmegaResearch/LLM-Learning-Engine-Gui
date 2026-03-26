#!/usr/bin/env python3
"""
Consolidated Tool Launcher
==========================
Generated: 2026-02-08T22:52:45.253601
Version: 1.0.0

Launch tool: Babel System Catalog
"""

import os
import sys
import json
import argparse
import subprocess
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Any

# Load menu configuration
MENU_FILE = Path(__file__).parent / "consolidated_menu.json"

def load_menu() -> Dict[str, Any]:
    """Load the menu configuration."""
    with open(MENU_FILE, 'r') as f:
        return json.load(f)

def list_tools(menu_data: Dict[str, Any]):
    """List all available tools."""
    print(f"\n{'='*60}")
    print(f"{menu_data['config'].get('name', 'Available Tools')}")
    print(f"{'='*60}")
    
    categories = {}
    for tool in menu_data['tools']:
        category = tool['category']
        if category not in categories:
            categories[category] = []
        categories[category].append(tool)
    
    for category, tools in categories.items():
        print(f"\n{category.upper()}:")
        for tool in tools:
            shortcut = tool.get('shortcut', '')
            shortcut_display = f" [{shortcut}]" if shortcut else ""
            print(f"  {tool['display_name']}{shortcut_display}")
            if tool.get('description'):
                print(f"    {tool['description']}")

def launch_tool(tool_id: str, menu_data: Dict[str, Any], args: List[str] = None):
    """Launch a specific tool."""
    for tool in menu_data['tools']:
        if tool['id'] == tool_id or tool['tool_id'] == tool_id:
            print(f"Launching: {tool['display_name']}")
            # In a real implementation, this would execute the actual tool
            # For now, just show what would happen
            print(f"Tool ID: {tool['tool_id']}")
            print(f"Command: {tool['command']}")
            if args:
                print(f"Arguments: {' '.join(args)}")
            return True
    
    print(f"Tool not found: {tool_id}")
    return False

def launch_gui(menu_data: Dict[str, Any]):
    """Launch GUI version of the menu."""
    try:
        from tkinter import Tk, ttk, messagebox
        import tkinter as tk
        
        class ToolLauncherGUI:
            def __init__(self, menu_data: Dict[str, Any]):
                self.menu_data = menu_data
                self.root = Tk()
                self.root.title(menu_data['config'].get('name', 'Tool Launcher'))
                self.root.geometry("800x600")
                
                self.setup_ui()
            
            def setup_ui(self):
                # Create notebook for categories
                notebook = ttk.Notebook(self.root)
                notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                # Group tools by category
                categories = {}
                for tool in self.menu_data['tools']:
                    category = tool['category']
                    if category not in categories:
                        categories[category] = []
                    categories[category].append(tool)
                
                # Create tab for each category
                for category, tools in categories.items():
                    frame = ttk.Frame(notebook)
                    notebook.add(frame, text=category.title())
                    
                    # Create listbox for tools
                    listbox = tk.Listbox(frame, font=("Courier", 12))
                    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
                    listbox.configure(yscrollcommand=scrollbar.set)
                    
                    for tool in tools:
                        shortcut = tool.get('shortcut', '')
                        shortcut_display = f" [{shortcut}]" if shortcut else ""
                        listbox.insert(tk.END, f"{tool['display_name']}{shortcut_display}")
                    
                    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                    
                    # Bind double-click
                    listbox.bind('<Double-Button-1>', lambda e, t=tools: self.on_tool_selected(t, listbox.curselection()))
                
                # Add status bar
                status_frame = ttk.Frame(self.root)
                status_frame.pack(fill=tk.X, padx=5, pady=2)
                
                ttk.Label(status_frame, 
                         text=f"{len(self.menu_data['tools'])} tools available").pack(side=tk.LEFT)
                
                ttk.Button(self.root, text="Refresh", command=self.refresh).pack(pady=5)
                ttk.Button(self.root, text="Exit", command=self.root.quit).pack(pady=5)
            
            def on_tool_selected(self, tools, selection):
                if selection:
                    index = selection[0]
                    if 0 <= index < len(tools):
                        tool = tools[index]
                        messagebox.showinfo("Tool Selected", 
                                          f"Selected: {tool['display_name']}\n\n"
                                          f"To launch from CLI:\n"
                                          f"  python launcher.py --tool {tool['id']}")
            
            def refresh(self):
                messagebox.showinfo("Refresh", "Menu would be refreshed from disk")
            
            def run(self):
                self.root.mainloop()
        
        gui = ToolLauncherGUI(menu_data)
        gui.run()
        
    except ImportError as e:
        print(f"GUI not available: {e}")
        list_tools(menu_data)

def main():
    parser = argparse.ArgumentParser(
        description='Consolidated Tool Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # List all tools
  onboarder.py --list
  
  # Launch specific tool
  onboarder.py --tool TOOL_ID [-- ARGS...]
  
  # Launch GUI
  onboarder.py --gui
  
  # Get help for a tool
  onboarder.py --help-tool TOOL_ID
        """
    )
    
    parser.add_argument('--list', '-l', action='store_true', help='List all available tools')
    parser.add_argument('--tool', '-t', help='Launch specific tool by ID or name')
    parser.add_argument('--gui', '-g', action='store_true', help='Launch GUI interface')
    parser.add_argument('--help-tool', help='Show help for a specific tool')
    parser.add_argument('args', nargs='*', help='Arguments to pass to the tool')
    
    args = parser.parse_args()
    
    # Load menu data
    try:
        menu_data = load_menu()
    except Exception as e:
        print(f"Error loading menu: {e}")
        return 1
    
    if args.list:
        list_tools(menu_data)
    
    elif args.tool:
        launch_tool(args.tool, menu_data, args.args)
    
    elif args.gui:
        launch_gui(menu_data)
    
    elif args.help_tool:
        print(f"Help for tool {args.help_tool} would be displayed here")
        # In reality, would show the tool's --help output
    
    else:
        parser.print_help()
        print(f"\nUse --list to see available tools")

if __name__ == '__main__':
    main()
