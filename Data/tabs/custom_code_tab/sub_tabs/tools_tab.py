"""
Tools Tab - Tool management and configuration
Manages which tools are enabled for chat interactions
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class ToolsTab(BaseTab):
    """Tools configuration and management tab"""

    # Context Providers: pre-prompt context injectors (NOT model-callable tools)
    # Toggling these enables/disables Omega context sources in chat_interface_tab
    CONTEXT_PROVIDERS = {
        "omega_ground": {
            "label": "Omega Grounding",
            "desc":  "OsToolkitGroundingBridge → gap_severity, probe_failures, hot_spots",
            "source": "OsToolkitGroundingBridge",
        },
        "task_context": {
            "label": "Active Task Context",
            "desc":  "Reads task_context_{tid}.json for the active task from planner board",
            "source": "task_context_json",
        },
        "temporal_narrative": {
            "label": "Temporal Narrative",
            "desc":  "TemporalNarrativeEngine.explain('last 24h') → dominant_domain + hot files",
            "source": "TemporalNarrativeEngine",
        },
        "biosphere_snapshot": {
            "label": "Biosphere Snapshot",
            "desc":  "biosphere_manifest.json entity catalog → ecosystem context",
            "source": "biosphere_manifest_json",
        },
        "latest_diffs": {
            "label": "Latest Diffs",
            "desc":  "Last 5 enriched_changes: verb / risk / context_class / risk_reasons",
            "source": "version_manifest.enriched_changes",
        },
    }

    # Os_Toolkit subcommands as context injectors (cached per task, not per message)
    OS_TOOLKIT_CONTEXT_TOOLS = {
        "ostk_assess": {
            "label": "assess <wherein>",
            "desc":  "Pre-change impact: blast radius + risk warnings for active task file",
            "arg":   ["assess"],
            "needs_wherein": True,
        },
        "ostk_todo": {
            "label": "todo view",
            "desc":  "Active task inbox + priority queue from todos.json",
            "arg":   ["todo", "view"],
            "needs_wherein": False,
        },
        "ostk_query": {
            "label": "query <wherein>",
            "desc":  "Call graph + change history for active task file",
            "arg":   ["query", "--graph"],
            "needs_wherein": True,
        },
        "ostk_explain": {
            "label": "explain 24h",
            "desc":  "Natural language summary of what was worked on in last 24h",
            "arg":   ["explain", "--last", "24h"],
            "needs_wherein": False,
        },
    }

    # Available OpenCode tools from tools.py
    AVAILABLE_TOOLS = {
        "File Operations": {
            "file_read": {"name": "File Read", "desc": "Read file contents", "risk": "SAFE"},
            "file_write": {"name": "File Write", "desc": "Write/create files", "risk": "MEDIUM"},
            "file_edit": {"name": "File Edit", "desc": "Edit existing files", "risk": "MEDIUM"},
            "file_copy": {"name": "File Copy", "desc": "Copy files", "risk": "LOW"},
            "file_move": {"name": "File Move", "desc": "Move/rename files", "risk": "MEDIUM"},
            "file_delete": {"name": "File Delete", "desc": "Delete files", "risk": "HIGH"},
            "file_create": {"name": "File Create", "desc": "Create empty files", "risk": "LOW"},
            "file_fill": {"name": "File Fill", "desc": "Fill file with content", "risk": "MEDIUM"},
        },
        "Search & Discovery": {
            "grep_search": {"name": "Grep Search", "desc": "Search file contents", "risk": "SAFE"},
            "file_search": {"name": "File Search", "desc": "Find files by name/pattern", "risk": "SAFE"},
            "directory_list": {"name": "Directory List", "desc": "List directory contents", "risk": "SAFE"},
        },
        "Execution": {
            "bash_execute": {"name": "Bash Execute", "desc": "Run shell commands", "risk": "CRITICAL"},
            "git_operations": {"name": "Git Operations", "desc": "Git commands", "risk": "MEDIUM"},
        },
        "System": {
            "system_info": {"name": "System Info", "desc": "Get system information", "risk": "SAFE"},
            "change_directory": {"name": "Change Directory", "desc": "Change working directory", "risk": "LOW"},
            "resource_request": {"name": "Resource Request", "desc": "Request system resources", "risk": "LOW"},
            "think_time": {"name": "Think Time", "desc": "Pause execution to think or plan", "risk": "MEDIUM"}
        },
        "Os_Toolkit": {
            "ostk_todo_view": {"name": "Todo View", "desc": "View project tasks and todos", "risk": "SAFE"},
            "ostk_assess": {"name": "Assess File", "desc": "Assess file change impact + blast radius", "risk": "SAFE"},
            "ostk_query": {"name": "Query File", "desc": "Query file context + call graph", "risk": "SAFE"},
            "ostk_explain": {"name": "Explain Recent", "desc": "Explain recent activity narrative", "risk": "SAFE"},
            "ostk_latest": {"name": "Latest Report", "desc": "Get latest project report", "risk": "SAFE"},
        }
    }

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.tool_vars = {}          # {tool_key: BooleanVar}
        self.context_provider_vars = {}  # {provider_key: BooleanVar}
        self.ostk_tool_vars = {}         # {ostk_key: BooleanVar}
        self.load_tool_settings()

    def create_ui(self):
        """Create the tools configuration UI"""
        log_message("TOOLS_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🔧 Tool Configuration",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="💾 Save Settings",
            command=self.save_tool_settings,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame,
            text="🔄 Reset to Defaults",
            command=self.reset_to_defaults,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # Main notebook: Page 1 = Tool Config, Page 2 = Consolidated Tools
        self.main_notebook = ttk.Notebook(self.parent)
        self.main_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        self.bind_sub_notebook(self.main_notebook, label='Tools')

        # ── Page 1: Tool Config ────────────────────────────────────────────────
        page1 = ttk.Frame(self.main_notebook, style='Category.TFrame')
        self.main_notebook.add(page1, text="🔧 Tool Config")
        page1.columnconfigure(0, weight=1)
        page1.rowconfigure(0, weight=1)

        list_container = ttk.Frame(page1, style='Category.TFrame')
        list_container.grid(row=0, column=0, sticky=tk.NSEW)
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.tools_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.tools_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.tools_canvas.yview
        )
        self.tools_scroll_frame = ttk.Frame(self.tools_canvas, style='Category.TFrame')

        self.tools_scroll_frame.bind(
            "<Configure>",
            lambda e: self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))
        )

        self.tools_canvas_window = self.tools_canvas.create_window(
            (0, 0),
            window=self.tools_scroll_frame,
            anchor="nw"
        )
        self.tools_canvas.configure(yscrollcommand=self.tools_scrollbar.set)

        self.tools_canvas.bind(
            "<Configure>",
            lambda e: self.tools_canvas.itemconfig(self.tools_canvas_window, width=e.width)
        )

        self.tools_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.tools_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Create tool categories (model-callable)
        self.create_tool_categories()

        # Context Provider section (pre-prompt injectors for Omega Gate)
        self.create_context_provider_section()

        # Os_Toolkit context tools section
        self.create_os_toolkit_context_section()

        # AoE Vector transparency panel
        self.create_aoe_vector_section()

        # ── Page 2: Consolidated Tools ────────────────────────────────────────
        page2 = ttk.Frame(self.main_notebook, style='Category.TFrame')
        self.main_notebook.add(page2, text="📦 Consolidated Tools")
        self.create_consolidated_tools_page(page2)

        log_message("TOOLS_TAB: UI created successfully")

    def create_tool_categories(self):
        """Create tool category sections with checkboxes"""
        for category, tools in self.AVAILABLE_TOOLS.items():
            # Category frame
            category_frame = ttk.LabelFrame(
                self.tools_scroll_frame,
                text=f"📂 {category}",
                style='TLabelframe'
            )
            category_frame.pack(fill=tk.X, padx=5, pady=5)

            # Tools in this category
            for tool_key, tool_info in tools.items():
                tool_row = ttk.Frame(category_frame, style='Category.TFrame')
                tool_row.pack(fill=tk.X, padx=10, pady=2)

                # Checkbox
                var = tk.BooleanVar(value=self.tool_vars.get(tool_key, tk.BooleanVar(value=True)).get())
                self.tool_vars[tool_key] = var

                cb = ttk.Checkbutton(
                    tool_row,
                    text=tool_info['name'],
                    variable=var,
                    style='Category.TCheckbutton'
                )
                cb.pack(side=tk.LEFT, padx=(0, 10))

                # Description
                desc_label = ttk.Label(
                    tool_row,
                    text=tool_info['desc'],
                    style='Config.TLabel',
                    font=("Arial", 9)
                )
                desc_label.pack(side=tk.LEFT, padx=(0, 10))

                # Risk indicator
                risk_color = {
                    'SAFE': '#98c379',
                    'LOW': '#61dafb',
                    'MEDIUM': '#e5c07b',
                    'HIGH': '#e06c75',
                    'CRITICAL': '#ff6b6b'
                }.get(tool_info['risk'], '#ffffff')

                risk_label = tk.Label(
                    tool_row,
                    text=tool_info['risk'],
                    font=("Arial", 8, "bold"),
                    bg='#2b2b2b',
                    fg=risk_color
                )
                risk_label.pack(side=tk.RIGHT, padx=5)

    def create_context_provider_section(self):
        """Create Context Providers section (Omega Gate toggles — NOT model-callable tools)."""
        section_frame = ttk.LabelFrame(
            self.tools_scroll_frame,
            text="⚡ Context Providers  (feeds ⚡ Task Watcher in chat tab)",
            style='TLabelframe'
        )
        section_frame.pack(fill=tk.X, padx=5, pady=10)

        ttk.Label(
            section_frame,
            text="Enable context sources to inject Omega grounding into the system prompt when Task Watcher is ON.",
            font=("Arial", 8),
            style='Config.TLabel',
            wraplength=500,
        ).pack(anchor=tk.W, padx=10, pady=(5, 3))

        for provider_key, provider_info in self.CONTEXT_PROVIDERS.items():
            row = ttk.Frame(section_frame, style='Category.TFrame')
            row.pack(fill=tk.X, padx=10, pady=2)

            var = self.context_provider_vars.get(provider_key, tk.BooleanVar(value=False))
            self.context_provider_vars[provider_key] = var

            ttk.Checkbutton(
                row,
                text=provider_info['label'],
                variable=var,
                command=self.save_tool_settings,
                style='Category.TCheckbutton'
            ).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(
                row,
                text=provider_info['desc'],
                font=("Arial", 9),
                style='Config.TLabel'
            ).pack(side=tk.LEFT, padx=(0, 10))

            tk.Label(
                row,
                text=f"src:{provider_info['source']}",
                font=("Arial", 7),
                bg='#2b2b2b',
                fg='#555577'
            ).pack(side=tk.RIGHT, padx=5)

    def create_os_toolkit_context_section(self):
        """Os_Toolkit subcommands as cached context injectors (run once per task, not per message)."""
        section_frame = ttk.LabelFrame(
            self.tools_scroll_frame,
            text="🔧 Os_Toolkit Context Tools  (cached per task — runs on Task Watcher ON or task switch)",
            style='TLabelframe'
        )
        section_frame.pack(fill=tk.X, padx=5, pady=(0, 10))

        ttk.Label(
            section_frame,
            text="Enable Os_Toolkit subcommands to inject grounding context (assess, todo, query, explain). Results cached until active task changes.",
            font=("Arial", 8),
            style='Config.TLabel',
            wraplength=500,
        ).pack(anchor=tk.W, padx=10, pady=(5, 3))

        for tool_key, tool_info in self.OS_TOOLKIT_CONTEXT_TOOLS.items():
            row = ttk.Frame(section_frame, style='Category.TFrame')
            row.pack(fill=tk.X, padx=10, pady=2)

            var = self.ostk_tool_vars.get(tool_key, tk.BooleanVar(value=False))
            self.ostk_tool_vars[tool_key] = var

            ttk.Checkbutton(
                row,
                text=tool_info['label'],
                variable=var,
                command=self.save_tool_settings,
                style='Category.TCheckbutton'
            ).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(
                row,
                text=tool_info['desc'],
                font=("Arial", 9),
                style='Config.TLabel'
            ).pack(side=tk.LEFT)

    # AoE layer → source system callgraph (static, reflects actual data flow)
    LAYER_SOURCES = {
        "attribution":     {"source": "version_manifest.json → enriched_changes",  "feeder": "recovery_util.register_event() → logger_util.log_change_attribution()", "path": "Data/backup/version_manifest.json",      "wired": True},
        "version_health":  {"source": "version_manifest.json → versions[]",          "feeder": "recovery_util.mark_version_stable/unstable()",                            "path": "Data/backup/version_manifest.json",      "wired": True},
        "ux_baseline":     {"source": "UX_EVENT_LOG",                                "feeder": "base_tab.safe_command() → ux_event_log.json",                             "path": "Data/backup/ux_event_log.json",          "wired": True},
        "code_profile":    {"source": "py_manifest.json",                            "feeder": "py_manifest_augmented.py → AST scan",                                     "path": "babel_data/py_manifest.json",            "wired": True},
        "query_weights":   {"source": "task_context_{tid}.json → query_weights_data","feeder": "planner_tab._do_sync() + GapAnalyzer",                                     "path": "Data/plans/Tasks/task_context_{tid}.json","wired": True},
        "morph_opinion":   {"source": "task_context_{tid}.json → morph_opinion_data","feeder": "activity_integration_bridge.py → morph_opinion_data",                     "path": "Data/plans/Tasks/task_context_{tid}.json","wired": True},
        "temporal_aoe":    {"source": "history_temporal_manifest.json",              "feeder": "filesync_temporal + debug_log scan",                                       "path": "babel_data/timeline/manifests/",          "wired": True},
        "weight_engine":   {"source": "CDALS_v3 (unwired)",                          "feeder": "—",                                                                        "path": "—",                                       "wired": False},
        "morphological":   {"source": "universal_taxonomy (unwired)",                "feeder": "—",                                                                        "path": "—",                                       "wired": False},
        "business_domain": {"source": "brain.py (unwired)",                          "feeder": "—",                                                                        "path": "—",                                       "wired": False},
        "graph_topology":  {"source": "biosphere + py_manifest (unwired)",           "feeder": "—",                                                                        "path": "—",                                       "wired": False},
    }

    def create_aoe_vector_section(self):
        """Collapsible AoE Vector transparency panel — shows 11 layers + 92 vectors with source callgraph."""
        # Collapsible wrapper
        self._aoe_collapsed = True
        outer = ttk.LabelFrame(
            self.tools_scroll_frame,
            text="📊 AoE Context Vectors  (click ▶ to expand — 11 layers, 92 vectors, read-only)",
            style='TLabelframe'
        )
        outer.pack(fill=tk.X, padx=5, pady=(0, 10))

        toggle_btn = ttk.Button(
            outer,
            text="▶ Show AoE Vector Callgraph",
            command=lambda: self._toggle_aoe_panel(toggle_btn, aoe_body),
            style='Select.TButton'
        )
        toggle_btn.pack(anchor=tk.W, padx=10, pady=5)

        aoe_body = ttk.Frame(outer, style='Category.TFrame')
        # Start collapsed — body not packed

        # Load aoe_vector_config.json
        _cfg_path = Path(__file__).parents[4] / "Data" / "plans" / "aoe_vector_config.json"
        try:
            _cfg = json.loads(_cfg_path.read_text(encoding="utf-8")) if _cfg_path.exists() else {}
        except Exception:
            _cfg = {}
        _layers = _cfg.get("layers", {})

        # Status label (shown when row selected)
        self._aoe_status_var = tk.StringVar(value="Click a layer to see feeder path")
        ttk.Label(
            outer,
            textvariable=self._aoe_status_var,
            font=("Courier", 8),
            style='Config.TLabel',
            foreground='#6699cc'
        ).pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Treeview inside body (deferred to expand)
        self._aoe_cfg = _cfg
        self._aoe_body = aoe_body
        self._aoe_outer = outer

    def _toggle_aoe_panel(self, btn, body):
        """Toggle show/hide of AoE body; build tree on first expand."""
        if self._aoe_collapsed:
            self._aoe_collapsed = False
            btn.config(text="▼ Hide AoE Vector Callgraph")
            body.pack(fill=tk.X, padx=5, pady=(0, 5))
            if not body.winfo_children():
                self._build_aoe_tree(body)
        else:
            self._aoe_collapsed = True
            btn.config(text="▶ Show AoE Vector Callgraph")
            body.pack_forget()

    def _build_aoe_tree(self, parent_frame):
        """Build TreeView of layers + vectors from aoe_vector_config.json."""
        cols = ("display", "field", "phase", "wired", "source")
        tv = ttk.Treeview(parent_frame, columns=cols, show="tree headings", height=12)
        tv.heading("#0",       text="Layer / Vector")
        tv.heading("display",  text="Display")
        tv.heading("field",    text="Field")
        tv.heading("phase",    text="Ph")
        tv.heading("wired",    text="Wired")
        tv.heading("source",   text="Source System")
        tv.column("#0",       width=200, stretch=False)
        tv.column("display",  width=100, stretch=False)
        tv.column("field",    width=100, stretch=False)
        tv.column("phase",    width=35,  stretch=False)
        tv.column("wired",    width=50,  stretch=False)
        tv.column("source",   width=280, stretch=True)

        _cfg  = self._aoe_cfg
        _vecs = _cfg.get("vectors", [])  # flat list

        for layer_key, layer_info in self.LAYER_SOURCES.items():
            _wired_str = "✅" if layer_info["wired"] else "⬜"
            layer_node = tv.insert("", "end", text=f"{layer_key}",
                                   values=("", "", "", _wired_str, layer_info["source"]),
                                   open=False)
            # Find vectors belonging to this layer (field prefix or layer attribute)
            _layer_vecs = [v for v in _vecs if v.get("layer", "").lower() == layer_key.lower()]
            if not _layer_vecs:
                # Fallback: match by id prefix (e.g. ec_ → attribution, vh_ → version_health)
                _prefix_map = {
                    "attribution": "ec_", "version_health": "vh_", "ux_baseline": "ux_",
                    "code_profile": "cp_", "query_weights": "qw_", "morph_opinion": "mo_",
                    "temporal_aoe": "ta_", "weight_engine": "we_", "morphological": "ml_",
                    "business_domain": "bd_", "graph_topology": "gt_",
                }
                _pfx = _prefix_map.get(layer_key, "")
                _layer_vecs = [v for v in _vecs if str(v.get("id", "")).startswith(_pfx)]
            for vec in _layer_vecs:
                _v_wired = "✅" if vec.get("wired") else "⬜"
                tv.insert(layer_node, "end",
                          text=f"  {vec.get('id', '?')}",
                          values=(
                              vec.get("display", ""),
                              vec.get("field", ""),
                              vec.get("phase", ""),
                              _v_wired,
                              layer_info["source"],
                          ))

        def _on_select(evt):
            sel = tv.selection()
            if sel:
                item = tv.item(sel[0])
                layer_text = item["text"].strip()
                # Lookup in LAYER_SOURCES
                for lk, li in self.LAYER_SOURCES.items():
                    if lk in layer_text or layer_text.startswith(lk[:6]):
                        self._aoe_status_var.set(f"feeder: {li['feeder']}  |  path: {li['path']}")
                        break

        tv.bind("<<TreeviewSelect>>", _on_select)

        sb = ttk.Scrollbar(parent_frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def create_consolidated_tools_page(self, page_frame):
        """Page 2: Consolidated Tools from consolidated_menu.json (161 tools)."""
        page_frame.columnconfigure(0, weight=1)
        page_frame.rowconfigure(1, weight=1)

        # Top bar
        top = ttk.Frame(page_frame, style='Category.TFrame')
        top.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=5)
        ttk.Label(top, text="📦 Consolidated Tool Catalog",
                  font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Label(top, text="(right-click a tool → Query in Os_Toolkit)",
                  font=("Arial", 8), style='Config.TLabel', foreground='#888888').pack(side=tk.LEFT, padx=10)

        # Split: left=tree, right=query result
        split = ttk.Frame(page_frame, style='Category.TFrame')
        split.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=(0, 5))
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)
        split.rowconfigure(0, weight=1)

        # TreeView
        cols = ("category", "command", "args", "enabled")
        tv = ttk.Treeview(split, columns=cols, show="tree headings")
        tv.heading("#0",       text="Name")
        tv.heading("category", text="Category")
        tv.heading("command",  text="Command")
        tv.heading("args",     text="Args")
        tv.heading("enabled",  text="On")
        tv.column("#0",       width=180, stretch=False)
        tv.column("category", width=130, stretch=False)
        tv.column("command",  width=130, stretch=False)
        tv.column("args",     width=80,  stretch=False)
        tv.column("enabled",  width=35,  stretch=False)

        # Load consolidated_menu.json
        _menu_path = (Path(__file__).parents[2]
                      / "action_panel_tab" / "babel_data" / "inventory" / "consolidated_menu.json")
        self._consolidated_tools = []
        if _menu_path.exists():
            try:
                _menu = json.loads(_menu_path.read_text(encoding="utf-8"))
                # May be a list or a dict with 'tools' key
                _tool_list = _menu if isinstance(_menu, list) else _menu.get("tools", [])
                self._consolidated_tools = _tool_list
            except Exception:
                pass

        # Group by category
        _by_cat = {}
        for tool in self._consolidated_tools:
            _cat = tool.get("category", "Uncategorized")
            _by_cat.setdefault(_cat, []).append(tool)

        _cat_nodes = {}
        for cat_name in sorted(_by_cat.keys()):
            node = tv.insert("", "end", text=cat_name,
                             values=(cat_name, "", "", ""), open=False)
            _cat_nodes[cat_name] = node
            for tool in _by_cat[cat_name]:
                _en = "✅" if tool.get("enabled", True) else "⬜"
                _args = str(tool.get("arguments", []))[:30]
                tv.insert(node, "end",
                          text=tool.get("display_name", tool.get("name", "?")),
                          values=(cat_name, tool.get("command", ""), _args, _en))

        sb_tv = ttk.Scrollbar(split, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb_tv.set)
        tv.grid(row=0, column=0, sticky=tk.NSEW)
        sb_tv.grid(row=0, column=0, sticky=tk.NS, padx=(0, 1))

        # Right panel: query result
        right = ttk.Frame(split, style='Category.TFrame')
        right.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 0))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="🔬 Os_Toolkit Query Result",
                  font=("Arial", 9, "bold"), style='Config.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 3))
        self._ctab_query_text = scrolledtext.ScrolledText(
            right, wrap=tk.WORD, font=("Courier", 8),
            bg='#1e1e1e', fg='#cccccc', height=20
        )
        self._ctab_query_text.grid(row=1, column=0, sticky=tk.NSEW)

        # Right-click menu on tree
        ctx_menu = tk.Menu(page_frame, tearoff=0)
        ctx_menu.add_command(label="🔬 Query in Os_Toolkit",
                             command=lambda: self._ctab_query_selected(tv))

        def _on_right_click(evt):
            tv.selection_set(tv.identify_row(evt.y))
            try:
                ctx_menu.tk_popup(evt.x_root, evt.y_root)
            finally:
                ctx_menu.grab_release()

        tv.bind("<Button-3>", _on_right_click)
        tv.bind("<Double-1>",  lambda e: self._ctab_query_selected(tv))

    def _ctab_query_selected(self, tv):
        """Run Os_Toolkit query on the selected consolidated tool's command."""
        sel = tv.selection()
        if not sel:
            return
        item = tv.item(sel[0])
        cmd = item["values"][1] if len(item["values"]) > 1 else ""
        if not cmd:
            return
        self._ctab_query_text.delete("1.0", tk.END)
        self._ctab_query_text.insert(tk.END, f"Querying: {cmd}...\n")

        import threading, subprocess as _sp, sys as _sys
        _tk_path = str(Path(__file__).parents[2] / "action_panel_tab" / "Os_Toolkit.py")

        def _run():
            try:
                _res = _sp.run(
                    [_sys.executable, _tk_path, "query", cmd],
                    capture_output=True, text=True, timeout=15,
                    cwd=str(Path(__file__).parents[2] / "action_panel_tab")
                )
                _out = _res.stdout or _res.stderr or "(no output)"
            except Exception as _e:
                _out = f"(error: {_e})"
            self.root.after(0, lambda o=_out: (
                self._ctab_query_text.delete("1.0", tk.END),
                self._ctab_query_text.insert(tk.END, o)
            ))

        threading.Thread(target=_run, daemon=True).start()

    def load_tool_settings(self):
        """Load tool settings from file"""
        settings_file = Path(__file__).parent.parent / "tool_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)

                for tool_key, enabled in settings.get('enabled_tools', {}).items():
                    self.tool_vars[tool_key] = tk.BooleanVar(value=enabled)

                # Load context provider settings
                for pk, enabled in settings.get('context_providers', {}).items():
                    self.context_provider_vars[pk] = tk.BooleanVar(value=enabled)

                # Load Os_Toolkit context tool settings
                for ok, enabled in settings.get('os_toolkit_tools', {}).items():
                    self.ostk_tool_vars[ok] = tk.BooleanVar(value=enabled)

                log_message("TOOLS_TAB: Settings loaded successfully")
            except Exception as e:
                log_message(f"TOOLS_TAB ERROR: Failed to load settings: {e}")
        else:
            # Default: all tools enabled except critical ones
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    self.tool_vars[tool_key] = tk.BooleanVar(value=default_enabled)

    def save_tool_settings(self):
        """Save tool settings to file"""
        settings_file = Path(__file__).parent.parent / "tool_settings.json"

        try:
            settings = {
                'enabled_tools': {
                    key: var.get() for key, var in self.tool_vars.items()
                },
                'context_providers': {
                    key: var.get() for key, var in self.context_provider_vars.items()
                },
                'os_toolkit_tools': {
                    key: var.get() for key, var in self.ostk_tool_vars.items()
                },
            }

            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

            log_message("TOOLS_TAB: Settings saved successfully")

            # Show success message
            from tkinter import messagebox
            messagebox.showinfo("Settings Saved", "Tool settings have been saved successfully!")

        except Exception as e:
            log_message(f"TOOLS_TAB ERROR: Failed to save settings: {e}")
            from tkinter import messagebox
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")

    def reset_to_defaults(self):
        """Reset all tools to default settings"""
        from tkinter import messagebox

        if messagebox.askyesno("Reset to Defaults", "Reset all tool settings to defaults?"):
            # Reset: enable all except critical
            for category, tools in self.AVAILABLE_TOOLS.items():
                for tool_key, tool_info in tools.items():
                    default_enabled = tool_info['risk'] != 'CRITICAL'
                    if tool_key in self.tool_vars:
                        self.tool_vars[tool_key].set(default_enabled)

            log_message("TOOLS_TAB: Reset to defaults")

    def get_enabled_tools(self):
        """Get list of currently enabled tools"""
        return [key for key, var in self.tool_vars.items() if var.get()]

    def get_enabled_context_providers(self):
        """Get list of currently enabled Omega context providers."""
        return [key for key, var in self.context_provider_vars.items() if var.get()]

    def get_enabled_ostk_tools(self):
        """Get list of enabled Os_Toolkit context tool keys."""
        return [key for key, var in self.ostk_tool_vars.items() if var.get()]

    def refresh(self):
        """Refresh the tools tab"""
        log_message("TOOLS_TAB: Refreshing...")
        self.load_tool_settings()
