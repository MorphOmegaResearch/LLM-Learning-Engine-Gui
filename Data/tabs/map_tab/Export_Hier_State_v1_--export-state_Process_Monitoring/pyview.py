#!/usr/bin/env python3
"""
PyView - Enhanced Python Project Visualizer
Extracts Classes, Functions, Variables, and Relationships.
"""

import ast
import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from unified_logger import get_logger

# Initialize logger
logging = get_logger("pyview")

# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CodeElement:
    """A class, function, variable, or import in a file."""
    name: str
    kind: str  # 'class', 'function', 'method', 'variable', 'import', 'string'
    line: int
    end_line: int = 0
    value: Optional[str] = None
    children: List['CodeElement'] = field(default_factory=list)

@dataclass 
class PyFile:
    """A Python file with its contents and relationships."""
    path: Path
    imports: List[CodeElement] = field(default_factory=list)
    elements: List[CodeElement] = field(default_factory=list)
    strings: List[CodeElement] = field(default_factory=list)
    error: Optional[str] = None
    lines: int = 0

# ─────────────────────────────────────────────────────────────────────────────
# AST Analysis
# ─────────────────────────────────────────────────────────────────────────────

def analyze_file(filepath: Path) -> PyFile:
    """Parse a Python file and extract its deep structure."""
    pyfile = PyFile(path=filepath)
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
        pyfile.lines = len(content.splitlines())
        tree = ast.parse(content)
        
        for node in ast.iter_child_nodes(tree):
            # 1. Imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        pyfile.imports.append(CodeElement(
                            name=alias.name, kind='import', line=node.lineno,
                            value=alias.asname
                        ))
                else:
                    module = node.module or ""
                    for alias in node.names:
                        pyfile.imports.append(CodeElement(
                            name=f"{module}.{alias.name}", kind='import', line=node.lineno,
                            value=alias.asname
                        ))

            # 2. Classes
            elif isinstance(node, ast.ClassDef):
                cls = CodeElement(name=node.name, kind='class', line=node.lineno, 
                                end_line=getattr(node, 'end_lineno', node.lineno))
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        cls.children.append(CodeElement(
                            name=item.name, kind='method', line=item.lineno,
                            end_line=getattr(item, 'end_lineno', item.lineno)
                        ))
                pyfile.elements.append(cls)
            
            # 3. Functions
            elif isinstance(node, ast.FunctionDef):
                pyfile.elements.append(CodeElement(
                    name=node.name, kind='function', line=node.lineno,
                    end_line=getattr(node, 'end_lineno', node.lineno)
                ))

            # 4. Global Variables
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        pyfile.elements.append(CodeElement(
                            name=target.id, kind='variable', line=node.lineno
                        ))

        # 5. Extract suspicious strings (IPs/URLs)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value
                if len(val) > 3 and (re.search(r'\d{1,3}\.\d{1,3}', val) or "http" in val or "/" in val):
                    pyfile.strings.append(CodeElement(
                        name=val[:100], kind='string', line=node.lineno
                    ))

    except Exception as e:
        pyfile.error = str(e)
        logging.error(f"Failed to analyze {filepath}: {e}")

    return pyfile

    

def scan_directory(root: Path, max_depth: int = 10) -> Dict[Path, PyFile]:
    files = {}
    root = root.resolve()
    skip = {'.git', '__pycache__', 'venv', 'node_modules'}
    
    for pypath in root.rglob('*.py'):
        if any(part in skip or part.startswith('.') for part in pypath.parts): continue
        if len(pypath.relative_to(root).parts) > max_depth: continue
        files[pypath] = analyze_file(pypath)
    return files

# ─────────────────────────────────────────────────────────────────────────────
# Terminal Visualization
# ─────────────────────────────────────────────────────────────────────────────

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIR = "\033[94m"
    FILE = "\033[97m"
    CLASS = "\033[93m"
    FUNC = "\033[96m"
    VAR = "\033[92m"
    STR = "\033[33m"
    ERROR = "\033[91m"

def print_tree(root: Path, files: Dict[Path, PyFile]):
    print(f"\n{C.BOLD}{C.DIR}● {root.name}/{C.RESET}")
    for path, pf in sorted(files.items()):
        rel = path.relative_to(root)
        print(f"  └── {C.FILE}{rel}{C.RESET} ({pf.lines}L)")
        for el in pf.elements:
            color = C.CLASS if el.kind == 'class' else (C.FUNC if el.kind == 'function' else C.VAR)
            print(f"      ├── [{el.kind[0].upper()}] {color}{el.name}{C.RESET}")
        for s in pf.strings[:3]: # Limit terminal strings
            print(f"      │   {C.STR}\"{s.name[:30]}...\"{C.RESET}")

# ─────────────────────────────────────────────────────────────────────────────
# HTML Export
# ─────────────────────────────────────────────────────────────────────────────

def export_html(root: Path, files: Dict[Path, PyFile], output: Path):
    # Standard HTML export logic from original version...
    data = {"name": root.name, "files": []}
    for path, pf in files.items():
        data["files"].append({
            "name": str(path.relative_to(root)),
            "elements": [{"name": e.name, "kind": e.kind} for e in pf.elements],
            "strings": [s.name for s in pf.strings]
        })
    output.write_text(f"<html><body><pre>{json.dumps(data, indent=2)}</pre></body></html>")
    print(f"Exported to {output}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="PyView Enhanced")
    parser.add_argument('path', nargs='?', default='.', help='Directory to scan')
    parser.add_argument('--html', metavar='FILE', help='Export to HTML')
    args = parser.parse_args()
    
    root = Path(args.path).resolve()
    files = scan_directory(root)
    if args.html: export_html(root, files, Path(args.html))
    else: print_tree(root, files)

if __name__ == "__main__":
    main()
