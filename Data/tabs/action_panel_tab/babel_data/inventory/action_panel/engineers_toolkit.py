#!/usr/bin/env python3
"""
Engineer's Toolkit GUI - A Tkinter-based interface for development workflows
Integrates CLI tools, quality checks, and project management with right-click support
"""

import os
import sys
import json
import subprocess
import threading
import tempfile
import shutil
import hashlib
import difflib
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import tkinter.font as tkfont

# Try to import optional tools with fallbacks
TOOLS_AVAILABLE = {}

try:
    import black

    TOOLS_AVAILABLE["black"] = black
except ImportError:
    TOOLS_AVAILABLE["black"] = None

try:
    import ruff

    TOOLS_AVAILABLE["ruff"] = ruff
except ImportError:
    TOOLS_AVAILABLE["ruff"] = None

try:
    import pyflakes.api

    TOOLS_AVAILABLE["pyflakes"] = pyflakes
except ImportError:
    TOOLS_AVAILABLE["pyflakes"] = None

try:
    import py_compile

    TOOLS_AVAILABLE["py_compile"] = py_compile
except ImportError:
    TOOLS_AVAILABLE["py_compile"] = None

# ============================================================================
# CORE ENGINEERING TOOLKIT
# ============================================================================


class ProjectSnapshot:
    """Manages project state snapshots and comparisons"""

    def __init__(self, project_path: Path):
        self.project_path = Path(project_path)
        self.snapshot_dir = self.project_path / ".engineer_snapshots"
        self.snapshot_dir.mkdir(exist_ok=True)

        # State files
        self.state_file = self.snapshot_dir / "project_variables.json"
        self.imports_file = self.snapshot_dir / "imports_analysis.json"
        self.structure_file = self.snapshot_dir / "file_structure.json"

    def create_snapshot(self, description: str = "") -> Dict:
        """Create a comprehensive project snapshot"""
        snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self.snapshot_dir / snapshot_id
        snapshot_dir.mkdir(exist_ok=True)

        snapshot_data = {
            "timestamp": datetime.now().isoformat(),
            "description": description,
            "project_path": str(self.project_path),
            "snapshot_id": snapshot_id,
            "files": self._scan_files(),
            "imports": self._analyze_imports(),
            "git_info": self._get_git_info(),
            "dependencies": self._scan_dependencies(),
            "checksums": self._calculate_checksums(),
            "metadata": self._gather_metadata(),
        }

        # Save snapshot
        snapshot_file = snapshot_dir / "snapshot.json"
        with open(snapshot_file, "w") as f:
            json.dump(snapshot_data, f, indent=2)

        # Update latest state
        with open(self.state_file, "w") as f:
            json.dump(
                {
                    "latest_snapshot": snapshot_id,
                    "snapshot_count": len(
                        list(self.snapshot_dir.glob("*/snapshot.json"))
                    ),
                    "last_updated": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

        return snapshot_data

    def compare_snapshots(self, snapshot1_id: str, snapshot2_id: str) -> Dict:
        """Compare two snapshots and return differences"""
        snapshot1_file = self.snapshot_dir / snapshot1_id / "snapshot.json"
        snapshot2_file = self.snapshot_dir / snapshot2_id / "snapshot.json"

        if not snapshot1_file.exists() or not snapshot2_file.exists():
            return {"error": "One or both snapshots not found"}

        with open(snapshot1_file, "r") as f:
            snap1 = json.load(f)
        with open(snapshot2_file, "r") as f:
            snap2 = json.load(f)

        differences = {
            "added_files": [],
            "removed_files": [],
            "modified_files": [],
            "import_changes": [],
            "dependency_changes": [],
            "timestamp_diff": None,
        }

        # Compare files
        files1 = set(snap1["files"])
        files2 = set(snap2["files"])

        differences["added_files"] = list(files2 - files1)
        differences["removed_files"] = list(files1 - files2)

        # Check for modifications in common files
        common_files = files1 & files2
        for file in common_files:
            if snap1["checksums"].get(file) != snap2["checksums"].get(file):
                differences["modified_files"].append(file)

        # Compare imports
        imports1 = snap1["imports"]
        imports2 = snap2["imports"]

        for file in set(imports1.keys()) | set(imports2.keys()):
            imports1_file = set(imports1.get(file, []))
            imports2_file = set(imports2.get(file, []))

            if imports1_file != imports2_file:
                differences["import_changes"].append(
                    {
                        "file": file,
                        "added": list(imports2_file - imports1_file),
                        "removed": list(imports1_file - imports2_file),
                    }
                )

        return differences

    def _scan_files(self) -> List[str]:
        """Scan all Python files in project"""
        python_files = []
        for ext in ["*.py", "*.pyw", "*.pyi"]:
            python_files.extend(
                [
                    str(p.relative_to(self.project_path))
                    for p in self.project_path.rglob(ext)
                ]
            )
        return sorted(python_files)

    def _analyze_imports(self) -> Dict[str, List[str]]:
        """Analyze imports in Python files"""
        import re

        import_pattern = re.compile(r"^\s*(?:import|from)\s+(\S+)", re.MULTILINE)

        imports = {}
        for py_file in self.project_path.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                file_imports = []
                for match in import_pattern.finditer(content):
                    import_stmt = match.group(1)
                    # Clean up the import statement
                    import_stmt = import_stmt.split(" ")[0].split(".")[0]
                    if import_stmt not in file_imports:
                        file_imports.append(import_stmt)

                relative_path = str(py_file.relative_to(self.project_path))
                imports[relative_path] = file_imports
            except Exception as e:
                continue

        return imports

    def _get_git_info(self) -> Dict:
        """Get Git repository information if available"""
        git_info = {"available": False}
        git_dir = self.project_path / ".git"

        if git_dir.exists():
            try:
                # Get current branch
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    git_info["branch"] = result.stdout.strip()
                    git_info["available"] = True

                # Get latest commit
                result = subprocess.run(
                    ["git", "log", "-1", "--oneline"],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    git_info["latest_commit"] = result.stdout.strip()
            except Exception:
                pass

        return git_info

    def _scan_dependencies(self) -> Dict:
        """Scan for dependency files"""
        deps = {
            "requirements_txt": [],
            "pyproject_toml": False,
            "setup_py": False,
            "pipfile": False,
        }

        # Check for requirements.txt
        req_files = list(self.project_path.glob("requirements*.txt"))
        for req_file in req_files:
            try:
                with open(req_file, "r") as f:
                    deps["requirements_txt"].append(
                        {
                            "file": req_file.name,
                            "dependencies": [
                                line.strip()
                                for line in f
                                if line.strip() and not line.startswith("#")
                            ],
                        }
                    )
            except:
                pass

        # Check for other dependency files
        deps["pyproject_toml"] = (self.project_path / "pyproject.toml").exists()
        deps["setup_py"] = (self.project_path / "setup.py").exists()
        deps["pipfile"] = (self.project_path / "Pipfile").exists()

        return deps

    def _calculate_checksums(self) -> Dict[str, str]:
        """Calculate SHA256 checksums for Python files"""
        checksums = {}
        for py_file in self.project_path.rglob("*.py"):
            try:
                with open(py_file, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                relative_path = str(py_file.relative_to(self.project_path))
                checksums[relative_path] = file_hash
            except Exception:
                pass

        return checksums

    def _gather_metadata(self) -> Dict:
        """Gather project metadata"""
        return {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "total_python_files": len(list(self.project_path.rglob("*.py"))),
            "project_size_mb": sum(
                f.stat().st_size for f in self.project_path.rglob("*") if f.is_file()
            )
            / 1024
            / 1024,
            "last_modified": datetime.fromtimestamp(
                self.project_path.stat().st_mtime
            ).isoformat(),
        }


class QualityChecker:
    """Comprehensive quality checking with multiple tools"""

    def __init__(self):
        self.tools = TOOLS_AVAILABLE
        self.check_results = {}

    def check_syntax(self, filepath: Path) -> Dict:
        """Check Python syntax"""
        result = {"passed": False, "errors": [], "tool": "py_compile"}

        if self.tools.get("py_compile"):
            try:
                self.tools["py_compile"].compile(str(filepath), doraise=True)
                result["passed"] = True
                result["message"] = "Syntax check passed"
            except self.tools["py_compile"].PyCompileError as e:
                result["errors"].append(str(e))
                result["message"] = f"Syntax error: {e}"
            except Exception as e:
                result["errors"].append(str(e))
                result["message"] = f"Error checking syntax: {e}"
        else:
            # Fallback to python -m py_compile
            try:
                subprocess.run(
                    [sys.executable, "-m", "py_compile", str(filepath)],
                    check=True,
                    capture_output=True,
                )
                result["passed"] = True
                result["message"] = "Syntax check passed"
            except subprocess.CalledProcessError as e:
                result["errors"].append(e.stderr.decode())
                result["message"] = f"Syntax check failed: {e.stderr.decode()[:100]}"

        return result

    def check_indentation(self, filepath: Path) -> Dict:
        """Check indentation consistency"""
        result = {"passed": True, "issues": [], "tool": "indentation"}

        try:
            with open(filepath, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                stripped = line.rstrip("\n")
                if stripped and stripped[-1].isspace():
                    result["issues"].append(f"Line {i}: Trailing whitespace")

                # Check for mixed tabs and spaces
                if "\t" in line and " " in line[: len(line) - len(line.lstrip())]:
                    result["issues"].append(
                        f"Line {i}: Mixed tabs and spaces in indentation"
                    )

                # Check indentation level (should be multiple of 4 for Python)
                leading = len(line) - len(line.lstrip())
                if leading % 4 != 0 and leading > 0:
                    result["issues"].append(
                        f"Line {i}: Indentation not multiple of 4 spaces"
                    )

            if result["issues"]:
                result["passed"] = False
                result["message"] = f"Found {len(result['issues'])} indentation issues"
            else:
                result["message"] = "Indentation check passed"

        except Exception as e:
            result["passed"] = False
            result["issues"].append(f"Error checking indentation: {e}")
            result["message"] = f"Error: {e}"

        return result

    def check_imports(self, filepath: Path) -> Dict:
        """Check import statements"""
        result = {"passed": True, "issues": [], "imports": [], "tool": "imports"}

        try:
            with open(filepath, "r") as f:
                content = f.read()

            # Simple import detection
            import re

            import_lines = []

            # Find import statements
            import_matches = re.finditer(
                r"^\s*(import|from)\s+(\S+)", content, re.MULTILINE
            )
            for match in import_matches:
                import_type = match.group(1)
                import_name = match.group(2)
                import_lines.append(f"{import_type} {import_name}")
                result["imports"].append(import_name.split()[0])

            # Check for duplicate imports
            import_counts = {}
            for imp in result["imports"]:
                import_counts[imp] = import_counts.get(imp, 0) + 1

            for imp, count in import_counts.items():
                if count > 1:
                    result["issues"].append(f"Duplicate import: {imp}")

            # Check for wildcard imports
            wildcard_imports = re.findall(
                r"^\s*from\s+\S+\s+import\s+\*", content, re.MULTILINE
            )
            for wildcard in wildcard_imports:
                result["issues"].append(f"Wildcard import: {wildcard.strip()}")

            if result["issues"]:
                result["passed"] = False
                result["message"] = f"Found {len(result['issues'])} import issues"
            else:
                result["message"] = f"Found {len(result['imports'])} imports, all OK"

        except Exception as e:
            result["passed"] = False
            result["issues"].append(f"Error checking imports: {e}")
            result["message"] = f"Error: {e}"

        return result

    def check_formatting(self, filepath: Path) -> Dict:
        """Check code formatting with black"""
        result = {"passed": False, "diff": "", "tool": "black"}

        if self.tools.get("black"):
            try:
                with open(filepath, "r") as f:
                    original = f.read()

                # Check formatting
                mode = self.tools["black"].Mode()
                try:
                    self.tools["black"].format_file_contents(
                        original, fast=False, mode=mode
                    )
                    result["passed"] = True
                    result["message"] = "Formatting check passed"
                except self.tools["black"].NothingChanged:
                    result["passed"] = True
                    result["message"] = "Formatting check passed"
                except Exception:
                    # Get diff
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        mode="w", suffix=".py", delete=False
                    ) as tmp:
                        tmp.write(original)
                        tmp.flush()

                        diff_result = subprocess.run(
                            ["black", "--diff", tmp.name],
                            capture_output=True,
                            text=True,
                        )
                        os.unlink(tmp.name)

                        result["diff"] = diff_result.stdout
                        result["message"] = "Formatting issues found"

            except Exception as e:
                result["message"] = f"Error checking formatting: {e}"
        else:
            result["message"] = "Black not available"

        return result

    def check_linting(self, filepath: Path) -> Dict:
        """Check linting with ruff/pyflakes"""
        result = {"passed": True, "issues": [], "tool": "ruff/pyflakes"}

        # Try ruff first
        if self.tools.get("ruff"):
            try:
                lint_result = subprocess.run(
                    ["ruff", "check", "--output-format", "text", str(filepath)],
                    capture_output=True,
                    text=True,
                )

                if lint_result.stdout:
                    result["issues"].extend(lint_result.stdout.strip().split("\n"))

            except Exception as e:
                result["issues"].append(f"Ruff error: {e}")

        # Fallback to pyflakes
        elif self.tools.get("pyflakes"):
            try:
                from io import StringIO

                with open(filepath, "r") as f:
                    content = f.read()

                stream = StringIO()
                reporter = self.tools["pyflakes"].reporter.Reporter(stream, stream)
                warnings = self.tools["pyflakes"].api.check(
                    content, str(filepath), reporter
                )
                output = stream.getvalue()

                if output:
                    result["issues"].extend(output.strip().split("\n"))

            except Exception as e:
                result["issues"].append(f"Pyflakes error: {e}")

        # If no linter available, skip
        else:
            result["message"] = "No linter available (ruff/pyflakes)"
            return result

        if result["issues"]:
            result["passed"] = False
            result["message"] = f"Found {len(result['issues'])} linting issues"
        else:
            result["message"] = "Linting check passed"

        return result

    def check_call_changes(self, filepath: Path, previous_file: Path = None) -> Dict:
        """Check for function/method call changes"""
        result = {
            "passed": True,
            "changes": [],
            "new_calls": [],
            "removed_calls": [],
            "tool": "call_analysis",
        }

        if not previous_file or not previous_file.exists():
            result["message"] = "No previous version for comparison"
            return result

        try:
            with open(filepath, "r") as f:
                current_content = f.read()
            with open(previous_file, "r") as f:
                previous_content = f.read()

            # Simple call detection (function calls with parentheses)
            import re

            call_pattern = re.compile(r"(\w+)\s*\([^)]*\)")

            current_calls = set(call_pattern.findall(current_content))
            previous_calls = set(call_pattern.findall(previous_content))

            result["new_calls"] = list(current_calls - previous_calls)
            result["removed_calls"] = list(previous_calls - current_calls)

            if result["new_calls"] or result["removed_calls"]:
                result["passed"] = False
                result["changes"] = [
                    f"New calls: {', '.join(result['new_calls'])}",
                    f"Removed calls: {', '.join(result['removed_calls'])}",
                ]
                result["message"] = (
                    f"Found {len(result['new_calls'])} new and {len(result['removed_calls'])} removed calls"
                )
            else:
                result["message"] = "No call changes detected"

        except Exception as e:
            result["passed"] = False
            result["message"] = f"Error analyzing calls: {e}"

        return result

    def run_all_checks(self, filepath: Path, previous_file: Path = None) -> Dict:
        """Run all available checks on a file"""
        filepath = Path(filepath)
        results = {
            "file": str(filepath),
            "timestamp": datetime.now().isoformat(),
            "checks": {},
        }

        # Run individual checks
        results["checks"]["syntax"] = self.check_syntax(filepath)
        results["checks"]["indentation"] = self.check_indentation(filepath)
        results["checks"]["imports"] = self.check_imports(filepath)
        results["checks"]["formatting"] = self.check_formatting(filepath)
        results["checks"]["linting"] = self.check_linting(filepath)

        if previous_file:
            results["checks"]["call_changes"] = self.check_call_changes(
                filepath, previous_file
            )

        # Calculate overall status
        all_passed = all(
            check["passed"]
            for check in results["checks"].values()
            if "passed" in check and check.get("tool") != "call_analysis"
        )

        results["overall_passed"] = all_passed
        results["summary"] = {
            "total_checks": len(results["checks"]),
            "passed_checks": sum(
                1 for check in results["checks"].values() if check.get("passed", False)
            ),
            "failed_checks": sum(
                1
                for check in results["checks"].values()
                if not check.get("passed", True)
            ),
        }

        return results


class FileBrowser:
    """Embedded file browser component"""

    def __init__(self, parent, on_file_select=None):
        self.parent = parent
        self.on_file_select = on_file_select
        self.current_path = Path.home()

        # Create widgets
        self.tree = ttk.Treeview(parent, show="tree")
        self.scrollbar = ttk.Scrollbar(
            parent, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        # Set up tree columns
        self.tree.heading("#0", text="File Browser", anchor="w")

        # Bind events
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        # Populate with initial directory
        self.refresh()

    def pack(self, **kwargs):
        """Pack the browser widgets"""
        # Extract parameters that should go to specific widgets
        tree_fill = kwargs.pop("fill", tk.BOTH)
        tree_expand = kwargs.pop("expand", True)

        self.tree.pack(side="left", fill=tree_fill, expand=tree_expand, **kwargs)
        self.scrollbar.pack(side="right", fill=tk.Y)

    def refresh(self, path=None):
        """Refresh the file browser"""
        if path:
            self.current_path = Path(path)

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Add parent directory
        if self.current_path.parent != self.current_path:
            parent_item = self.tree.insert(
                "", "end", text="..", values=["..", "parent"], tags=("parent",)
            )

        # Add directories
        try:
            for item in sorted(self.current_path.iterdir()):
                if item.is_dir() and not item.name.startswith("."):
                    item_id = self.tree.insert(
                        "",
                        "end",
                        text=item.name,
                        values=[str(item), "directory"],
                        tags=("directory",),
                    )

                    # Check if directory has subdirectories for expand icon
                    try:
                        has_subdirs = any(
                            subitem.is_dir()
                            for subitem in item.iterdir()
                            if not subitem.name.startswith(".")
                        )
                        if has_subdirs:
                            self.tree.insert(
                                item_id, "end", text="dummy"
                            )  # Placeholder
                    except:
                        pass

            # Add Python files
            for item in sorted(self.current_path.glob("*.py")):
                self.tree.insert(
                    "",
                    "end",
                    text=item.name,
                    values=[str(item), "file"],
                    tags=("file", "python"),
                )

            # Add other files
            for item in sorted(self.current_path.iterdir()):
                if (
                    item.is_file()
                    and item.suffix not in [".py", ""]
                    and not item.name.startswith(".")
                ):
                    self.tree.insert(
                        "",
                        "end",
                        text=item.name,
                        values=[str(item), "file"],
                        tags=("file",),
                    )
        except PermissionError:
            self.tree.insert("", "end", text="[Permission denied]")

    def _on_tree_select(self, event):
        """Handle tree selection"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item["values"]

        if values and len(values) >= 2:
            item_type = values[1]
            item_path = values[0]

            if item_type == "parent" and item["text"] == "..":
                # Go up one directory
                self.refresh(self.current_path.parent)
            elif self.on_file_select:
                self.on_file_select(Path(item_path))

    def _on_tree_double_click(self, event):
        """Handle double-click on directory"""
        selection = self.tree.selection()
        if not selection:
            return

        item = self.tree.item(selection[0])
        values = item["values"]

        if values and len(values) >= 2:
            item_type = values[1]
            item_path = values[0]

            if item_type == "directory":
                self.refresh(item_path)
            elif item_path == "..":
                self.refresh(self.current_path.parent)


# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================


class EngineersToolkitGUI:
    """Main Tkinter GUI application"""

    def __init__(self, root):
        self.root = root
        self.root.title("Engineer's Toolkit v1.0")
        self.root.geometry("1400x900")

        # Project state
        self.project_path = None
        self.current_project = None  # Alias for compatibility
        self.snapshot_manager = None
        self.quality_checker = QualityChecker()
        self.current_file = None
        self.check_results = {}

        # Setup styles
        self.setup_styles()

        # Create main layout
        self.create_widgets()

        # Initialize with welcome message
        self.log("Engineer's Toolkit initialized")
        self.log(f"Python: {sys.version}")
        self.log(
            f"Available tools: {', '.join([k for k, v in TOOLS_AVAILABLE.items() if v])}"
        )

    def setup_styles(self):
        """Setup Tkinter styles"""
        style = ttk.Style()

        # Configure colors
        self.colors = {
            "bg_dark": "#1e1e1e",
            "bg_medium": "#2d2d2d",
            "bg_light": "#3c3c3c",
            "fg_light": "#d4d4d4",
            "fg_dark": "#858585",
            "accent": "#007acc",
            "success": "#4ec9b0",
            "warning": "#d7ba7d",
            "error": "#f44747",
            "info": "#569cd6",
        }

        # Configure root
        self.root.configure(bg=self.colors["bg_dark"])

        # Configure styles
        style.theme_use("clam")

        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 16, "bold"),
            foreground=self.colors["accent"],
        )

        style.configure("Console.TFrame", background=self.colors["bg_medium"])

        style.configure(
            "Console.TText",
            background=self.colors["bg_medium"],
            foreground=self.colors["fg_light"],
            insertbackground=self.colors["fg_light"],
            font=("Consolas", 10),
        )

    def create_widgets(self):
        """Create all GUI widgets - HOLLOW CENTER DESIGN with panels at edges"""
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Left Panel - Controls on LEFT edge
        left_frame = ttk.Frame(
            main_container, relief=tk.RIDGE, borderwidth=2, width=250
        )
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2), pady=5)
        left_frame.pack_propagate(False)

        # Right Panel - Checks on RIGHT edge
        right_frame = ttk.Frame(
            main_container, relief=tk.RIDGE, borderwidth=2, width=250
        )
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 0), pady=5)
        right_frame.pack_propagate(False)

        # Center/Vertical container for hollow workspace and console
        center_container = ttk.Frame(main_container)
        center_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Hollow workspace (middle - EMPTY)
        hollow_frame = ttk.Frame(center_container, relief=tk.FLAT)
        hollow_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Minimal placeholder in center
        placeholder = ttk.Label(
            hollow_frame,
            text="⚙️\n\nEmpty Workspace",
            justify=tk.CENTER,
            font=("Segoe UI", 14),
        )
        placeholder.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # CLI Input (between hollow and console)
        cli_frame = ttk.LabelFrame(center_container, text="CLI Input", padding=5)
        cli_frame.pack(fill=tk.X, pady=(0, 5))

        self.cli_input_var = tk.StringVar()
        self.cli_input_entry = ttk.Entry(
            cli_frame, textvariable=self.cli_input_var, font=("Consolas", 11)
        )
        self.cli_input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self.cli_input_entry.bind("<Return>", self.execute_cli_command)
        self.cli_input_entry.focus_set()

        ttk.Button(
            cli_frame, text="Execute", command=lambda: self.execute_cli_command(None)
        ).pack(side=tk.RIGHT)

        self.cli_status_label = ttk.Label(
            center_container,
            text="Type: claude, thunar, terminal",
            foreground="#569cd6",
        )
        self.cli_status_label.pack(pady=2)

        # Console at BOTTOM
        console_frame = ttk.Frame(
            center_container, relief=tk.RIDGE, borderwidth=2, height=150
        )
        console_frame.pack(fill=tk.X, pady=0)
        console_frame.pack_propagate(False)

        # Build all panels
        self.build_left_panel(left_frame)
        self.build_right_panel(right_frame)
        self.build_console_panel(console_frame)

        # Create status bar
        self.create_status_bar()

    def build_left_panel(self, parent):
        """Build left panel - Project & Tool Controls"""
        # Title
        title_label = ttk.Label(parent, text="CONTROLS", style="Title.TLabel")
        title_label.pack(pady=10)

        # Project selection
        project_frame = ttk.LabelFrame(parent, text="Project", padding=10)
        project_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(project_frame, text="Current Project:").pack(anchor=tk.W)

        self.project_label = ttk.Label(
            project_frame, text="No project selected", foreground=self.colors["fg_dark"]
        )
        self.project_label.pack(anchor=tk.W, pady=(0, 5))

        button_frame = ttk.Frame(project_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Select", command=self.select_project).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(button_frame, text="Refresh", command=self.refresh_project).pack(
            side=tk.LEFT, padx=2
        )

        # Tool Selector for Hollow Space
        tool_selector_frame = ttk.LabelFrame(
            parent, text="Hollow Workspace Tool", padding=10
        )
        tool_selector_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(tool_selector_frame, text="Active Tool:").pack(anchor=tk.W)

        self.active_tool_var = tk.StringVar(value="None")
        tool_selector = ttk.Combobox(
            tool_selector_frame,
            textvariable=self.active_tool_var,
            state="readonly",
            values=[
                "None",
                "Terminal",
                "Thunar Browser",
                "Claude CLI",
                "grep_helper",
                "Dr Code",
            ],
        )
        tool_selector.pack(fill=tk.X, pady=5)
        tool_selector.bind("<<ComboboxSelected>>", self.on_tool_selected)

        # Tool control buttons
        tool_btn_frame = ttk.Frame(tool_selector_frame)
        tool_btn_frame.pack(fill=tk.X)

        ttk.Button(tool_btn_frame, text="Spawn", command=self.spawn_selected_tool).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(tool_btn_frame, text="Kill", command=self.kill_hollow_tool).pack(
            side=tk.LEFT, padx=2
        )

        # Snapshot controls
        snapshot_frame = ttk.LabelFrame(parent, text="Snapshots", padding=10)
        snapshot_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(snapshot_frame, text="📸 Create", command=self.create_snapshot).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(
            snapshot_frame, text="📊 Compare", command=self.compare_snapshots
        ).pack(fill=tk.X, pady=2)
        ttk.Button(snapshot_frame, text="📋 Report", command=self.generate_report).pack(
            fill=tk.X, pady=2
        )

        # Quick Actions (moved from bottom)
        actions_frame = ttk.LabelFrame(parent, text="Quick Actions", padding=10)
        actions_frame.pack(fill=tk.X, padx=5, pady=5)

        action_buttons = [
            ("🐚 Terminal", self.open_terminal),
            ("📁 File Manager", self.open_file_manager),
            ("🧹 Clean", self.clean_project),
        ]

        for text, command in action_buttons:
            ttk.Button(actions_frame, text=text, command=command).pack(
                fill=tk.X, pady=2
            )

    def build_right_panel(self, parent):
        """Build right panel - Quality Checks & Results"""
        # Title
        title_label = ttk.Label(parent, text="CHECKS & RESULTS", style="Title.TLabel")
        title_label.pack(pady=10)

        # Quality Checks
        checks_frame = ttk.LabelFrame(parent, text="Quality Checks", padding=10)
        checks_frame.pack(fill=tk.X, padx=5, pady=5)

        check_buttons = [
            ("✅ Syntax", self.check_syntax),
            ("↔️ Indentation", self.check_indentation),
            ("📦 Imports", self.check_imports),
            ("🎨 Formatting", self.check_formatting),
            ("🔍 Linting", self.check_linting),
            ("📞 Call Changes", self.check_call_changes),
            ("🚀 All Checks", self.run_all_checks),
            ("🔄 Auto-Fix", self.auto_fix),
        ]

        for text, command in check_buttons:
            ttk.Button(checks_frame, text=text, command=command).pack(fill=tk.X, pady=2)

        # Results tabs
        results_frame = ttk.LabelFrame(parent, text="Results", padding=5)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.build_results_panel(results_frame)

    def build_results_panel(self, parent):
        """Build results display panel"""
        # Create notebook for different result views
        self.results_notebook = ttk.Notebook(parent)
        self.results_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Check results tab
        check_results_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(check_results_frame, text="Check Results")

        self.results_text = scrolledtext.ScrolledText(
            check_results_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Diff viewer tab
        diff_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(diff_frame, text="Diff Viewer")

        self.diff_text = scrolledtext.ScrolledText(
            diff_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.diff_text.pack(fill=tk.BOTH, expand=True)

        # File content tab
        content_frame = ttk.Frame(self.results_notebook)
        self.results_notebook.add(content_frame, text="File Content")

        self.content_text = scrolledtext.ScrolledText(
            content_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
        )
        self.content_text.pack(fill=tk.BOTH, expand=True)

        # Make all text widgets read-only
        for widget in [self.results_text, self.diff_text, self.content_text]:
            widget.configure(state="disabled")

    def build_console_panel(self, parent):
        """Build console output panel"""
        console_label = ttk.Label(
            parent, text="Console Output", font=("Segoe UI", 10, "bold")
        )
        console_label.pack(anchor=tk.W, padx=5, pady=(5, 0))

        self.console_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg=self.colors["bg_medium"],
            fg=self.colors["fg_light"],
            insertbackground=self.colors["fg_light"],
        )
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Console controls
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        ttk.Button(
            control_frame, text="Clear Console", command=self.clear_console
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(control_frame, text="Save Log", command=self.save_log).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(control_frame, text="Copy", command=self.copy_console).pack(
            side=tk.LEFT, padx=2
        )

        # Make console read-only
        self.console_text.configure(state="disabled")

    def create_status_bar(self):
        """Create status bar at bottom"""
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Status message
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(self.status_bar, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, padx=5)

        # File info
        self.file_var = tk.StringVar(value="File: None")
        ttk.Label(self.status_bar, textvariable=self.file_var).pack(
            side=tk.LEFT, padx=20
        )

        # Project info
        self.project_var = tk.StringVar(value="Project: None")
        ttk.Label(self.status_bar, textvariable=self.project_var).pack(
            side=tk.LEFT, padx=20
        )

        # Tool availability
        tool_count = sum(1 for v in TOOLS_AVAILABLE.values() if v)
        self.tools_var = tk.StringVar(
            value=f"Tools: {tool_count}/{len(TOOLS_AVAILABLE)}"
        )
        ttk.Label(self.status_bar, textvariable=self.tools_var).pack(
            side=tk.RIGHT, padx=5
        )

    def log(self, message: str, level: str = "INFO"):
        """Log message to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Color coding based on level
        if level == "ERROR":
            color = self.colors["error"]
            prefix = "[ERROR]"
        elif level == "WARNING":
            color = self.colors["warning"]
            prefix = "[WARN]"
        elif level == "SUCCESS":
            color = self.colors["success"]
            prefix = "[OK]"
        else:
            color = self.colors["info"]
            prefix = "[INFO]"

        log_entry = f"[{timestamp}] {prefix} {message}\n"

        self.console_text.configure(state="normal")

        # Insert with color tag
        self.console_text.insert(tk.END, log_entry)

        # Apply color to the line
        start_index = f"{int(self.console_text.index('end-1c').split('.')[0]) - 1}.0"
        end_index = f"{int(self.console_text.index('end-1c').split('.')[0])}.0"

        self.console_text.tag_add(level, start_index, end_index)
        self.console_text.tag_config(level, foreground=color)

        self.console_text.see(tk.END)
        self.console_text.configure(state="disabled")

        # Update status for important messages
        if level in ["ERROR", "WARNING"]:
            self.status_var.set(f"{level}: {message[:50]}")

    def display_results(self, results: Dict, title: str = "Results"):
        """Display check results in results panel"""
        self.results_text.configure(state="normal")
        self.results_text.delete(1.0, tk.END)

        # Format results nicely
        if isinstance(results, dict):
            self._format_dict_results(results, title)
        else:
            self.results_text.insert(1.0, str(results))

        self.results_text.configure(state="disabled")
        self.results_notebook.select(0)  # Switch to results tab

    def _format_dict_results(self, data: Dict, title: str, indent: int = 0):
        """Recursively format dictionary results"""
        indent_str = "  " * indent

        if indent == 0:
            self.results_text.insert(tk.END, f"=== {title} ===\n\n")

        for key, value in data.items():
            if isinstance(value, dict):
                self.results_text.insert(tk.END, f"{indent_str}{key}:\n")
                self._format_dict_results(value, "", indent + 1)
            elif isinstance(value, list):
                self.results_text.insert(tk.END, f"{indent_str}{key}:\n")
                for item in value:
                    self.results_text.insert(tk.END, f"{indent_str}  - {item}\n")
            else:
                # Color code based on value
                if key == "passed":
                    color = self.colors["success"] if value else self.colors["error"]
                    tag_name = f"passed_{value}"
                    self.results_text.tag_config(tag_name, foreground=color)
                    self.results_text.insert(tk.END, f"{indent_str}{key}: ", "")
                    self.results_text.insert(tk.END, f"{value}\n", tag_name)
                elif "error" in key.lower() or "failed" in key.lower():
                    tag_name = f"error_{indent}"
                    self.results_text.tag_config(
                        tag_name, foreground=self.colors["error"]
                    )
                    self.results_text.insert(tk.END, f"{indent_str}{key}: ", "")
                    self.results_text.insert(tk.END, f"{value}\n", tag_name)
                else:
                    self.results_text.insert(tk.END, f"{indent_str}{key}: {value}\n")

        if indent == 0:
            self.results_text.insert(tk.END, "\n" + "=" * 40 + "\n")

    def display_diff(self, diff_text: str, title: str = "Differences"):
        """Display diff in diff viewer"""
        self.diff_text.configure(state="normal")
        self.diff_text.delete(1.0, tk.END)

        if diff_text:
            self.diff_text.insert(1.0, f"=== {title} ===\n\n")
            self.diff_text.insert(tk.END, diff_text)
        else:
            self.diff_text.insert(1.0, "No differences found")

        self.diff_text.configure(state="disabled")
        self.results_notebook.select(1)  # Switch to diff tab

    def display_file_content(self, filepath: Path):
        """Display file content in content viewer"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            self.content_text.configure(state="normal")
            self.content_text.delete(1.0, tk.END)
            self.content_text.insert(1.0, f"=== {filepath.name} ===\n\n")
            self.content_text.insert(tk.END, content)
            self.content_text.configure(state="disabled")

            self.content_text.see(1.0)
            self.results_notebook.select(2)  # Switch to content tab

        except Exception as e:
            self.log(f"Error reading file: {e}", "ERROR")

    # ============================================================================
    # CORE FUNCTIONALITY
    # ============================================================================

    def select_project(self):
        """Select a project directory"""
        project_path = filedialog.askdirectory(
            title="Select Project Directory", mustexist=True
        )

        if project_path:
            self.project_path = Path(project_path)
            self.project_label.configure(text=str(self.project_path))
            self.project_var.set(f"Project: {self.project_path.name}")

            # Initialize snapshot manager
            self.snapshot_manager = ProjectSnapshot(self.project_path)

            # Refresh file browser
            self.file_browser.refresh(self.project_path)

            self.log(f"Project loaded: {self.project_path}")
            self.log(f"Found {len(list(self.project_path.rglob('*.py')))} Python files")

    def refresh_project(self):
        """Refresh current project view"""
        if self.project_path:
            self.file_browser.refresh(self.project_path)
            self.log("Project refreshed")
        else:
            messagebox.showwarning("Warning", "No project selected")

    def create_snapshot(self):
        """Create a project snapshot"""
        if not self.project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        description = simpledialog.askstring(
            "Snapshot Description", "Enter description for snapshot:", parent=self.root
        )

        self.log(f"Creating snapshot of {self.project_path.name}...")
        self.status_var.set("Creating snapshot...")

        def snapshot_thread():
            try:
                snapshot_data = self.snapshot_manager.create_snapshot(description or "")

                # Update UI
                self.root.after(
                    0,
                    self.log,
                    f"Snapshot created: {snapshot_data['snapshot_id']}",
                    "SUCCESS",
                )
                self.root.after(
                    0,
                    self.display_results,
                    {"snapshot": snapshot_data},
                    "Snapshot Created",
                )
                self.root.after(0, lambda: self.status_var.set("Snapshot created"))

            except Exception as e:
                self.root.after(0, self.log, f"Error creating snapshot: {e}", "ERROR")
                self.root.after(0, lambda: self.status_var.set("Snapshot failed"))

        threading.Thread(target=snapshot_thread, daemon=True).start()

    def compare_snapshots(self):
        """Compare two snapshots"""
        if not self.snapshot_manager:
            messagebox.showwarning("Warning", "No project loaded")
            return

        # Get available snapshots
        snapshot_dirs = list(self.snapshot_manager.snapshot_dir.glob("*"))
        snapshots = [d.name for d in snapshot_dirs if d.is_dir()]

        if len(snapshots) < 2:
            messagebox.showinfo("Info", "Need at least 2 snapshots to compare")
            return

        # Create comparison dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Compare Snapshots")
        dialog.geometry("400x200")
        dialog.transient(self.root)

        ttk.Label(dialog, text="First Snapshot:").pack(pady=(10, 0))
        snapshot1_var = tk.StringVar(value=snapshots[0])
        snapshot1_combo = ttk.Combobox(
            dialog, textvariable=snapshot1_var, values=snapshots, state="readonly"
        )
        snapshot1_combo.pack(pady=5)

        ttk.Label(dialog, text="Second Snapshot:").pack(pady=(10, 0))
        snapshot2_var = tk.StringVar(
            value=snapshots[-1] if len(snapshots) > 1 else snapshots[0]
        )
        snapshot2_combo = ttk.Combobox(
            dialog, textvariable=snapshot2_var, values=snapshots, state="readonly"
        )
        snapshot2_combo.pack(pady=5)

        def do_compare():
            snapshot1 = snapshot1_var.get()
            snapshot2 = snapshot2_var.get()

            if snapshot1 == snapshot2:
                messagebox.showwarning("Warning", "Please select different snapshots")
                return

            dialog.destroy()

            self.log(f"Comparing {snapshot1} with {snapshot2}...")
            self.status_var.set("Comparing snapshots...")

            def compare_thread():
                try:
                    differences = self.snapshot_manager.compare_snapshots(
                        snapshot1, snapshot2
                    )

                    self.root.after(0, self.log, "Comparison complete", "SUCCESS")
                    self.root.after(
                        0, self.display_results, differences, "Snapshot Comparison"
                    )

                    # Show diff if there are modified files
                    if differences.get("modified_files"):
                        self.root.after(
                            0,
                            self.show_file_diff,
                            snapshot1,
                            snapshot2,
                            differences["modified_files"][0],
                        )

                    self.root.after(
                        0, lambda: self.status_var.set("Comparison complete")
                    )

                except Exception as e:
                    self.root.after(
                        0, self.log, f"Error comparing snapshots: {e}", "ERROR"
                    )
                    self.root.after(0, lambda: self.status_var.set("Comparison failed"))

            threading.Thread(target=compare_thread, daemon=True).start()

        ttk.Button(dialog, text="Compare", command=do_compare).pack(pady=20)

    def show_file_diff(self, snapshot1_id: str, snapshot2_id: str, filename: str):
        """Show diff for a specific file between snapshots"""
        try:
            # Get file paths from snapshots
            file1_path = (
                self.snapshot_manager.snapshot_dir / snapshot1_id / "files" / filename
            )
            file2_path = (
                self.snapshot_manager.snapshot_dir / snapshot2_id / "files" / filename
            )

            # If snapshot doesn't have individual file copies, use current project
            if not file1_path.exists():
                file1_path = self.project_path / filename
            if not file2_path.exists():
                file2_path = self.project_path / filename

            if file1_path.exists() and file2_path.exists():
                with open(file1_path, "r") as f1, open(file2_path, "r") as f2:
                    lines1 = f1.readlines()
                    lines2 = f2.readlines()

                diff = difflib.unified_diff(
                    lines1,
                    lines2,
                    fromfile=f"{snapshot1_id}/{filename}",
                    tofile=f"{snapshot2_id}/{filename}",
                    lineterm="",
                )

                diff_text = "\n".join(diff)
                self.display_diff(diff_text, f"Diff: {filename}")

        except Exception as e:
            self.log(f"Error generating diff: {e}", "ERROR")

    def generate_report(self):
        """Generate project report"""
        if not self.project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        self.log("Generating project report...")

        def report_thread():
            try:
                # Analyze project
                imports = self.snapshot_manager._analyze_imports()
                dependencies = self.snapshot_manager._scan_dependencies()
                files = self.snapshot_manager._scan_files()

                # Create report
                report = {
                    "project": str(self.project_path),
                    "generated": datetime.now().isoformat(),
                    "summary": {
                        "total_files": len(files),
                        "total_imports": sum(len(imps) for imps in imports.values()),
                        "unique_imports": len(
                            set(imp for imps in imports.values() for imp in imps)
                        ),
                        "has_requirements": len(dependencies["requirements_txt"]) > 0,
                        "has_pyproject": dependencies["pyproject_toml"],
                    },
                    "files": files[:50],  # Limit to first 50 files
                    "top_imports": self._get_top_imports(imports),
                    "dependencies": dependencies,
                }

                # Save report
                report_file = self.project_path / "project_report.json"
                with open(report_file, "w") as f:
                    json.dump(report, f, indent=2)

                self.root.after(
                    0, self.log, f"Report saved to {report_file}", "SUCCESS"
                )
                self.root.after(0, self.display_results, report, "Project Report")

            except Exception as e:
                self.root.after(0, self.log, f"Error generating report: {e}", "ERROR")

        threading.Thread(target=report_thread, daemon=True).start()

    def _get_top_imports(self, imports: Dict[str, List[str]]) -> List[Tuple[str, int]]:
        """Get most common imports"""
        import_counts = {}
        for file_imports in imports.values():
            for imp in file_imports:
                import_counts[imp] = import_counts.get(imp, 0) + 1

        return sorted(import_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    def on_file_selected(self, filepath: Path):
        """Handle file selection from browser"""
        if filepath.is_file():
            self.current_file = filepath
            self.file_var.set(f"File: {filepath.name}")

            # Display file content
            self.display_file_content(filepath)

            self.log(f"Selected: {filepath.name}")

    def check_syntax(self):
        """Run syntax check on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Checking syntax: {self.current_file.name}")
        result = self.quality_checker.check_syntax(self.current_file)
        self.display_results(result, "Syntax Check")

        if result["passed"]:
            self.log("Syntax check passed", "SUCCESS")
        else:
            self.log(f"Syntax check failed: {result.get('message', '')}", "ERROR")

    def check_indentation(self):
        """Run indentation check on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Checking indentation: {self.current_file.name}")
        result = self.quality_checker.check_indentation(self.current_file)
        self.display_results(result, "Indentation Check")

        if result["passed"]:
            self.log("Indentation check passed", "SUCCESS")
        else:
            self.log(f"Indentation issues: {len(result['issues'])} found", "WARNING")

    def check_imports(self):
        """Run import check on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Checking imports: {self.current_file.name}")
        result = self.quality_checker.check_imports(self.current_file)
        self.display_results(result, "Import Check")

        if result["passed"]:
            self.log(
                f"Import check passed ({len(result['imports'])} imports)", "SUCCESS"
            )
        else:
            self.log(f"Import issues: {len(result['issues'])} found", "WARNING")

    def check_formatting(self):
        """Run formatting check on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Checking formatting: {self.current_file.name}")
        result = self.quality_checker.check_formatting(self.current_file)
        self.display_results(result, "Formatting Check")

        if result["passed"]:
            self.log("Formatting check passed", "SUCCESS")
        else:
            self.log("Formatting issues found", "WARNING")
            if result.get("diff"):
                self.display_diff(result["diff"], "Formatting Changes")

    def check_linting(self):
        """Run linting check on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Checking linting: {self.current_file.name}")
        result = self.quality_checker.check_linting(self.current_file)
        self.display_results(result, "Linting Check")

        if result["passed"]:
            self.log("Linting check passed", "SUCCESS")
        else:
            self.log(f"Linting issues: {len(result['issues'])} found", "WARNING")

    def check_call_changes(self):
        """Check for call changes compared to previous version"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        # Ask for previous version
        previous_file = filedialog.askopenfilename(
            title="Select Previous Version",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )

        if not previous_file:
            return

        self.log(f"Checking call changes: {self.current_file.name}")
        result = self.quality_checker.check_call_changes(
            self.current_file, Path(previous_file)
        )
        self.display_results(result, "Call Changes Check")

        if result["passed"]:
            self.log("No call changes detected", "SUCCESS")
        else:
            self.log(f"Call changes detected", "WARNING")

    def run_all_checks(self):
        """Run all quality checks on current file"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Running all checks: {self.current_file.name}")

        # Check for previous version
        previous_file = None
        if self.snapshot_manager and self.snapshot_manager.snapshot_dir.exists():
            # Look for previous version in snapshots
            snapshot_dirs = list(self.snapshot_manager.snapshot_dir.glob("*"))
            if snapshot_dirs:
                # Use the most recent snapshot
                latest_snapshot = max(snapshot_dirs, key=lambda x: x.stat().st_mtime)
                previous_file = (
                    latest_snapshot
                    / "files"
                    / self.current_file.relative_to(self.project_path)
                )
                if not previous_file.exists():
                    previous_file = None

        def all_checks_thread():
            try:
                results = self.quality_checker.run_all_checks(
                    self.current_file, previous_file
                )

                self.root.after(0, self.log, "All checks complete", "SUCCESS")
                self.root.after(0, self.display_results, results, "All Quality Checks")

                # Store results
                self.check_results = results

                # Show summary
                summary = results.get("summary", {})
                self.root.after(
                    0,
                    self.log,
                    f"Summary: {summary.get('passed_checks', 0)}/{summary.get('total_checks', 0)} checks passed",
                )

            except Exception as e:
                self.root.after(0, self.log, f"Error running checks: {e}", "ERROR")

        threading.Thread(target=all_checks_thread, daemon=True).start()

    def auto_fix(self):
        """Attempt to auto-fix issues"""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please select a file first")
            return

        self.log(f"Attempting auto-fix: {self.current_file.name}")

        # Create backup
        backup_file = self.current_file.with_suffix(
            self.current_file.suffix + ".backup"
        )
        shutil.copy2(self.current_file, backup_file)

        fixes_applied = []

        # Try black formatting
        if TOOLS_AVAILABLE.get("black"):
            try:
                subprocess.run(
                    ["black", str(self.current_file)], check=True, capture_output=True
                )
                fixes_applied.append("formatting")
            except Exception as e:
                self.log(f"Black auto-fix failed: {e}", "WARNING")

        # Try ruff fixes
        if TOOLS_AVAILABLE.get("ruff"):
            try:
                subprocess.run(
                    ["ruff", "--fix", str(self.current_file)],
                    check=True,
                    capture_output=True,
                )
                fixes_applied.append("linting")
            except Exception as e:
                self.log(f"Ruff auto-fix failed: {e}", "WARNING")

        if fixes_applied:
            # Show diff
            with open(backup_file, "r") as f1, open(self.current_file, "r") as f2:
                diff = difflib.unified_diff(
                    f1.readlines(),
                    f2.readlines(),
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
                diff_text = "\n".join(diff)

            self.display_diff(diff_text, "Auto-Fix Changes")
            self.display_file_content(self.current_file)  # Refresh content view

            self.log(f"Auto-fix applied: {', '.join(fixes_applied)}", "SUCCESS")
            self.log(f"Backup saved to: {backup_file}")
        else:
            self.log("No auto-fixes available or applied", "WARNING")
            backup_file.unlink()  # Remove backup if no changes

    def open_terminal(self):
        """Open terminal in project directory"""
        if not self.project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        try:
            # Try different terminal emulators
            terminals = [
                "gnome-terminal",
                "xterm",
                "konsole",
                "terminator",
                "xfce4-terminal",
            ]

            for terminal in terminals:
                if shutil.which(terminal):
                    subprocess.Popen(
                        [terminal, "--working-directory", str(self.project_path)]
                    )
                    self.log(f"Opened {terminal} in project directory", "SUCCESS")
                    return

            # Fallback: use system default
            import platform

            system = platform.system()

            if system == "Windows":
                os.startfile(str(self.project_path))
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", str(self.project_path)])
            else:  # Linux/Unix
                subprocess.Popen(["xdg-open", str(self.project_path)])

            self.log("Opened file manager in project directory", "SUCCESS")

        except Exception as e:
            self.log(f"Error opening terminal: {e}", "ERROR")

    def open_file_manager(self):
        """Open file manager in project directory"""
        if not self.project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        try:
            import platform

            system = platform.system()

            if system == "Windows":
                os.startfile(str(self.project_path))
            elif system == "Darwin":  # macOS
                subprocess.Popen(["open", str(self.project_path)])
            else:  # Linux/Unix
                subprocess.Popen(["xdg-open", str(self.project_path)])

            self.log("Opened file manager", "SUCCESS")

        except Exception as e:
            self.log(f"Error opening file manager: {e}", "ERROR")

    def clean_project(self):
        """Clean project temporary files"""
        if not self.project_path:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        # Ask for confirmation
        if not messagebox.askyesno(
            "Confirm Clean",
            "Clean temporary files from project?\n\n"
            "This will remove:\n"
            "- __pycache__ directories\n"
            "- .pyc files\n"
            "- .pyo files\n"
            "- .pyd files\n"
            "- .coverage files\n"
            "- .cache directories",
        ):
            return

        self.log("Cleaning project...")

        patterns_to_remove = [
            "__pycache__",
            "*.pyc",
            "*.pyo",
            "*.pyd",
            ".coverage",
            ".cache",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        ]

        files_removed = 0
        dirs_removed = 0

        for pattern in patterns_to_remove:
            if "*" in pattern:
                # File pattern
                for file in self.project_path.rglob(pattern):
                    try:
                        file.unlink()
                        files_removed += 1
                    except Exception:
                        pass
            else:
                # Directory pattern
                for dir_path in self.project_path.rglob(pattern):
                    if dir_path.is_dir():
                        try:
                            shutil.rmtree(dir_path)
                            dirs_removed += 1
                        except Exception:
                            pass

        self.log(
            f"Cleaned {files_removed} files and {dirs_removed} directories", "SUCCESS"
        )

    def run_custom_command(self):
        """Run a custom shell command"""
        command = simpledialog.askstring(
            "Custom Command", "Enter command to run:", parent=self.root
        )

        if not command:
            return

        if self.project_path:
            cwd = str(self.project_path)
        else:
            cwd = None

        self.log(f"Running: {command}")

        def command_thread():
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                output = []
                if result.stdout:
                    output.append(f"STDOUT:\n{result.stdout}")
                if result.stderr:
                    output.append(f"STDERR:\n{result.stderr}")

                self.root.after(
                    0, self.log, f"Command exited with code: {result.returncode}"
                )
                self.root.after(
                    0,
                    self.display_results,
                    {
                        "command": command,
                        "returncode": result.returncode,
                        "output": "\n".join(output),
                    },
                    "Command Results",
                )

            except subprocess.TimeoutExpired:
                self.root.after(
                    0, self.log, "Command timed out after 30 seconds", "ERROR"
                )
            except Exception as e:
                self.root.after(0, self.log, f"Error running command: {e}", "ERROR")

        threading.Thread(target=command_thread, daemon=True).start()

    def clear_console(self):
        """Clear console output"""
        self.console_text.configure(state="normal")
        self.console_text.delete(1.0, tk.END)
        self.console_text.configure(state="disabled")

    def save_log(self):
        """Save console log to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[
                ("Log files", "*.log"),
                ("Text files", "*.txt"),
                ("All files", "*.*"),
            ],
        )

        if filename:
            try:
                with open(filename, "w") as f:
                    f.write(self.console_text.get(1.0, tk.END))
                self.log(f"Log saved to {filename}", "SUCCESS")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")

    def copy_console(self):
        """Copy console content to clipboard"""
        content = self.console_text.get(1.0, tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.log("Console content copied to clipboard", "SUCCESS")

    # ========================================================================
    # HOLLOW WORKSPACE - Tool Spawning & Management
    # ========================================================================

    def on_tool_selected(self, event=None):
        """Handle tool selection from dropdown"""
        tool = self.active_tool_var.get()
        self.cli_status_label.config(
            text=f"Selected: {tool} - Click 'Spawn' to activate"
        )

    def spawn_selected_tool(self):
        """Spawn the selected tool as external window"""
        tool = self.active_tool_var.get()

        if tool == "None":
            messagebox.showwarning("No Tool", "Please select a tool first")
            return

        # Spawn based on tool type
        tool_map = {
            "Terminal": self.spawn_terminal,
            "Thunar Browser": self.spawn_thunar,
            "Claude CLI": self.spawn_claude_cli,
            "grep_helper": self.spawn_grep_helper,
            "Dr Code": self.spawn_dr_code,
        }

        spawn_func = tool_map.get(tool)
        if spawn_func:
            try:
                spawn_func()
                self.cli_status_label.config(
                    text=f"✓ {tool} launched", foreground=self.colors["success"]
                )
            except Exception as e:
                self.cli_status_label.config(
                    text=f"✗ Error launching {tool}: {e}",
                    foreground=self.colors["error"],
                )
                self.log(f"Error launching {tool}: {e}", "ERROR")

    def kill_hollow_tool(self):
        """Placeholder - tools launch externally, user closes them"""
        self.log("Tools launched externally - close them manually", "INFO")

    def spawn_terminal(self):
        """Spawn external terminal"""
        try:
            subprocess.Popen(["xterm"])
            self.log("Terminal launched", "SUCCESS")
        except FileNotFoundError:
            self.log("xterm not found", "ERROR")
            raise

    def spawn_thunar(self):
        """Spawn Thunar file browser"""
        # Get current project path or home
        path = str(self.current_project or Path.home())

        try:
            subprocess.Popen(["thunar", path])
            self.log(f"Thunar launched at {path}", "SUCCESS")
        except FileNotFoundError:
            self.log("Thunar not found", "ERROR")
            raise

    def spawn_claude_cli(self):
        """Spawn Claude CLI in external terminal"""
        try:
            subprocess.Popen(["xterm", "-e", "claude"])
            self.log("Claude CLI launched", "SUCCESS")
        except FileNotFoundError as e:
            self.log(f"Error launching Claude CLI: {e}", "ERROR")
            raise

    def spawn_grep_helper(self):
        """Spawn grep_helper"""
        self.log("grep_helper integration coming soon", "INFO")
        messagebox.showinfo("Coming Soon", "grep_helper integration coming soon!")

    def spawn_dr_code(self):
        """Spawn Dr Code CLI"""
        self.log("Dr Code integration coming soon", "INFO")
        messagebox.showinfo("Coming Soon", "Dr Code integration coming soon!")

    def execute_cli_command(self, event=None):
        """Execute command from CLI input line - launches xterm with command"""
        command = self.cli_input_var.get().strip()

        if not command:
            return

        self.log(f"> {command}", "INFO")

        # Parse command
        parts = command.split()
        cmd_name = parts[0].lower()

        # Route to appropriate handler
        if cmd_name in ["claude", "sonnet", "opus", "haiku"]:
            # Launch xterm with claude CLI
            try:
                subprocess.Popen(["xterm", "-e", command])
                self.log(f"Launched: {command}", "SUCCESS")
                self.cli_status_label.config(
                    text=f"✓ {command} launched", foreground=self.colors["success"]
                )
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                self.cli_status_label.config(
                    text=f"✗ Error: {e}", foreground=self.colors["error"]
                )

        elif cmd_name in ["thunar", "browser", "files"]:
            # Launch Thunar
            path = parts[1] if len(parts) > 1 else str(Path.home())
            try:
                subprocess.Popen(["thunar", path])
                self.log(f"Thunar launched at {path}", "SUCCESS")
                self.cli_status_label.config(
                    text="✓ Thunar launched", foreground=self.colors["success"]
                )
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")

        elif cmd_name in ["terminal", "term", "shell", "xterm"]:
            # Launch terminal
            try:
                subprocess.Popen(["xterm"])
                self.log("Terminal launched", "SUCCESS")
                self.cli_status_label.config(
                    text="✓ Terminal launched", foreground=self.colors["success"]
                )
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")

        else:
            # Execute as system command in xterm
            try:
                subprocess.Popen(["xterm", "-hold", "-e", "bash", "-c", command])
                self.log(f"Executed: {command}", "SUCCESS")
                self.cli_status_label.config(
                    text=f"✓ {command}", foreground=self.colors["success"]
                )
            except Exception as e:
                self.log(f"Error: {e}", "ERROR")
                self.cli_status_label.config(
                    text=f"✗ Error: {e}", foreground=self.colors["error"]
                )

        # Clear input
        self.cli_input_var.set("")


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Engineer's Toolkit GUI - Development workflow tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Launch GUI
  %(prog)s --project /path/to/project  # Launch with project loaded
  %(prog)s --check file.py          # Run quick check on file
  %(prog)s --snapshot              # Create snapshot of current directory
        
Features:
  • Project state snapshots and comparison
  • Comprehensive quality checks (syntax, indentation, imports, etc.)
  • Integrated file browser
  • Auto-fix capabilities
  • Terminal and file manager integration
  • Custom command execution
        """,
    )

    parser.add_argument("--project", "-p", help="Load project directory")
    parser.add_argument("--check", "-c", help="Quick check file and exit")
    parser.add_argument(
        "--snapshot", "-s", action="store_true", help="Create snapshot and exit"
    )
    parser.add_argument(
        "--report", "-r", action="store_true", help="Generate report and exit"
    )
    parser.add_argument("--no-gui", action="store_true", help="Run in CLI mode only")

    args = parser.parse_args()

    # CLI mode for quick operations
    if args.no_gui or args.check or args.snapshot or args.report:
        print("Engineer's Toolkit - CLI Mode")
        print("=" * 50)

        if args.check:
            filepath = Path(args.check)
            if filepath.exists():
                checker = QualityChecker()
                results = checker.run_all_checks(filepath)
                print(f"\nResults for {filepath.name}:")
                print(json.dumps(results, indent=2))
            else:
                print(f"File not found: {filepath}")

        elif args.snapshot:
            project_path = Path(args.project) if args.project else Path.cwd()
            snapshot = ProjectSnapshot(project_path)
            data = snapshot.create_snapshot("CLI snapshot")
            print(f"\nSnapshot created: {data['snapshot_id']}")
            print(f"Files: {len(data['files'])}")
            print(f"Snapshot saved to: {snapshot.snapshot_dir / data['snapshot_id']}")

        elif args.report:
            project_path = Path(args.project) if args.project else Path.cwd()
            snapshot = ProjectSnapshot(project_path)
            imports = snapshot._analyze_imports()
            dependencies = snapshot._scan_dependencies()

            print(f"\nProject Report: {project_path.name}")
            print(f"Python files: {len(list(project_path.rglob('*.py')))}")
            print(f"Total imports: {sum(len(imps) for imps in imports.values())}")
            print(f"Dependency files: {len(dependencies['requirements_txt'])}")

        return

    # GUI mode
    try:
        root = tk.Tk()
        app = EngineersToolkitGUI(root)

        # Load project if specified
        if args.project:
            project_path = Path(args.project)
            if project_path.exists():
                app.project_path = project_path
                app.project_label.configure(text=str(project_path))
                app.project_var.set(f"Project: {project_path.name}")
                app.snapshot_manager = ProjectSnapshot(project_path)
                app.file_browser.refresh(project_path)
                app.log(f"Loaded project: {project_path}")

        # Center window
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.mainloop()

    except Exception as e:
        print(f"Error starting GUI: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
