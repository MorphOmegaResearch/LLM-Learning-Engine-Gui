#!/usr/bin/env python3
"""
Directory structure blueprint generator for Big Bug Hunt.
Generates full directory tree with file counts, sizes, types, and relationship density.
Enhanced with ASCII tree visualization, target highlighting, and interactive summary.
Phase: Context Surfacing & Intelligence

# 📋 FLOW INDEX
#   [SEQ:1] Detect project root + init tracker
#   [SEQ:2] Scan directory structure (stats)
#   [SEQ:3] Generate ASCII tree + summaries
#   [SEQ:4] Write latest + marker files

# 🔗 LINK MARKERS
#   [LINK:TRACKER] link_tracker.py (index + metrics)
#   [LINK:BLUEPRINT_DIR] .bug_links/blueprints/
#   [LINK:UTIL] scripts/debug_utils.py (debug notify)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import ast
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
from scripts import debug_utils

def _dbg(stage: str, project: Path, details: dict) -> None:
    meta = {"tool": "generate_blueprint", "stage": stage, "change_type": stage.lower()}
    meta.update(details or {})
    debug_utils.debug_notify(project, "Generate Blueprint", stage, "\n".join([f"{k}: {v}" for k,v in meta.items()]), meta)

from link_tracker import detect_project_root, ProjectLinkTracker, SKIP_DIRS, SKIP_EXTENSIONS


class BlueprintGenerator:
    """Generates comprehensive directory structure blueprints."""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root).resolve()
        self.blueprint_dir = self.project_root / ".bug_links" / "blueprints"
        self.blueprint_dir.mkdir(parents=True, exist_ok=True)
        self.marker_file = self.project_root / ".bug_links" / ".blueprint_ready"
        
        # Initialize link tracker for deep context
        self.tracker = ProjectLinkTracker(self.project_root)
        try:
            self.tracker_data = self.tracker.ensure_index()
        except Exception:
            self.tracker_data = {}
        
    def scan_directory_structure(self) -> Dict:
        """Scan directory structure and collect statistics."""
        _dbg("ScanStart", self.project_root, {"file": str(self.project_root)})
        file_stats = defaultdict(lambda: {"count": 0, "total_size": 0, "files": []})
        dir_stats = defaultdict(lambda: {"files": 0, "subdirs": 0, "total_size": 0})
        
        files_data = self.tracker_data.get("files", {})
        file_metrics = {f["relative_path"]: f for f in files_data.values()}
        
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS]
            
            rel_root = Path(root).relative_to(self.project_root)
            if str(rel_root) == ".":
                rel_root_str = ""
            else:
                rel_root_str = str(rel_root)
            
            for file in files:
                if any(file.endswith(ext) for ext in SKIP_EXTENSIONS):
                    continue
                
                file_path = Path(root) / file
                try:
                    file_size = file_path.stat().st_size
                    ext = file_path.suffix or "(no extension)"
                    
                    file_stats[ext]["count"] += 1
                    file_stats[ext]["total_size"] += file_size
                    file_stats[ext]["files"].append({
                        "path": str(Path(rel_root_str) / file) if rel_root_str else file,
                        "size": file_size
                    })
                    
                    dir_stats[rel_root_str]["files"] += 1
                    dir_stats[rel_root_str]["total_size"] += file_size
                    
                    rel_path = str(Path(rel_root_str) / file) if rel_root_str else file
                    if rel_path in file_metrics:
                        metrics = file_metrics[rel_path]
                        if "relationships" not in dir_stats[rel_root_str]:
                            dir_stats[rel_root_str]["relationships"] = 0
                        dir_stats[rel_root_str]["relationships"] += metrics.get("relationships", 0)
                        
                except (OSError, PermissionError):
                    pass
            
            dir_stats[rel_root_str]["subdirs"] = len(dirs)
        
        stats = {
            "file_stats": dict(file_stats),
            "dir_stats": dict(dir_stats),
            "file_metrics": {k: {
                "relationships": v.get("relationships", 0),
                "connectors": len(v.get("connectors", [])),
                "size": v.get("size", 0),
                "lines": v.get("lines", 0)
            } for k, v in file_metrics.items()}
        }
        _dbg("ScanComplete", self.project_root, {"files": sum(s["count"] for s in stats["file_stats"].values())})
        return stats
    
    def generate_ascii_tree(self, target_file: Optional[str] = None) -> List[str]:
        """Generate ASCII tree representation with metrics."""
        tree_lines = []
        files_data = self.tracker_data.get("files", {})
        file_metrics = {f["relative_path"]: f for f in files_data.values()}

        def walk_tree(directory, prefix=""):
            try:
                entries = sorted(list(directory.iterdir()), key=lambda e: (e.is_file(), e.name.lower()))
            except PermissionError:
                return

            entries = [e for e in entries if not e.name.startswith('.') and e.name not in SKIP_DIRS]
            
            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                
                try:
                    rel_path = str(entry.relative_to(self.project_root))
                except ValueError:
                    rel_path = entry.name
                
                metrics = file_metrics.get(rel_path, {})
                rels = metrics.get("relationships", 0)
                conns = len(metrics.get("connectors", []))
                
                name_str = entry.name
                if entry.is_dir():
                    name_str += "/"
                
                info = ""
                if rels > 0 or conns > 0:
                    info = f" [R:{rels} C:{conns}]"
                
                marker = ""
                if target_file and rel_path == target_file:
                    marker = " <=== TARGET"
                    name_str = f"**{name_str}**"
                
                tree_lines.append(f"{prefix}{connector}{name_str}{info}{marker}")
                
                if entry.is_dir():
                    extension = "    " if is_last else "│   "
                    walk_tree(entry, prefix + extension)

        tree_lines.append(f"{self.project_root.name}/")
        walk_tree(self.project_root)
        return tree_lines

    def analyze_file_context(self, file_path: Path) -> Dict[str, Any]:
        """
        Deep analysis of a specific file to extract logical summary and relationships.
        Leverages link_tracker data for precision.
        """
        context = {
            "name": file_path.name,
            "path": str(file_path.relative_to(self.project_root)),
            "summary": "No summary available",
            "relatives": [],
            "incoming": [],
            "bug_count": 0,
            "todo_count": 0
        }
        
        # 1. Fetch Link Tracker Data
        metrics = self.tracker.get_file_metrics(file_path, self.tracker_data)
        if metrics:
            # Extract outgoing connections (imports)
            connectors = metrics.get("connectors", [])
            context["relatives"] = [c.get("file", c.get("module")) for c in connectors if c.get("file")]
            
            # Extract incoming connections (called by)
            context["incoming"] = metrics.get("called_by", [])
            
            # Extract Todos
            context["todo_count"] = metrics.get("todo_count", 0)
            
            # Extract Bugs from Tooling Data
            tooling = metrics.get("tooling", {})
            context["bug_count"] = tooling.get("bugs", {}).get("total", 0)

        # 2. AST Analysis for Job Summary (Docstring)
        if file_path.suffix == '.py':
            try:
                content = file_path.read_text(errors='ignore')
                tree = ast.parse(content)
                docstring = ast.get_docstring(tree)
                if docstring:
                    # Get first non-empty line
                    summary_lines = [line.strip() for line in docstring.split('\n') if line.strip()]
                    if summary_lines:
                        context["summary"] = summary_lines[0]
            except Exception:
                pass
                
        # 3. Sibling Analysis (Local Context)
        try:
            siblings = [p.name for p in file_path.parent.iterdir() if p.is_file() and p.name != file_path.name]
            context["siblings"] = siblings[:5]
        except:
            context["siblings"] = []
            
        return context

    def get_folder_job_summary(self, folder_path: Path) -> str:
        """
        Synthesize a job summary for a folder by checking README or aggregating children.
        """
        # Check for README
        readme = folder_path / "README.md"
        if readme.exists():
            try:
                content = readme.read_text().split('\n')
                for line in content:
                    if line.strip() and not line.startswith('#'):
                        return f"From README: {line.strip()[:100]}..."
            except: pass
            
        # Aggregate from children docstrings
        py_files = list(folder_path.glob("*.py"))
        summaries = []
        for py in py_files[:3]: # Check top 3
            try:
                doc = ast.get_docstring(ast.parse(py.read_text(errors='ignore')))
                if doc:
                    summary = doc.split('\n')[0].strip()
                    summaries.append(f"{py.name}: {summary}")
            except: pass
            
        if summaries:
            return " | ".join(summaries)
            
        return "Generic Container"

    def generate_report_text(self, stats: Dict, target_file: Optional[str] = None) -> str:
        """Generate full text report including tree."""
        lines = []
        lines.append("=" * 60)
        lines.append("PROJECT BLUEPRINT")
        lines.append("=" * 60)
        lines.append(f"Project: {self.project_root}")
        lines.append(f"Generated: {datetime.now().isoformat()}")
        
        if target_file:
            target_path = self.project_root / target_file
            context = self.analyze_file_context(target_path)
            lines.append("-" * 60)
            lines.append(f"🎯 TARGET FOCUS: {target_file}")
            lines.append(f"📝 Job Summary: {context['summary']}")
            lines.append(f"🐞 Bugs: {context['bug_count']} | ✅ Todos: {context['todo_count']}")
            lines.append(f"🔗 Incoming (Called By): {len(context['incoming'])}")
            if context['incoming']:
                lines.append(f"   - {', '.join(context['incoming'][:3])}...")
            lines.append(f"📤 Outgoing (Imports): {len(context['relatives'])}")
            if context['relatives']:
                lines.append(f"   - {', '.join(context['relatives'][:3])}...")
            lines.append("-" * 60)
            
        lines.append("")
        lines.append("DIRECTORY TREE:")
        lines.append("")
        lines.extend(self.generate_ascii_tree(target_file))
        lines.append("")
        
        lines.append("FILE STATISTICS:")
        file_stats = stats["file_stats"]
        total_files = sum(s["count"] for s in file_stats.values())
        total_size = sum(s["total_size"] for s in file_stats.values())
        
        lines.append(f"Total Files: {total_files}")
        lines.append(f"Total Size: {total_size / (1024 * 1024):.1f} MB")
        lines.append("")
        
        sorted_types = sorted(file_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        for ext, stat in sorted_types[:10]:
            count = stat["count"]
            size = stat["total_size"]
            size_str = f"{size / 1024:.1f} KB"
            lines.append(f"  {ext:15s}: {count:4d} files ({size_str})")
            
        return "\n".join(lines)
    
    def generate(self, output_format: str = "both", target_file: Optional[str] = None) -> Tuple[Optional[Path], Optional[Path]]:
        """Generate blueprint files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        stats = self.scan_directory_structure()
        
        text_file = None
        json_file = None
        
        if output_format in ("text", "both"):
            text_content = self.generate_report_text(stats, target_file)
            text_file = self.blueprint_dir / f"blueprint_{timestamp}.txt"
            text_file.write_text(text_content)
            
            # Update latest and marker
            latest = (self.blueprint_dir / "latest.txt")
            latest.write_text(text_content)
            self.marker_file.touch()
            _dbg("TextWritten", self.project_root, {"file": str(latest)})
        
        if output_format in ("json", "both"):
            json_content = self.generate_json(stats)
            json_file = self.blueprint_dir / f"blueprint_{timestamp}.json"
            json_file.write_text(json.dumps(json_content, indent=2))
            _dbg("JsonWritten", self.project_root, {"file": str(json_file)})
        
        return text_file, json_file

    def generate_json(self, stats: Dict) -> Dict:
        """Generate JSON metadata."""
        return {
            "project_root": str(self.project_root),
            "timestamp": datetime.now().isoformat(),
            "file_statistics": stats["file_stats"],
            "directory_statistics": stats["dir_stats"],
            "file_metrics": stats["file_metrics"]
        }

    def view_latest(self):
        """View the latest blueprint."""
        latest = self.blueprint_dir / "latest.txt"
        if latest.exists():
            subprocess.run(["less", "-R", str(latest)])
        else:
            print("No existing blueprint found.")

    def show_summary(self, stats: Dict, target_rel: Optional[str] = None):
        """Show high-level summary in terminal."""
        print(f"\n📊 PROJECT SUMMARY: {self.project_root.name}")
        file_stats = stats["file_stats"]
        total_files = sum(s["count"] for s in file_stats.values())
        print(f"   Files: {total_files} | Dirs: {len(stats['dir_stats'])}")
        
        if target_rel:
            target_path = self.project_root / target_rel
            if target_path.exists():
                if target_path.is_file():
                    context = self.analyze_file_context(target_path)
                    print(f"\n🎯 FILE FOCUS: {target_rel}")
                    print(f"   Job: {context['summary']}")
                    print(f"   Context: {len(context['incoming'])} callers, {len(context['relatives'])} imports")
                    print(f"   Status: {context['bug_count']} Bugs, {context['todo_count']} Todos")
                elif target_path.is_dir():
                    summary = self.get_folder_job_summary(target_path)
                    print(f"\n📂 FOLDER FOCUS: {target_rel}")
                    print(f"   Job: {summary}")
                    # Count children
                    children = list(target_path.iterdir())
                    print(f"   Contains: {len(children)} items")

