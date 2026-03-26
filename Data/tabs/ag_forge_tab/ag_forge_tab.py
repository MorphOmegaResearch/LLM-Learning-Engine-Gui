"""
AgForgeTab — Agriculture Knowledge Suite as a top-level Trainer tab.

Embeds Ag_Forge's quick_clip sub-tab Frames directly into a ttk.Notebook
without using ClipboardAssistant's tk.Tk() / mainloop().

Lazy-init: create_ui() shows a placeholder; full init runs the first time
the tab is selected via <<NotebookTabChanged>>.

sys.path is patched at import time so all Ag_Forge internal imports resolve
(modules.quick_clip.providers, modules.brain, etc.)
"""
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path

# ── Path fix: Ag_Forge expects its own root on sys.path ──────────────────────
_AG_ROOT = Path(__file__).parent          # tabs/ag_forge_tab/
if str(_AG_ROOT) not in sys.path:
    sys.path.insert(0, str(_AG_ROOT))

from tabs.base_tab import BaseTab
import logger_util


class _AppRef:
    """
    Minimal shim passed as app_ref to Ag_Forge sub-tab classes that need it.
    Provides config, notebook, root, ollama_url, models and shared
    KnowledgeForgeApp references without requiring ClipboardAssistant.
    """
    def __init__(self):
        self.notebook = None   # set after inner notebook is created
        self.root = None       # set after inner notebook is created
        self.config = None
        self.knowledge_forge = None  #[Mark:UNIVERSAL_CATALOG_APPREF]
        try:
            from modules.quick_clip.config import ConfigManager
            self.config = ConfigManager()
        except Exception as e:
            logger_util.log_message(f"AG_FORGE: ConfigManager unavailable: {e}")
            self.config = _FallbackConfig()
        # Provider defaults — read from config, fallback to safe values
        self.ollama_url = self.config.get(
            'Endpoints', 'ollama_url', 'http://localhost:11434/api/generate'
        )
        self.models = [self.config.get('Ollama', 'model', 'llama2')]
        # Shared KnowledgeForgeApp — data-only, no Tk window
        try:
            from modules.meta_learn_agriculture import KnowledgeForgeApp
            _kf_base = _AG_ROOT / "knowledge_forge_data"
            self.knowledge_forge = KnowledgeForgeApp(base_path=_kf_base)
            logger_util.log_message(
                f"AG_FORGE: KnowledgeForgeApp loaded — {len(self.knowledge_forge.entities)} entities"
            )
        except Exception as e:
            logger_util.log_message(f"AG_FORGE: KnowledgeForgeApp unavailable: {e}")


class _FallbackConfig:
    """Fallback config that returns empty strings for all keys."""
    def get(self, section, key, fallback=''):
        return fallback


