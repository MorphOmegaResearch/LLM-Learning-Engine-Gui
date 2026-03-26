#!/usr/bin/env python3
"""
PyView - Simple Python Project Visualizer
Point at a folder, see your structure..

Usage:
    python pyview.py                    # Current directory
    python pyview.py /path/to/project   # Specific directory
    python pyview.py -d 3               # Limit depth to 3
    python pyview.py --html output.html # Export visual HTML
"""

import ast
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CodeElement:
    """A class, function, or variable in a file."""
    name: str
    kind: str  # 'class', 'function', 'method'
    line: int
    children: List['CodeElement'] = field(default_factory=list)


@dataclass 
class PyFile:
    """A Python file with its contents."""
    path: Path
    imports: List[str] = field(default_factory=list)
    elements: List[CodeElement] = field(default_factory=list)
    error: Optional[str] = None
    lines: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# AST Analysis (kept simple)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_file(filepath: Path) -> PyFile:
    """Parse a Python file and extract its structure."""
    pyfile = PyFile(path=filepath)
    
    try:
        content = filepath.read_text(encoding='utf-8', errors='replace')
        pyfile.lines = len(content.splitlines())
        tree = ast.parse(content)
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pyfile.imports.append(alias.name.split('.')[0])
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pyfile.imports.append(node.module.split('.')[0])
            
            elif isinstance(node, ast.ClassDef):
                cls = CodeElement(name=node.name, kind='class', line=node.lineno)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        cls.children.append(CodeElement(
                            name=item.name, kind='method', line=item.lineno
                        ))
                pyfile.elements.append(cls)
            
            elif isinstance(node, ast.FunctionDef):
                pyfile.elements.append(CodeElement(
                    name=node.name, kind='function', line=node.lineno
                ))
        
        # Dedupe imports
        pyfile.imports = list(set(pyfile.imports))
        
    except SyntaxError as e:
        pyfile.error = f"Syntax error line {e.lineno}"
    except Exception as e:
        pyfile.error = str(e)[:50]
    
    return pyfile


# ─────────────────────────────────────────────────────────────────────────────
# Directory Scanning
# ─────────────────────────────────────────────────────────────────────────────

def scan_directory(root: Path, max_depth: int = 10) -> Dict[Path, PyFile]:
    """Scan directory for Python files."""
    files = {}
    root = root.resolve()
    
    # Directories to skip
    skip = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.tox', 'eggs', '*.egg-info'}
    
    def should_skip(p: Path) -> bool:
        return any(part.startswith('.') or part in skip or part.endswith('.egg-info') 
                   for part in p.parts)
    
    for pypath in root.rglob('*.py'):
        if should_skip(pypath.relative_to(root)):
            continue
        
        # Check depth
        depth = len(pypath.relative_to(root).parts)
        if depth > max_depth:
            continue
            
        files[pypath] = analyze_file(pypath)
    
    return files


# ─────────────────────────────────────────────────────────────────────────────
# Terminal Visualization
# ─────────────────────────────────────────────────────────────────────────────

# Box drawing characters
V = "│"   # vertical
H = "─"   # horizontal  
T = "├"   # tee
L = "└"   # corner
D = "●"   # dot

# Colors (ANSI)
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    DIR = "\033[94m"      # blue
    FILE = "\033[97m"     # white
    CLASS = "\033[93m"    # yellow
    FUNC = "\033[96m"     # cyan
    METHOD = "\033[36m"   # dark cyan
    ERROR = "\033[91m"    # red
    LINES = "\033[90m"    # gray