def main():
    parser = argparse.ArgumentParser(description="Generate directory structure blueprint")
    parser.add_argument("path", nargs="?", default=".", help="Project root or target file")
    parser.add_argument("--format", choices=["text", "json", "both"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--view", action="store_true", help="View latest blueprint without regenerating")
    parser.add_argument("--target-file", help="Specific file to highlight (relative path)")
    parser.add_argument("--no-interactive", action="store_true", help="Skip interactive prompt")
    
    args = parser.parse_args()
    
    path_obj = Path(args.path).resolve()
    
    # Determine project root and target file
    if path_obj.is_file():
        # If run on a file, it's the target
        try:
            project_root = detect_project_root(path_obj)
        except:
            project_root = path_obj.parent
        try:
            target_rel = str(path_obj.relative_to(project_root))
        except ValueError:
            target_rel = path_obj.name
            
    else:
        # If run on directory
        project_root = path_obj
        # But wait, Thunar passes %f which is the SELECTED item.
        # If selected item is a SUBDIR, we want that as the focus target?
        # Detect project root by walking up
        try:
            actual_root = detect_project_root(path_obj)
            if actual_root != path_obj:
                # Selected is a subdir of project
                project_root = actual_root
                target_rel = str(path_obj.relative_to(project_root))
            else:
                target_rel = None
        except:
            target_rel = None

    generator = BlueprintGenerator(project_root)
    
    if args.view:
        generator.view_latest()
        return

    # Generate stats first for summary
    stats = generator.scan_directory_structure()
    generator.show_summary(stats, target_rel)
    
    # Interactive prompt
    if not args.no_interactive:
        try:
            choice = input("\nShow full blueprint? [y/N]: ").strip().lower()
            if choice == 'y':
                # Generate and show
                text_file, _ = generator.generate(args.format, target_file=target_rel)
                if text_file:
                    subprocess.run(["less", "-R", str(text_file)])
            else:
                # Just generate in background
                print("Generating blueprint in background...")
                generator.generate(args.format, target_file=target_rel)
                print(f"Blueprint saved to {generator.blueprint_dir}")
        except KeyboardInterrupt:
            print("\nCancelled.")
    else:
        text_file, _ = generator.generate(args.format, target_file=target_rel)
        if text_file:
            print(f"Blueprint generated: {text_file}")

if __name__ == "__main__":
    main()
