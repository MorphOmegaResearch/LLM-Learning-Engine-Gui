#!/usr/bin/env python3
"""
Profile Viewer - Taxonomy & Capability Explorer
Fetches taxonomized data from measurement_registry.json
"""

import sys
import os
import json
import argparse
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="View Taxonomized Module Profiles")
    parser.add_argument("--target", type=str, help="Specific file path to view profile for")
    args = parser.parse_args()

    # Resolve paths
    current_dir = Path(__file__).parent
    repo_root = current_dir.parents[3]
    registry_path = current_dir.parents[2] / "measurement_registry.json"

    # Create UI
    root = tk.Tk()
    root.title(f"Profile Viewer - {args.target if args.target else 'Global'}")
    root.geometry("900x700")
    root.configure(bg='#1e1e1e')

    # Load Data
    data = {}
    if registry_path.exists():
        try:
            with open(registry_path, 'r') as f:
                data = json.load(f)
        except: pass

    # Header
    header = tk.Frame(root, bg='#1e1e1e', pady=15)
    header.pack(fill=tk.X, padx=20)
    tk.Label(header, text="👤 Taxonomized Capability Profiles", bg='#1e1e1e', fg='#4ec9b0', font=('Arial', 14, 'bold')).pack(side=tk.LEFT)
    tk.Label(header, text=f"Source: measurement_registry.json", bg='#1e1e1e', fg='#888888', font=('Arial', 9)).pack(side=tk.RIGHT)

    # Main List
    main_frame = tk.Frame(root, bg='#1e1e1e')
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    columns = ('Name', 'Type', 'Taxonomy', 'Confidence')
    tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=25)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150 if col != 'Taxonomy' else 350)
    
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    # Filtering Logic
    target_rel = ""
    if args.target:
        try:
            target_rel = str(Path(args.target).relative_to(repo_root))
        except: target_rel = args.target

    # Populate
    tools = data.get("tools", {})
    count = 0
    for tid, tdata in tools.items():
        if target_rel and target_rel not in tid: continue
        
        tax_str = " > ".join(tdata.get("taxonomy", []))
        conf = tdata.get("confidence", 0.0)
        conf_str = f"{conf*100:.0f}%"
        
        tree.insert('', 'end', values=(
            tdata.get("tool_id"),
            tdata.get("system_type", "Unknown"),
            tax_str,
            conf_str
        ))
        count += 1

    if count == 0:
        tk.Label(root, text="No profiles found for this target in registry.", bg='#1e1e1e', fg='#ff5555').pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    main()