def print_tree(root: Path, files: Dict[Path, PyFile], show_contents: bool = True):
    """Print the file tree to terminal."""
    
    root = root.resolve()
    print(f"\n{C.BOLD}{C.DIR}{D} {root.name}/{C.RESET}")
    
    # Build tree structure
    tree: Dict[Path, List[Path]] = {}  # parent -> children
    all_paths: Set[Path] = set()
    
    for filepath in sorted(files.keys()):
        rel = filepath.relative_to(root)
        all_paths.add(filepath)
        
        # Add all parent directories
        current = root
        for part in rel.parts[:-1]:
            parent = current
            current = current / part
            all_paths.add(current)
            if parent not in tree:
                tree[parent] = []
            if current not in tree[parent]:
                tree[parent].append(current)
        
        # Add file to parent
        parent = filepath.parent
        if parent not in tree:
            tree[parent] = []
        if filepath not in tree[parent]:
            tree[parent].append(filepath)
    
    def print_node(path: Path, prefix: str = "", is_last: bool = True):
        connector = L if is_last else T
        
        if path.is_dir():
            # Directory
            name = path.name
            print(f"{prefix}{connector}{H}{H} {C.DIR}{name}/{C.RESET}")
        else:
            # Python file
            pyfile = files.get(path)
            name = path.name
            
            if pyfile and pyfile.error:
                status = f" {C.ERROR}[{pyfile.error}]{C.RESET}"
            else:
                status = f" {C.LINES}({pyfile.lines}L){C.RESET}" if pyfile else ""
            
            print(f"{prefix}{connector}{H}{H} {C.FILE}{name}{C.RESET}{status}")
            
            # Show contents if enabled
            if show_contents and pyfile and not pyfile.error:
                child_prefix = prefix + ("    " if is_last else f"{V}   ")
                print_contents(pyfile, child_prefix)
        
        # Print children
        children = tree.get(path, [])
        children = sorted(children, key=lambda p: (p.is_file(), p.name.lower()))
        
        for i, child in enumerate(children):
            child_is_last = (i == len(children) - 1)
            child_prefix = prefix + ("    " if is_last else f"{V}   ")
            print_node(child, child_prefix, child_is_last)
    
    # Print from root's children
    root_children = tree.get(root, [])
    root_children = sorted(root_children, key=lambda p: (p.is_file(), p.name.lower()))
    
    for i, child in enumerate(root_children):
        is_last = (i == len(root_children) - 1)
        print_node(child, "", is_last)