class AgForgeTab(BaseTab):
    """
    Top-level Ag_Forge tab. Lazy-inits on first notebook selection.
    Inner notebook mirrors Ag_Forge's quick_clip tab layout.
    """

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)
        self._ag_initialized = False

    # ── BaseTab interface ─────────────────────────────────────────────────────

    def create_ui(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Placeholder shown until first selection
        self._placeholder = ttk.Frame(self.parent)
        self._placeholder.grid(row=0, column=0, sticky='nsew')
        self._placeholder.columnconfigure(0, weight=1)
        self._placeholder.rowconfigure(0, weight=1)

        ttk.Label(
            self._placeholder,
            text="🌾  Ag Knowledge Suite",
            font=("Arial", 14, "bold")
        ).grid(row=0, column=0, pady=(80, 6))

        ttk.Label(
            self._placeholder,
            text="Select this tab to initialise the Agriculture Knowledge Suite.",
            font=("Arial", 10)
        ).grid(row=1, column=0)

        ttk.Label(
            self._placeholder,
            text="(Planner · Chat · Tools · State · Collections)",
            font=("Arial", 9),
            foreground='grey'
        ).grid(row=2, column=0, pady=(2, 0))

        # Bind lazy-init to notebook tab change
        notebook = self.parent.master
        if hasattr(notebook, 'bind'):
            notebook.bind('<<NotebookTabChanged>>', self._on_tab_selected, add='+')

        logger_util.log_ux_event(
            "ag_forge_tab", "TAB_PRIMED", "placeholder",
            outcome="primed",
            detail="AgForgeTab placeholder ready — awaiting first selection",
            wherein="AgForgeTab::create_ui"
        )

        # Probe sub-tab imports now and surface any issues as warnings.
        # Nothing is instantiated — this is a dry import check only.
        self._probe_imports()

    # ── Import probe ──────────────────────────────────────────────────────────

    def _probe_imports(self):
        """
        Dry-run import check for each Ag_Forge sub-tab module.
        Logs a {warn} line per failure so issues surface in the live log
        before the user ever clicks the tab.
        """
        probes = [
            ("modules.quick_clip.tabs.planner_tab", "PlannerSuite",  "Planner"),
            ("modules.quick_clip.tabs.chat_tab",    "ChatTab",        "Chat/IDE"),
            ("modules.quick_clip.tabs.tools_tab",   "ToolsTab",       "Tools"),
            ("modules.quick_clip.tabs.state_manager_tab", "StateManagerTab", "State"),
            ("modules.quick_clip.tabs.collections_tab", "CollectionsTab", "Collections"),
            ("modules.quick_clip.config",           "ConfigManager",  "Config"),
            ("modules.quick_clip.providers",        "get_provider",   "Providers"),
            # Dark module activation probes  #[Mark:UNIVERSAL_CATALOG_PROBES]
            ("modules.meta_learn_agriculture", "KnowledgeForgeApp", "KnowledgeForge"),
            ("modules.ag_importer",            "stream_tsv_file",   "Ag Importer"),
            ("modules.ag_onboarding",          "OnboardingReviewWorkflow", "Onboarding"),
            ("modules.brain",                  "CLIWorkflow",        "Brain"),
        ]
        issues = []
        for module_path, symbol, label in probes:
            try:
                mod = __import__(module_path, fromlist=[symbol])
                if not hasattr(mod, symbol):
                    raise ImportError(f"{symbol} not found in {module_path}")
            except Exception as e:
                issues.append((label, str(e)))
                logger_util.log_message(
                    f"AG_FORGE_PROBE [{label}] {'{warn}'} import failed: {e}"
                )

        if not issues:
            logger_util.log_message(
                "AG_FORGE_PROBE: all sub-tab imports resolved — tab ready for selection"
            )
        else:
            names = ", ".join(l for l, _ in issues)
            logger_util.log_message(
                f"AG_FORGE_PROBE {'{warn}'}: {len(issues)} sub-tab(s) may fail on init: {names}"
            )

    # ── Lazy init ─────────────────────────────────────────────────────────────

    def _on_tab_selected(self, event=None):
        if self._ag_initialized:
            return
        try:
            notebook = self.parent.master
            selected = notebook.nametowidget(notebook.select())
            if selected is self.parent:
                self._init_ag_forge()
        except Exception:
            pass

    def _init_ag_forge(self):
        self._ag_initialized = True

        # Remove placeholder
        if hasattr(self, '_placeholder') and self._placeholder.winfo_exists():
            self._placeholder.destroy()

        try:
            self._build_inner_tabs()
            logger_util.log_ux_event(
                "ag_forge_tab", "TAB_INIT", "inner_notebook",
                outcome="success",
                detail="AgForgeTab inner notebook built successfully",
                wherein="AgForgeTab::_init_ag_forge"
            )
        except Exception as e:
            ttk.Label(
                self.parent,
                text=f"Ag_Forge failed to initialise:\n{e}",
                foreground='red',
                justify='left'
            ).grid(row=0, column=0, padx=20, pady=40, sticky='nw')
            logger_util.log_message(f"AG_FORGE_TAB: init error: {e}")

    def _build_inner_tabs(self):
        """
        Create inner ttk.Notebook and embed each Ag_Forge Frame sub-tab.
        Import order: lightweight imports first so a failure in one doesn't
        block the others.
        """
        app_ref = _AppRef()

        inner_nb = ttk.Notebook(self.parent)
        inner_nb.grid(row=0, column=0, sticky='nsew')
        app_ref.notebook = inner_nb  # let sub-tabs navigate between each other
        app_ref.root = self.root    # needed for .after() thread callbacks

        def _load(label, fn):
            """Run fn(), log success or {warn} on failure, return True/False."""
            try:
                fn()
                logger_util.log_message(f"AG_FORGE_INIT [{label}]: loaded OK")
                return True
            except Exception as e:
                logger_util.log_message(
                    f"AG_FORGE_INIT [{label}] {'{warn}'}: {e}"
                )
                self._stub_tab(inner_nb, label, str(e))
                return False

        # ── Planner ──────────────────────────────────────────────────────────
        def _planner():
            from modules.quick_clip.tabs.planner_tab import PlannerSuite
            plans_base = str(Path(__file__).parent.parent.parent / "plans")
            plan_frame = ttk.Frame(inner_nb)
            inner_nb.add(plan_frame, text='📝 Planner')
            PlannerSuite(plan_frame, app_ref=app_ref, base_path=plans_base).pack(fill='both', expand=True)
        _load('📝 Planner', _planner)

        # ── Chat / IDE ───────────────────────────────────────────────────────
        def _chat():
            from modules.quick_clip.tabs.chat_tab import ChatTab
            chat_frame = ttk.Frame(inner_nb)
            inner_nb.add(chat_frame, text='💬 Chat / IDE')
            ChatTab(chat_frame, app_ref=app_ref).pack(fill='both', expand=True)
        _load('💬 Chat/IDE', _chat)

        # ── Tools ─────────────────────────────────────────────────────────────
        def _tools():
            from modules.quick_clip.tabs.tools_tab import ToolsTab
            tools_frame = ttk.Frame(inner_nb)
            inner_nb.add(tools_frame, text='🛠️ Tools')
            ToolsTab(tools_frame).pack(fill='both', expand=True)
        _load('🛠️ Tools', _tools)

        # ── State Manager ─────────────────────────────────────────────────────
        def _state():
            from modules.quick_clip.tabs.state_manager_tab import StateManagerTab
            state_frame = ttk.Frame(inner_nb)
            inner_nb.add(state_frame, text='🗄️ State')
            StateManagerTab(state_frame, app_ref=app_ref).pack(fill='both', expand=True)
        _load('🗄️ State', _state)

        # ── Collections ──────────────────────────────────────────────────────
        #[Mark:UNIVERSAL_CATALOG_COLLECTIONS_TAB]
        def _collections():
            from modules.quick_clip.tabs.collections_tab import CollectionsTab
            coll_frame = ttk.Frame(inner_nb)
            inner_nb.add(coll_frame, text='📚 Collections')
            CollectionsTab(coll_frame, app_ref=app_ref).pack(fill='both', expand=True)
        _load('📚 Collections', _collections)

        # Bind right-click context menu to AgForge inner notebook tab headers
        self.bind_sub_notebook(inner_nb, label='AgForge')

    @staticmethod
    def _stub_tab(notebook, label, error_msg):
        """Insert a placeholder frame when a sub-tab fails to load."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=label)
        ttk.Label(
            frame,
            text=f"{label} unavailable:\n{error_msg}",
            foreground='red',
            justify='left'
        ).pack(padx=20, pady=20, anchor='nw')
