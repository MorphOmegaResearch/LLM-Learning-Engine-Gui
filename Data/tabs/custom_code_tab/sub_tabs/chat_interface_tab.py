"""
Chat Interface Tab - Interactive chat with Ollama models
Provides a simple chat interface to test and interact with models
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import json
import threading
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message, get_next_event_id


class ChatInterfaceTab(BaseTab):
    """Chat interface for interacting with Ollama models"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.current_model = None
        self.chat_history = []
        self.is_generating = False
        self.is_mounted = False
        self.is_standard_mode = False
        self.training_mode_enabled = False
        self.realtime_eval_scores = {}
        self.conversation_histories = {}  # {model_name: [chat_history]}
        self.last_user_message = ""  # Track for tool call validation

        # Load backend settings first
        self.backend_settings = self.load_backend_settings()

        # Session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)

        # Tool execution
        self.tool_executor = None
        self.initialize_tool_executor()

        # Tool call logging and detection
        self.tool_call_logger = None
        self.tool_call_detector = None
        self.initialize_tool_logging()

        # Chat history management
        self.chat_history_manager = None
        self.current_session_id = None
        self.initialize_history_manager()

        # Load advanced settings
        self.advanced_settings = self.load_advanced_settings()

        # System Prompt and Tool Schema management
        self.current_system_prompt = "default"
        self.current_tool_schema = "default"
        self.system_prompts_dir = Path(__file__).parent.parent / "system_prompts"
        self.tool_schemas_dir = Path(__file__).parent.parent / "tool_schemas_configs"
        self._ensure_prompt_schema_dirs()

        # Initialize advanced components (all based on settings)
        self.initialize_advanced_components()

    def update_session_temp_label(self, value):
        self.session_temperature = round(float(value), 1)
        self.session_temp_label.config(text=f"Temp: {self.session_temperature:.1f}")

    def create_ui(self):
        """Create the chat interface UI"""
        log_message("CHAT_INTERFACE: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Model selector
        self.parent.rowconfigure(1, weight=1)  # Chat display
        self.parent.rowconfigure(2, weight=0)  # Input area

        # Top section: Model selector and controls
        self.create_top_controls(self.parent)

        # Middle section: Chat display
        self.create_chat_display(self.parent)

        # Bottom section: Input area
        self.create_input_area(self.parent)

        log_message("CHAT_INTERFACE: UI created successfully")

    def create_top_controls(self, parent):
        """Create top control bar with model info and actions"""
        controls_frame = ttk.Frame(parent, style='Category.TFrame')
        controls_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=(10, 5))
        controls_frame.columnconfigure(1, weight=1)

        # Model label
        ttk.Label(
            controls_frame,
            text="Active Model:",
            style='Config.TLabel',
            font=("Arial", 10, "bold")
        ).grid(row=0, column=0, sticky=tk.W, padx=(5, 10))

        # Model name display (with color indicator for mount status)
        self.model_label = tk.Label(
            controls_frame,
            text="No model selected",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#ffffff'
        )
        self.model_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 10))

        # Session Temperature control
        self.session_temp_label = ttk.Label(
            controls_frame,
            text=f"Temp: {self.backend_settings.get('temperature', 0.8):.1f}",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        )
        self.session_temp_label.grid(row=0, column=2, sticky=tk.W, padx=(10, 0))

        self.session_temperature_var = tk.DoubleVar(value=self.backend_settings.get('temperature', 0.8))
        session_temp_scale = ttk.Scale(
            controls_frame,
            from_=0.0,
            to=2.0,
            orient=tk.HORIZONTAL,
            variable=self.session_temperature_var,
            command=self.update_session_temp_label,
            length=100
        )
        session_temp_scale.grid(row=0, column=3, sticky=tk.W, padx=(5, 10))

        # Tool Schema selector button
        ttk.Button(
            controls_frame,
            text="🔧 Tool Schema",
            command=self.select_tool_schema,
            style='Action.TButton'
        ).grid(row=0, column=4, padx=5)

        # System Prompt selector button
        ttk.Button(
            controls_frame,
            text="📝 System Prompt",
            command=self.select_system_prompt,
            style='Action.TButton'
        ).grid(row=0, column=5, padx=5)

        # Change Directory button
        ttk.Button(
            controls_frame,
            text="📂 Change Dir",
            command=self.change_working_directory,
            style='Action.TButton'
        ).grid(row=0, column=6, padx=5)

        # Mode selector button
        ttk.Button(
            controls_frame,
            text="⚡ Mode",
            command=self.open_mode_selector,
            style='Action.TButton'
        ).grid(row=0, column=7, padx=5)

        # ── Row 1: Inline session history dropdown ──────────────────────────
        ttk.Label(
            controls_frame,
            text="📜 Session:",
            style='Config.TLabel',
            font=("Arial", 9, "bold")
        ).grid(row=1, column=0, sticky=tk.W, padx=(5, 5), pady=(3, 0))

        self._history_session_ids = []  # parallel list to combobox values
        self.history_combo_var = tk.StringVar()
        self.history_combo = ttk.Combobox(
            controls_frame,
            textvariable=self.history_combo_var,
            state='readonly',
            font=("Arial", 9),
            width=55,
        )
        self.history_combo.grid(row=1, column=1, columnspan=6, sticky=tk.EW,
                                padx=(0, 5), pady=(3, 0))
        self.history_combo.bind('<<ComboboxSelected>>', self._on_history_dropdown_select)

        ttk.Button(
            controls_frame,
            text="↺",
            command=self._populate_history_dropdown,
            style='Action.TButton',
            width=3
        ).grid(row=1, column=7, padx=5, pady=(3, 0))

        # ── Row 2: Task Watcher toggle + Toggle Context button ───────────────
        self.task_watcher_enabled = False
        self.task_watcher_var = tk.BooleanVar(value=False)
        self._omega_context_cache = {}
        self._context_panel = None  # lazy-created

        ttk.Checkbutton(
            controls_frame,
            text="⚡ Task Watcher",
            variable=self.task_watcher_var,
            command=self._on_task_watcher_toggle,
            style='Config.TLabel'
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(3, 0))

        ttk.Button(
            controls_frame,
            text="👁 Context",
            command=self._toggle_context_display,
            style='Action.TButton'
        ).grid(row=2, column=2, padx=5, pady=(3, 0))

        ttk.Label(
            controls_frame,
            text="(Omega context preview — does not enter chat)",
            style='Config.TLabel',
            font=("Arial", 8),
            foreground='#888888'
        ).grid(row=2, column=3, columnspan=4, sticky=tk.W, padx=2, pady=(3, 0))

        # ── Row 3: Omega context preview panel (hidden until 👁 button clicked) ──
        self._context_panel = scrolledtext.ScrolledText(
            controls_frame,
            height=18,            # enlarged for multi-section display
            font=("Courier", 9),
            state=tk.DISABLED,
            wrap=tk.WORD,
            bg='#1a1a2e',
            fg='#98c379',
            relief='flat',
        )
        # Not gridded yet — shown/hidden by _toggle_context_display()

        # Suggested actions async cache (R2b)
        self._suggested_actions_cache = ""
        self._suggested_actions_ts = 0.0

        # Context pool (R2a) — rolling list of context items accumulated while Task Watcher ON
        self._context_pool = []           # list of {ts, type, source, content}
        self._context_pool_timer = None   # after() handle for cancellation

    def _populate_history_dropdown(self):
        """Refresh the inline session history dropdown with the last 5 sessions."""
        if not self.chat_history_manager:
            return
        try:
            convs = self.chat_history_manager.list_conversations(
                model_name=self.current_model if self.current_model else None
            )
            # Take at most 5 most recent (list_conversations returns newest first)
            convs = convs[:5]
            labels = []
            session_ids = []
            for conv in convs:
                date_str = conv.get("saved_at", "")
                try:
                    from datetime import datetime
                    date_fmt = datetime.fromisoformat(date_str).strftime("%m-%d %H:%M")
                except Exception:
                    date_fmt = date_str[:16] if date_str else "?"
                n_msgs = conv.get("message_count", 0)
                preview = conv.get("preview", "")[:40]
                model = conv.get("model_name", "?")
                label = f"{date_fmt}  [{n_msgs} msgs]  {model}  — {preview}"
                labels.append(label)
                session_ids.append(conv.get("session_id", ""))

            # Also surface bi-hemi sessions from babel_data/sessions/
            try:
                _babel_sessions = (
                    Path(__file__).parents[2]
                    / "action_panel_tab" / "babel_data" / "sessions"
                )
                if _babel_sessions.exists():
                    _bihemi_files = sorted(
                        _babel_sessions.glob("session_bihemi_*.txt"), reverse=True
                    )[:3]
                    for bf in _bihemi_files:
                        # Parse timestamp from filename: session_bihemi_YYYYMMDD_HHMMSS.txt
                        _ts = bf.stem.replace("session_bihemi_", "")
                        try:
                            _dt_fmt = (
                                _ts[:4] + "-" + _ts[4:6] + "-" + _ts[6:8]
                                + " " + _ts[9:11] + ":" + _ts[11:13]
                            )
                        except Exception:
                            _dt_fmt = _ts
                        label = f"{_dt_fmt}  [bi-hemi]  Morph GGUF  — {bf.name}"
                        labels.append(label)
                        session_ids.append(f"__bihemi__{bf}")
            except Exception:
                pass

            self._history_session_ids = session_ids
            self.history_combo['values'] = labels
            if labels:
                self.history_combo.set(labels[0])
            else:
                self.history_combo.set("No sessions saved yet")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: history dropdown populate error: {e}")

    def _on_history_dropdown_select(self, event=None):
        """Load a conversation selected from the inline dropdown."""
        idx = self.history_combo.current()
        if idx < 0 or idx >= len(self._history_session_ids):
            return
        session_id = self._history_session_ids[idx]
        if not session_id:
            return

        # bi-hemi flat-text session: display read-only in chat area
        if session_id.startswith("__bihemi__"):
            file_path = Path(session_id[len("__bihemi__"):])
            try:
                text = file_path.read_text(encoding="utf-8")
                self.clear_chat()
                self.add_message("system", f"── bi-hemi session: {file_path.name} ──")
                self.add_message("assistant", text)
                log_message(f"CHAT_INTERFACE: Displayed bi-hemi session {file_path.name}")
            except Exception as e:
                log_message(f"CHAT_INTERFACE: bi-hemi load error: {e}")
            return

        try:
            conversation = self.chat_history_manager.load_conversation(session_id)
            if not conversation:
                log_message(f"CHAT_INTERFACE: dropdown load failed for {session_id}")
                return
            self.chat_history = conversation.get("chat_history", [])
            self.current_session_id = session_id
            loaded_model = conversation.get("model_name", self.current_model)
            if loaded_model != self.current_model:
                self.current_model = loaded_model
                self.model_label.config(text=loaded_model)
            self.redisplay_conversation()
            self.add_message("system", f"✓ Loaded session: {session_id}")
            log_message(f"CHAT_INTERFACE: Loaded session {session_id} from dropdown")
        except Exception as e:
            log_message(f"CHAT_INTERFACE: dropdown load error: {e}")

    # ── Omega Gate: context building, injection, and display ─────────────────

    def _get_enabled_context_providers(self) -> list:
        """Read enabled context providers from the Tools sub-tab (if available)."""
        try:
            # CustomCodeTab stores ToolsTab as self.tools_interface
            _tools_tab = getattr(self.parent_tab, 'tools_interface', None)
            if _tools_tab and hasattr(_tools_tab, 'get_enabled_context_providers'):
                return _tools_tab.get_enabled_context_providers()
        except Exception:
            pass
        # Default: all providers enabled if we can't read the settings
        return ["omega_ground", "task_context", "temporal_narrative", "biosphere_snapshot"]

    def _build_omega_context(self) -> dict:
        """Pull OsToolkitGroundingBridge for pre-prompt omega context.
        Respects enabled context providers from the Tools tab."""
        enabled = self._get_enabled_context_providers()
        result = {}
        # Always include omega_ground base if enabled
        if "omega_ground" in enabled:
            try:
                _bdir = str(
                    Path(__file__).parents[2]
                    / "action_panel_tab" / "regex_project" / "activities" / "tools" / "scripts"
                )
                if _bdir not in sys.path:
                    sys.path.insert(0, _bdir)
                from activity_integration_bridge import OsToolkitGroundingBridge
                _root = Path(__file__).parents[4]
                result = OsToolkitGroundingBridge(_root).load()
            except Exception as e:
                log_message(f"CHAT: omega_ground context build failed: {e}")

        # task_context: inject active task context if enabled
        if "task_context" in enabled:
            try:
                _plans_dir = Path(__file__).parents[4] / "Data" / "plans" / "Tasks"
                _ctx_files = sorted(_plans_dir.glob("task_context_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                if _ctx_files:
                    import json as _json
                    _tc = _json.loads(_ctx_files[0].read_text(encoding="utf-8"))
                    _meta = _tc.get('_meta') or _tc  # support both layouts
                    result['active_task_id'] = _meta.get('task_id', _tc.get('task_id', 'unknown'))
                    result['active_task_title'] = _meta.get('title', _tc.get('title', ''))
                    result['active_task_wherein'] = _meta.get('wherein', _tc.get('wherein', ''))
                    # Blame brief (up to 3 entries)
                    _blame = _tc.get('blame', [])[:3]
                    result['blame_brief'] = [
                        f"{b.get('target', '?')} {'(mod)' if b.get('modified_this_version') else ''}"
                        for b in _blame if isinstance(b, dict)
                    ]
                    # Expected diffs summary
                    _expdiffs = _tc.get('expected_diffs', [])
                    result['expected_diffs_count'] = len(_expdiffs)
                    result['expected_diffs_list'] = [str(e)[:80] for e in _expdiffs[:3]]
                    # Plan doc link — find latest morph_plan_{tid}_*.md (timestamped)
                    _tid = result.get('active_task_id', '')
                    if _tid:
                        _morph_dir = Path(__file__).parents[4] / "Data" / "plans" / "Morph"
                        _plan_matches = sorted(
                            _morph_dir.glob(f"morph_plan_{_tid}_*.md"),
                            key=lambda p: p.stat().st_mtime, reverse=True
                        ) if _morph_dir.exists() else []
                        if _plan_matches:
                            result['task_plan_doc'] = str(_plan_matches[0].relative_to(Path(__file__).parents[4]))
                        else:
                            result['task_plan_doc'] = ''
                    # Project link (projects.json)
                    _proj_path = Path(__file__).parents[4] / "Data" / "plans" / "projects.json"
                    if _proj_path.exists() and _tid:
                        try:
                            _projs = _json.loads(_proj_path.read_text(encoding="utf-8"))
                            for _pid, _pc in _projs.items():
                                if _tid in str(_pc.get('tasks', [])):
                                    result['task_project_id'] = _pid
                                    break
                        except Exception:
                            pass
            except Exception as e:
                log_message(f"CHAT: task_context provider failed: {e}")

        # live_changes: read pending_live_changes from version_manifest (always when Task Watcher ON)
        try:
            import json as _json
            _vm_path = Path(__file__).parents[4] / "Data" / "backup" / "version_manifest.json"
            if _vm_path.exists():
                _vm = _json.loads(_vm_path.read_text(encoding='utf-8'))
                _plc = _vm.get('pending_live_changes', {})
                result['pending_live_changes'] = [
                    {'path': k, 'diff_snippet': str(v)[:120]}
                    for k, v in list(_plc.items())[-3:]
                ]
            else:
                result['pending_live_changes'] = []
        except Exception:
            result['pending_live_changes'] = []

        # temporal_narrative: inject TemporalNarrativeEngine explain if enabled
        if "temporal_narrative" in enabled:
            try:
                _bdir2 = str(Path(__file__).parents[2] / "action_panel_tab")
                if _bdir2 not in sys.path:
                    sys.path.insert(0, _bdir2)
                from temporal_narrative_engine import TemporalNarrativeEngine
                _tne = TemporalNarrativeEngine(Path(__file__).parents[4])
                _narr = _tne.explain("last 24h") if hasattr(_tne, 'explain') else {}
                if _narr:
                    result['temporal_dominant_domain'] = _narr.get('dominant_domain', '')
                    result['temporal_hot_files'] = _narr.get('hot_files', [])[:3]
            except Exception:
                pass  # temporal_narrative is optional

        # biosphere_snapshot: inject entity catalog if enabled
        if "biosphere_snapshot" in enabled:
            try:
                _bio_path = Path(__file__).parents[3] / "map_tab" / "biosphere_manifest.json"
                if _bio_path.exists():
                    import json as _json
                    _bio = _json.loads(_bio_path.read_text(encoding="utf-8"))
                    result['biosphere_entity_count'] = len(_bio.get('entities', []))
                    result['biosphere_top_entities'] = [
                        e.get('name', '') for e in _bio.get('entities', [])[:3]
                    ]
            except Exception:
                pass  # biosphere is optional

        # latest_diffs: read enriched_changes and surface classification fields
        if "latest_diffs" in enabled:
            try:
                import json as _json
                _vm_path = Path(__file__).parents[4] / "Data" / "backup" / "version_manifest.json"
                if _vm_path.exists():
                    _vm = _json.loads(_vm_path.read_text(encoding="utf-8"))
                    _ec = _vm.get("enriched_changes", {})
                    _recent_ec = sorted(
                        _ec.values(),
                        key=lambda c: c.get("timestamp", ""),
                        reverse=True
                    )[:5]
                    result["latest_diffs"] = [
                        {
                            "file":      c.get("file", "?"),
                            "verb":      c.get("verb", "unknown"),
                            "risk":      c.get("risk_level", "LOW"),
                            "risk_why":  (c.get("risk_reasons") or [])[:2],
                            "ctx_class": c.get("context_class", ""),
                            "ctx_func":  c.get("context_function", ""),
                            "adds":      c.get("additions", 0),
                            "dels":      c.get("deletions", 0),
                            "task_ids":  (c.get("task_ids") or [])[:2],
                        }
                        for c in _recent_ec
                    ]
            except Exception:
                pass  # latest_diffs is optional

        # os_toolkit_tools: run enabled Os_Toolkit subcommands, cache per active task
        _ostk_keys = getattr(
            getattr(self, 'parent_tab', None),
            'tools_interface', None
        )
        _ostk_enabled = _ostk_keys.get_enabled_ostk_tools() if _ostk_keys and hasattr(_ostk_keys, 'get_enabled_ostk_tools') else []
        if _ostk_enabled:
            _wherein = result.get('active_task_wherein', '')
            _curr_tid = result.get('active_task_id', '')
            # Invalidate cache if task changed
            if _curr_tid and _curr_tid != getattr(self, '_last_ostk_task_id', ''):
                for _k in list(getattr(self, '_omega_context_cache', {}).keys()):
                    if _k.startswith('ostk_'):
                        self._omega_context_cache.pop(_k, None)
                self._last_ostk_task_id = _curr_tid
            _tk_path = str(Path(__file__).parents[2] / "action_panel_tab" / "Os_Toolkit.py")
            _tk_dir  = str(Path(__file__).parents[2] / "action_panel_tab")
            for _tool_key in _ostk_enabled:
                _cache_key = f'ostk_{_tool_key}'
                if not hasattr(self, '_omega_context_cache'):
                    self._omega_context_cache = {}
                if _cache_key not in self._omega_context_cache:
                    # Access class constant via the already-retrieved tools instance
                    _tool_def = getattr(type(_ostk_keys), 'OS_TOOLKIT_CONTEXT_TOOLS', {}).get(_tool_key, {})
                    _args = list(_tool_def.get('arg', []))
                    if _tool_def.get('needs_wherein') and _wherein:
                        _args.append(_wherein)
                    try:
                        _out = subprocess.run(
                            [sys.executable, _tk_path] + _args,
                            capture_output=True, text=True, timeout=12, cwd=_tk_dir
                        ).stdout
                        _out = self._strip_babel_log(_out)[:600] or '(no output)'
                        self._omega_context_cache[_cache_key] = _out
                    except Exception as _e:
                        self._omega_context_cache[_cache_key] = f"(error: {_e})"
                result[_cache_key] = self._omega_context_cache.get(_cache_key, '')

        log_message(
            f"CHAT: omega context built — providers={enabled} "
            f"gap={result.get('gap_severity','?')} keys={list(result.keys())}"
        )
        return result

    def _format_omega_context_block(self, omega: dict, ctx_id: str) -> str:
        """Shim — delegates to _format_context_sections(). All callers unchanged."""
        _eid = get_next_event_id()
        _gap = omega.get('gap_severity', 'unknown')
        _hot = omega.get('temporal_hot_spots', [])
        _pf = omega.get('probe_failures', [])
        log_message(
            f"{_eid} CONTEXT_INJECTION: gap={_gap} "
            f"hot={len(_hot)} probe_fails={len(_pf)} "
            f"session={getattr(self, 'current_session_id', 'none')}"
        )
        return self._format_context_sections(omega, ctx_id)

    _DIV = "━" * 72  # section divider

    def _format_context_sections(self, omega: dict, ctx_id: str) -> str:
        """Render omega context as labeled sections for panel display AND model injection.
        Sections injected into model: [OMEGA GROUNDING] + [ACTIVE TASK] + [ORCHESTRATOR].
        Display-only: [LIVE CHANGES POOL], [SUGGESTED ACTIONS], [BI-HEMI], [MODEL PAYLOAD].
        """
        D = self._DIV
        out = []

        # ── [OMEGA GROUNDING] ─────────────────────────────────────────────────
        gap_sev  = omega.get('gap_severity', 'unknown')
        priority = omega.get('priority_pct', 0.0)
        hot      = [str(h) for h in omega.get('temporal_hot_spots', [])[:3]]
        probes   = [str(p.get('file', p) if isinstance(p, dict) else p)
                    for p in omega.get('probe_failures', [])[:3]]
        hrf      = [str(r.get('file', r) if isinstance(r, dict) else r)
                    for r in omega.get('high_risk_files', [])[:3]]
        out.append(f"{D[:20]} [OMEGA GROUNDING | {ctx_id}] {D[:20]}")
        out.append(f"  gap_severity    : {gap_sev}")
        try:
            out.append(f"  priority_pct    : {float(priority):.2f}")
        except Exception:
            out.append(f"  priority_pct    : {priority}")
        out.append(f"  hot_spots       : {', '.join(hot) if hot else 'none'}")
        out.append(f"  probe_failures  : {', '.join(probes) if probes else 'none'}")
        out.append(f"  high_risk_files : {', '.join(hrf) if hrf else 'none'}")
        _omega_inject = "\n".join(out)  # save injection snapshot

        # ── [ACTIVE TASK] ─────────────────────────────────────────────────────
        _task_lines = []
        _tid    = omega.get('active_task_id', '')
        _title  = omega.get('active_task_title', '')
        _where  = omega.get('active_task_wherein', '')
        if _tid or _title or _where:
            _task_lines.append(f"\n{D[:28]} [ACTIVE TASK] {D[:28]}")
            if _tid:   _task_lines.append(f"  task_id  : {_tid}")
            if _title: _task_lines.append(f"  title    : {_title}")
            if _where: _task_lines.append(f"  wherein  : {_where}")
            _blame = omega.get('blame_brief', [])
            if _blame:
                _task_lines.append(f"  blame    : {'; '.join(_blame)}")
            _ed_count = omega.get('expected_diffs_count', 0)
            _ed_list  = omega.get('expected_diffs_list', [])
            if _ed_count:
                _ed_preview = ', '.join(_ed_list) if _ed_list else ''
                _task_lines.append(f"  exp_diffs: ({_ed_count} expected){(' — ' + _ed_preview) if _ed_preview else ''}")
            _plan_doc = omega.get('task_plan_doc', '')
            if _plan_doc:
                _task_lines.append(f"  plan_doc : {_plan_doc}  ✓")
            _proj_id = omega.get('task_project_id', '')
            if _proj_id:
                _task_lines.append(f"  project  : {_proj_id}")
            out.extend(_task_lines)
            _task_inject = "\n".join(_task_lines)
        else:
            _task_inject = ""

        # ── [ORCHESTRATOR] — populated by generate_response() metastate merge ─
        _orc_lines = []
        _domain    = omega.get('active_domain', '')
        _dialogue  = omega.get('dialogue_mode', '')
        _activity  = omega.get('suggested_activity', '')
        _conf      = omega.get('system_confidence', '')
        _orc_lines.append(f"\n{D[:26]} [ORCHESTRATOR] {D[:26]}")
        if _domain or _dialogue or _activity:
            _orc_lines.append(f"  domain    : {_domain or '?':<16} dialogue : {_dialogue or '?'}")
            _orc_lines.append(f"  activity  : {_activity or '?':<16} confidence: {_conf or '?'}")
            _orc_inject = "\n".join(_orc_lines)
        else:
            _tw = getattr(self, 'task_watcher_enabled', False)
            _hint = "(cold-start pending — toggle Task Watcher)" if not _tw else "(orchestrator did not return — check debug log)"
            _orc_lines.append(f"  {_hint}")
            _orc_inject = ""
        out.extend(_orc_lines)

        # ── [LIVE CHANGES POOL] — display only ────────────────────────────────
        out.append(f"\n{D[:24]} [LIVE CHANGES POOL] {D[:24]}")
        _plc = omega.get('pending_live_changes', [])
        # Also merge _context_pool items
        _pool = getattr(self, '_context_pool', [])
        _pool_diffs = [e for e in _pool if e.get('type') == 'pending_diff']
        if _plc:
            for i, item in enumerate(_plc, 1):
                _ppath = item.get('path', '?')
                _snip  = item.get('diff_snippet', '')[:80].replace('\n', ' ')
                out.append(f"  [{i}] {_ppath:<30}  {_snip}")
        elif _pool_diffs:
            for i, entry in enumerate(_pool_diffs[-3:], 1):
                out.append(f"  [{i}] {entry.get('source','?'):<30}  {entry.get('content','')[:60]}")
        else:
            out.append("  (no pending changes)")

        # ── [LATEST DIFFS] — display only ─────────────────────────────────────
        _ld = omega.get('latest_diffs', [])
        if _ld:
            out.append(f"\n{D[:25]} [LATEST DIFFS] {D[:25]}")
            for i, d in enumerate(_ld, 1):
                _fname = str(d.get('file') or '?').split('/')[-1]
                _verb  = str(d.get('verb') or '?')
                _risk  = str(d.get('risk') or 'LOW')
                _func  = str(d.get('ctx_func') or d.get('ctx_class') or
                             d.get('feature') or _fname)
                _adds  = d.get('adds', 0) or 0
                _dels  = d.get('dels', 0) or 0
                _why   = (d.get('risk_why') or [])[:1]
                _why_s = f" ({_why[0][:40]})" if _why else ""
                out.append(f"  [{i}] {_fname:<28} +{_adds}/-{_dels}  {_verb:<8} "
                           f"ctx:{_func:<20} risk:{_risk}{_why_s}")

        # ── [SUGGESTED ACTIONS] — display only ────────────────────────────────
        out.append(f"\n{D[:23]} [SUGGESTED ACTIONS] {D[:23]}")
        _ms = omega.get('metastate', {})
        if _ms:
            _ctrl = _ms.get('thought_event', omega.get('suggested_activity', ''))
            out.append(f"  control_signal : {_ctrl}")
        _suggest_txt = self._get_suggested_actions()
        _suggest_preview = _suggest_txt[:200].replace('\n', ' | ') if _suggest_txt else '(loading…)'
        out.append(f"  [Os_Toolkit]   : {_suggest_preview}")

        # ── [OS_TOOLKIT TOOLS] — display only ─────────────────────────────────
        _ostk_keys = [k for k in omega if k.startswith('ostk_') and omega[k]]
        if _ostk_keys:
            out.append(f"\n{D[:23]} [OS_TOOLKIT TOOLS] {D[:23]}")
            _ostk_labels = {
                'ostk_ostk_assess':  'assess',
                'ostk_ostk_todo':    'todo view',
                'ostk_ostk_query':   'query',
                'ostk_ostk_explain': 'explain',
            }
            for _ok in _ostk_keys:
                _lbl = _ok.replace('ostk_ostk_', '').replace('ostk_', '')
                _val = str(omega[_ok])[:200].replace('\n', ' | ')
                out.append(f"  [{_lbl}] {_val}")

        # ── [COLD START PLAN] — display only (T3-6) ────────────────────────────
        _csp = omega.get('cold_start_plan', '')
        if _csp:
            out.append(f"\n{D[:23]} [COLD START PLAN] {D[:24]}")
            for _line in _csp.splitlines()[:8]:
                out.append(f"  {_line}")

        # ── [MODEL PAYLOAD] — display only ────────────────────────────────────
        _ld_for_payload = omega.get('latest_diffs', [])
        _injected_sections = []
        if _omega_inject:     _injected_sections.append("[OMEGA GROUNDING]")
        if _task_inject:      _injected_sections.append("[ACTIVE TASK]")
        if _orc_inject:       _injected_sections.append("[ORCHESTRATOR]")
        if _ld_for_payload:   _injected_sections.append("[RECENT CHANGES]")
        _inject_str = " + ".join(_injected_sections) if _injected_sections else "none"
        _char_est   = len(_omega_inject) + len(_task_inject) + len(_orc_inject) + (50 * len(_ld_for_payload))
        out.append(f"\n{D[:26]} [MODEL PAYLOAD] {D[:26]}")
        out.append(f"  Injecting: {_inject_str}")
        out.append(f"  Est. chars: ~{_char_est}")

        # ── [BI-HEMI] — display only (set by _run_bihemi_response) ───────────
        _bh = omega.get('_bihemi_prior')
        if _bh:
            out.append(f"\n{D[:28]} [BI-HEMI] {D[:28]}")
            out.append(f"  OMEGA PRIOR ─────────────────────  ALPHA PAYLOAD ──────────────────")
            out.append(f"  domain    : {str(_bh.get('active_domain','')):<18}  ctrl_signal: {_bh.get('control_signal','')}")
            out.append(f"  persona   : {str(_bh.get('active_persona','')):<18}  temperature: {_bh.get('temperature','')} / max_tok: {_bh.get('max_new_tokens','')}")
            out.append(f"  gap       : {str(_bh.get('gap_severity','')):<18}  top_p      : {_bh.get('top_p', 0.9)}")

        return "\n".join(out)

    @staticmethod
    def _strip_babel_log(text: str) -> str:
        """Remove log/session-loading lines from Os_Toolkit stdout."""
        lines = []
        for l in text.splitlines():
            if l.startswith('BABEL_LOG:'):
                continue
            if l.startswith('[+]') or l.startswith('[-]') or l.startswith('[*]') or l.startswith('[]'):
                continue
            lines.append(l)
        return '\n'.join(lines).strip()

    def _get_suggested_actions(self) -> str:
        """Return cached Os_Toolkit suggest output; refresh async if stale (TTL=60s)."""
        import time
        now = time.time()
        if now - self._suggested_actions_ts < 60.0 and self._suggested_actions_cache:
            return self._suggested_actions_cache
        # Cache miss — fire background refresh, return stale/placeholder immediately
        def _bg_suggest():
            try:
                _ostk_path = str(
                    Path(__file__).parents[2] / "action_panel_tab" / "Os_Toolkit.py"
                )
                _trainer_root = Path(__file__).parents[4]
                # Use active task wherein file if available, else project root
                _wherein = getattr(self, '_omega_context_cache', {}).get(
                    'active_task_wherein', '')
                if _wherein:
                    _target = str(_trainer_root / _wherein)
                else:
                    _target = str(_trainer_root)
                _res = subprocess.run(
                    [sys.executable, _ostk_path, "suggest", _target,
                     "--context", "latest", "--format", "text"],
                    capture_output=True, text=True, timeout=8,
                    cwd=str(Path(__file__).parents[2] / "action_panel_tab")
                )
                _raw = _res.stdout if _res.returncode == 0 else f"(suggest rc={_res.returncode})"
                _out = self._strip_babel_log(_raw)[:500] or f"(suggest rc={_res.returncode})"
            except subprocess.TimeoutExpired:
                _out = "(Os_Toolkit suggest timed out)"
            except Exception as _e:
                _out = f"(suggest error: {_e})"
            self._suggested_actions_cache = _out
            self._suggested_actions_ts = time.time()
        threading.Thread(target=_bg_suggest, daemon=True).start()
        return self._suggested_actions_cache or "(loading…)"

    def _run_orchestrator_metastate(self, message: str) -> dict:
        """Call orchestrator.py subprocess with message, parse METASTATE JSON line.
        Returns metastate dict or {} on failure. Called from bg thread; timeout=8s."""
        _orc_path = (
            Path(__file__).parents[2]
            / "action_panel_tab" / "regex_project" / "orchestrator.py"
        )
        if not _orc_path.exists():
            log_message(f"CHAT: orchestrator not found at {_orc_path}")
            return {}
        try:
            # Clean message: single line, no shell-unsafe chars, bounded length
            _clean_msg = ' '.join(message.replace('\n', ' ').split())[:500]
            _res = subprocess.run(
                [sys.executable, str(_orc_path), _clean_msg],
                capture_output=True, text=True, timeout=8,
                cwd=str(_orc_path.parent)
            )
            if _res.stderr:
                log_message(f"CHAT: orchestrator stderr: {_res.stderr[:300]}")
            for line in _res.stdout.splitlines():
                if line.startswith("METASTATE:"):
                    try:
                        _meta = json.loads(line[len("METASTATE:"):].strip())
                        log_message(
                            f"CHAT: orchestrator OK — domain={_meta.get('active_domain','')} "
                            f"activity={_meta.get('suggested_activity','')} "
                            f"confidence={_meta.get('system_confidence','')}")
                        return _meta
                    except Exception:
                        pass
            log_message(f"CHAT: orchestrator returned no METASTATE line (rc={_res.returncode})")
        except subprocess.TimeoutExpired:
            log_message("CHAT: orchestrator metastate timed out (8s)")
        except Exception as _e:
            log_message(f"CHAT: orchestrator metastate error: {_e}")
        return {}

    def _build_cold_start_message(self, omega: dict) -> str:
        """Build synthetic message from available context for orchestrator cold-start.
        Feeds: latest diffs, active task, gap severity, probe failures."""
        parts = []
        _tid = omega.get('active_task_id', '')
        if _tid:
            parts.append(f"Active task: {_tid} — {omega.get('active_task_title', '')}")
            _w = omega.get('active_task_wherein', '')
            if _w:
                parts.append(f"Working on: {_w}")
        parts.append(f"Gap severity: {omega.get('gap_severity', 'unknown')}")
        _ld = omega.get('latest_diffs', [])
        if _ld:
            _files = [str(d.get('file', '?')).split('/')[-1] for d in _ld[:3]]
            _verbs = [str(d.get('verb', '?')) for d in _ld[:3]]
            parts.append(f"Recent: {', '.join(f'{v} {f}' for v, f in zip(_verbs, _files))}")
        _pf = omega.get('probe_failures', [])
        if _pf:
            parts.append(f"Probe failures: {', '.join(str(p) for p in _pf[:3])}")
        return ". ".join(parts) if parts else "System cold start — assess current project state"

    def _refresh_context_panel(self, preview: str):
        """Update context panel text on main thread."""
        if self._context_panel:
            try:
                self._context_panel.config(state=tk.NORMAL)
                self._context_panel.delete("1.0", tk.END)
                self._context_panel.insert(tk.END, preview)
                self._context_panel.config(state=tk.DISABLED)
            except Exception:
                pass

    def _log_context_to_session(self, ctx_block: str, ctx_id: str):
        """Write context packet to a side-log file (not to chat_history)."""
        try:
            _session_id = getattr(self, 'current_session_id', None)
            if not _session_id:
                return
            _hist_dir = Path(__file__).parents[4] / "Training_Data-Sets" / "ChatHistories"
            _hist_dir.mkdir(parents=True, exist_ok=True)
            _log_file = _hist_dir / f"{_session_id}_context.log"
            _eid = get_next_event_id()
            _entry = (
                f"\n<Context_Packet:[{_eid}] ts={ctx_id}>\n"
                f"{ctx_block}\n"
                f"</Context_Packet>\n"
            )
            with open(_log_file, "a", encoding="utf-8") as fh:
                fh.write(_entry)
        except Exception as e:
            log_message(f"CHAT: context log write failed: {e}")

    def _pool_tick(self):
        """30-second periodic pool refresh when Task Watcher is ON. Runs on Tk main thread."""
        if not self.task_watcher_enabled:
            return  # watcher turned off; self-terminate
        try:
            import json as _json
            _vm_path = Path(__file__).parents[4] / "Data" / "backup" / "version_manifest.json"
            if _vm_path.exists():
                _vm = _json.loads(_vm_path.read_text(encoding='utf-8'))
                _plc = _vm.get('pending_live_changes', {})
                for k, v in list(_plc.items())[-3:]:
                    if not any(e.get('source') == k for e in self._context_pool):
                        self._context_pool.append({
                            'ts': datetime.now().isoformat(),
                            'type': 'pending_diff',
                            'source': k,
                            'content': str(v)[:100],
                        })
        except Exception as _e:
            log_message(f"CHAT: pool_tick error: {_e}")
        # Check if planner Latest has new data (ostoolkit_latest.txt)
        try:
            _latest_txt = Path(__file__).parents[4] / "Data" / "plans" / "Refs" / "ostoolkit_latest.txt"
            if _latest_txt.exists():
                _mtime = _latest_txt.stat().st_mtime
                if _mtime > getattr(self, '_latest_txt_mtime', 0):
                    _content = self._strip_babel_log(
                        _latest_txt.read_text(encoding='utf-8', errors='replace')[:500])
                    if _content:
                        self._context_pool.append({
                            'ts': datetime.now().isoformat(),
                            'type': 'latest_report',
                            'source': 'planner_latest',
                            'content': _content,
                        })
                    self._latest_txt_mtime = _mtime
        except Exception:
            pass
        self._context_pool = self._context_pool[-20:]  # bounded
        # Reschedule
        try:
            self._context_pool_timer = self.root.after(30000, self._pool_tick)
        except Exception:
            pass

    def _on_task_watcher_toggle(self):
        """Handle Task Watcher toggle. Immediately builds omega context in background when turned ON.
        Also starts/stops the 30s context pool timer."""
        self.task_watcher_enabled = self.task_watcher_var.get()
        _state = "ON" if self.task_watcher_enabled else "OFF"
        _ts = datetime.now().strftime("%H:%M")
        self._log_context_to_session(f"[Task Watcher: {_state} at {_ts}]", _ts)
        log_message(f"CHAT: Task Watcher toggled {_state}")
        if self.task_watcher_enabled:
            self._context_pool = []  # fresh pool on each enable
            # Build context immediately in background so 👁 Context shows content right away
            def _bg_build():
                _omega = self._build_omega_context()
                # Cold-start orchestrator with synthesized context
                _cold_msg = self._build_cold_start_message(_omega)
                _metastate = self._run_orchestrator_metastate(_cold_msg)
                if _metastate:
                    _omega.update({
                        'active_domain':      _metastate.get('active_domain', ''),
                        'dialogue_mode':      _metastate.get('dialogue_mode', ''),
                        'suggested_activity': _metastate.get('suggested_activity', ''),
                        'system_confidence':  _metastate.get('system_confidence', ''),
                        'metastate':          _metastate,
                    })
                    log_message(
                        f"CHAT: Cold-start orchestrator: domain={_metastate.get('active_domain', '')} "
                        f"activity={_metastate.get('suggested_activity', '')}"
                    )
                # Write orchestrator metastate for planner Latest to consume (T3-7)
                if _metastate:
                    try:
                        _orc_out = Path(__file__).parents[4] / "Data" / "plans" / "Refs" / "orchestrator_metastate.json"
                        _orc_out.parent.mkdir(parents=True, exist_ok=True)
                        _orc_out.write_text(json.dumps({
                            'ts': datetime.now().isoformat(),
                            'metastate': _metastate,
                            'cold_start_message': _cold_msg,
                        }, indent=2), encoding='utf-8')
                    except Exception:
                        pass

                # Cold-start plan generation via Os_Toolkit plan show (T3-5)
                try:
                    _ostk_path = str(
                        Path(__file__).parents[2] / "action_panel_tab" / "Os_Toolkit.py"
                    )
                    _plan_res = subprocess.run(
                        [sys.executable, _ostk_path, "plan", "show"],
                        capture_output=True, text=True, timeout=10,
                        cwd=str(Path(__file__).parents[2] / "action_panel_tab")
                    )
                    _plan_out = self._strip_babel_log(_plan_res.stdout)[:800]
                    if _plan_out:
                        _omega['cold_start_plan'] = _plan_out
                        self._context_pool.append({
                            'ts': datetime.now().isoformat(),
                            'type': 'cold_start_plan',
                            'source': 'ostk_plan_show',
                            'content': _plan_out,
                        })
                        log_message(f"CHAT: Cold-start plan generated ({len(_plan_out)} chars)")
                    # Refresh active project template if one exists
                    _active_project = _omega.get('task_project_id', '')
                    if _active_project:
                        subprocess.run(
                            [sys.executable, _ostk_path, "plan", "refresh", _active_project],
                            capture_output=True, text=True, timeout=12,
                            cwd=str(Path(__file__).parents[2] / "action_panel_tab")
                        )
                        log_message(f"CHAT: Cold-start refreshed project: {_active_project}")
                except Exception as _e:
                    log_message(f"CHAT: Cold-start plan error: {_e}")

                self._omega_context_cache = _omega
                # Seed pool from pending_live_changes in the fresh omega
                for _item in _omega.get('pending_live_changes', []):
                    self._context_pool.append({
                        'ts': datetime.now().isoformat(),
                        'type': 'pending_diff',
                        'source': _item.get('path', '?'),
                        'content': _item.get('diff_snippet', ''),
                    })
                # Auto-refresh context panel if visible
                if self._context_panel:
                    try:
                        _preview = self._format_omega_context_block(
                            _omega, datetime.now().strftime("%Y%m%d_%H%M%S"))
                        self.root.after(0, lambda p=_preview: self._refresh_context_panel(p))
                    except Exception:
                        pass
            threading.Thread(target=_bg_build, daemon=True).start()
            # Start pool timer on main thread
            try:
                self._context_pool_timer = self.root.after(30000, self._pool_tick)
            except Exception:
                pass
        else:
            # Cancel timer
            if self._context_pool_timer:
                try:
                    self.root.after_cancel(self._context_pool_timer)
                except Exception:
                    pass
                self._context_pool_timer = None

    def _toggle_context_display(self):
        """Show/hide the Omega context preview panel (row 3 of controls_frame).
        If no cache yet, builds context on-demand."""
        if self._context_panel is None:
            return
        try:
            _is_visible = self._context_panel.winfo_ismapped()
        except Exception:
            return

        if _is_visible:
            self._context_panel.grid_remove()
        else:
            # Refresh content from latest cache, or build on demand
            omega = getattr(self, '_omega_context_cache', {})
            if not omega:
                # Build synchronously on first click (small latency, better UX than empty panel)
                omega = self._build_omega_context()
                self._omega_context_cache = omega
            if omega:
                _ctx_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                preview = self._format_omega_context_block(omega, _ctx_id)
            else:
                enabled = self._get_enabled_context_providers()
                preview = (
                    "[Omega context returned empty]\n"
                    f"Enabled providers: {', '.join(enabled) if enabled else 'none'}\n"
                    "Check that OsToolkitGroundingBridge and version_manifest are available."
                )
            self._context_panel.config(state=tk.NORMAL)
            self._context_panel.delete("1.0", tk.END)
            self._context_panel.insert(tk.END, preview)
            self._context_panel.config(state=tk.DISABLED)
            # Grid at row 3, spanning all columns
            self._context_panel.grid(
                row=3, column=0, columnspan=8, sticky=tk.EW, padx=5, pady=(3, 3)
            )

    # ── End Omega Gate methods ────────────────────────────────────────────────

    def create_chat_display(self, parent):
        """Create the chat message display area"""
        display_frame = ttk.Frame(parent, style='Category.TFrame')
        display_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=5)
        display_frame.columnconfigure(0, weight=1)
        display_frame.rowconfigure(0, weight=1)

        # Scrolled text widget for chat
        self.chat_display = scrolledtext.ScrolledText(
            display_frame,
            wrap=tk.WORD,
            font=("Arial", 10),
            state=tk.DISABLED,
            relief='flat',
            borderwidth=0,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.chat_display.grid(row=0, column=0, sticky=tk.NSEW)

        # Configure tags for styling
        self.chat_display.tag_config('user', foreground='#61dafb', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('assistant', foreground='#98c379', font=("Arial", 10, "bold"))
        self.chat_display.tag_config('system', foreground='#e06c75', font=("Arial", 9, "italic"))
        self.chat_display.tag_config('error', foreground='#ff6b6b', font=("Arial", 9))

    def create_input_area(self, parent):
        """Create the message input area"""
        input_frame = ttk.Frame(parent, style='Category.TFrame')
        input_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(5, 10))
        input_frame.columnconfigure(0, weight=1)

        # Button bar above input (Mount/Dismount/Clear Chat)
        button_bar = ttk.Frame(input_frame, style='Category.TFrame')
        button_bar.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 5))

        # Mount button
        self.mount_btn = ttk.Button(
            button_bar,
            text="📌 Mount",
            command=self.mount_model,
            style='Action.TButton',
            state=tk.DISABLED
        )
        self.mount_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Dismount button
        self.dismount_btn = ttk.Button(
            button_bar,
            text="📍 Dismount",
            command=self.dismount_model,
            style='Select.TButton',
            state=tk.DISABLED
        )
        self.dismount_btn.pack(side=tk.LEFT, padx=(0, 5))

        # Clear chat button
        ttk.Button(
            button_bar,
            text="🗑️ Clear Chat",
            command=self.clear_chat,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=(0, 5))

        # Load Chat button
        ttk.Button(
            button_bar,
            text="📂 Load Chat",
            command=self.load_chat_history,
            style='Action.TButton'
        ).pack(side=tk.LEFT)

        # Text input
        self.input_text = tk.Text(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Arial", 10),
            relief='flat',
            borderwidth=1,
            highlightthickness=1,
            highlightbackground='#454545',
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        self.input_text.grid(row=1, column=0, sticky=tk.EW, padx=(0, 5))

        # Bind Enter key (Shift+Enter for new line)
        self.input_text.bind('<Return>', self.on_enter_key)

        # Button container (Send/Stop buttons on the right side of input)
        button_container = ttk.Frame(input_frame, style='Category.TFrame')
        button_container.grid(row=1, column=1, sticky=tk.NS)

        # Send button
        self.send_btn = ttk.Button(
            button_container,
            text="Send ➤",
            command=self.send_message,
            style='Action.TButton',
            state=tk.DISABLED
        )
        self.send_btn.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

        # Stop button (moved here)
        self.stop_btn = ttk.Button(
            button_container,
            text="⏹️ Stop",
            command=self.stop_generation,
            style='Select.TButton',
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.TOP, fill=tk.X)

        # Instructions
        ttk.Label(
            input_frame,
            text="Press Enter to send • Shift+Enter for new line",
            style='Config.TLabel',
            font=("Arial", 8)
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))

    def on_enter_key(self, event):
        """Handle Enter key press"""
        # If Shift is held, insert newline (default behavior)
        if event.state & 0x1:  # Shift key
            return None  # Allow default behavior
        else:
            # Otherwise, send message
            self.send_message()
            return "break"  # Prevent newline insertion

    def set_model(self, model_name, model_info=None):
        """Set the active model for chat. model_info carries type/path for GGUF."""
        # Auto-save current conversation if switching models
        if self.current_model and self.chat_history:
            self.conversation_histories[self.current_model] = self.chat_history.copy()
            # Auto-save to persistent storage if enabled
            if self.backend_settings.get('auto_save_history', True):
                self._auto_save_conversation()

            # Persist real-time scores for the previous model
            if self.training_mode_enabled and self.current_model in self.realtime_eval_scores:
                self.persist_realtime_scores(self.current_model)

        self.current_model = model_name
        self.current_model_info = model_info or {"name": model_name, "type": "ollama", "path": None}
        self.is_mounted = False
        # Release any cached llama_cpp instance when switching models
        self._llama_instance = None
        self._llama_instance_path = None

        _provider = self.current_model_info.get("type", "ollama")
        _label = f"{model_name}  [llama.cpp]" if _provider == "gguf" else model_name
        # Update label color to red (not mounted)
        self.model_label.config(text=_label, fg='#ff6b6b')

        # Enable mount button, disable send and dismount
        self.mount_btn.config(state=tk.NORMAL)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        log_message(f"CHAT_INTERFACE: Model set to {model_name}")

        # Load conversation history for this model if exists
        if model_name in self.conversation_histories:
            self.chat_history = self.conversation_histories[model_name].copy()
            # Redisplay the conversation
            self.redisplay_conversation()
            self.add_message("system", f"Model switched to: {model_name} (conversation restored)")
        else:
            self.chat_history = []
            self.clear_chat()
            self.add_message("system", f"Model switched to: {model_name} (new conversation)")

        # Refresh session history dropdown for new model
        if hasattr(self, 'history_combo'):
            self._populate_history_dropdown()

        # Auto-mount if enabled in settings
        if self.backend_settings.get('auto_mount_model', False):
            log_message(f"CHAT_INTERFACE: Auto-mounting {model_name}")
            self.mount_model()

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)

    def mount_model(self):
        """Mount the selected model — Ollama or local GGUF via llama_cpp_python."""
        if not self.current_model:
            return

        _provider = getattr(self, 'current_model_info', {}).get('type', 'ollama')
        log_message(f"CHAT_INTERFACE: Mounting {self.current_model} [{_provider}]...")
        self.add_message("system", f"Loading {self.current_model}…")

        def mount_thread():
            try:
                if _provider == 'gguf':
                    # Load via llama_cpp_python — pre-warm the instance
                    self._ensure_llama_instance()
                    self.root.after(0, self._on_mount_success)
                else:
                    result = subprocess.run(
                        ["ollama", "run", self.current_model, "--verbose"],
                        input="",
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0 or "success" in result.stderr.lower():
                        self.root.after(0, self._on_mount_success)
                    else:
                        error_msg = f"Mount failed: {result.stderr}"
                        self.root.after(0, lambda: self._on_mount_error(error_msg))
            except subprocess.TimeoutExpired:
                self.root.after(0, self._on_mount_success)
            except Exception as e:
                error_msg = f"Mount error: {str(e)}"
                self.root.after(0, lambda: self._on_mount_error(error_msg))

        threading.Thread(target=mount_thread, daemon=True).start()

    def _ensure_llama_instance(self):
        """Load/cache a Llama instance for the current GGUF model."""
        gguf_path = str(getattr(self, 'current_model_info', {}).get('path', ''))
        if not gguf_path:
            raise ValueError("No GGUF path in current_model_info")
        if (getattr(self, '_llama_instance', None) is not None
                and getattr(self, '_llama_instance_path', None) == gguf_path):
            return  # Already loaded
        from llama_cpp import Llama
        log_message(f"CHAT_INTERFACE: Loading GGUF via llama_cpp: {gguf_path}")
        self._llama_instance = Llama(
            model_path=gguf_path,
            n_ctx=2048,
            n_threads=4,
            verbose=False,
        )
        self._llama_instance_path = gguf_path
        log_message("CHAT_INTERFACE: llama_cpp model loaded")

    def _on_mount_success(self):
        """Handle successful model mount"""
        self.is_mounted = True
        self.model_label.config(fg='#98c379')  # Green
        self.mount_btn.config(state=tk.DISABLED)
        self.dismount_btn.config(state=tk.NORMAL)
        self.send_btn.config(state=tk.NORMAL)
        self.add_message("system", f"{self.current_model} mounted successfully ✓")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} mounted")

    def _on_mount_error(self, error_msg):
        """Handle model mount error"""
        self.add_message("error", error_msg)
        log_message(f"CHAT_INTERFACE ERROR: {error_msg}")

    def dismount_model(self):
        """Dismount the current model"""
        if not self.current_model:
            return

        log_message(f"CHAT_INTERFACE: Dismounting model {self.current_model}...")
        self.is_mounted = False

        # Update UI immediately
        self.model_label.config(fg='#ff6b6b')  # Red
        self.mount_btn.config(state=tk.NORMAL)
        self.dismount_btn.config(state=tk.DISABLED)
        self.send_btn.config(state=tk.DISABLED)

        self.add_message("system", f"{self.current_model} dismounted")
        log_message(f"CHAT_INTERFACE: Model {self.current_model} dismounted")

        # Note: Ollama doesn't have a specific "unload" command
        # Models are automatically unloaded after inactivity

    def change_working_directory(self):
        """Open dialog to change working directory for tool execution"""
        from tkinter import filedialog, messagebox

        # Get current working directory
        current_dir = str(Path.cwd())
        if self.tool_executor:
            current_dir = self.tool_executor.get_working_directory()

        # Open directory selection dialog
        new_dir = filedialog.askdirectory(
            title="Select Working Directory for Tool Execution",
            initialdir=current_dir
        )

        if new_dir:
            # Update tool executor
            if self.tool_executor:
                success = self.tool_executor.set_working_directory(new_dir)
                if success:
                    # Update backend settings
                    self.backend_settings['working_directory'] = new_dir

                    # Save to settings file
                    settings_file = Path(__file__).parent.parent / "custom_code_settings.json"
                    try:
                        with open(settings_file, 'r') as f:
                            settings = json.load(f)
                        settings['working_directory'] = new_dir
                        with open(settings_file, 'w') as f:
                            json.dump(settings, f, indent=2)

                        log_message(f"CHAT_INTERFACE: Working directory changed to {new_dir}")
                        self.add_message("system", f"Working directory changed to: {new_dir}")
                        messagebox.showinfo("Directory Changed", f"Working directory set to:\n{new_dir}")
                    except Exception as e:
                        log_message(f"CHAT_INTERFACE ERROR: Failed to save working directory: {e}")
                        messagebox.showerror("Save Error", f"Directory changed but failed to save to settings:\n{str(e)}")
                else:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to change working directory to {new_dir}")
                    messagebox.showerror("Directory Error", f"Failed to change working directory:\n{new_dir}\n\nDirectory may not exist or be inaccessible.")
            else:
                log_message("CHAT_INTERFACE ERROR: Tool executor not initialized")
                messagebox.showerror("Error", "Tool executor not initialized")

    def clear_chat(self):
        """Clear chat history and renews the session"""
        # Save the current conversation before clearing, if not empty
        if self.chat_history and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()

        self.chat_history = []
        self.current_session_id = None  # This makes the session renewable
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)
        self.add_message("system", "Chat cleared. New session started.")
        log_message("CHAT_INTERFACE: Chat cleared and session renewed")

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)

    def get_mode_parameters(self, mode):
        """Get default parameters for a specific mode"""
        mode_configs = {
            'standard': {
                'Resource Usage': 'Default',
                'Max Context Tokens': '4096',
                'Generation Step': '24 tokens',
                'CPU Threads': 'Default',
                'Token Caps (Reasoning)': '300',
                'Token Caps (Standard)': '200',
                'Token Caps (Structured)': '150',
                'Quality Mode': 'Standard',
                'Description': 'Standard settings for general use, without resource profiles.'
            },
            'fast': {
                'Resource Usage': '25% (conservative)',
                'Max Context Tokens': '3072',
                'Generation Step': '16 tokens',
                'CPU Threads': 'Minimal (1-2)',
                'Token Caps (Reasoning)': '200',
                'Token Caps (Standard)': '120',
                'Token Caps (Structured)': '90',
                'Quality Mode': 'Fast',
                'Description': 'Quick responses, minimal processing'
            },
            'smart': {
                'Resource Usage': '50% (balanced)',
                'Max Context Tokens': '5120',
                'Generation Step': '32 tokens',
                'CPU Threads': 'Half of available',
                'Token Caps (Reasoning)': '450',
                'Token Caps (Standard)': '300',
                'Token Caps (Structured)': '220',
                'Quality Mode': 'Auto/Smart',
                'Description': 'Balanced speed and intelligence'
            },
            'think': {
                'Resource Usage': '75% (aggressive)',
                'Max Context Tokens': '8192',
                'Generation Step': '48 tokens',
                'CPU Threads': 'Most available (n-2)',
                'Token Caps (Reasoning)': '900',
                'Token Caps (Standard)': '600',
                'Token Caps (Structured)': '350',
                'Quality Mode': 'Think (with verification)',
                'Think Time': 'Dynamic (configurable)',
                'Description': 'Deep reasoning, thorough analysis'
            }
        }
        return mode_configs.get(mode, mode_configs['smart'])

    def open_mode_selector(self):
        """Open quick mode selector dialog"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Quick Mode Selection")
        dialog.geometry("450x450")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"450x450+{x}+{y}")

        # Main content
        content_frame = ttk.Frame(dialog, style='Category.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        ttk.Label(
            content_frame,
            text="⚡ Select Mode",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 20))

        # Load current mode from mode_settings.json (same as mode selector tab)
        mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
        try:
            with open(mode_settings_file, 'r') as f:
                settings = json.load(f)
            current_mode = settings.get('current_mode', 'smart')
        except Exception as e:
            log_message(f"CHAT_INTERFACE: Failed to load mode settings: {e}")
            current_mode = 'smart'

        # Mode buttons
        modes = [
            ('standard', '🔹 Standard', 'Balanced performance and capability'),
            ('fast', '⚡ Fast', 'Optimized for speed'),
            ('smart', '🧠 Smart', 'Enhanced reasoning and tools'),
            ('think', '💭 Think', 'Maximum capability and depth')
        ]

        selected_mode = tk.StringVar(value=current_mode)

        for mode_id, mode_name, mode_desc in modes:
            mode_frame = ttk.Frame(content_frame, style='Category.TFrame')
            mode_frame.pack(fill=tk.X, pady=5)

            rb = ttk.Radiobutton(
                mode_frame,
                text=mode_name,
                variable=selected_mode,
                value=mode_id,
                style='TRadiobutton'
            )
            rb.pack(anchor=tk.W)

            ttk.Label(
                mode_frame,
                text=mode_desc,
                font=("Arial", 8),
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=(25, 0))

        # Button frame
        btn_frame = ttk.Frame(content_frame, style='Category.TFrame')
        btn_frame.pack(pady=(20, 0))

        def apply_mode():
            """Apply the selected mode"""
            new_mode = selected_mode.get()
            try:
                # Load current settings
                with open(mode_settings_file, 'r') as f:
                    mode_settings = json.load(f)

                # Update mode
                mode_settings['current_mode'] = new_mode

                # Get default parameters for this mode
                mode_parameters = self.get_mode_parameters(new_mode)
                mode_settings['mode_parameters'] = mode_parameters

                # Save to mode_settings.json
                with open(mode_settings_file, 'w') as f:
                    json.dump(mode_settings, f, indent=2)

                log_message(f"CHAT_INTERFACE: Mode changed to {new_mode}")
                self.add_message("system", f"Mode changed to: {new_mode.upper()}")

                # Notify Advanced Settings tab about mode change
                if hasattr(self.parent_tab, 'settings_interface'):
                    if hasattr(self.parent_tab.settings_interface, 'on_mode_changed'):
                        self.parent_tab.settings_interface.on_mode_changed(new_mode)
                        log_message(f"CHAT_INTERFACE: Notified Advanced Settings of mode change to {new_mode}")

                # Apply mode to chat interface
                if hasattr(self, 'set_mode_parameters'):
                    self.set_mode_parameters(new_mode, mode_parameters)

                dialog.destroy()
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to save mode: {e}")
                messagebox.showerror("Error", f"Failed to save mode:\n{str(e)}")

        ok_btn = ttk.Button(
            btn_frame,
            text="✓ OK",
            command=apply_mode,
            style='Action.TButton',
            width=12
        )
        ok_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="✕ Cancel",
            command=dialog.destroy,
            style='Select.TButton',
            width=12
        ).pack(side=tk.LEFT, padx=5)

        # Bind Enter key to apply
        dialog.bind('<Return>', lambda e: apply_mode())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

        # Focus the OK button
        ok_btn.focus_set()

    def redisplay_conversation(self):
        """Redisplay the entire conversation history"""
        self.chat_display.config(state=tk.NORMAL)
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state=tk.DISABLED)

        for msg in self.chat_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            self.add_message(role, content)

    def add_message(self, role, content):
        """Add a message to the chat display"""
        self.chat_display.config(state=tk.NORMAL)

        if role == "user":
            prefix = "You: "
            tag = "user"
        elif role == "assistant":
            prefix = f"{self.current_model}: "
            tag = "assistant"
        elif role == "system":
            prefix = "[System] "
            tag = "system"
        elif role == "error":
            prefix = "[Error] "
            tag = "error"
        else:
            prefix = ""
            tag = None

        # Add prefix with tag
        if tag:
            self.chat_display.insert(tk.END, prefix, tag)

        # Add content
        self.chat_display.insert(tk.END, content + "\n\n")

        # Auto-scroll to bottom
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)

    def send_message(self):
        """Send message to Ollama model"""
        if not self.current_model:
            self.add_message("error", "Please select a model from the right panel first")
            return

        if self.is_generating:
            return

        # Get message text
        message = self.input_text.get(1.0, tk.END).strip()
        if not message:
            return

        # Clear input
        self.input_text.delete(1.0, tk.END)

        # Add user message to display
        self.add_message("user", message)

        # Add to history
        self.chat_history.append({"role": "user", "content": message})

        # Track for tool call validation
        self.last_user_message = message

        # Pool: record user message when Task Watcher is ON
        if getattr(self, 'task_watcher_enabled', False):
            self._context_pool.append({
                'ts': datetime.now().isoformat(),
                'type': 'user_message',
                'source': 'chat',
                'content': message[:100],
            })
            self._context_pool = self._context_pool[-20:]

        # Disable send button and enable stop button
        self.send_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.is_generating = True

        # Generate response in background thread
        threading.Thread(
            target=self.generate_response,
            args=(message,),
            daemon=True
        ).start()

    def generate_response(self, message):
        """Generate response from Ollama with tool support (runs in background thread)"""
        try:
            log_message(f"CHAT_INTERFACE: Generating response for: {message[:50]}...")

            # Apply Intelligent Router (pre-process message)
            if self.router:
                try:
                    routing_result = self.router.route_intent(message)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router intent: {routing_result.get('intent', 'unknown')}, " +
                                   f"confidence: {routing_result.get('confidence', 0.0)}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Router error: {e}")

            # Apply Pre-RAG Optimizer (optimize chat history)
            chat_history_to_use = self.chat_history
            if self.pre_rag_optimizer:
                try:
                    # Combine chat history into single string for optimization
                    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in self.chat_history])
                    optimized = self.pre_rag_optimizer.optimize_context(history_text)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG compression ratio: {optimized.get('compression_ratio', 1.0)}")
                    # Note: For now we still use original history, full integration would reconstruct from optimized
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Pre-RAG Optimizer error: {e}")

            # Apply Context Scorer (score context quality)
            if self.context_scorer:
                try:
                    score_result = self.context_scorer.score_context(chat_history_to_use)
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context score: {score_result.get('final_score', 0.0)}, " +
                                   f"target_met: {score_result.get('target_met', False)}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Context Scorer error: {e}")

            # Get enabled tool schemas (filtered by current schema config)
            tool_schemas = self.get_tool_schemas()
            schema_config = self.get_current_tool_schema_config()
            if schema_config.get("enabled_tools") != "all":
                enabled_list = schema_config.get("enabled_tools", [])
                tool_schemas = [t for t in tool_schemas if t['function']['name'] in enabled_list]

            # Inject system prompt at the start of conversation
            system_prompt = self.get_current_system_prompt()

            # ── Debug: log dispatch config ────────────────────────────
            log_message(
                f"CHAT_DISPATCH: model={self.current_model} "
                f"provider={getattr(self, 'current_model_info', {}).get('type', 'ollama')} "
                f"schema={getattr(self, 'current_tool_schema', 'default')}({len(tool_schemas)} tools) "
                f"prompt={getattr(self, 'current_system_prompt', 'default')}({len(system_prompt)} chars) "
                f"task_watcher={'ON' if getattr(self, 'task_watcher_enabled', False) else 'OFF'}"
            )

            # ── Omega Gate: inject grounding context when Task Watcher is ON ──
            if getattr(self, 'task_watcher_enabled', False):
                try:
                    _omega = self._build_omega_context()
                    # Enrich with orchestrator METASTATE (runs on bg thread, 8s timeout)
                    _metastate = self._run_orchestrator_metastate(message)
                    if _metastate:
                        _omega.update({
                            'active_domain':      _metastate.get('active_domain', ''),
                            'dialogue_mode':      _metastate.get('dialogue_mode', ''),
                            'suggested_activity': _metastate.get('suggested_activity', ''),
                            'system_confidence':  _metastate.get('system_confidence', ''),
                            'metastate':          _metastate,
                        })
                    self._omega_context_cache = _omega
                    _ctx_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Build model-injection block (grounding + task + orchestrator only)
                    _inject_parts = []
                    _gap = _omega.get('gap_severity', 'unknown')
                    _hot = [str(h) for h in _omega.get('temporal_hot_spots', [])[:3]]
                    _pf  = [str(p.get('file', p) if isinstance(p, dict) else p)
                            for p in _omega.get('probe_failures', [])[:3]]
                    _hrf = [str(r.get('file', r) if isinstance(r, dict) else r)
                            for r in _omega.get('high_risk_files', [])[:3]]
                    _inject_parts.append(
                        f"[OMEGA GROUNDING | {_ctx_id}]\n"
                        f"  gap_severity: {_gap}\n"
                        f"  hot_spots   : {', '.join(_hot) if _hot else 'none'}\n"
                        f"  probes_fail : {', '.join(_pf) if _pf else 'none'}\n"
                        f"  high_risk   : {', '.join(_hrf) if _hrf else 'none'}"
                    )
                    _tid = _omega.get('active_task_id', '')
                    if _tid:
                        _inject_parts.append(
                            f"[ACTIVE TASK]\n"
                            f"  task_id: {_tid}  title: {_omega.get('active_task_title','')}\n"
                            f"  wherein: {_omega.get('active_task_wherein','')}"
                        )
                    if _metastate:
                        _inject_parts.append(
                            f"[ORCHESTRATOR]\n"
                            f"  domain: {_omega.get('active_domain','')}  "
                            f"activity: {_omega.get('suggested_activity','')}"
                        )
                    # Compact latest diffs summary for model payload (T1-7)
                    _ld = _omega.get('latest_diffs', [])
                    if _ld:
                        _verb_counts = {}
                        _risk_counts = {}
                        for _d in _ld:
                            _v = str(_d.get('verb') or '?')
                            _r = str(_d.get('risk') or 'LOW')
                            _verb_counts[_v] = _verb_counts.get(_v, 0) + 1
                            _risk_counts[_r] = _risk_counts.get(_r, 0) + 1
                        _files = [str(_d.get('file', '?')).split('/')[-1] for _d in _ld[:3]]
                        _inject_parts.append(
                            f"[RECENT CHANGES]\n"
                            f"  {len(_ld)} recent changes: {_verb_counts}\n"
                            f"  risk: {_risk_counts}\n"
                            f"  files: {', '.join(_files)}"
                        )
                    _ctx_block = "\n\n".join(_inject_parts)
                    system_prompt = _ctx_block + "\n\n---\n\n" + system_prompt
                    self._log_context_to_session(_ctx_block, _ctx_id)
                    log_message(
                        f"CHAT_DISPATCH: injected {len(_inject_parts)} context sections "
                        f"({len(_ctx_block)} chars): "
                        f"{[p.split(chr(10))[0] for p in _inject_parts]}"
                    )
                    # Auto-refresh context panel if visible (orchestrator now populated)
                    if self._context_panel:
                        try:
                            if self._context_panel.winfo_ismapped():
                                _preview = self._format_omega_context_block(
                                    self._omega_context_cache,
                                    datetime.now().strftime("%Y%m%d_%H%M%S"))
                                self.root.after(0, lambda p=_preview: self._refresh_context_panel(p))
                        except Exception:
                            pass
                except Exception as _oge:
                    log_message(f"CHAT: Omega Gate injection failed: {_oge}")
            # ─────────────────────────────────────────────────────────────────

            # ── Bi-Hemi routing branch (R4b) ─────────────────────────────────
            _bi_hemi_on = False
            try:
                _ms = getattr(getattr(self, 'parent_tab', None), 'mode_selector', None)
                if _ms and getattr(_ms, 'bi_hemi_enabled', False):
                    _bi_hemi_on = True
            except Exception:
                pass
            if _bi_hemi_on:
                _bh_resp = self._run_bihemi_response(message, system_prompt, chat_history_to_use)
                self.root.after(0, lambda r=_bh_resp: self.add_message("assistant", r))
                self.root.after(0, self.reset_buttons)
                return
            # ─────────────────────────────────────────────────────────────────

            messages_with_system = [{"role": "system", "content": system_prompt}] + chat_history_to_use

            # Prepare the chat payload
            payload = {
                "model": self.current_model,
                "messages": messages_with_system,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # NOTE: We do NOT add tools to the payload using Ollama's native API
            # Instead, tool schemas are embedded in the system prompt, and the model
            # learns to output tool calls in text format which are detected by Format Translator
            # This approach works with ANY model, not just those supporting Ollama's tools API
            if tool_schemas:
                log_message(f"CHAT_INTERFACE: {len(tool_schemas)} tool schemas available (embedded in system prompt)")

            # --- Provider branch: llama_cpp_python (GGUF) or Ollama HTTP ---
            _provider = getattr(self, 'current_model_info', {}).get('type', 'ollama')

            if _provider == 'gguf':
                # Local GGUF via llama_cpp_python
                try:
                    self._ensure_llama_instance()
                    _llm = self._llama_instance
                    # Build flat prompt from messages list
                    _prompt_parts = []
                    for _msg in messages_with_system:
                        _role = _msg.get('role', 'user')
                        _content = _msg.get('content', '')
                        if _role == 'system':
                            _prompt_parts.append(f"<|im_start|>system\n{_content}<|im_end|>")
                        elif _role == 'user':
                            _prompt_parts.append(f"<|im_start|>user\n{_content}<|im_end|>")
                        elif _role == 'assistant':
                            _prompt_parts.append(f"<|im_start|>assistant\n{_content}<|im_end|>")
                    _prompt_parts.append("<|im_start|>assistant\n")
                    _prompt = "\n".join(_prompt_parts)
                    _out = _llm(_prompt,
                                max_tokens=512,
                                temperature=self.session_temperature,
                                stop=["<|im_end|>", "</s>", "<|im_start|>"],
                                echo=False)
                    response_content = _out['choices'][0]['text'].strip()
                    message_data = {"content": response_content, "role": "assistant"}
                except Exception as _lce:
                    error_msg = f"llama_cpp error: {_lce}"
                    log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                    self.root.after(0, lambda: self.add_message("error", error_msg))
                    return
            else:
            # Call Ollama API via HTTP (using curl as subprocess)
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(payload, f)
                    payload_file = f.name

                try:
                    result = subprocess.run(
                        ["curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                         "-H", "Content-Type: application/json",
                         "-d", f"@{payload_file}"],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                finally:
                    Path(payload_file).unlink(missing_ok=True)

                if result.returncode != 0:
                    error_msg = f"Ollama error: {result.stderr}"
                    log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                    self.root.after(0, lambda: self.add_message("error", error_msg))
                    return

            if _provider != 'gguf':  # gguf already has message_data set above
                # Log raw response for debugging
                log_message(f"CHAT_INTERFACE DEBUG: Raw Ollama response (first 1000 chars): {result.stdout[:1000]}")

                # Parse response (with JSON Fixer if enabled)
                if self.json_fixer_enabled:
                    try:
                        response_data = self.smart_json_parse(result.stdout)
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message("DEBUG: JSON Fixer used to parse response")
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: JSON Fixer failed, falling back to standard JSON: {e}")
                        response_data = json.loads(result.stdout)
                else:
                    response_data = json.loads(result.stdout)

                # Check if Ollama returned an error
                if "error" in response_data:
                    error_msg = response_data["error"]
                    log_message(f"CHAT_INTERFACE ERROR: Ollama API error: {error_msg}")
                    self.root.after(0, lambda: self.add_message("error", f"Ollama error: {error_msg}"))
                    return

                message_data = response_data.get("message", {})

                # Apply Quality Assurance to response if enabled
                if self.quality_assurance:
                    try:
                        qa_result = self.quality_assurance.assess_quality(response_data)
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: QA assessment score: {qa_result.get('score', 0.0)}, " +
                                       f"passed: {qa_result.get('passed', True)}")

                        # Auto-recovery if enabled and QA failed
                        if self.advanced_settings.get('quality_assurance', {}).get('auto_recovery', True):
                            if not qa_result.get('passed', True):
                                if self.backend_settings.get('enable_debug_logging', False):
                                    log_message(f"DEBUG: QA auto-recovery triggered due to low quality")
                                # Could implement retry logic here
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Quality Assurance error: {e}")

                # Apply Format Translator if enabled and no standard tool_calls
                tool_calls = message_data.get("tool_calls", [])
                if not tool_calls and self.format_translator:
                    try:
                        response_content = message_data.get("content", "")
                        translated = self.format_translator.translate(response_content)
                        if translated:
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Format Translator detected tool call: {translated.get('name', 'unknown')}")
                            # Convert to Ollama tool_call format
                            tool_calls = [{
                                "function": {
                                    "name": translated.get("name", ""),
                                    "arguments": translated.get("args", {})
                                }
                            }]
                    except Exception as e:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Format Translator error: {e}")

                # Check for tool calls
                if tool_calls:
                    # Model wants to use tools
                    log_message(f"CHAT_INTERFACE: Model requested {len(tool_calls)} tool calls")
                    self.root.after(0, lambda: self.handle_tool_calls(tool_calls, message_data))
                else:
                    # Regular response
                    response_content = message_data.get("content", "")

                    # Check if response is empty
                    if not response_content or response_content.strip() == "":
                        log_message("CHAT_INTERFACE WARNING: Model returned empty response")
                        log_message(f"CHAT_INTERFACE DEBUG: Full response data: {response_data}")
                        response_content = "[Model returned empty response]"

                    # Add to history
                    self.chat_history.append({"role": "assistant", "content": response_content})

                    # Display response
                    self.root.after(0, lambda: self.add_message("assistant", response_content))
                    log_message("CHAT_INTERFACE: Response generated successfully")

                    # Auto-save conversation
                    if self.backend_settings.get('auto_save_history', True):
                        self.root.after(0, self._auto_save_conversation)

            else:
                # GGUF path — message_data already set; display directly
                response_content = message_data.get("content", "")
                if not response_content or response_content.strip() == "":
                    response_content = "[Model returned empty response]"
                self.chat_history.append({"role": "assistant", "content": response_content})
                self.root.after(0, lambda rc=response_content: self.add_message("assistant", rc))
                log_message("CHAT_INTERFACE: GGUF response generated successfully")
                if self.backend_settings.get('auto_save_history', True):
                    self.root.after(0, self._auto_save_conversation)

        except subprocess.TimeoutExpired:
            error_msg = "Request timed out after 120 seconds"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        except Exception as e:
            error_msg = f"Error generating response: {str(e)}"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        finally:
            # Re-enable send button and disable stop button
            self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        """Reset button states after generation"""
        self.is_generating = False
        self.send_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def _run_bihemi_response(self, message: str, system_prompt: str, chat_history: list) -> str:
        """Bi-Hemi path: OmegaBridge epistemic/metacog state → GGUF Alpha inference.
        Runs on background thread (called from generate_response). Returns response string."""
        _trainer_root = Path(__file__).parents[4]

        # ── Step 1: OmegaBridge — derive epistemic + sampling params ─────────
        _omega_prior = {}
        try:
            _ob_dir = str(
                Path(__file__).parents[3]
                / "action_panel_tab" / "regex_project"
            )
            if _ob_dir not in sys.path:
                sys.path.insert(0, _ob_dir)
            from omega_bridge import OmegaBridge
            _ob = OmegaBridge(_trainer_root)
            _wherein = self._omega_context_cache.get('active_task_wherein', '') if self._omega_context_cache else ''
            # Try to get entity; fallback to empty dict
            _entity = {}
            try:
                if hasattr(_ob, '_get_entity') and _wherein:
                    _entity = _ob._get_entity(_wherein) or {}
            except Exception:
                pass
            _epistemic  = _ob.build_epistemic_state(_entity, {}) if hasattr(_ob, 'build_epistemic_state') else {}
            _metacog    = _ob.build_metacognitive_state(_entity) if hasattr(_ob, 'build_metacognitive_state') else {}
            # Module-level helpers
            import omega_bridge as _ob_mod
            _ctrl_sig  = _ob_mod._derive_control_signal(_epistemic, _metacog) if hasattr(_ob_mod, '_derive_control_signal') else 'NEUTRAL'
            _sampling  = _ob_mod._derive_sampling_params(_epistemic, _metacog) if hasattr(_ob_mod, '_derive_sampling_params') else {}
            _omega_prior = {
                'control_signal':  _ctrl_sig,
                'gap_severity':    _epistemic.get('gap_severity', 'low'),
                'active_domain':   _metacog.get('active_domain', 'general'),
                'active_persona':  _metacog.get('active_persona', 'Mate'),
                'temperature':     _sampling.get('temperature', self.session_temperature),
                'max_new_tokens':  _sampling.get('max_new_tokens', 256),
                'top_p':           _sampling.get('top_p', 0.9),
            }
        except Exception as _oe:
            log_message(f"CHAT: Bi-Hemi OmegaBridge error: {_oe}")

        # ── Step 2: Build system prompt with Omega prior ──────────────────────
        _prior_text = ""
        if _omega_prior:
            _prior_text = (
                "[OMEGA PRIOR]\n"
                f"  control_signal : {_omega_prior.get('control_signal','?')}\n"
                f"  gap_severity   : {_omega_prior.get('gap_severity','?')}\n"
                f"  active_domain  : {_omega_prior.get('active_domain','?')}\n"
                f"  active_persona : {_omega_prior.get('active_persona','?')}\n"
            )
        _bh_system_prompt = _prior_text + "\n---\n\n" + system_prompt if _prior_text else system_prompt

        # ── Step 3: Route to GGUF Alpha (llama_cpp) ──────────────────────────
        _alpha_response = ""
        _model_info = getattr(self, 'current_model_info', {}) or {}
        if _model_info.get('type') != 'gguf':
            _alpha_response = "[Bi-Hemi requires a mounted GGUF model — mount one in the Custom Code tab model selector]"
        else:
            try:
                if not hasattr(self, '_llama_instance') or self._llama_instance is None:
                    self._ensure_llama_instance()
                _llm = self._llama_instance
                # Build prompt in ChatML format
                _parts = [f"<|im_start|>system\n{_bh_system_prompt}<|im_end|>"]
                for _msg in chat_history[-6:]:
                    _r = _msg.get('role', 'user')
                    _c = _msg.get('content', '')
                    _parts.append(f"<|im_start|>{_r}\n{_c}<|im_end|>")
                _parts.append("<|im_start|>assistant\n")
                _prompt = "\n".join(_parts)
                _temp   = _omega_prior.get('temperature', self.session_temperature)
                _maxtok = int(_omega_prior.get('max_new_tokens', 256))
                _top_p  = float(_omega_prior.get('top_p', 0.9))
                _out = _llm(
                    _prompt,
                    max_tokens=_maxtok,
                    temperature=_temp,
                    top_p=_top_p,
                    stop=["<|im_end|>", "<|im_start|>"],
                    echo=False
                )
                _alpha_response = _out['choices'][0]['text'].strip()
            except Exception as _ae:
                log_message(f"CHAT: Bi-Hemi Alpha error: {_ae}")
                _alpha_response = f"[Bi-Hemi Alpha error: {_ae}]"

        # ── Step 4: Store omega_prior in cache for panel display ──────────────
        if _omega_prior and self._omega_context_cache is not None:
            self._omega_context_cache['_bihemi_prior'] = _omega_prior

        log_message(f"CHAT: Bi-Hemi response generated — ctrl={_omega_prior.get('control_signal','?')} len={len(_alpha_response)}")
        return _alpha_response

    def stop_generation(self):
        """Stop ongoing generation (placeholder)"""
        # Note: subprocess doesn't easily support stopping mid-execution
        # This is a placeholder for future streaming implementation
        log_message("CHAT_INTERFACE: Stop requested (not fully implemented)")
        self.add_message("system", "Stop requested - waiting for current generation to complete")

    def handle_tool_calls(self, tool_calls, message_data):
        """Handle tool calls from model response"""
        log_message(f"CHAT_INTERFACE: Handling {len(tool_calls)} tool calls")

        # Add assistant message with tool calls to history
        self.chat_history.append(message_data)

        # Get enabled tools from Tools tab
        enabled_tools = []
        if hasattr(self.parent_tab, 'tools_interface') and self.parent_tab.tools_interface:
            enabled_tools = self.parent_tab.tools_interface.get_enabled_tools()
            log_message(f"CHAT_INTERFACE: {len(enabled_tools)} tools are enabled in Tools tab")
        else:
            log_message("CHAT_INTERFACE WARNING: Tools tab not available, allowing all tools")
            enabled_tools = None  # None means allow all

        # Display tool execution message
        self.add_message("system", f"🔧 Executing {len(tool_calls)} tool(s)...")

        # Execute each tool
        tool_results = []
        for tool_call in tool_calls:
            function_data = tool_call.get("function", {})
            tool_name = function_data.get("name")
            arguments = function_data.get("arguments", {})

            # Check if tool is enabled in Tools tab
            if enabled_tools is not None and tool_name not in enabled_tools:
                log_message(f"CHAT_INTERFACE: Tool '{tool_name}' is DISABLED in Tools tab, skipping")
                self.add_message("system", f"  ✗ {tool_name}: Tool is disabled in Tools tab")
                tool_results.append({
                    "role": "tool",
                    "content": json.dumps({"error": "Tool is disabled in settings"}),
                    "tool_call_id": tool_call.get("id", ""),
                    "name": tool_name
                })
                continue

            # Parse arguments if they're a JSON string (with JSON Fixer if enabled)
            if isinstance(arguments, str):
                try:
                    if self.json_fixer_enabled:
                        arguments = self.smart_json_parse(arguments)
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: JSON Fixer parsed tool arguments")
                    else:
                        arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    log_message(f"CHAT_INTERFACE ERROR: Failed to parse tool arguments: {arguments}")
                    arguments = {}

            # Apply Schema Validator if enabled
            if self.schema_validator:
                try:
                    validation_result = self.schema_validator.validate(tool_name, arguments)
                    if not validation_result.get('valid', True):
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Schema validation failed for {tool_name}: {validation_result.get('errors', [])}")
                        # Optionally skip invalid tool calls based on mode
                        if self.advanced_settings.get('schema_validation', {}).get('mode') == 'strict':
                            self.add_message("error", f"  ✗ {tool_name}: Schema validation failed")
                            continue
                    else:
                        if self.backend_settings.get('enable_debug_logging', False):
                            log_message(f"DEBUG: Schema validation passed for {tool_name}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Schema Validator error: {e}")

            log_message(f"CHAT_INTERFACE: Executing tool: {tool_name} with args: {arguments}")

            # Show detailed tool call info if enabled in settings
            show_details = self.backend_settings.get('show_tool_call_details', True)
            if show_details:
                self.add_message("system", f"  → {tool_name}({', '.join(f'{k}={v}' for k, v in arguments.items())})")

            # Execute tool (via Orchestrator if enabled, otherwise direct)
            if self.tool_orchestrator:
                # Use Tool Orchestrator for intelligent execution
                try:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Using Tool Orchestrator for {tool_name}")
                    # Orchestrator expects a chain of operations
                    # For now, create single-tool chain
                    orchestrator_result = self.tool_orchestrator.execute_tool_with_gates(
                        tool_name, arguments
                    )
                    result = {
                        'success': orchestrator_result.get('success', False),
                        'output': orchestrator_result.get('output', ''),
                        'error': orchestrator_result.get('error')
                    }
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Tool Orchestrator error, falling back to direct execution: {e}")
                    # Fallback to direct execution
                    result = self.tool_executor.execute_tool_sync(tool_name, arguments)
            elif self.tool_executor:
                # Direct execution
                result = self.tool_executor.execute_tool_sync(tool_name, arguments)
            else:
                result = {'success': False, 'output': '', 'error': 'Tool executor not initialized'}

            # Apply Verification Engine to result if enabled
            if self.verification_engine and result['success']:
                try:
                    verification_result = self.verification_engine.verify_output(
                        tool_name, result['output']
                    )
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Verification result for {tool_name}: " +
                                   f"passed={verification_result.get('passed', True)}")

                    # Auto-fix if enabled and verification suggests fixes
                    if self.advanced_settings.get('verification', {}).get('auto_fix', True):
                        if verification_result.get('fixed_output'):
                            result['output'] = verification_result['fixed_output']
                            if self.backend_settings.get('enable_debug_logging', False):
                                log_message(f"DEBUG: Auto-fixed output for {tool_name}")
                except Exception as e:
                    if self.backend_settings.get('enable_debug_logging', False):
                        log_message(f"DEBUG: Verification Engine error: {e}")

            # Process result
            if result['success']:
                if show_details:
                    output_preview = result['output'][:200] if len(result['output']) > 200 else result['output']
                    self.add_message("system", f"  ✓ {tool_name}: {output_preview}")
                tool_results.append({
                    "role": "tool",
                    "content": result['output']
                })
            else:
                error_msg = result.get('error', 'Unknown error')
                self.add_message("error", f"  ✗ {tool_name}: {error_msg}")
                tool_results.append({
                    "role": "tool",
                    "content": f"Error: {error_msg}"
                })

        # Add tool results to history
        self.chat_history.extend(tool_results)

        # Log for training and real-time evaluation if enabled
        if self.training_mode_enabled:
            try:
                model_name = self.current_model

                # Use ToolCallLogger for training data logging
                if self.tool_call_logger:
                    self.tool_call_logger.log_training_example(self.chat_history.copy(), model_name)
                    self.tool_call_logger.log_batch_tool_calls(tool_calls, tool_results, model_name)
                    log_message(f"CHAT_INTERFACE: Logged tool calls via ToolCallLogger")

                # Perform real-time evaluation scoring
                if model_name not in self.realtime_eval_scores:
                    self.realtime_eval_scores[model_name] = {}

                for tool_call, res in zip(tool_calls, tool_results):
                    tool_name = tool_call.get("function", {}).get("name")
                    if tool_name not in self.realtime_eval_scores[model_name]:
                        self.realtime_eval_scores[model_name][tool_name] = {"success": 0, "failure": 0, "errors": []}

                    # Enhanced success validation
                    is_success, failure_reason = self._validate_tool_call_success(
                        tool_call, res, self.last_user_message
                    )

                    if is_success:
                        self.realtime_eval_scores[model_name][tool_name]["success"] += 1
                    else:
                        self.realtime_eval_scores[model_name][tool_name]["failure"] += 1
                        error_msg = f"{failure_reason}: {res['content'][:200]}"
                        self.realtime_eval_scores[model_name][tool_name]["errors"].append(error_msg)

                log_message(f"CHAT_INTERFACE: Updated real-time scores for {model_name}: {self.realtime_eval_scores[model_name]}")
                self.add_message("system", f"📈 Real-time score updated for {model_name}.")

            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed during training mode operation: {e}")
                self.add_message("error", f"Failed to process training data: {e}")

        # Send tool results back to model for final response
        self.add_message("system", "📨 Sending tool results to model...")
        threading.Thread(
            target=self.generate_final_response_after_tools,
            daemon=True
        ).start()

    def generate_final_response_after_tools(self):
        """Generate final response after tool execution"""
        try:
            log_message("CHAT_INTERFACE: Generating final response after tool execution")

            # Prepare payload with tool results
            payload = {
                "model": self.current_model,
                "messages": self.chat_history,
                "stream": False,
                "options": {
                    "temperature": self.session_temperature
                }
            }

            # Call Ollama API
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(payload, f)
                payload_file = f.name

            try:
                result = subprocess.run(
                    ["curl", "-s", "-X", "POST", "http://localhost:11434/api/chat",
                     "-H", "Content-Type: application/json",
                     "-d", f"@{payload_file}"],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
            finally:
                Path(payload_file).unlink(missing_ok=True)

            if result.returncode != 0:
                error_msg = f"Ollama error: {result.stderr}"
                log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
                self.root.after(0, lambda: self.add_message("error", error_msg))
            else:
                # Parse final response
                response_data = json.loads(result.stdout)
                response_content = response_data.get("message", {}).get("content", "")

                # Add to history
                self.chat_history.append({"role": "assistant", "content": response_content})

                # Display response
                self.root.after(0, lambda: self.add_message("assistant", response_content))
                log_message("CHAT_INTERFACE: Final response generated successfully")

                # Auto-save conversation
                if self.backend_settings.get('auto_save_history', True):
                    self.root.after(0, self._auto_save_conversation)

        except Exception as e:
            error_msg = f"Error generating final response: {str(e)}"
            log_message(f"CHAT_INTERFACE ERROR: {error_msg}")
            self.root.after(0, lambda: self.add_message("error", error_msg))
        finally:
            self.root.after(0, self.reset_buttons)

    def initialize_tool_executor(self):
        """Initialize the tool executor"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_executor import ToolExecutor

            # Get working directory from settings if available
            working_dir = None
            if hasattr(self, 'backend_settings'):
                working_dir_str = self.backend_settings.get('working_directory')
                if working_dir_str:
                    working_dir = Path(working_dir_str)

            self.tool_executor = ToolExecutor(working_dir=working_dir)
            log_message(f"CHAT_INTERFACE: Tool executor initialized with working dir: {self.tool_executor.working_dir}")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool executor: {e}")
            self.tool_executor = None

    def initialize_tool_logging(self):
        """Initialize tool call logger and detector"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from tool_call_logger import ToolCallLogger
            from tool_call_detector import ToolCallDetector

            self.tool_call_logger = ToolCallLogger()
            self.tool_call_detector = ToolCallDetector()
            log_message("CHAT_INTERFACE: Tool call logger and detector initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize tool logging: {e}")
            self.tool_call_logger = None
            self.tool_call_detector = None

    def initialize_history_manager(self):
        """Initialize chat history manager"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from chat_history_manager import ChatHistoryManager

            self.chat_history_manager = ChatHistoryManager()
            log_message("CHAT_INTERFACE: Chat history manager initialized")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to initialize history manager: {e}")
            self.chat_history_manager = None

    def load_enabled_tools(self):
        """Load enabled tools from settings"""
        tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"

        if tool_settings_file.exists():
            try:
                with open(tool_settings_file, 'r') as f:
                    settings = json.load(f)
                return settings.get('enabled_tools', {})
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load tool settings: {e}")

        # Default: all safe tools enabled
        return {}

    def get_tool_schemas(self):
        """Get Ollama tool schemas for enabled tools"""
        try:
            from tool_schemas import get_enabled_tool_schemas

            enabled_tools = self.load_enabled_tools()
            schemas = get_enabled_tool_schemas(enabled_tools)

            log_message(f"CHAT_INTERFACE: Loaded {len(schemas)} enabled tool schemas")
            return schemas

        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to load tool schemas: {e}")
            return []

    def load_backend_settings(self):
        """Load backend settings from custom_code_settings.json"""
        settings_file = Path(__file__).parent.parent / "custom_code_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CHAT_INTERFACE: Backend settings loaded")
                    return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load backend settings: {e}")

        # Return defaults
        return {
            'working_directory': str(Path.cwd()),
            'auto_mount_model': False,
            'auto_save_history': True,
            'show_tool_call_details': True,
            'tool_timeout': 30
        }

    def load_advanced_settings(self):
        """Load advanced settings from advanced_settings.json"""
        settings_file = Path(__file__).parent.parent / "advanced_settings.json"

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("CHAT_INTERFACE: Advanced settings loaded")
                    return settings
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to load advanced settings: {e}")

        # Return defaults (all disabled)
        return {
            'format_translation': {'enabled': False},
            'json_repair': {'enabled': False},
            'schema_validation': {'enabled': False},
            'tool_orchestrator': {'enabled': False},
            'intelligent_routing': {'enabled': False},
            'resource_management': {'profile': 'balanced'},
            'time_slicing': {'enabled': False},
            'context_scoring': {'enabled': False},
            'pre_rag_optimizer': {'enabled': False},
            'verification': {'enabled': False},
            'quality_assurance': {'enabled': False}
        }

    def initialize_advanced_components(self):
        """Initialize advanced OpenCode components based on settings"""
        if self.is_standard_mode:
            log_message("CHAT_INTERFACE: Standard mode is active, bypassing advanced component initialization.")
            self.format_translator = None
            self.json_fixer_enabled = False
            self.schema_validator = None
            self.tool_orchestrator = None
            self.router = None
            self.time_slicer = None
            self.context_scorer = None
            self.pre_rag_optimizer = None
            self.verification_engine = None
            self.quality_assurance = None
            self.adaptive_workflow = None
            self.agentic_project = None
            self.workflow_optimizer = None
            self.project_store = None
            self.session_manager_adv = None
            self.master_quality = None
            self.quality_recovery = None
            self.performance_benchmark = None
            self.rag_feedback = None
            self.complexity_analyzer = None
            self.hardening_manager = None
            self.atomic_writer = None
            self.confirmation_gates_standalone = None
            self.model_optimizer = None
            self.model_selector = None
            self.quant_manager = None
            self.mvco_engine = None
            self.auto_policy = None
            self.command_policy = None
            self.mcp_integration = None
            self.mcp_server = None
            self.langchain_adapter = None
            self.instant_hooks = None
            self.version_manager = None
            self.ollama_direct = None
            return

        # Add path for OpenCode modules
        sys.path.insert(0, str(Path(__file__).parent.parent / "site-packages"))

        # Format Translator
        if self.advanced_settings.get('format_translation', {}).get('enabled', False):
            try:
                from opencode.format_translator import FormatTranslator
                self.format_translator = FormatTranslator()
                log_message("CHAT_INTERFACE: FormatTranslator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: FormatTranslator enabled with settings: " +
                               json.dumps(self.advanced_settings.get('format_translation', {})))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize FormatTranslator: {e}")
                self.format_translator = None
        else:
            self.format_translator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: FormatTranslator disabled")

        # JSON Fixer
        if self.advanced_settings.get('json_repair', {}).get('enabled', False):
            try:
                from opencode.json_fixer import smart_json_parse, parse_partial_json
                self.json_fixer_enabled = True
                self.smart_json_parse = smart_json_parse
                self.parse_partial_json = parse_partial_json
                log_message("CHAT_INTERFACE: JSON Fixer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: JSON Fixer enabled with aggressiveness: " +
                               self.advanced_settings.get('json_repair', {}).get('aggressiveness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize JSON Fixer: {e}")
                self.json_fixer_enabled = False
        else:
            self.json_fixer_enabled = False
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: JSON Fixer disabled")

        # Schema Validator
        if self.advanced_settings.get('schema_validation', {}).get('enabled', False):
            try:
                from opencode.tool_schema_validator import ToolSchemaValidator
                self.schema_validator = ToolSchemaValidator()
                log_message("CHAT_INTERFACE: Schema Validator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Schema Validator enabled with mode: " +
                               self.advanced_settings.get('schema_validation', {}).get('mode', 'permissive'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Schema Validator: {e}")
                self.schema_validator = None
        else:
            self.schema_validator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Schema Validator disabled")

        # Tool Orchestrator
        if self.advanced_settings.get('tool_orchestrator', {}).get('enabled', False):
            try:
                from opencode.tool_orchestrator import AdvancedToolOrchestrator
                from opencode.config import Config
                config = Config()
                # Tool manager will be the tool_executor
                self.tool_orchestrator = AdvancedToolOrchestrator(self.tool_executor, config)
                log_message("CHAT_INTERFACE: Tool Orchestrator initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Tool Orchestrator enabled with risk_assessment: " +
                               str(self.advanced_settings.get('tool_orchestrator', {}).get('risk_assessment', True)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Tool Orchestrator: {e}")
                self.tool_orchestrator = None
        else:
            self.tool_orchestrator = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Tool Orchestrator disabled")

        # Intelligent Router
        if self.advanced_settings.get('intelligent_routing', {}).get('enabled', False):
            try:
                from opencode.router import Router
                self.router = Router()
                log_message("CHAT_INTERFACE: Intelligent Router initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Router enabled with confidence threshold: " +
                               str(self.advanced_settings.get('intelligent_routing', {}).get('confidence_threshold', 0.7)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Router: {e}")
                self.router = None
        else:
            self.router = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Intelligent Router disabled")

        # Resource Management (applied to tool executor)
        resource_profile = self.advanced_settings.get('resource_management', {}).get('profile', 'balanced')
        try:
            from opencode.runtime_profiles import resource_manager
            profile = resource_manager.get_profile_by_name(resource_profile)

            # Apply profile constraints to tool executor if it exists
            if self.tool_executor and hasattr(self.tool_executor, 'set_resource_limits'):
                limits = {
                    'num_threads': profile.num_threads,
                    'max_tokens': profile.max_tokens,
                    'memory_limit_mb': profile.memory_limit_mb if hasattr(profile, 'memory_limit_mb') else None
                }
                self.tool_executor.set_resource_limits(limits)
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Applied resource profile '{resource_profile}' to tool executor: {limits}")
            else:
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Resource profile '{resource_profile}' loaded but not applied (tool executor doesn't support limits)")
        except Exception as e:
            if self.backend_settings.get('enable_debug_logging', False):
                log_message(f"DEBUG: Failed to apply resource profile: {e}")

        # Time Slicer
        if self.advanced_settings.get('time_slicing', {}).get('enabled', False):
            try:
                from opencode.time_slicer import TimeSlicedGenerator, TimeBudget
                from opencode.runtime_profiles import resource_manager
                profile = resource_manager.get_profile_by_name(resource_profile)
                self.time_slicer = TimeSlicedGenerator(profile)
                log_message("CHAT_INTERFACE: Time Slicer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Time Slicer enabled with tokens_per_slice: " +
                               str(self.advanced_settings.get('time_slicing', {}).get('tokens_per_slice', 32)))
                    log_message("DEBUG: Note - Time Slicer requires streaming mode (stream=True) to function")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Time Slicer: {e}")
                self.time_slicer = None
        else:
            self.time_slicer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Time Slicer disabled")

        # Context Scorer
        if self.advanced_settings.get('context_scoring', {}).get('enabled', False):
            try:
                from opencode.context_scorer import AdaptiveContextScorer
                from opencode.config import Config
                config = Config()
                self.context_scorer = AdaptiveContextScorer(config)
                log_message("CHAT_INTERFACE: Context Scorer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Context Scorer enabled with memory_threshold: " +
                               str(self.advanced_settings.get('context_scoring', {}).get('memory_threshold_percent', 85)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Context Scorer: {e}")
                self.context_scorer = None
        else:
            self.context_scorer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Context Scorer disabled")

        # Pre-RAG Optimizer
        if self.advanced_settings.get('pre_rag_optimizer', {}).get('enabled', False):
            try:
                from opencode.pre_rag_optimizer import PreRAGOptimizer
                from opencode.config import Config
                config = Config()
                self.pre_rag_optimizer = PreRAGOptimizer(config)
                log_message("CHAT_INTERFACE: Pre-RAG Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    optimizations = self.advanced_settings.get('pre_rag_optimizer', {}).get('optimizations', {})
                    log_message("DEBUG: Pre-RAG Optimizer enabled with optimizations: " + json.dumps(optimizations))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Pre-RAG Optimizer: {e}")
                self.pre_rag_optimizer = None
        else:
            self.pre_rag_optimizer = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Pre-RAG Optimizer disabled")

        # Verification Engine
        if self.advanced_settings.get('verification', {}).get('enabled', False):
            try:
                from opencode.verification_engine import VerificationEngine
                self.verification_engine = VerificationEngine()
                log_message("CHAT_INTERFACE: Verification Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Verification Engine enabled with strictness: " +
                               self.advanced_settings.get('verification', {}).get('strictness', 'medium'))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Verification Engine: {e}")
                self.verification_engine = None
        else:
            self.verification_engine = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Verification Engine disabled")

        # Quality Assurance
        if self.advanced_settings.get('quality_assurance', {}).get('enabled', False):
            try:
                from opencode.quality_integration import QualityIntegration
                self.quality_assurance = QualityIntegration()
                log_message("CHAT_INTERFACE: Quality Assurance initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message("DEBUG: Quality Assurance enabled with threshold: " +
                               str(self.advanced_settings.get('quality_assurance', {}).get('threshold', 0.8)))
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Assurance: {e}")
                self.quality_assurance = None
        else:
            self.quality_assurance = None
            if self.backend_settings.get('enable_debug_logging', False):
                log_message("DEBUG: Quality Assurance disabled")

        # ========== Additional 26 Systems ==========

        # Adaptive Workflow Engine
        if self.advanced_settings.get('adaptive_workflow', {}).get('enabled', False):
            try:
                from opencode.adaptive_workflow_engine import AdaptiveWorkflowEngine
                self.adaptive_workflow = AdaptiveWorkflowEngine()
                log_message("CHAT_INTERFACE: Adaptive Workflow Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Adaptive Workflow enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Adaptive Workflow: {e}")
                self.adaptive_workflow = None
        else:
            self.adaptive_workflow = None

        # Agentic Project System
        if self.advanced_settings.get('agentic_project', {}).get('enabled', False):
            try:
                from opencode.agentic_project_system import AgenticProjectSystem
                self.agentic_project = AgenticProjectSystem()
                log_message("CHAT_INTERFACE: Agentic Project System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Agentic Project enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Agentic Project: {e}")
                self.agentic_project = None
        else:
            self.agentic_project = None

        # Workflow Optimizer
        if self.advanced_settings.get('workflow_optimizer', {}).get('enabled', False):
            try:
                from opencode.workflow_optimizer import WorkflowOptimizer
                self.workflow_optimizer = WorkflowOptimizer()
                log_message("CHAT_INTERFACE: Workflow Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Workflow Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Workflow Optimizer: {e}")
                self.workflow_optimizer = None
        else:
            self.workflow_optimizer = None

        # Project Store
        if self.advanced_settings.get('project_store', {}).get('enabled', False):
            try:
                from opencode.project_store import ProjectStore
                self.project_store = ProjectStore()
                log_message("CHAT_INTERFACE: Project Store initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Project Store enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Project Store: {e}")
                self.project_store = None
        else:
            self.project_store = None

        # Session Manager
        if self.advanced_settings.get('session_manager', {}).get('enabled', False):
            try:
                from opencode.session_manager import SessionManager
                self.session_manager_adv = SessionManager()
                log_message("CHAT_INTERFACE: Session Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Session Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Session Manager: {e}")
                self.session_manager_adv = None
        else:
            self.session_manager_adv = None

        # Master Quality System
        if self.advanced_settings.get('master_quality', {}).get('enabled', False):
            try:
                from opencode.master_quality_system import MasterQualitySystem
                self.master_quality = MasterQualitySystem()
                log_message("CHAT_INTERFACE: Master Quality System initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Master Quality System enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Master Quality: {e}")
                self.master_quality = None
        else:
            self.master_quality = None

        # Quality Recovery Engine
        if self.advanced_settings.get('quality_recovery', {}).get('enabled', False):
            try:
                from opencode.quality_recovery_engine import QualityRecoveryEngine
                self.quality_recovery = QualityRecoveryEngine()
                log_message("CHAT_INTERFACE: Quality Recovery Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quality Recovery enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quality Recovery: {e}")
                self.quality_recovery = None
        else:
            self.quality_recovery = None

        # Performance Benchmark
        if self.advanced_settings.get('performance_benchmark', {}).get('enabled', False):
            try:
                from opencode.performance_benchmark_system import PerformanceBenchmarkSystem
                self.performance_benchmark = PerformanceBenchmarkSystem()
                log_message("CHAT_INTERFACE: Performance Benchmark initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Performance Benchmark enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Performance Benchmark: {e}")
                self.performance_benchmark = None
        else:
            self.performance_benchmark = None

        # RAG Feedback Engine
        if self.advanced_settings.get('rag_feedback', {}).get('enabled', False):
            try:
                from opencode.rag_feedback_engine import RAGFeedbackEngine
                self.rag_feedback = RAGFeedbackEngine()
                log_message("CHAT_INTERFACE: RAG Feedback Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: RAG Feedback enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize RAG Feedback: {e}")
                self.rag_feedback = None
        else:
            self.rag_feedback = None

        # Complexity Analyzer
        if self.advanced_settings.get('complexity_analyzer', {}).get('enabled', False):
            try:
                from opencode.complexity_analyzer import ComplexityAnalyzer
                self.complexity_analyzer = ComplexityAnalyzer()
                log_message("CHAT_INTERFACE: Complexity Analyzer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Complexity Analyzer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Complexity Analyzer: {e}")
                self.complexity_analyzer = None
        else:
            self.complexity_analyzer = None

        # Hardening Manager
        if self.advanced_settings.get('hardening_manager', {}).get('enabled', False):
            try:
                from opencode.hardening_manager import HardeningManager
                self.hardening_manager = HardeningManager()
                log_message("CHAT_INTERFACE: Hardening Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Hardening Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Hardening Manager: {e}")
                self.hardening_manager = None
        else:
            self.hardening_manager = None

        # Atomic Writer
        if self.advanced_settings.get('atomic_writer', {}).get('enabled', False):
            try:
                from opencode.atomic_writer import AtomicWriter
                self.atomic_writer = AtomicWriter()
                log_message("CHAT_INTERFACE: Atomic Writer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Atomic Writer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Atomic Writer: {e}")
                self.atomic_writer = None
        else:
            self.atomic_writer = None

        # Confirmation Gates (standalone)
        if self.advanced_settings.get('confirmation_gates', {}).get('enabled', False):
            try:
                from opencode.confirmation_gates import ConfirmationGates
                self.confirmation_gates_standalone = ConfirmationGates()
                log_message("CHAT_INTERFACE: Confirmation Gates initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Confirmation Gates enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Confirmation Gates: {e}")
                self.confirmation_gates_standalone = None
        else:
            self.confirmation_gates_standalone = None

        # Model Optimizer
        if self.advanced_settings.get('model_optimizer', {}).get('enabled', False):
            try:
                from opencode.model_optimizer import ModelOptimizer
                self.model_optimizer = ModelOptimizer()
                log_message("CHAT_INTERFACE: Model Optimizer initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Optimizer enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Optimizer: {e}")
                self.model_optimizer = None
        else:
            self.model_optimizer = None

        # Model Selector
        if self.advanced_settings.get('model_selector', {}).get('enabled', False):
            try:
                from opencode.model_selector import ModelSelector
                self.model_selector = ModelSelector()
                log_message("CHAT_INTERFACE: Model Selector initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Model Selector enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Model Selector: {e}")
                self.model_selector = None
        else:
            self.model_selector = None

        # Quant Manager
        if self.advanced_settings.get('quant_manager', {}).get('enabled', False):
            try:
                from opencode.quant_manager import QuantManager
                self.quant_manager = QuantManager()
                log_message("CHAT_INTERFACE: Quant Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Quant Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Quant Manager: {e}")
                self.quant_manager = None
        else:
            self.quant_manager = None

        # MVCO Engine
        if self.advanced_settings.get('mvco_engine', {}).get('enabled', False):
            try:
                from opencode.mvco_engine import MVCOEngine
                self.mvco_engine = MVCOEngine()
                log_message("CHAT_INTERFACE: MVCO Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MVCO Engine enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MVCO Engine: {e}")
                self.mvco_engine = None
        else:
            self.mvco_engine = None

        # Auto Policy
        if self.advanced_settings.get('auto_policy', {}).get('enabled', False):
            try:
                from opencode.auto_policy import AutoPolicy
                self.auto_policy = AutoPolicy()
                log_message("CHAT_INTERFACE: Auto Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Auto Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Auto Policy: {e}")
                self.auto_policy = None
        else:
            self.auto_policy = None

        # Command Policy
        if self.advanced_settings.get('command_policy', {}).get('enabled', False):
            try:
                from opencode.command_policy import CommandPolicy
                self.command_policy = CommandPolicy()
                log_message("CHAT_INTERFACE: Command Policy initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Command Policy enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Command Policy: {e}")
                self.command_policy = None
        else:
            self.command_policy = None

        # MCP Integration
        if self.advanced_settings.get('mcp_integration', {}).get('enabled', False):
            try:
                from opencode.mcp_integration import MCPIntegration
                self.mcp_integration = MCPIntegration()
                log_message("CHAT_INTERFACE: MCP Integration initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Integration enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Integration: {e}")
                self.mcp_integration = None
        else:
            self.mcp_integration = None

        # MCP Server
        if self.advanced_settings.get('mcp_server', {}).get('enabled', False):
            try:
                from opencode.mcp_server_wrapper import MCPServerWrapper
                self.mcp_server = MCPServerWrapper()
                log_message("CHAT_INTERFACE: MCP Server initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: MCP Server enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize MCP Server: {e}")
                self.mcp_server = None
        else:
            self.mcp_server = None

        # LangChain Adapter
        if self.advanced_settings.get('langchain_adapter', {}).get('enabled', False):
            try:
                adapter_type = self.advanced_settings.get('langchain_adapter', {}).get('adapter_type', 'simple')
                if adapter_type == 'simple':
                    from opencode.langchain_adapter_simple import LangChainAdapterSimple
                    self.langchain_adapter = LangChainAdapterSimple()
                else:
                    from opencode.langchain_adapter import LangChainAdapter
                    self.langchain_adapter = LangChainAdapter()
                log_message(f"CHAT_INTERFACE: LangChain Adapter ({adapter_type}) initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: LangChain Adapter enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize LangChain Adapter: {e}")
                self.langchain_adapter = None
        else:
            self.langchain_adapter = None

        # Instant Hooks Engine
        if self.advanced_settings.get('instant_hooks', {}).get('enabled', False):
            try:
                from opencode.instant_hook_engine import InstantHookEngine
                self.instant_hooks = InstantHookEngine()
                log_message("CHAT_INTERFACE: Instant Hook Engine initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Instant Hooks enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Instant Hooks: {e}")
                self.instant_hooks = None
        else:
            self.instant_hooks = None

        # Version Manager
        if self.advanced_settings.get('version_manager', {}).get('enabled', False):
            try:
                from opencode.version_manager import VersionManager
                self.version_manager = VersionManager()
                log_message("CHAT_INTERFACE: Version Manager initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Version Manager enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Version Manager: {e}")
                self.version_manager = None
        else:
            self.version_manager = None

        # Ollama Direct Client
        if self.advanced_settings.get('ollama_direct', {}).get('enabled', False):
            try:
                from opencode.ollama_client import OllamaClient
                self.ollama_direct = OllamaClient()
                log_message("CHAT_INTERFACE: Ollama Direct Client initialized")
                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG: Ollama Direct Client enabled")
            except Exception as e:
                log_message(f"CHAT_INTERFACE ERROR: Failed to initialize Ollama Direct: {e}")
                self.ollama_direct = None
        else:
            self.ollama_direct = None

    def _ensure_prompt_schema_dirs(self):
        """Ensure system_prompts and tool_schemas_configs directories exist"""
        self.system_prompts_dir.mkdir(exist_ok=True)
        self.tool_schemas_dir.mkdir(exist_ok=True)

        # Create default system prompt if doesn't exist
        default_prompt_file = self.system_prompts_dir / "default.txt"
        if not default_prompt_file.exists():
            with open(default_prompt_file, 'w') as f:
                f.write("You are a helpful AI assistant with access to various tools. Use them when appropriate to help the user.")

        # Create default tool schema config if doesn't exist
        default_schema_file = self.tool_schemas_dir / "default.json"
        if not default_schema_file.exists():
            with open(default_schema_file, 'w') as f:
                json.dump({"enabled_tools": "all", "description": "Default - All tools enabled"}, f, indent=2)

    def select_system_prompt(self):
        """Open dialog to select and edit system prompt"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("System Prompt Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Prompt list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Prompts",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for prompts
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        prompt_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        prompt_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=prompt_listbox.yview)

        # Load prompts
        prompts = sorted([f.stem for f in self.system_prompts_dir.glob("*.txt")])
        for prompt in prompts:
            prompt_listbox.insert(tk.END, prompt)
            if prompt == self.current_system_prompt:
                prompt_listbox.selection_set(prompts.index(prompt))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        prompt_name_label = ttk.Label(
            header_frame,
            text="Select a prompt to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        prompt_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_prompt_name = [None]
        modified = [False]

        def load_prompt(event=None):
            """Load selected prompt into editor"""
            selection = prompt_listbox.curselection()
            if not selection:
                return

            # Check if current prompt was modified
            if modified[0] and current_prompt_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_prompt_name[0]}'.\n\nSave before switching?"
                ):
                    save_prompt()

            prompt_name = prompt_listbox.get(selection[0])
            current_prompt_name[0] = prompt_name
            modified[0] = False

            prompt_file = self.system_prompts_dir / f"{prompt_name}.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r') as f:
                    content = f.read()
                editor.delete(1.0, tk.END)
                editor.insert(1.0, content)
                prompt_name_label.config(text=f"📝 {prompt_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_prompt_name[0]:
                prompt_name_label.config(text=f"📝 {current_prompt_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        prompt_listbox.bind('<<ListboxSelect>>', load_prompt)

        # Load initially selected prompt
        if prompt_listbox.curselection():
            load_prompt()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        def save_prompt():
            """Save current prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Prompt content cannot be empty")
                return

            prompt_file = self.system_prompts_dir / f"{current_prompt_name[0]}.txt"
            with open(prompt_file, 'w') as f:
                f.write(content)

            modified[0] = False
            prompt_name_label.config(text=f"📝 {current_prompt_name[0]}")
            messagebox.showinfo("Saved", f"Prompt '{current_prompt_name[0]}' saved successfully")

        def new_prompt():
            """Create new prompt"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Prompt", "Enter prompt name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Prompt name must contain alphanumeric characters")
                    return

                prompt_file = self.system_prompts_dir / f"{name}.txt"
                if prompt_file.exists():
                    messagebox.showerror("Exists", f"Prompt '{name}' already exists")
                    return

                # Create empty prompt
                with open(prompt_file, 'w') as f:
                    f.write("You are a helpful AI assistant.")

                # Reload list
                prompt_listbox.insert(tk.END, name)
                prompt_listbox.selection_clear(0, tk.END)
                prompt_listbox.selection_set(tk.END)
                load_prompt()

        def delete_prompt():
            """Delete selected prompt"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            if current_prompt_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default prompt")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_prompt_name[0]}'?"
            ):
                prompt_file = self.system_prompts_dir / f"{current_prompt_name[0]}.txt"
                prompt_file.unlink(missing_ok=True)

                # Reload list
                selection = prompt_listbox.curselection()
                prompt_listbox.delete(selection[0])
                current_prompt_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                prompt_name_label.config(text="Select a prompt to view/edit")

        def select_and_apply():
            """Select prompt and apply it"""
            if not current_prompt_name[0]:
                messagebox.showwarning("No Selection", "Please select a prompt first")
                return

            # Save if modified
            if modified[0]:
                save_prompt()

            self.current_system_prompt = current_prompt_name[0]
            self.add_message("system", f"✓ Loaded system prompt: {current_prompt_name[0]}")
            log_message(f"CHAT_INTERFACE: Loaded system prompt: {current_prompt_name[0]}")

            # Remount model to apply new prompt
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_prompt,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_prompt,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def select_tool_schema(self):
        """Open dialog to select and edit tool schema configuration"""
        from tkinter import messagebox

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Tool Schema Manager")
        dialog.geometry("900x700")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=0)  # List on left
        dialog.columnconfigure(1, weight=1)  # Editor on right
        dialog.rowconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=0)

        # Left panel - Schema list
        left_frame = ttk.Frame(dialog, style='Category.TFrame')
        left_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(10, 5), pady=10)

        ttk.Label(
            left_frame,
            text="Available Schemas",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=(0, 5))

        # Listbox for schemas
        list_frame = ttk.Frame(left_frame, style='Category.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        schema_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg='#1e1e1e',
            fg='#ffffff',
            selectbackground='#61dafb',
            font=("Arial", 10),
            width=25
        )
        schema_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=schema_listbox.yview)

        # Load schemas
        schemas = sorted([f.stem for f in self.tool_schemas_dir.glob("*.json")])
        for schema in schemas:
            schema_listbox.insert(tk.END, schema)
            if schema == self.current_tool_schema:
                schema_listbox.selection_set(schemas.index(schema))

        # Right panel - Editor
        right_frame = ttk.Frame(dialog, style='Category.TFrame')
        right_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 10), pady=10)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)

        # Editor header
        header_frame = ttk.Frame(right_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 5))
        header_frame.columnconfigure(0, weight=1)

        schema_name_label = ttk.Label(
            header_frame,
            text="Select a schema to view/edit",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        )
        schema_name_label.grid(row=0, column=0, sticky=tk.W)

        # Text editor
        editor = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg='#1e1e1e',
            fg='#ffffff',
            insertbackground='#61dafb'
        )
        editor.grid(row=1, column=0, sticky=tk.NSEW)

        # Track current selection
        current_schema_name = [None]
        modified = [False]

        def load_schema(event=None):
            """Load selected schema into editor"""
            selection = schema_listbox.curselection()
            if not selection:
                return

            # Check if current schema was modified
            if modified[0] and current_schema_name[0]:
                if messagebox.askyesno(
                    "Unsaved Changes",
                    f"You have unsaved changes to '{current_schema_name[0]}'.\n\nSave before switching?"
                ):
                    save_schema()

            schema_name = schema_listbox.get(selection[0])
            current_schema_name[0] = schema_name
            modified[0] = False

            schema_file = self.tool_schemas_dir / f"{schema_name}.json"
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    content = f.read()
                editor.delete(1.0, tk.END)
                editor.insert(1.0, content)
                schema_name_label.config(text=f"🔧 {schema_name}")

        def on_text_change(event=None):
            """Mark as modified when text changes"""
            modified[0] = True
            if current_schema_name[0]:
                schema_name_label.config(text=f"🔧 {current_schema_name[0]} *")

        editor.bind('<KeyRelease>', on_text_change)
        schema_listbox.bind('<<ListboxSelect>>', load_schema)

        # Load initially selected schema
        if schema_listbox.curselection():
            load_schema()

        # Bottom buttons
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, padx=10, pady=(0, 10))

        def save_schema():
            """Save current schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            content = editor.get(1.0, tk.END).strip()
            if not content:
                messagebox.showwarning("Empty Content", "Schema content cannot be empty")
                return

            # Validate JSON
            try:
                schema_data = json.loads(content)
            except json.JSONDecodeError as e:
                messagebox.showerror("Invalid JSON", f"JSON validation failed:\n{str(e)}")
                return

            # Validate schema structure
            if "enabled_tools" not in schema_data:
                messagebox.showerror("Invalid Schema", "Schema must contain 'enabled_tools' field")
                return

            schema_file = self.tool_schemas_dir / f"{current_schema_name[0]}.json"
            with open(schema_file, 'w') as f:
                json.dump(schema_data, f, indent=2)

            modified[0] = False
            schema_name_label.config(text=f"🔧 {current_schema_name[0]}")
            messagebox.showinfo("Saved", f"Schema '{current_schema_name[0]}' saved successfully")

        def new_schema():
            """Create new schema"""
            from tkinter import simpledialog
            name = simpledialog.askstring("New Schema", "Enter schema name:")
            if name:
                # Clean name
                name = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
                if not name:
                    messagebox.showerror("Invalid Name", "Schema name must contain alphanumeric characters")
                    return

                schema_file = self.tool_schemas_dir / f"{name}.json"
                if schema_file.exists():
                    messagebox.showerror("Exists", f"Schema '{name}' already exists")
                    return

                # Create default schema
                default_schema = {
                    "enabled_tools": "all",
                    "description": f"Custom schema: {name}"
                }
                with open(schema_file, 'w') as f:
                    json.dump(default_schema, f, indent=2)

                # Reload list
                schema_listbox.insert(tk.END, name)
                schema_listbox.selection_clear(0, tk.END)
                schema_listbox.selection_set(tk.END)
                load_schema()

        def delete_schema():
            """Delete selected schema"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            if current_schema_name[0] == "default":
                messagebox.showerror("Cannot Delete", "Cannot delete the default schema")
                return

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete '{current_schema_name[0]}'?"
            ):
                schema_file = self.tool_schemas_dir / f"{current_schema_name[0]}.json"
                schema_file.unlink(missing_ok=True)

                # Reload list
                selection = schema_listbox.curselection()
                schema_listbox.delete(selection[0])
                current_schema_name[0] = None
                modified[0] = False
                editor.delete(1.0, tk.END)
                schema_name_label.config(text="Select a schema to view/edit")

        def select_and_apply():
            """Select schema and apply it"""
            if not current_schema_name[0]:
                messagebox.showwarning("No Selection", "Please select a schema first")
                return

            # Save if modified
            if modified[0]:
                save_schema()

            self.current_tool_schema = current_schema_name[0]
            self.add_message("system", f"✓ Loaded tool schema: {current_schema_name[0]}")
            log_message(f"CHAT_INTERFACE: Loaded tool schema: {current_schema_name[0]}")

            # Reload tool schemas
            self.tool_executor._initialize_tools()

            # Remount model to apply new schema
            if self.is_mounted:
                self.dismount_model()
                self.root.after(500, self.mount_model)

            dialog.destroy()

        # Buttons
        ttk.Button(
            button_frame,
            text="💾 Save",
            command=save_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="➕ New",
            command=new_schema,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_schema,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="✓ Select & Apply",
            command=select_and_apply,
            style='Action.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def _format_tools_for_prompt(self) -> str:
        """Format enabled tool schemas as a text block for system prompt injection."""
        try:
            tool_schemas = self.get_tool_schemas()
            schema_config = self.get_current_tool_schema_config()
            if schema_config.get("enabled_tools") != "all":
                enabled_list = schema_config.get("enabled_tools", [])
                tool_schemas = [t for t in tool_schemas
                                if t.get('function', {}).get('name') in enabled_list]

            if not tool_schemas:
                return "(no tools enabled)"

            lines = []
            for ts in tool_schemas:
                fn = ts.get('function', {})
                name = fn.get('name', '?')
                desc = fn.get('description', '')
                params = fn.get('parameters', {}).get('properties', {})
                req = fn.get('parameters', {}).get('required', [])
                param_str = ', '.join(
                    f"{k}: {v.get('type', 'str')}" + (" (required)" if k in req else "")
                    for k, v in params.items()
                )
                lines.append(f"- {name}({param_str}) — {desc}")
            return '\n'.join(lines)
        except Exception as e:
            log_message(f"CHAT: _format_tools_for_prompt error: {e}")
            return "(tools list unavailable)"

    def get_current_system_prompt(self):
        """Get the current system prompt content with template vars resolved."""
        prompt_file = self.system_prompts_dir / f"{self.current_system_prompt}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                raw = f.read()
        else:
            raw = "You are a helpful AI assistant."

        # Resolve template variables ({available_tools}, {working_dir})
        _tools_text = self._format_tools_for_prompt()
        _wd = self.tool_executor.get_working_directory() if self.tool_executor else '.'
        try:
            return raw.replace('{available_tools}', _tools_text).replace('{working_dir}', str(_wd))
        except Exception:
            return raw

    def get_current_tool_schema_config(self):
        """Get the current tool schema configuration"""
        schema_file = self.tool_schemas_dir / f"{self.current_tool_schema}.json"
        if schema_file.exists():
            with open(schema_file, 'r') as f:
                return json.load(f)
        return {"enabled_tools": "all"}

    def get_realtime_eval_scores(self):
        """Return the real-time evaluation scores"""
        return self.realtime_eval_scores

    def _validate_tool_call_success(self, tool_call, result, user_message):
        """
        Enhanced tool call validation beyond simple error string matching.

        Returns:
            Tuple[bool, str]: (is_success, failure_reason)
        """
        result_content = result.get('content', '')
        tool_name = tool_call.get('function', {}).get('name', 'unknown')

        # 1. Check for explicit error indicators
        error_indicators = ['Error:', 'error:', 'ERROR:', 'Exception:', 'Failed:', 'failed:']
        for indicator in error_indicators:
            if indicator in result_content:
                return False, "error_in_result"

        # 2. Check for empty or suspiciously short results for tools that should return data
        data_returning_tools = ['file_read', 'grep_search', 'list_directory', 'web_fetch', 'bash']
        if tool_name in data_returning_tools:
            if len(result_content.strip()) < 10:
                return False, "empty_result"

        # 3. Tool-specific validations
        if tool_name == 'file_read':
            # File read should not return "file not found" or similar
            if any(phrase in result_content.lower() for phrase in ['not found', 'does not exist', 'no such file']):
                return False, "file_not_found"

        elif tool_name == 'file_write':
            # File write should confirm success
            if not any(phrase in result_content.lower() for phrase in ['written', 'success', 'saved', 'created']):
                return False, "write_not_confirmed"

        elif tool_name == 'bash':
            # Bash commands with non-zero exit codes often indicate failure
            if 'exit code' in result_content.lower() and 'exit code 0' not in result_content.lower():
                return False, "non_zero_exit_code"

        elif tool_name == 'grep_search':
            # Grep with no matches might be valid, but if user asked for something specific, it's likely a failure
            if 'no matches found' in result_content.lower() or result_content.strip() == '':
                # Check if user was expecting specific content
                if user_message and any(word in user_message.lower() for word in ['find', 'search', 'where', 'show me']):
                    return False, "no_matches_found"

        # 4. Check result format makes sense (basic sanity check)
        # If result is just a stack trace or exception, it's likely a failure
        if result_content.count('\n') > 20 and 'Traceback' in result_content:
            return False, "exception_traceback"

        # If we got here, consider it a success
        return True, "success"

    def persist_realtime_scores(self, model_name=None):
        """Persist real-time scores to ToolCallLogger for permanent storage"""
        if not self.tool_call_logger:
            log_message("CHAT_INTERFACE: ToolCallLogger not available for persisting scores")
            return

        # If model_name not specified, persist all models' scores
        models_to_persist = [model_name] if model_name else list(self.realtime_eval_scores.keys())

        for model in models_to_persist:
            if model not in self.realtime_eval_scores:
                continue

            log_message(f"CHAT_INTERFACE: Persisting real-time scores for {model}")

            for tool_name, stats in self.realtime_eval_scores[model].items():
                success_count = stats.get('success', 0)
                failure_count = stats.get('failure', 0)

                # Log each success and failure to ToolCallLogger
                # This updates the persistent tool_realtime_data.jsonl file
                for _ in range(success_count):
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},  # Args not tracked in realtime scores
                        result="Success (from realtime persistence)",
                        success=True,
                        model_name=model
                    )

                for error in stats.get('errors', [])[:failure_count]:
                    self.tool_call_logger.log_tool_call(
                        tool_name=tool_name,
                        tool_args={},
                        result=error,
                        success=False,
                        model_name=model
                    )

            log_message(f"CHAT_INTERFACE: ✓ Persisted real-time scores for {model}")

    def _auto_save_conversation(self):
        """Auto-save current conversation to persistent storage"""
        if not self.chat_history_manager or not self.current_model or not self.chat_history:
            return

        try:
            # Collect metadata
            current_mode = 'unknown'
            try:
                mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
                if mode_settings_file.exists():
                    with open(mode_settings_file, 'r') as f:
                        settings = json.load(f)
                    current_mode = settings.get('current_mode', 'unknown')
            except Exception:
                pass

            tool_settings = {}
            try:
                tool_settings_file = Path(__file__).parent.parent / "tool_settings.json"
                if tool_settings_file.exists():
                    with open(tool_settings_file, 'r') as f:
                        tool_settings = json.load(f)
            except Exception:
                pass

            metadata = {
                "mode": current_mode,
                "temperature": self.session_temperature,
                "system_prompt": self.current_system_prompt,
                "tool_schema": self.current_tool_schema,
                "working_directory": self.tool_executor.get_working_directory() if self.tool_executor else 'unknown',
                "training_data_collection": self.training_mode_enabled,
                "model": self.current_model,
                "tool_settings": tool_settings
            }

            # Save conversation
            session_id = self.chat_history_manager.save_conversation(
                model_name=self.current_model,
                chat_history=self.chat_history,
                session_name=self.current_session_id,
                metadata=metadata
            )

            # Update current session ID
            if session_id:
                self.current_session_id = session_id
                log_message(f"CHAT_INTERFACE: Auto-saved conversation as {session_id}")

                # Refresh the history tab in the parent
                if hasattr(self.parent_tab, 'refresh_history'):
                    self.root.after(0, self.parent_tab.refresh_history)

                # Refresh inline session dropdown
                if hasattr(self, 'history_combo'):
                    self.root.after(0, self._populate_history_dropdown)
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to auto-save conversation: {e}")

    def load_chat_history(self):
        """Open dialog to select and load a previous conversation"""
        from tkinter import messagebox

        if not self.chat_history_manager:
            messagebox.showerror("Error", "Chat history manager not initialized")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Chat History")
        dialog.geometry("800x600")
        dialog.configure(bg='#2b2b2b')

        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()

        # Main layout
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=0)  # Filter controls
        dialog.rowconfigure(1, weight=1)  # Chat list
        dialog.rowconfigure(2, weight=0)  # Buttons

        # Filter controls
        filter_frame = ttk.Frame(dialog, style='Category.TFrame')
        filter_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)
        filter_frame.columnconfigure(1, weight=1)

        ttk.Label(
            filter_frame,
            text="Filter by Model:",
            font=("Arial", 10),
            style='Config.TLabel'
        ).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))

        model_filter_var = tk.StringVar(value="All Models")
        model_filter = ttk.Combobox(
            filter_frame,
            textvariable=model_filter_var,
            state='readonly',
            font=("Arial", 10)
        )
        model_filter.grid(row=0, column=1, sticky=tk.EW, padx=(0, 10))

        # Get all unique model names
        all_conversations = self.chat_history_manager.list_conversations()
        model_names = sorted(list(set(conv["model_name"] for conv in all_conversations)))
        model_filter['values'] = ["All Models"] + model_names

        # Chat list frame
        list_frame = ttk.Frame(dialog, style='Category.TFrame')
        list_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Create Treeview for chat list
        tree_scroll = ttk.Scrollbar(list_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        chat_tree = ttk.Treeview(
            list_frame,
            columns=("Model", "Messages", "Date", "Preview"),
            show='headings',
            yscrollcommand=tree_scroll.set,
            style='Treeview'
        )
        chat_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=chat_tree.yview)

        # Configure columns
        chat_tree.heading("Model", text="Model")
        chat_tree.heading("Messages", text="Messages")
        chat_tree.heading("Date", text="Date")
        chat_tree.heading("Preview", text="Preview")

        chat_tree.column("Model", width=150, anchor=tk.W)
        chat_tree.column("Messages", width=80, anchor=tk.CENTER)
        chat_tree.column("Date", width=150, anchor=tk.W)
        chat_tree.column("Preview", width=300, anchor=tk.W)

        # Configure Treeview style
        style = ttk.Style()
        style.configure('Treeview', background='#1e1e1e', foreground='#ffffff', fieldbackground='#1e1e1e')
        style.map('Treeview', background=[('selected', '#61dafb')])

        def populate_tree(filter_model=None):
            """Populate tree with conversations"""
            chat_tree.delete(*chat_tree.get_children())

            conversations = self.chat_history_manager.list_conversations(
                model_name=filter_model if filter_model != "All Models" else None
            )

            for conv in conversations:
                # Format date
                date_str = conv.get("saved_at", "")
                if date_str:
                    try:
                        date_obj = datetime.fromisoformat(date_str)
                        date_formatted = date_obj.strftime("%Y-%m-%d %H:%M")
                    except:
                        date_formatted = date_str[:16]
                else:
                    date_formatted = "Unknown"

                chat_tree.insert(
                    "",
                    tk.END,
                    values=(
                        conv.get("model_name", "Unknown"),
                        conv.get("message_count", 0),
                        date_formatted,
                        conv.get("preview", "")
                    ),
                    tags=(conv.get("session_id", ""),)
                )

        # Initial population
        populate_tree()

        def on_filter_change(event=None):
            """Handle filter change"""
            populate_tree(model_filter_var.get())

        model_filter.bind('<<ComboboxSelected>>', on_filter_change)

        # Button frame
        button_frame = ttk.Frame(dialog, style='Category.TFrame')
        button_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        def load_selected():
            """Load the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to load")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Load conversation
            conversation = self.chat_history_manager.load_conversation(session_id)
            if not conversation:
                messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
                return

            # Check if we need to save current conversation
            if self.chat_history and self.backend_settings.get('auto_save_history', True):
                if messagebox.askyesno(
                    "Save Current Chat?",
                    "Do you want to save the current conversation before loading a new one?"
                ):
                    self._auto_save_conversation()

            # Load the conversation
            self.chat_history = conversation.get("chat_history", [])
            self.current_model = conversation.get("model_name")
            self.current_session_id = session_id

            # Update UI
            self.model_label.config(text=self.current_model)
            self.redisplay_conversation()
            self.add_message("system", f"✓ Loaded conversation: {session_id}")
            log_message(f"CHAT_INTERFACE: Loaded conversation {session_id}")

            dialog.destroy()

        def delete_selected():
            """Delete the selected conversation"""
            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to delete")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            if messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete this conversation?\n\n{session_id}"
            ):
                if self.chat_history_manager.delete_conversation(session_id):
                    messagebox.showinfo("Deleted", "Conversation deleted successfully")
                    populate_tree(model_filter_var.get())
                else:
                    messagebox.showerror("Error", "Failed to delete conversation")

        def export_selected():
            """Export the selected conversation"""
            from tkinter import filedialog

            selection = chat_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a conversation to export")
                return

            item = chat_tree.item(selection[0])
            session_id = item['tags'][0]

            # Ask for export format
            export_format = messagebox.askquestion(
                "Export Format",
                "Export as JSON?\n(No = Export as Text)",
                icon='question'
            )
            format_ext = "json" if export_format == "yes" else "txt"

            # Ask for save location
            export_path = filedialog.asksaveasfilename(
                title="Export Conversation",
                defaultextension=f".{format_ext}",
                filetypes=[(f"{format_ext.upper()} files", f"*.{format_ext}"), ("All files", "*.*")],
                initialfile=f"{session_id}.{format_ext}"
            )

            if export_path:
                if self.chat_history_manager.export_conversation(session_id, Path(export_path), format_ext):
                    messagebox.showinfo("Exported", f"Conversation exported to:\n{export_path}")
                else:
                    messagebox.showerror("Error", "Failed to export conversation")

        # Buttons
        ttk.Button(
            button_frame,
            text="✓ Load",
            command=load_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🗑️ Delete",
            command=delete_selected,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="📤 Export",
            command=export_selected,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

    def save_on_exit(self):
        """Save conversation when application is closing"""
        if self.chat_history and self.backend_settings.get('auto_save_history', True):
            self._auto_save_conversation()
            log_message("CHAT_INTERFACE: Saved conversation on exit")

    def set_training_mode(self, enabled):
        """Enable or disable training mode"""
        # If disabling training mode, persist any accumulated scores
        if not enabled and self.training_mode_enabled and self.realtime_eval_scores:
            log_message("CHAT_INTERFACE: Training mode being disabled - persisting real-time scores")
            self.persist_realtime_scores()  # Persist all models
            self.add_message("system", "💾 Real-time scores persisted to permanent storage.")

        self.training_mode_enabled = enabled
        log_message(f"CHAT_INTERFACE: Training mode set to {enabled}")
        self.add_message("system", f"📚 Training mode has been {'enabled' if enabled else 'disabled'}.")

    def set_mode_parameters(self, mode, params):
        """Set mode-specific parameters from the mode selector"""
        log_message(f"CHAT_INTERFACE: Setting mode to '{mode}' with params: {params}")

        if mode == 'standard':
            self.is_standard_mode = True
            self.add_message("system", "⚙️ Mode updated to Standard. Advanced systems bypassed.")
            # We don't change advanced_settings.json in standard mode
            self.initialize_advanced_components() # Re-initialize to disable components
            return

        self.is_standard_mode = False
        # Map mode to resource profile
        profile_map = {
            'fast': 'conservative',
            'smart': 'balanced',
            'think': 'aggressive'
        }
        profile = profile_map.get(mode, 'balanced')

        # Update advanced settings
        if 'resource_management' not in self.advanced_settings:
            self.advanced_settings['resource_management'] = {}
        self.advanced_settings['resource_management']['profile'] = profile

        # Potentially map other parameters from params to advanced_settings here
        # For now, we just handle the main profile

        # Save the updated settings to file
        try:
            settings_file = Path(__file__).parent.parent / "advanced_settings.json"
            with open(settings_file, 'w') as f:
                json.dump(self.advanced_settings, f, indent=2)
            log_message(f"CHAT_INTERFACE: Saved updated advanced settings for mode '{mode}'")
        except Exception as e:
            log_message(f"CHAT_INTERFACE ERROR: Failed to save advanced_settings.json: {e}")

        # Re-initialize advanced components to apply new settings
        self.initialize_advanced_components()

        self.add_message("system", f"⚙️ Mode updated to '{mode.capitalize()}' ({profile} profile). Settings applied.")

    def refresh(self):
        """Refresh the chat interface"""
        log_message("CHAT_INTERFACE: Refreshing...")
        # Reload backend settings
        self.backend_settings = self.load_backend_settings()

        # Reload advanced settings
        self.advanced_settings = self.load_advanced_settings()

        # Reinitialize advanced components
        self.initialize_advanced_components()

        # Update tool executor working directory if changed
        if self.tool_executor:
            working_dir = self.backend_settings.get('working_directory', str(Path.cwd()))
            self.tool_executor.set_working_directory(working_dir)