def print_contents(pyfile: PyFile, prefix: str):
    """Print file contents (classes/functions)."""
    if not pyfile.elements:
        return
    
    for i, elem in enumerate(pyfile.elements):
        is_last = (i == len(pyfile.elements) - 1)
        connector = L if is_last else T
        
        if elem.kind == 'class':
            print(f"{prefix}{connector}{H} {C.CLASS}class {elem.name}{C.RESET}")
            
            # Methods
            method_prefix = prefix + ("    " if is_last else f"{V}   ")
            for j, method in enumerate(elem.children[:5]):  # Limit to 5 methods shown
                m_last = (j == len(elem.children[:5]) - 1)
                m_conn = L if m_last else T
                print(f"{method_prefix}{m_conn}{H} {C.METHOD}.{method.name}(){C.RESET}")
            
            if len(elem.children) > 5:
                print(f"{method_prefix}   {C.DIM}...+{len(elem.children)-5} more{C.RESET}")
                
        else:
            print(f"{prefix}{connector}{H} {C.FUNC}def {elem.name}(){C.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Dependency Graph
# ─────────────────────────────────────────────────────────────────────────────

def print_dependencies(root: Path, files: Dict[Path, PyFile]):
    """Show which files import what from within the project."""
    print(f"\n{C.BOLD}Dependencies (internal){C.RESET}")
    print(H * 40)
    
    # Get all module names in project
    project_modules = set()
    for filepath in files:
        rel = filepath.relative_to(root)
        module = rel.stem
        project_modules.add(module)
        # Also add parent packages
        for part in rel.parts[:-1]:
            project_modules.add(part)
    
    # Find internal imports
    found_any = False
    for filepath, pyfile in sorted(files.items()):
        internal_imports = [imp for imp in pyfile.imports if imp in project_modules]
        if internal_imports:
            found_any = True
            rel = filepath.relative_to(root)
            print(f"{C.FILE}{rel}{C.RESET}")
            for imp in internal_imports:
                print(f"  {T}{H} imports {C.FUNC}{imp}{C.RESET}")
    
    if not found_any:
        print(f"{C.DIM}No internal dependencies found{C.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# HTML Export
# ─────────────────────────────────────────────────────────────────────────────

def export_html(root: Path, files: Dict[Path, PyFile], output: Path):
    """Export an interactive HTML visualization."""
    
    root = root.resolve()
    
    # Build data structure for JS
    def build_tree_data(path: Path, files: Dict[Path, PyFile], root: Path) -> dict:
        children = []
        
        # Get all unique child directories and files
        child_paths = set()
        for filepath in files:
            try:
                rel = filepath.relative_to(path)
                first_part = rel.parts[0] if rel.parts else None
                if first_part:
                    child_paths.add(path / first_part)
            except ValueError:
                continue
        
        for child in sorted(child_paths, key=lambda p: (p.is_file(), p.name.lower())):
            if child.is_dir():
                children.append(build_tree_data(child, files, root))
            elif child in files:
                pyfile = files[child]
                file_node = {
                    "name": child.name,
                    "type": "file",
                    "lines": pyfile.lines,
                    "error": pyfile.error,
                    "elements": []
                }
                for elem in pyfile.elements:
                    elem_node = {
                        "name": elem.name,
                        "kind": elem.kind,
                        "methods": [m.name for m in elem.children] if elem.kind == 'class' else []
                    }
                    file_node["elements"].append(elem_node)
                children.append(file_node)
        
        return {
            "name": path.name,
            "type": "directory",
            "children": children
        }
    
    tree_data = build_tree_data(root, files, root)
    
    import json
    tree_json = json.dumps(tree_data, indent=2)
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>PyView - {root.name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'SF Mono', 'Consolas', monospace;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
            line-height: 1.6;
        }}
        h1 {{ 
            color: #00d9ff;
            margin-bottom: 20px;
            font-size: 1.4em;
        }}
        .tree {{ padding-left: 0; }}
        .tree ul {{ 
            padding-left: 20px;
            border-left: 1px solid #333;
            margin-left: 8px;
        }}
        .tree li {{ 
            list-style: none;
            padding: 3px 0;
        }}
        .node {{ 
            cursor: pointer;
            padding: 2px 8px;
            border-radius: 3px;
            display: inline-block;
        }}
        .node:hover {{ background: #2a2a4e; }}
        .directory {{ color: #6eb5ff; }}
        .directory::before {{ content: "📁 "; }}
        .file {{ color: #fff; }}
        .file::before {{ content: "🐍 "; }}
        .lines {{ color: #666; font-size: 0.85em; }}
        .error {{ color: #ff6b6b; }}
        .elements {{ 
            padding-left: 25px;
            border-left: 1px dashed #444;
            margin-left: 10px;
            margin-top: 4px;
        }}
        .class {{ color: #ffd93d; }}
        .class::before {{ content: "◆ "; }}
        .function {{ color: #6bcb77; }}
        .function::before {{ content: "ƒ "; }}
        .method {{ color: #4d96ff; font-size: 0.9em; }}
        .method::before {{ content: "→ "; }}
        .collapsed > ul {{ display: none; }}
        .collapsed > .elements {{ display: none; }}
        .toggle {{ 
            color: #666;
            margin-right: 5px;
            width: 12px;
            display: inline-block;
        }}
    </style>
</head>
<body>
    <h1>📊 {root.name}</h1>
    <div id="tree" class="tree"></div>
    
    <script>
    const data = {tree_json};
    
    function renderNode(node, container) {{
        const li = document.createElement('li');
        
        const toggle = document.createElement('span');
        toggle.className = 'toggle';
        
        const span = document.createElement('span');
        span.className = 'node ' + node.type;
        span.textContent = node.name;
        
        if (node.type === 'file') {{
            if (node.error) {{
                span.innerHTML += ' <span class="error">[' + node.error + ']</span>';
            }} else {{
                span.innerHTML += ' <span class="lines">(' + node.lines + 'L)</span>';
            }}
            
            // Add elements
            if (node.elements && node.elements.length > 0) {{
                toggle.textContent = '▼';
                const elements = document.createElement('div');
                elements.className = 'elements';
                
                node.elements.forEach(elem => {{
                    const elemDiv = document.createElement('div');
                    elemDiv.className = elem.kind;
                    elemDiv.textContent = (elem.kind === 'class' ? 'class ' : 'def ') + elem.name;
                    elements.appendChild(elemDiv);
                    
                    if (elem.methods && elem.methods.length > 0) {{
                        elem.methods.slice(0, 5).forEach(m => {{
                            const methodDiv = document.createElement('div');
                            methodDiv.className = 'method';
                            methodDiv.textContent = '.' + m + '()';
                            methodDiv.style.paddingLeft = '15px';
                            elements.appendChild(methodDiv);
                        }});
                        if (elem.methods.length > 5) {{
                            const more = document.createElement('div');
                            more.className = 'method';
                            more.textContent = '...+' + (elem.methods.length - 5) + ' more';
                            more.style.paddingLeft = '15px';
                            elements.appendChild(more);
                        }}
                    }}
                }});
                
                li.appendChild(elements);
                
                toggle.onclick = () => {{
                    li.classList.toggle('collapsed');
                    toggle.textContent = li.classList.contains('collapsed') ? '▶' : '▼';
                }};
            }}
        }}
        
        if (node.type === 'directory' && node.children && node.children.length > 0) {{
            toggle.textContent = '▼';
            const ul = document.createElement('ul');
            node.children.forEach(child => renderNode(child, ul));
            li.appendChild(ul);
            
            toggle.onclick = () => {{
                li.classList.toggle('collapsed');
                toggle.textContent = li.classList.contains('collapsed') ? '▶' : '▼';
            }};
        }}
        
        const header = document.createElement('div');
        header.appendChild(toggle);
        header.appendChild(span);
        li.insertBefore(header, li.firstChild);
        
        container.appendChild(li);
    }}
    
    const tree = document.getElementById('tree');
    const ul = document.createElement('ul');
    if (data.children) {{
        data.children.forEach(child => renderNode(child, ul));
    }}
    tree.appendChild(ul);
    </script>
</body>
</html>'''
    
    output.write_text(html)
    print(f"\n{C.BOLD}Exported to: {output}{C.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Summary Stats
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(files: Dict[Path, PyFile]):
    """Print quick stats."""
    total_files = len(files)
    total_lines = sum(f.lines for f in files.values())
    total_classes = sum(len([e for e in f.elements if e.kind == 'class']) for f in files.values())
    total_functions = sum(len([e for e in f.elements if e.kind == 'function']) for f in files.values())
    errors = sum(1 for f in files.values() if f.error)
    
    print(f"\n{C.BOLD}Summary{C.RESET}")
    print(H * 40)
    print(f"  Files:     {total_files}")
    print(f"  Lines:     {total_lines:,}")
    print(f"  Classes:   {total_classes}")
    print(f"  Functions: {total_functions}")
    if errors:
        print(f"  {C.ERROR}Errors:    {errors}{C.RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="PyView - Simple Python Project Visualizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pyview.py                      # View current directory
  pyview.py ~/projects/myapp     # View specific directory
  pyview.py -d 2                 # Limit depth to 2 levels
  pyview.py --no-contents        # Just show files, not internals
  pyview.py --html view.html     # Export interactive HTML
  pyview.py --deps               # Show internal dependencies
        """
    )
    
    parser.add_argument('path', nargs='?', default='.', help='Directory to scan')
    parser.add_argument('-d', '--depth', type=int, default=10, help='Max depth (default: 10)')
    parser.add_argument('--no-contents', action='store_true', help="Don't show classes/functions")
    parser.add_argument('--html', metavar='FILE', help='Export to HTML file')
    parser.add_argument('--deps', action='store_true', help='Show internal dependencies')
    parser.add_argument('--summary', action='store_true', help='Show summary only')
    
    args = parser.parse_args()
    
    root = Path(args.path).resolve()
    
    if not root.exists():
        print(f"{C.ERROR}Error: Path does not exist: {root}{C.RESET}")
        sys.exit(1)
    
    if not root.is_dir():
        print(f"{C.ERROR}Error: Not a directory: {root}{C.RESET}")
        sys.exit(1)
    
    # Scan
    files = scan_directory(root, args.depth)
    
    if not files:
        print(f"{C.DIM}No Python files found in {root}{C.RESET}")
        sys.exit(0)
    
    # Output
    if args.summary:
        print_summary(files)
    elif args.html:
        export_html(root, files, Path(args.html))
        print_summary(files)
    else:
        print_tree(root, files, show_contents=not args.no_contents)
        
        if args.deps:
            print_dependencies(root, files)
        
        print_summary(files)


if __name__ == '__main__':
    main()
