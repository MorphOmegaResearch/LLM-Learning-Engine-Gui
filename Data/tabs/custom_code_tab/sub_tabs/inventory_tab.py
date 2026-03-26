"""
Inventory Tab — Document Ingestion + Stash Management UX

Surfaces three backend systems in one sub-tab:
1. Pattern DB ingestion (txt / md / stl / sha / .py → py_manifest_augmented.py)
2. Stash snapshot management (wraps stash_script.py via subprocess)
3. Project inventory state (reads unified_entity_index.json)
"""

import json
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from datetime import datetime

from logger_util import log_message

def log_error(msg): log_message(f"ERROR: {msg}")
def log_exception(msg): log_message(f"EXCEPTION: {msg}")

# ---------------------------------------------------------------------------
# Path constants (relative to __file__ for portability)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).parent
_CUSTOM_CODE_TAB_DIR = _HERE.parent
_DATA_DIR = _CUSTOM_CODE_TAB_DIR.parent.parent  # Data/

STASH_SCRIPT = _DATA_DIR / "tabs" / "ag_forge_tab" / "modules" / "quick_clip" / "stash_script.py"
PY_MANIFEST = _DATA_DIR / "pymanifest" / "py_manifest_augmented.py"
BABEL_INDEX = _DATA_DIR / "tabs" / "action_panel_tab" / "babel_data" / "index" / "unified_entity_index.json"
PATTERNS_JSON = _DATA_DIR / "pymanifest" / "pymanifest_patterns.json"
VARIANT_EXPORTER = _DATA_DIR / "pymanifest" / "variant_exporter.py"
SPAWN_LOG = _DATA_DIR / "pymanifest" / "variants" / "spawn_log.jsonl"

# Resolve BaseTab from parent package
try:
    from tabs.base_tab import BaseTab
except ImportError:
    # Fallback: minimal stub so the file is importable standalone
    class BaseTab:  # type: ignore
        def __init__(self, parent, root, style, *args, **kwargs):
            self.parent = parent
            self.root = root
            self.style = style

        def safe_create(self):
            self.create_ui()


