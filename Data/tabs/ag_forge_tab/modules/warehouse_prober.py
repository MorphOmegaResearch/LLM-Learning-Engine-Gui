#!/usr/bin/env python3
"""
Warehouse Prober - Local Example Fetching Engine
------------------------------------------------
Scans Python-master and other version directories to find matching 
scripts based on user-defined keywords/goals.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any
import re

class WarehouseProber:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.warehouse_path = self.root_dir / "versions" / "Warrior_Flow_v0_9w_Monkey_Buisness_v1" / "Modules" / "Ag_Forge_v1c" / "modules" / "Python-master"
        self.versions_path = self.root_dir / "versions"
        self.ignore_dirs = [".git", "__pycache__", "venv", ".ruff_cache", "logs"]

    def search_examples(self, query: str) -> List[Dict]:
        """Search for scripts matching the query in warehouse and versions"""
        results = []
        keywords = [k.lower() for k in query.split()]
        
        # 1. Scan Warehouse (Python-master)
        if self.warehouse_path.exists():
            results.extend(self._scan_dir(self.warehouse_path, keywords, "Warehouse"))
            
        # 2. Scan All Versions
        if self.versions_path.exists():
            results.extend(self._scan_dir(self.versions_path, keywords, "Version-Library"))
            
        # Sort results by score (number of keyword matches)
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:10] # Return top 10

    def _scan_dir(self, directory: Path, keywords: List[str], source_label: str) -> List[Dict]:
        found = []
        for root, dirs, files in os.walk(directory):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            for file in files:
                if file.endswith(".py"):
                    file_path = Path(root) / file
                    score = 0
                    description = ""
                    
                    # Check filename match
                    if any(k in file.lower() for k in keywords):
                        score += 2
                        
                    # Check content match (docstrings/imports)
                    try:
                        with open(file_path, 'r', errors='ignore') as f:
                            head = "".join([f.readline() for _ in range(50)]).lower()
                            
                            # Extract docstring (simple regex)
                            doc_match = re.search(r'"""(.*?) """', head, re.DOTALL)
                            if doc_match:
                                description = doc_match.group(1).strip().split('\n')[0]
                                
                            for k in keywords:
                                if k in head:
                                    score += 1
                    except:
                        continue
                        
                    if score > 0:
                        found.append({
                            "name": file,
                            "path": str(file_path.relative_to(self.root_dir)),
                            "description": description or "No description found.",
                            "source": source_label,
                            "score": score
                        })
        return found

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 warehouse_prober.py <keywords>")
        sys.exit(1)
        
    query = " ".join(sys.argv[1:])
    prober = WarehouseProber("/home/commander/3_Inventory/Warrior_Flow")
    matches = prober.search_examples(query)
    
    if not matches:
        print(f"No examples found for: {query}")
    else:
        print(f"--- FOUND {len(matches)} EXAMPLES FOR: {query} ---")
        for i, m in enumerate(matches, 1):
            print(f"{i}. [{m['source']}] {m['name']} (Score: {m['score']})")
            print(f"   Path: {m['path']}")
            print(f"   Note: {m['description']}\n")
