"""
Models Tab - Model information, notes, and statistics
Isolated module for models-related functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
import subprocess
import shutil
import venv

import sys
import os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation_engine import EvaluationEngine
import threading
import json

from tabs.base_tab import BaseTab
try:
    from tabs.models_tab.morph_lineage import MorphLineagePanel, load_brain_maps
except Exception:
    MorphLineagePanel = None
from evaluation_engine import EvaluationEngine
from config import (
    get_ollama_models,
    get_ollama_model_info,
    parse_ollama_model_info,
    save_model_note,
    load_model_note,
    list_model_notes,
    load_training_stats,
    get_latest_training_stats,
    get_all_trained_models,
    delete_trained_model,
    get_model_skills,
    save_evaluation_report,
    get_test_suites,
    list_system_prompts,
    load_system_prompt,
    list_tool_schemas,
    load_tool_schema,
    save_baseline_report,
    load_baseline_report,
    load_latest_evaluation_report,
    get_all_trained_models,
    get_regression_policy,
    load_baseline_report,
    MODELS_DIR,
    TRAINING_DATA_DIR)


class ModelsTab(BaseTab):
    """Models information, notes, and statistics tab"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)

        # Get available models (all types)
        self.all_models = get_all_trained_models()
        self.ollama_models = get_ollama_models()  # Keep for backward compatibility

        # State variables
        self.current_model_for_stats = None
        self.current_model_info = None  # Store full model info dict
        self.tab_instances = getattr(self, 'tab_instances', None)
        # Adapters selection state
        self.adapters_select_mode = tk.BooleanVar(value=False)
        self.adapters_selection = {}  # path(str) -> BooleanVar
        self.adapters_estimate_btn = None
        self.adapters_levelup_btn = None
        
        # Levels expand/collapse state in model list
        self.levels_expanded = {}
        self.levels_ui = {}
        # Morph expand/collapse state
        self.morph_expanded = {}
        self.morph_ui = {}
        # Unified list pane section collapse state
        self.list_sections = {'base': True, 'ollama': True, 'morph': True, 'providers': True}
        self.list_section_ui = {}  # key -> {'arrow': btn, 'content': frame, 'badge': label}

    def create_ui(self):
        """Create the models tab UI"""
        # ═══════════════════════════════════════════════════════════════════
        # LAYOUT ORIENTATION
        #   LEFT  (col 0, weight=1) = model_info_frame → sub-tab detail panels
        #                             (Overview, Adapters, History, Notes, Stats, etc.)
        #   RIGHT (col 1, weight=0) = model_list_frame → scrollable selection list
        #                             (Base PyTorch, Morph Architects, Ollama/GGUF)
        # Clicking anything in RIGHT panel populates LEFT sub-tabs.
        # ═══════════════════════════════════════════════════════════════════
        parent = self.parent
        parent.columnconfigure(0, weight=1) # Model Info column (LEFT)
        parent.columnconfigure(1, weight=0) # Model List column (RIGHT)
        parent.rowconfigure(0, weight=1)

        # Left side: Model Information Display
        model_info_frame = ttk.Frame(parent, style='Category.TFrame')
        model_info_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        model_info_frame.columnconfigure(0, weight=1)
        model_info_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(model_info_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Label(header_frame, text="🧠 Model Information", font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(header_frame, text="🔄 Refresh",
                  command=self.refresh_models_tab,
                  style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        
        self.model_info_notebook = ttk.Notebook(model_info_frame)
        self.model_info_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bind_sub_notebook(self.model_info_notebook, label='Model Info')

        # Overview Tab
        self.overview_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.overview_tab_frame, text="Overview")
        # Labels for parsed info will be created dynamically in display_model_info

        # Adapters Tab (New)
        self.adapters_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.adapters_tab_frame, text="🎯 Adapters")

        # Training History Tab (New)
        self.history_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.history_tab_frame, text="📈 History")
        # Sub-tabs inside History: Runs and Levels
        self.history_notebook = ttk.Notebook(self.history_tab_frame)
        self.history_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bind_sub_notebook(self.history_notebook, label='History')
        self.history_runs_frame = ttk.Frame(self.history_notebook)
        self.history_levels_frame = ttk.Frame(self.history_notebook)
        self.history_notebook.add(self.history_runs_frame, text="Runs")
        self.history_notebook.add(self.history_levels_frame, text="Levels")

        # Raw Info Tab
        self.raw_info_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.raw_info_tab_frame, text="Raw Info")
        self.raw_model_info_text = scrolledtext.ScrolledText(
            self.raw_info_tab_frame,
            width=60,
            height=20,
            font=("Courier", 10),
            wrap=tk.WORD,
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=0
        )
        self.raw_model_info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.raw_model_info_text.config(background='#1e1e1e', foreground='#61dafb') # Fallback styling

        # Notes Tab
        self.notes_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.notes_tab_frame, text="Notes")
        self.create_notes_panel(self.notes_tab_frame)

        # Stats Tab
        self.stats_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.stats_tab_frame, text="Stats")
        self.create_stats_panel(self.stats_tab_frame)

        # Skills Tab
        self.skills_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.skills_tab_frame, text="Skills")
        self.create_skills_panel(self.skills_tab_frame)

        # Evaluation Tab
        self.evaluation_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.evaluation_tab_frame, text="🧪 Evaluation")
        self.create_evaluation_panel(self.evaluation_tab_frame)

        # Baselines Tab
        self.baselines_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.baselines_tab_frame, text="Baselines")
        self.create_baselines_panel(self.baselines_tab_frame)

        # Compare Tab
        self.compare_tab_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.compare_tab_frame, text="Compare")
        self.create_compare_panel(self.compare_tab_frame)

        # Ω Inspector Tab (omega/alpha variant inspector — populated on selection)
        self.omega_inspector_frame = ttk.Frame(self.model_info_notebook)
        self.model_info_notebook.add(self.omega_inspector_frame, text="\u03a9 Inspector")

        # Right side: Unified scrollable model list pane
        model_list_frame = ttk.Frame(parent, style='Category.TFrame')
        model_list_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        model_list_frame.columnconfigure(0, weight=1)
        model_list_frame.rowconfigure(0, weight=1)

        # Single canvas + scrollbar for the whole list pane
        right_canvas = tk.Canvas(model_list_frame, bg="#2b2b2b", highlightthickness=0)
        right_scrollbar = ttk.Scrollbar(model_list_frame, orient="vertical", command=right_canvas.yview)
        right_content = ttk.Frame(right_canvas)
        right_content.bind("<Configure>", lambda e: right_canvas.configure(scrollregion=right_canvas.bbox("all")))
        self._right_canvas_win = right_canvas.create_window((0, 0), window=right_content, anchor="nw")
        right_canvas.configure(yscrollcommand=right_scrollbar.set)
        right_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        right_scrollbar.grid(row=0, column=1, sticky=tk.NS)
        right_canvas.bind("<Configure>", lambda e: right_canvas.itemconfig(self._right_canvas_win, width=e.width))
        self.bind_mousewheel_to_canvas(right_canvas)

        # --- Section: Base Models ---
        _sec_base_hdr = ttk.Frame(right_content)
        _sec_base_hdr.pack(fill=tk.X, padx=4, pady=(6, 0))
        _base_arrow = ttk.Button(_sec_base_hdr, text='▼', width=2,
                                 command=lambda: self._toggle_list_section('base'),
                                 style='Select.TButton')
        _base_arrow.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(_sec_base_hdr, text="Available Models", font=("Arial", 11, "bold"),
                  foreground='#61dafb', style='Config.TLabel').pack(side=tk.LEFT)
        _base_badge = ttk.Label(_sec_base_hdr, text="", style='Config.TLabel', foreground='#858585')
        _base_badge.pack(side=tk.RIGHT, padx=6)
        self.base_buttons_frame = ttk.Frame(right_content)
        self.base_buttons_frame.pack(fill=tk.X)
        ttk.Separator(right_content, orient='horizontal').pack(fill=tk.X, padx=6, pady=4)
        self.list_section_ui['base'] = {'arrow': _base_arrow, 'content': self.base_buttons_frame, 'badge': _base_badge}

        # --- Section: Ollama / GGUF ---
        _sec_oll_hdr = ttk.Frame(right_content)
        _sec_oll_hdr.pack(fill=tk.X, padx=4, pady=(2, 0))
        _oll_arrow = ttk.Button(_sec_oll_hdr, text='▼', width=2,
                                command=lambda: self._toggle_list_section('ollama'),
                                style='Select.TButton')
        _oll_arrow.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(_sec_oll_hdr, text="🟡 Ollama / GGUF", font=("Arial", 11, "bold"),
                  foreground='#e8b04b', style='Config.TLabel').pack(side=tk.LEFT)
        _oll_badge = ttk.Label(_sec_oll_hdr, text="", style='Config.TLabel', foreground='#858585')
        _oll_badge.pack(side=tk.RIGHT, padx=6)
        self.ollama_buttons_frame = ttk.Frame(right_content)
        self.ollama_buttons_frame.pack(fill=tk.X)
        ttk.Separator(right_content, orient='horizontal').pack(fill=tk.X, padx=6, pady=4)
        self.list_section_ui['ollama'] = {'arrow': _oll_arrow, 'content': self.ollama_buttons_frame, 'badge': _oll_badge}

        # --- Section: Morph Specialists ---
        _sec_morph_hdr = ttk.Frame(right_content)
        _sec_morph_hdr.pack(fill=tk.X, padx=4, pady=(2, 0))
        _morph_arrow = ttk.Button(_sec_morph_hdr, text='▼', width=2,
                                  command=lambda: self._toggle_list_section('morph'),
                                  style='Select.TButton')
        _morph_arrow.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(_sec_morph_hdr, text="⚡ Morph Architects", font=("Arial", 11, "bold"),
                  foreground='#a78bfa', style='Config.TLabel').pack(side=tk.LEFT)
        _morph_badge = ttk.Label(_sec_morph_hdr, text="", style='Config.TLabel', foreground='#858585')
        _morph_badge.pack(side=tk.RIGHT, padx=6)
        self.morph_buttons_frame = ttk.Frame(right_content)
        self.morph_buttons_frame.pack(fill=tk.X)
        self.list_section_ui['morph'] = {'arrow': _morph_arrow, 'content': self.morph_buttons_frame, 'badge': _morph_badge}

        # --- Section: Providers ---
        _sec_prov_hdr = ttk.Frame(right_content)
        _sec_prov_hdr.pack(fill=tk.X, padx=4, pady=(4, 0))
        _prov_arrow = ttk.Button(_sec_prov_hdr, text='▼', width=2,
                                 command=lambda: self._toggle_list_section('providers'),
                                 style='Select.TButton')
        _prov_arrow.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(_sec_prov_hdr, text='> Providers', font=('Arial', 11, 'bold'),
                  foreground='#50fa7b', style='Config.TLabel').pack(side=tk.LEFT)
        _prov_badge = ttk.Label(_sec_prov_hdr, text='', style='Config.TLabel', foreground='#858585')
        _prov_badge.pack(side=tk.RIGHT, padx=6)
        self.providers_frame = ttk.Frame(right_content)
        self.providers_frame.pack(fill=tk.X)
        self.list_section_ui['providers'] = {
            'arrow': _prov_arrow,
            'content': self.providers_frame,
            'badge': _prov_badge
        }

        # Expanded state for Ollama groups
        self.ollama_expanded = {}
        self.ollama_ui = {}

        self.populate_model_list()

    def refresh_models_tab(self):
        """Refresh the models tab - reloads all models and updates display."""
        # Refresh model lists
        self.all_models = get_all_trained_models()
        self.ollama_models = get_ollama_models()

        # Refresh the model list display
        self.populate_model_list()

        # Refresh current model display if one is selected
        if self.current_model_info:
            # Find the current model in the refreshed list
            for model in self.all_models:
                if model['name'] == self.current_model_info['name']:
                    self.display_model_info_from_dict(model)
                    break

        print("✓ Models tab refreshed")

    def populate_model_list(self):
        """Populates the scrollable frame with buttons for each model (all types)."""
        # Clear existing buttons
        for widget in self.base_buttons_frame.winfo_children():
            widget.destroy()
        for widget in self.ollama_buttons_frame.winfo_children():
            widget.destroy()
        for widget in self.morph_buttons_frame.winfo_children():
            widget.destroy()

        # Refresh model list
        self.all_models = get_all_trained_models()

        if not self.all_models:
            ttk.Label(self.base_buttons_frame, text="No models found.", style='Config.TLabel').pack(pady=10)
            return

        # Group models by type (morph and base_config are handled by populate_morph_section)
        pytorch_models = [m for m in self.all_models if m["type"] == "pytorch"]
        trained_models = [m for m in self.all_models if m["type"] == "trained"]
        ollama_models = [m for m in self.all_models if m["type"] == "ollama"]
        gguf_models = [m for m in self.all_models if m["type"] == "gguf"]
        base_config_models = [m for m in self.all_models if m["type"] == "base_config"]

        # Display PyTorch models (base models) - Trainable
        if pytorch_models:
            ttk.Label(self.base_buttons_frame, text="🔵 Base Models (PyTorch)",
                     font=("Arial", 10, "bold"), foreground='#61dafb').pack(anchor=tk.W, padx=5, pady=(10, 5))

            for model_info in pytorch_models:
                base_name = model_info['name']
                self.levels_expanded[base_name] = self.levels_expanded.get(base_name, False)

                # wrapper holds both header row + expandable container so children
                # appear inline directly below their parent, not at section end
                wrapper = ttk.Frame(self.base_buttons_frame)
                wrapper.pack(fill=tk.X, padx=5, pady=2)

                row = ttk.Frame(wrapper)
                row.pack(fill=tk.X)

                arrow_btn = ttk.Button(row, text=('▼' if self.levels_expanded[base_name] else '▶'), width=2,
                                       command=lambda b=base_name: self._toggle_levels(b), style='Select.TButton')
                arrow_btn.pack(side=tk.LEFT, padx=(0, 5))

                size_text = f" • {model_info['size']}" if model_info.get("size") else ""
                ttk.Button(row, text=f"📦 {base_name}{size_text} • trainable",
                           command=lambda m=model_info: self.display_model_info_from_dict(m),
                           style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)

                # container is child of wrapper → packs inline after row
                container = ttk.Frame(wrapper)
                has_children = False

                # LoRA level children
                levels = []
                try:
                    levels = self._discover_levels_for_base(base_name)
                except Exception:
                    levels = []
                if levels:
                    has_children = True
                    for level in sorted(levels, key=lambda d: d.get('created', ''), reverse=True):
                        ttk.Button(container, text=f"   • {level.get('name', '(unnamed)')}",
                                   command=lambda b=base_name, lv=level: self.display_level_info(b, lv),
                                   style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)

                # GGUF export children — links CLI-exported GGUFs to their parent
                if model_info.get('path'):
                    _gguf_dir = Path(str(model_info['path'])) / 'exports' / 'gguf'
                    if _gguf_dir.exists():
                        for _gf in sorted(_gguf_dir.glob('*.gguf')):
                            has_children = True
                            try:
                                _sz = f"{_gf.stat().st_size // (1024 * 1024)}MB"
                            except Exception:
                                _sz = '?'
                            _gm = {'name': _gf.stem, 'type': 'gguf', 'path': _gf,
                                   'size': _sz, 'has_stats': False}
                            ttk.Button(container,
                                       text=f"   🟣 {_gf.stem}  •  {_sz}",
                                       command=lambda m=_gm: self.display_model_info(m),
                                       style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)

                self.levels_ui[base_name] = {'arrow': arrow_btn, 'container': container}

                # Hide arrow if no children; expand inline if already open
                if not has_children:
                    arrow_btn.pack_forget()
                elif self.levels_expanded[base_name]:
                    container.pack(fill=tk.X)

        # Display Arch Specs (config.json present but no trainable weights)
        if base_config_models:
            ttk.Label(self.base_buttons_frame, text="🧩 Arch Specs",
                     font=("Arial", 10, "bold"), foreground='#a8d8a8').pack(anchor=tk.W, padx=5, pady=(10, 5))
            for model_info in base_config_models:
                ttk.Button(self.base_buttons_frame,
                           text=f"🗂 {model_info['name']}  •  {model_info.get('size', '?')}",
                           command=lambda m=model_info: self.display_model_info_from_dict(m),
                           style='Select.TButton').pack(fill=tk.X, padx=5, pady=2)

        # Populate Ollama grouped by base (using level manifests if available)
        if ollama_models:
            grouped = self._group_ollama_by_base([m['name'] for m in ollama_models])
            for base_name, names in grouped.items():
                self.ollama_expanded[base_name] = self.ollama_expanded.get(base_name, False)
                # wrapper ensures expand is inline, not appended to section end
                wrapper = ttk.Frame(self.ollama_buttons_frame)
                wrapper.pack(fill=tk.X, padx=5, pady=2)
                row = ttk.Frame(wrapper)
                row.pack(fill=tk.X)
                arrow_btn = ttk.Button(row, text=('▼' if self.ollama_expanded[base_name] else '▶'), width=2,
                                       command=lambda b=base_name: self._toggle_ollama_group(b), style='Select.TButton')
                arrow_btn.pack(side=tk.LEFT, padx=(0, 5))
                ttk.Label(row, text=base_name, style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
                cont = ttk.Frame(wrapper)
                self.ollama_ui[base_name] = {'arrow': arrow_btn, 'container': cont}
                for n in names:
                    ttk.Button(cont, text=f"   🔶 {n} • inference-only",
                               command=lambda name=n: self.display_model_info({'name': name, 'type': 'ollama'}),
                               style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)
                if self.ollama_expanded[base_name] and names:
                    cont.pack(fill=tk.X)

        # Local GGUF files — only truly standalone ones (not sub-exports of a base model)
        _linked_gguf_paths = set()
        try:
            for _md in MODELS_DIR.iterdir():
                if _md.is_dir():
                    _gd = _md / 'exports' / 'gguf'
                    if _gd.exists():
                        for _gf in _gd.glob('*.gguf'):
                            _linked_gguf_paths.add(str(_gf))
        except Exception:
            pass
        standalone_gguf = [gm for gm in gguf_models
                           if str(gm.get('path', '')) not in _linked_gguf_paths]

        if standalone_gguf:
            ttk.Label(self.ollama_buttons_frame, text="🟣 Local GGUF (standalone)",
                     font=("Arial", 10, "bold"), foreground='#c792ea').pack(anchor=tk.W, padx=5, pady=(10, 3))
            for gm in standalone_gguf:
                gname = gm['name']
                gsize = gm.get('size', '?')
                gpath = gm.get('path')
                row = ttk.Frame(self.ollama_buttons_frame)
                row.pack(fill=tk.X, padx=5, pady=2)
                ttk.Button(row, text=f"🟣 {gname} • {gsize}",
                           command=lambda m=gm: self.display_model_info(m),
                           style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)
                def _load_ollama(path=gpath, name=gname):
                    self._load_gguf_via_ollama(path, name)
                ttk.Button(row, text="🔶 Load", width=7,
                           command=_load_ollama, style='Select.TButton').pack(side=tk.LEFT, padx=(4, 0))

        self.populate_morph_section()
        self.populate_providers_section()
        self._update_list_badges()

    def populate_morph_section(self):
        """Build the Morph specialist tree: variants/ sub-tree + Models/Morph* sub-tree."""
        import json as _j
        import re as _re

        for w in self.morph_buttons_frame.winfo_children():
            w.destroy()

        try:
            from config import DATA_DIR
            spawn_log = DATA_DIR / "pymanifest" / "variants" / "spawn_log.jsonl"
            variants_dir = DATA_DIR / "pymanifest" / "variants"
        except Exception:
            from pathlib import Path
            variants_dir = Path(__file__).parent.parent.parent / "pymanifest" / "variants"
            spawn_log = variants_dir / "spawn_log.jsonl"

        # ── Sub-section A: pymanifest/variants/ ────────────────────────────
        ttk.Label(self.morph_buttons_frame, text="📁 pymanifest/variants/",
                  font=("Arial", 9), foreground='#858585',
                  style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=(6, 0))
        ttk.Separator(self.morph_buttons_frame, orient='horizontal').pack(fill=tk.X, padx=8, pady=(2, 4))

        if not spawn_log.exists():
            ttk.Label(self.morph_buttons_frame, text="  No spawn_log.jsonl found.",
                      style='Config.TLabel').pack(anchor=tk.W, padx=12, pady=4)
        else:
            entries = []
            try:
                with open(spawn_log) as _f:
                    for line in _f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(_j.loads(line))
                            except Exception:
                                pass
            except Exception:
                entries = []

            # Deduplicate omegas: keep latest ts per name
            omega_by_name = {}
            for e in entries:
                if e.get('event') == 'omega_spawn' and e.get('outcome') == 'ok':
                    n = e['name']
                    if n not in omega_by_name or e['ts'] > omega_by_name[n]['ts']:
                        omega_by_name[n] = e

            def _ver(e):
                m = _re.search(r'v(\d+)', e.get('name', ''))
                return int(m.group(1)) if m else 0

            omegas = sorted(omega_by_name.values(), key=_ver, reverse=True)

            # Group alphas by parent omega name
            alphas_by_parent = {}
            for e in entries:
                if e.get('event') == 'alpha_spawn':
                    p = e.get('parent', 'unknown')
                    alphas_by_parent.setdefault(p, []).append(e)

            if not omegas:
                ttk.Label(self.morph_buttons_frame, text="  No Morph omegas found.",
                          style='Config.TLabel').pack(anchor=tk.W, padx=12, pady=4)
            else:
                for omega in omegas:
                    name = omega['name']
                    patterns = omega.get('pattern_count', 0)
                    children = alphas_by_parent.get(name, [])
                    self.morph_expanded[name] = self.morph_expanded.get(name, False)

                    # wrapper keeps alpha children inline under their omega
                    wrapper = ttk.Frame(self.morph_buttons_frame)
                    wrapper.pack(fill=tk.X, padx=5, pady=2)

                    row = ttk.Frame(wrapper)
                    row.pack(fill=tk.X)

                    arrow_btn = ttk.Button(row, text=('▼' if self.morph_expanded[name] else '▶'), width=2,
                                           command=lambda b=name: self._toggle_morph_omega(b),
                                           style='Select.TButton')
                    arrow_btn.pack(side=tk.LEFT, padx=(0, 5))

                    ttk.Button(row, text=f"⚡ {name}  •  {patterns:,} patterns",
                               command=lambda e=omega, vd=variants_dir: self.display_morph_model_info(e, vd),
                               style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)

                    # cont is child of wrapper → expands inline after row
                    cont = ttk.Frame(wrapper)
                    self.morph_ui[name] = {'arrow': arrow_btn, 'container': cont}

                    for alpha in sorted(children, key=lambda x: x.get('ts', ''), reverse=True):
                        domain = alpha.get('domain', '?')
                        apatterns = alpha.get('pattern_count', 0)
                        script = alpha.get('script', '')
                        profile_label = ''
                        try:
                            bj = variants_dir / f"build_{script.replace('.py', '')}.json"
                            if bj.exists():
                                bdata = _j.loads(bj.read_text())
                                pname = bdata.get('spawn_profile', {}).get('profile_name', '')
                                if pname:
                                    profile_label = f" [{pname}]"
                        except Exception:
                            pass
                        label = f"   🧬 {domain}{profile_label}  •  {apatterns:,} pts"
                        ttk.Button(cont, text=label,
                                   command=lambda e=alpha, vd=variants_dir: self.display_morph_model_info(e, vd),
                                   style='Select.TButton').pack(fill=tk.X, padx=25, pady=1)

                    if not children:
                        arrow_btn.pack_forget()
                    elif self.morph_expanded[name]:
                        cont.pack(fill=tk.X)

        # ── Sub-section B: Models/Morph* dirs ──────────────────────────────
        # (Alpha Lineage moved to LEFT Overview sub-tab — shown on alpha click)
        ttk.Separator(self.morph_buttons_frame, orient='horizontal').pack(fill=tk.X, padx=8, pady=(8, 2))
        ttk.Label(self.morph_buttons_frame, text="📁 Models/Morph*/",
                  font=("Arial", 9), foreground='#858585',
                  style='Config.TLabel').pack(anchor=tk.W, padx=8, pady=(0, 4))

        morph_model_dirs = []
        try:
            morph_model_dirs = sorted(
                [d for d in MODELS_DIR.iterdir()
                 if d.is_dir() and d.name.lower().startswith('morph')],
                key=lambda d: d.name
            )
        except Exception:
            pass

        if not morph_model_dirs:
            ttk.Label(self.morph_buttons_frame, text="  No Morph model dirs found.",
                      style='Config.TLabel').pack(anchor=tk.W, padx=12, pady=4)
        else:
            for morph_dir in morph_model_dirs:
                has_regex = (morph_dir / 'Morph_regex').exists()
                # Note: GGUFs shown under parent in Available Models — only show status indicator here
                has_gguf = (morph_dir / 'exports' / 'gguf').exists() and any(
                    (morph_dir / 'exports' / 'gguf').glob('*.gguf'))
                indicators = ''
                if has_gguf:
                    indicators += ' • gguf ✓'
                if has_regex:
                    indicators += ' • regex ✓'

                mkey = f"_mdir_{morph_dir.name}"
                self.morph_expanded[mkey] = self.morph_expanded.get(mkey, False)

                # wrapper keeps sub-items inline
                wrapper = ttk.Frame(self.morph_buttons_frame)
                wrapper.pack(fill=tk.X, padx=5, pady=2)

                row = ttk.Frame(wrapper)
                row.pack(fill=tk.X)

                arrow_btn = ttk.Button(row, text=('▼' if self.morph_expanded[mkey] else '▶'), width=2,
                                       command=lambda k=mkey: self._toggle_morph_omega(k),
                                       style='Select.TButton')
                arrow_btn.pack(side=tk.LEFT, padx=(0, 5))

                entry = {'event': 'morph_model', 'name': morph_dir.name,
                         'path': str(morph_dir), 'has_regex': has_regex, 'has_gguf': has_gguf}
                ttk.Button(row, text=f"🧠 {morph_dir.name}{indicators}",
                           command=lambda e=entry: self.display_morph_model_info(e),
                           style='Select.TButton').pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Sub-items: Morph state system info only (GGUFs are under parent in Available Models)
                cont = ttk.Frame(wrapper)
                self.morph_ui[mkey] = {'arrow': arrow_btn, 'container': cont}

                sub_items = 0

                # Runtime state snapshots
                if has_regex:
                    var_dir = morph_dir / 'Morph_regex' / 'variants'
                    if var_dir.exists():
                        vcount = len(list(var_dir.glob('morph_variant_*.json')))
                        if vcount:
                            ttk.Label(cont,
                                      text=f"   🧬 {vcount} runtime state snapshot{'s' if vcount != 1 else ''}",
                                      font=("Arial", 8), foreground='#82aaff',
                                      style='Config.TLabel').pack(anchor=tk.W, padx=28, pady=1)
                            sub_items += 1

                # Future: alpha specialist scripts spawned into this dir
                alpha_scripts = list(morph_dir.glob('specialist_*.py'))
                if alpha_scripts:
                    ttk.Label(cont,
                              text=f"   📜 {len(alpha_scripts)} alpha specialist{'s' if len(alpha_scripts) != 1 else ''}",
                              font=("Arial", 8), foreground='#4ec9b0',
                              style='Config.TLabel').pack(anchor=tk.W, padx=28, pady=1)
                    sub_items += 1

                if not sub_items:
                    arrow_btn.pack_forget()
                elif self.morph_expanded[mkey]:
                    cont.pack(fill=tk.X)

    def display_morph_model_info(self, entry, variants_dir=None):
        """Show Morph omega/alpha/model-dir info in the right panel."""
        import json as _j
        from pathlib import Path

        self.current_model_info = entry
        event = entry.get('event', '')
        is_omega = event == 'omega_spawn'
        is_morph_model = event == 'morph_model'
        is_morph_gguf = event == 'morph_gguf'

        if variants_dir is None:
            try:
                from config import DATA_DIR
                variants_dir = DATA_DIR / "pymanifest" / "variants"
            except Exception:
                variants_dir = Path(__file__).parent.parent.parent / "pymanifest" / "variants"

        # Clear overview tab
        for w in self.overview_tab_frame.winfo_children():
            w.destroy()

        # ── Branch: deployed Morph model directory ──────────────────────────
        if is_morph_model:
            model_path = Path(entry.get('path', ''))
            ttk.Label(self.overview_tab_frame,
                      text=f"🧠 {entry.get('name', '?')}",
                      font=("Arial", 13, "bold"),
                      style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=10, pady=(10, 5))

            info_frame = ttk.LabelFrame(self.overview_tab_frame, text="Model Directory", padding=10)
            info_frame.pack(fill=tk.X, padx=10, pady=5)

            # File inventory
            checks = [
                ("config.json", (model_path / 'config.json').exists()),
                ("pytorch_model/", (model_path / 'pytorch_model').exists()),
                ("Morph_regex/", (model_path / 'Morph_regex').exists()),
                ("exports/gguf/", (model_path / 'exports' / 'gguf').exists()),
            ]
            for fname, exists in checks:
                r = ttk.Frame(info_frame)
                r.pack(fill=tk.X, pady=1)
                ttk.Label(r, text="✓" if exists else "✗", width=3, style='Config.TLabel',
                          foreground='#4ec9b0' if exists else '#858585').pack(side=tk.LEFT)
                ttk.Label(r, text=fname, style='Config.TLabel').pack(side=tk.LEFT, padx=(2, 0))

            # GGUF exports list
            gguf_dir = model_path / 'exports' / 'gguf'
            if gguf_dir.exists():
                ggufs = list(gguf_dir.glob('*.gguf'))
                if ggufs:
                    gf = ttk.LabelFrame(self.overview_tab_frame, text=f"📦 GGUF Exports ({len(ggufs)})", padding=8)
                    gf.pack(fill=tk.X, padx=10, pady=5)
                    for g in sorted(ggufs):
                        try:
                            sz = f"{g.stat().st_size // (1024*1024)}MB"
                        except Exception:
                            sz = '?'
                        gr = ttk.Frame(gf)
                        gr.pack(fill=tk.X, pady=1)
                        ttk.Label(gr, text=f"🟣 {g.stem}  •  {sz}", style='Config.TLabel',
                                  foreground='#c792ea').pack(side=tk.LEFT)
                        ttk.Button(gr, text="Load in Chat",
                                   command=lambda p=g, n=g.stem: self._notify_chat_load_gguf(p, n),
                                   style='Small.TButton').pack(side=tk.RIGHT, padx=4)

            # Morph_regex runtime state snapshots
            var_dir = model_path / 'Morph_regex' / 'variants'
            if var_dir.exists():
                vfiles = sorted(var_dir.glob('morph_variant_*.json'))
                if vfiles:
                    # Load variant_registry for descriptions
                    registry = {}
                    try:
                        reg_file = model_path / 'Morph_regex' / 'variant_registry.json'
                        if reg_file.exists():
                            reg_data = _j.loads(reg_file.read_text())
                            for v in reg_data.get('variants', []):
                                registry[v['sha']] = v
                    except Exception:
                        pass

                    sf = ttk.LabelFrame(self.overview_tab_frame,
                                        text=f"🧬 Runtime State Snapshots ({len(vfiles)})", padding=8)
                    sf.pack(fill=tk.X, padx=10, pady=5)
                    ttk.Label(sf, text="Inference-time control packet captures — no weight changes",
                              font=("Arial", 8), foreground='#858585',
                              style='Config.TLabel').pack(anchor=tk.W, pady=(0, 4))
                    for vf in vfiles[:8]:  # cap display at 8
                        sha = vf.stem.replace('morph_variant_', '')[:16]
                        meta = registry.get(vf.stem.replace('morph_variant_', ''), {})
                        desc = meta.get('description', '')[:60] if meta else ''
                        ts_str = meta.get('timestamp', '')[:10] if meta else ''
                        lbl = f"  SHA:{sha}…  {ts_str}  {desc}"
                        ttk.Label(sf, text=lbl, font=("Arial", 8), foreground='#82aaff',
                                  style='Config.TLabel').pack(anchor=tk.W)
                    if len(vfiles) > 8:
                        ttk.Label(sf, text=f"  … and {len(vfiles)-8} more",
                                  font=("Arial", 8), foreground='#858585',
                                  style='Config.TLabel').pack(anchor=tk.W)

            # spawn_profile from variant_registry
            try:
                reg_file = model_path / 'Morph_regex' / 'variant_registry.json'
                if reg_file.exists():
                    spawn_prof = _j.loads(reg_file.read_text()).get('spawn_profile')
                    if spawn_prof:
                        pf = ttk.LabelFrame(self.overview_tab_frame, text="Spawn Profile", padding=8)
                        pf.pack(fill=tk.X, padx=10, pady=5)
                        for k, v in spawn_prof.items():
                            pr = ttk.Frame(pf)
                            pr.pack(fill=tk.X, pady=1)
                            ttk.Label(pr, text=f"{k}:", width=20, foreground='#858585',
                                      style='Config.TLabel').pack(side=tk.LEFT)
                            ttk.Label(pr, text=str(v), style='Config.TLabel').pack(side=tk.LEFT, padx=(4, 0))
            except Exception:
                pass

            # Open folder button
            btn_f = ttk.Frame(self.overview_tab_frame)
            btn_f.pack(anchor=tk.W, padx=10, pady=6)
            ttk.Button(btn_f, text="📂 Open Folder",
                       command=lambda p=model_path: __import__('subprocess').Popen(['xdg-open', str(p)]),
                       style='Select.TButton').pack(side=tk.LEFT)

            raw_text = _j.dumps(entry, indent=2)
            self.raw_model_info_text.config(state=tk.NORMAL)
            self.raw_model_info_text.delete(1.0, tk.END)
            self.raw_model_info_text.insert(1.0, raw_text)
            self.raw_model_info_text.config(state=tk.DISABLED)
            self.model_info_notebook.select(self.overview_tab_frame)
            return

        # ── Branch: Morph GGUF sub-item ────────────────────────────────────
        if is_morph_gguf:
            ttk.Label(self.overview_tab_frame,
                      text=f"🟣 {entry.get('name', '?')}",
                      font=("Arial", 13, "bold"),
                      style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=10, pady=(10, 5))
            gf_frame = ttk.LabelFrame(self.overview_tab_frame, text="GGUF Export", padding=10)
            gf_frame.pack(fill=tk.X, padx=10, pady=5)
            for lbl, val in [("File", entry.get('name', '?')),
                              ("Size", entry.get('size', '?')),
                              ("Parent", entry.get('parent_model', '?')),
                              ("Path", entry.get('path', '?'))]:
                r = ttk.Frame(gf_frame)
                r.pack(fill=tk.X, pady=2)
                ttk.Label(r, text=f"{lbl}:", width=10, foreground='#858585',
                          style='Config.TLabel').pack(side=tk.LEFT)
                ttk.Label(r, text=str(val), style='Config.TLabel',
                          wraplength=320, justify=tk.LEFT).pack(side=tk.LEFT, padx=(4, 0))
            btn_f = ttk.Frame(self.overview_tab_frame)
            btn_f.pack(anchor=tk.W, padx=10, pady=6)
            gpath = Path(entry.get('path', ''))
            gname = entry.get('name', '')
            ttk.Button(btn_f, text="Load in Chat",
                       command=lambda p=gpath, n=gname: self._notify_chat_load_gguf(p, n),
                       style='Action.TButton').pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(btn_f, text="Via Ollama",
                       command=lambda p=gpath, n=gname: self._load_gguf_via_ollama(p, n),
                       style='Select.TButton').pack(side=tk.LEFT)
            self.raw_model_info_text.config(state=tk.NORMAL)
            self.raw_model_info_text.delete(1.0, tk.END)
            self.raw_model_info_text.insert(1.0, _j.dumps(entry, indent=2))
            self.raw_model_info_text.config(state=tk.DISABLED)
            self.model_info_notebook.select(self.overview_tab_frame)
            return

        # ── Branch: omega / alpha specialist (spawn_log entries) ───────────
        script = entry.get('script', '')
        build_profile = {}
        if script:
            try:
                bj = variants_dir / f"build_{script.replace('.py', '')}.json"
                if bj.exists():
                    bdata = _j.loads(bj.read_text())
                    build_profile = bdata.get('spawn_profile', {})
            except Exception:
                pass

        if not is_omega:
            # Alpha clicked → rich overview with brain_map data in LEFT sub-tab
            self._populate_morph_overview(entry, variants_dir)
        else:
            # Omega: show spawn info + launch actions
            ttk.Label(self.overview_tab_frame,
                      text=f"⚡ Omega: {entry.get('name', '?')}",
                      font=("Arial", 13, "bold"),
                      style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=10, pady=(10, 5))

            info_frame = ttk.LabelFrame(self.overview_tab_frame, text="Spawn Info", padding=10)
            info_frame.pack(fill=tk.X, padx=10, pady=5)

            ts = entry.get('ts', '')[:19].replace('T', ' ')
            fields = [("Patterns", f"{entry.get('pattern_count', 0):,}"),
                      ("Spawned", ts),
                      ("Script", script or '?'),
                      ("Status", "✓ ok" if entry.get('outcome') == 'ok' else entry.get('outcome', '?'))]
            if build_profile.get('profile_name'):
                fields.append(("Profile", build_profile['profile_name']))

            for label, value in fields:
                r = ttk.Frame(info_frame)
                r.pack(fill=tk.X, pady=2)
                ttk.Label(r, text=f"{label}:", width=12, style='Config.TLabel',
                          foreground='#858585').pack(side=tk.LEFT)
                ttk.Label(r, text=str(value), style='Config.TLabel',
                          wraplength=300, justify=tk.LEFT).pack(side=tk.LEFT, padx=(5, 0))

            if script:
                act_frame = ttk.LabelFrame(self.overview_tab_frame, text="Launch", padding=8)
                act_frame.pack(fill=tk.X, padx=10, pady=5)
                ttk.Label(act_frame, text="Run omega CLI:", style='Config.TLabel').pack(anchor=tk.W)
                ttk.Label(act_frame, text=f"  cd variants && python3 {script}",
                          font=("Courier", 9), foreground='#4ec9b0').pack(anchor=tk.W, pady=(2, 4))
                ttk.Button(act_frame, text="⚡ Spawn Alpha…",
                           command=lambda e=entry, vd=variants_dir: self._show_spawn_alpha_dialog(e, vd),
                           style='Action.TButton').pack(anchor=tk.W)

        # Raw info tab — spawn_log entry + build JSON
        raw_parts = [_j.dumps(entry, indent=2)]
        if script:
            try:
                bj = variants_dir / f"build_{script.replace('.py', '')}.json"
                if bj.exists():
                    bdata = _j.loads(bj.read_text())
                    raw_parts.append(f"\n\n// build JSON:\n{_j.dumps(bdata, indent=2)}")
            except Exception:
                pass

        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        self.raw_model_info_text.insert(1.0, ''.join(raw_parts))
        self.raw_model_info_text.config(state=tk.DISABLED)

        # Populate Ω Inspector tab for omega/alpha entries
        self._populate_omega_inspector(entry, variants_dir)

        self.model_info_notebook.select(self.overview_tab_frame)

    def _populate_morph_overview(self, alpha_entry, variants_dir):
        """
        Populate LEFT Overview sub-tab with rich alpha data from brain_map files.
        Shows: arch summary, temporal hierarchy, domain grades, hooks, variant profile.
        Called when an alpha button is clicked in the RIGHT Morph Architects panel.
        """
        import json as _j2
        _GRADE_COLORS = {"A+": "#00ff88", "A": "#4ec9b0", "B": "#82aaff",
                         "C": "#e8b04b", "D": "#f78c6c", "F": "#ff5370"}

        frame = self.overview_tab_frame

        # Title row
        ttk.Label(frame,
                  text=f"🧬 Alpha: {alpha_entry.get('name', '?')}  ·  {alpha_entry.get('domain', '')}",
                  font=("Arial", 13, "bold"),
                  style='CategoryPanel.TLabel').pack(anchor=tk.W, padx=10, pady=(10, 4))

        # ── 1. Arch summary from spawn info ─────────────────────────────────
        info_frame = ttk.LabelFrame(frame, text="Spawn Info", padding=8)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        ts_str = alpha_entry.get('ts', '')[:19].replace('T', ' ')
        for lbl, val in [("Domain",   alpha_entry.get('domain', '?')),
                          ("Parent",   alpha_entry.get('parent', '?')),
                          ("Patterns", f"{alpha_entry.get('pattern_count', 0):,}"),
                          ("Spawned",  ts_str)]:
            r = ttk.Frame(info_frame)
            r.pack(fill=tk.X, pady=1)
            ttk.Label(r, text=f"{lbl}:", width=12, foreground='#858585',
                      style='Config.TLabel').pack(side=tk.LEFT)
            ttk.Label(r, text=str(val), style='Config.TLabel').pack(side=tk.LEFT, padx=(4, 0))

        # ── 2. Brain-map data ────────────────────────────────────────────────
        if MorphLineagePanel is None:
            ttk.Label(frame, text="(morph_lineage not available — brain_map data hidden)",
                      foreground='#858585', style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=4)
            return

        try:
            from tabs.models_tab.morph_lineage import load_brain_maps, build_lineage_tree
        except ImportError:
            try:
                from Data.tabs.models_tab.morph_lineage import load_brain_maps, build_lineage_tree
            except ImportError:
                ttk.Label(frame, text="(brain_map import failed)",
                          foreground='#858585', style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=4)
                return

        bmap_files = sorted(variants_dir.glob("brain_map_*.jsonl"), key=lambda p: p.stat().st_mtime)
        if not bmap_files:
            ttk.Label(frame, text="(no brain_map files found in variants/)",
                      foreground='#858585', style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=4)
            return

        # ── 2a. Temporal omega hierarchy (brain_map files sorted by mtime) ──
        hier_frame = ttk.LabelFrame(frame, text="Temporal Spawn Hierarchy", padding=8)
        hier_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        for i, bf in enumerate(bmap_files):
            is_latest = (i == len(bmap_files) - 1)
            marker = "▶" if is_latest else "·"
            color = "#a78bfa" if is_latest else "#858585"
            import datetime as _dt
            try:
                mtime = _dt.datetime.fromtimestamp(bf.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:
                mtime = "?"
            ttk.Label(hier_frame,
                      text=f"  {marker} {bf.name}  {mtime}",
                      foreground=color, style='Config.TLabel',
                      font=("Courier", 8)).pack(anchor=tk.W)

        # ── 2b. Domain grades from latest brain_map survivors ───────────────
        try:
            data = load_brain_maps(variants_dir)
            tree = build_lineage_tree(data)
        except Exception as _e:
            ttk.Label(frame, text=f"(brain_map load error: {_e})",
                      foreground='#ff5370', style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=4)
            return

        alpha_events = data.get("alpha_events", [])
        hook_events  = data.get("hook_events", [])

        # Collect all survivors from the latest generation
        all_gens = tree.get("all_gens", [])
        if all_gens:
            latest_gen = max(all_gens)
            gen_data = tree.get("gens", {}).get(latest_gen, {})
            survivors = [a for a in gen_data.get("alphas", []) if a.get("survived")]
        else:
            survivors = [a for a in alpha_events if a.get("survived")]

        if survivors:
            grades_frame = ttk.LabelFrame(frame, text="Domain Grades (Latest Gen Survivors)", padding=8)
            grades_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

            # Header
            hdr = ttk.Frame(grades_frame)
            hdr.pack(fill=tk.X)
            for col, w in [("Domain", 18), ("Grade", 7), ("Score", 8)]:
                ttk.Label(hdr, text=col, width=w, foreground='#858585',
                          style='Config.TLabel', font=("Arial", 8, "bold")).pack(side=tk.LEFT)

            # Aggregate: average score per domain across survivors
            domain_agg = {}
            for sv in survivors:
                dom_scores = sv.get("domain_scores", {})
                domains_detail = sv.get("domains", {})
                for dom, score in dom_scores.items():
                    if dom not in domain_agg:
                        domain_agg[dom] = []
                    domain_agg[dom].append((score, domains_detail.get(dom, {}).get("grade", "")))

            _GRADE_FROM_SCORE = [(0.97, "A+"), (0.90, "A"), (0.80, "B"),
                                  (0.68, "C"), (0.54, "D"), (0.0, "F")]
            for dom in sorted(domain_agg.keys()):
                scores_grades = domain_agg[dom]
                avg_score = sum(s for s, _ in scores_grades) / len(scores_grades)
                # Use stored grade if available, else derive
                stored_grade = scores_grades[0][1] if scores_grades[0][1] else ""
                if not stored_grade:
                    stored_grade = next((g for t, g in _GRADE_FROM_SCORE if avg_score >= t), "F")
                color = _GRADE_COLORS.get(stored_grade, "#cccccc")
                row = ttk.Frame(grades_frame)
                row.pack(fill=tk.X, pady=1)
                ttk.Label(row, text=dom, width=18, style='Config.TLabel').pack(side=tk.LEFT)
                ttk.Label(row, text=stored_grade, width=7, foreground=color,
                          style='Config.TLabel', font=("Arial", 9, "bold")).pack(side=tk.LEFT)
                ttk.Label(row, text=f"{avg_score:.3f}", width=8,
                          style='Config.TLabel').pack(side=tk.LEFT)

        # ── 2c. Hooks/mutations for this alpha's parent arch ─────────────────
        if hook_events:
            arch_name = alpha_entry.get('parent', alpha_entry.get('name', ''))
            relevant_hooks = [h for h in hook_events
                              if arch_name and (arch_name in str(h.get('hook', {}).get('from_arch', ''))
                                                or arch_name in str(h.get('hook', {}).get('to_arch', '')))]
            if not relevant_hooks:
                relevant_hooks = hook_events[-3:]  # fallback: show last 3 hooks

            if relevant_hooks:
                hook_frame = ttk.LabelFrame(frame, text="Hook / Mutation Lessons", padding=8)
                hook_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
                for hk in relevant_hooks[:4]:
                    obs_list = hk.get('hook', {}).get('observations', [])
                    if obs_list:
                        ttk.Label(hook_frame, text=f"  · {obs_list[0][:80]}",
                                  foreground='#82aaff', style='Config.TLabel',
                                  font=("Arial", 8)).pack(anchor=tk.W)

        # ── 2d. Variant profile (from config.py) ─────────────────────────────
        try:
            import sys as _sys
            _trainer_root = str(variants_dir.parent.parent.parent)
            if _trainer_root not in _sys.path:
                _sys.path.insert(0, _trainer_root)
            from Data.config import load_variant_profile
            profile = load_variant_profile("MorphAlpha-v3-768")
            if profile:
                prof_frame = ttk.LabelFrame(frame, text="Variant Profile", padding=8)
                prof_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
                cl = profile.get("class_level", "novice")
                ttk.Label(prof_frame, text=f"Class Level: {cl}",
                          foreground='#a78bfa', style='Config.TLabel',
                          font=("Arial", 9, "bold")).pack(anchor=tk.W)
                tool_prof = profile.get("tool_proficiency", {})
                if tool_prof:
                    ttk.Label(prof_frame, text="Tool Proficiency:",
                              foreground='#858585', style='Config.TLabel',
                              font=("Arial", 8, "bold")).pack(anchor=tk.W, pady=(4, 0))
                    for dom, gdata in sorted(tool_prof.items()):
                        grade = gdata.get("grade", "?")
                        score = gdata.get("score", 0.0)
                        color = _GRADE_COLORS.get(grade, "#cccccc")
                        pr = ttk.Frame(prof_frame)
                        pr.pack(fill=tk.X, pady=1)
                        ttk.Label(pr, text=dom, width=18,
                                  style='Config.TLabel').pack(side=tk.LEFT)
                        ttk.Label(pr, text=grade, width=5, foreground=color,
                                  style='Config.TLabel',
                                  font=("Arial", 9, "bold")).pack(side=tk.LEFT)
                        ttk.Label(pr, text=f"{score:.3f}",
                                  style='Config.TLabel').pack(side=tk.LEFT, padx=(4, 0))
        except Exception:
            pass

    def _toggle_morph_omega(self, name):
        """Expand/collapse an omega's alpha children in the Morph section."""
        try:
            ui = self.morph_ui.get(name)
            if not ui:
                return
            cont = ui['container']
            arrow = ui['arrow']
            expanded = bool(cont.winfo_ismapped())
            if expanded:
                cont.pack_forget()
                arrow.config(text='▶')
            else:
                cont.pack(fill=tk.X)
                arrow.config(text='▼')
            self.morph_expanded[name] = not expanded
        except Exception:
            pass

    def _toggle_list_section(self, key: str):
        """Collapse/expand one of the unified list pane sections (base/ollama/morph)."""
        try:
            ui = self.list_section_ui.get(key)
            if not ui:
                return
            cont = ui['content']
            arrow = ui['arrow']
            expanded = bool(cont.winfo_ismapped())
            if expanded:
                cont.pack_forget()
                arrow.config(text='▶')
            else:
                cont.pack(fill=tk.X)
                arrow.config(text='▼')
            self.list_sections[key] = not expanded
        except Exception:
            pass

    def _update_list_badges(self):
        """Refresh the count badges on each list section header."""
        try:
            for key, ui in self.list_section_ui.items():
                frame = ui['content']
                count = len(frame.winfo_children())
                badge = ui['badge']
                badge.config(text=f"({count})" if count else "")
        except Exception:
            pass

    def populate_providers_section(self):
        """Detect installed provider CLIs + list bundled Provisions packages."""
        import subprocess
        import json
        from pathlib import Path
        for w in self.providers_frame.winfo_children():
            w.destroy()

        # ── CLI Providers ─────────────────────────────────────────
        ttk.Label(self.providers_frame, text='CLI Providers',
                  font=('Arial', 9, 'bold'), foreground='#aaaaaa',
                  style='Config.TLabel').pack(anchor=tk.W, padx=6, pady=(6, 2))

        _cli_providers = [
            ('Claude Code', 'claude',  '#50fa7b'),
            ('Ollama',      'ollama',  '#e8b04b'),
            ('Python3',     'python3', '#61dafb'),
        ]
        for name, cmd, color in _cli_providers:
            try:
                r = subprocess.run(['which', cmd], capture_output=True, text=True, timeout=2)
                path = r.stdout.strip()
            except Exception:
                path = ''
            row = ttk.Frame(self.providers_frame)
            row.pack(fill=tk.X, padx=6, pady=1)
            if path:
                ttk.Label(row, text=f'● {name}', foreground=color,
                          font=('Arial', 9), style='Config.TLabel').pack(side=tk.LEFT)
                ttk.Label(row, text=path, foreground='#666666',
                          font=('Courier', 8), style='Config.TLabel').pack(side=tk.LEFT, padx=(6, 0))
            else:
                ttk.Label(row, text=f'○ {name}  —  not found', foreground='#444444',
                          font=('Arial', 9), style='Config.TLabel').pack(side=tk.LEFT)

        # ── Local site-packages ───────────────────────────────────
        _sp_dir = Path(__file__).parents[2] / 'custom_code_tab' / 'site-packages'
        if _sp_dir.exists():
            _sp_pkgs = [d.name for d in _sp_dir.iterdir() if d.is_dir()]
            ttk.Label(self.providers_frame, text='Local site-packages',
                      font=('Arial', 9, 'bold'), foreground='#aaaaaa',
                      style='Config.TLabel').pack(anchor=tk.W, padx=6, pady=(8, 2))
            row = ttk.Frame(self.providers_frame)
            row.pack(fill=tk.X, padx=6, pady=1)
            ttk.Label(row, text=f'📂 {str(_sp_dir)}', foreground='#666666',
                      font=('Courier', 7), style='Config.TLabel').pack(side=tk.LEFT)
            for pkg in sorted(_sp_pkgs):
                pr = ttk.Frame(self.providers_frame)
                pr.pack(fill=tk.X, padx=10, pady=0)
                ttk.Label(pr, text=f'● {pkg}', foreground='#61dafb',
                          font=('Arial', 8), style='Config.TLabel').pack(side=tk.LEFT)

        # ── Provisions (bundled wheels) ───────────────────────────
        ttk.Label(self.providers_frame, text='Provisions (bundled)',
                  font=('Arial', 9, 'bold'), foreground='#aaaaaa',
                  style='Config.TLabel').pack(anchor=tk.W, padx=6, pady=(8, 2))
        _cat_path = (Path(__file__).parents[2] /
                     'action_panel_tab' / 'babel_data' / 'inventory' / 'provisions_catalog.json')
        try:
            catalog = json.loads(_cat_path.read_text()) if _cat_path.exists() else {}
            pkgs = catalog.get('packages', [])
            for pkg in pkgs:
                status = pkg.get('install_status', 'bundled')
                icon = '✓' if status == 'installed' else '○'
                clr = '#55ff55' if status == 'installed' else '#555555'
                row = ttk.Frame(self.providers_frame)
                row.pack(fill=tk.X, padx=10, pady=0)
                ttk.Label(row, text=f'{icon} {pkg["name"]}  {pkg.get("version", "")}',
                          foreground=clr, font=('Arial', 8),
                          style='Config.TLabel').pack(side=tk.LEFT)
        except Exception as ex:
            ttk.Label(self.providers_frame,
                      text=f'(catalog unavailable: {ex})',
                      foreground='#555555', font=('Arial', 8),
                      style='Config.TLabel').pack(anchor=tk.W, padx=10)

    def _show_spawn_alpha_dialog(self, omega_entry, variants_dir=None):
        """Open dialog to spawn an alpha specialist from the selected omega."""
        import json as _j
        import threading
        import subprocess
        import sys
        from pathlib import Path
        from tkinter import scrolledtext as _st

        if variants_dir is None:
            try:
                from config import DATA_DIR
                variants_dir = DATA_DIR / "pymanifest" / "variants"
            except Exception:
                variants_dir = Path(__file__).parent.parent.parent / "pymanifest" / "variants"

        script_name = omega_entry.get('script', '')
        omega_name = omega_entry.get('name', 'omega')
        script_path = variants_dir / script_name

        # Collect known domains from spawn_log
        known_domains = ['planning', 'debug', 'analysis', 'neural_network', 'semantic_systems']
        try:
            spawn_log = variants_dir / "spawn_log.jsonl"
            if spawn_log.exists():
                with open(spawn_log) as _f:
                    for line in _f:
                        try:
                            rec = _j.loads(line.strip())
                            d = rec.get('domain')
                            if d and d not in known_domains:
                                known_domains.insert(0, d)
                        except Exception:
                            pass
        except Exception:
            pass

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Spawn Alpha from {omega_name}")
        dlg.geometry("500x400")
        dlg.resizable(False, False)
        dlg.grab_set()

        ttk.Label(dlg, text=f"⚡ Spawn Alpha from {omega_name}",
                  font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(padx=12, pady=(10, 6), anchor=tk.W)

        form = ttk.Frame(dlg)
        form.pack(fill=tk.X, padx=12)

        # Domain
        ttk.Label(form, text="Domain:", style='Config.TLabel', width=10).grid(row=0, column=0, sticky=tk.W, pady=3)
        domain_var = tk.StringVar(value=known_domains[0] if known_domains else 'planning')
        domain_cb = ttk.Combobox(form, textvariable=domain_var, values=known_domains, width=22)
        domain_cb.grid(row=0, column=1, sticky=tk.W, padx=4)

        # Profile
        profiles = ['hybrid', 'language', 'thinking', 'action', 'code']
        ttk.Label(form, text="Profile:", style='Config.TLabel', width=10).grid(row=1, column=0, sticky=tk.W, pady=3)
        profile_var = tk.StringVar(value='hybrid')
        profile_cb = ttk.Combobox(form, textvariable=profile_var, values=profiles, width=22)
        profile_cb.grid(row=1, column=1, sticky=tk.W, padx=4)

        # Output area
        out_frame = ttk.LabelFrame(dlg, text="Output", padding=6)
        out_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
        out_text = _st.ScrolledText(out_frame, height=8, font=("Courier", 9),
                                    state=tk.DISABLED, wrap=tk.WORD,
                                    bg='#1e1e1e', fg='#c8c8c8')
        out_text.pack(fill=tk.BOTH, expand=True)

        status_var = tk.StringVar(value="")
        ttk.Label(dlg, textvariable=status_var, style='Config.TLabel',
                  foreground='#4ec9b0').pack(padx=12, anchor=tk.W)

        # Buttons
        btn_row = ttk.Frame(dlg)
        btn_row.pack(fill=tk.X, padx=12, pady=(4, 10))
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy,
                   style='Select.TButton').pack(side=tk.RIGHT, padx=(4, 0))
        spawn_btn = ttk.Button(btn_row, text="⚡ Spawn", style='Action.TButton')
        spawn_btn.pack(side=tk.RIGHT)

        def _append(text):
            out_text.config(state=tk.NORMAL)
            out_text.insert(tk.END, text)
            out_text.see(tk.END)
            out_text.config(state=tk.DISABLED)

        def _do_spawn():
            spawn_btn.config(state=tk.DISABLED)
            domain = domain_var.get().strip() or 'planning'
            profile = profile_var.get().strip() or 'hybrid'
            status_var.set("Running…")
            _append(f"$ python3 {script_name}\n> spawn-alpha {domain} {profile}\n\n")
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                stdout, _ = proc.communicate(
                    input=f"spawn-alpha {domain} {profile}\nquit\n",
                    timeout=120
                )
                self.root.after(0, _append, stdout)
                if proc.returncode == 0:
                    self.root.after(0, status_var.set, "✓ Alpha spawned successfully")
                    self.root.after(0, self.populate_morph_section)
                    self.root.after(0, self._update_list_badges)
                else:
                    self.root.after(0, status_var.set, f"✗ Exit code {proc.returncode}")
            except subprocess.TimeoutExpired:
                proc.kill()
                self.root.after(0, status_var.set, "✗ Timed out after 120s")
                self.root.after(0, _append, "\n[TIMEOUT]\n")
            except Exception as ex:
                self.root.after(0, status_var.set, f"✗ Error: {ex}")
                self.root.after(0, _append, f"\n[ERROR] {ex}\n")
            finally:
                self.root.after(0, spawn_btn.config, {'state': tk.NORMAL})

        spawn_btn.config(command=lambda: threading.Thread(target=_do_spawn, daemon=True).start())

    def create_notes_panel(self, parent):
        """Create the notes panel for model-specific notes."""
        parent.columnconfigure(0, weight=3)  # Editor column
        parent.columnconfigure(1, weight=1)  # Notes list column
        parent.rowconfigure(1, weight=1)

        # Top controls
        controls_frame = ttk.Frame(parent)
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(controls_frame, text="Note Name:", style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        self.note_name_var = tk.StringVar()
        note_name_entry = ttk.Entry(controls_frame, textvariable=self.note_name_var, width=30)
        note_name_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text="💾 Save", command=self.save_note, style='Action.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(controls_frame, text="🗑️ Delete", command=self.delete_note, style='Action.TButton').pack(side=tk.LEFT, padx=2)

        # Notes text area (left side)
        self.notes_text = scrolledtext.ScrolledText(
            parent,
            width=60,
            height=20,
            font=("Arial", 10),
            wrap=tk.WORD,
            relief='flat',
            borderwidth=0,
            highlightthickness=0
        )
        self.notes_text.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        self.notes_text.config(background='#1e1e1e', foreground='#ffffff', insertbackground='#61dafb')

        # Notes list panel (right side)
        notes_list_frame = ttk.Frame(parent, style='Category.TFrame')
        notes_list_frame.grid(row=0, column=1, rowspan=2, sticky=tk.NSEW, padx=5, pady=5)
        notes_list_frame.columnconfigure(0, weight=1)
        notes_list_frame.rowconfigure(1, weight=1)

        ttk.Label(notes_list_frame, text="📝 Saved Notes", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').grid(row=0, column=0, pady=5, sticky=tk.W, padx=5)

        # Scrollable list of notes
        notes_list_canvas = tk.Canvas(notes_list_frame, bg="#2b2b2b", highlightthickness=0)
        notes_list_scrollbar = ttk.Scrollbar(notes_list_frame, orient="vertical", command=notes_list_canvas.yview)
        self.notes_list_buttons_frame = ttk.Frame(notes_list_canvas)

        self.notes_list_buttons_frame.bind(
            "<Configure>",
            lambda e: notes_list_canvas.configure(scrollregion=notes_list_canvas.bbox("all"))
        )

        self.notes_list_canvas_window_id = notes_list_canvas.create_window((0, 0), window=self.notes_list_buttons_frame, anchor="nw")
        notes_list_canvas.configure(yscrollcommand=notes_list_scrollbar.set)

        notes_list_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        notes_list_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        notes_list_canvas.bind("<Configure>", lambda e: notes_list_canvas.itemconfig(self.notes_list_canvas_window_id, width=e.width))

        # Store current model name for notes
        self.current_model_for_notes = None

    def create_evaluation_panel(self, parent):
        """Create the evaluation panel for running benchmarks."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1) # Row 1 for the output text area

        # --- Controls Frame ---
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        controls_frame.columnconfigure(1, weight=1)

        # Selected Model Display
        self.selected_model_label_eval = ttk.Label(
            controls_frame,
            text="Selected Model: None",
            font=("Arial", 10, "bold"),
            style='Config.TLabel',
            foreground='#61dafb'
        )
        self.selected_model_label_eval.grid(row=0, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)

        # Source display (Ollama/PyTorch)
        self.eval_source_label = ttk.Label(
            controls_frame,
            text="Source: Unknown",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#bbbbbb'
        )
        self.eval_source_label.grid(row=0, column=2, sticky=tk.E, padx=5, pady=5)

        # Test suite dropdown
        ttk.Label(controls_frame, text="Test Suite:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.test_suite_var = tk.StringVar()
        
        available_suites = get_test_suites()
        all_options = ["All"] + available_suites if available_suites else ["All"]

        self.test_suite_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.test_suite_var,
            values=all_options,
            state="readonly",
            width=20
        )
        self.test_suite_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.test_suite_combo.bind('<<ComboboxSelected>>', self._on_suite_changed)
        
        if available_suites:
            self.test_suite_combo.set(available_suites[0])
        else:
            self.test_suite_combo.set("All")

        # System Prompt controls
        self.use_system_prompt_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Use System Prompt",
            variable=self.use_system_prompt_var,
            command=self._toggle_system_prompt_controls,
            style='Config.TCheckbutton'
        ).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)

        self.system_prompt_var = tk.StringVar()
        self.system_prompt_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.system_prompt_var,
            values=list_system_prompts(),
            state="readonly",
            width=20
        )
        self.system_prompt_combo.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)
        self.system_prompt_combo.set("None") # Default
        self.system_prompt_combo.config(state=tk.DISABLED) # Initially disabled

        # Tool Schema controls
        self.use_tool_schema_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Use Tool Schema",
            variable=self.use_tool_schema_var,
            command=self._toggle_tool_schema_controls,
            style='Config.TCheckbutton'
        ).grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)

        self.tool_schema_var = tk.StringVar()
        self.tool_schema_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.tool_schema_var,
            values=list_tool_schemas(),
            state="readonly",
            width=20
        )
        self.tool_schema_combo.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)
        self.tool_schema_combo.set("None") # Default
        self.tool_schema_combo.config(state=tk.DISABLED) # Initially disabled

        # Baseline checkbox
        self.run_as_baseline_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Run as Pre-Training Baseline",
            variable=self.run_as_baseline_var,
            style='Config.TCheckbutton'
        ).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)

        # Regression check toggle (compare vs baseline after run)
        self.eval_regression_check_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Regression Check (compare vs baseline)",
            variable=self.eval_regression_check_var,
            style='Config.TCheckbutton'
        ).grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)

        # Quick regression toggle (sampled subset for faster checks)
        self.eval_quick_regression_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls_frame,
            text="Quick Regression (sample ~20%)",
            variable=self.eval_quick_regression_var,
            style='Config.TCheckbutton'
        ).grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)

        # Run button (row 4)
        self.run_eval_button = ttk.Button(
            controls_frame,
            text="▶️ Run Evaluation",
            command=self.run_evaluation,
            style='Action.TButton'
        )
        self.run_eval_button.grid(row=4, column=2, rowspan=3, sticky=tk.E, padx=10, pady=5)

        # Quick access: open Debug tab (manual only)
        ttk.Button(
            controls_frame,
            text="🐞 Debug",
            command=self._focus_settings_debug_tab,
            style='Select.TButton'
        ).grid(row=4, column=3, rowspan=3, sticky=tk.E, padx=(0,5), pady=5)

        # --- Output Frame ---
        output_frame = ttk.LabelFrame(parent, text="Live Output", style='TLabelframe')
        output_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.eval_output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Courier", 9),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.eval_output_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Initialize from Training tab selections if available
        try:
            tinst = self.get_training_tab()
            if tinst:
                # Mirror toggles
                if hasattr(tinst, 'runner_panel'):
                    self.use_system_prompt_var.set(bool(tinst.runner_panel.use_prompt_for_eval_var.get()))
                    self.use_tool_schema_var.set(bool(tinst.runner_panel.use_schema_for_eval_var.get()))
                # Mirror selected names
                psel = getattr(tinst, 'prompt_selected_var', None)
                ssel = getattr(tinst, 'schema_selected_var', None)
                if psel and psel.get():
                    self.system_prompt_combo.config(state='readonly')
                    self.system_prompt_combo.set(psel.get())
                if ssel and ssel.get():
                    self.tool_schema_combo.config(state='readonly')
                    self.tool_schema_combo.set(ssel.get())
        except Exception:
            pass

    def _toggle_system_prompt_controls(self):
        """Enables/disables the system prompt combobox based on checkbox state."""
        if self.use_system_prompt_var.get():
            self.system_prompt_combo.config(state="readonly")
            if not self.system_prompt_var.get() or self.system_prompt_var.get() == "None":
                available_prompts = list_system_prompts()
                if available_prompts:
                    self.system_prompt_combo.set(available_prompts[0])
                else:
                    self.system_prompt_combo.set("No prompts available")
        else:
            self.system_prompt_combo.config(state=tk.DISABLED)
            self.system_prompt_combo.set("None")

    def _toggle_tool_schema_controls(self):
        """Enables/disables the tool schema combobox based on checkbox state."""
        if self.use_tool_schema_var.get():
            self.tool_schema_combo.config(state="readonly")
            if not self.tool_schema_var.get() or self.tool_schema_var.get() == "None":
                available_schemas = list_tool_schemas()
                if available_schemas:
                    self.tool_schema_combo.set(available_schemas[0])
                else:
                    self.tool_schema_combo.set("No schemas available")
        else:
            self.tool_schema_combo.config(state=tk.DISABLED)
            self.tool_schema_combo.set("None")

    def run_evaluation(self):
        """
        Starts the evaluation process in a new thread to keep the GUI responsive.
        """
        suite = self.test_suite_var.get()
        # Prefer explicit selection for eval; fall back to current_model_info
        model = self.current_model_for_stats or ((self.current_model_info or {}).get('name'))
        # Resolve from own combos; if empty and toggles on, fall back to Training tab selections
        system_prompt_name = self.system_prompt_var.get() if self.use_system_prompt_var.get() else None
        tool_schema_name = self.tool_schema_var.get() if self.use_tool_schema_var.get() else None
        try:
            tinst = self.get_training_tab()
            if tinst:
                if self.use_system_prompt_var.get() and (not system_prompt_name or system_prompt_name == 'None'):
                    system_prompt_name = tinst.prompt_selected_var.get() or None
                if self.use_tool_schema_var.get() and (not tool_schema_name or tool_schema_name == 'None'):
                    tool_schema_name = tinst.schema_selected_var.get() or None
        except Exception:
            pass

        if not model:
            messagebox.showwarning("No Model Selected", "Please select a model from the list before running an evaluation.")
            return

        self.run_eval_button.config(state=tk.DISABLED)

        self.eval_output_text.config(state=tk.NORMAL)
        self.eval_output_text.delete(1.0, tk.END)
        self.eval_output_text.insert(tk.END, f"Starting evaluation for model: {model}\n")
        self.eval_output_text.insert(tk.END, f"Test Suite: {suite}\n")
        if system_prompt_name:
            self.eval_output_text.insert(tk.END, f"System Prompt: {system_prompt_name}\n")
        if tool_schema_name:
            self.eval_output_text.insert(tk.END, f"Tool Schema: {tool_schema_name}\n")
        self.eval_output_text.insert(tk.END, f"Scoring: {'schema-aware' if bool(tool_schema_name) else 'basic'}\n")
        if self.eval_regression_check_var.get():
            self.eval_output_text.insert(tk.END, "Regression Check: ON (will compare to baseline if available)\n")
        if self.eval_quick_regression_var.get():
            self.eval_output_text.insert(tk.END, "Quick Regression: ON (sampling ~20% of tests)\n")
        self.eval_output_text.insert(tk.END, "----------------------------------------\n")
        self.eval_output_text.config(state=tk.DISABLED)

        # Preflight: backend availability + inference model presence
        if not self._preflight_eval_backend(tool_schema_name):
            # Re-enable button on early exit
            try:
                self.run_eval_button.config(state=tk.NORMAL)
            except Exception:
                pass
            return

        # Ensure we have an inference (GGUF) model if evaluating a trainable base/level
        try:
            sel_type = (self.current_model_info or {}).get('type')
            if tool_schema_name and sel_type in ('pytorch', 'trained'):
                if not self._ensure_inference_model_for_eval(model):
                    # User cancelled or no compatible model selected/created; re-enable
                    try:
                        self.run_eval_button.config(state=tk.NORMAL)
                    except Exception:
                        pass
                    return
        except Exception:
            pass

        # Baseline conformer: if baseline selected, confirm before run
        baseline_flag = bool(self.run_as_baseline_var.get())
        if baseline_flag:
            if not self._confirm_baseline_creation(model, suite, system_prompt_name, tool_schema_name):
                baseline_flag = False

        # Stash context for potential auto-resume (e.g., after GGUF pull/create)
        try:
            self._last_eval_context = {
                'model': model,
                'suite': suite,
                'prompt': system_prompt_name,
                'schema': tool_schema_name,
                'baseline': baseline_flag,
            }
        except Exception:
            pass

        thread = threading.Thread(
            target=self._run_evaluation_thread,
            args=(model, suite, system_prompt_name, tool_schema_name, baseline_flag)
        )
        thread.daemon = True
        thread.start()

    def _preflight_eval_backend(self, tool_schema_name: str) -> bool:
        """Check that Ollama API is reachable and that an inference model exists when needed."""
        # Check Ollama API is reachable
        try:
            import requests
            r = requests.get("http://localhost:11434/api/version", timeout=2)
            if r.status_code != 200:
                raise RuntimeError(f"status {r.status_code}")
        except Exception:
            messagebox.showwarning(
                "Backend Unavailable",
                "Ollama API is not reachable at http://localhost:11434.\n"
                "Start it with 'ollama serve' or 'sudo systemctl start ollama', then retry."
            )
            return False
        # If schema-aware and selected model is trainable, ensure an inference (GGUF) model exists
        try:
            sel_type = (self.current_model_info or {}).get('type')
            if tool_schema_name and sel_type in ('pytorch', 'trained'):
                if not (self.ollama_models or []):
                    messagebox.showinfo(
                        "Export Required",
                        "No inference (GGUF) models are installed.\n"
                        "Export your base/level to GGUF first (Models → Levels: Export to GGUF), then run baseline."
                    )
                    return False
        except Exception:
            pass
        return True

    def _ensure_inference_model_for_eval(self, base_model_name: str) -> bool:
        """If evaluating a trainable model, ensure a GGUF (Ollama) model is available.
        If none compatible is found, offer to (1) create first baseline GGUF via Level export, or (2) pick an existing GGUF.
        If compatible GGUFs exist, prompt to select which to use; set override for this run.
        """
        # Refresh available Ollama models
        try:
            self.ollama_models = get_ollama_models()
        except Exception:
            pass
        # Build list of compatible GGUF names
        compat = []
        try:
            for m in (self.ollama_models or []):
                name = ''
                if isinstance(m, dict):
                    name = m.get('name') or ''
                elif isinstance(m, str):
                    name = m
                base = name.split(':', 1)[0].lower()
                bsel = base_model_name.lower().split(':', 1)[0]
                if (bsel in base) or (base in base_model_name.lower()):
                    compat.append(name)
        except Exception:
            compat = []

        if compat:
            # Let user pick which GGUF to use
            win = tk.Toplevel(self.root); win.title('Select Inference Model')
            frame = ttk.Frame(win); frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            ttk.Label(frame, text=f"Select GGUF model for evaluation of base '{base_model_name}':", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
            var = tk.StringVar(value=compat[0])
            combo = ttk.Combobox(frame, textvariable=var, values=compat, state='readonly', width=50)
            combo.grid(row=1, column=0, sticky=tk.EW, pady=6)
            decision = {"ok": False}
            def do_ok():
                self._eval_override_model_name = var.get()
                decision["ok"] = True
                win.destroy()
            def do_cancel():
                win.destroy()
            btns = ttk.Frame(frame); btns.grid(row=2, column=0, sticky=tk.E, pady=(6,0))
            ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Use This Model', command=do_ok, style='Action.TButton').pack(side=tk.RIGHT)
            win.grab_set(); win.wait_window()
            return bool(decision["ok"])  # proceed only if selected

        # No compatible GGUF; offer to create
        win = tk.Toplevel(self.root); win.title('No Export Detected')
        fr = ttk.Frame(win); fr.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        msg = (
            f"No inference (GGUF) export detected for base '{base_model_name}'.\n\n"
            "Create First Baseline GGUF now? This exports a Level to GGUF for evaluation.\n"
            "Alternatively, you can pick an existing GGUF model (if any) to evaluate."
        )
        txt = tk.Text(fr, height=6, width=64, bg='#ffffff', fg='#000000', font=('Arial', 9))
        txt.insert(1.0, msg); txt.config(state=tk.DISABLED)
        txt.grid(row=0, column=0, columnspan=3, sticky=tk.EW)
        decision = {"create": False, "pick": False}
        def do_create():
            decision["create"] = True; win.destroy()
        def do_pick():
            decision["pick"] = True; win.destroy()
        def do_cancel():
            win.destroy()
        btns = ttk.Frame(fr); btns.grid(row=1, column=0, columnspan=3, sticky=tk.E, pady=(8,0))
        ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Pick Existing', command=do_pick, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Create Baseline GGUF', command=do_create, style='Action.TButton').pack(side=tk.RIGHT)
        win.grab_set(); win.wait_window()

        if decision["pick"]:
            # Re-run compat detection (in case user added during session) and show dialog even if empty
            # Here, simply inform user to install GGUF via Ollama or Export Levels.
            messagebox.showinfo("Select GGUF", "Install or export a GGUF model, then select it under 'Ollama Models (GGUF)' to evaluate.")
            return False

        if decision["create"]:
            # Export BASE model to GGUF for first baseline
            try:
                base_path = self._find_base_path(base_model_name)
                if not base_path:
                    messagebox.showerror("Export Error", "Base model path not found.")
                    return False
                self._export_base_to_gguf_dialog(base_model_name, base_path)
                return False
            except Exception as e:
                messagebox.showerror("Export Error", f"Could not start baseline export: {e}")
                return False
        return False

    def _export_base_to_gguf_dialog(self, base_model_name: str, base_model_path):
        # Simple quant picker then spawn export thread
        win = tk.Toplevel(self.root); win.title('Export Base to GGUF')
        f = ttk.Frame(win); f.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ttk.Label(f, text=f"Export base '{base_model_name}' to GGUF", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W)
        ttk.Label(f, text="Quantization:", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(6,2))
        qvar = tk.StringVar(value='q4_k_m')
        combo = ttk.Combobox(f, textvariable=qvar, values=['q4_k_m','q5_k_m','q8_0'], state='readonly', width=12)
        combo.grid(row=1, column=1, sticky=tk.W)
        def go():
            win.destroy()
            self._run_export_base_to_gguf(base_model_path, qvar.get())
        ttk.Button(f, text='Start Export', command=go, style='Action.TButton').grid(row=2, column=1, sticky=tk.E, pady=(8,0))

    def _run_export_base_to_gguf(self, base_model_path, quant: str):
        # Spawn export_base_to_gguf.py in a thread
        self.append_runner_output(f"\n--- Exporting Base to GGUF ({quant}) ---\n")
        def worker():
            try:
                import subprocess, sys
                script = Path(__file__).parent.parent.parent / 'export_base_to_gguf.py'
                # Canonical output: Models/<model_name>/exports/gguf/
                base_name = Path(str(base_model_path)).name
                outdir = Path(str(base_model_path)) / 'exports' / 'gguf'
                outdir.mkdir(parents=True, exist_ok=True)
                cmd = [sys.executable, str(script), '--base', str(base_model_path), '--output', str(outdir), '--quant', quant]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                while True:
                    line = proc.stdout.readline()
                    if line == '' and proc.poll() is not None:
                        break
                    if line:
                        self.root.after(0, self.append_runner_output, line)
                rc = proc.poll()
                if rc == 0:
                    # Attempt to create an Ollama model referencing the GGUF
                    try:
                        gguf_path = outdir / f"{base_name}.{quant}.gguf"
                        modelfile = outdir / f"{base_name}.Modelfile"
                        mf = f"FROM {gguf_path}\nTEMPLATE \"{{{{ .Prompt }}}}\"\n"
                        modelfile.write_text(mf)
                        model_tag = f"{base_name}:latest"
                        create_cmd = ['ollama', 'create', model_tag, '-f', str(modelfile)]
                        self.root.after(0, self.append_runner_output, f"\n--- Creating Ollama model {model_tag} ---\n")
                        cproc = subprocess.Popen(create_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        while True:
                            l2 = cproc.stdout.readline()
                            if l2 == '' and cproc.poll() is not None:
                                break
                            if l2:
                                self.root.after(0, self.append_runner_output, l2)
                        crc = cproc.poll()
                        if crc == 0:
                            def _done():
                                messagebox.showinfo('Export', f'Base GGUF export complete and Ollama model created: {model_tag}. Starting baseline evaluation...')
                                # Refresh Ollama list so it appears
                                self.ollama_models = get_ollama_models()
                                self.populate_model_list()
                                self.append_runner_output("\n--- Export complete. Starting baseline evaluation with created model ---\n")
                                self._resume_eval_with_override(model_tag)
                            self.root.after(0, _done)
                        else:
                            self.root.after(0, lambda: messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model. You can create it manually.'))
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showwarning('Ollama', f'GGUF export complete, but Ollama create failed: {e}'))
                else:
                    # Offer to pull a prebuilt base from Ollama registry as fallback (GPU-less env)
                    try:
                        base_name = Path(str(base_model_path)).name
                        tag = self._guess_ollama_tag_from_base_name(base_name)
                        if tag and messagebox.askyesno('Export Failed', f'Base GGUF export failed (likely no GPU).\n\nPull prebuilt base from Ollama registry and use that instead?\n\nModel: {tag}'):
                            self.root.after(0, self.append_runner_output, f"\n--- Pulling Ollama model {tag} ---\n")
                            p2 = subprocess.Popen(['ollama','pull',tag], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                            while True:
                                l3 = p2.stdout.readline()
                                if l3 == '' and p2.poll() is not None:
                                    break
                                if l3:
                                    self.root.after(0, self.append_runner_output, l3)
                            prc = p2.poll()
                            if prc == 0:
                                def _done2():
                                    self.ollama_models = get_ollama_models(); self.populate_model_list()
                                    self.append_runner_output("\n--- Pull complete. Starting baseline evaluation with pulled model ---\n")
                                    self._resume_eval_with_override(tag)
                                self.root.after(0, _done2)
                            else:
                                self.root.after(0, lambda: messagebox.showerror('Ollama', f'Pull failed with code {prc}'))
                        else:
                            self.root.after(0, lambda: messagebox.showerror('Export Failed', f'Export failed with code {rc}'))
                    except Exception:
                        self.root.after(0, lambda: messagebox.showerror('Export Failed', f'Export failed with code {rc}'))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Export Error', str(e)))
        t = threading.Thread(target=worker); t.daemon=True; t.start()

    def _guess_ollama_tag_from_base_name(self, base_name: str) -> str:
        try:
            lower = base_name.lower()
            # Heuristic for Qwen2.5-Xb[-instruct]
            if 'qwen2.5' in lower:
                import re
                m = re.search(r'(\d+(?:\.\d+)?b)', lower)
                size = m.group(1) if m else None
                if size:
                    return f"qwen2.5:{size}"
                return 'qwen2.5:0.5b'
            return ''
        except Exception:
            return ''

    def _focus_settings_debug_tab(self):
        try:
            tabs = getattr(self, 'tab_instances', None)
            if not tabs or 'settings_tab' not in tabs:
                return
            settings_meta = tabs['settings_tab']
            settings_frame = settings_meta.get('frame')
            settings_inst = settings_meta.get('instance')
            if settings_frame and settings_frame.master:
                # Select the main Settings tab in the top-level notebook
                nb = settings_frame.master
                try:
                    nb.select(settings_frame)
                except Exception:
                    pass
            if settings_inst and hasattr(settings_inst, 'settings_notebook') and hasattr(settings_inst, 'debug_tab_frame'):
                try:
                    settings_inst.settings_notebook.select(settings_inst.debug_tab_frame)
                    # Ensure the debug combobox/poller shows Live Log
                    if hasattr(settings_inst, 'populate_log_file_combobox'):
                        settings_inst.populate_log_file_combobox()
                    if hasattr(settings_inst, 'start_log_polling'):
                        settings_inst.start_log_polling()
                except Exception:
                    pass
        except Exception:
            pass

    def _compute_skills_from_results(self, results: dict) -> dict:
        try:
            per = {}
            for r in results.get('results', []):
                s = r.get('skill') or 'Unknown'
                b = per.setdefault(s, {'passed': 0, 'total': 0})
                b['total'] += 1
                if r.get('passed'):
                    b['passed'] += 1
            if not per:
                return {}
            out = {}
            for s, c in per.items():
                passed = c['passed']; total = c['total']
                if passed == total:
                    status = 'Verified'
                elif passed > 0:
                    status = 'Partial'
                else:
                    status = 'Failed'
                out[s] = {'status': status, 'details': f'Passed {passed}/{total} tests.'}
            return out
        except Exception:
            return {}

    def _run_evaluation_thread(self, model_name, suite_name, system_prompt_name, tool_schema_name, baseline_flag):
        """
        This function runs in a background thread.
        """
        try:
            test_suite_dir = TRAINING_DATA_DIR / 'Test'
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            sample_fraction = 0.2 if self.eval_quick_regression_var.get() else None
            # Call run_benchmark with optional sampling (backwards compatible signature)
            try:
                inference_override = getattr(self, '_eval_override_model_name', None)
                results = engine.run_benchmark(model_name, suite_name, system_prompt_name, tool_schema_name, sample_fraction=sample_fraction, inference_override=inference_override)
            except TypeError:
                # Older engine signature: fallback to full run
                results = engine.run_benchmark(model_name, suite_name, system_prompt_name, tool_schema_name)

            # Save the report (baseline or evaluation)
            if "error" not in results:
                if baseline_flag:
                    mode = getattr(self, '_baseline_mode', 'overwrite')
                    delete_old = bool(getattr(self, '_baseline_delete_old', False))
                    try:
                        import time
                        from config import (
                            get_baseline_report_path,
                            update_model_baseline_index,
                            save_evaluation_report,
                            get_benchmarks_dir,
                        )
                        meta = results.get('metadata', {})
                        meta = {**meta, "timestamp": int(time.time())}
                        if mode == 'new':
                            # Save as a new timestamped baseline under benchmarks dir
                            bdir = get_benchmarks_dir()
                            clean = model_name.replace('/', '_').replace(':', '_')
                            ts = time.strftime('%Y%m%d_%H%M%S')
                            new_path = bdir / f"{clean}_baseline_{ts}.json"
                            # Reuse evaluation saver to get a proper JSON file
                            # (We want exact contents of results)
                            with open(new_path, 'w') as f:
                                import json as _json
                                _json.dump(results, f, indent=2)
                            # Optionally delete old canonical baseline
                            if delete_old:
                                try:
                                    oldp = get_baseline_report_path(model_name)
                                    if oldp.exists():
                                        oldp.unlink()
                                except Exception:
                                    pass
                            update_model_baseline_index(model_name, new_path, meta, set_active=True)
                        else:
                            # Overwrite canonical baseline path
                            from config import save_baseline_report
                            path = save_baseline_report(model_name, results)
                            update_model_baseline_index(model_name, path, meta, set_active=True)
                    except Exception:
                        pass
                else:
                    save_evaluation_report(model_name, results)
            
            # Optional regression comparison summary
            compare_summary = None
            try:
                if (not self.run_as_baseline_var.get()) and self.eval_regression_check_var.get():
                    baseline = load_baseline_report(model_name)
                    if baseline:
                        from config import get_regression_policy
                        policy = get_regression_policy() or {}
                        threshold = float(policy.get('alert_drop_percent', 5.0))
                        cmp = engine.compare_models(baseline, results, regression_threshold=threshold, improvement_threshold=threshold)
                        overall = cmp.get('overall', {})
                        delta = overall.get('delta', '+0.00%')
                        regs = ", ".join([r.get('skill','') for r in cmp.get('regressions', [])]) or 'None'
                        imps = ", ".join([r.get('skill','') for r in cmp.get('improvements', [])]) or 'None'
                        compare_summary = (
                            "\n--- Regression Check Summary ---\n"
                            f"Overall Δ vs baseline: {delta}\n"
                            f"Regressions (>{threshold:.1f}%): {regs}\n"
                            f"Improvements (>{threshold:.1f}%): {imps}\n"
                        )
            except Exception:
                pass

            # Persist skills summary
            try:
                from config import save_skills_file
                skills = self._compute_skills_from_results(results)
                meta = (results or {}).get('metadata', {})
                if skills:
                    save_skills_file(model_name, skills, meta)
            except Exception:
                pass

            # Schedule the UI update on the main thread
            self.root.after(0, self._update_ui_with_results, results)
            if compare_summary:
                self.root.after(0, self._append_eval_summary, compare_summary)
        except Exception as e:
            error_results = {"error": f"An unexpected error occurred in the evaluation thread: {e}"}
            self.root.after(0, self._update_ui_with_results, error_results)

    def _resume_eval_with_override(self, tag: str):
        try:
            ctx = getattr(self, '_last_eval_context', None)
            if not ctx:
                messagebox.showinfo('Evaluation', f'Installed {tag}. Select it under Ollama Models to evaluate.')
                return
            self._eval_override_model_name = tag
            self.append_runner_output("\n--- Continuing evaluation with inference model: %s ---\n" % tag)
            t = threading.Thread(target=self._run_evaluation_thread,
                                 args=(ctx['model'], ctx['suite'], ctx['prompt'], ctx['schema'], ctx['baseline']))
            t.daemon = True
            t.start()
        except Exception:
            pass

    def _update_ui_with_results(self, results):
        """
        This function is called by the main thread to safely update the UI.
        """
        self.eval_output_text.config(state=tk.NORMAL)
        results_str = json.dumps(results, indent=2)
        self.eval_output_text.insert(tk.END, "\n--- Benchmark Complete ---\n")
        self.eval_output_text.insert(tk.END, results_str)
        self.eval_output_text.see(tk.END)
        self.eval_output_text.config(state=tk.DISABLED)
        self.run_eval_button.config(state=tk.NORMAL)

        # Refresh Skills/Baselines/Compare lists for the current model so the user sees updates immediately
        try:
            if self.current_model_for_stats:
                self.populate_skills_display()
                self._refresh_baselines_panel()
                self._refresh_compare_lists()
        except Exception:
            pass

        # On errors, offer to open the Debug tab (no auto-routing)
        try:
            if isinstance(results, dict) and results.get('error'):
                if messagebox.askyesno("Open Debug?", "Evaluation reported an error. Open Debug tab to view live logs?"):
                    self._focus_settings_debug_tab()
        except Exception:
            pass
        
    def _append_eval_summary(self, text: str):
        try:
            self.eval_output_text.config(state=tk.NORMAL)
            self.eval_output_text.insert(tk.END, text)
            self.eval_output_text.see(tk.END)
            self.eval_output_text.config(state=tk.DISABLED)
        except Exception:
            pass

    # --- Baselines: UI and conformer ---
    def _confirm_baseline_creation(self, model_name: str, suite: str, prompt: str, schema: str) -> bool:
        try:
            import json
            from config import get_baseline_report_path
            path = get_baseline_report_path(model_name)
            exists = path.exists()
            win = tk.Toplevel(self.root)
            win.title("Baseline Options")
            frame = ttk.Frame(win)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            lines = [
                f"Model: {model_name}",
                f"Suite: {suite}",
                f"Schema: {schema or 'None'}",
                f"Prompt: {prompt or 'None'}",
                f"Sampling: {'ON' if self.eval_quick_regression_var.get() else 'OFF'}",
                "",
                ("A baseline already exists. You can overwrite it, or create a new one side-by-side and set it active." if exists else "This will create a new baseline for regression comparisons."),
                "Recommendation: Baselines should use full suites (no sampling)."
            ]
            txt = tk.Text(frame, height=8, width=60, bg='#ffffff', fg='#000000', font=('Arial', 9))
            txt.insert(1.0, "\n".join(lines))
            txt.config(state=tk.DISABLED)
            txt.grid(row=0, column=0, columnspan=2, sticky=tk.EW)

            # Options: Overwrite vs Create New, plus optional delete old
            mode_var = tk.StringVar(value=('overwrite' if exists else 'new'))
            opt_row = ttk.Frame(frame); opt_row.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(8,4))
            ttk.Radiobutton(opt_row, text='Overwrite existing baseline', value='overwrite', variable=mode_var).pack(side=tk.LEFT, padx=(0,12))
            ttk.Radiobutton(opt_row, text='Create new baseline (keep previous)', value='new', variable=mode_var).pack(side=tk.LEFT)
            del_var = tk.BooleanVar(value=False)
            if exists:
                del_row = ttk.Frame(frame); del_row.grid(row=2, column=0, columnspan=2, sticky=tk.W)
                ttk.Checkbutton(del_row, text='Also delete the old baseline file', variable=del_var).pack(side=tk.LEFT)

            decision = {"ok": False}
            def do_overwrite():
                mode_var.set('overwrite'); decision["ok"] = True; win.destroy()
            def do_create_new():
                mode_var.set('new'); decision["ok"] = True; win.destroy()
            def do_cancel():
                win.destroy()
            btns = ttk.Frame(frame)
            btns.grid(row=3, column=0, columnspan=2, sticky=tk.E, pady=(8,0))
            ttk.Button(btns, text='Cancel', command=do_cancel, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Create New', command=do_create_new, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
            ttk.Button(btns, text='Overwrite', command=do_overwrite, style='Action.TButton').pack(side=tk.RIGHT)
            win.grab_set()
            win.wait_window()
            if decision["ok"]:
                # Persist choice for the evaluation thread
                try:
                    self._baseline_mode = mode_var.get()  # 'overwrite' or 'new'
                    self._baseline_delete_old = bool(del_var.get()) if exists else False
                except Exception:
                    self._baseline_mode = 'overwrite'; self._baseline_delete_old = False
                return True
            return False
        except Exception:
            # On error, fail safe: do not create baseline automatically
            return False

    def create_baselines_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        ttk.Label(header, text="Baselines Manager", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text="🔄 Refresh", command=self._refresh_baselines_panel, style='Select.TButton').pack(side=tk.RIGHT)

        # Table area
        self.baselines_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        self.baselines_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.baselines_canvas.yview)
        self.baselines_content = ttk.Frame(self.baselines_canvas, style='Category.TFrame')
        self.baselines_content.bind("<Configure>", lambda e: self.baselines_canvas.configure(scrollregion=self.baselines_canvas.bbox("all")))
        self._bl_canvas_win = self.baselines_canvas.create_window((0, 0), window=self.baselines_content, anchor="nw")
        self.baselines_canvas.configure(yscrollcommand=self.baselines_scrollbar.set)
        self.baselines_canvas.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0,10))
        self.baselines_scrollbar.grid(row=1, column=1, sticky=tk.NS)
        self.baselines_canvas.bind("<Configure>", lambda e: self.baselines_canvas.itemconfig(self._bl_canvas_win, width=e.width))
        self._refresh_baselines_panel()

    def _refresh_baselines_panel(self):
        for w in self.baselines_content.winfo_children():
            w.destroy()
        # Load index
        try:
            from config import load_benchmarks_index
            idx = load_benchmarks_index() or {}
        except Exception:
            idx = {}
        model_name = self.current_model_for_stats or (self.current_model_info or {}).get('name')
        # Try exact, then tolerant match on key variants
        def _slug(s: str):
            import re
            return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
        clean = (model_name or '').replace('/', '_').replace(':', '_')
        models_idx = (idx.get('models') or {})
        matched_keys = []
        if model_name:
            want = _slug(model_name)
            for k in models_idx.keys():
                if want in _slug(k) or _slug(k) in want:
                    matched_keys.append(k)
        # Aggregate entries across all matched keys
        aggregate_entries = []
        active_entry = None
        for k in matched_keys or [clean]:
            md = models_idx.get(k) or {}
            for e in (md.get('entries') or []):
                aggregate_entries.append(e)
            if not active_entry and md.get('active'):
                active_entry = md.get('active')
        # Filter out entries that no longer exist on disk
        try:
            from pathlib import Path as _P
            aggregate_entries = [e for e in aggregate_entries if e.get('path') and _P(e.get('path')).exists()]
            if active_entry and (not active_entry.get('path') or not _P(active_entry.get('path')).exists()):
                active_entry = None
        except Exception:
            pass
        m = { 'entries': aggregate_entries, 'active': active_entry }
        matched_key = matched_keys[0] if matched_keys else clean
        row = 0
        header_txt = f"Model: {model_name or 'None selected'}"
        if m and matched_key != clean:
            header_txt += f"  (showing baselines saved under '{matched_key}')"
        ttk.Label(self.baselines_content, text=header_txt, style='Config.TLabel', font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, padx=5, pady=(5,3))
        row += 1
        if not m or not (m.get('entries') or m.get('active')):
            ttk.Label(self.baselines_content, text="No baselines found.", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            return
        # Auto-select the best baseline as active (highest pass_rate_percent)
        try:
            import json as _json
            from pathlib import Path as _P
            from config import save_benchmarks_index
            def _pct(v):
                try:
                    return float(str(v or '0').replace('%',''))
                except Exception:
                    return 0.0
            entries = m.get('entries') or []
            best = None; best_score = -1.0
            for e in entries:
                p = e.get('path');
                if not p or not _P(p).exists():
                    continue
                try:
                    with open(p,'r') as f:
                        data = _json.load(f)
                    score = _pct(data.get('pass_rate_percent'))
                    if score > best_score:
                        best_score = score; best = e
                except Exception:
                    continue
            active = m.get('active') or {}
            active_score = 0.0
            try:
                ap = active.get('path')
                if ap and _P(ap).exists():
                    with open(ap,'r') as f:
                        ad = _json.load(f)
                    active_score = _pct(ad.get('pass_rate_percent'))
            except Exception:
                pass
            # If best exists and is better than current active (or no active), set it active
            if best and (best_score > active_score or not active):
                m['active'] = best
                save_benchmarks_index(idx)
        except Exception:
            pass
        active = m.get('active') or {}
        ttk.Label(self.baselines_content, text=f"Active: suite={active.get('suite')} schema={active.get('schema')} prompt={active.get('prompt')}\n{active.get('path', '')}", style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=(0,8))
        row += 1
        for entry in (m.get('entries') or []):
            f = ttk.Frame(self.baselines_content, style='Category.TFrame')
            f.grid(row=row, column=0, sticky=tk.EW, padx=10, pady=2)
            ttk.Label(f, text=f"suite={entry.get('suite')} schema={entry.get('schema')} prompt={entry.get('prompt')}", style='Config.TLabel').pack(side=tk.LEFT)
            ttk.Button(f, text="View", style='Select.TButton', command=lambda p=entry.get('path'): self._view_json_file(p)).pack(side=tk.RIGHT, padx=3)
            ttk.Button(f, text="Set Active", style='Action.TButton', command=lambda e=entry, k=matched_key: self._set_active_baseline(k, e)).pack(side=tk.RIGHT, padx=3)
            row += 1

    def _set_active_baseline(self, clean_name: str, entry: dict):
        try:
            from config import load_benchmarks_index, save_benchmarks_index
            idx = load_benchmarks_index()
            m = idx.setdefault('models', {}).setdefault(clean_name, {"entries": [], "active": None})
            m['active'] = entry
            save_benchmarks_index(idx)
            self._refresh_baselines_panel()
            # Refresh skills to reflect new active baseline
            self.populate_skills_display()
        except Exception:
            pass

    def _view_json_file(self, path: str):
        try:
            import json
            p = Path(path)
            if not p.exists():
                messagebox.showerror("View", f"File not found: {path}")
                return
            with open(p, 'r') as f:
                data = json.load(f)
            self._show_json_window(f"Baseline: {p.name}", data)
        except Exception as e:
            messagebox.showerror("View", f"Failed to open: {e}")

    # --- Suite recommendation conformer ---
    def _on_suite_changed(self, *_):
        try:
            suite = self.test_suite_var.get()
            if not suite or suite == 'All':
                return
            if not hasattr(self, 'eval_suite_reco_suppressed'):
                self.eval_suite_reco_suppressed = {}
            if self.eval_suite_reco_suppressed.get(suite):
                return
            prompt, schema_options, default_schema = self._recommend_prompt_schema_for_suite(suite)
            if not prompt and not schema_options:
                return
            self._show_suite_recommendation_dialog(suite, prompt, schema_options, default_schema)
        except Exception:
            pass

    def _recommend_prompt_schema_for_suite(self, suite: str):
        # Return (prompt_name or None, [schema options], default_schema)
        suite_lower = suite.lower()
        prompt = None
        options = []
        default_schema = None
        # Recommend based on simple mapping
        if 'orchestration' in suite_lower:
            prompt = 'Revised_tools'
            options = ['think_time']
            default_schema = 'think_time'
        elif 'tools' in suite_lower:
            prompt = 'Revised_tools'
            options = ['json_calls_full', 'file_ops_compat', 'search_ops']
            default_schema = 'json_calls_full'
        elif 'errors' in suite_lower:
            prompt = 'Revised_tools'
            options = ['json_calls_full', 'file_ops_compat']
            default_schema = 'json_calls_full'
        return (prompt, options, default_schema)

    def _show_suite_recommendation_dialog(self, suite: str, prompt: str, schema_options: list, default_schema: str):
        win = tk.Toplevel(self.root)
        win.title('Apply Recommended Prompt/Schema?')
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        msg = f"This suite has recommended settings:\n\nSuite: {suite}\n"
        if prompt:
            msg += f"Prompt: '{prompt}'\n"
        if schema_options:
            msg += f"Schema: {', '.join(schema_options)}\n\nApply these for this evaluation?"
        else:
            msg += "\nApply the recommended prompt?"
        info = tk.Text(frame, height=5, width=60, bg='#ffffff', fg='#000000', font=('Arial', 9))
        info.insert(1.0, msg)
        info.config(state=tk.DISABLED)
        info.grid(row=0, column=0, columnspan=3, sticky=tk.EW)

        chosen_schema = tk.StringVar(value=default_schema or (schema_options[0] if schema_options else ''))
        if schema_options and len(schema_options) > 1:
            ttk.Label(frame, text='Schema:', font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=(6,2))
            schema_combo = ttk.Combobox(frame, textvariable=chosen_schema, values=schema_options, state='readonly', width=24)
            schema_combo.grid(row=1, column=1, sticky=tk.W, pady=(6,2))

        def apply_and_close():
            try:
                # Apply prompt
                if prompt:
                    self.use_system_prompt_var.set(True)
                    self.system_prompt_combo.config(state='readonly')
                    # Verify prompt exists; fall back silently if not
                    from config import list_system_prompts
                    if prompt in list_system_prompts():
                        self.system_prompt_combo.set(prompt)
                # Apply schema
                if schema_options:
                    pick = chosen_schema.get() or default_schema or schema_options[0]
                    from config import list_tool_schemas
                    if pick in list_tool_schemas():
                        self.use_tool_schema_var.set(True)
                        self.tool_schema_combo.config(state='readonly')
                        self.tool_schema_combo.set(pick)
            except Exception:
                pass
            win.destroy()

        def dismiss():
            win.destroy()

        def dont_ask():
            if not hasattr(self, 'eval_suite_reco_suppressed'):
                self.eval_suite_reco_suppressed = {}
            self.eval_suite_reco_suppressed[suite] = True
            win.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=2, column=0, columnspan=3, sticky=tk.E, pady=(8,0))
        ttk.Button(btns, text='Don\'t ask again', command=dont_ask, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Skip', command=dismiss, style='Select.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(btns, text='Apply', command=apply_and_close, style='Action.TButton').pack(side=tk.RIGHT)

    def get_training_tab(self):
        try:
            tabs = getattr(self, 'tab_instances', None)
            if tabs and 'training_tab' in tabs:
                return tabs['training_tab']['instance']
        except Exception:
            pass
        return None

    def create_compare_panel(self, parent):
        """Create the comparison panel for comparing two models' latest evaluations."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Controls
        controls = ttk.Frame(parent, style='Category.TFrame')
        controls.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Parent Model:", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Label(controls, text="Advanced: Other Model (latest eval)", style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.compare_model_a_var = tk.StringVar()
        self.compare_model_b_var = tk.StringVar()

        # Populate only models that have at least one evaluation report or a baseline
        names = self._filtered_models_for_compare()

        self.compare_model_a_combo = ttk.Combobox(controls, textvariable=self.compare_model_a_var, values=names, state="readonly", width=40)
        self.compare_model_b_combo = ttk.Combobox(controls, textvariable=self.compare_model_b_var, values=names, state="readonly", width=40)
        self.compare_model_a_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)
        self.compare_model_b_combo.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)

        self.compare_other_btn = ttk.Button(controls, text="🔍 Compare (Other Model)", command=self.run_compare_models, style='Action.TButton')
        self.compare_other_btn.grid(row=0, column=2, rowspan=2, sticky=tk.E, padx=10, pady=5)
        ttk.Button(controls, text="🔄 Refresh", command=self._refresh_compare_lists, style='Select.TButton').grid(row=0, column=3, rowspan=2, sticky=tk.E, padx=5, pady=5)

        # Baseline compare (Latest vs Baseline)
        baseline_frame = ttk.Frame(parent, style='Category.TFrame')
        baseline_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0,8))
        ttk.Label(baseline_frame, text="Reference Baseline (Parent):", style='Config.TLabel').pack(side=tk.LEFT, padx=5)
        self.compare_baseline_var = tk.StringVar()
        self.compare_baseline_combo = ttk.Combobox(baseline_frame, textvariable=self.compare_baseline_var, values=[], state='readonly', width=50)
        self.compare_baseline_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(baseline_frame, text="Compare Latest Eval vs Reference", command=self.run_compare_latest_vs_baseline, style='Select.TButton').pack(side=tk.RIGHT, padx=5)

        # Update baseline list when Parent changes
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._populate_compare_baselines)
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._populate_compare_baseline_pairs)
        # Update Other Model compare button enabled/disabled
        self.compare_model_a_combo.bind('<<ComboboxSelected>>', self._update_compare_other_state)
        self.compare_model_b_combo.bind('<<ComboboxSelected>>', self._update_compare_other_state)

        # Baseline vs Baseline (same parent: Model A)
        bb_frame = ttk.Frame(parent, style='Category.TFrame')
        bb_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0,8))
        ttk.Label(bb_frame, text="Reference vs Target (Parent Baselines):", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5)
        self.compare_baseline_a_var = tk.StringVar()
        self.compare_baseline_b_var = tk.StringVar()
        self.compare_baseline_a_combo = ttk.Combobox(bb_frame, textvariable=self.compare_baseline_a_var, values=[], state='readonly', width=45)
        self.compare_baseline_b_combo = ttk.Combobox(bb_frame, textvariable=self.compare_baseline_b_var, values=[], state='readonly', width=45)
        self.compare_baseline_a_combo.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.compare_baseline_b_combo.grid(row=0, column=2, sticky=tk.EW, padx=5)
        ttk.Button(bb_frame, text="Compare Baselines", command=self.run_compare_baseline_vs_baseline, style='Select.TButton').grid(row=0, column=3, sticky=tk.E, padx=5)
        # (bindings added above)

        # Output
        output_frame = ttk.LabelFrame(parent, text="Comparison Result", style='TLabelframe')
        output_frame.grid(row=3, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.compare_output_text = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Courier", 9),
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.compare_output_text.grid(row=0, column=0, sticky=tk.NSEW)

        # Initialize Parent selection and baseline lists on open
        try:
            preferred = (self.current_model_info or {}).get('name')
            if preferred and preferred in names:
                self.compare_model_a_var.set(preferred)
                self.compare_model_a_combo.set(preferred)
            elif names:
                self.compare_model_a_var.set(names[0])
                self.compare_model_a_combo.set(names[0])
            self._populate_compare_baselines()
            self._populate_compare_baseline_pairs()
            self._update_compare_other_state()
        except Exception:
            pass

        # Actions row under output: generate suggestions / save examples
        actions_row = ttk.Frame(parent, style='Category.TFrame')
        actions_row.grid(row=4, column=0, sticky=tk.EW, padx=10, pady=(0,10))
        ttk.Button(actions_row, text='🧠 Generate Training Suggestions', command=self._compare_generate_suggestions, style='Select.TButton').pack(side=tk.LEFT)
        ttk.Button(actions_row, text='💾 Save Example Stubs', command=self._compare_save_examples, style='Select.TButton').pack(side=tk.LEFT, padx=6)

    def _update_compare_other_state(self, *_):
        """Enable 'Compare (Other Model)' only when both selections have a latest evaluation report."""
        try:
            from config import load_latest_evaluation_report
            a = self.compare_model_a_var.get() or ''
            b = self.compare_model_b_var.get() or ''
            has_a = bool(load_latest_evaluation_report(a))
            has_b = bool(load_latest_evaluation_report(b))
            state = tk.NORMAL if (has_a and has_b) else tk.DISABLED
            self.compare_other_btn.config(state=state)
        except Exception:
            try:
                self.compare_other_btn.config(state=tk.DISABLED)
            except Exception:
                pass

    def _refresh_compare_lists(self):
        try:
            names = self._filtered_models_for_compare()
            self.compare_model_a_combo['values'] = names
            self.compare_model_b_combo['values'] = names
            # Reset baseline list for Model A based on any new baselines
            self._populate_compare_baselines()
        except Exception:
            pass

    def _filtered_models_for_compare(self):
        try:
            from config import list_evaluation_reports, load_baseline_report
            names = []
            for m in get_all_trained_models():
                name = m.get('name')
                if not name:
                    continue
                # Only list trainable parents (pytorch/trained) to avoid Ollama tag duplicates
                if (m.get('type') not in ('pytorch', 'trained')):
                    continue
                has_eval = bool(list_evaluation_reports(name))
                has_base = bool(load_baseline_report(name))
                if has_eval or has_base:
                    names.append(name)
            # Deduplicate by case/format variations
            seen = set(); out = []
            for n in names:
                key = n.lower().replace(':','_')
                if key not in seen:
                    seen.add(key); out.append(n)
            return sorted(out)
        except Exception:
            # Fallback to previous behavior if filtering fails
            return [m["name"] for m in get_all_trained_models()]

    def _collect_parent_baselines(self, parent_name: str):
        """Return human‑readable labels for all baselines belonging to the parent (tolerant of name variants)."""
        try:
            import re
            from config import load_benchmarks_index
            idx = load_benchmarks_index() or {}
            models = (idx.get('models') or {})
            def slug(s: str):
                return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
            pslug = slug(parent_name)
            labels = []
            for key, data in models.items():
                if not isinstance(data, dict):
                    continue
                kslug = slug(key)
                if pslug and (pslug == kslug or pslug in kslug or kslug in pslug):
                    for e in (data.get('entries') or []):
                        labels.append(self._format_baseline_label(e))
            return labels
        except Exception:
            return []

    def _format_baseline_label(self, entry: dict) -> str:
        """Build a readable label: YYYY‑MM‑DD HH:MM | pass 50.00% | suite | schema | prompt -> path"""
        try:
            import json, time
            p = entry.get('path','')
            ts = entry.get('timestamp')
            dt = time.strftime('%Y-%m-%d %H:%M', time.localtime(ts)) if ts else 'Unknown time'
            pr = 'n/a'
            if p:
                from pathlib import Path
                fp = Path(p)
                if fp.exists():
                    with open(fp,'r') as f:
                        data = json.load(f)
                        pr = data.get('pass_rate_percent') or 'n/a'
            suite = entry.get('suite') or 'All'
            schema = entry.get('schema') or 'None'
            prompt = entry.get('prompt') or 'None'
            return f"{dt} | pass {pr} | {suite} | {schema} | {prompt} -> {p}"
        except Exception:
            return f"{entry.get('suite') or 'All'} | {entry.get('schema') or 'None'} | {entry.get('prompt') or 'None'} -> {entry.get('path','')}"

    def run_compare_models(self):
        a = self.compare_model_a_var.get()
        b = self.compare_model_b_var.get()
        if not a or not b:
            messagebox.showwarning("Select Models", "Please select both Model A and Model B.")
            return

        a_report = load_latest_evaluation_report(a)
        b_report = load_latest_evaluation_report(b)
        if not a_report or not b_report:
            messagebox.showwarning("Missing Reports", "One or both models lack evaluation reports.")
            return

        # Use engine's compare to compute diffs
        try:
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(a_report, b_report)
            # Store context for suggestions
            self._last_comparison_ctx = {'baseline': a_report, 'new': b_report, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare: {e}")

    def _populate_compare_baselines(self, *_):
        try:
            mname = self.compare_model_a_var.get()
            labels = self._collect_parent_baselines(mname)
            # Build mapping label -> path for reliable resolution
            self._baseline_label_map = {}
            for lab in labels:
                try:
                    path = lab.split('->',1)[1].strip()
                except Exception:
                    path = ''
                self._baseline_label_map[lab] = path
            self.compare_baseline_combo['values'] = labels
            if labels:
                self.compare_baseline_combo.set(labels[0])
            else:
                self.compare_baseline_combo.set('')
        except Exception:
            self.compare_baseline_combo['values'] = []
            self.compare_baseline_combo.set('')

    def _populate_compare_baseline_pairs(self, *_):
        try:
            mname = self.compare_model_a_var.get()
            labels = self._collect_parent_baselines(mname)
            # Build mapping label -> path for reliable resolution
            self._baseline_pair_label_map = {}
            for lab in labels:
                try:
                    path = lab.split('->',1)[1].strip()
                except Exception:
                    path = ''
                self._baseline_pair_label_map[lab] = path
            self.compare_baseline_a_combo['values'] = labels
            self.compare_baseline_b_combo['values'] = labels
            # Preselect two different entries if available
            if len(labels) >= 1:
                self.compare_baseline_a_combo.set(labels[0])
            if len(labels) >= 2:
                self.compare_baseline_b_combo.set(labels[1])
        except Exception:
            self.compare_baseline_a_combo['values'] = []
            self.compare_baseline_b_combo['values'] = []
            self.compare_baseline_a_combo.set('')
            self.compare_baseline_b_combo.set('')

    def run_compare_latest_vs_baseline(self):
        a = self.compare_model_a_var.get()
        if not a:
            messagebox.showwarning("Select Model", "Please select Model A.")
            return
        label = self.compare_baseline_var.get()
        if not label:
            messagebox.showwarning("Select Baseline", "Please select a baseline entry for Model A.")
            return
        # Resolve via mapping (fallback to split)
        path = ''
        try:
            path = (self._baseline_label_map or {}).get(label, '')
        except Exception:
            path = ''
        if not path and '->' in label:
            path = label.split('->',1)[1].strip()
        try:
            import json
            from pathlib import Path
            from config import load_latest_evaluation_report
            latest = load_latest_evaluation_report(a)
            if not latest:
                messagebox.showwarning("Missing Report", "Model A has no latest evaluation report.")
                return
            p = Path(path)
            if not p.exists():
                messagebox.showwarning("Missing Baseline", "Selected baseline file not found on disk.")
                return
            with open(p, 'r') as f:
                baseline = json.load(f)
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(baseline, latest)
            self._last_comparison_ctx = {'baseline': baseline, 'new': latest, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
            # Offer to save latest eval as new baseline if better
            try:
                def _pct(s):
                    try: return float((s or '0').replace('%',''))
                    except: return 0.0
                b_overall = _pct((baseline or {}).get('pass_rate_percent'))
                n_overall = _pct((latest or {}).get('pass_rate_percent'))
                if n_overall > b_overall and messagebox.askyesno('Set Active Baseline?', f'Latest evaluation ({n_overall:.2f}%) is higher than the reference baseline ({b_overall:.2f}%).\n\nSave latest eval as a new baseline and set it active?'):
                    from config import save_baseline_report, update_model_baseline_index
                    import time
                    model_name = self.compare_model_a_var.get()
                    path = save_baseline_report(model_name, latest)
                    meta = (latest.get('metadata') or {})
                    meta = {**meta, 'timestamp': int(time.time())}
                    update_model_baseline_index(model_name, path, meta, set_active=True)
                    self._refresh_baselines_panel()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare: {e}")

    def run_compare_baseline_vs_baseline(self):
        a = self.compare_model_a_var.get()
        if not a:
            messagebox.showwarning("Select Model", "Please select Model A.")
            return
        la = self.compare_baseline_a_var.get() or ''
        lb = self.compare_baseline_b_var.get() or ''
        if not la or not lb:
            messagebox.showwarning("Select Baselines", "Please select two baseline entries for Model A.")
            return
        # Resolve via mapping (fallback to split)
        pa = (getattr(self, '_baseline_pair_label_map', {}) or {}).get(la, '')
        pb = (getattr(self, '_baseline_pair_label_map', {}) or {}).get(lb, '')
        if (not pa and '->' in la): pa = la.split('->',1)[1].strip()
        if (not pb and '->' in lb): pb = lb.split('->',1)[1].strip()
        try:
            import json
            from pathlib import Path
            pa = Path(pa); pb = Path(pb)
            if not pa.exists() or not pb.exists():
                messagebox.showwarning("Missing Baseline", "One or both selected baseline files were not found.")
                return
            with open(pa,'r') as fa: ba = json.load(fa)
            with open(pb,'r') as fb: bb = json.load(fb)
            test_suite_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Test"
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            comparison = engine.compare_models(ba, bb)
            self._last_comparison_ctx = {'baseline': ba, 'new': bb, 'comparison': comparison}
            self.compare_output_text.config(state=tk.NORMAL)
            self.compare_output_text.delete(1.0, tk.END)
            self.compare_output_text.insert(tk.END, json.dumps(comparison, indent=2))
            self.compare_output_text.config(state=tk.DISABLED)
            # Offer to set Target baseline active if better
            try:
                def _pct(s):
                    try: return float((s or '0').replace('%',''))
                    except: return 0.0
                b_overall = _pct((ba or {}).get('pass_rate_percent'))
                n_overall = _pct((bb or {}).get('pass_rate_percent'))
                if n_overall > b_overall:
                    parent = self.compare_model_a_var.get() or ''
                    if messagebox.askyesno('Set Active Baseline?', f'Target baseline ({n_overall:.2f}%) is higher than Reference ({b_overall:.2f}%).\n\nSet Target as active for {parent}?'):
                        from config import load_benchmarks_index, save_benchmarks_index
                        clean = parent.replace('/','_').replace(':','_')
                        idx = load_benchmarks_index()
                        m = idx.setdefault('models', {}).setdefault(clean, { 'entries': [], 'active': None })
                        # find target entry by path
                        target_entry = None
                        for e in (m.get('entries') or []):
                            if e.get('path') == str(pb):
                                target_entry = e; break
                        if target_entry:
                            m['active'] = target_entry
                            save_benchmarks_index(idx)
                            self._refresh_baselines_panel()
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Compare Error", f"Failed to compare baselines: {e}")

    def _compare_generate_suggestions(self):
        try:
            ctx = getattr(self, '_last_comparison_ctx', None)
            if not ctx:
                messagebox.showinfo('Suggestions', 'Run a comparison first.'); return
            test_suite_dir = TRAINING_DATA_DIR / 'Test'
            engine = EvaluationEngine(tests_dir=test_suite_dir)
            s = engine.generate_training_suggestions(ctx.get('baseline') or {}, ctx.get('new') or {})
            # Render into a new window
            win = tk.Toplevel(self.root); win.title('Training Suggestions')
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4")
            txt.pack(fill=tk.BOTH, expand=True)
            txt.insert(1.0, json.dumps(s, indent=2))
            txt.config(state=tk.DISABLED)
            # Save on the side
            self._last_suggestions = s
        except Exception as e:
            messagebox.showerror('Suggestions', f'Failed to generate suggestions: {e}')

    def _compare_save_examples(self):
        """Save example training stubs from comparison results"""
        try:
            # Check if we have suggestions to save
            suggestions = getattr(self, '_last_suggestions', None)
            if not suggestions:
                # Try to generate suggestions first
                ctx = getattr(self, '_last_comparison_ctx', None)
                if not ctx:
                    messagebox.showinfo('Save Examples', 'Run a comparison and generate suggestions first.')
                    return

                # Generate suggestions
                test_suite_dir = TRAINING_DATA_DIR / 'Test'
                engine = EvaluationEngine(tests_dir=test_suite_dir)
                suggestions = engine.generate_training_suggestions(ctx.get('baseline') or {}, ctx.get('new') or {})
                self._last_suggestions = suggestions

            # Check if suggestions have examples
            examples_jsonl = suggestions.get('examples_jsonl', '')
            if not examples_jsonl:
                messagebox.showinfo('Save Examples', 'No example stubs available in the suggestions.')
                return

            # Ask user for save location
            from tkinter import filedialog
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"training_examples_{timestamp}.jsonl"

            filepath = filedialog.asksaveasfilename(
                title="Save Training Examples",
                defaultextension=".jsonl",
                filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
                initialfile=default_filename,
                initialdir=str(TRAINING_DATA_DIR / 'Training')
            )

            if not filepath:
                return  # User cancelled

            # Write examples to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(examples_jsonl)

            messagebox.showinfo(
                'Save Examples',
                f'Training examples saved successfully!\n\nLocation: {filepath}\n\nYou can now use these examples for fine-tuning.'
            )

        except Exception as e:
            messagebox.showerror('Save Examples', f'Failed to save examples: {e}')

    def create_skills_panel(self, parent):
        """Create the skills panel for verified model skills."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        # Scrollable skills area
        skills_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        skills_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=skills_canvas.yview)
        self.skills_content_frame = ttk.Frame(skills_canvas, style='Category.TFrame')

        self.skills_content_frame.bind(
            "<Configure>",
            lambda e: skills_canvas.configure(scrollregion=skills_canvas.bbox("all"))
        )

        self.skills_canvas_window_id = skills_canvas.create_window((0, 0), window=self.skills_content_frame, anchor="nw")
        skills_canvas.configure(yscrollcommand=skills_scrollbar.set)

        skills_canvas.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        skills_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        skills_canvas.bind("<Configure>", lambda e: skills_canvas.itemconfig(self.skills_canvas_window_id, width=e.width))

        # Initialize with placeholder
        ttk.Label(self.skills_content_frame, text="Select a model to view verified skills",
                 font=("Arial", 12), style='Config.TLabel').pack(pady=20)

        # Store current model name for skills
        self.current_model_for_skills = None

    def populate_skills_display(self):
        """Populate the skills display with real-time evaluation data."""
        # Clear existing content
        for widget in self.skills_content_frame.winfo_children():
            widget.destroy()

        model_name = self.current_model_for_stats
        if not model_name:
            ttk.Label(
                self.skills_content_frame,
                text="Select a model to view skills.",
                style='Config.TLabel'
            ).pack(pady=20)
            return

        # Get real-time scores from the chat interface
        scores = self.get_realtime_scores_for_model(model_name)

        if not scores:
            ttk.Label(
                self.skills_content_frame,
                text="No real-time skill data available for this model. Use the model in Custom Code tab with Training Mode enabled to collect data.",
                style='Config.TLabel',
                wraplength=600
            ).pack(pady=20, padx=20)
            return

        # Header
        header_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(
            header_frame,
            text=f"🛠️ Real-Time Tool Skills: {model_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(anchor=tk.W)

        # Display each skill
        for skill, data in sorted(scores.items()):
            success = data.get('success', 0)
            failure = data.get('failure', 0)
            total = success + failure
            success_rate = (success / total * 100) if total > 0 else 0

            # Determine status and color
            if success_rate >= 80:
                status = "Verified"
                color = "#00ff00"
            elif success_rate > 0:
                status = "Partial"
                color = "#ffff00"
            else:
                status = "Failed"
                color = "#ff0000"

            # Skill frame
            skill_frame = ttk.LabelFrame(
                self.skills_content_frame,
                text=f"{skill} ({status})",
                style='TLabelframe'
            )
            skill_frame.pack(fill=tk.X, padx=10, pady=5)

            # Success rate
            ttk.Label(
                skill_frame,
                text=f"Success Rate: {success_rate:.2f}%",
                foreground=color,
                font=("Arial", 10, "bold")
            ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=2)

            # Success/failure counts
            ttk.Label(
                skill_frame,
                text=f"Successes: {success}"
            ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)

            ttk.Label(
                skill_frame,
                text=f"Failures: {failure}"
            ).grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)

            # Error details if any
            if data.get("errors"):
                import tkinter.scrolledtext as scrolledtext
                errors_str = "\n".join(data["errors"][:5])  # Limit to first 5 errors
                if len(data["errors"]) > 5:
                    errors_str += f"\n... and {len(data['errors']) - 5} more errors"

                error_details = scrolledtext.ScrolledText(
                    skill_frame,
                    height=3,
                    width=60,
                    wrap=tk.WORD,
                    font=("Courier", 8)
                )
                error_details.insert(tk.END, errors_str)
                error_details.config(state=tk.DISABLED)
                error_details.grid(row=3, column=0, sticky=tk.W, padx=10, pady=5)

    def get_realtime_scores_for_model(self, model_name):
        """Get real-time evaluation scores for a model from the chat interface."""
        # The parent of ModelsTab is the main notebook, we need to get the CustomCodeTab instance
        if self.tab_instances and 'custom_code_tab' in self.tab_instances:
            custom_code_tab = self.tab_instances['custom_code_tab']['instance']
            if hasattr(custom_code_tab, 'get_chat_interface_scores'):
                all_scores = custom_code_tab.get_chat_interface_scores()
                return all_scores.get(model_name, {})
        return {}

    def create_stats_panel(self, parent):
        """Create the stats panel for model training statistics."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Category filter dropdown
        filter_frame = ttk.Frame(parent, style='Category.TFrame')
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=5)

        ttk.Label(filter_frame, text="Filter by Category:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').pack(side=tk.LEFT, padx=5)

        self.stats_category_filter_var = tk.StringVar(value="All Categories")
        self.stats_category_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.stats_category_filter_var,
            values=["All Categories"],
            state="readonly",
            width=25
        )
        self.stats_category_dropdown.pack(side=tk.LEFT, padx=5)
        self.stats_category_dropdown.bind("<<ComboboxSelected>>", lambda e: self.populate_stats_display())

        # Scrollable stats area
        stats_canvas = tk.Canvas(parent, bg="#2b2b2b", highlightthickness=0)
        stats_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=stats_canvas.yview)
        self.stats_content_frame = ttk.Frame(stats_canvas, style='Category.TFrame')

        self.stats_content_frame.bind(
            "<Configure>",
            lambda e: stats_canvas.configure(scrollregion=stats_canvas.bbox("all"))
        )

        self.stats_canvas_window_id = stats_canvas.create_window((0, 0), window=self.stats_content_frame, anchor="nw")
        stats_canvas.configure(yscrollcommand=stats_scrollbar.set)

        stats_canvas.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=10)
        stats_scrollbar.grid(row=1, column=1, sticky=tk.NS)

        stats_canvas.bind("<Configure>", lambda e: stats_canvas.itemconfig(self.stats_canvas_window_id, width=e.width))

        # Initialize with placeholder
        ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                 font=("Arial", 12), style='Config.TLabel').pack(pady=20)

        # Store current model name for stats
        self.current_model_for_stats = None

    def populate_stats_display(self):
        """Populate the stats display for the current model with category filtering."""
        # Clear existing content
        for widget in self.stats_content_frame.winfo_children():
            widget.destroy()

        if not self.current_model_for_stats:
            ttk.Label(self.stats_content_frame, text="Select a model to view training statistics",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)
            return

        # Load stats for current model
        stats = load_training_stats(self.current_model_for_stats)
        all_runs = stats.get("training_runs", [])

        # Extract unique categories and update dropdown
        categories = sorted(set(run.get("category", "Unknown") for run in all_runs))
        category_options = ["All Categories"] + categories
        self.stats_category_dropdown["values"] = category_options

        # Filter by selected category
        selected_category = self.stats_category_filter_var.get()
        if selected_category != "All Categories":
            filtered_runs = [run for run in all_runs if run.get("category") == selected_category]
        else:
            filtered_runs = all_runs

        # Update stats dict with filtered runs
        stats["training_runs"] = filtered_runs
        latest = filtered_runs[-1] if filtered_runs else None

        # Header
        header_frame = ttk.Frame(self.stats_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        header_text = f"📊 Training Statistics: {self.current_model_for_stats}"
        if selected_category != "All Categories":
            header_text += f" (Category: {selected_category})"

        ttk.Label(header_frame, text=header_text,
                 font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W)

        if not filtered_runs:
            if selected_category == "All Categories":
                ttk.Label(self.stats_content_frame, text="No training runs recorded yet",
                         font=("Arial", 11), style='Config.TLabel').pack(pady=20)
                ttk.Label(self.stats_content_frame,
                         text="Stats will appear here after training completes",
                         font=("Arial", 9), style='Config.TLabel').pack()
            else:
                ttk.Label(self.stats_content_frame, text=f"No training runs for category: {selected_category}",
                         font=("Arial", 11), style='Config.TLabel').pack(pady=20)
                ttk.Label(self.stats_content_frame,
                         text="Try selecting 'All Categories' or a different category",
                         font=("Arial", 9), style='Config.TLabel').pack()
            return

        # Summary section
        summary_frame = ttk.LabelFrame(self.stats_content_frame, text="Summary", style='TLabelframe')
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(summary_frame, text=f"Total Training Runs:", font=("Arial", 10, "bold"),
                 style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
        ttk.Label(summary_frame, text=f"{len(stats['training_runs'])}", font=("Arial", 10),
                 style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)

        if stats.get("last_updated"):
            ttk.Label(summary_frame, text=f"Last Training:", font=("Arial", 10, "bold"),
                     style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(summary_frame, text=f"{stats['last_updated'][:19]}", font=("Arial", 10),
                     style='Config.TLabel').grid(row=1, column=1, sticky=tk.W, padx=10, pady=3)

        # Latest run details
        if latest:
            latest_frame = ttk.LabelFrame(self.stats_content_frame, text="Latest Training Run", style='TLabelframe')
            latest_frame.pack(fill=tk.X, padx=10, pady=5)
            row = 0
            for key, value in latest.items():
                if key not in ["timestamp", "eval_report_path"]:  # Exclude eval_report_path from direct display
                    ttk.Label(latest_frame, text=f"{key.replace('_', ' ').title()}:",
                    font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                    row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(latest_frame, text=str(value), font=("Arial", 10),
                    style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
                    row += 1
                        # --- Evaluation and Comparison Summary ---
            eval_report_path = latest.get("eval_report_path")
            if eval_report_path and Path(eval_report_path).exists():
                try:
                    with open(eval_report_path, 'r') as f:
                        eval_report = json.load(f)
                    # Load active baseline for comparison
                    base_model_name = latest.get("base_model")
                    if base_model_name:
                        test_suite_dir = TRAINING_DATA_DIR / "Test"
                        eval_engine = EvaluationEngine(tests_dir=test_suite_dir)
                        baseline_report = load_baseline_report(base_model_name)
                        if baseline_report:
                            comparison = eval_engine.compare_models(baseline_report, eval_report)
                            # Display comparison summary
                            compare_frame = ttk.LabelFrame(latest_frame, text="Evaluation vs. Baseline", style='TLabelframe')
                            compare_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
                            compare_row = 0
                            overall_delta = comparison.get('overall', {}).get('delta', '+0.00%')
                            ttk.Label(compare_frame, text=f"Overall Pass Rate Delta: {overall_delta}",
                            font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                            compare_row += 1
                            regressions = comparison.get('regressions', [])
                            if regressions:
                                reg_text = ", ".join([r.get('skill', '') for r in regressions])
                                ttk.Label(compare_frame, text=f"⚠️ Regressions: {reg_text}",
                                font=("Arial", 10, "bold"), foreground='red', style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1
                                # Add button for suggestions
                                ttk.Button(compare_frame, text="💡 Get Suggestions", style='Action.TButton',
                                command=lambda br=baseline_report, nr=eval_report: self._show_suggestions_dialog(br, nr)).grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1
                            improvements = comparison.get('improvements', [])
                            if improvements:
                                imp_text = ", ".join([i.get('skill', '') for i in improvements])
                                ttk.Label(compare_frame, text=f"✅ Improvements: {imp_text}",
                                font=("Arial", 10, "bold"), foreground='green', style='Config.TLabel').grid(row=compare_row, column=0, sticky=tk.W, padx=5, pady=2)
                                compare_row += 1
                            row += 1  # Increment main row counter for latest_frame
                        else:
                            ttk.Label(latest_frame, text="No active baseline found for comparison.",
                            font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                            row += 1
                    else:
                        ttk.Label(latest_frame, text="Base model name not available for baseline lookup.",
                                  font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                        row += 1

                    # Display overall evaluation results
                    ttk.Label(latest_frame, text=f"Evaluation Pass Rate: {eval_report.get('pass_rate_percent', 'N/A')}",
                              font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1
                    ttk.Label(latest_frame, text=f"Prompt: {eval_report.get('metadata', {}).get('prompt_name', 'N/A')}",
                              font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1
                    ttk.Label(latest_frame, text=f"Schema: {eval_report.get('metadata', {}).get('schema_name', 'N/A')}",
                              font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                    row += 1

                except Exception as e:
                    ttk.Label(latest_frame, text=f"Error loading evaluation report: {e}",
                              font=("Arial", 9), foreground='red', style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                    row += 1
            else:
                ttk.Label(latest_frame, text="No evaluation report linked to this training run.",
                          font=("Arial", 9), style='Config.TLabel').grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=10, pady=2)
                row += 1

            if latest.get("eval_loss") is not None:
                ttk.Label(latest_frame, text="Eval Loss:",
                          font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                              row=row, column=0, sticky=tk.W, padx=10, pady=2)
                ttk.Label(latest_frame, text=f"{latest.get('eval_loss', 0.0):.4f}", font=("Arial", 10),
                          style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=10, pady=2)
                row += 1

            # Baseline Skills Results
            baseline_skills = latest.get("baseline_skills_results")
            if baseline_skills:
                skills_frame = ttk.LabelFrame(self.stats_content_frame, text="Baseline Skill Test Results", style='TLabelframe')
                skills_frame.pack(fill=tk.X, padx=10, pady=5)

                skill_row = 0
                for skill_name, skill_data in baseline_skills.items():
                    status_icon = "✅" if skill_data.get("passed") else "❌"
                    ttk.Label(skills_frame, text=f"{status_icon} {skill_name}:",
                              font=("Arial", 10, "bold"), style='Config.TLabel').grid(
                                  row=skill_row, column=0, sticky=tk.W, padx=10, pady=2)
                    ttk.Label(skills_frame, text=str(skill_data.get("passed")),
                              font=("Arial", 10), style='Config.TLabel').grid(
                                  row=skill_row, column=1, sticky=tk.W, padx=10, pady=2)
                    skill_row += 1

        # Training history
        if len(stats["training_runs"]) > 1:
            history_frame = ttk.LabelFrame(self.stats_content_frame, text="Training History", style='TLabelframe')
            history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            for idx, run in enumerate(reversed(stats["training_runs"]), 1):
                run_frame = ttk.Frame(history_frame, style='Category.TFrame')
                run_frame.pack(fill=tk.X, padx=5, pady=2)

                timestamp = run.get("timestamp", "Unknown")[:19]
                ttk.Label(run_frame, text=f"Run #{len(stats['training_runs']) - idx + 1} - {timestamp}",
                         font=("Arial", 9, "bold"), style='Config.TLabel').pack(anchor=tk.W)

                details = ", ".join([f"{k}: {v}" for k, v in run.items() if k != "timestamp"])
                ttk.Label(run_frame, text=details, font=("Arial", 8),
                         style='Config.TLabel').pack(anchor=tk.W, padx=10)

    def populate_skills_display(self):
        """Populate the skills display with runtime AND evaluation skills for comparison."""
        for widget in self.skills_content_frame.winfo_children():
            widget.destroy()

        model_name = self.current_model_for_stats
        if not model_name:
            ttk.Label(self.skills_content_frame, text="Select a model to view skills.", style='Config.TLabel').pack(pady=20)
            return

        # Get BOTH runtime skills (actual usage) AND evaluation skills (test results)
        try:
            from config import _get_runtime_skills, get_model_skills
            runtime_skills = _get_runtime_skills(model_name)
            eval_skills = get_model_skills(model_name)
        except Exception as e:
            log_message(f"MODELS_TAB ERROR: Failed to get skills: {e}")
            runtime_skills = {}
            eval_skills = {}

        # Merge runtime and evaluation skills
        all_skills = set(list(runtime_skills.keys()) + list(eval_skills.keys()))

        # If no skills at all, show message
        if not all_skills:
            ttk.Label(
                self.skills_content_frame,
                text="No skill data available.\n\nUse the model in Custom Code tab with Training Mode enabled to collect runtime data,\nor run evaluations in the Evaluation tab.",
                style='Config.TLabel',
                wraplength=600
            ).pack(pady=20, padx=20)
            return

        # Header
        header_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text=f"🛠️ Tool Skills: {model_name}",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(anchor=tk.W, pady=(0, 5))

        ttk.Label(
            header_frame,
            text="Comparing Runtime (actual usage) vs Evaluation (test results)",
            font=("Arial", 9),
            style='Config.TLabel',
            foreground='#888888'
        ).pack(anchor=tk.W)

        # Categorize skills
        verified_runtime = []  # High runtime success
        unverified_eval = []  # Good eval but no/low runtime usage
        failed_runtime = []  # Poor runtime success
        no_data = []  # Skills with no meaningful data

        for skill in sorted(all_skills):
            runtime_data = runtime_skills.get(skill, {})
            eval_data = eval_skills.get(skill, {})

            runtime_rate = runtime_data.get('success_rate', 0)
            runtime_calls = runtime_data.get('total_calls', 0)
            eval_status = eval_data.get('status', 'Unknown')

            if runtime_calls >= 3:  # Has meaningful runtime data
                if runtime_rate >= 80:
                    verified_runtime.append((skill, runtime_data, eval_data))
                else:
                    failed_runtime.append((skill, runtime_data, eval_data))
            elif eval_status in ['Verified', 'Partial']:
                unverified_eval.append((skill, runtime_data, eval_data))
            else:
                no_data.append((skill, runtime_data, eval_data))

        # Summary
        summary_frame = ttk.Frame(self.skills_content_frame, style='Category.TFrame')
        summary_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(
            summary_frame,
            text=f"✅ Verified (Runtime): {len(verified_runtime)} | ⚠️ Claimed (Eval only): {len(unverified_eval)} | ❌ Failed (Runtime): {len(failed_runtime)}",
            font=("Arial", 10),
            style='Config.TLabel'
        ).pack(anchor=tk.W)

        # Section 1: Verified Runtime Skills (Green - High Confidence)
        if verified_runtime:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="✅ Verified Skills (Runtime Success ≥80%)",
                font=("Arial", 12, "bold"),
                foreground="#00ff00"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data in verified_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#00ff00", "✅")

        # Section 2: Claimed Skills (Yellow - Unverified)
        if unverified_eval:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="⚠️ Claimed Skills (Evaluation Only - Not Verified in Runtime)",
                font=("Arial", 12, "bold"),
                foreground="#ffff00"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data in unverified_eval:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#ffff00", "⚠️")

        # Section 3: Failed Runtime Skills (Red - Needs Training)
        if failed_runtime:
            section_label = ttk.Label(
                self.skills_content_frame,
                text="❌ Failed Skills (Runtime Success <80% - Needs Training)",
                font=("Arial", 12, "bold"),
                foreground="#ff6b6b"
            )
            section_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

            for skill, runtime_data, eval_data in failed_runtime:
                self._create_skill_comparison_frame(skill, runtime_data, eval_data, "#ff6b6b", "❌")

    def _create_skill_comparison_frame(self, skill, runtime_data, eval_data, color, icon):
        """Create a frame showing both runtime and eval data for a skill"""
        skill_frame = ttk.LabelFrame(
            self.skills_content_frame,
            text=f"{icon} {skill}",
            style='TLabelframe'
        )
        skill_frame.pack(fill=tk.X, padx=10, pady=3)

        # Create two columns: Runtime (left) and Evaluation (right)
        left_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        right_frame = ttk.Frame(skill_frame, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Left: Runtime Data
        if runtime_data and runtime_data.get('total_calls', 0) > 0:
            ttk.Label(
                left_frame,
                text="Runtime Usage:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            success_rate = runtime_data.get('success_rate', 0)
            ttk.Label(
                left_frame,
                text=f"{success_rate:.1f}% success",
                foreground=color,
                font=("Arial", 10, "bold")
            ).grid(row=1, column=0, sticky=tk.W, padx=(0, 10))

            ttk.Label(
                left_frame,
                text=f"({runtime_data.get('success_count', 0)}/{runtime_data.get('total_calls', 0)} calls)",
                style='Config.TLabel'
            ).grid(row=1, column=1, sticky=tk.W)
        else:
            ttk.Label(
                left_frame,
                text="Runtime: No usage data",
                font=("Arial", 9),
                foreground="#888888"
            ).grid(row=0, column=0, sticky=tk.W)

        # Right: Evaluation Data
        if eval_data and eval_data.get('status'):
            ttk.Label(
                right_frame,
                text="Evaluation:",
                font=("Arial", 9, "bold"),
                foreground="#61dafb"
            ).grid(row=0, column=0, sticky=tk.W, columnspan=2)

            eval_status = eval_data.get('status', 'Unknown')
            eval_color = "#00ff00" if eval_status == "Verified" else "#ffff00" if eval_status == "Partial" else "#888888"

            ttk.Label(
                right_frame,
                text=eval_status,
                foreground=eval_color,
                font=("Arial", 10)
            ).grid(row=1, column=0, sticky=tk.W)
        else:
            ttk.Label(
                right_frame,
                text="Evaluation: No data",
                font=("Arial", 9),
                foreground="#888888"
            ).grid(row=0, column=0, sticky=tk.W)

        # Show errors if available
        errors = runtime_data.get("errors", [])
        if errors:
            error_text = "\n".join(errors[:3])  # Show max 3 errors
            error_label = ttk.Label(
                skill_frame,
                text=f"Recent errors: {error_text}",
                font=("Courier", 8),
                foreground="#ff6b6b",
                wraplength=600
            )
            error_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=10, pady=(0, 5))


    def populate_notes_list(self):
        """Populate the notes list for the current model."""
        for widget in self.notes_list_buttons_frame.winfo_children():
            widget.destroy()

        if not self.current_model_info:
            ttk.Label(self.notes_list_buttons_frame, text="Select a model", style='Config.TLabel').pack(pady=10)
            return

        notes = list_model_notes(self.current_model_info)

        if not notes:
            ttk.Label(self.notes_list_buttons_frame, text="No notes yet", style='Config.TLabel').pack(pady=10)
            return

        for note_name in notes:
            note_btn = ttk.Button(
                self.notes_list_buttons_frame,
                text=note_name,
                command=lambda n=note_name: self.load_note(n),
                style='Select.TButton'
            )
            note_btn.pack(fill=tk.X, pady=2, padx=5)

    def save_note(self):
        """Save the current note for the selected model."""
        if not self.current_model_info:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter a name for the note.")
            return

        content = self.notes_text.get(1.0, tk.END).strip()

        try:
            save_model_note(self.current_model_info, note_name, content)
            messagebox.showinfo("Note Saved", f"Note '{note_name}' saved for {self.current_model_info['name']}")
            self.populate_notes_list()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save note: {e}")

    def load_note(self, note_name):
        """Load a specific note for the current model."""
        if not self.current_model_info:
            return

        content = load_model_note(self.current_model_info, note_name)
        self.note_name_var.set(note_name)
        self.notes_text.delete(1.0, tk.END)
        self.notes_text.insert(1.0, content)

    def delete_note(self):
        """Delete the current note."""
        if not self.current_model_info:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        note_name = self.note_name_var.get().strip()
        if not note_name:
            messagebox.showwarning("No Note Name", "Please enter the name of the note to delete.")
            return

        if messagebox.askyesno("Confirm Delete", f"Delete note '{note_name}'?"):
            if delete_model_note(self.current_model_info, note_name):
                messagebox.showinfo("Note Deleted", f"Note '{note_name}' deleted.")
                self.notes_text.delete(1.0, tk.END)
                self.note_name_var.set("")
                self.populate_notes_list()
            else:
                messagebox.showwarning("Not Found", f"Note '{note_name}' not found.")

    def display_model_info_from_dict(self, model_info):
        """Display model information for PyTorch/Trained models and populate the adapters tab."""
        self.current_model_info = model_info
        model_name = model_info["name"]
        model_type = model_info["type"]

        # --- Populate Overview Tab ---
        # Clear previous content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

        # Load config.json if available
        model_config = {}
        config_file = Path(model_info["path"]) / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    model_config = json.load(f)
            except: pass

        info_frame = ttk.LabelFrame(self.overview_tab_frame, text="Base Model Information", style='TLabelframe')
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        info_frame.columnconfigure(1, weight=1)

        # Display base model info
        row = 0
        ttk.Label(info_frame, text="Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        name_frame = ttk.Frame(info_frame)
        name_frame.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(name_frame, text=model_name, font=("Arial", 10), style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
        ttk.Button(name_frame, text="📎", command=self._copy_name_to_clipboard, style='Select.TButton', width=2).pack(side=tk.LEFT, padx=5)
        row += 1
        ttk.Label(info_frame, text="Type:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info_frame, text=("Trained" if model_type == 'trained' else "Base (PyTorch)"), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1
        if model_info.get('path'):
            ttk.Label(info_frame, text="Path:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            ttk.Label(info_frame, text=str(model_info['path']), font=("Arial", 9), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1
        if model_info.get('size'):
            ttk.Label(info_frame, text="Size:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
            ttk.Label(info_frame, text=str(model_info['size']), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row += 1

        # Architecture details from config.json
        if model_config:
            arch_rows = []
            if model_config.get('model_type'):
                arch_rows.append(("Architecture", model_config['model_type']))
            if model_config.get('num_hidden_layers') is not None:
                arch_rows.append(("Layers", model_config['num_hidden_layers']))
            if model_config.get('hidden_size') is not None:
                arch_rows.append(("Hidden Size", model_config['hidden_size']))
            if model_config.get('num_attention_heads') is not None:
                arch_rows.append(("Attention Heads", model_config['num_attention_heads']))
            if model_config.get('intermediate_size') is not None:
                arch_rows.append(("Intermediate Size", model_config['intermediate_size']))
            if model_config.get('max_position_embeddings') is not None:
                arch_rows.append(("Max Seq Length", model_config['max_position_embeddings']))
            if model_config.get('vocab_size') is not None:
                arch_rows.append(("Vocab Size", f"{model_config['vocab_size']:,}"))
            for k,v in arch_rows:
                ttk.Label(info_frame, text=f"{k}:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=2)
                ttk.Label(info_frame, text=str(v), font=("Arial", 10), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
                row += 1

        # Behavior indicators (Compliance/Creativity/Coherence)
        try:
            from config import get_model_behavior_profile
            prof = get_model_behavior_profile(model_name) or {}
            beh = prof.get('behavior') or {}
            beh_frame = ttk.LabelFrame(self.overview_tab_frame, text="Behavior Indicators", style='TLabelframe')
            beh_frame.pack(fill=tk.X, padx=10, pady=6)
            def _badge(k: str) -> str:
                v = (beh.get(k) or '0.00%')
                return v
            ttk.Label(beh_frame, text=f"Compliance: {_badge('compliance')}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Creativity: {_badge('creativity')}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Coherence: {_badge('coherence')}", style='Config.TLabel').grid(row=0, column=2, sticky=tk.W, padx=10, pady=3)
        except Exception:
            pass

        # --- Populate Adapters Tab ---
        self._populate_adapters_tab(model_info)

        # --- Populate History Tab ---
        self._populate_history_tab(model_info)

        # --- Populate Other Tabs ---
        # Ensure skills/stats context reflects this selection
        self.current_model_for_stats = model_name
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        if model_config:
            self.raw_model_info_text.insert(1.0, f"Config.json:\n{'='*60}\n{json.dumps(model_config, indent=2)}")
        else:
            self.raw_model_info_text.insert(1.0, "No config.json found.")
        self.raw_model_info_text.config(state=tk.DISABLED)

        self.notes_text.delete(1.0, tk.END)
        self.note_name_var.set("")
        self.populate_notes_list()
        self.populate_stats_display()
        self.populate_skills_display()
        try:
            self._refresh_baselines_panel()
        except Exception:
            pass

        if hasattr(self, 'selected_model_label_eval'):
            self.selected_model_label_eval.config(text=f"Selected Model: {model_name}")
        if hasattr(self, 'eval_source_label'):
            src = "Trainable (PyTorch)"
            self.eval_source_label.config(text=f"Source: {src}")

    def display_level_info(self, base_model_name: str, level_data: dict):
        """Display Level overview: base info, adapters in level, eval/skill deltas, and export status."""
        # Clear overview
        for w in self.overview_tab_frame.winfo_children():
            w.destroy()
        info = ttk.LabelFrame(self.overview_tab_frame, text="Level Overview", style='TLabelframe')
        info.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        info.columnconfigure(1, weight=1)

        row = 0
        ttk.Label(info, text="Level Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=level_data.get('name','(unnamed)'), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        ttk.Label(info, text="Base Model:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=base_model_name, style='Config.TLabel', foreground='#61dafb').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        ttk.Label(info, text="Created:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=level_data.get('created',''), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Adapters list
        adapters = [a.get('name') for a in (level_data.get('adapters') or []) if a.get('name')]
        ttk.Label(info, text="Adapters:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=(', '.join(adapters) if adapters else 'None'), style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Evaluation summary for primary adapter (first)
        primary = adapters[0] if adapters else None
        summary = "Unverified"
        if primary:
            try:
                baseline = load_baseline_report(base_model_name) or {}
                latest = load_latest_evaluation_report(primary) or {}
                if latest and baseline:
                    engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
                    policy = get_regression_policy() or {}
                    threshold = float(policy.get('alert_drop_percent', 5.0))
                    cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
                    overall = cmp.get('overall', {})
                    summary = f"Overall: {overall.get('new','N/A')} (Δ {overall.get('delta','+0.00%')})"
            except Exception:
                pass
        ttk.Label(info, text="Evaluation:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=summary, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Status (Ollama installed?)
        status = "Archived only"
        try:
            exports = level_data.get('exports') or []
            if exports:
                status = "Ollama: installed"
        except Exception:
            pass
        ttk.Label(info, text="Status:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(info, text=status, style='Config.TLabel').grid(row=row, column=1, sticky=tk.W, padx=5, pady=5); row+=1
        # Actions
        act = ttk.Frame(info)
        act.grid(row=row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=8)
        ttk.Button(act, text="Export to GGUF", style='Action.TButton', command=lambda b=base_model_name, lv=level_data: self._levels_export_to_gguf({"name":b, "path": self._find_base_path(b)}, lv)).pack(side=tk.LEFT, padx=5)
        ttk.Button(act, text="Open Level Folder", style='Select.TButton', command=lambda b=base_model_name, n=level_data.get('name',''): self._levels_open_folder(b, n)).pack(side=tk.LEFT, padx=5)

    def _find_base_path(self, base_model_name: str):
        # Helper to locate base model path from self.all_models
        try:
            for m in self.all_models:
                if m.get('name') == base_model_name and m.get('type') == 'pytorch':
                    return m.get('path')
        except Exception:
            pass
        return None

    def _toggle_levels(self, base_name: str):
        """Expand/collapse the levels list for a base in the right-side model list."""
        try:
            ui = self.levels_ui.get(base_name)
            if not ui:
                return
            container = ui['container']
            arrow = ui['arrow']
            expanded = bool(container.winfo_ismapped())
            if expanded:
                container.pack_forget()
                arrow.config(text='▶')
            else:
                container.pack(fill=tk.X)
                arrow.config(text='▼')
            self.levels_expanded[base_name] = not expanded
        except Exception:
            pass

    def _group_ollama_by_base(self, ollama_names: list) -> dict:
        """Group Ollama model names under base models if discoverable via level manifests; others under 'Unassigned'."""
        grouping = {}
        # Seed with Unassigned
        grouping['Unassigned'] = []
        try:
            # Map export names to base by scanning all bases' levels
            base_names = [m['name'] for m in self.all_models if m.get('type') == 'pytorch']
            export_to_base = {}
            for b in base_names:
                levels = self._discover_levels_for_base(b)
                for lv in levels:
                    for exp in (lv.get('exports') or []):
                        name = exp.get('name')
                        if name:
                            export_to_base[name] = b
            # Group ollama names
            for name in ollama_names:
                base = export_to_base.get(name)
                if base:
                    grouping.setdefault(base, []).append(name)
                else:
                    grouping['Unassigned'].append(name)
            # Remove Unassigned if empty
            if not grouping['Unassigned']:
                grouping.pop('Unassigned', None)
        except Exception:
            # Fallback: put all under Unassigned
            grouping = {'Unassigned': ollama_names}
        return grouping

    def _toggle_ollama_group(self, base_name: str):
        try:
            ui = self.ollama_ui.get(base_name)
            if not ui: return
            cont = ui['container']; arrow = ui['arrow']
            expanded = bool(cont.winfo_ismapped())
            if expanded:
                cont.pack_forget(); arrow.config(text='▶')
            else:
                cont.pack(fill=tk.X); arrow.config(text='▼')
            self.ollama_expanded[base_name] = not expanded
        except Exception:
            pass

    def _display_gguf_info(self, model_info: dict):
        """Show local GGUF file info in the overview panel."""
        from pathlib import Path as _Path
        model_name = model_info["name"]
        gpath = model_info.get("path")
        gsize = model_info.get("size", "?")

        # Raw info tab
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        info_lines = [
            f"Name:   {model_name}",
            f"Type:   Local GGUF (on-disk)",
            f"Size:   {gsize}",
            f"Path:   {gpath}",
            "",
            "Provider options:",
            "  • Ollama  — click 'Load' to register, then use chat interface",
            "  • llama_cpp_python — available if installed (used by Morph bridge)",
        ]
        self.raw_model_info_text.insert(1.0, "\n".join(info_lines))
        self.raw_model_info_text.config(state=tk.DISABLED)

        # Overview tab
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

        info_frame = ttk.LabelFrame(self.overview_tab_frame,
                                    text=f"🟣 Local GGUF: {model_name}", style='TLabelframe')
        info_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)
        info_frame.columnconfigure(1, weight=1)

        for i, (label, value) in enumerate([
            ("File", str(gpath)),
            ("Size", gsize),
            ("Status", "On-disk (not yet in Ollama)"),
        ]):
            ttk.Label(info_frame, text=f"{label}:", font=("Arial", 10, "bold"),
                     style='Config.TLabel').grid(row=i, column=0, sticky=tk.W, padx=8, pady=4)
            ttk.Label(info_frame, text=value, style='Config.TLabel',
                     foreground='#c792ea', wraplength=400).grid(row=i, column=1, sticky=tk.W, padx=8)

        btn_frame = ttk.Frame(self.overview_tab_frame)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=8, sticky=tk.W, padx=5)
        ttk.Button(btn_frame, text="🔶 Register with Ollama",
                   command=lambda: self._load_gguf_via_ollama(gpath, model_name),
                   style='Action.TButton').pack(side=tk.LEFT, padx=4)

        # Sibling exports and Morph runtime states under the same base model dir
        try:
            # Walk up from the GGUF path to find the direct child of MODELS_DIR
            _gpath = _Path(str(gpath)) if gpath else None
            _base_name = None
            if _gpath:
                _p = _gpath
                while _p.parent != MODELS_DIR and _p.parent != _p:
                    _p = _p.parent
                if _p.parent == MODELS_DIR:
                    _base_name = _p.name
            if _base_name:
                _all = self._discover_gguf_exports_for_base(_base_name)
                _ggufs = [x for x in _all if x["type"] == "gguf"]
                _states = [x for x in _all if x["type"] == "variant_json"]

                # ── GGUF Exports (actual inference binaries) ──
                if _ggufs:
                    exp_frame = ttk.LabelFrame(self.overview_tab_frame,
                                               text=f"📦 Exports ({len(_ggufs)})", style='TLabelframe')
                    exp_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=6)
                    exp_frame.columnconfigure(1, weight=1)
                    for _i, _ex in enumerate(_ggufs):
                        _sz = f"({_ex['size_mb']} MB)" if _ex["size_mb"] > 0 else ""
                        _lbl = f"🟣 {_ex['name']} {_sz}".strip()
                        ttk.Label(exp_frame, text=_lbl, style='Config.TLabel',
                                  foreground='#c792ea').grid(row=_i, column=0, sticky=tk.W, padx=8, pady=2)
                        _ebtn_frame = ttk.Frame(exp_frame)
                        _ebtn_frame.grid(row=_i, column=1, sticky=tk.W, padx=4)
                        _ep = _ex["path"]
                        _en = _ex["name"]
                        ttk.Button(_ebtn_frame, text="Load in Chat",
                                   command=lambda p=_ep, n=_en: self._notify_chat_load_gguf(p, n),
                                   style='Small.TButton').pack(side=tk.LEFT, padx=2)
                        ttk.Button(_ebtn_frame, text="Via Ollama",
                                   command=lambda p=_ep, n=_en: self._load_gguf_via_ollama(p, n),
                                   style='Small.TButton').pack(side=tk.LEFT, padx=2)

                # ── Morph Runtime States (inference-time snapshots, NOT exports) ──
                if _states:
                    st_frame = ttk.LabelFrame(self.overview_tab_frame,
                                              text=f"🧬 Morph Runtime States ({len(_states)})",
                                              style='TLabelframe')
                    st_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=4)
                    ttk.Label(st_frame,
                              text="Control packet snapshots from inference sessions — no weight changes stored",
                              font=("Arial", 8), foreground='#858585',
                              style='Config.TLabel').grid(row=0, column=0, columnspan=2,
                                                          sticky=tk.W, padx=8, pady=(2, 4))
                    for _i, _ex in enumerate(_states):
                        sha = _ex['name'].replace('morph_variant_', '')[:16]
                        ttk.Label(st_frame, text=f"  SHA:{sha}…", style='Config.TLabel',
                                  foreground='#82aaff').grid(row=_i + 1, column=0,
                                                             sticky=tk.W, padx=8, pady=1)
        except Exception:
            pass

    def _notify_chat_load_gguf(self, gguf_path, model_name: str):
        """Broadcast GGUF selection to any listening chat interface."""
        from tkinter import messagebox
        try:
            # Try to find chat_interface in parent notebook tabs and call set_model
            _root = self.frame.winfo_toplevel()
            # Walk widget tree looking for a frame with set_model attribute
            def _find_chat(_w):
                for _child in _w.winfo_children():
                    if hasattr(_child, 'set_model'):
                        return _child
                    _found = _find_chat(_child)
                    if _found:
                        return _found
                return None
            _chat = _find_chat(_root)
            if _chat:
                _chat.set_model(model_name, model_info={"name": model_name, "type": "gguf", "path": gguf_path})
                messagebox.showinfo("Model Loaded", f"GGUF model '{model_name}' sent to chat interface.")
            else:
                messagebox.showinfo("GGUF Path", f"Path: {gguf_path}\n\nOpen Custom Code tab → select model from list.")
        except Exception as _e:
            messagebox.showinfo("GGUF Path", f"Path: {gguf_path}")

    def _load_gguf_via_ollama(self, gguf_path, model_name: str):
        """Register a local GGUF with Ollama, auto-generating a minimal Modelfile."""
        import threading, subprocess, tempfile
        from pathlib import Path as _Path

        # Check if a hand-crafted Modelfile already exists nearby
        _mf_candidates = [
            _Path(gguf_path).parent / "Modelfile",
            _Path(gguf_path).parent.parent.parent / "training_data" / "Morph.modelfile",
        ]
        _mf_path = next((p for p in _mf_candidates if p.exists()), None)

        def _run():
            try:
                if _mf_path:
                    mf = str(_mf_path)
                else:
                    # Write a minimal temporary Modelfile
                    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.modelfile',
                                                       delete=False, encoding='utf-8')
                    _tmp.write(f'FROM {gguf_path}\nTEMPLATE "{{{{ .Prompt }}}}"\n')
                    _tmp.flush(); _tmp.close()
                    mf = _tmp.name

                ollama_name = model_name.replace('.', '-').replace('_', '-').lower()
                result = subprocess.run(
                    ["ollama", "create", ollama_name, "-f", mf],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    self.root.after(0, lambda n=ollama_name: (
                        self.populate_model_list(),
                        messagebox.showinfo("GGUF Loaded",
                            f"✓ Registered '{n}' with Ollama.\nModel list refreshed.")
                    ))
                else:
                    err = (result.stderr or result.stdout or "unknown error")[:300]
                    self.root.after(0, lambda e=err: messagebox.showerror(
                        "Load Failed", f"ollama create failed:\n{e}"))
            except FileNotFoundError:
                self.root.after(0, lambda: messagebox.showwarning(
                    "Ollama Not Found",
                    "ollama binary not found in PATH.\n"
                    "Install ollama, or use llama_cpp_python directly via Morph bridge."))
            except Exception as ex:
                self.root.after(0, lambda e=str(ex): messagebox.showerror("Error", e))

        messagebox.showinfo("Loading GGUF",
            f"Registering {model_name} with Ollama in background…")
        threading.Thread(target=_run, daemon=True).start()

    def _populate_adapters_tab(self, base_model_info):
        """Scans for and displays all adapters trained from the given base model."""
        for widget in self.adapters_tab_frame.winfo_children():
            widget.destroy()

        base_model_name = base_model_info["name"]
        base_dir = Path(base_model_info["path"]).parent
        all_training_dirs = list(base_dir.glob("training_*"))

        # Header controls
        header = ttk.Frame(self.adapters_tab_frame)
        header.pack(fill=tk.X, padx=8, pady=(6, 2))
        ttk.Checkbutton(header, text="Select Mode", variable=self.adapters_select_mode, style='Category.TCheckbutton',
                        command=lambda: self._toggle_adapters_select_mode(base_model_info)).pack(side=tk.LEFT)
        ttk.Button(header, text="Select All", style='Select.TButton',
                   command=lambda: self._adapters_select_all(True)).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(header, text="Clear", style='Select.TButton',
                   command=lambda: self._adapters_select_all(False)).pack(side=tk.LEFT, padx=(2, 8))
        self.adapters_estimate_btn = ttk.Button(header, text="Estimate Size", style='Select.TButton',
                                                command=self._adapters_estimate_size)
        self.adapters_estimate_btn.pack(side=tk.RIGHT)
        self.adapters_levelup_btn = ttk.Button(header, text="Level Up 🚀", style='Action.TButton',
                                               command=lambda: self._adapters_level_up_selected(base_model_info))
        self.adapters_levelup_btn.pack(side=tk.RIGHT, padx=(0, 6))
        # Save as Level button
        self.adapters_save_level_btn = ttk.Button(header, text="Save as Level", style='Select.TButton',
                                                  command=lambda: self._adapters_save_as_level(base_model_info))
        self.adapters_save_level_btn.pack(side=tk.RIGHT, padx=(0, 6))

        found_adapters = []
        for adapter_dir in all_training_dirs:
            try:
                adapter_config_path = adapter_dir / 'adapter_config.json'
                if adapter_config_path.exists():
                    with open(adapter_config_path, 'r') as f:
                        adapter_config = json.load(f)
                    # Match by exact base name or contains cleaned base name
                    base_field = (adapter_config.get('base_model_name_or_path') or '')
                    clean_base = base_model_name.replace('/', '_').replace(':', '_')
                    alt_clean = clean_base.replace('-Instruct', '')
                    if base_field == base_model_name or clean_base in adapter_dir.name or alt_clean in adapter_dir.name:
                        found_adapters.append(adapter_dir)
                    continue
                # Fallback: infer by directory naming pattern if adapter_config.json missing
                clean_base = base_model_name.replace('/', '_').replace(':', '_')
                alt_clean = clean_base.replace('-Instruct', '')
                if clean_base in adapter_dir.name or alt_clean in adapter_dir.name:
                    found_adapters.append(adapter_dir)
            except Exception:
                continue # Ignore folders that can't be read

        if not found_adapters:
            ttk.Label(self.adapters_tab_frame, text="No adapters have been trained from this base model yet.", style='Config.TLabel').pack(padx=10, pady=10)
            return

        canvas = tk.Canvas(self.adapters_tab_frame, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.adapters_tab_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        for adapter_path in sorted(found_adapters, key=lambda p: p.stat().st_mtime, reverse=True):
            adapter_name = adapter_path.name
            adapter_frame = ttk.Frame(scrollable_frame, style='Category.TFrame', borderwidth=1, relief="solid")
            adapter_frame.pack(fill=tk.X, padx=5, pady=5, expand=True)
            adapter_frame.columnconfigure(1, weight=1)

            col = 0
            if self.adapters_select_mode.get():
                var = self.adapters_selection.get(str(adapter_path))
                if var is None:
                    var = tk.BooleanVar(value=False)
                    self.adapters_selection[str(adapter_path)] = var
                ttk.Checkbutton(adapter_frame, text="", variable=var, style='Category.TCheckbutton', width=2,
                                command=self._adapters_update_actions_state).grid(row=0, column=col, sticky=tk.W, padx=5)
                col += 1

            ttk.Label(adapter_frame, text=f"▶ {adapter_name}", font=("Arial", 10, "bold"), foreground="#51cf66").grid(row=0, column=col, sticky=tk.W, padx=5, pady=2)
            col += 1
            # Readiness pill
            status_label = ttk.Label(adapter_frame, text="", font=("Arial", 8), style='Config.TLabel')
            status_label.grid(row=0, column=col, sticky=tk.W, padx=5)
            readiness = self._compute_adapter_readiness(adapter_name, base_model_name)
            pill_text = readiness.get('status', 'Unverified')
            pill_color = '#51cf66' if pill_text == 'Ready' else ('#ffd43b' if pill_text in ('Needs Eval', 'Unverified') else '#ff6b6b')
            status_label.config(text=pill_text, foreground=pill_color)

            stats = get_latest_training_stats(adapter_name)
            if stats:
                stats_text = f"Epochs: {stats.get('epochs', 'N/A')} | Loss: {stats.get('training_loss', 0.0):.4f} | Runtime: {stats.get('train_runtime', 0):.1f}s"
                span = 3 if self.adapters_select_mode.get() else 2
                ttk.Label(adapter_frame, text=stats_text, font=("Arial", 8), style='Config.TLabel').grid(row=1, column=0, columnspan=span, sticky=tk.W, padx=15)

            button_frame = ttk.Frame(adapter_frame)
            span = 3 if self.adapters_select_mode.get() else 2
            button_frame.grid(row=2, column=0, columnspan=span, sticky=tk.W, padx=15, pady=5)
            ttk.Button(button_frame, text="Archive", command=lambda ap=adapter_path: self._archive_adapter(ap), style='Select.TButton').pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete", command=lambda ap=adapter_path: self._delete_adapter(ap), style='Select.TButton').pack(side=tk.LEFT, padx=5)

        # Update header button states
        self._adapters_update_actions_state()

    def _compute_adapter_readiness(self, adapter_name: str, base_model_name: str) -> dict:
        """Return readiness info for an adapter based on baseline/evaluation comparison.
        Structure: {status, delta_overall(float), regressions(list[str]), issues(list[str])}
        """
        info = {"status": "Unverified", "delta_overall": None, "regressions": [], "issues": []}
        try:
            baseline = load_baseline_report(base_model_name) or {}
            latest_eval = load_latest_evaluation_report(adapter_name) or {}
            if not latest_eval:
                info["status"] = "Needs Eval"
                info["issues"].append("No evaluation report found for adapter.")
                if not baseline:
                    info["issues"].append("No baseline report found for base model.")
                return info
            if not baseline:
                info["status"] = "Unverified"
                info["issues"].append("No baseline report found for base model.")
                return info

            # Compare
            try:
                test_suite_dir = TRAINING_DATA_DIR / 'Test'
                engine = EvaluationEngine(tests_dir=test_suite_dir)
                policy = get_regression_policy() or {}
                threshold = float(policy.get("alert_drop_percent", 5.0))
                cmp = engine.compare_models(baseline, latest_eval, regression_threshold=threshold, improvement_threshold=threshold)
                delta_str = cmp.get('overall', {}).get('delta', '+0.00%').replace('%', '')
                delta = float(delta_str) if delta_str else 0.0
                info["delta_overall"] = delta
                regs = [r.get('skill') for r in (cmp.get('regressions') or [])]
                info["regressions"] = regs

                if delta >= threshold and not regs:
                    info["status"] = "Ready"
                elif regs:
                    info["status"] = "Regression Detected"
                    info["issues"].append(f"Regressions: {', '.join(regs)}")
                else:
                    info["status"] = "Unverified"
                    info["issues"].append(f"Overall delta below threshold ({delta:.2f}% < {threshold:.2f}%)")
            except Exception as e:
                info["issues"].append(f"Comparison failed: {e}")
        except Exception as e:
            info["issues"].append(f"Readiness check error: {e}")
        return info


    def _populate_history_tab(self, base_model_info):
        """Populate History → Runs and Levels for the selected base model without destroying the tab structure."""
        # Clear content areas only
        for frame in (self.history_runs_frame, self.history_levels_frame):
            for w in frame.winfo_children():
                w.destroy()

        # --- Runs sub-tab ---
        runs_header = ttk.Frame(self.history_runs_frame)
        runs_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(runs_header, text="Training Runs", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(runs_header, text="🔄 Refresh", command=lambda: self._populate_history_tab(base_model_info), style='Select.TButton').pack(side=tk.RIGHT)

        base_model_name = base_model_info["name"]
        base_dir = Path(base_model_info["path"]).parent
        all_training_dirs = list(base_dir.glob("training_*"))

        found = []
        for adapter_dir in all_training_dirs:
            try:
                acfg = adapter_dir / 'adapter_config.json'
                if acfg.exists():
                    with open(acfg, 'r') as f:
                        cfg = json.load(f)
                    if cfg.get('base_model_name_or_path') == base_model_name:
                        found.append(adapter_dir)
            except Exception:
                continue

        if not found:
            ttk.Label(self.history_runs_frame, text="No training history for this base model yet.", style='Config.TLabel').pack(padx=10, pady=10)
        else:
            found = sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)
            canvas = tk.Canvas(self.history_runs_frame, bg="#2b2b2b", highlightthickness=0)
            scrollbar = ttk.Scrollbar(self.history_runs_frame, orient="vertical", command=canvas.yview)
            list_frame = ttk.Frame(canvas)
            list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=list_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y")

            for adapter_dir in found:
                adapter_name = adapter_dir.name
                row = ttk.Frame(list_frame, style='Category.TFrame', borderwidth=1)
                row.pack(fill=tk.X, padx=8, pady=3)
                ttk.Label(row, text=f"🎯 {adapter_name}", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=6, pady=(4, 2))
                # Stats summary
                summary = "Unverified"
                try:
                    stats = get_latest_training_stats(adapter_name)
                    if stats:
                        parts = []
                        if stats.get('epochs') is not None:
                            parts.append(f"Epochs: {stats.get('epochs')}")
                        if 'training_loss' in stats:
                            try:
                                parts.append(f"Loss: {float(stats['training_loss']):.4f}")
                            except Exception:
                                parts.append(f"Loss: {stats['training_loss']}")
                        if 'train_runtime' in stats:
                            try:
                                parts.append(f"Time: {float(stats['train_runtime']):.1f}s")
                            except Exception:
                                parts.append(f"Time: {stats['train_runtime']}")
                        if stats.get('timestamp'):
                            parts.append(f"When: {stats.get('timestamp').split('T')[0]}")
                        summary = " | ".join(parts) if parts else summary
                except Exception:
                    pass
                ttk.Label(row, text=summary, font=("Arial", 9), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=20, pady=(0, 2))

                # Evaluation summary and actions
                eval_line = "Evaluation: Unverified"
                try:
                    base_name = base_model_name
                    baseline = load_baseline_report(base_name) or {}
                    latest = load_latest_evaluation_report(adapter_name) or {}
                    if latest and baseline:
                        engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
                        policy = get_regression_policy() or {}
                        threshold = float(policy.get('alert_drop_percent', 5.0))
                        cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
                        overall = cmp.get('overall', {})
                        new = overall.get('new','N/A'); delta = overall.get('delta','+0.00%')
                        eval_line = f"Evaluation: {new} (Δ {delta})"
                except Exception:
                    pass
                ttk.Label(row, text=eval_line, font=("Arial", 9), style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=20, pady=(0, 6))

                # Action buttons
                actions = ttk.Frame(row)
                actions.grid(row=3, column=0, sticky=tk.W, padx=20, pady=(0,8))
                ttk.Button(actions, text="View Report", style='Select.TButton',
                           command=lambda n=adapter_name: self._history_view_report(n)).pack(side=tk.LEFT, padx=3)
                ttk.Button(actions, text="Compare", style='Select.TButton',
                           command=lambda b=base_model_name, n=adapter_name: self._history_compare_baseline(b, n)).pack(side=tk.LEFT, padx=3)
                ttk.Button(actions, text="Open Folder", style='Select.TButton',
                           command=lambda p=adapter_dir: self._open_folder(p)).pack(side=tk.LEFT, padx=3)

        # --- Levels sub-tab ---
        levels_header = ttk.Frame(self.history_levels_frame)
        levels_header.pack(fill=tk.X, padx=10, pady=(8, 4))
        ttk.Label(levels_header, text="Levels (Archived Sets)", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(levels_header, text="🔄 Refresh", command=lambda: self._populate_history_tab(base_model_info), style='Select.TButton').pack(side=tk.RIGHT)

        levels_list_frame = ttk.Frame(self.history_levels_frame)
        levels_list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)
        levels = self._discover_levels_for_base(base_model_name)
        if not levels:
            ttk.Label(levels_list_frame, text="No levels archived for this base model.", style='Config.TLabel').pack(padx=10, pady=10)
        else:
            for level in sorted(levels, key=lambda d: d.get('created',''), reverse=True):
                lf = ttk.LabelFrame(levels_list_frame, text=level.get('name','(unnamed)'), style='TLabelframe')
                lf.pack(fill=tk.X, padx=5, pady=5)
                ttk.Label(lf, text=f"Created: {level.get('created','')}", style='Config.TLabel').pack(anchor=tk.W, padx=10)
                ttk.Label(lf, text=f"Adapters: {', '.join(a.get('name','') for a in level.get('adapters',[]))}", style='Config.TLabel').pack(anchor=tk.W, padx=10, pady=(0,4))
                btnrow = ttk.Frame(lf)
                btnrow.pack(fill=tk.X, padx=8, pady=4)
                ttk.Button(btnrow, text="Export to GGUF", style='Action.TButton', command=lambda lv=level: self._levels_export_to_gguf(base_model_info, lv)).pack(side=tk.LEFT, padx=4)
                ttk.Button(btnrow, text="Open Folder", style='Select.TButton', command=lambda lv=level: self._levels_open_folder(base_model_name, lv.get('name',''))).pack(side=tk.LEFT, padx=4)

    def _toggle_adapters_select_mode(self, base_model_info):
        # Re-render adapters list to show/hide checkboxes
        self._populate_adapters_tab(base_model_info)

    def _get_selected_adapters(self):
        try:
            return [Path(p) for p, v in self.adapters_selection.items() if v.get()]
        except Exception:
            return []

    def _adapters_select_all(self, state: bool):
        for var in self.adapters_selection.values():
            var.set(bool(state))
        self._adapters_update_actions_state()

    def _adapters_update_actions_state(self):
        selected = self._get_selected_adapters()
        if self.adapters_estimate_btn:
            try:
                self.adapters_estimate_btn.config(state=(tk.NORMAL if selected else tk.DISABLED))
            except Exception:
                pass
        if self.adapters_levelup_btn:
            try:
                self.adapters_levelup_btn.config(state=(tk.NORMAL if len(selected) == 1 else tk.DISABLED))
            except Exception:
                pass
        if hasattr(self, 'adapters_save_level_btn') and self.adapters_save_level_btn:
            try:
                self.adapters_save_level_btn.config(state=(tk.NORMAL if selected else tk.DISABLED))
            except Exception:
                pass

    def _adapters_estimate_size(self):
        selected = self._get_selected_adapters()
        if not selected:
            messagebox.showinfo("Estimate", "Select at least one adapter in Select Mode.")
            return
        # Rough estimate based on base model disk size
        try:
            base_path = Path(self.current_model_info["path"]) if self.current_model_info else None
            base_bytes = 0
            if base_path and base_path.exists():
                for f in base_path.rglob('*'):
                    if f.is_file():
                        base_bytes += f.stat().st_size
            gb = base_bytes / (1024*1024*1024) if base_bytes else 0
            msg = [
                "Parameter count: Same as base (merging LoRA does not add parameters).",
                f"Base HF model size: ~{gb:.2f} GB" if gb else "Base size: unknown",
                "GGUF size estimates (rough):",
                " - q4_k_m: ~30–50% of FP16",
                " - q5_k_m: ~40–60% of FP16",
                " - q8_0: ~70–90% of FP16",
                f"Selected: {', '.join(p.name for p in selected)}",
            ]
            messagebox.showinfo("Estimate", "\n".join(msg))
        except Exception as e:
            messagebox.showerror("Estimate Error", f"Failed to estimate: {e}")

    def _adapters_level_up_selected(self, base_model_info):
        selected = self._get_selected_adapters()
        if len(selected) != 1:
            messagebox.showwarning("Level Up", "Select exactly one adapter in Select Mode to level up.")
            return
        adapter_path = selected[0]
        base_path = base_model_info["path"]
        # Compute readiness and open unified confirm + quant dialog
        readiness = self._compute_adapter_readiness(adapter_path.name, base_model_info["name"])
        self._confirm_quant_and_export(base_model_info["name"], base_path, adapter_path, readiness)

    def _adapters_save_as_level(self, base_model_info):
        from tkinter import simpledialog
        sels = self._get_selected_adapters()
        if not sels:
            messagebox.showinfo("Save as Level", "Select one or more adapters in Select Mode.")
            return
        level_name = simpledialog.askstring("Save as Level", "Enter a level name:")
        if not level_name:
            return
        notes = simpledialog.askstring("Save as Level", "Optional notes:") or ""
        try:
            clean_base = base_model_info["name"].replace('/','_').replace(':','_')
            level_dir = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name
            level_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "name": level_name,
                "base_model": base_model_info["name"],
                "created": __import__('datetime').datetime.now().isoformat(),
                "adapters": [{"name": p.name} for p in sels],
                "notes": notes,
            }
            with open(level_dir / 'manifest.json', 'w') as f:
                json.dump(manifest, f, indent=2)
            messagebox.showinfo("Saved", f"Level '{level_name}' saved.")
            self._populate_history_tab(base_model_info)
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save level: {e}")

    def _discover_levels_for_base(self, base_model_name: str):
        levels = []
        try:
            clean_base = base_model_name.replace('/','_').replace(':','_')
            base_levels_dir = MODELS_DIR / 'archive' / 'levels' / clean_base
            if not base_levels_dir.exists():
                return []
            for d in base_levels_dir.iterdir():
                if not d.is_dir():
                    continue
                mf = d / 'manifest.json'
                if mf.exists():
                    try:
                        with open(mf, 'r') as f:
                            data = json.load(f)
                        data['name'] = d.name
                        data['path'] = str(d)
                        levels.append(data)
                    except Exception:
                        continue
        except Exception:
            return []
        return levels

    def _discover_gguf_exports_for_base(self, base_model_name: str) -> list:
        """
        Find all GGUF exports and Morph variant JSONs under Models/<base>/exports/gguf/
        and Models/<base>/Morph_regex/variants/.
        Returns list of dicts: {name, path, size_mb, type}
        """
        result = []
        try:
            base_dir = MODELS_DIR / base_model_name
            gguf_dir = base_dir / "exports" / "gguf"
            if gguf_dir.exists():
                for gf in sorted(gguf_dir.glob("*.gguf")):
                    try:
                        sz = gf.stat().st_size // (1024 * 1024)
                    except Exception:
                        sz = 0
                    result.append({"name": gf.stem, "path": gf, "size_mb": sz, "type": "gguf"})
            variant_dir = base_dir / "Morph_regex" / "variants"
            if variant_dir.exists():
                for vf in sorted(variant_dir.glob("morph_variant_*.json")):
                    result.append({"name": vf.stem, "path": vf, "size_mb": 0, "type": "variant_json"})
        except Exception:
            pass
        return result

    def _levels_open_folder(self, base_model_name: str, level_name: str):
        try:
            clean_base = base_model_name.replace('/','_').replace(':','_')
            path = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name
            if path.exists():
                __import__('subprocess').run(["xdg-open", str(path)])
        except Exception:
            pass

    def _levels_export_to_gguf(self, base_model_info, level_data: dict):
        adapters = [a.get('name') for a in (level_data.get('adapters') or []) if a.get('name')]
        if not adapters:
            messagebox.showinfo("Export", "No adapters listed in this level.")
            return
        adapter_name = adapters[0]
        if len(adapters) > 1:
            if not messagebox.askyesno("Export", f"Multiple adapters in level. Proceed exporting the first: {adapter_name}?"):
                return
        base_dir = Path(base_model_info["path"]).parent
        adapter_path = base_dir / adapter_name
        if not adapter_path.exists():
            messagebox.showerror("Export", f"Adapter folder not found: {adapter_path}")
            return
        readiness = self._compute_adapter_readiness(adapter_name, base_model_info["name"])
        self._confirm_quant_and_export(base_model_info["name"], base_model_info["path"], adapter_path, readiness, level_name=level_data.get('name'))

    def _confirm_quant_and_export(self, base_model_name: str, base_model_path, adapter_path, readiness: dict, level_name: str = None):
        """Single dialog to show readiness/warnings and let user pick quant with size estimate, then export."""
        try:
            win = tk.Toplevel(self.root)
            win.title("Level Up: Confirm & Export")
            wrapper = ttk.Frame(win)
            wrapper.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Info box (small font, black on white for readability)
            info = scrolledtext.ScrolledText(wrapper, wrap=tk.WORD, font=("Arial", 9), bg="#ffffff", fg="#000000", height=10)
            info.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
            wrapper.rowconfigure(0, weight=1)
            wrapper.columnconfigure(1, weight=1)
            # Compose message
            lines = []
            lines.append(f"Adapter: {adapter_path.name}")
            status = readiness.get('status', 'Unverified')
            lines.append(f"Status: {status}")
            delta = readiness.get('delta_overall')
            lines.append(f"Overall Δ: {delta:.2f}%" if delta is not None else "Overall Δ: N/A")
            issues = readiness.get('issues') or []
            if issues:
                lines.append("Issues:")
                for it in issues:
                    lines.append(f" - {it}")
            lines.append("")
            # Base size + quant notes
            base_est = self._estimate_gguf_size_gb(base_model_path, 'q4_k_m')
            if base_est is not None:
                lines.append(f"Base HF size approx: ~{(base_est/0.4):.2f} GB")
            lines.append("Quantization affects size and quality:")
            lines.append(" - q4_k_m ≈ 30–50% of FP16")
            lines.append(" - q5_k_m ≈ 40–60% of FP16")
            lines.append(" - q8_0  ≈ 70–90% of FP16")
            lines.append("")
            info.insert(1.0, "\n".join(lines))
            info.config(state=tk.DISABLED)

            # Quant picker + live estimate (small black font)
            ttk.Label(wrapper, text="Quantization:", font=("Arial", 9), foreground="#000000").grid(row=1, column=0, sticky=tk.W, padx=(0,6), pady=(8,4))
            quant_var = tk.StringVar(value="q4_k_m")
            combo = ttk.Combobox(wrapper, textvariable=quant_var, values=["q4_k_m","q5_k_m","q8_0"], state='readonly', width=12)
            combo.grid(row=1, column=1, sticky=tk.W, pady=(8,4))
            est_size = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000")
            est_size.grid(row=2, column=0, columnspan=2, sticky=tk.W)
            est_more = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000", justify=tk.LEFT)
            est_more.grid(row=3, column=0, columnspan=2, sticky=tk.W)
            est_perf = ttk.Label(wrapper, text="", font=("Arial", 9), foreground="#000000")
            est_perf.grid(row=4, column=0, columnspan=2, sticky=tk.W)

            def update_est(*_):
                q = quant_var.get()
                g = self._estimate_gguf_size_gb(base_model_path, q)
                if g is not None:
                    est_size.config(text=f"Estimated GGUF size for {q}: ~{g:.2f} GB")
                    # Simple heuristics for runtime RAM and disk needs
                    load_ram = g * 1.2  # ~20% overhead
                    disk_need = g * 2.0 # export temp + headroom
                    quality_notes = {
                        'q4_k_m': 'Smallest, fastest; noticeable quality drop vs q5/q8',
                        'q5_k_m': 'Balanced size/quality; good default if RAM allows',
                        'q8_0':   'Largest; closest to FP16 quality'
                    }
                    note = quality_notes.get(q, 'Quantized weights; quality vs size trade-off')
                    more = (
                        f"Runtime RAM (load) ≈ {load_ram:.2f} GB\n"
                        f"Disk free recommended ≈ {disk_need:.2f} GB during export\n"
                        f"Parameters unchanged; weights quantized to {q.split('_')[0][1:]}-bit"
                        f"\nQuality: {note}"
                    )
                    est_more.config(text=more)
                    # Tokens/sec estimate (CPU)
                    low, high, cores = self._estimate_tokens_per_sec(g, q)
                    if low is not None:
                        est_perf.config(text=f"Estimated tokens/sec (CPU, ~{cores} threads): ~{low:.1f}–{high:.1f} tok/s")
                    else:
                        est_perf.config(text="")
                else:
                    est_size.config(text=f"Estimated GGUF size for {q}: unknown")
                    est_more.config(text="")
                    est_perf.config(text="")
            combo.bind('<<ComboboxSelected>>', update_est)
            update_est()

            # Buttons
            btns = ttk.Frame(wrapper)
            btns.grid(row=5, column=0, columnspan=2, sticky=tk.E, pady=(10,0))
            ttk.Button(btns, text="Cancel", style='Select.TButton', command=win.destroy).pack(side=tk.RIGHT, padx=5)
            def do_export():
                q = quant_var.get()
                win.destroy()
                self._run_merge_and_export(base_model_path, adapter_path, q, base_model_name=base_model_name, level_name=level_name)
            ttk.Button(btns, text="Export", style='Action.TButton', command=do_export).pack(side=tk.RIGHT)
        except Exception as e:
            messagebox.showerror("Export", f"Could not open export dialog: {e}")

    def _estimate_gguf_size_gb(self, base_model_path, quant: str):
        ratios = {"q4_k_m": 0.4, "q5_k_m": 0.5, "q8_0": 0.8}
        ratio = ratios.get(quant, 0.5)
        try:
            base_path = Path(base_model_path)
            total = 0
            if base_path and base_path.exists():
                for f in base_path.rglob('*'):
                    if f.is_file():
                        total += f.stat().st_size
            if total == 0:
                return None
            gb = total / (1024*1024*1024)
            return gb * ratio
        except Exception:
            return None

    def _estimate_tokens_per_sec(self, gguf_size_gb: float, quant: str):
        """Rough CPU tokens/sec estimate based on GGUF size, quant, and CPU cores.
        Returns (low, high, cores) where low/high define a range.
        Heuristic assumes llama.cpp-like threading and AVX2-class CPU.
        """
        try:
            if gguf_size_gb is None or gguf_size_gb <= 0:
                return (None, None, os.cpu_count() or 4)
            # Baseline: for q4_k_m on a 4-core CPU, ~20 tok/s per GB inverse
            # e.g., 0.5 GB -> ~40 tok/s, 4 GB -> ~5 tok/s
            base_per_gb = 20.0
            quant_scale = { 'q4_k_m': 1.0, 'q5_k_m': 0.85, 'q8_0': 0.60 }.get(quant, 0.80)
            cores = os.cpu_count() or 4
            # Scale with threads up to 16 cores with diminishing returns
            core_scale = min(max(1, cores), 16) / 4.0
            est = (base_per_gb / gguf_size_gb) * quant_scale * core_scale
            low = est * 0.7
            high = est * 1.3
            return (low, high, int(cores))
        except Exception:
            return (None, None, os.cpu_count() or 4)

    # --- History helpers ---
    def _history_view_report(self, adapter_name: str):
        """Open a window showing the latest evaluation report for an adapter."""
        try:
            report = load_latest_evaluation_report(adapter_name) or {}
            self._show_json_window(f"Latest Eval: {adapter_name}", report)
        except Exception as e:
            messagebox.showerror("View Report", f"Failed to load report: {e}")

    def _history_compare_baseline(self, base_model_name: str, adapter_name: str):
        try:
            baseline = load_baseline_report(base_model_name) or {}
            latest = load_latest_evaluation_report(adapter_name) or {}
            if not latest or not baseline:
                messagebox.showinfo("Compare", "Missing baseline or evaluation report.")
                return
            engine = EvaluationEngine(tests_dir=TRAINING_DATA_DIR / 'Test')
            policy = get_regression_policy() or {}
            threshold = float(policy.get('alert_drop_percent', 5.0))
            cmp = engine.compare_models(baseline, latest, regression_threshold=threshold, improvement_threshold=threshold)
            self._show_json_window(f"Compare: {adapter_name} vs baseline", cmp)
        except Exception as e:
            messagebox.showerror("Compare", f"Failed to compare: {e}")

    def _open_folder(self, path: Path):
        try:
            __import__('subprocess').run(["xdg-open", str(path)])
        except Exception:
            pass

    def _show_json_window(self, title: str, data: dict):
        """Utility: Show a JSON object in a scrollable window for inspection."""
        try:
            win = tk.Toplevel(self.root)
            win.title(title or 'JSON')
            txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Courier", 9), bg="#1e1e1e", fg="#d4d4d4")
            txt.pack(fill=tk.BOTH, expand=True)
            try:
                payload = json.dumps(data, indent=2)
            except Exception:
                payload = str(data)
            txt.insert(1.0, payload)
            txt.config(state=tk.DISABLED)
        except Exception:
            try:
                messagebox.showerror('View', 'Failed to render JSON window.')
            except Exception:
                pass

    def _show_suggestions_dialog(self, baseline_report: dict, new_report: dict):
        """Displays training suggestions in a new window."""
        try:
            test_suite_dir = TRAINING_DATA_DIR / "Test"
            eval_engine = EvaluationEngine(tests_dir=test_suite_dir)
            suggestions = eval_engine.generate_training_suggestions(baseline_report, new_report)

            win = tk.Toplevel(self.root)
            win.title("Training Suggestions")
            win.transient(self.root) # Make it appear on top of the main window
            win.grab_set() # Make it modal

            frame = ttk.Frame(win)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            ttk.Label(frame, text="💡 Training Suggestions", font=("Arial", 14, "bold"), style='CategoryPanel.TLabel').pack(anchor=tk.W, pady=(0, 10))

            if suggestions.get('error'):
                ttk.Label(frame, text=f"Error generating suggestions: {suggestions['error']}", foreground='red', style='Config.TLabel').pack(anchor=tk.W)
                return

            # Summary
            summary_frame = ttk.LabelFrame(frame, text="Summary", style='TLabelframe')
            summary_frame.pack(fill=tk.X, pady=5)
            for k, v in suggestions.get('summary', {}).items():
                ttk.Label(summary_frame, text=f"{k.replace('_', ' ').title()}: {v}", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Reason Counts
            if suggestions.get('reason_counts'):
                reasons_frame = ttk.LabelFrame(frame, text="Failure Reasons", style='TLabelframe')
                reasons_frame.pack(fill=tk.X, pady=5)
                for k, v in suggestions['reason_counts'].items():
                    ttk.Label(reasons_frame, text=f"{k.replace('_', ' ').title()}: {v}", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Top Failures
            if suggestions.get('top_failures'):
                failures_frame = ttk.LabelFrame(frame, text="Top Failing Test Cases", style='TLabelframe')
                failures_frame.pack(fill=tk.X, pady=5)
                for tf in suggestions['top_failures']:
                    ttk.Label(failures_frame, text=f"- {tf.get('test_case')} (Reason: {tf.get('reason')})", style='Config.TLabel').pack(anchor=tk.W, padx=5)

            # Example Stubs (JSONL)
            if suggestions.get('examples_jsonl'):
                ttk.Label(frame, text="\nExample JSONL Stubs for Retraining:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(anchor=tk.W, pady=(10, 5))
                jsonl_text = scrolledtext.ScrolledText(
                    frame,
                    wrap=tk.WORD,
                    height=10,
                    font=("Courier", 9),
                    bg="#1e1e1e",
                    fg="#d4d4d4"
                )
                jsonl_text.insert(tk.END, suggestions['examples_jsonl'])
                jsonl_text.config(state=tk.DISABLED)
                jsonl_text.pack(fill=tk.BOTH, expand=True)

            ttk.Button(frame, text="Close", command=win.destroy, style='Select.TButton').pack(pady=10)

            self.root.wait_window(win) # Wait for the dialog to close

        except Exception as e:
            messagebox.showerror("Suggestions Error", f"Failed to generate or display suggestions: {e}")
    def display_model_info(self, model_info):
        """Displays information for the selected model (Ollama or local GGUF)."""
        self.current_model_info = model_info
        model_name = model_info["name"]

        # Local GGUF — show file info without querying Ollama
        if model_info.get("type") == "gguf":
            self._display_gguf_info(model_info)
            return

        raw_info = get_ollama_model_info(model_name)
        parsed_info = parse_ollama_model_info(raw_info)

        # Update Raw Info Tab
        self.raw_model_info_text.config(state=tk.NORMAL)
        self.raw_model_info_text.delete(1.0, tk.END)
        self.raw_model_info_text.insert(1.0, raw_info)
        self.raw_model_info_text.config(state=tk.DISABLED)

        # Update Overview Tab
        # Clear previous overview content
        for widget in self.overview_tab_frame.winfo_children():
            widget.destroy()

        # Model Rename Section at the top
        rename_frame = ttk.LabelFrame(self.overview_tab_frame, text="🏷️ Rename Model", style='TLabelframe')
        rename_frame.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)
        rename_frame.columnconfigure(1, weight=1)

        ttk.Label(rename_frame, text="Current Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        name_frame = ttk.Frame(rename_frame)
        name_frame.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        ttk.Label(name_frame, text=model_name, font=("Arial", 10), style='Config.TLabel', foreground='#61dafb').pack(side=tk.LEFT)
        ttk.Button(name_frame, text="📎", command=self._copy_name_to_clipboard, style='Select.TButton', width=2).pack(side=tk.LEFT, padx=5)

        ttk.Label(rename_frame, text="New Name:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        self.rename_entry_var = tk.StringVar()
        rename_entry = ttk.Entry(rename_frame, textvariable=self.rename_entry_var, width=40)
        rename_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)

        # Validation label
        self.rename_validation_label = ttk.Label(rename_frame, text="", font=("Arial", 9), style='Config.TLabel')
        self.rename_validation_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)

        # Buttons
        button_frame = ttk.Frame(rename_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=5)

        ttk.Button(button_frame, text="✓ Validate Name", command=self.validate_model_name, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Rename Model", command=self.rename_model, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Delete Model", command=self.delete_model, style='Action.TButton').pack(side=tk.LEFT, padx=5)

        # Info text
        info_text = "HuggingFace naming rules:\n• Alphanumeric chars, '-', '_', '.' only\n• Cannot start/end with '-' or '.'\n• Max 96 characters\n• No colons (:) or slashes (/)\n\nNote: Ollama will add ':latest' tag automatically.\nThis is normal - it will be stripped during training."
        ttk.Label(rename_frame, text=info_text, font=("Arial", 8), style='Config.TLabel', foreground='#888888').grid(
            row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)

        # Separator
        ttk.Separator(self.overview_tab_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)

        # Training Capability Notice
        cap_frame = ttk.LabelFrame(self.overview_tab_frame, text="Capability", style='TLabelframe')
        cap_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=5)
        ttk.Label(cap_frame, text="Training Capability:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        ttk.Label(cap_frame, text="Inference-only (GGUF via Ollama) — not trainable here. Evaluations supported.", font=("Arial", 10), style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)

        # Bump subsequent content rows
        next_row_base = 3

        # Model Info
        row_num = next_row_base
        for key, value in parsed_info.items():
            ttk.Label(self.overview_tab_frame, text=f"{key.replace('_', ' ').title()}:", font=("Arial", 10, "bold"), style='Config.TLabel').grid(row=row_num, column=0, sticky=tk.W, padx=5, pady=2)
            ttk.Label(self.overview_tab_frame, text=value, font=("Arial", 10), style='Config.TLabel').grid(row=row_num, column=1, sticky=tk.W, padx=5, pady=2)
            row_num += 1

        # Lineage - Try LineageTracker first, then fall back to old method
        lineage_record = None
        lineage_chain = []
        found = None

        # Try new LineageTracker
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent / "tabs" / "custom_code_tab"))
            from lineage_tracker import get_tracker

            tracker = get_tracker()
            if tracker.has_lineage(model_name):
                lineage_record = tracker.get_lineage_record(model_name)
                lineage_chain = tracker.get_lineage_chain(model_name)
        except Exception as e:
            log_message(f"MODELS_TAB: LineageTracker not available: {e}")

        # Fall back to old method if LineageTracker didn't find anything
        if not lineage_record:
            try:
                from config import MODELS_DIR
                base_names = [m['name'] for m in (self.all_models or []) if m.get('type') == 'pytorch']
                for b in base_names:
                    clean_base = b.replace('/','_').replace(':','_')
                    base_levels_dir = MODELS_DIR / 'archive' / 'levels' / clean_base
                    if not base_levels_dir.exists():
                        continue
                    for d in base_levels_dir.iterdir():
                        mf = d / 'manifest.json'
                        if mf.exists():
                            try:
                                with open(mf,'r') as f:
                                    data = json.load(f)
                                for ex in (data.get('exports') or []):
                                    if (ex.get('name') or '') == model_name:
                                        found = { 'base': b, 'level': d.name, 'adapters': [a.get('name') for a in (data.get('adapters') or []) if a.get('name')] }
                                        raise StopIteration
                            except Exception:
                                continue
            except StopIteration:
                pass
            except Exception:
                found = None

        # Display lineage information (from either source)
        if lineage_record or found:
            lin = ttk.LabelFrame(self.overview_tab_frame, text="🧬 Model Lineage", style='TLabelframe')
            lin.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=6)

            if lineage_record:
                # Display from LineageTracker
                current_row = 0

                # Base model info
                ttk.Label(
                    lin,
                    text=f"Base Model: {lineage_record.get('base_model', 'Unknown')}",
                    font=("Arial", 10, "bold"),
                    style='Config.TLabel'
                ).grid(row=current_row, column=0, sticky=tk.W, padx=8, pady=2)

                ttk.Label(
                    lin,
                    text=f"Training Method: {lineage_record.get('training_method', 'Unknown')}",
                    style='Config.TLabel'
                ).grid(row=current_row, column=1, sticky=tk.W, padx=8, pady=2)
                current_row += 1

                # Training date
                training_date = lineage_record.get('training_date', '')
                if training_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(training_date)
                        formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_date = training_date
                    ttk.Label(
                        lin,
                        text=f"Trained: {formatted_date}",
                        style='Config.TLabel'
                    ).grid(row=current_row, column=0, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Training data source
                data_source = lineage_record.get('training_data_source')
                if data_source:
                    ttk.Label(
                        lin,
                        text=f"Training Data: {data_source}",
                        style='Config.TLabel'
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Lineage chain (ancestry)
                if len(lineage_chain) > 1:
                    chain_text = " → ".join([r.get('model_name', 'Unknown') for r in lineage_chain])
                    ttk.Label(
                        lin,
                        text=f"Ancestry: {chain_text}",
                        style='Config.TLabel',
                        wraplength=500
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)
                    current_row += 1

                # Metadata (if any)
                metadata = lineage_record.get('metadata', {})
                if metadata:
                    metadata_str = ", ".join([f"{k}: {v}" for k, v in metadata.items()])
                    ttk.Label(
                        lin,
                        text=f"Metadata: {metadata_str}",
                        style='Config.TLabel',
                        wraplength=500
                    ).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)

            elif found:
                # Display from old method
                ttk.Label(lin, text=f"Parent Base: {found['base']}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=8, pady=2)
                ttk.Label(lin, text=f"Level: {found['level']}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=8, pady=2)
                ttk.Label(lin, text=f"Adapters: {', '.join(found['adapters']) if found['adapters'] else 'None'}", style='Config.TLabel').grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=8, pady=2)

                # Parent baseline and primary adapter evaluation snapshots
                try:
                    from config import load_baseline_report, load_latest_evaluation_report
                    base_bl = load_baseline_report(found['base']) or {}
                    if base_bl:
                        ttk.Label(lin, text=f"Parent Baseline Overall: {base_bl.get('pass_rate_percent','N/A')}", style='Config.TLabel').grid(row=2, column=0, sticky=tk.W, padx=8, pady=2)
                    if found['adapters']:
                        primary = found['adapters'][0]
                        lad = load_latest_evaluation_report(primary) or {}
                        if lad:
                            ttk.Label(lin, text=f"Primary Adapter Eval Overall: {lad.get('pass_rate_percent','N/A')}", style='Config.TLabel').grid(row=2, column=1, sticky=tk.W, padx=8, pady=2)
                except Exception:
                    pass

            row_num += 1

        # Update Notes Tab context
        self.notes_text.delete(1.0, tk.END)
        self.note_name_var.set("")
        self.populate_notes_list()  # Load notes list for this model

        # Update Stats Tab
        self.current_model_for_stats = model_name
        self.populate_stats_display()  # Load stats for this model

        # Behavior indicators for GGUF (if evaluated)
        try:
            from config import get_model_behavior_profile
            prof = get_model_behavior_profile(model_name) or {}
            beh = prof.get('behavior') or {}
            beh_frame = ttk.LabelFrame(self.overview_tab_frame, text="Behavior Indicators", style='TLabelframe')
            beh_frame.grid(row=row_num, column=0, columnspan=2, sticky=tk.EW, padx=5, pady=10)
            ttk.Label(beh_frame, text=f"Compliance: {(beh.get('compliance') or '0.00%')}", style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Creativity: {(beh.get('creativity') or '0.00%')}", style='Config.TLabel').grid(row=0, column=1, sticky=tk.W, padx=10, pady=3)
            ttk.Label(beh_frame, text=f"Coherence: {(beh.get('coherence') or '0.00%')}", style='Config.TLabel').grid(row=0, column=2, sticky=tk.W, padx=10, pady=3)
        except Exception:
            pass

        # Update Selected Model Label in Evaluation Tab
        if hasattr(self, 'selected_model_label_eval'):
            self.selected_model_label_eval.config(text=f"Selected Model: {model_name}")
        if hasattr(self, 'eval_source_label'):
            self.eval_source_label.config(text="Source: Ollama (GGUF)")

    def validate_model_name(self):
        """Validate the proposed model name against HuggingFace rules."""
        new_name = self.rename_entry_var.get().strip()

        if not new_name:
            self.rename_validation_label.config(text="⚠️ Please enter a model name", foreground='#ff6b6b')
            return False

        # HuggingFace validation rules
        import re

        # Check length
        if len(new_name) > 96:
            self.rename_validation_label.config(text="❌ Name too long (max 96 characters)", foreground='#ff6b6b')
            return False

        # Check for forbidden characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', new_name):
            self.rename_validation_label.config(text="❌ Only alphanumeric, '-', '_', '.' allowed", foreground='#ff6b6b')
            return False

        # Check for colons (common mistake from Ollama names)
        if ':' in new_name:
            self.rename_validation_label.config(text="❌ Colons (:) not allowed - remove ':latest' or version tags", foreground='#ff6b6b')
            return False

        # Check for slashes
        if '/' in new_name:
            self.rename_validation_label.config(text="❌ Slashes (/) not allowed - use '-' or '_' instead", foreground='#ff6b6b')
            return False

        # Check for forbidden patterns
        if new_name.startswith('-') or new_name.startswith('.'):
            self.rename_validation_label.config(text="❌ Cannot start with '-' or '.'", foreground='#ff6b6b')
            return False

        if new_name.endswith('-') or new_name.endswith('.'):
            self.rename_validation_label.config(text="❌ Cannot end with '-' or '.'", foreground='#ff6b6b')
            return False

        if '--' in new_name or '..' in new_name:
            self.rename_validation_label.config(text="❌ Cannot contain '--' or '..'", foreground='#ff6b6b')
            return False

        # All checks passed
        self.rename_validation_label.config(text="✅ Valid HuggingFace model name", foreground='#51cf66')
        return True

    def rename_model(self):
        """Rename the selected Ollama model."""
        if not hasattr(self, 'current_model_for_notes') or not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        # Validate name first
        if not self.validate_model_name():
            messagebox.showerror("Invalid Name", "Please fix the validation errors before renaming.")
            return

        old_name = self.current_model_for_notes
        new_name = self.rename_entry_var.get().strip()

        if old_name == new_name:
            messagebox.showinfo("No Change", "New name is the same as the current name.")
            return

        # Confirm with user
        confirm_msg = f"Rename model:\n\nFrom: {old_name}\nTo:   {new_name}\n\nThis will create a copy with the new name. Continue?"
        if not messagebox.askyesno("Confirm Rename", confirm_msg):
            return

        try:
            import subprocess
            import tempfile
            import os

            # Create a Modelfile that references the original model
            # This approach should prevent Ollama from auto-adding :latest
            with tempfile.NamedTemporaryFile(mode='w', suffix='.modelfile', delete=False) as f:
                f.write(f"FROM {old_name}\n")
                modelfile_path = f.name

            try:
                # Create the new model using ollama create with explicit name (no tag)
                result = subprocess.run(
                    ["ollama", "create", new_name, "-f", modelfile_path],
                    capture_output=True,
                    text=True,
                    check=True
                )

                # Clean up the temporary Modelfile
                os.unlink(modelfile_path)

                # Verify what was actually created
                updated_models = get_ollama_models()
                actual_new_name = None

                # Look for the new model (check if :latest was added)
                for model in updated_models:
                    if model == new_name:
                        actual_new_name = new_name
                        break
                    elif model.startswith(f"{new_name}:"):
                        actual_new_name = model
                        break

                if not actual_new_name:
                    # Couldn't find the model, something went wrong
                    messagebox.showerror("Rename Failed", f"Model was created but couldn't be found in model list.\n\nOutput: {result.stdout}\nError: {result.stderr}")
                    return

                if actual_new_name != new_name:
                    # Ollama added :latest (this is expected and OK)
                    messagebox.showinfo(
                        "Rename Successful",
                        f"✅ Model renamed successfully!\n\nOld: {old_name}\nNew: {actual_new_name}\n\nℹ️ Note: Ollama automatically adds ':latest' tag to all models. This is normal behavior and won't affect training - the tag will be automatically stripped when using the model for HuggingFace training.\n\nOriginal model '{old_name}' still exists. You can delete it using the Delete button if needed."
                    )
                else:
                    messagebox.showinfo(
                        "Rename Successful",
                        f"✅ Model renamed successfully!\n\nOld: {old_name}\nNew: {new_name}\n\nNote: Original model '{old_name}' still exists. You can delete it using the Delete button if needed."
                    )

                # Refresh model list
                self.ollama_models = get_ollama_models()
                self.populate_model_list()

                # Clear rename field
                self.rename_entry_var.set("")
                self.rename_validation_label.config(text="")

                # Display the new model
                if actual_new_name in self.ollama_models:
                    self.display_model_info(actual_new_name)

            except subprocess.CalledProcessError as e:
                # Clean up the temporary file
                if os.path.exists(modelfile_path):
                    os.unlink(modelfile_path)
                error_msg = e.stderr if e.stderr else str(e)
                messagebox.showerror("Rename Failed", f"Failed to create model:\n\n{error_msg}")
            except Exception as e:
                # Clean up the temporary file
                if os.path.exists(modelfile_path):
                    os.unlink(modelfile_path)
                raise

        except Exception as e:
            messagebox.showerror("Rename Failed", f"An error occurred:\n\n{str(e)}")

    def delete_trained_model_action(self):
        """Delete the currently selected trained model."""
        if not self.current_model_info or self.current_model_info["type"] != "trained":
            messagebox.showwarning("Invalid Model", "Can only delete trained models.")
            return

        model_name = self.current_model_info["name"]
        model_path = self.current_model_info["path"]

        # Confirm deletion
        confirm_msg = f"⚠️ DELETE TRAINED MODEL?\n\nModel: {model_name}\nPath: {model_path}\n\nThis will permanently delete:\n• The trained model directory\n• All model files\n• Associated training statistics\n\nThis action cannot be undone!\n\nContinue?"
        if not messagebox.askyesno("Confirm Delete", confirm_msg):
            return

        try:
            # Delete the trained model
            if delete_trained_model(model_path):
                messagebox.showinfo("Delete Successful", f"Trained model '{model_name}' has been deleted.")

                # Refresh model list
                self.all_models = get_all_trained_models()
                self.populate_model_list()

                # Clear the overview tab
                for widget in self.overview_tab_frame.winfo_children():
                    widget.destroy()

                ttk.Label(self.overview_tab_frame, text="Select a model to view details",
                         font=("Arial", 12), style='Config.TLabel').pack(pady=20)

                # Clear other tabs
                self.current_model_for_notes = None
                self.current_model_for_stats = None
                self.current_model_info = None
                self.notes_text.delete(1.0, tk.END)
                self.note_name_var.set("")
                self.populate_notes_list()
                self.populate_stats_display()
            else:
                messagebox.showerror("Delete Failed", f"Failed to delete model '{model_name}'.")

        except Exception as e:
            messagebox.showerror("Delete Failed", f"An error occurred:\n\n{str(e)}")

    def _run_merge_and_export(self, base_model_path, adapter_path, quant: str = None, *, base_model_name: str = None, level_name: str = None):
        """Runs the merge_and_export.py script in a separate thread."""
        if not messagebox.askyesno("Confirm Export", f"This will start the GGUF export process for:\n\nAdapter: {adapter_path.name}\n\nThis can take several minutes and consume significant RAM. Continue?"):
            return

        # Find the button to disable it - this is a bit complex
        # For now, we just run the process.

        self.append_runner_output(f"\n--- Starting GGUF Export for {adapter_path.name} ---\n")

        def _find_python_with_unsloth(candidates=None):
            """Search existing interpreters for Unsloth; do not install anything automatically."""
            import subprocess as _sp
            paths = candidates or []
            paths += [sys.executable, shutil.which('python3') or '', shutil.which('python') or '']
            # Common locations for venv/conda
            for root in [str(Path.home() / 'miniconda3' / 'envs'), str(Path.home() / '.pyenv' / 'versions')]:
                p = Path(root)
                if p.exists():
                    for d in p.iterdir():
                        cand = d / 'bin' / 'python'
                        if cand.exists():
                            paths.append(str(cand))
            tested = []
            for pth in [p for p in paths if p]:
                if pth in tested:
                    continue
                tested.append(pth)
                try:
                    out = _sp.check_output([pth, '-c', 'import unsloth,sys;print(sys.executable)'], text=True, stderr=_sp.DEVNULL, timeout=3)
                    return out.strip()
                except Exception:
                    continue
            return None

        def export_thread():
            try:
                # __file__ is Data/tabs/models_tab/models_tab.py; parent.parent.parent is Data/
                script_path = Path(__file__).parent.parent.parent / "merge_and_export.py"
                py_for_unsloth = _find_python_with_unsloth()
                py_exec = py_for_unsloth or sys.executable
                command = [py_exec, str(script_path), "--base", str(base_model_path), "--adapter", str(adapter_path)]
                if quant:
                    command += ["--quant", quant]
                env = os.environ.copy()
                if py_for_unsloth and py_for_unsloth != sys.executable:
                    env["UNSLOTH_PYTHON"] = py_for_unsloth
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                
                gguf_path_emitted = None
                output_buffer = []
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        output_buffer.append(output)
                        # Try to capture GGUF_PATH line
                        if output.startswith('GGUF_PATH:'):
                            try:
                                gguf_path_emitted = output.split(':',1)[1].strip()
                            except Exception:
                                gguf_path_emitted = None
                        self.root.after(0, self.append_runner_output, output)
                
                rc = process.poll()
                if rc == 0:
                    # Create an Ollama model referencing the GGUF
                    try:
                        outdir = Path(gguf_path_emitted).parent if gguf_path_emitted else (Path(__file__).parent.parent.parent / 'exports' / 'gguf')
                        adapter_name = Path(str(adapter_path)).name
                        # Tag the Ollama model after adapter for uniqueness
                        model_tag = f"{adapter_name}:latest"
                        modelfile = outdir / f"{adapter_name}.Modelfile"
                        gguf_path = gguf_path_emitted or str(outdir / f"{Path(base_model_path).name}-merged-{adapter_name}.{quant or 'q4_k_m'}.gguf")
                        mf = f"FROM {gguf_path}\nTEMPLATE \"{{{{ .Prompt }}}}\"\n"
                        Path(modelfile).write_text(mf)
                        create_cmd = ['ollama', 'create', model_tag, '-f', str(modelfile)]
                        self.root.after(0, self.append_runner_output, f"\n--- Creating Ollama model {model_tag} ---\n")
                        cproc = subprocess.Popen(create_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                        while True:
                            l2 = cproc.stdout.readline()
                            if l2 == '' and cproc.poll() is not None:
                                break
                            if l2:
                                self.root.after(0, self.append_runner_output, l2)
                        crc = cproc.poll()
                        if crc == 0:
                            def _done():
                                # Update level manifest with export lineage
                                try:
                                    if base_model_name and level_name:
                                        clean_base = base_model_name.replace('/','_').replace(':','_')
                                        mfpath = MODELS_DIR / 'archive' / 'levels' / clean_base / level_name / 'manifest.json'
                                        if mfpath.exists():
                                            import json as _json
                                            with open(mfpath, 'r') as f:
                                                man = _json.load(f)
                                            ex = man.setdefault('exports', [])
                                            from datetime import datetime
                                            ex.append({
                                                'name': model_tag,
                                                'created': datetime.now().isoformat(),
                                                'gguf_path': gguf_path
                                            })
                                            with open(mfpath, 'w') as f:
                                                _json.dump(man, f, indent=2)
                                except Exception:
                                    pass
                                try:
                                    self.ollama_models = get_ollama_models()
                                    self.populate_model_list()
                                except Exception:
                                    pass
                                # Notify success
                                messagebox.showinfo("Export Complete", f"GGUF export finished and Ollama model created: {model_tag}")
                                # Prompt for rename of Ollama tag
                                try:
                                    from tkinter import simpledialog
                                    new_tag = simpledialog.askstring(
                                        "Rename Model",
                                        "Enter a new Ollama model tag (optional):",
                                        initialvalue=model_tag
                                    )
                                    if new_tag and new_tag.strip() and new_tag.strip() != model_tag:
                                        nt = new_tag.strip()
                                        # Try fast copy-rename; fallback to recreate from Modelfile
                                        try:
                                            rcp = subprocess.run(['ollama', 'cp', model_tag, nt], text=True, capture_output=True)
                                            if rcp.returncode == 0:
                                                subprocess.run(['ollama', 'rm', model_tag], text=True)
                                                # Update manifest export name
                                                try:
                                                    if base_model_name and level_name:
                                                        clean_base2 = base_model_name.replace('/','_').replace(':','_')
                                                        mfpath2 = MODELS_DIR / 'archive' / 'levels' / clean_base2 / level_name / 'manifest.json'
                                                        if mfpath2.exists():
                                                            import json as _json
                                                            with open(mfpath2, 'r') as f:
                                                                man2 = _json.load(f)
                                                            for it in (man2.get('exports') or []):
                                                                if it.get('name') == model_tag:
                                                                    it['name'] = nt
                                                            with open(mfpath2, 'w') as f:
                                                                _json.dump(man2, f, indent=2)
                                                except Exception:
                                                    pass
                                                messagebox.showinfo("Model Renamed", f"Ollama model renamed to: {nt}")
                                            else:
                                                # Fallback: recreate
                                                try:
                                                    subprocess.run(['ollama', 'create', nt, '-f', str(modelfile)], check=True, text=True)
                                                    subprocess.run(['ollama', 'rm', model_tag], text=True)
                                                    messagebox.showinfo("Model Renamed", f"Ollama model renamed to: {nt}")
                                                except Exception as re:
                                                    messagebox.showwarning("Rename Failed", f"Could not rename model: {re}")
                                        except Exception as re:
                                            messagebox.showwarning("Rename Failed", f"Could not rename model: {re}")
                                except Exception:
                                    pass
                            self.root.after(0, _done)
                        else:
                            self.root.after(0, lambda: messagebox.showwarning('Ollama', 'GGUF export complete, but failed to create Ollama model.'))
                    except Exception as e:
                        msg = f"GGUF export complete, but Ollama create failed: {e}"
                        self.root.after(0, lambda m=msg: messagebox.showwarning('Ollama', m))
                else:
                    # Provide clearer error if Unsloth was missing
                    combined = "".join(output_buffer)
                    # Persist full export log for troubleshooting
                    try:
                        from datetime import datetime
                        # __file__ is Data/tabs/models_tab/models_tab.py; parent.parent.parent is Data/
                        log_dir = Path(__file__).parent.parent.parent / 'DeBug'
                        log_dir.mkdir(parents=True, exist_ok=True)
                        log_path = log_dir / f"gguf_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                        log_path.write_text(combined)
                    except Exception:
                        log_path = None
                    if "Unsloth is required for GGUF export" in combined:
                        self.root.after(0, lambda: messagebox.showerror(
                            "Export Failed",
                            "Unsloth is required for GGUF export.\n\nInstall Unsloth or export via another machine with GPU/Unsloth, or use a prebuilt GGUF from Ollama."
                        ))
                    else:
                        tail = combined.splitlines()[-10:]
                        msg = f"GGUF export failed with exit code {rc}.\n\n" + ("\n".join(tail) if tail else "(no output)")
                        if log_path:
                            msg += f"\n\nFull log: {log_path}"
                        self.root.after(0, lambda m=msg: messagebox.showerror("Export Failed", m))

            except Exception as e:
                msg = f"An error occurred: {e}"
                self.root.after(0, lambda m=msg: messagebox.showerror("Export Error", m))

        thread = threading.Thread(target=export_thread)
        thread.daemon = True
        thread.start()

    def _archive_adapter(self, adapter_path: Path):
        """Moves an adapter and its stats to the archive directory."""
        if not messagebox.askyesno("Confirm Archive", f"Archive the adapter '{adapter_path.name}'?"):
            return
        try:
            archive_dir = Path(self.current_model_info["path"]).parent.parent / "archive"
            archive_dir.mkdir(exist_ok=True)

            # Move adapter directory
            adapter_path.rename(archive_dir / adapter_path.name)

            # Move stats file
            stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{adapter_path.name}_stats.json"
            if stats_file.exists():
                stats_file.rename(archive_dir / stats_file.name)

            messagebox.showinfo("Archived", f"Adapter '{adapter_path.name}' has been archived.")
            self.refresh_models_tab()
        except Exception as e:
            messagebox.showerror("Archive Failed", f"Could not archive adapter: {e}")

    def _delete_adapter(self, adapter_path: Path):
        """Deletes an adapter and its stats permanently."""
        if not messagebox.askyesno("⚠️ CONFIRM DELETE ⚠️", f"PERMANENTLY DELETE the adapter '{adapter_path.name}' and its stats?\n\nThis action cannot be undone."):
            return
        try:
            import shutil
            # Delete adapter directory
            shutil.rmtree(adapter_path)

            # Delete stats file
            stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{adapter_path.name}_stats.json"
            if stats_file.exists():
                stats_file.unlink()

            messagebox.showinfo("Deleted", f"Adapter '{adapter_path.name}' has been permanently deleted.")
            self.refresh_models_tab()
        except Exception as e:
            messagebox.showerror("Delete Failed", f"Could not delete adapter: {e}")

    def append_runner_output(self, text):
        """Appends text to the evaluation output console for feedback."""
        self.eval_output_text.config(state=tk.NORMAL)
        self.eval_output_text.insert(tk.END, text)
        self.eval_output_text.see(tk.END)
        self.eval_output_text.config(state=tk.DISABLED)

    def _copy_name_to_clipboard(self):
        """Copies the current model's name to the clipboard."""
        if not self.current_model_info:
            return
        try:
            model_name = self.current_model_info['name']
            self.root.clipboard_clear()
            self.root.clipboard_append(model_name)
            # Give subtle feedback without a disruptive messagebox
            print(f"Copied to clipboard: {model_name}")
        except Exception as e:
            print(f"Failed to copy model name to clipboard: {e}")

    def rename_trained_model_action(self):
        """Renames a trained model folder and all its associated data files."""
        if not self.current_model_info or self.current_model_info["type"] != "trained":
            messagebox.showwarning("Invalid Model", "Can only rename trained models.")
            return

        old_path = Path(self.current_model_info["path"])
        old_name = old_path.name
        new_name = self.trained_rename_entry_var.get().strip()

        if not new_name or new_name == old_name:
            messagebox.showinfo("No Change", "New name is invalid or the same as the current name.")
            return

        new_path = old_path.with_name(new_name)
        if new_path.exists():
            messagebox.showerror("Exists", f"A directory named '{new_name}' already exists.")
            return

        confirm_msg = f"Rename trained model:\n\nFrom: {old_name}\nTo:   {new_name}\n\nThis will rename the folder and all associated data (stats, notes, evals). Continue?"
        if not messagebox.askyesno("Confirm Rename", confirm_msg):
            return

        try:
            # 1. Rename model directory
            old_path.rename(new_path)

            # 2. Rename stats file
            old_stats_file = Path(self.current_model_info["path"]).parent / "training_stats" / f"{old_name}_stats.json"
            if old_stats_file.exists():
                new_stats_file = old_stats_file.with_name(f"{new_name}_stats.json")
                old_stats_file.rename(new_stats_file)

            # 3. Rename notes directory
            old_notes_dir = Path(self.current_model_info["path"]).parent.parent / "model_notes" / old_name
            if old_notes_dir.exists():
                new_notes_dir = old_notes_dir.with_name(new_name)
                old_notes_dir.rename(new_notes_dir)

            # 4. Rename evaluation reports
            evals_dir = Path(self.current_model_info["path"]).parent / "evaluations"
            for report in evals_dir.glob(f"{old_name}_eval_*.json"):
                new_report_name = report.name.replace(old_name, new_name)
                report.rename(report.with_name(new_report_name))

            # 5. Rename baseline report
            baseline_report = Path(self.current_model_info["path"]).parent / "benchmarks" / f"{old_name}_baseline.json"
            if baseline_report.exists():
                new_baseline_name = baseline_report.name.replace(old_name, new_name)
                baseline_report.rename(baseline_report.with_name(new_baseline_name))

            messagebox.showinfo("Rename Successful", f"Model renamed to '{new_name}'.")
            self.refresh_models_tab()

        except Exception as e:
            messagebox.showerror("Rename Failed", f"An error occurred during rename: {e}")
            # Attempt to rollback if something failed mid-way
            if new_path.exists() and not old_path.exists():
                new_path.rename(old_path)
            self.refresh_models_tab()

    def delete_model(self):
        """Delete the selected Ollama model."""
        if not hasattr(self, 'current_model_for_notes') or not self.current_model_for_notes:
            messagebox.showwarning("No Model Selected", "Please select a model first.")
            return

        model_name = self.current_model_for_notes

        # Confirm deletion
        confirm_msg = f"⚠️ DELETE MODEL?\n\nModel: {model_name}\n\nThis will permanently delete the model from Ollama.\n\nThis action cannot be undone!\n\nContinue?"
        if not messagebox.askyesno("Confirm Delete", confirm_msg):
            return

        try:
            import subprocess
            result = subprocess.run(
                ["ollama", "rm", model_name],
                capture_output=True,
                text=True,
                check=True
            )

            messagebox.showinfo("Delete Successful", f"Model '{model_name}' has been deleted.")

            # Refresh model list
            self.ollama_models = get_ollama_models()
            self.populate_model_list()

            # Clear the overview tab
            for widget in self.overview_tab_frame.winfo_children():
                widget.destroy()

            ttk.Label(self.overview_tab_frame, text="Select a model to view details",
                     font=("Arial", 12), style='Config.TLabel').pack(pady=20)

            # Clear other tabs
            self.current_model_for_notes = None
            self.current_model_for_stats = None
            self.notes_text.delete(1.0, tk.END)
            self.note_name_var.set("")
            self.populate_notes_list()
            self.populate_stats_display()

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            messagebox.showerror("Delete Failed", f"Failed to delete model:\n\n{error_msg}")
        except Exception as e:
            messagebox.showerror("Delete Failed", f"An error occurred:\n\n{str(e)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # Ω Inspector — 11th sub-tab of model_info_notebook
    # Populated when an omega or alpha entry is selected in the Morph section.
    # ═══════════════════════════════════════════════════════════════════════════

    _OI_PYMANIFEST   = None   # resolved lazily
    _OI_VARIANTS_DIR = None

    def _oi_variants_dir(self, variants_dir=None):
        """Return variants dir Path (cached after first call)."""
        if variants_dir:
            self._OI_VARIANTS_DIR = variants_dir
        if self._OI_VARIANTS_DIR is None:
            try:
                from config import DATA_DIR
                self._OI_VARIANTS_DIR = DATA_DIR / "pymanifest" / "variants"
            except Exception:
                from pathlib import Path
                self._OI_VARIANTS_DIR = (
                    Path(__file__).parent.parent.parent / "pymanifest" / "variants")
        return self._OI_VARIANTS_DIR

    def _populate_omega_inspector(self, entry: dict, variants_dir=None):
        """Rebuild the Ω Inspector tab for the given spawn_log *entry*."""
        import json as _ji
        import threading as _thi
        from pathlib import Path

        vdir = self._oi_variants_dir(variants_dir)

        # Clear existing content
        for w in self.omega_inspector_frame.winfo_children():
            w.destroy()

        name    = entry.get('name', '')
        tier    = 'omega' if entry.get('event') == 'omega_spawn' else 'alpha'
        domain  = entry.get('domain') or 'general'
        pc      = entry.get('pattern_count', 0)
        script  = entry.get('script', '')

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = ttk.Frame(self.omega_inspector_frame)
        hdr.pack(fill=tk.X, padx=6, pady=(6, 2))

        tier_col = {'omega': '#569cd6', 'alpha': '#4ec9b0'}.get(tier, '#cccccc')
        ttk.Label(hdr, text=f"{name}", font=("Arial", 11, "bold")).pack(side=tk.LEFT)
        ttk.Label(hdr, text=f"  [{tier}]", foreground=tier_col).pack(side=tk.LEFT)
        ttk.Label(hdr, text=f"  {pc:,} patterns",
                  foreground='#858585').pack(side=tk.LEFT, padx=8)

        # Grade badge from lineage_graph if alpha
        if tier == 'alpha':
            try:
                graph = _ji.loads(
                    (vdir / 'lineage_graph.json').read_text())
                node  = graph.get(name, {})
                pg    = node.get('peak_grade', '?')
                sc    = node.get('session_count', 0)
                ttk.Label(hdr, text=f"peak_grade={pg}  sessions={sc}",
                          foreground='#d7ba7d').pack(side=tk.LEFT, padx=4)
            except Exception:
                pass

        # ── Inner 4-tab notebook ────────────────────────────────────────────────
        inner = ttk.Notebook(self.omega_inspector_frame)
        inner.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Tab 1 — Patterns
        f_pat = ttk.Frame(inner)
        inner.add(f_pat, text="Patterns")
        self._build_oi_patterns_tab(f_pat, name, tier, vdir)

        # Tab 2 — Weights
        f_wt = ttk.Frame(inner)
        inner.add(f_wt, text="Weights")
        self._build_oi_weights_tab(f_wt, name, domain, script, vdir)

        # Tab 3 — Regex Chain
        f_rx = ttk.Frame(inner)
        inner.add(f_rx, text="Regex Chain")
        self._build_oi_regex_tab(f_rx, name, script, vdir)

        # Tab 4 — Lineage
        f_lin = ttk.Frame(inner)
        inner.add(f_lin, text="Lineage")
        self._build_oi_lineage_tab(f_lin, name, domain, vdir)

    def _build_oi_patterns_tab(self, parent, name: str, tier: str, vdir):
        """Patterns tab — lazy-load patterns for the selected variant (EXT-2)."""
        import threading as _thi
        import json as _jp

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Filter bar
        fbar = ttk.Frame(parent)
        fbar.grid(row=0, column=0, columnspan=2, sticky=tk.EW, padx=4, pady=(4, 2))
        ttk.Label(fbar, text="Type:").pack(side=tk.LEFT)
        oi_type_var = tk.StringVar(value="(all)")
        type_cb = ttk.Combobox(fbar, textvariable=oi_type_var, width=18, state='readonly')
        type_cb.pack(side=tk.LEFT, padx=2)
        ttk.Label(fbar, text="Domain:").pack(side=tk.LEFT, padx=(6, 2))
        oi_dom_var = tk.StringVar(value="(all)")
        dom_cb = ttk.Combobox(fbar, textvariable=oi_dom_var, width=16, state='readonly')
        dom_cb.pack(side=tk.LEFT, padx=2)
        ttk.Label(fbar, text="SHA:").pack(side=tk.LEFT, padx=(6, 2))
        oi_sha_var = tk.StringVar()
        ttk.Entry(fbar, textvariable=oi_sha_var, width=12).pack(side=tk.LEFT)

        status_var = tk.StringVar(value="Loading…")
        ttk.Label(fbar, textvariable=status_var, foreground='#858585').pack(side=tk.LEFT, padx=8)

        # Treeview
        cols = ('sha', 'type', 'domain', 'seen', 'count')
        tree = ttk.Treeview(parent, columns=cols, show='headings', selectmode='browse', height=16)
        for col, w in zip(cols, (90, 130, 110, 60, 55)):
            tree.heading(col, text=col.title())
            tree.column(col, width=w, stretch=(col == 'type'))
        vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(4, 0), pady=2)
        vsb.grid(row=1, column=1, sticky=tk.NS)

        detail = tk.Text(parent, height=6, state=tk.DISABLED, wrap=tk.WORD,
                         background='#1e1e1e', foreground='#d4d4d4',
                         font=('Consolas', 9))
        detail.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=4, pady=(0, 4))
        parent.rowconfigure(2, minsize=80)

        all_rows = []

        def _filter(*_):
            tf = oi_type_var.get()
            df = oi_dom_var.get()
            sf = oi_sha_var.get().lower()
            filtered = [r for r in all_rows
                        if (tf in ('(all)', '', r[1]))
                        and (df in ('(all)', '', r[2]))
                        and (not sf or sf in r[0].lower())]
            for item in tree.get_children():
                tree.delete(item)
            for r in filtered[:500]:
                tree.insert('', 'end', values=r[:5])

        def _on_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            visible = [r for r in all_rows]  # simplified lookup
            if idx < len(all_rows):
                raw = all_rows[idx][5] if len(all_rows[idx]) > 5 else {}
                detail.config(state=tk.NORMAL)
                detail.delete('1.0', tk.END)
                detail.insert('1.0', _jp.dumps(raw, indent=2))
                detail.config(state=tk.DISABLED)

        tree.bind('<<TreeviewSelect>>', _on_select)
        for var in (oi_type_var, oi_dom_var):
            var.trace_add('write', _filter)
        oi_sha_var.trace_add('write', _filter)

        def _load():
            pfiles = list(vdir.glob(f"patterns*{name}*.json"))
            if not pfiles:
                self.after(0, lambda: status_var.set("No pattern file found."))
                return
            try:
                data = _jp.loads(pfiles[-1].read_text())
                items = list(data.values()) if isinstance(data, dict) else data
            except Exception as e:
                self.after(0, lambda: status_var.set(f"Load error: {e}"))
                return

            seen_t, seen_d = set(), set()
            for rec in items[:500]:
                if isinstance(rec, dict):
                    sha   = str(rec.get('context_hash', rec.get('sha', '')))[:8]
                    ptype = str(rec.get('pattern_type', rec.get('type', '')))
                    dom   = str(rec.get('domain', ''))
                    seen  = str(rec.get('first_seen', ''))[:10]
                    cnt   = str(rec.get('occurrence_count', rec.get('count', '')))
                    all_rows.append((sha, ptype, dom, seen, cnt, rec))
                    seen_t.add(ptype); seen_d.add(dom)

            def _update():
                type_cb['values'] = ['(all)'] + sorted(seen_t)
                dom_cb['values']  = ['(all)'] + sorted(seen_d)
                status_var.set(f"{len(all_rows)} patterns loaded (top 500)")
                _filter()
            self.after(0, _update)

        _thi.Thread(target=_load, daemon=True).start()

    def _build_oi_weights_tab(self, parent, name: str, domain: str,
                               script: str, vdir):
        """Weights tab — scratchpad bar chart + morph_index.jsonl snapshot (EXT-3)."""
        import json as _jw
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            _mpl = True
        except ImportError:
            _mpl = False

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=0)

        # Radio: scratchpad vs morph_index
        src_var = tk.StringVar(value="scratchpad")
        ctrl = ttk.Frame(parent)
        ctrl.grid(row=0, column=0, sticky=tk.NW, padx=4, pady=4)
        ttk.Radiobutton(ctrl, text="Scratchpad weights", variable=src_var,
                        value="scratchpad", command=lambda: _show()).pack(side=tk.LEFT)
        ttk.Radiobutton(ctrl, text="morph_index snapshot", variable=src_var,
                        value="morph_index", command=lambda: _show()).pack(side=tk.LEFT, padx=8)

        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky=tk.NSEW, padx=4, pady=2)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        info_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=info_var, foreground='#858585').grid(
            row=2, column=0, sticky=tk.W, padx=4, pady=2)

        fig_holder = [None, None]  # [Figure, FigureCanvasTkAgg]

        def _show():
            for w in content.winfo_children():
                w.destroy()
            if src_var.get() == "scratchpad":
                _show_scratchpad()
            else:
                _show_morph_index()

        def _show_scratchpad():
            sp_path = vdir / "scratch_pad.json"
            if not sp_path.exists():
                ttk.Label(content, text="scratch_pad.json not found").pack()
                return
            try:
                data = _jw.loads(sp_path.read_text())
            except Exception as e:
                ttk.Label(content, text=f"Load error: {e}").pack()
                return

            grade_map = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "F": 0.0}
            # Filter by domain if alpha
            domains_show = [domain] if domain and domain in data else list(
                k for k in data if not k.startswith('_'))
            sums, all_items = {}, []
            for d in domains_show:
                items = data.get(d, [])
                if isinstance(items, list):
                    s = 0.0
                    for it in items:
                        w  = float(it.get('weight', 0))
                        g  = str(it.get('meta', {}).get('grade', it.get('grade', 'D'))).upper()
                        s += w * grade_map.get(g, 0.5)
                        all_items.append((d, it.get('id', '')[:10], it.get('type', ''),
                                          w, it.get('ttl', ''), g))
                    sums[d] = s

            if _mpl:
                content.columnconfigure(0, weight=1)
                content.rowconfigure(0, weight=2)
                content.rowconfigure(1, weight=1)
                pf = ttk.Frame(content)
                pf.grid(row=0, column=0, sticky=tk.NSEW)
                pf.columnconfigure(0, weight=1); pf.rowconfigure(0, weight=1)
                fig = Figure(figsize=(6, 2.5), facecolor='#1a1a2e')
                ax  = fig.add_subplot(111, facecolor='#1a1a2e')
                ax.barh(list(sums.keys()), list(sums.values()), color='#4ec9b0')
                ax.set_title('Scratchpad Weight Sums', color='#cccccc', fontsize=9)
                ax.tick_params(colors='#cccccc', labelsize=8)
                fig.tight_layout(pad=0.5)
                canvas = FigureCanvasTkAgg(fig, master=pf)
                canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)
                canvas.draw()
                fig_holder[:] = [fig, canvas]

            cols2 = ('domain', 'id', 'type', 'weight', 'ttl', 'grade')
            tree2 = ttk.Treeview(content, columns=cols2, show='headings', height=8)
            for c2, w2 in zip(cols2, (80, 90, 80, 60, 40, 45)):
                tree2.heading(c2, text=c2.title())
                tree2.column(c2, width=w2, stretch=(c2 == 'id'))
            for row in all_items[:300]:
                tree2.insert('', 'end', values=(row[0], row[1], row[2],
                                                 f"{row[3]:.3f}", row[4], row[5]))
            vsb5 = ttk.Scrollbar(content, orient='vertical', command=tree2.yview)
            tree2.configure(yscrollcommand=vsb5.set)
            r_idx = 1 if _mpl else 0
            tree2.grid(row=r_idx, column=0, sticky=tk.NSEW, padx=(4, 0))
            vsb5.grid(row=r_idx, column=1, sticky=tk.NS)
            info_var.set(f"{len(all_items)} scratchpad items shown")

        def _show_morph_index():
            mi_path = vdir / "morph_index.jsonl"
            if not mi_path.exists():
                ttk.Label(content, text="morph_index.jsonl not found").pack()
                return
            entry_data = {}
            try:
                for line in mi_path.read_text().splitlines():
                    if line.strip():
                        e = _jw.loads(line)
                        if e.get('name') == name:
                            entry_data = e
            except Exception:
                pass
            if not entry_data:
                ttk.Label(content, text=f"No morph_index entry for '{name}'").pack()
                return
            lf = ttk.LabelFrame(content, text="morph_index snapshot", padding=8)
            lf.pack(fill=tk.X, padx=4, pady=4)
            for k, v in entry_data.items():
                r = ttk.Frame(lf)
                r.pack(fill=tk.X, pady=1)
                ttk.Label(r, text=f"{k}:", width=28, foreground='#858585').pack(side=tk.LEFT)
                ttk.Label(r, text=str(v), wraplength=320).pack(side=tk.LEFT, padx=4)
            info_var.set("morph_index.jsonl entry displayed")

        _show()

    def _build_oi_regex_tab(self, parent, name: str, script: str, vdir):
        """Regex Chain tab — morph_regex_index from build JSON or Morph_regex/ scan (EXT-4)."""
        import json as _jr
        from pathlib import Path

        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Regex chain from build JSON morph_regex_index:",
                  foreground='#858585').grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)

        cols = ('regex_id', 'domain', 'ptype', 'sha', 'audit')
        tree = ttk.Treeview(parent, columns=cols, show='headings', height=14)
        for col, w in zip(cols, (100, 90, 110, 90, 60)):
            tree.heading(col, text=col.title())
            tree.column(col, width=w, stretch=(col == 'regex_id'))
        vsb = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(4, 0))
        vsb.grid(row=1, column=1, sticky=tk.NS)

        detail = tk.Text(parent, height=5, state=tk.DISABLED, wrap=tk.WORD,
                         background='#1e1e1e', foreground='#d4d4d4', font=('Consolas', 9))
        detail.grid(row=2, column=0, columnspan=2, sticky=tk.EW, padx=4, pady=(0, 4))
        parent.rowconfigure(2, minsize=70)

        rows_rx = []

        def _on_rx_select(event=None):
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            if idx < len(rows_rx):
                detail.config(state=tk.NORMAL)
                detail.delete('1.0', tk.END)
                detail.insert('1.0', _jr.dumps(rows_rx[idx], indent=2))
                detail.config(state=tk.DISABLED)

        tree.bind('<<TreeviewSelect>>', _on_rx_select)

        # Load from build JSON
        if script:
            try:
                bj = vdir / f"build_{script.replace('.py', '')}.json"
                if bj.exists():
                    bdata = _jr.loads(bj.read_text())
                    rx_idx = bdata.get('morph_regex_index', {})
                    for k, v in (rx_idx.items() if isinstance(rx_idx, dict) else enumerate(rx_idx)):
                        rows_rx.append({'regex_id': str(k), 'domain': str(v.get('domain', '') if isinstance(v, dict) else ''),
                                        'ptype': str(v.get('pattern_type', '') if isinstance(v, dict) else ''),
                                        'sha': str(v.get('sha', '') if isinstance(v, dict) else '')[:12],
                                        'audit': str(v.get('audit_status', '') if isinstance(v, dict) else '')})
            except Exception:
                pass

        if not rows_rx:
            tree.insert('', 'end', values=('(no morph_regex_index in build JSON)',
                                            '', '', '', ''))
        else:
            for r in rows_rx:
                tree.insert('', 'end', values=(r['regex_id'], r['domain'],
                                                r['ptype'], r['sha'], r['audit']))

    def _build_oi_lineage_tab(self, parent, name: str, domain: str, vdir):
        """Lineage tab — back-propagated chain + superposition view (EXT-5)."""
        import json as _jl

        parent.columnconfigure(0, minsize=250)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(0, weight=1)

        # ── LEFT: back-propagated chain ────────────────────────────────────────
        left = ttk.LabelFrame(parent, text="Back-Propagated Chain", padding=4)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(4, 2), pady=4)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(0, weight=1)

        tier_col = {'omega': '#569cd6', 'alpha': '#4ec9b0',
                    'fix': '#d7ba7d', 'ancestor': '#858585', 'mutant': '#e68aff'}
        c_lin = ('tier', 'gen', 'patterns', 'grade')
        lin_tree = ttk.Treeview(left, columns=c_lin, show='tree headings',
                                 selectmode='browse', height=20)
        lin_tree.heading('#0',       text='Name')
        lin_tree.heading('tier',     text='Tier')
        lin_tree.heading('gen',      text='Gen')
        lin_tree.heading('patterns', text='Pats')
        lin_tree.heading('grade',    text='Grade')
        lin_tree.column('#0',        width=110, stretch=True)
        for c, w in zip(c_lin, (50, 32, 55, 40)):
            lin_tree.column(c, width=w, stretch=False)
        vsb_l = ttk.Scrollbar(left, orient='vertical', command=lin_tree.yview)
        lin_tree.configure(yscrollcommand=vsb_l.set)
        lin_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb_l.grid(row=0, column=1, sticky=tk.NS)

        # Load lineage graph and walk back from name to root
        graph = {}
        pc_map = {}
        try:
            graph = _jl.loads((vdir / 'lineage_graph.json').read_text())
        except Exception:
            pass
        try:
            for line in (vdir / 'spawn_log.jsonl').read_text().splitlines():
                if line.strip():
                    e = _jl.loads(line)
                    if e.get('name'):
                        pc_map[e['name']] = e.get('pattern_count', 0)
        except Exception:
            pass

        # Build ancestor chain: walk parent links
        chain = []
        cur = name
        visited = set()
        while cur and cur not in visited:
            visited.add(cur)
            node = graph.get(cur, {})
            chain.append((cur, node))
            cur = node.get('parent')

        for node_name, node in chain:
            t   = node.get('tier', 'ancestor')
            gen = node.get('generation', '')
            pc  = pc_map.get(node_name, '')
            pg  = node.get('peak_grade', '')
            iid = lin_tree.insert('', 'end', text=node_name,
                                   values=(t[:6], gen, pc, pg or ''),
                                   tags=(t,))
            try:
                lin_tree.tag_configure(t, foreground=tier_col.get(t, '#cccccc'))
            except Exception:
                pass

        # ── RIGHT: superposition view ──────────────────────────────────────────
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky=tk.NSEW, padx=(2, 4), pady=4)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctrl2 = ttk.Frame(right)
        ctrl2.grid(row=0, column=0, sticky=tk.EW, padx=2, pady=(2, 4))
        ttk.Label(ctrl2, text="Turn:").pack(side=tk.LEFT)
        turn_var = tk.IntVar(value=0)
        summary_var   = tk.StringVar(value="")
        query_var     = tk.StringVar(value="")

        c_sup = ('step', 'pid', 'type', 'domain', 'weight')
        sup_tree = ttk.Treeview(right, columns=c_sup, show='headings', height=14)
        for c, w in zip(c_sup, (38, 110, 110, 90, 58)):
            sup_tree.heading(c, text='Pattern ID' if c == 'pid' else c.title())
            sup_tree.column(c, width=w, stretch=(c == 'pid'))
        vsb_r = ttk.Scrollbar(right, orient='vertical', command=sup_tree.yview)
        sup_tree.configure(yscrollcommand=vsb_r.set)
        sup_tree.grid(row=1, column=0, sticky=tk.NSEW, padx=(2, 0))
        vsb_r.grid(row=1, column=1, sticky=tk.NS)
        ttk.Label(right, textvariable=query_var, foreground='#cccccc',
                  wraplength=400).grid(row=2, column=0, sticky=tk.EW, padx=2, pady=2)
        ttk.Label(right, textvariable=summary_var, foreground='#4ec9b0').grid(
            row=3, column=0, sticky=tk.EW, padx=2, pady=(0, 4))

        def _load_turn(idx):
            for item in sup_tree.get_children():
                sup_tree.delete(item)
            sess_path = vdir / 'session_state.json'
            if not sess_path.exists():
                summary_var.set("session_state.json not found")
                return
            try:
                ss    = _jl.loads(sess_path.read_text())
                turns = ss.get('turn_history', [])
            except Exception:
                return
            # Filter to this domain for alphas
            filtered = [t for t in turns if t.get('domain') == domain] if domain else turns
            spin.config(to=max(0, len(filtered) - 1))
            if idx >= len(filtered):
                summary_var.set(f"Turn {idx} out of range ({len(filtered)} for domain={domain})")
                return
            turn    = filtered[idx]
            pids    = turn.get('activated_pids', [])
            grade   = turn.get('grade', '?')
            gap     = turn.get('gap', '?')
            td      = turn.get('domain', '?')
            query_var.set(str(turn.get('user', ''))[:120])
            for step, pid in enumerate(pids):
                sup_tree.insert('', 'end', values=(step, str(pid)[:12], '', td, ''))
            summary_var.set(f"grade={grade}  gap={gap}  domain={td}  pids={len(pids)}")

        spin = ttk.Spinbox(ctrl2, from_=0, to=50, textvariable=turn_var, width=5,
                           command=lambda: _load_turn(turn_var.get()))
        spin.pack(side=tk.LEFT, padx=4)
        ttk.Label(ctrl2, textvariable=query_var, foreground='#858585',
                  wraplength=300).pack(side=tk.LEFT, padx=4)

        _load_turn(0)