class InventoryTab(BaseTab):
    """Unified inventory UX: document ingestion, stash management, project index."""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self._selected_file: str = ""
        self._last_ingest_time: str = ""

    # ------------------------------------------------------------------
    # BaseTab entry point
    # ------------------------------------------------------------------
    def create_ui(self):
        log_message("INVENTORY_TAB: Creating UI")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # file onboarding bar
        self.parent.rowconfigure(1, weight=0)  # export variant bar
        self.parent.rowconfigure(2, weight=1)  # middle panes
        self.parent.rowconfigure(3, weight=0)  # stats bar

        self._build_onboarding_bar(self.parent)
        self._build_export_bar(self.parent)
        self._build_middle_row(self.parent)
        self._build_stats_bar(self.parent)
        self._refresh_stats()
        log_message("INVENTORY_TAB: UI created")

    # ------------------------------------------------------------------
    # TOP ROW: file onboarding bar
    # ------------------------------------------------------------------
    def _build_onboarding_bar(self, parent):
        bar = ttk.LabelFrame(parent, text="📂 Document Onboarding → Pattern DB", padding=6)
        bar.grid(row=0, column=0, sticky=tk.EW, padx=8, pady=(8, 4))
        bar.columnconfigure(5, weight=1)

        btn_style = 'Select.TButton'

        ttk.Button(bar, text="📄 Add TXT", style=btn_style,
                   command=lambda: self._pick_file([("Text", "*.txt"), ("All", "*.*")])).grid(
            row=0, column=0, padx=(0, 3))
        ttk.Button(bar, text="📋 Add MD", style=btn_style,
                   command=lambda: self._pick_file([("Markdown", "*.md"), ("All", "*.*")])).grid(
            row=0, column=1, padx=3)
        ttk.Button(bar, text="🧊 Add STL", style=btn_style,
                   command=lambda: self._pick_file([("STL", "*.stl"), ("All", "*.*")])).grid(
            row=0, column=2, padx=3)
        ttk.Button(bar, text="🔑 Add SHA", style=btn_style,
                   command=lambda: self._pick_file([("JSON", "*.json"), ("All", "*.*")])).grid(
            row=0, column=3, padx=3)
        ttk.Button(bar, text="🐍 Add .py", style=btn_style,
                   command=lambda: self._pick_file([("Python", "*.py"), ("All", "*.*")])).grid(
            row=0, column=4, padx=3)

        # Selected file display
        self._file_var = tk.StringVar(value="(no file selected)")
        ttk.Entry(bar, textvariable=self._file_var, state='readonly', width=50).grid(
            row=0, column=5, padx=8, sticky=tk.EW)

        ttk.Button(bar, text="⚡ Ingest to Pattern DB", style='Select.TButton',
                   command=self._run_ingest).grid(row=0, column=6, padx=(3, 0))

        self._ingest_result_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._ingest_result_var,
                  foreground="#a8d8a8").grid(row=1, column=0, columnspan=7, sticky=tk.W, pady=(3, 0))

    def _pick_file(self, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            self._selected_file = path
            self._file_var.set(path)
            self._ingest_result_var.set("")

    def _run_ingest(self):
        path = self._selected_file
        if not path:
            self._ingest_result_var.set("⚠ No file selected")
            return
        ext = Path(path).suffix.lower()
        if ext == ".txt":
            flag = "--txt"
        elif ext == ".md":
            flag = "--md"
        elif ext == ".stl":
            flag = "--stl"
        elif ext == ".json":
            flag = "--sha"
        elif ext == ".py":
            flag = "--script"
        else:
            flag = "--txt"  # fallback

        cmd = [sys.executable, str(PY_MANIFEST), "ingest", flag, path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                               cwd=str(PY_MANIFEST.parent))
            output = r.stdout + r.stderr
            # Extract summary line
            for line in output.splitlines():
                if "ingest-" in line or "ingested" in line.lower():
                    self._ingest_result_var.set(f"✓ {line.strip()}")
                    break
            else:
                self._ingest_result_var.set(f"✓ Done (see log)")
            self._last_ingest_time = datetime.now().strftime("%H:%M:%S")
            self._refresh_stats()
        except subprocess.TimeoutExpired:
            self._ingest_result_var.set("⚠ Ingest timed out (>60s)")
        except Exception as e:
            self._ingest_result_var.set(f"✗ Error: {e}")

    # ------------------------------------------------------------------
    # EXPORT VARIANT BAR
    # ------------------------------------------------------------------
    def _build_export_bar(self, parent):
        bar = ttk.LabelFrame(parent, text="🚀 Export Variant State", padding=6)
        bar.grid(row=1, column=0, sticky=tk.EW, padx=8, pady=(0, 4))
        bar.columnconfigure(1, weight=1)

        btn_style = 'Select.TButton'

        # Row 0: variant selector + output dir + export button
        ttk.Label(bar, text="Variant:").grid(row=0, column=0, padx=(0, 3), sticky=tk.W)
        self._export_variant_var = tk.StringVar(value="(loading…)")
        self._export_variant_cb = ttk.Combobox(bar, textvariable=self._export_variant_var,
                                                state='readonly', width=30)
        self._export_variant_cb.grid(row=0, column=1, padx=(0, 6), sticky=tk.W)

        ttk.Label(bar, text="Output:").grid(row=0, column=2, padx=(6, 3), sticky=tk.W)
        self._export_out_var = tk.StringVar(value=str(Path.home()))
        ttk.Entry(bar, textvariable=self._export_out_var, width=28).grid(
            row=0, column=3, padx=(0, 3), sticky=tk.EW)
        ttk.Button(bar, text="📁", style=btn_style, width=3,
                   command=self._browse_export_dir).grid(row=0, column=4, padx=(0, 6))

        ttk.Button(bar, text="🚀 Export Variant", style=btn_style,
                   command=self._run_export).grid(row=0, column=5, padx=(0, 0))

        # Row 1: checkboxes + result label
        check_frame = ttk.Frame(bar)
        check_frame.grid(row=1, column=0, columnspan=4, sticky=tk.W, pady=(4, 0))

        self._export_toolkit_var = tk.BooleanVar(value=True)
        self._export_viz_var = tk.BooleanVar(value=True)
        self._export_gguf_var = tk.BooleanVar(value=True)
        self._export_register_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(check_frame, text="Include Toolkit",
                        variable=self._export_toolkit_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(check_frame, text="Include Viz",
                        variable=self._export_viz_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(check_frame, text="Include GGUF",
                        variable=self._export_gguf_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Checkbutton(check_frame, text="Register with Stash",
                        variable=self._export_register_var).pack(side=tk.LEFT)

        self._export_result_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self._export_result_var,
                  foreground="#a8d8a8").grid(row=1, column=4, columnspan=2,
                                             sticky=tk.W, padx=(6, 0), pady=(4, 0))

        # Populate variant list
        self._load_export_variants()

    def _load_export_variants(self):
        """Populate variant combobox from spawn_log.jsonl."""
        names = []
        if SPAWN_LOG.exists():
            try:
                seen = set()
                for line in reversed(SPAWN_LOG.read_text().splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        name = entry.get("name", "")
                        if name and name not in seen:
                            seen.add(name)
                            names.append(name)
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                log_error(f"INVENTORY_TAB: spawn_log read error: {e}")
        if not names:
            names = ["(no variants found)"]
        self._export_variant_cb['values'] = names
        self._export_variant_var.set(names[0])

    def _browse_export_dir(self):
        path = filedialog.askdirectory(title="Select export output directory")
        if path:
            self._export_out_var.set(path)

    def _run_export(self):
        variant = self._export_variant_var.get().strip()
        output = self._export_out_var.get().strip()
        if not variant or variant.startswith("("):
            self._export_result_var.set("⚠ Select a variant first")
            return
        if not output:
            self._export_result_var.set("⚠ Choose an output directory")
            return

        self._export_result_var.set("⏳ Exporting…")
        self.parent.update_idletasks()

        cmd = [sys.executable, str(VARIANT_EXPORTER), "--export", variant, "--output", output]
        if not self._export_toolkit_var.get():
            cmd.append("--no-toolkit")
        if not self._export_viz_var.get():
            cmd.append("--no-viz")
        if not self._export_gguf_var.get():
            cmd.append("--no-gguf")
        if self._export_register_var.get():
            cmd.append("--register")

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                               cwd=str(VARIANT_EXPORTER.parent))
            output_text = r.stdout + r.stderr
            # Extract key line
            for line in output_text.splitlines():
                if "Size:" in line or "Path:" in line:
                    size_line = line.strip()
                    path_line = ""
                    for l2 in output_text.splitlines():
                        if "Path:" in l2:
                            path_line = l2.strip()
                            break
                    self._export_result_var.set(f"✓ {path_line}  {size_line}")
                    break
            else:
                if r.returncode == 0:
                    self._export_result_var.set("✓ Export complete")
                else:
                    self._export_result_var.set(f"✗ Export failed (see log)")
        except subprocess.TimeoutExpired:
            self._export_result_var.set("⚠ Export timed out (>120s)")
        except Exception as e:
            self._export_result_var.set(f"✗ Error: {e}")

    # ------------------------------------------------------------------
    # MIDDLE ROW: stash manager (left) + project index (right)
    # ------------------------------------------------------------------
    def _build_middle_row(self, parent):
        mid = ttk.Frame(parent)
        mid.grid(row=2, column=0, sticky=tk.NSEW, padx=8, pady=4)
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)

        self._build_stash_panel(mid)
        self._build_project_index_panel(mid)

    # --- Left: Stash Manager ---
    def _build_stash_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="📸 Stash", padding=6)
        frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 4))
        frame.rowconfigure(5, weight=1)

        btn_style = 'Select.TButton'
        ttk.Button(frame, text="📸 Quick Stash", style=btn_style,
                   command=lambda: self._run_stash(["-s"])).grid(
            row=0, column=0, sticky=tk.EW, pady=2)
        ttk.Button(frame, text="📋 View Lineage", style=btn_style,
                   command=lambda: self._run_stash(["-l"])).grid(
            row=1, column=0, sticky=tk.EW, pady=2)
        ttk.Button(frame, text="📦 List Inventories", style=btn_style,
                   command=lambda: self._run_stash(["--list-inventories"])).grid(
            row=2, column=0, sticky=tk.EW, pady=2)
        ttk.Button(frame, text="➕ Add to Inventory", style=btn_style,
                   command=self._add_to_inventory_dialog).grid(
            row=3, column=0, sticky=tk.EW, pady=2)

        # Output log
        self._stash_log = ScrolledText(frame, height=12, width=36,
                                       bg="#1e1e1e", fg="#cccccc",
                                       font=("Courier", 8), state='disabled',
                                       wrap=tk.WORD)
        self._stash_log.grid(row=5, column=0, sticky=tk.NSEW, pady=(6, 0))

    def _run_stash(self, args: list):
        if not STASH_SCRIPT.exists():
            self._stash_append(f"⚠ stash_script.py not found at:\n  {STASH_SCRIPT}\n")
            return
        cmd = [sys.executable, str(STASH_SCRIPT)] + args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                               cwd=str(STASH_SCRIPT.parent))
            output = (r.stdout + r.stderr).strip()
            lines = output.splitlines()
            self._stash_append("\n".join(lines[-20:]) + "\n")
        except subprocess.TimeoutExpired:
            self._stash_append("⚠ Stash command timed out\n")
        except Exception as e:
            self._stash_append(f"✗ Error: {e}\n")

    def _stash_append(self, text: str):
        self._stash_log.config(state='normal')
        self._stash_log.insert(tk.END, text)
        self._stash_log.see(tk.END)
        self._stash_log.config(state='disabled')

    def _add_to_inventory_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Add to Inventory")
        dlg.resizable(False, False)
        ttk.Label(dlg, text="Inventory name:").grid(row=0, column=0, padx=8, pady=8, sticky=tk.W)
        name_var = tk.StringVar()
        ttk.Entry(dlg, textvariable=name_var, width=30).grid(row=0, column=1, padx=8)
        ttk.Label(dlg, text="File path:").grid(row=1, column=0, padx=8, pady=4, sticky=tk.W)
        file_var = tk.StringVar(value=self._selected_file)
        ttk.Entry(dlg, textvariable=file_var, width=30).grid(row=1, column=1, padx=8)

        def do_add():
            name = name_var.get().strip()
            fpath = file_var.get().strip()
            if not name or not fpath:
                messagebox.showerror("Missing fields", "Name and file path are required.", parent=dlg)
                return
            self._run_stash(["--add-inventory", name, fpath])
            dlg.destroy()

        ttk.Button(dlg, text="Add", command=do_add).grid(row=2, column=0, columnspan=2, pady=8)

    # --- Right: Project Inventory ---
    def _build_project_index_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="🗂 Project Index", padding=6)
        frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(4, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Entity count label
        self._entity_count_var = tk.StringVar(value="Loading...")
        ttk.Label(frame, textvariable=self._entity_count_var).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 4))

        # Treeview
        cols = ("file_path", "owning_tab", "loc", "activity_score")
        self._entity_tree = ttk.Treeview(frame, columns=cols, show='headings', height=14)
        self._entity_tree.heading("file_path", text="File")
        self._entity_tree.heading("owning_tab", text="Tab")
        self._entity_tree.heading("loc", text="LOC")
        self._entity_tree.heading("activity_score", text="Score")
        self._entity_tree.column("file_path", width=280, stretch=True)
        self._entity_tree.column("owning_tab", width=80, stretch=False)
        self._entity_tree.column("loc", width=55, stretch=False, anchor=tk.E)
        self._entity_tree.column("activity_score", width=60, stretch=False, anchor=tk.E)

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self._entity_tree.yview)
        self._entity_tree.configure(yscrollcommand=vsb.set)
        self._entity_tree.grid(row=1, column=0, sticky=tk.NSEW)
        vsb.grid(row=1, column=1, sticky=tk.NS)

        ttk.Button(frame, text="🔄 Refresh Index", style='Select.TButton',
                   command=self._refresh_index).grid(row=2, column=0, sticky=tk.EW, pady=(4, 0))

        self._refresh_index()

    def _refresh_index(self):
        for row in self._entity_tree.get_children():
            self._entity_tree.delete(row)
        if not BABEL_INDEX.exists():
            self._entity_count_var.set(f"⚠ Index not found: {BABEL_INDEX.name}")
            return
        try:
            data = json.loads(BABEL_INDEX.read_text())
            entities = list(data.values())
            # Sort by activity_score descending, take top 50
            entities.sort(key=lambda e: float(e.get("activity_score", 0) or 0), reverse=True)
            self._entity_count_var.set(f"Entities: {len(data)} total, showing top 50")
            for ent in entities[:50]:
                fp = ent.get("file_path", "")
                # Shorten path for display
                display_fp = Path(fp).name if fp else "(unknown)"
                self._entity_tree.insert("", tk.END, values=(
                    display_fp,
                    ent.get("owning_tab", ""),
                    ent.get("loc", ""),
                    f"{float(ent.get('activity_score', 0) or 0):.1f}",
                ))
        except Exception as e:
            self._entity_count_var.set(f"✗ Error reading index: {e}")

    # ------------------------------------------------------------------
    # BOTTOM: Stats bar
    # ------------------------------------------------------------------
    def _build_stats_bar(self, parent):
        bar = ttk.LabelFrame(parent, text="📊 Stats", padding=4)
        bar.grid(row=3, column=0, sticky=tk.EW, padx=8, pady=(4, 8))

        self._stat_patterns_var = tk.StringVar(value="Pattern DB: —")
        self._stat_mtime_var = tk.StringVar(value="Last ingest: —")
        self._stat_stash_var = tk.StringVar(value="Stash snapshots: —")

        ttk.Label(bar, textvariable=self._stat_patterns_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(bar, textvariable=self._stat_mtime_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(bar, textvariable=self._stat_stash_var).pack(side=tk.LEFT, padx=10)
        ttk.Button(bar, text="🔄 Refresh Stats", style='Select.TButton',
                   command=self._refresh_stats).pack(side=tk.RIGHT, padx=6)

    def _refresh_stats(self):
        # Pattern count
        try:
            if PATTERNS_JSON.exists():
                data = json.loads(PATTERNS_JSON.read_text())
                count = len(data)
                mtime = datetime.fromtimestamp(PATTERNS_JSON.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                self._stat_patterns_var.set(f"Pattern DB: {count:,} patterns")
                self._stat_mtime_var.set(f"Last ingest: {mtime}")
            else:
                self._stat_patterns_var.set("Pattern DB: (not found)")
                self._stat_mtime_var.set("Last ingest: —")
        except Exception as e:
            self._stat_patterns_var.set(f"Pattern DB: err ({e})")

        # Stash snapshot count
        try:
            stash_dir = STASH_SCRIPT.parent / "snapshots"
            if stash_dir.exists():
                n = sum(1 for p in stash_dir.iterdir() if p.is_dir())
                self._stat_stash_var.set(f"Stash snapshots: {n}")
            else:
                self._stat_stash_var.set("Stash snapshots: 0")
        except Exception:
            self._stat_stash_var.set("Stash snapshots: —")
