"""
3D Interactive Brain Visualization
Real 3D neural network with mouse interaction
"""

import tkinter as tk
from tkinter import ttk
import time
import json
import os

# ── Logger integration ──────────────────────────────────────────────────────
def _bviz_log(msg: str, level: str = 'INFO') -> None:
    """Push to logger_util if available, otherwise print."""
    try:
        import sys, os as _os
        _here = _os.path.dirname(_os.path.abspath(__file__))
        _data = _os.path.dirname(_os.path.dirname(_here))
        if _data not in sys.path:
            sys.path.insert(0, _data)
        from logger_util import log_message
        log_message(f"BRAIN_VIZ [{level}]: {msg}")
    except Exception:
        print(f"BRAIN_VIZ [{level}]: {msg}")

# ── Dependency audit at import time ─────────────────────────────────────────
_DEPS_OK = True

try:
    import numpy as np
    _bviz_log(f"numpy OK  version={np.__version__}")
except ImportError as _e:
    _bviz_log(f"numpy MISSING — {_e}", 'ERROR')
    _DEPS_OK = False
    np = None

try:
    import matplotlib
    import matplotlib.pyplot as plt
    _bviz_log(f"matplotlib OK  version={matplotlib.__version__}  backend={matplotlib.get_backend()}")
except ImportError as _e:
    _bviz_log(f"matplotlib MISSING — {_e}", 'ERROR')
    _DEPS_OK = False
    matplotlib = None
    plt = None

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _bviz_log("FigureCanvasTkAgg OK")
except ImportError as _e:
    _bviz_log(f"FigureCanvasTkAgg MISSING — {_e}  (check Pillow/PIL.ImageTk)", 'ERROR')
    _DEPS_OK = False
    FigureCanvasTkAgg = None

try:
    from mpl_toolkits.mplot3d import Axes3D
    _bviz_log("mpl_toolkits.mplot3d OK")
except ImportError as _e:
    _bviz_log(f"mpl_toolkits.mplot3d MISSING — {_e}", 'ERROR')
    _DEPS_OK = False
    Axes3D = None

try:
    from matplotlib.patches import FancyBboxPatch
    import matplotlib.patches as mpatches
except ImportError as _e:
    _bviz_log(f"matplotlib.patches MISSING — {_e}", 'ERROR')
    FancyBboxPatch = None
    mpatches = None

try:
    from PIL import ImageTk as _pil_itk
    _bviz_log("PIL.ImageTk OK")
except ImportError as _e:
    _bviz_log(f"PIL.ImageTk MISSING — {_e}  (FigureCanvasTkAgg may fail silently)", 'WARN')

if _DEPS_OK:
    _bviz_log("All core dependencies satisfied — Brain3DVisualization ready")
else:
    _bviz_log("One or more dependencies missing — Brain3DVisualization will show a fallback", 'WARN')


class Brain3DVisualization(tk.Frame):
    """Interactive 3D brain neural network visualization"""

    def __init__(self, parent, style=None):
        _t0 = time.time()
        _bviz_log("Brain3DVisualization.__init__ starting")
        if not _DEPS_OK:
            _bviz_log("Skipping init — dependencies missing", 'WARN')
            super().__init__(parent, bg='#0a0a0a')
            self.style = style
            tk.Label(
                self, text="⚠ Brain Map unavailable\nMissing: numpy / matplotlib / mpl_toolkits",
                bg='#0a0a0a', fg='#ff6b6b', font=('Arial', 12), justify='center'
            ).pack(expand=True)
            return
        super().__init__(parent, bg='#0a0a0a')
        self.style = style
        self._render_count = 0   # for periodic render timing logs
        self._last_render_warn_ts = 0.0

        # 3D state
        self.nodes = []
        self.edges = []
        self.regions = {}
        self.selected_node = None
        self.model_kernel = None

        # Mouse interaction state
        self.mouse_pressed = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.zoom_level = 1.0
        self._last_interaction_ts = 0.0
        self._rot_vx = 0.0  # smoothed dx
        self._rot_vy = 0.0  # smoothed dy
        self._hover_timer = None
        self._pending_hover_node = None

        # Control settings
        self.scroll_enabled = tk.BooleanVar(value=True)
        self.rotation_enabled = tk.BooleanVar(value=True)
        self.invert_scroll = tk.BooleanVar(value=False)
        self.mode_3d_enabled = tk.BooleanVar(value=True)
        self.rotation_speed = tk.DoubleVar(value=0.5)  # 0.1 to 2.0
        self.scroll_speed = tk.DoubleVar(value=0.12)   # zoom step (0.05–0.4)
        self.drag_smoothing = tk.DoubleVar(value=0.0)  # 0.0 disables smoothing
        self.hover_region = None  # currently hovered region key for highlighting
        self.node_alpha = tk.DoubleVar(value=0.95)
        self.edge_alpha = tk.DoubleVar(value=0.35)
        self.edge_width = tk.DoubleVar(value=0.6)
        self.surface_enabled = tk.BooleanVar(value=True)
        self.surface_alpha = tk.DoubleVar(value=0.08)
        self.surface_detail = tk.IntVar(value=24)  # wireframe density (u resolution)
        self.backdrop_enabled = tk.BooleanVar(value=False)  # 3-square panes
        self.grid_enabled = tk.BooleanVar(value=False)  # Grid overlay separate from panes
        self.white_bg_enabled = tk.BooleanVar(value=True)
        self.hull_enabled = tk.BooleanVar(value=True)  # draw anatomical hull instead of per-region surfaces
        self.hull_static_brightness = tk.DoubleVar(value=0.08)  # Base hull opacity
        self.hull_hover_brightness = tk.DoubleVar(value=0.25)  # Hover highlight intensity
        # Node size global scale (uniformly scales all nodes)
        self.node_size_scale = tk.DoubleVar(value=1.0)  # 0.5 - 2.0
        # Layout state (controls collapse + left pane width)
        self.controls_collapsed = tk.BooleanVar(value=False)
        self.left_pane_width = tk.IntVar(value=250)
        # Axes/marks visibility
        self.axes_marks_enabled = tk.BooleanVar(value=False)  # Start with marks OFF for cleaner view

        # Automation and screensaver
        self.auto_rotate_enabled = tk.BooleanVar(value=False)
        self.auto_rotate_deg_per_sec = tk.DoubleVar(value=10.0)  # degrees/sec
        self.auto_cycle_enabled = tk.BooleanVar(value=False)
        self.auto_cycle_seconds = tk.IntVar(value=8)  # per region
        self.screensaver_enabled = tk.BooleanVar(value=True)
        self.screensaver_idle_seconds = tk.IntVar(value=120)
        self._auto_rotate_after = None
        self._auto_cycle_after = None
        self._screensaver_after = None
        self._screensaver_active = False
        self._auto_rotate_last_ts = None
        self._view_animating = False
        self._saver_after = None
        # Rendering view preservation
        self._reset_limits_next = True  # first render uses defaults, then preserve thereafter

        # Fullscreen controls
        self.fullscreen_enabled = tk.BooleanVar(value=False)
        self.screensaver_fullscreen = tk.BooleanVar(value=False)
        self._prev_geometry = None
        self._fs_was_for_screensaver = False

        # Active model highlighting
        self.active_type = None
        self.active_class_color = '#90EE90'
        self._active_regions = set()
        self._active_edges = set()

        # Optional callbacks (can be set by parent)
        self.open_file_callback = None
        self.open_tab_callback = None

        # Initialize brain structure FIRST (before UI needs it)
        self._initialize_brain_regions()
        self._generate_brain_network()

        # Load user preferences if available
        self._load_prefs()
        # Load plan overrides for component details (best-effort)
        self._plan_overrides = self._load_plan_component_overrides()

        # Create UI (now regions exist for tree population)
        self._create_ui()
        self._create_control_panel()
        # Apply background preference immediately
        self._apply_background()

        # Bind fullscreen shortcuts (Esc exits)
        self._bind_fullscreen_shortcuts()

        # Render brain
        self._render_brain()

        _elapsed = time.time() - _t0
        _bviz_log(
            f"Brain3DVisualization init complete  "
            f"nodes={len(self.nodes)}  regions={len(self.regions)}  "
            f"elapsed={_elapsed:.3f}s"
        )

    def _create_ui(self):
        """Create the integrated 2D+3D visualization UI"""
        _t0 = time.time()
        _bviz_log("_create_ui starting")

        # Configure grid layout: 2D tree (col0), resizer (col1), 3D view (col2)
        self.columnconfigure(0, weight=0, minsize=int(self.left_pane_width.get()))
        self.columnconfigure(1, weight=0, minsize=6)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)

        # Create 2D file tree panel
        try:
            self._create_2d_tree_panel()
            _bviz_log("2D component tree panel created OK")
        except Exception as _e:
            _bviz_log(f"2D component tree panel FAILED — {_e}", 'ERROR')
            import traceback as _tb
            _bviz_log(_tb.format_exc(), 'ERROR')

        # Create matplotlib figure (background applied later by _apply_background)
        try:
            plt.style.use('default')
        except Exception:
            pass
        try:
            self.fig = plt.Figure(figsize=(10, 8), facecolor='#ffffff' if self.white_bg_enabled.get() else '#0a0a0a')
            self.ax = self.fig.add_subplot(111, projection='3d', facecolor=self.fig.get_facecolor())
            _bviz_log(f"matplotlib Figure + Axes3D created  facecolor={'white' if self.white_bg_enabled.get() else 'dark'}")
        except Exception as _e:
            _bviz_log(f"Figure/Axes3D creation FAILED — {_e}", 'ERROR')
            import traceback as _tb
            _bviz_log(_tb.format_exc(), 'ERROR')
            raise

        # Style the axes (grid will be controlled by toggle)
        self.ax.set_xlabel('X', color='#666666', fontsize=8)
        self.ax.set_ylabel('Y', color='#666666', fontsize=8)
        self.ax.set_zlabel('Z', color='#666666', fontsize=8)
        self.ax.tick_params(colors='#333333', labelsize=6)

        # Set viewing angle
        self.ax.view_init(elev=20, azim=45)

        # Expand axes to occupy more space and set aspect
        try:
            self.fig.subplots_adjust(left=0.05, right=0.98, bottom=0.06, top=0.98)
            self.ax.set_box_aspect([1.8, 1.4, 1.2])
        except Exception as _e:
            _bviz_log(f"subplots_adjust/set_box_aspect warn — {_e}", 'WARN')

        # Embed in tkinter (3D view goes in column 2)
        try:
            self.canvas = FigureCanvasTkAgg(self.fig, master=self)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.grid(row=1, column=2, sticky=tk.NSEW)
            _bviz_log("FigureCanvasTkAgg embedded in tkinter grid OK")
        except Exception as _e:
            _bviz_log(f"FigureCanvasTkAgg embed FAILED — {_e}", 'ERROR')
            import traceback as _tb
            _bviz_log(_tb.format_exc(), 'ERROR')
            raise

        # Vertical resizer between tree and viz
        self.left_resizer = tk.Frame(self, width=6, bg='#2a2a2a', cursor='sb_h_double_arrow')
        self.left_resizer.grid(row=1, column=1, sticky=tk.NS)
        self.left_resizer.bind('<ButtonPress-1>', self._on_left_resizer_press)
        self.left_resizer.bind('<B1-Motion>', self._on_left_resizer_drag)
        self.left_resizer.bind('<ButtonRelease-1>', self._on_left_resizer_release)

        # Connect mouse events — each wrapped so errors surface to logger
        try:
            self.canvas.mpl_connect('button_press_event', self._on_mouse_press)
            self.canvas.mpl_connect('button_release_event', self._on_mouse_release)
            self.canvas.mpl_connect('motion_notify_event', self._on_mouse_motion)
            self.canvas.mpl_connect('scroll_event', self._on_scroll)
            self.canvas.mpl_connect('pick_event', self._on_pick)
            _bviz_log("mpl_connect: 5 events registered (press, release, motion, scroll, pick)")
        except Exception as _e:
            _bviz_log(f"mpl_connect registration FAILED — {_e}", 'ERROR')

        # Apply initial states for all toggles
        try:
            self._update_backdrop()
            self._update_grid()
            self._apply_axes_marks()
        except Exception as _e:
            _bviz_log(f"Initial toggle state application FAILED — {_e}", 'WARN')

        _bviz_log(f"_create_ui complete  elapsed={time.time() - _t0:.3f}s")

    def _create_2d_tree_panel(self):
        """Create 2D file tree panel on the left side"""
        import tkinter.ttk as ttk

        # Create frame for 2D tree
        tree_frame = tk.Frame(self, bg='#1a1a1a', borderwidth=1, relief=tk.SOLID)
        tree_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=(5, 2), pady=5)

        # Header
        header = tk.Label(tree_frame, text="🧠 Brain Components", bg='#2a2a2a', fg='#4a90e2',
                         font=('Arial', 10, 'bold'), pady=5)
        header.pack(fill=tk.X)

        # Create treeview with scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.component_tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set,
                                          selectmode='browse', height=20)
        self.component_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.component_tree.yview)

        # Configure columns
        self.component_tree['columns'] = ('type',)
        self.component_tree.column('#0', width=180, minwidth=150)
        self.component_tree.column('type', width=70, minwidth=50)
        self.component_tree.heading('#0', text='Component', anchor=tk.W)
        self.component_tree.heading('type', text='Type', anchor=tk.W)

        # Bind events
        self.component_tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.component_tree.bind('<Motion>', self._on_tree_hover)

        # Populate tree with brain regions and components
        self._populate_component_tree()

    def _get_component_file_mapping(self):
        """Map component names to actual .py file locations"""
        import os

        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        return {
            # Frontal Lobe - Planning & Orchestration
            'Planner': os.path.join(base_path, 'planner.py'),
            'Orchestrator': os.path.join(base_path, 'orchestrator.py'),
            'Task Manager': os.path.join(base_path, 'task_manager.py'),

            # Parietal Lobe - Stats & Processing
            'Stats System': os.path.join(base_path, 'stats_tracker.py'),
            'Evolution Tracker': os.path.join(base_path, 'evolution.py'),
            'XP Manager': os.path.join(base_path, 'xp_system.py'),

            # Temporal Lobe - Memory & RAG
            'RAG Network': os.path.join(base_path, 'rag_network.py'),
            'Training History': os.path.join(base_path, 'training_history.py'),
            'Chat History': os.path.join(base_path, 'tabs', 'chat_tab', 'chat_tab.py'),

            # Occipital Lobe - Visualization
            'Brain Map': os.path.join(base_path, 'tabs', 'models_tab', 'brain_viz_3d.py'),
            'Stats Dashboard': os.path.join(base_path, 'tabs', 'models_tab', 'models_tab.py'),
            'RAG Visualizer': os.path.join(base_path, 'tabs', 'rag_tab', 'rag_tab.py'),

            # Motor Cortex - Hardware & Execution
            'Training Scripts': os.path.join(base_path, 'trainer.py'),
            'Evaluation Pipeline': os.path.join(base_path, 'evaluator.py'),
            'Tool Registry': os.path.join(base_path, 'tools_registry.py'),

            # Sensory Cortex - Input Processing
            'User Input': os.path.join(base_path, 'tabs', 'chat_tab', 'chat_tab.py'),
            'Data Processing': os.path.join(base_path, 'data_processor.py'),
            'Prompt Handler': os.path.join(base_path, 'prompt_handler.py'),

            # Cerebellum - Type Coordination
            'Type Catalog': os.path.join(base_path, 'tabs', 'models_tab', 'types_panel.py'),
            'Class System': os.path.join(base_path, 'class_system.py'),
            'Skill Tree': os.path.join(base_path, 'skill_tree.py'),

            # Corpus Callosum - Communication
            'Event Bus': os.path.join(base_path, 'event_bus.py'),
            'State Management': os.path.join(base_path, 'state_manager.py'),
            'Config System': os.path.join(base_path, 'config.py'),
        }

    def _get_component_database(self):
        """Curated component details (official module path, description, dependencies).
        Uses the file mapping above for canonical file_path values.
        """
        file_map = self._get_component_file_mapping()
        # Prefer JSON source of truth if present
        json_db = self._load_component_details_json()
        def ent(name, desc, deps=None):
            return {
                'name': name,
                'description': desc,
                'file_path': file_map.get(name),
                'dependencies': deps or []
            }
        db = {
            # Frontal
            'Planner': ent('Planner', 'Plans tasks and orchestrates multi-step actions.'),
            'Orchestrator': ent('Orchestrator', 'Routes intents, coordinates subsystems, and manages execution flow.'),
            'Task Manager': ent('Task Manager', 'Queues, schedules, and tracks task lifecycles.'),
            # Parietal
            'Stats System': ent('Stats System', 'Aggregates metrics and computes analytics over time.'),
            'Evolution Tracker': ent('Evolution Tracker', 'Tracks capability growth and regression across versions.'),
            'XP Manager': ent('XP Manager', 'Awards XP and handles progression thresholds.'),
            # Temporal
            'RAG Network': ent('RAG Network', 'Retrieval-augmented memory access and indexing.'),
            'Training History': ent('Training History', 'Chronological record of training runs and results.'),
            'Chat History': ent('Chat History', 'Conversation logs and memory recall utilities.'),
            # Occipital
            'Brain Map': ent('Brain Map', 'Interactive 3D visualization of the system brain.'),
            'Stats Dashboard': ent('Stats Dashboard', 'Visual KPIs and performance charts.'),
            'RAG Visualizer': ent('RAG Visualizer', 'Graph view of retrieval sources and links.'),
            # Motor
            'Training Scripts': ent('Training Scripts', 'Launchers and pipelines for model training.'),
            'Evaluation Pipeline': ent('Evaluation Pipeline', 'Automated evaluation harness and scoring.'),
            'Tool Registry': ent('Tool Registry', 'Registered tools and adapters for execution.'),
            # Sensory
            'User Input': ent('User Input', 'Interfaces for prompts, voice, and GUI interactions.'),
            'Data Processing': ent('Data Processing', 'Pre/post-processing and normalization of inputs.'),
            'Prompt Handler': ent('Prompt Handler', 'Prompt templates and instruction routing.'),
            # Cerebellum
            'Type Catalog': ent('Type Catalog', 'Definitions for model types, skills, and classes.'),
            'Class System': ent('Class System', 'Rules for promotions, badges, and grading.'),
            'Skill Tree': ent('Skill Tree', 'Skill taxonomy and progression links.'),
            # Corpus Callosum
            'Event Bus': ent('Event Bus', 'In-process pub/sub for system events.'),
            'State Management': ent('State Management', 'Centralized app state and cache.'),
            'Config System': ent('Config System', 'Configuration loader, persistence, and helpers.'),
        }
        # Default related components and quick actions
        defaults_related = {
            'Planner': ['Orchestrator', 'Task Manager', 'Event Bus'],
            'Orchestrator': ['Planner', 'Event Bus', 'State Management'],
            'Stats System': ['XP Manager', 'Class System'],
            'RAG Network': ['Chat History', 'Data Processing'],
            'Brain Map': ['Stats Dashboard', 'RAG Visualizer'],
            'Training Scripts': ['Evaluation Pipeline', 'Tool Registry'],
        }
        for k, rel in defaults_related.items():
            if k in db:
                db[k]['related_components'] = rel
        # Default Quick Actions per component (can be overridden by plan)
        for name, entry in db.items():
            qa = [
                {'label': 'Open .py', 'action': 'open_module'},
                {'label': 'Related Tab', 'action': 'open_tab'},
                {'label': 'RAG Network', 'action': 'open_rag'},
                {'label': 'Agents', 'action': 'open_agents'},
            ]
            entry['quick_actions'] = qa
        # Merge in JSON overrides first
        try:
            if json_db:
                for name, entry in json_db.items():
                    if name not in db:
                        db[name] = {}
                    # If JSON lacks file_path, patch from file_map
                    merged = dict(entry)
                    if not merged.get('file_path'):
                        merged['file_path'] = file_map.get(name)
                    db[name].update(merged)
        except Exception:
            pass

        # Merge in plan overrides if present
        try:
            if getattr(self, '_plan_overrides', None):
                for name, override in self._plan_overrides.items():
                    if name in db:
                        db[name].update({k: v for k, v in override.items() if v})
        except Exception:
            pass
        return db

    def _get_component_details(self, comp_name):
        try:
            db = self._get_component_database()
            base = db.get(comp_name) or {}
            # Merge detected modules
            region = {}
            modules = self._discover_related_files(comp_name, region)
            if modules:
                base = dict(base)
                base['detected_modules'] = modules
            return base
        except Exception:
            return {}

    # --- Module/test/docs status helpers ---
    def _repo_base(self):
        try:
            return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        except Exception:
            return os.getcwd()

    def _compute_component_status(self, name, region):
        """Return status dict: {module_path, module_exists, tests_found, docs_found}.
        Uses JSON/plan mapping for primary module, then searches for tests and docs.
        """
        status = {
            'module_path': None,
            'module_exists': False,
            'tests_found': False,
            'docs_found': False,
            'test_paths': [],
            'doc_paths': [],
        }
        try:
            detail = self._get_component_details(name) or {}
            rel_path = detail.get('file_path') or self._component_to_file_path(name, region) or ''
            base = self._repo_base()
            abs_path = rel_path
            if rel_path and not os.path.isabs(rel_path):
                abs_path = os.path.abspath(os.path.join(base, rel_path))
            status['module_path'] = rel_path or None
            status['module_exists'] = bool(abs_path and os.path.exists(abs_path))

            # Derive module basename for test/doc search
            mod_base = None
            try:
                if abs_path:
                    mod_base = os.path.splitext(os.path.basename(abs_path))[0]
            except Exception:
                mod_base = None

            # Tests: look in same dir and any 'tests' folders for files containing mod_base and 'test'
            try:
                tests_found = False
                searched = 0
                if abs_path:
                    mod_dir = os.path.dirname(abs_path)
                    for f in os.listdir(mod_dir or '.'):
                        if f.endswith('.py') and 'test' in f.lower():
                            if (not mod_base) or (mod_base.lower() in f.lower()):
                                tests_found = True
                                status['test_paths'].append(os.path.relpath(os.path.join(mod_dir, f), base))
                # Fallback: scan repo tests dirs lightly
                if not tests_found and mod_base:
                    for root, dirs, files in os.walk(base):
                        # Skip heavy folders
                        if any(skip in root for skip in ['.git', '__pycache__', 'exports', 'user_prefs', 'venv']):
                            continue
                        if 'test' in os.path.basename(root).lower() or 'tests' in os.path.basename(root).lower():
                            for f in files:
                                if f.endswith('.py') and 'test' in f.lower() and mod_base.lower() in f.lower():
                                    tests_found = True
                                    status['test_paths'].append(os.path.relpath(os.path.join(root, f), base))
                                    if len(status['test_paths']) >= 5:
                                        break
                            searched += 1
                            if searched > 120:  # cap walk
                                break
                            if tests_found:
                                break
                status['tests_found'] = tests_found
            except Exception:
                status['tests_found'] = False

            # Docs: README in module dir or docs folder with component token
            try:
                docs_found = False
                token = (name or '').lower().replace(' ', '_')
                if abs_path:
                    mod_dir = os.path.dirname(abs_path)
                    for fname in ['README.md', 'README.txt']:
                        p = os.path.join(mod_dir, fname)
                        if os.path.exists(p):
                            docs_found = True
                            status['doc_paths'].append(os.path.relpath(p, base))
                if not docs_found and token:
                    docs_dir = os.path.join(base, 'docs')
                    if os.path.isdir(docs_dir):
                        for root, _dirs, files in os.walk(docs_dir):
                            for f in files:
                                if f.lower().endswith(('.md', '.txt')) and token in f.lower():
                                    docs_found = True
                                    status['doc_paths'].append(os.path.relpath(os.path.join(root, f), base))
                                    if len(status['doc_paths']) >= 5:
                                        break
                            if docs_found:
                                break
                status['docs_found'] = docs_found
            except Exception:
                status['docs_found'] = False
        except Exception:
            pass
        return status

    def _load_component_details_json(self):
        try:
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            path = os.path.join(base, 'component_details.json')
            if not os.path.exists(path):
                return {}
            with open(path, 'r', encoding='utf-8') as f:
                import json as _json
                data = _json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _load_plan_component_overrides(self):
        """Parse the plan document for component summaries, related components, and optional quick actions.
        Returns a dict keyed by component name.
        """
        overrides = {}
        try:
            plan_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     '..', '..', 'Learning engine context', 'Plans',
                                     'Unified_Execution_Plan_S10_Hybrids_XP_Grades_Agents.md')
            plan_path = os.path.abspath(plan_path)
            if not os.path.exists(plan_path):
                return overrides
            with open(plan_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Attempt to extract per-component blocks using simple patterns
            names = [
                'Planner','Orchestrator','Task Manager','Stats System','Evolution Tracker','XP Manager',
                'RAG Network','Training History','Chat History','Brain Map','Stats Dashboard','RAG Visualizer',
                'Training Scripts','Evaluation Pipeline','Tool Registry','User Input','Data Processing','Prompt Handler',
                'Type Catalog','Class System','Skill Tree','Event Bus','State Management','Config System'
            ]
            for name in names:
                desc = None
                related = None
                # Look for bold section like **1. Planner** then capture a short paragraph
                import re
                patt = re.compile(r"\*\*\s*\d+\.\s*" + re.escape(name) + r"\s*\*\*", re.IGNORECASE)
                m = patt.search(content)
                start = m.end() if m else -1
                if start > 0:
                    snippet = content[start:start+600]
                    # First non-empty lines up to blank
                    lines = [ln.strip() for ln in snippet.splitlines()[:12]]
                    chunk = []
                    for ln in lines:
                        if not ln:
                            break
                        # stop at next bold header
                        if ln.startswith('**'):
                            break
                        chunk.append(ln)
                    if chunk:
                        desc = ' '.join(chunk)[:800]
                # Look for a dict-like block with related_components
                rc = re.search(r"'name'\s*:\s*'" + re.escape(name) + r"'.{0,300}?'related_components'\s*:\s*\[([^\]]+)\]", content, re.DOTALL)
                if rc:
                    try:
                        rel_raw = rc.group(1)
                        related = [s.strip().strip("'\"") for s in rel_raw.split(',') if s.strip()]
                    except Exception:
                        related = None
                if desc or related:
                    overrides[name] = {}
                    if desc:
                        overrides[name]['description'] = desc
                    if related:
                        overrides[name]['related_components'] = related
        except Exception:
            return overrides
        return overrides

    def _execute_action(self, action, node=None, region=None, detail=None):
        try:
            a = (action or '').lower()
            if a == 'open_module':
                nm = node.get('name') if node else (detail.get('name') if detail else None)
                rg = self.regions.get(node.get('region')) if node else region
                self._open_source_file(self._component_to_file_path(nm, rg))
            elif a == 'open_tab':
                self._open_related_tab(region or (self.regions.get(node.get('region')) if node else {}))
            elif a == 'open_rag':
                self._open_related_tab({'tab': 'RAG'})
            elif a == 'open_agents':
                self._open_related_tab({'tab': 'Agents'})
            elif a == 'open_models':
                self._open_related_tab({'tab': 'Models'})
            elif a == 'open_types':
                self._open_related_tab({'tab': 'Types'})
            elif a == 'open_training':
                self._open_related_tab({'tab': 'Training'})
            elif a == 'open_settings':
                self._open_related_tab({'tab': 'Settings'})
            elif a == 'open_skills':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Skills'})
            elif a == 'open_stats':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Stats'})
            elif a == 'open_adapters':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Adapters'})
            elif a == 'open_levels':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Levels'})
            elif a == 'open_evaluation':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Evaluation'})
            elif a == 'open_baselines':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Baselines'})
            elif a == 'open_compare':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Compare'})
            elif a == 'open_visualization':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Visualization'})
            elif a == 'open_collections':
                self._open_related_tab({'tab': 'Models', 'subtab': 'Collections'})
            elif a == 'open_chat_quick':
                self._open_related_tab({'tab': 'Chat', 'subtab': 'QuickActions', 'session': 'chat'})
            elif a == 'open_project_quick':
                self._open_related_tab({'tab': 'Projects', 'subtab': 'QuickActions', 'session': 'project'})
        except Exception:
            pass

    def _populate_component_tree(self):
        """Populate the 2D tree with brain regions and components, linking to actual files"""
        # Clear existing items
        for item in self.component_tree.get_children():
            self.component_tree.delete(item)

        # Get file mappings
        file_mapping = self._get_component_file_mapping()

        # Track region->tree item mapping for selection sync
        self._region_tree_ids = {}
        # Track (region, component)->tree item mapping
        self._component_item_ids = {}

        # Add regions and their components
        for region_key, region_data in self.regions.items():
            # Add region as parent
            region_id = self.component_tree.insert('', 'end',
                                                   text=f"  {region_data['name']}",
                                                   values=('region',),
                                                   tags=('region', region_key))
            self._region_tree_ids[region_key] = region_id

            # Add components as children
            for component in region_data['components']:
                # Skip hardware emoji components for file mapping
                comp_name = component
                if any(emoji in component for emoji in ['🎮', '💻', '🧠', '⚡']):
                    # Hardware component - no file mapping
                    comp_id = self.component_tree.insert(region_id, 'end',
                                                         text=f"    {component}",
                                                         values=('hardware',),
                                                         tags=('hardware',))
                else:
                    # Software component - has file mapping
                    file_path = file_mapping.get(comp_name, '')
                    comp_id = self.component_tree.insert(region_id, 'end',
                                                         text=f"    {component}",
                                                         values=('component',),
                                                         tags=('component', region_key))

                    # Store file path in item data
                    if file_path:
                        # Use item iid to store path in a dict
                        if not hasattr(self, '_component_file_paths'):
                            self._component_file_paths = {}
                        self._component_file_paths[comp_id] = file_path
                # Map component to tree id for cycling
                try:
                    self._component_item_ids[(region_key, component)] = comp_id
                except Exception:
                    pass

        # Configure tag colors
        self.component_tree.tag_configure('region', foreground='#4a90e2')
        self.component_tree.tag_configure('component', foreground='#888888')
        self.component_tree.tag_configure('hardware', foreground='#6dd5ed')

    def _select_tree_region(self, region_key):
        try:
            if not hasattr(self, '_region_tree_ids'):
                return
            item = self._region_tree_ids.get(region_key)
            if not item:
                return
            self.component_tree.selection_set(item)
            self.component_tree.see(item)
        except Exception:
            pass

    def _create_control_panel(self):
        """Create control panel with position indicators and toggles"""
        control_frame = tk.Frame(self, bg='#1a1a1a')
        control_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, padx=5, pady=5)

        # Two-row layout to avoid cramping
        row1 = tk.Frame(control_frame, bg='#1a1a1a')
        row1.pack(side=tk.TOP, fill=tk.X)
        row2 = tk.Frame(control_frame, bg='#1a1a1a')
        row2.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

        # Position indicators (row1)
        pos_frame = tk.Frame(row1, bg='#1a1a1a')
        pos_frame.pack(side=tk.LEFT, padx=10)

        tk.Label(pos_frame, text="Camera:", fg='#888888', bg='#1a1a1a',
                font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=(0, 5))

        self.azim_label = tk.Label(pos_frame, text="Az: 45°", fg='#4a90e2', bg='#1a1a1a',
                                   font=('Arial', 9))
        self.azim_label.pack(side=tk.LEFT, padx=3)

        self.elev_label = tk.Label(pos_frame, text="El: 20°", fg='#4a90e2', bg='#1a1a1a',
                                   font=('Arial', 9))
        self.elev_label.pack(side=tk.LEFT, padx=3)

        self.zoom_label = tk.Label(pos_frame, text="Zoom: 100%", fg='#4a90e2', bg='#1a1a1a',
                                   font=('Arial', 9))
        self.zoom_label.pack(side=tk.LEFT, padx=3)

        # Separator
        tk.Label(row1, text="|", fg='#333333', bg='#1a1a1a').pack(side=tk.LEFT, padx=5)

        # Control toggles
        toggle_frame = tk.Frame(row1, bg='#1a1a1a')
        toggle_frame.pack(side=tk.LEFT, padx=5)

        tk.Checkbutton(toggle_frame, text="Rot", variable=self.rotation_enabled,
                      bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a',
                      activebackground='#1a1a1a', activeforeground='#4a90e2',
                      font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        tk.Checkbutton(toggle_frame, text="Zoom", variable=self.scroll_enabled,
                      bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a',
                      activebackground='#1a1a1a', activeforeground='#4a90e2',
                      font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        tk.Checkbutton(toggle_frame, text="Invert", variable=self.invert_scroll,
                      bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a',
                      activebackground='#1a1a1a', activeforeground='#4a90e2',
                      font=('Arial', 9)).pack(side=tk.LEFT, padx=3)

        # Separator
        tk.Label(row1, text="|", fg='#333333', bg='#1a1a1a').pack(side=tk.LEFT, padx=5)

        # 3D Mode toggle
        tk.Checkbutton(row1, text="3D", variable=self.mode_3d_enabled,
                       command=self._on_3d_mode_toggle,
                       bg='#1a1a1a', fg='#4a90e2', selectcolor='#2a2a2a',
                       activebackground='#1a1a1a', activeforeground='#4a90e2',
                       font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        # Separator
        tk.Label(row1, text="|", fg='#333333', bg='#1a1a1a').pack(side=tk.LEFT, padx=5)

        # Fullscreen toggle
        tk.Checkbutton(row1, text="Fullscreen", variable=self.fullscreen_enabled,
                       command=lambda: self._apply_fullscreen(self.fullscreen_enabled.get()),
                       bg='#1a1a1a', fg='#4a90e2', selectcolor='#2a2a2a',
                       activebackground='#1a1a1a', activeforeground='#4a90e2',
                       font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        # Display Controls toggle (expand/collapse)
        def _toggle_controls():
            collapsed = bool(self.controls_collapsed.get())
            try:
                if collapsed:
                    # Expand
                    row2.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
                    if hasattr(self, 'row3') and self.row3:
                        self.row3.pack(side=tk.TOP, fill=tk.X, pady=(4, 2))
                    self.controls_collapsed.set(False)
                else:
                    # Collapse
                    row2.pack_forget()
                    if hasattr(self, 'row3') and self.row3:
                        self.row3.pack_forget()
                    self.controls_collapsed.set(True)
                # Update button label to reflect new state
                if hasattr(self, 'display_btn') and self.display_btn:
                    self.display_btn.config(text=('Show Controls' if self.controls_collapsed.get() else 'Hide Controls'))
            except Exception:
                pass
            self._save_prefs()

        # Display Controls button with dynamic label
        self.display_btn = ttk.Button(row1, text='Display Controls', command=_toggle_controls, style='Select.TButton')
        self.display_btn.pack(side=tk.RIGHT)

        # Vertical section columns
        sections = tk.Frame(row2, bg='#1a1a1a')
        sections.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

        def col(parent):
            f = tk.Frame(parent, bg='#1a1a1a')
            f.pack(side=tk.LEFT, padx=10, anchor='n')
            return f

        speed_col = col(sections)
        node_col = col(sections)
        edge_col = col(sections)
        surf_col = col(sections)
        hull_col = col(sections)
        auto_col = col(sections)

        # Speed Controls (vertical)
        tk.Label(speed_col, text="Speed Controls", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')
        srow = tk.Frame(speed_col, bg='#1a1a1a'); srow.pack(anchor='w')
        tk.Label(srow, text="Drag", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        self.speed_slider = tk.Scale(srow, from_=0.1, to=2.0, resolution=0.1, orient=tk.HORIZONTAL,
                                     variable=self.rotation_speed, bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a',
                                     activebackground='#4a90e2', highlightthickness=0, length=120, width=12, font=('Arial', 8))
        self.speed_slider.pack(side=tk.LEFT, padx=(6,0))

        srow2 = tk.Frame(speed_col, bg='#1a1a1a'); srow2.pack(anchor='w', pady=(2,0))
        tk.Label(srow2, text="Scroll", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(srow2, from_=0.05, to=0.4, resolution=0.01, orient=tk.HORIZONTAL, variable=self.scroll_speed,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8)).pack(side=tk.LEFT, padx=(6,0))

        srow3 = tk.Frame(speed_col, bg='#1a1a1a'); srow3.pack(anchor='w', pady=(2,0))
        tk.Label(srow3, text="Smooth", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(srow3, from_=0.0, to=0.6, resolution=0.05, orient=tk.HORIZONTAL, variable=self.drag_smoothing,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8)).pack(side=tk.LEFT, padx=(6,0))

        # Node Controls (vertical)
        tk.Label(node_col, text="Node Controls", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')
        nrow1 = tk.Frame(node_col, bg='#1a1a1a'); nrow1.pack(anchor='w')
        tk.Label(nrow1, text="Nodes", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(nrow1, from_=0.3, to=1.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.node_alpha,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        nrow2 = tk.Frame(node_col, bg='#1a1a1a'); nrow2.pack(anchor='w', pady=(2,0))
        tk.Label(nrow2, text="Size", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(nrow2, from_=0.5, to=2.0, resolution=0.05, orient=tk.HORIZONTAL, variable=self.node_size_scale,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        # Edge Controls (vertical)
        tk.Label(edge_col, text="Edge Controls", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')
        erow1 = tk.Frame(edge_col, bg='#1a1a1a'); erow1.pack(anchor='w')
        tk.Label(erow1, text="Edges", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(erow1, from_=0.05, to=0.5, resolution=0.01, orient=tk.HORIZONTAL, variable=self.edge_alpha,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        erow2 = tk.Frame(edge_col, bg='#1a1a1a'); erow2.pack(anchor='w', pady=(2,0))
        tk.Label(erow2, text="Width", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(erow2, from_=0.3, to=1.5, resolution=0.05, orient=tk.HORIZONTAL, variable=self.edge_width,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        # Surface Controls (vertical)
        tk.Label(surf_col, text="Surface", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')
        sfc1 = tk.Frame(surf_col, bg='#1a1a1a'); sfc1.pack(anchor='w')
        tk.Checkbutton(sfc1, text="Brain Surface", variable=self.surface_enabled, command=self._render_brain,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)

        sfc2 = tk.Frame(surf_col, bg='#1a1a1a'); sfc2.pack(anchor='w', pady=(2,0))
        tk.Label(sfc2, text="Alpha", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(sfc2, from_=0.0, to=0.2, resolution=0.01, orient=tk.HORIZONTAL, variable=self.surface_alpha,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        sfc3 = tk.Frame(surf_col, bg='#1a1a1a'); sfc3.pack(anchor='w', pady=(2,0))
        tk.Label(sfc3, text="Detail", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(sfc3, from_=8, to=40, resolution=1, orient=tk.HORIZONTAL, variable=self.surface_detail,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        sfc4 = tk.Frame(surf_col, bg='#1a1a1a'); sfc4.pack(anchor='w', pady=(2,0))
        tk.Checkbutton(sfc4, text="Panes", variable=self.backdrop_enabled, command=self._update_backdrop,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Checkbutton(sfc4, text="BG", variable=self.white_bg_enabled, command=self._apply_background,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Checkbutton(sfc4, text="Hull", variable=self.hull_enabled, command=self._render_brain,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Checkbutton(sfc4, text="Marks", variable=self.axes_marks_enabled, command=self._apply_axes_marks,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Checkbutton(sfc4, text="Grid", variable=self.grid_enabled, command=self._update_grid,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))

        # Hull/Surface extra (hover brightness/static) already defined elsewhere in UI

        # Auto Controls (vertical)
        tk.Label(auto_col, text="Automation", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')
        arow1 = tk.Frame(auto_col, bg='#1a1a1a'); arow1.pack(anchor='w')
        tk.Checkbutton(arow1, text="Auto-Rotate", variable=self.auto_rotate_enabled,
                       command=self._update_auto_timers,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(arow1, text="deg/s", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Scale(arow1, from_=2.0, to=40.0, resolution=1.0, orient=tk.HORIZONTAL, variable=self.auto_rotate_deg_per_sec,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._update_auto_timers()).pack(side=tk.LEFT, padx=(6,0))

        arow2 = tk.Frame(auto_col, bg='#1a1a1a'); arow2.pack(anchor='w', pady=(2,0))
        tk.Checkbutton(arow2, text="Auto-Cycle", variable=self.auto_cycle_enabled,
                       command=self._update_auto_timers,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(arow2, text="sec", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Scale(arow2, from_=3, to=30, resolution=1, orient=tk.HORIZONTAL, variable=self.auto_cycle_seconds,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._update_auto_timers()).pack(side=tk.LEFT, padx=(6,0))

        arow3 = tk.Frame(auto_col, bg='#1a1a1a'); arow3.pack(anchor='w', pady=(2,0))
        tk.Checkbutton(arow3, text="Screensaver", variable=self.screensaver_enabled,
                       command=self._update_auto_timers,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(arow3, text="idle s", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT, padx=(6,0))
        tk.Scale(arow3, from_=30, to=600, resolution=10, orient=tk.HORIZONTAL, variable=self.screensaver_idle_seconds,
                 bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2', highlightthickness=0,
                 length=120, width=12, font=('Arial', 8), command=lambda _=None: self._update_auto_timers()).pack(side=tk.LEFT, padx=(6,0))

        arow4 = tk.Frame(auto_col, bg='#1a1a1a'); arow4.pack(anchor='w', pady=(2,0))
        tk.Checkbutton(arow4, text="Saver Fullscreen", variable=self.screensaver_fullscreen,
                       command=self._update_auto_timers,
                       bg='#1a1a1a', fg='#888888', selectcolor='#2a2a2a', activebackground='#1a1a1a',
                       activeforeground='#4a90e2', font=('Arial', 9)).pack(side=tk.LEFT)

        # Kick timers once controls exist
        self._update_auto_timers()

        # Hull Controls in separate column
        tk.Label(hull_col, text="Hull Controls", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(anchor='w')

        # Hull static brightness
        hc1 = tk.Frame(hull_col, bg='#1a1a1a'); hc1.pack(anchor='w')
        tk.Label(hc1, text="Static", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(hc1, from_=0.0, to=0.3, resolution=0.01, orient=tk.HORIZONTAL,
                variable=self.hull_static_brightness,
                bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2',
                highlightthickness=0, length=120, width=12, font=('Arial', 8),
                command=lambda _=None: self._render_brain()).pack(side=tk.LEFT, padx=(6,0))

        # Hull hover brightness
        hc2 = tk.Frame(hull_col, bg='#1a1a1a'); hc2.pack(anchor='w', pady=(2,0))
        tk.Label(hc2, text="Hover", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Scale(hc2, from_=0.1, to=0.5, resolution=0.01, orient=tk.HORIZONTAL,
                variable=self.hull_hover_brightness,
                bg='#2a2a2a', fg='#888888', troughcolor='#1a1a1a', activebackground='#4a90e2',
                highlightthickness=0, length=120, width=12, font=('Arial', 8)).pack(side=tk.LEFT, padx=(6,0))

        # Reset button in hull column
        hc3 = tk.Frame(hull_col, bg='#1a1a1a'); hc3.pack(anchor='w', pady=(2,0))
        tk.Button(hc3, text="↻ Reset", command=self.reset_view, bg='#2a2a2a', fg='#888888', relief=tk.FLAT,
                  activebackground='#3a3a3a', activeforeground='#4a90e2', font=('Arial', 9), padx=8, pady=2).pack(side=tk.LEFT)

        # Update position labels periodically
        self._update_position_labels()

        # Persist preference changes with a slight debounce
        self._attach_pref_traces()

        # Row 3: Relative controls beneath groups
        row3 = tk.Frame(control_frame, bg='#1a1a1a')
        row3.pack(side=tk.TOP, fill=tk.X, pady=(4, 2))
        self.row2 = row2
        self.row3 = row3

        # Apply collapsed/expanded state if saved
        self._apply_layout_from_prefs()

    def _detect_hardware_components(self):
        """Detect available hardware and return as component list"""
        components = []

        try:
            import subprocess
            import re

            # Detect GPU
            try:
                result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'VGA' in line or '3D controller' in line:
                            if 'AMD' in line or 'Radeon' in line:
                                # Extract GPU model
                                match = re.search(r'(RX \d+|Radeon [^\]]+)', line)
                                if match:
                                    components.append(f"🎮 GPU: AMD {match.group(1)}")
                                else:
                                    components.append("🎮 GPU: AMD Radeon")
                            elif 'NVIDIA' in line:
                                match = re.search(r'(GTX|RTX) \d+', line)
                                if match:
                                    components.append(f"🎮 GPU: NVIDIA {match.group(0)}")
                                else:
                                    components.append("🎮 GPU: NVIDIA")
            except Exception:
                pass

            # Detect CPU
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line:
                            cpu_name = line.split(':')[1].strip()
                            # Simplify CPU name
                            cpu_name = re.sub(r'\(R\)|\(TM\)|\s+CPU\s+@.*', '', cpu_name).strip()
                            components.append(f"💻 CPU: {cpu_name}")
                            break
            except Exception:
                pass

            # Detect RAM
            try:
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if 'MemTotal' in line:
                            mem_kb = int(line.split()[1])
                            mem_gb = round(mem_kb / (1024 * 1024))
                            components.append(f"🧠 RAM: {mem_gb}GB")
                            break
            except Exception:
                pass

            # Detect ROCm/CUDA
            try:
                result = subprocess.run(['rocminfo'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and 'gfx' in result.stdout:
                    components.append("⚡ ROCm Backend")
            except Exception:
                pass

        except Exception as e:
            print(f"Hardware detection error: {e}")

        return components if components else ["Hardware Detection Unavailable"]

    def _initialize_brain_regions(self):
        """Define 8 brain regions in 3D space with anatomical brain shape"""
        # Positioned to form brain-like silhouette when viewed from distance
        # Coordinate system: X (left-right), Y (front-back), Z (up-down)
        self.regions = {
            'frontal': {
                'name': 'Frontal Lobe',
                'subtitle': 'Planning & Orchestration',
                'center': np.array([0.0, 0.5, 0.15]),  # Front-top center
                'radii': np.array([0.35, 0.28, 0.25]),  # Wide, shallow front lobe
                'color': '#5ac8fa',  # Light neon blue
                'default_color': '#5ac8fa',
                'components': ['Planner', 'Orchestrator', 'Task Manager']
            },
            'parietal': {
                'name': 'Parietal Lobe',
                'subtitle': 'Stats & Processing',
                'center': np.array([0.0, 0.05, 0.35]),  # Top-back center
                'radii': np.array([0.32, 0.25, 0.22]),  # Top crown area
                'color': '#64d2ff',  # Lighter blue
                'default_color': '#64d2ff',
                'components': ['Stats System', 'Evolution Tracker', 'XP Manager']
            },
            'temporal': {
                'name': 'Temporal Lobe',
                'subtitle': 'Memory & RAG',
                'center': np.array([-0.38, 0.0, -0.05]),  # Left side, mid-level
                'radii': np.array([0.22, 0.28, 0.25]),  # Side protrusion
                'color': '#48d1cc',  # Turquoise blue
                'default_color': '#48d1cc',
                'components': ['RAG Network', 'Training History', 'Chat History']
            },
            'occipital': {
                'name': 'Occipital Lobe',
                'subtitle': 'Visualization',
                'center': np.array([0.0, -0.45, 0.08]),  # Back center, slight up
                'radii': np.array([0.28, 0.22, 0.24]),  # Back bulge
                'color': '#7dd3c0',  # Mint blue
                'default_color': '#7dd3c0',
                'components': ['Brain Map', 'Stats Dashboard', 'RAG Visualizer']
            },
            'motor': {
                'name': 'Motor Cortex',
                'subtitle': 'Hardware & Execution',
                'center': np.array([-0.18, 0.25, 0.25]),  # Left front-top
                'radii': np.array([0.18, 0.2, 0.18]),  # Strip along top
                'color': '#4fc3f7',  # Sky blue
                'default_color': '#4fc3f7',
                'components': self._detect_hardware_components() + ['Training Scripts', 'Evaluation Pipeline', 'Tool Registry']
            },
            'sensory': {
                'name': 'Sensory Cortex',
                'subtitle': 'Input Processing',
                'center': np.array([0.18, 0.25, 0.25]),  # Right front-top
                'radii': np.array([0.18, 0.2, 0.18]),  # Strip along top
                'color': '#6dd5ed',  # Pale blue
                'default_color': '#6dd5ed',
                'components': ['User Input', 'Data Processing', 'Prompt Handler']
            },
            'cerebellum': {
                'name': 'Cerebellum',
                'subtitle': 'Type Coordination',
                'center': np.array([0.0, -0.5, -0.25]),  # Back-bottom center
                'radii': np.array([0.25, 0.2, 0.2]),  # Small rounded back-bottom
                'color': '#4dd0e1',  # Cyan blue
                'default_color': '#4dd0e1',
                'components': ['Type Catalog', 'Class System', 'Skill Tree']
            },
            'corpus': {
                'name': 'Corpus Callosum',
                'subtitle': 'Communication',
                'center': np.array([0.0, 0.0, 0.05]),  # Center core
                'radii': np.array([0.12, 0.35, 0.08]),  # Thin horizontal bridge
                'color': '#26c6da',  # Deep neon blue
                'default_color': '#26c6da',
                'components': ['Event Bus', 'State Management', 'Config System']
            }
        }

    def _generate_brain_network(self):
        """Generate nodes and connections for brain network"""
        self.nodes = []
        self.edges = []

        # Generate nodes for each region
        node_id = 0
        for region_key, region_data in self.regions.items():
            center = region_data['center']
            radii = region_data['radii']
            color = region_data['color']
            components = region_data['components']

            # Generate 8-12 nodes per region
            n_nodes = len(components) + np.random.randint(5, 9)

            for i in range(n_nodes):
                # Random point within ellipsoid
                theta = np.random.uniform(0, 2 * np.pi)
                phi = np.random.uniform(0, np.pi)
                r = np.random.uniform(0.3, 0.9)  # Don't fill entire ellipsoid

                # Ellipsoid parametric equations
                x = center[0] + r * radii[0] * np.sin(phi) * np.cos(theta)
                y = center[1] + r * radii[1] * np.sin(phi) * np.sin(theta)
                z = center[2] + r * radii[2] * np.cos(phi)

                # Component name (use real component if available)
                if i < len(components):
                    comp_name = components[i]
                else:
                    comp_name = f"{region_data['name']} Node {i - len(components) + 1}"

                self.nodes.append({
                    'id': node_id,
                    'pos': np.array([x, y, z]),
                    'region': region_key,
                    'color': color,
                    'name': comp_name,
                    'size': np.random.uniform(50, 150)
                })
                node_id += 1

        # Generate connections between nodes
        # Connect nodes within regions
        for region_key in self.regions.keys():
            region_nodes = [n for n in self.nodes if n['region'] == region_key]

            # Connect random pairs within region
            for i in range(len(region_nodes)):
                # Connect to 2-4 random neighbors
                n_connections = np.random.randint(2, 5)
                for _ in range(n_connections):
                    j = np.random.randint(0, len(region_nodes))
                    if i != j:
                        self.edges.append((region_nodes[i]['id'], region_nodes[j]['id']))

        # Connect regions via corpus callosum
        corpus_nodes = [n for n in self.nodes if n['region'] == 'corpus']
        for region_key in self.regions.keys():
            if region_key != 'corpus':
                region_nodes = [n for n in self.nodes if n['region'] == region_key]
                if region_nodes and corpus_nodes:
                    # Connect 1-2 nodes from each region to corpus
                    for _ in range(min(2, len(region_nodes))):
                        src = np.random.choice(region_nodes)
                        dst = np.random.choice(corpus_nodes)
                        self.edges.append((src['id'], dst['id']))

    def _render_brain(self):
        """Render the 3D brain network"""
        _rt0 = time.time()
        self._render_count = getattr(self, '_render_count', 0) + 1
        # Capture current view/limits to preserve during redraw
        try:
            cur_xlim = self.ax.get_xlim()
            cur_ylim = self.ax.get_ylim()
            cur_zlim = self.ax.get_zlim()
            cur_elev = self.ax.elev
            cur_azim = self.ax.azim
        except Exception:
            cur_xlim = cur_ylim = cur_zlim = None
            cur_elev = cur_azim = None

        self.ax.clear()

        # Set axis limits: use defaults only when explicitly requested
        if self._reset_limits_next or cur_xlim is None:
            self.ax.set_xlim(-1, 1)
            self.ax.set_ylim(-0.8, 0.8)
            self.ax.set_zlim(-0.6, 0.6)

        # Draw edges first (so they're behind nodes). Highlight active connectors.
        base_edge_color = '#7c8a98' if self.white_bg_enabled.get() else '#3c596e'
        base_edge_lw = float(self.edge_width.get())
        for src_id, dst_id in self.edges:
            src_node = self.nodes[src_id]
            dst_node = self.nodes[dst_id]

            src_pos = src_node['pos']
            dst_pos = dst_node['pos']

            # Active?
            active = (src_id, dst_id) in self._active_edges or (dst_id, src_id) in self._active_edges
            color = self.active_class_color if active else base_edge_color
            alpha = 0.9 if active else float(self.edge_alpha.get())
            lw = max(base_edge_lw, 1.2) if active else base_edge_lw

            self.ax.plot([src_pos[0], dst_pos[0]],
                         [src_pos[1], dst_pos[1]],
                         [src_pos[2], dst_pos[2]],
                         color=color, alpha=alpha, linewidth=lw)

        # Draw translucent brain surface outline
        if self.surface_enabled.get():
            self._draw_brain_surface()

        # Draw nodes grouped by region for better picking
        for region_key, region_data in self.regions.items():
            region_nodes = [n for n in self.nodes if n['region'] == region_key]

            if region_nodes:
                xs = [n['pos'][0] for n in region_nodes]
                ys = [n['pos'][1] for n in region_nodes]
                zs = [n['pos'][2] for n in region_nodes]

                # Highlight hovered region by scaling sizes and edge color
                if self.hover_region == region_key:
                    sizes = [n['size'] * 1.3 for n in region_nodes]
                    edge = '#bbbb33' if self.white_bg_enabled.get() else '#ffffaa'
                    alpha = 1.0
                else:
                    sizes = [n['size'] for n in region_nodes]
                    edge = '#1a1a1a' if self.white_bg_enabled.get() else 'white'
                    alpha = 0.95

                # Uniformly scale sizes with clamp to reasonable limits
                try:
                    scale = float(self.node_size_scale.get())
                    S_MIN, S_MAX = 24.0, 260.0
                    sizes = [max(S_MIN, min(S_MAX, s * scale)) for s in sizes]
                except Exception:
                    pass

                # Plot with picking enabled - brighter alpha and thicker edges
                self.ax.scatter(xs, ys, zs,
                              c=region_data['color'],
                              s=sizes,
                              alpha=float(alpha if self.node_alpha.get() is None else self.node_alpha.get() if self.hover_region != region_key else min(1.0, self.node_alpha.get()+0.05)),
                              edgecolors=edge,
                              linewidths=0.8,
                              picker=5)  # 5 point tolerance for picking

        # Draw model kernel if loaded
        if self.model_kernel:
            self.ax.scatter([0], [0], [0.1],
                          c='#ffff00',
                          s=400,
                          alpha=0.9,
                          edgecolors='#ffffff',
                          linewidths=2,
                          marker='*')

            # Add kernel label
            self.ax.text(0, 0, 0.25, self.model_kernel['name'],
                       color='#ffff00', fontsize=9, ha='center',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='#0a0a0a',
                                edgecolor='#ffff00', alpha=0.7))

        # Style axes and apply panes/grid/frame/marks consistently
        try:
            self._update_backdrop()
            self._apply_axes_marks()
        except Exception:
            pass

        # Restore previous view if not resetting
        try:
            if not self._reset_limits_next and cur_xlim is not None:
                self.ax.set_xlim(cur_xlim)
                self.ax.set_ylim(cur_ylim)
                self.ax.set_zlim(cur_zlim)
                if (cur_elev is not None) and (cur_azim is not None):
                    self.ax.view_init(elev=cur_elev, azim=cur_azim)
        except Exception:
            pass

        # Apply marks again after any limit/view restoration to ensure ticks match
        try:
            self._apply_axes_marks()
        except Exception:
            pass

        # Update canvas
        try:
            self.canvas.draw()
        except Exception as _e:
            _bviz_log(f"canvas.draw() FAILED on render #{self._render_count} — {_e}", 'ERROR')
            import traceback as _tb
            _bviz_log(_tb.format_exc(), 'ERROR')

        # After the first defaulted render, preserve view on subsequent renders
        self._reset_limits_next = False

        # Timing: log first render, and any render that's slow (>80ms)
        _rt = time.time() - _rt0
        if self._render_count == 1:
            _bviz_log(f"First render complete  nodes={len(self.nodes)}  edges={len(self.edges)}  elapsed={_rt:.3f}s")
        elif _rt > 0.08:
            _now = time.time()
            if _now - getattr(self, '_last_render_warn_ts', 0) > 5.0:
                _bviz_log(f"Slow render #{self._render_count}  elapsed={_rt:.3f}s  (>80ms)", 'WARN')
                self._last_render_warn_ts = _now

    def _draw_brain_surface(self):
        """Draw translucent surfaces for a clearer brain silhouette.
        If hull is enabled, draw hemispheres + temporal bulges + cerebellum.
        Otherwise, draw per-region surfaces.
        """
        if self.hull_enabled.get():
            self._draw_brain_hull()
            return

        # Fallback: per-region ellipsoids
        for region_key in ['frontal', 'parietal', 'temporal', 'occipital', 'cerebellum']:
            if region_key not in self.regions:
                continue
            region = self.regions[region_key]
            self._draw_ellipsoid(region['center'], region['radii'], region_key=region_key)

    def _draw_ellipsoid(self, center, radii, color='#4a90e2', region_key=None):
        u_res = max(8, int(self.surface_detail.get()))
        v_res = max(6, int(round(self.surface_detail.get() * 0.66)))
        u = np.linspace(0, 2 * np.pi, u_res)
        v = np.linspace(0, np.pi, v_res)
        x = center[0] + radii[0] * np.outer(np.cos(u), np.sin(v))
        y = center[1] + radii[1] * np.outer(np.sin(u), np.sin(v))
        z = center[2] + radii[2] * np.outer(np.ones(np.size(u)), np.cos(v))
        lw = 0.6 if self.white_bg_enabled.get() else 0.3

        # Use hull static brightness, or fallback to surface_alpha
        if self.hull_enabled.get():
            alpha = float(self.hull_static_brightness.get())
        else:
            alpha = float(self.surface_alpha.get())

        # Increase brightness if this region is hovered
        if region_key and self.hover_region == region_key:
            alpha = float(self.hull_hover_brightness.get())

        if self.white_bg_enabled.get():
            alpha = max(alpha, 0.12)

        self.ax.plot_wireframe(x, y, z, color=color, alpha=alpha,
                               linewidth=lw, rstride=2, cstride=2)

    def _draw_brain_hull(self):
        """Approximate anatomical silhouette with overlapping hemispheres and temporal bulges."""
        # Hemispheres (slightly asymmetric, broader front, tapered rear)
        left_center = np.array([-0.19, 0.06, 0.06])
        right_center = np.array([0.19, 0.04, 0.05])
        hemi_radii = np.array([0.58, 0.46, 0.42])
        self._draw_ellipsoid(left_center, hemi_radii, color='#6aa9ff')
        self._draw_ellipsoid(right_center, hemi_radii, color='#6aa9ff')

        # Temporal bulges (sides, slightly lower)
        lt_center = np.array([-0.44, 0.02, -0.06])
        rt_center = np.array([0.44, 0.03, -0.06])
        temp_radii = np.array([0.24, 0.30, 0.22])
        self._draw_ellipsoid(lt_center, temp_radii, color='#6aa9ff')
        self._draw_ellipsoid(rt_center, temp_radii, color='#6aa9ff')

        # Cerebellum (back-bottom)
        cere_center = np.array([0.0, -0.58, -0.30])
        cere_radii = np.array([0.30, 0.24, 0.18])
        self._draw_ellipsoid(cere_center, cere_radii, color='#6aa9ff')

        # Occipital bulge (rear upper)
        occ_center = np.array([0.0, -0.62, 0.08])
        occ_radii = np.array([0.30, 0.20, 0.20])
        self._draw_ellipsoid(occ_center, occ_radii, color='#6aa9ff')

        # Frontal bulge (front upper)
        front_center = np.array([0.0, 0.55, 0.18])
        front_radii = np.array([0.32, 0.18, 0.24])
        self._draw_ellipsoid(front_center, front_radii, color='#6aa9ff')

        # Longitudinal fissure (midline hint)
        y = np.linspace(-0.65, 0.65, 40)
        z = 0.06 + 0.04 * np.cos((y + 0.65) * np.pi)  # slight crown
        x = np.zeros_like(y)
        self.ax.plot(x, y, z, color='#6aa9ff', alpha=float(self.surface_alpha.get()) * 1.5, linewidth=0.5)

    def _update_backdrop(self):
        """Enable/disable 3D backdrop panes (3-square positional panes) without affecting grid."""
        enabled = bool(self.backdrop_enabled.get())
        # Removed spammy debug print - use log_message if needed for debugging
        # print(f"[Brain] Panes toggle: enabled={enabled}")
        try:
            # Control pane visibility AND edges (front 3 lines are pane edges)
            for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
                try:
                    # Set pane visibility
                    axis.pane.set_visible(enabled)

                    # Control pane appearance
                    if enabled:
                        # When enabled: show panes with colors and edges
                        axis.pane.set_facecolor('#ffffff')
                        axis.pane.set_edgecolor('#cccccc')
                        axis.pane.set_linewidth(1.0)
                        axis.pane.set_alpha(1.0)
                    else:
                        # When disabled: aggressively hide everything
                        axis.pane.set_edgecolor('none')  # Try 'none' instead of transparent
                        axis.pane.set_linewidth(0)
                        axis.pane.set_facecolor('none')
                        axis.pane.set_alpha(0)

                    # Also control the axis line drawn along the pane edge
                    try:
                        # Each axis has gridlines that might appear as edges
                        axis.line.set_visible(enabled)
                        if not enabled:
                            axis.line.set_linewidth(0)
                            axis.line.set_color((0,0,0,0))
                    except:
                        pass

                except Exception as e:
                    print(f"[Brain] pane error: {e}")

            # Frame lines (cube border) - control ALL axis lines
            try:
                # Ensure the overall axes frame respects the toggle
                try:
                    self.ax.set_frame_on(enabled)
                except Exception:
                    pass
                # Control the main axis frame lines (back edges) where available
                for attr in ('w_xaxis','w_yaxis','w_zaxis'):
                    try:
                        a = getattr(self.ax, attr)
                        a.line.set_visible(enabled)
                        if enabled:
                            a.line.set_color('#cccccc' if self.white_bg_enabled.get() else '#444444')
                            a.line.set_linewidth(1.0)
                        else:
                            a.line.set_linewidth(0)
                            a.line.set_color((0,0,0,0))
                    except Exception:
                        # Some backends omit w_*axis; ignore silently
                        pass

                # Also control the 2D projection spines
                for spine in self.ax.spines.values():
                    spine.set_visible(enabled)
                    if enabled:
                        spine.set_color('#cccccc' if self.white_bg_enabled.get() else '#444444')
                        spine.set_linewidth(1.0)

                # Suppress axisline visuals at the mplot3d _axinfo layer when disabled
                if not enabled:
                    for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
                        try:
                            axis._axinfo['axisline']['linewidth'] = 0.0
                            axis._axinfo['axisline']['color'] = (0, 0, 0, 0)
                        except Exception:
                            pass
            except Exception as e:
                print(f"[Brain] frame lines error: {e}")
        except Exception:
            # Legacy fallback
            for name in ['w_xaxis', 'w_yaxis', 'w_zaxis']:
                try:
                    pane = getattr(self.ax, name).pane
                    try:
                        pane.set_visible(enabled)
                    except Exception:
                        pass
                    if enabled:
                        try:
                            pane.set_facecolor('#ffffff')
                        except Exception:
                            pass
                except Exception:
                    pass
        self.canvas.draw()

    def _update_grid(self):
        """Enable/disable grid lines independently of panes."""
        enabled = bool(self.grid_enabled.get())
        print(f"[Brain] Grid toggle: enabled={enabled}")
        try:
            # For 3D axes, control ONLY the grid lines, NOT pane edges
            if enabled:
                # Turn grid on with visible colors
                gc = (0.6, 0.6, 0.6, 0.8) if self.white_bg_enabled.get() else (0.4, 0.4, 0.4, 0.6)
                # Set grid colors and linewidths via _axinfo
                for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
                    axis._axinfo['grid']['color'] = gc
                    axis._axinfo['grid']['linewidth'] = 0.8
                    axis._axinfo['grid']['linestyle'] = '-'
            else:
                # Fully hide grid by making it transparent and zero width
                for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
                    axis._axinfo['grid']['color'] = (0, 0, 0, 0)
                    axis._axinfo['grid']['linewidth'] = 0
        except Exception as e:
            print(f"[Brain] grid toggle error: {e}")
        self.canvas.draw()

    def _apply_axes_marks(self):
        """Show/hide axis labels and tick marks for mplot3d axes."""
        enabled = bool(self.axes_marks_enabled.get())
        try:
            # Axis labels
            self.ax.set_xlabel('X' if enabled else '', color='#666666' if enabled else (0,0,0,0), fontsize=8)
            self.ax.set_ylabel('Y' if enabled else '', color='#666666' if enabled else (0,0,0,0), fontsize=8)
            self.ax.set_zlabel('Z' if enabled else '', color='#666666' if enabled else (0,0,0,0), fontsize=8)

            # Tick locations/labels: mplot3d ignores some tick_params for visibility, so set ticks explicitly
            if enabled:
                try:
                    # Recreate simple symmetric ticks matching our limits
                    xlim = self.ax.get_xlim()
                    ylim = self.ax.get_ylim()
                    zlim = self.ax.get_zlim()
                    import numpy as _np
                    self.ax.set_xticks(_np.linspace(xlim[0], xlim[1], 5))
                    self.ax.set_yticks(_np.linspace(ylim[0], ylim[1], 5))
                    self.ax.set_zticks(_np.linspace(zlim[0], zlim[1], 5))
                    # Ensure tick label color contrasts background
                    self.ax.tick_params(colors='#333333' if self.white_bg_enabled.get() else '#bbbbbb', labelsize=6)
                except Exception:
                    pass
            else:
                self.ax.set_xticks([])
                self.ax.set_yticks([])
                self.ax.set_zticks([])
        except Exception as e:
            print(f"[Brain] marks toggle error: {e}")
        self.canvas.draw()

    def _apply_background(self):
        """Toggle overall figure/axes background between dark and white."""
        white = bool(self.white_bg_enabled.get())
        try:
            if white:
                self.fig.set_facecolor('#ffffff')
                self.ax.set_facecolor('#ffffff')
                self.ax.tick_params(colors='#333333')
                # Set brighter default connectors on white
                if float(self.edge_alpha.get()) < 0.3:
                    self.edge_alpha.set(0.35)
                if float(self.edge_width.get()) < 0.6:
                    self.edge_width.set(0.6)
            else:
                self.fig.set_facecolor('#0a0a0a')
                self.ax.set_facecolor('#0a0a0a')
                self.ax.tick_params(colors='#333333')
                if float(self.edge_alpha.get()) < 0.2:
                    self.edge_alpha.set(0.2)
                if float(self.edge_width.get()) > 0.6:
                    self.edge_width.set(0.4)
            # Reapply grid state after background change
            self._update_grid()
        except Exception:
            pass
        # Backdrop may need refresh with new background
        self._update_backdrop()
        self._render_brain()

    # --- Layout: left resizer handlers and apply from prefs ---
    def _on_left_resizer_press(self, event):
        self._left_start_x = event.x_root
        self._left_start_width = int(self.left_pane_width.get())

    def _on_left_resizer_drag(self, event):
        try:
            dx = event.x_root - self._left_start_x
            new_w = max(180, min(600, self._left_start_width + dx))
            self.left_pane_width.set(int(new_w))
            self.columnconfigure(0, minsize=int(new_w))
        except Exception:
            pass

    def _on_left_resizer_release(self, event):
        try:
            self._save_prefs()
        except Exception:
            pass

    def _apply_layout_from_prefs(self):
        try:
            self.columnconfigure(0, minsize=int(self.left_pane_width.get()))
            collapsed = bool(self.controls_collapsed.get())
            if hasattr(self, 'row2') and self.row2 is not None:
                if collapsed:
                    try:
                        self.row2.pack_forget()
                    except Exception:
                        pass
                else:
                    try:
                        self.row2.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))
                    except Exception:
                        pass
            if hasattr(self, 'row3') and self.row3 is not None:
                if collapsed:
                    try:
                        self.row3.pack_forget()
                    except Exception:
                        pass
                else:
                    try:
                        self.row3.pack(side=tk.TOP, fill=tk.X, pady=(4, 2))
                    except Exception:
                        pass
            # Update button label to reflect state
            try:
                if hasattr(self, 'display_btn') and self.display_btn:
                    self.display_btn.config(text=('Show Controls' if collapsed else 'Hide Controls'))
            except Exception:
                pass
        except Exception:
            pass
    # --- Preferences persistence ---
    def _prefs_file(self):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        folder = os.path.join(base, 'user_prefs')
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        return os.path.join(folder, 'brain_viz.json')

    def _load_prefs(self):
        try:
            path = self._prefs_file()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                # Assign if present
                self.rotation_enabled.set(bool(data.get('rotation_enabled', True)))
                self.scroll_enabled.set(bool(data.get('scroll_enabled', True)))
                self.invert_scroll.set(bool(data.get('invert_scroll', False)))
                self.mode_3d_enabled.set(bool(data.get('mode_3d_enabled', True)))
                self.rotation_speed.set(float(data.get('rotation_speed', 0.5)))
                self.node_alpha.set(float(data.get('node_alpha', 0.95)))
                self.edge_alpha.set(float(data.get('edge_alpha', 0.35)))
                self.edge_width.set(float(data.get('edge_width', 0.6)))
                self.surface_enabled.set(bool(data.get('surface_enabled', True)))
                self.surface_alpha.set(float(data.get('surface_alpha', 0.08)))
                self.surface_detail.set(int(data.get('surface_detail', 24)))
                self.backdrop_enabled.set(bool(data.get('backdrop_enabled', False)))
                self.grid_enabled.set(bool(data.get('grid_enabled', False)))
                self.white_bg_enabled.set(bool(data.get('white_bg_enabled', True)))
                self.hull_enabled.set(bool(data.get('hull_enabled', True)))
                self.hull_static_brightness.set(float(data.get('hull_static_brightness', 0.08)))
                self.hull_hover_brightness.set(float(data.get('hull_hover_brightness', 0.25)))
                self.node_size_scale.set(float(data.get('node_size_scale', 1.0)))
                self.scroll_speed.set(float(data.get('scroll_speed', 0.12)))
                self.drag_smoothing.set(float(data.get('drag_smoothing', 0.0)))
                self.controls_collapsed.set(bool(data.get('controls_collapsed', False)))
                self.left_pane_width.set(int(data.get('left_pane_width', 250)))
                self.axes_marks_enabled.set(bool(data.get('axes_marks_enabled', True)))
                # Automation
                self.auto_rotate_enabled.set(bool(data.get('auto_rotate_enabled', False)))
                self.auto_rotate_deg_per_sec.set(float(data.get('auto_rotate_deg_per_sec', 10.0)))
                self.auto_cycle_enabled.set(bool(data.get('auto_cycle_enabled', False)))
                self.auto_cycle_seconds.set(int(data.get('auto_cycle_seconds', 8)))
                self.screensaver_enabled.set(bool(data.get('screensaver_enabled', True)))
                self.screensaver_idle_seconds.set(int(data.get('screensaver_idle_seconds', 120)))
                # Fullscreen
                self.fullscreen_enabled.set(bool(data.get('fullscreen_enabled', False)))
                self.screensaver_fullscreen.set(bool(data.get('screensaver_fullscreen', False)))
        except Exception as e:
            print(f"[Brain] load prefs failed: {e}")

    def _attach_pref_traces(self):
        self._pref_save_after = None
        def schedule_save(*_):
            try:
                if self._pref_save_after:
                    self.after_cancel(self._pref_save_after)
            except Exception:
                pass
            self._pref_save_after = self.after(400, self._save_prefs)
        for var in [
            self.rotation_enabled, self.scroll_enabled, self.invert_scroll, self.mode_3d_enabled,
            self.rotation_speed, self.node_alpha, self.edge_alpha, self.edge_width,
            self.surface_enabled, self.surface_alpha, self.surface_detail,
            self.backdrop_enabled, self.grid_enabled, self.white_bg_enabled, self.hull_enabled,
            self.hull_static_brightness, self.hull_hover_brightness,
            self.node_size_scale, self.controls_collapsed, self.left_pane_width,
            self.scroll_speed, self.drag_smoothing,
            self.auto_rotate_enabled, self.auto_rotate_deg_per_sec,
            self.auto_cycle_enabled, self.auto_cycle_seconds,
            self.screensaver_enabled, self.screensaver_idle_seconds,
            self.fullscreen_enabled, self.screensaver_fullscreen
        ]:
            try:
                var.trace_add('write', lambda *_: schedule_save())
            except Exception:
                pass

        # Also trace axes marks toggle for persistence
        try:
            self.axes_marks_enabled.trace_add('write', lambda *_: schedule_save())
        except Exception:
            pass

        # NOTE: _save_prefs is defined as a class method below (not nested) so
        # it is available across the class and during scheduled saves.

    def _on_mouse_press(self, event):
        """Handle mouse button press"""
        if event.button == 1:  # Left click
            self.mouse_pressed = True
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self._set_user_active()

    def _save_prefs(self):
        try:
            data = {
                'rotation_enabled': bool(self.rotation_enabled.get()),
                'scroll_enabled': bool(self.scroll_enabled.get()),
                'invert_scroll': bool(self.invert_scroll.get()),
                'mode_3d_enabled': bool(self.mode_3d_enabled.get()),
                'rotation_speed': float(self.rotation_speed.get()),
                'node_alpha': float(self.node_alpha.get()),
                'edge_alpha': float(self.edge_alpha.get()),
                'edge_width': float(self.edge_width.get()),
                'surface_enabled': bool(self.surface_enabled.get()),
                'surface_alpha': float(self.surface_alpha.get()),
                'surface_detail': int(self.surface_detail.get()),
                'backdrop_enabled': bool(self.backdrop_enabled.get()),
                'grid_enabled': bool(self.grid_enabled.get()),
                'white_bg_enabled': bool(self.white_bg_enabled.get()),
                'hull_enabled': bool(self.hull_enabled.get()),
                'hull_static_brightness': float(self.hull_static_brightness.get()),
                'hull_hover_brightness': float(self.hull_hover_brightness.get()),
                'node_size_scale': float(self.node_size_scale.get()),
                'scroll_speed': float(self.scroll_speed.get()),
                'drag_smoothing': float(self.drag_smoothing.get()),
                'controls_collapsed': bool(self.controls_collapsed.get()),
                'left_pane_width': int(self.left_pane_width.get()),
                'axes_marks_enabled': bool(self.axes_marks_enabled.get()),
                # Automation
                'auto_rotate_enabled': bool(self.auto_rotate_enabled.get()),
                'auto_rotate_deg_per_sec': float(self.auto_rotate_deg_per_sec.get()),
                'auto_cycle_enabled': bool(self.auto_cycle_enabled.get()),
                'auto_cycle_seconds': int(self.auto_cycle_seconds.get()),
                'screensaver_enabled': bool(self.screensaver_enabled.get()),
                'screensaver_idle_seconds': int(self.screensaver_idle_seconds.get()),
                'fullscreen_enabled': bool(self.fullscreen_enabled.get()),
                'screensaver_fullscreen': bool(self.screensaver_fullscreen.get()),
            }
            with open(self._prefs_file(), 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Brain] save prefs failed: {e}")

    def _on_mouse_release(self, event):
        """Handle mouse button release"""
        if event.button == 1:
            self.mouse_pressed = False
            self._drag_draw_ts = 0.0  # reset throttle
            self.canvas.draw_idle()   # settle final position
            self._set_user_active()

    def _on_mouse_motion(self, event):
        """Handle mouse motion for rotation"""
        if self.mouse_pressed and event.xdata is not None:
            if not self.rotation_enabled.get() or not self.mode_3d_enabled.get():
                return
            # Calculate rotation delta
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            # Get current view angles
            elev = self.ax.elev
            azim = self.ax.azim

            # Apply speed multiplier (default 0.5, user adjustable 0.1-2.0)
            speed = self.rotation_speed.get()

            # Optional low-pass filter for smoother rotation
            alpha = float(self.drag_smoothing.get())
            if alpha <= 0.0:
                vx, vy = dx, dy
            else:
                self._rot_vx = (1 - alpha) * self._rot_vx + alpha * dx
                self._rot_vy = (1 - alpha) * self._rot_vy + alpha * dy
                vx, vy = self._rot_vx, self._rot_vy

            # Update angles (invert dy for intuitive rotation)
            new_azim = azim + vx * speed
            new_elev = elev - vy * speed

            # Clamp elevation to avoid gimbal lock
            new_elev = np.clip(new_elev, -89, 89)

            # Normalize azimuth to keep continuity
            new_azim = (new_azim + 360.0) % 360.0
            # Apply new view
            self.ax.view_init(elev=new_elev, azim=new_azim)

            # Throttle canvas redraws to ~30fps during drag to avoid queuing
            _now = time.time()
            if _now - getattr(self, '_drag_draw_ts', 0.0) >= 0.033:
                self.canvas.draw_idle()
                self._drag_draw_ts = _now

            # Update last position
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self._set_user_active()
        else:
            # Hover detection (when not dragging)
            try:
                self._detect_hover_node(event)
                # If no node under cursor, try region center proximity for hull hover
                if self._pending_hover_node is None:
                    self._detect_hover_region_from_cursor(event)
            except Exception:
                pass

    def _detect_hover_node(self, event):
        """Detect nearest node to cursor and show tooltip with a short summary."""
        # Do not show tooltip while interacting (drag/scroll)
        if (time.time() - self._last_interaction_ts) < 0.15:
            self._hide_tooltip()
            return
        if event.x is None or event.y is None:
            self._hide_tooltip()
            return
        # Project node 3D positions to 2D display coordinates
        try:
            from mpl_toolkits.mplot3d import proj3d
            min_dist = 18  # pixel threshold
            nearest = None
            for node in self.nodes:
                x3, y3, z3 = node['pos']
                x2, y2, _ = proj3d.proj_transform(x3, y3, z3, self.ax.get_proj())
                xpix, ypix = self.ax.transData.transform((x2, y2))
                d = ((event.x - xpix) ** 2 + (event.y - ypix) ** 2) ** 0.5
                if d < min_dist:
                    min_dist = d
                    nearest = node
            # Debounce with a short dwell to avoid spam
            if self._hover_timer:
                self.after_cancel(self._hover_timer)
                self._hover_timer = None
            if nearest is not None:
                self._pending_hover_node = (event, nearest)
                self._hover_timer = self.after(200, self._commit_hover_tooltip)
            else:
                self._hide_tooltip()
        except Exception:
            self._hide_tooltip()

    def _commit_hover_tooltip(self):
        self._hover_timer = None
        if self._pending_hover_node is None:
            return
        event, node = self._pending_hover_node
        self._pending_hover_node = None
        if (time.time() - self._last_interaction_ts) < 0.15:
            return
        self._show_tooltip(event, node)
        try:
            self._select_tree_region(node.get('region'))
        except Exception:
            pass

    def _show_tooltip(self, event, node):
        """Show or update a small tooltip near cursor for the hovered node."""
        try:
            text = node.get('name', 'Component')
            region = self.regions.get(node['region'], {})
            subtitle = region.get('subtitle', '')
            short = f"{text}\n{subtitle}"
            if not hasattr(self, '_tooltip') or not self._tooltip:
                tip = tk.Toplevel(self)
                tip.overrideredirect(True)
                tip.configure(bg='#000000')
                label = tk.Label(tip, text=short, bg='#111111', fg='#eeeeee',
                                 font=('Arial', 9), justify='left',
                                 relief=tk.SOLID, borderwidth=1)
                label.pack(ipadx=6, ipady=4)
                self._tooltip = tip
                self._tooltip_label = label
            else:
                self._tooltip_label.configure(text=short)
            # Position near cursor
            x = self.winfo_rootx() + int(event.x) + 12
            y = self.winfo_rooty() + int(event.y) + 12
            self._tooltip.geometry(f"+{x}+{y}")
            self._tooltip.deiconify()
        except Exception:
            self._hide_tooltip()

    def _hide_tooltip(self):
        if hasattr(self, '_tooltip') and self._tooltip:
            try:
                self._tooltip.withdraw()
            except Exception:
                pass

    def _on_scroll(self, event):
        """Handle mouse wheel zoom"""
        if not self.scroll_enabled.get() or not self.mode_3d_enabled.get():
            return

        # Zoom factor (invert if toggle is on)
        step = float(self.scroll_speed.get())
        up_scale = 1.0 + step
        down_scale = 1.0 / (1.0 + step)
        if self.invert_scroll.get():
            scale = down_scale if event.button == 'up' else up_scale
        else:
            scale = up_scale if event.button == 'up' else down_scale

        # Get current limits
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        zlim = self.ax.get_zlim()

        # Center of brain
        xcenter, ycenter, zcenter = 0, 0, 0

        # Scale around center
        new_xlim = [xcenter + (x - xcenter) * scale for x in xlim]
        new_ylim = [ycenter + (y - ycenter) * scale for y in ylim]
        new_zlim = [zcenter + (z - zcenter) * scale for z in zlim]

        # Apply new limits
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.ax.set_zlim(new_zlim)

        # Keep axis marks consistent with updated limits
        try:
            self._apply_axes_marks()
        except Exception:
            pass

        # Update zoom level for reference
        self.zoom_level *= scale

        # Redraw
        self.canvas.draw_idle()
        self._set_user_active()

    # --- Auto rotate / cycle / screensaver ---
    def _set_user_active(self):
        self._last_interaction_ts = time.time()
        # Exit screensaver mode when user interacts
        if self._screensaver_active:
            self._screensaver_active = False
            # Restore node/edge alphas by re-rendering
            self._render_brain()
            # Exit fullscreen if we entered it for screensaver
            if self._fs_was_for_screensaver:
                self._fs_was_for_screensaver = False
                if self.fullscreen_enabled.get():
                    # Turn off fullscreen that was set by saver
                    self.fullscreen_enabled.set(False)
                    self._apply_fullscreen(False)
            # Stop saver timer if running
            try:
                if self._saver_after:
                    self.after_cancel(self._saver_after)
                    self._saver_after = None
            except Exception:
                self._saver_after = None
        self._update_auto_timers()

    def _update_auto_timers(self, *_):
        # Cancel existing timers
        try:
            if self._auto_rotate_after:
                self.after_cancel(self._auto_rotate_after)
        except Exception:
            pass
        try:
            if self._auto_cycle_after:
                self.after_cancel(self._auto_cycle_after)
        except Exception:
            pass
        try:
            if self._screensaver_after:
                self.after_cancel(self._screensaver_after)
        except Exception:
            pass

        # Enforce exclusivity between auto-rotate and auto-cycle
        try:
            if bool(self.auto_rotate_enabled.get()) and bool(self.auto_cycle_enabled.get()):
                # Prefer the one just toggled; if uncertain, prefer rotate
                # Heuristic: if rotate is on, disable cycle; else disable rotate
                if self.auto_rotate_enabled.get():
                    self.auto_cycle_enabled.set(False)
                else:
                    self.auto_rotate_enabled.set(False)
        except Exception:
            pass

        # Schedule auto-rotate if enabled (and 3D mode on)
        if bool(self.auto_rotate_enabled.get()) and bool(self.mode_3d_enabled.get()):
            self._auto_rotate_last_ts = time.time()
            self._auto_rotate_after = self.after(33, self._auto_rotate_tick)  # ~30fps
        else:
            self._auto_rotate_after = None

        # Schedule auto-cycle if enabled
        if bool(self.auto_cycle_enabled.get()):
            self._auto_cycle_after = self.after(1000, self._auto_cycle_tick)
        else:
            self._auto_cycle_after = None

        # Schedule screensaver check if enabled
        if bool(self.screensaver_enabled.get()):
            self._screensaver_after = self.after(1000, self._screensaver_tick)
        else:
            self._screensaver_after = None

        # Persist prefs after any change
        try:
            self._save_prefs()
        except Exception:
            pass

    def _auto_rotate_tick(self):
        # Only operate and reschedule if still enabled
        if not bool(self.auto_rotate_enabled.get()) or not bool(self.mode_3d_enabled.get()):
            self._auto_rotate_after = None
            return
        if not self.winfo_exists():
            return
        # Avoid conflicting with view animations (e.g., auto-cycle camera moves)
        if self._view_animating:
            self._auto_rotate_after = self.after(33, self._auto_rotate_tick)
            return
        # Time-based delta for smooth motion
        now = time.time()
        if self._auto_rotate_last_ts is None:
            self._auto_rotate_last_ts = now
        dt = max(0.0, min(0.2, now - self._auto_rotate_last_ts))
        self._auto_rotate_last_ts = now
        deg_per_sec = float(self.auto_rotate_deg_per_sec.get())
        deg_inc = deg_per_sec * dt
        new_azim = (self.ax.azim + deg_inc) % 360.0
        elev = self.ax.elev
        if self._screensaver_active:
            import math
            elev = 20 + 4 * math.sin(now * 0.3)
        self.ax.view_init(elev=elev, azim=new_azim)
        self.canvas.draw_idle()
        # Reschedule only if still enabled
        if bool(self.auto_rotate_enabled.get()) and bool(self.mode_3d_enabled.get()):
            self._auto_rotate_after = self.after(33, self._auto_rotate_tick)
        else:
            self._auto_rotate_after = None

    def _auto_cycle_tick(self):
        try:
            if not bool(self.auto_cycle_enabled.get()):
                return
            # Build sequence of components in left tree order if needed
            if not hasattr(self, '_cycle_sequence') or not self._cycle_sequence:
                self._build_cycle_sequence()
            if not hasattr(self, '_cycle_index'):
                self._cycle_index = 0
            if not self._cycle_sequence:
                return
            entry = self._cycle_sequence[self._cycle_index % len(self._cycle_sequence)]
            self._cycle_index += 1
            region_key, comp_name = entry
            self._cycle_to_component(region_key, comp_name)
        finally:
            # Reschedule based on seconds
            ms = max(1000, int(self.auto_cycle_seconds.get()) * 1000)
            self._auto_cycle_after = self.after(ms, self._auto_cycle_tick)

    def _build_cycle_sequence(self):
        """Linearize left tree items top-to-bottom into a list of (region_key, component_name)."""
        seq = []
        try:
            for region_key, region_data in self.regions.items():
                # Use the order we inserted components under regions
                for comp in region_data.get('components', []):
                    # Skip hardware emojis in cycle
                    if any(emoji in comp for emoji in ['🎮', '💻', '🧠', '⚡']):
                        continue
                    seq.append((region_key, comp))
        except Exception:
            pass
        self._cycle_sequence = seq

    def _cycle_to_component(self, region_key, comp_name):
        """Select left tree entry, zoom to node/component, open popup, highlight hull."""
        try:
            # Select in left tree
            item = None
            try:
                item = self._component_item_ids.get((region_key, comp_name))
                if item:
                    self.component_tree.selection_set(item)
                    self.component_tree.see(item)
            except Exception:
                pass

            # Highlight hull for region
            if region_key != self.hover_region:
                self.hover_region = region_key
                self._render_brain()

            # Find node for component
            node = self._find_node_for_component(region_key, comp_name)
            if node is None:
                # Fallback: zoom to region
                self._zoom_to_region(region_key)
                return

            # Zoom to node and show lightweight tip shortly after
            self._zoom_to_node(node)
            # Show tip after animation (~350ms)
            delay = 350
            try:
                if hasattr(self, '_auto_popup_after') and self._auto_popup_after:
                    self.after_cancel(self._auto_popup_after)
            except Exception:
                pass
            # Hide any previous tip
            self._hide_cycle_tip()
            self._auto_popup_after = self.after(delay, lambda n=node: self._show_cycle_tip(n))
            # Schedule tip close before next advance
            try:
                if hasattr(self, '_auto_popup_close_after') and self._auto_popup_close_after:
                    self.after_cancel(self._auto_popup_close_after)
            except Exception:
                pass
            dwell_ms = max(600, int(self.auto_cycle_seconds.get() * 1000 * 0.7))
            self._auto_popup_close_after = self.after(dwell_ms, lambda: self._hide_cycle_tip())
        except Exception:
            pass

    def _close_info_popup(self):
        try:
            if hasattr(self, '_info_win') and self._info_win and self._info_win.winfo_exists():
                self._info_win.destroy()
        except Exception:
            pass

    def _show_cycle_tip(self, node):
        """Show a small in-panel tooltip near the node (no window)."""
        try:
            # Compute screen position of node
            from mpl_toolkits.mplot3d import proj3d
            x3, y3, z3 = node.get('pos')
            x2, y2, _ = proj3d.proj_transform(x3, y3, z3, self.ax.get_proj())
            xpix, ypix = self.ax.transData.transform((x2, y2))
            # Translate to widget coords
            cx, cy = self.canvas_widget.winfo_rootx(), self.canvas_widget.winfo_rooty()
            tx = max(8, int(xpix - cx) + 12)
            ty = max(8, int(ypix - cy) + 12)

            # Build content
            region = self.regions.get(node.get('region'), {})
            text = f"{node.get('name','')}\n{region.get('subtitle','')}"

            if not hasattr(self, '_cycle_tip') or self._cycle_tip is None:
                f = tk.Frame(self.canvas_widget, bg='#000000')
                lbl = tk.Label(f, text=text, bg='#111111', fg='#eeeeee',
                               font=('Arial', 9), justify='left',
                               relief=tk.SOLID, borderwidth=1)
                lbl.pack(ipadx=6, ipady=4)
                self._cycle_tip = f
                self._cycle_tip_label = lbl
            else:
                self._cycle_tip_label.configure(text=text)
            # Place within canvas widget
            self._cycle_tip.place(x=tx, y=ty)
            self._cycle_tip.lift()
        except Exception:
            self._hide_cycle_tip()

    def _hide_cycle_tip(self):
        try:
            if hasattr(self, '_cycle_tip') and self._cycle_tip:
                self._cycle_tip.place_forget()
        except Exception:
            pass

    def _find_node_for_component(self, region_key, comp_name):
        try:
            # Exact name match preferred
            for n in self.nodes:
                if n.get('region') == region_key and (n.get('name') == comp_name):
                    return n
            # Try by name across regions
            for n in self.nodes:
                if n.get('name') == comp_name:
                    return n
            # Fallback: any node in region
            for n in self.nodes:
                if n.get('region') == region_key:
                    return n
        except Exception:
            pass
        return None

    def _zoom_to_node(self, node, steps=20):
        try:
            pos = node.get('pos')
            if pos is None:
                return
            x, y, z = pos
            # Face node center
            azim = float(np.degrees(np.arctan2(y, x)))
            dist = float(np.sqrt(x**2 + y**2))
            elev = float(np.degrees(np.arctan2(z, max(1e-6, dist))))
            # Tight limits around node
            margin = 0.12
            target_limits = (
                (x - margin, x + margin),
                (y - margin, y + margin),
                (z - margin, z + margin)
            )
            self._animate_view_to(elev, azim, target_limits, steps=steps)
        except Exception:
            pass

    def _screensaver_tick(self):
        try:
            if not bool(self.screensaver_enabled.get()):
                return
            idle = time.time() - float(self._last_interaction_ts or 0)
            if idle >= int(self.screensaver_idle_seconds.get()):
                # Enter screensaver mode without changing user toggles
                if not self._screensaver_active:
                    self._screensaver_active = True
                    # Start saver-only gentle rotation; do not modify auto_* toggles
                    self._start_saver_motion()
                if bool(self.screensaver_fullscreen.get()) and not bool(self.fullscreen_enabled.get()):
                    # Enter fullscreen for screensaver and remember to exit later
                    self._fs_was_for_screensaver = True
                    self.fullscreen_enabled.set(True)
                    self._apply_fullscreen(True)
        finally:
            self._screensaver_after = self.after(1000, self._screensaver_tick)

    def _start_saver_motion(self):
        # Gentle rotation independent of auto-rotate toggle
        try:
            self._saver_last_ts = time.time()
        except Exception:
            pass
        def tick():
            if not self._screensaver_active or not self.winfo_exists():
                return
            now = time.time()
            dt = max(0.0, min(0.2, now - getattr(self, '_saver_last_ts', now)))
            self._saver_last_ts = now
            # 10 deg/sec by default
            deg_inc = 10.0 * dt
            new_azim = (self.ax.azim + deg_inc) % 360.0
            # Subtle bob
            try:
                import math
                elev = 20 + 3 * math.sin(now * 0.25)
            except Exception:
                elev = self.ax.elev
            self.ax.view_init(elev=elev, azim=new_azim)
            self.canvas.draw_idle()
            # Requeue
            self._saver_after = self.after(33, tick)
        # Kick it off
        self._saver_after = self.after(33, tick)

    # --- Hover region heuristic when not over a node ---
    def _detect_hover_region_from_cursor(self, event):
        try:
            if event.x is None or event.y is None:
                return
            from mpl_toolkits.mplot3d import proj3d
            nearest = None
            best = 28.0  # px
            for key, region in self.regions.items():
                cx, cy, cz = region['center']
                x2, y2, _ = proj3d.proj_transform(cx, cy, cz, self.ax.get_proj())
                xpix, ypix = self.ax.transData.transform((x2, y2))
                d = ((event.x - xpix) ** 2 + (event.y - ypix) ** 2) ** 0.5
                if d < best:
                    best = d
                    nearest = key
            # Apply if changed
            if nearest != self.hover_region:
                self.hover_region = nearest
                self._render_brain()
                if nearest:
                    self._select_tree_region(nearest)
        except Exception:
            pass

    def _on_pick(self, event):
        """Handle node picking (click)"""
        # matplotlib pick event for 3D scatter is limited
        # For now, show a dialog with region info
        # In Phase 3, we'll implement proper 3D ray picking

        try:
            # Only respond to a clean left-click (not scroll/drag)
            me = getattr(event, 'mouseevent', None)
            now = time.time()
            if not me or getattr(me, 'button', None) != 1:
                return
            if now - self._last_interaction_ts < 0.2 or self.mouse_pressed:
                return

            ind = event.ind[0] if hasattr(event, 'ind') and len(event.ind) > 0 else None
            if ind is not None:
                node = self.nodes[ind] if ind < len(self.nodes) else None
                if node:
                    self._show_node_info(node)
        except Exception as e:
            print(f"Pick event error: {e}")

    def _show_node_info(self, node):
        """Show component details; reuses a single info window and swaps content."""
        try:
            region = self.regions.get(node['region'], {})
            self._open_info_window(title="Component Details")
            self._render_node_panel(node, region)
        except Exception as e:
            print(f"Info popup error: {e}")

    def _show_region_info(self, region_key):
        """Open region details popup with component buttons that swap to node view."""
        try:
            if region_key not in self.regions:
                return
            region = self.regions[region_key]
            self._open_info_window(title=f"{region.get('name','Region')} Details")
            self._render_region_panel(region_key)
        except Exception as e:
            print(f"Region info error: {e}")

    # --- Info window infra ---
    def _open_info_window(self, title="Details"):
        try:
            if not hasattr(self, '_info_win') or self._info_win is None or not self._info_win.winfo_exists():
                win = tk.Toplevel(self)
                win.configure(bg='#1a1a1a')
                win.geometry("420x340")
                self._info_win = win
                self._info_container = tk.Frame(win, bg='#1a1a1a')
                self._info_container.pack(fill='both', expand=True)
                win.bind('<Escape>', lambda _e: win.destroy())
            self._info_win.title(title)
            # Clear previous body
            for child in list(self._info_container.children.values()):
                try:
                    child.destroy()
                except Exception:
                    pass
        except Exception:
            pass

    def _render_region_panel(self, region_key):
        try:
            region = self.regions.get(region_key, {})
            c = self._info_container
            header = tk.Frame(c, bg='#1a1a1a'); header.pack(fill='x', pady=(8,4))
            tk.Label(header, text=region.get('name','Region'), fg='#ffffff', bg='#1a1a1a',
                     font=('Arial', 12, 'bold')).pack(anchor='w', padx=10)
            tk.Label(header, text=region.get('subtitle',''), fg='#bbbbbb', bg='#1a1a1a',
                     font=('Arial', 9)).pack(anchor='w', padx=10)

            # Components as buttons
            tk.Label(c, text="Components:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(8, 4))
            body = tk.Frame(c, bg='#1a1a1a'); body.pack(fill='both', expand=True)
            # Scrollable container if needed could be added later
            for comp in region.get('components', []):
                if any(emoji in comp for emoji in ['🎮','💻','🧠','⚡']):
                    fg = '#6dd5ed'
                else:
                    fg = '#dddddd'
                b = tk.Button(body, text=comp, anchor='w', relief=tk.FLAT, bg='#2a2a2a', fg=fg,
                              activebackground='#3a3a3a',
                              command=(lambda rk=region_key, cn=comp: self._on_region_component_button(rk, cn)))
                b.pack(fill='x', padx=10, pady=2)

            # Footer quick actions
            footer = tk.Frame(c, bg='#1a1a1a'); footer.pack(fill='x', pady=(6,8))
            tk.Button(footer, text="Open Related Tab", relief=tk.FLAT,
                      command=(lambda r=region: self._open_related_tab(r)),
                      bg='#2a2a2a', fg='#88c0d0', activebackground='#3a3a3a').pack(side='left', padx=8)
        except Exception:
            pass

    def _on_region_component_button(self, region_key, comp_name):
        try:
            # Resolve region if component belongs elsewhere
            rk = region_key
            try:
                found = False
                for k, r in self.regions.items():
                    if comp_name in r.get('components', []):
                        rk = k
                        found = True
                        break
            except Exception:
                rk = region_key
            node = self._find_node_for_component(rk, comp_name)
            if node is None:
                # Render message inline
                self._open_info_window(title="Component Details")
                c = self._info_container
                tk.Label(c, text=f"No node generated for {comp_name} yet.", fg='#cccccc', bg='#1a1a1a',
                         font=('Arial', 10)).pack(padx=10, pady=10, anchor='w')
                return
            self._open_info_window(title="Component Details")
            self._render_node_panel(node, self.regions.get(rk, {}))
        except Exception:
            pass

    def _render_node_panel(self, node, region):
        try:
            c = self._info_container
            header = tk.Frame(c, bg='#1a1a1a'); header.pack(fill='x', pady=(8,4))
            tk.Label(header, text=node.get('name','Component'), fg='#ffffff', bg='#1a1a1a',
                     font=('Arial', 12, 'bold')).pack(anchor='w', padx=10)
            tk.Label(header, text=f"{region.get('name','')} — {region.get('subtitle','')}", fg='#bbbbbb', bg='#1a1a1a',
                     font=('Arial', 9)).pack(anchor='w', padx=10)

            # Official component details
            details = self._get_component_details(node.get('name',''))
            if details:
                desc = details.get('description') or ''
                if desc:
                    tk.Label(c, text=desc, fg='#cfd8dc', bg='#1a1a1a', font=('Arial', 9), wraplength=380, justify='left').pack(anchor='w', padx=10, pady=(6, 6))
                fp = details.get('file_path')
                row = tk.Frame(c, bg='#1a1a1a'); row.pack(anchor='w', padx=10, pady=(0, 6))
                tk.Label(row, text="Module:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(side='left')
                if fp:
                    tk.Button(row, text=str(fp), command=(lambda p=fp: self._open_source_file(p)), relief=tk.FLAT,
                              bg='#2a2a2a', fg='#88c0d0', activebackground='#3a3a3a').pack(side='left', padx=(6,0))
                else:
                    tk.Label(row, text="(not mapped)", fg='#777777', bg='#1a1a1a', font=('Arial', 9)).pack(side='left', padx=(6,0))

            # Status badges (module/tests/docs)
            st = self._compute_component_status(node.get('name',''), region)
            srow = tk.Frame(c, bg='#1a1a1a'); srow.pack(anchor='w', padx=10, pady=(0,6))
            tk.Label(srow, text="Status:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(side='left', padx=(0,6))
            def badge(text, ok):
                col = '#7fb77e' if ok else '#d97777'
                tk.Label(srow, text=text, fg='#eeeeee', bg=col, font=('Arial', 8, 'bold'), padx=6, pady=1).pack(side='left', padx=3)
            badge('Module', bool(st.get('module_exists')))
            badge('Tests', bool(st.get('tests_found')))
            badge('Docs', bool(st.get('docs_found')))

            # Optional: list first few test/doc files as quick-open buttons
            if st.get('test_paths'):
                trow = tk.Frame(c, bg='#1a1a1a'); trow.pack(anchor='w', padx=10, pady=(2,2))
                tk.Label(trow, text="Tests:", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side='left', padx=(0,6))
                for p in st['test_paths'][:3]:
                    tk.Button(trow, text=p, relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc', activebackground='#3a3a3a',
                              command=(lambda q=p: self._open_source_file(q))).pack(side='left', padx=3)
            if st.get('doc_paths'):
                drow = tk.Frame(c, bg='#1a1a1a'); drow.pack(anchor='w', padx=10, pady=(2,6))
                tk.Label(drow, text="Docs:", fg='#888888', bg='#1a1a1a', font=('Arial', 9)).pack(side='left', padx=(0,6))
                for p in st['doc_paths'][:3]:
                    tk.Button(drow, text=p, relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc', activebackground='#3a3a3a',
                              command=(lambda q=p: self._open_source_file(q))).pack(side='left', padx=3)

            # Detected modules list (click-to-open)
            tk.Label(c, text="Detected Modules:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10)
            mod_wrap = tk.Frame(c, bg='#1a1a1a'); mod_wrap.pack(fill='both', expand=False, padx=10)
            mods = self._discover_related_files(node.get('name',''), region)
            if mods:
                for p in mods[:8]:
                    tk.Button(mod_wrap, text=p, anchor='w', relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc',
                              activebackground='#3a3a3a', command=(lambda q=p: self._open_source_file(q))).pack(fill='x', pady=1)
            else:
                tk.Label(mod_wrap, text="(none found)", fg='#777777', bg='#1a1a1a', font=('Arial', 9)).pack(anchor='w')

            # Related components (swap view on click)
            tk.Label(c, text="Related:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 10, 'bold')).pack(anchor='w', padx=10, pady=(6,2))
            rel = tk.Frame(c, bg='#1a1a1a'); rel.pack(fill='x')
            rel_list = []
            try:
                if details and isinstance(details, dict):
                    rel_list = details.get('related_components') or []
            except Exception:
                rel_list = []
            if not rel_list:
                rel_list = region.get('components', [])
            for comp in rel_list[:6]:
                tk.Button(rel, text=comp, relief=tk.FLAT, bg='#2a2a2a', fg='#dddddd', activebackground='#3a3a3a',
                          command=(lambda cn=comp: self._on_region_component_button(node.get('region'), cn))).pack(side='left', padx=4, pady=2)

            # Quick actions (from component details, overrideable by plan)
            qa = tk.Frame(c, bg='#1a1a1a'); qa.pack(fill='x', pady=(8,8))
            tk.Label(qa, text="Quick Actions:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 10, 'bold')).pack(side='left', padx=10)
            detail = self._get_component_details(node.get('name',''))
            actions = (detail.get('quick_actions') if isinstance(detail, dict) else None) or []
            if not actions:
                actions = [
                    {'label': 'Open .py', 'action': 'open_module'},
                    {'label': 'Related Tab', 'action': 'open_tab'},
                    {'label': 'RAG Network', 'action': 'open_rag'},
                    {'label': 'Agents', 'action': 'open_agents'},
                    {'label': 'Models', 'action': 'open_models'},
                    {'label': 'Types', 'action': 'open_types'},
                ]
            for a in actions[:6]:
                lbl = a.get('label','Action')
                act = a.get('action','')
                tk.Button(qa, text=lbl, relief=tk.FLAT, bg='#2a2a2a', fg='#88c0d0', activebackground='#3a3a3a',
                          command=(lambda _act=act, _node=node, _region=region, _detail=detail: self._execute_action(_act, _node, _region, _detail))).pack(side='left', padx=4)

            # Open Tabs group
            tabs = tk.Frame(c, bg='#1a1a1a'); tabs.pack(fill='x', pady=(2,2))
            tk.Label(tabs, text="Open Tabs:", fg='#4a90e2', bg='#1a1a1a', font=('Arial', 10, 'bold')).pack(side='left', padx=10)
            for lbl, act in [('Models','open_models'),('Types','open_types'),('Agents','open_agents'),('Training','open_training'),('Settings','open_settings'),('RAG','open_rag')]:
                tk.Button(tabs, text=lbl, relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc', activebackground='#3a3a3a',
                          command=(lambda a=act: self._execute_action(a, node, region, detail))).pack(side='left', padx=3)

            # Models subtabs group
            subs = tk.Frame(c, bg='#1a1a1a'); subs.pack(fill='x', pady=(2,2))
            tk.Label(subs, text="Models →", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(side='left', padx=10)
            sub_actions = [
                ('Skills','open_skills'),('Stats','open_stats'),('Adapters','open_adapters'),('Levels','open_levels'),
                ('Evaluation','open_evaluation'),('Baselines','open_baselines'),('Compare','open_compare'),('Viz','open_visualization')
            ]
            for lbl, act in sub_actions:
                tk.Button(subs, text=lbl, relief=tk.FLAT, bg='#2a2a2a', fg='#dddddd', activebackground='#3a3a3a',
                          command=(lambda a=act: self._execute_action(a, node, region, detail))).pack(side='left', padx=3)

            # Sessions quick actions
            sess = tk.Frame(c, bg='#1a1a1a'); sess.pack(fill='x', pady=(2,8))
            tk.Label(sess, text="Sessions:", fg='#888888', bg='#1a1a1a', font=('Arial', 9, 'bold')).pack(side='left', padx=10)
            tk.Button(sess, text='Chat Quick Actions', relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc', activebackground='#3a3a3a',
                      command=lambda: self._execute_action('open_chat_quick', node, region, detail)).pack(side='left', padx=3)
            tk.Button(sess, text='Project Quick Actions', relief=tk.FLAT, bg='#2a2a2a', fg='#cfd8dc', activebackground='#3a3a3a',
                      command=lambda: self._execute_action('open_project_quick', node, region, detail)).pack(side='left', padx=3)

            # Back to region
            back = tk.Frame(c, bg='#1a1a1a'); back.pack(fill='x')
            tk.Button(back, text=f"← Back to {region.get('name','Region')}", relief=tk.FLAT, bg='#2a2a2a', fg='#dddddd',
                      activebackground='#3a3a3a', command=(lambda rk=node.get('region'): self._render_region_panel(rk))).pack(anchor='w', padx=10, pady=(6,8))
        except Exception:
            pass

    def _discover_related_files(self, name, region):
        """Heuristic scan for .py files that match component/region tokens.
        Returns a list of repo-relative paths.
        """
        results = []
        try:
            tokens = []
            nm = (name or '').strip().lower()
            if nm:
                tokens.extend([t for t in nm.replace('-', ' ').replace('_', ' ').split() if len(t) > 2])
            reg = (region.get('name','') or '').lower()
            if reg:
                tokens.extend([t for t in reg.replace('-', ' ').split() if len(t) > 3])
            # Dedup
            seen = set(tokens)
            if not seen:
                return results
            base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            for root, _dirs, files in os.walk(base):
                # Skip big export or data folders
                if any(skip in root for skip in ['exports', 'venv', '.git', '__pycache__', 'user_prefs']):
                    continue
                for f in files:
                    if not f.endswith('.py'):
                        continue
                    # Simple filename match on any token
                    fl = f.lower()
                    if any(tok in fl for tok in seen):
                        full = os.path.join(root, f)
                        try:
                            rel = os.path.relpath(full, base)
                        except Exception:
                            rel = full
                        results.append(rel)
                        if len(results) >= 12:
                            return results
        except Exception:
            pass
        return results

    def _component_to_file_path(self, comp_name, region):
        """Map a component (and region) to a likely source file path in the app."""
        try:
            name = (comp_name or '').lower()
            region_name = (region.get('name','') or '').lower()
            # Known mappings
            mapping = {
                'brain map': 'Data/tabs/models_tab/brain_viz_3d.py',
                'stats system': 'Data/tabs/models_tab/stats_panel.py',
                'stats dashboard': 'Data/tabs/models_tab/stats_panel.py',
                'type catalog': 'Data/tabs/models_tab/types_panel.py',
                'models tab': 'Data/tabs/models_tab/models_tab.py',
                'rag network': 'Data/tabs/collections_tab/rag_network_viz.py',
                'rag visualizer': 'Data/tabs/collections_tab/rag_network_viz.py',
                'training scripts': 'Data/tabs/training_tab/training_tab.py',
                'evaluation pipeline': 'Data/tabs/training_tab/training_tab.py',
                'tool registry': 'Data/tabs/training_tab/training_tab.py',
                'event bus': 'Data/tabs/settings_tab/settings_tab.py',
                'state management': 'Data/tabs/settings_tab/settings_tab.py',
                'config system': 'Data/tabs/settings_tab/settings_tab.py',
                'chat history': 'Data/tabs/models_tab/models_tab.py',
                'training history': 'Data/tabs/models_tab/models_tab.py',
            }
            # Fallbacks by region
            if name in mapping:
                return mapping[name]
            if 'frontal' in region_name:
                return 'Data/tabs/models_tab/models_tab.py'
            if 'parietal' in region_name:
                return 'Data/tabs/models_tab/stats_panel.py'
            if 'temporal' in region_name:
                return 'Data/tabs/collections_tab/rag_network_viz.py'
            if 'occipital' in region_name:
                return 'Data/tabs/models_tab/brain_viz_3d.py'
            if 'motor' in region_name:
                return 'Data/tabs/training_tab/training_tab.py'
            if 'sensory' in region_name:
                return 'Data/tabs/custom_code_tab/sub_tabs/chat_interface_tab.py'
            if 'cerebellum' in region_name:
                return 'Data/tabs/models_tab/types_panel.py'
            if 'corpus' in region_name:
                return 'Data/tabs/settings_tab/settings_tab.py'
        except Exception:
            pass
        return None

    def _open_source_file(self, rel_path):
        """Open a source file via callback or OS handler, if possible."""
        if not rel_path:
            return
        try:
            import os, sys, subprocess
            # Prefer app-level callback if provided
            if callable(self.open_file_callback):
                self.open_file_callback(rel_path)
                return
            # Fallback: open with OS
            abs_path = rel_path
            # Models tab typically runs with CWD at project root
            if not os.path.isabs(abs_path):
                # Try to resolve relative to repo root (two parents up from this file)
                base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                abs_path = os.path.abspath(os.path.join(base, rel_path))
            if sys.platform.startswith('win'):
                os.startfile(abs_path)  # noqa: P204
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', abs_path])
            else:
                subprocess.Popen(['xdg-open', abs_path])
        except Exception as e:
            print(f"Open file failed: {e}")

    def _open_related_tab(self, region):
        """Navigate to a related UI tab via callback; fallback to toast/log."""
        try:
            # If a rich payload dict is provided with explicit tab/subtab/session, forward as-is
            if isinstance(region, dict) and ('tab' in region or 'subtab' in region or 'session' in region):
                payload = dict(region)
                if callable(self.open_tab_callback):
                    self.open_tab_callback(payload)
                    return
                print(f"[Brain] Open route: {payload}")
                return

            # Normalize simple inputs to a canonical tab identifier
            name = ''
            if isinstance(region, dict):
                name = region.get('name','')
            elif isinstance(region, str):
                name = region
            key = (name or '').strip().lower()
            aliases = {
                'rag network': 'RAG',
                'rag': 'RAG',
                'brain map': 'Models',
                'types': 'Types',
                'type catalog': 'Types',
                'agents': 'Agents',
                'settings': 'Settings',
                'training': 'Training',
                'models': 'Models',
                'collections': 'Models',
            }
            tab_id = aliases.get(key, name)
            if callable(self.open_tab_callback):
                self.open_tab_callback({'tab': tab_id})
                return
            print(f"[Brain] Open related tab requested: {tab_id}")
        except Exception as e:
            print(f"Open tab failed: {e}")

    # --- Fullscreen helpers ---
    def _bind_fullscreen_shortcuts(self):
        try:
            top = self.winfo_toplevel()
            # ESC exits fullscreen safely
            top.bind('<Escape>', lambda _e: self._exit_fullscreen())
        except Exception:
            pass

    def _apply_fullscreen(self, enabled=None):
        try:
            if enabled is None:
                enabled = bool(self.fullscreen_enabled.get())
            top = self.winfo_toplevel()
            if enabled:
                # Save current geometry to restore later
                try:
                    self._prev_geometry = top.geometry()
                except Exception:
                    self._prev_geometry = None
                # Enter fullscreen
                try:
                    top.attributes('-fullscreen', True)
                except Exception:
                    top.wm_attributes('-fullscreen', True)
            else:
                # Exit fullscreen
                try:
                    top.attributes('-fullscreen', False)
                except Exception:
                    top.wm_attributes('-fullscreen', False)
                # Restore previous geometry if available
                if self._prev_geometry:
                    try:
                        top.geometry(self._prev_geometry)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[Brain] fullscreen error: {e}")

    def _exit_fullscreen(self):
        try:
            if self.fullscreen_enabled.get():
                self.fullscreen_enabled.set(False)
                self._apply_fullscreen(False)
        except Exception:
            pass

    def load_model_kernel(self, model_data):
        """Load a model into the brain center as kernel and light up brain regions"""
        self.model_kernel = {
            'name': model_data.get('trainee_name', 'Model'),
            'type': model_data.get('assigned_type', 'unknown'),
            'class': model_data.get('class_level', 'novice'),
            'data': model_data
        }

        # Determine model's class color
        # Class colors (matches type_catalog_v2.json structure)
        class_colors = {
            'novice': '#90EE90',      # Light green
            'skilled': '#FFD700',     # Gold
            'adept': '#FF8C00',       # Dark orange
            'expert': '#FF4500',      # Red-orange
            'master': '#DC143C',      # Crimson
            'grand_master': '#8B008B',# Dark magenta
            'legendary': '#FFD700'    # Bright gold (legacy/future)
        }

        model_class = model_data.get('class_level', 'novice').lower()
        model_color = class_colors.get(model_class, '#90EE90')

        # Get skills and stats to determine which regions should light up
        skills = model_data.get('skills', {})
        assigned_type = model_data.get('assigned_type', '')

        # Calculate how trained the model is (0.0 to 1.0)
        # XP can be int (old format) or dict with 'total' key (new format)
        xp_data = model_data.get('xp', 0)
        if isinstance(xp_data, dict):
            total_xp = xp_data.get('total', 0)
        elif isinstance(xp_data, (int, float)):
            total_xp = int(xp_data)
        else:
            total_xp = 0
        training_level = min(total_xp / 10000.0, 1.0)  # Cap at 10k XP for full brightness

        # Map skills and model type to brain regions
        region_activation = {
            'frontal': 0.3,      # Always some base activity (planning/orchestration)
            'parietal': 0.3,     # Always some base activity (processing)
            'temporal': 0.3,     # Always some base activity (memory)
            'occipital': 0.3,    # Always some base activity (visualization)
            'motor': 0.3,        # Always some base activity (execution)
            'sensory': 0.3,      # Always some base activity (input)
            'cerebellum': 0.3,   # Always some base activity (coordination)
            'corpus': 0.5        # Central communication always active
        }

        # Increase activation based on skills
        if 'planning' in skills or 'orchestration' in skills:
            region_activation['frontal'] = 0.9
        if 'analytics' in skills or 'stats' in skills:
            region_activation['parietal'] = 0.9
        if 'memory' in skills or 'rag' in skills or 'retrieval' in skills:
            region_activation['temporal'] = 0.9
        if 'visualization' in skills:
            region_activation['occipital'] = 0.9
        if 'execution' in skills or 'tools' in skills:
            region_activation['motor'] = 0.9
        if 'input' in skills or 'processing' in skills:
            region_activation['sensory'] = 0.9
        if 'coordination' in skills or 'typing' in skills:
            region_activation['cerebellum'] = 0.9

        # Type-specific activations
        if 'orchestrator' in assigned_type.lower():
            # Orchestrators use everything
            for region in region_activation:
                region_activation[region] = max(region_activation[region], 0.95)
        elif 'planner' in assigned_type.lower():
            region_activation['frontal'] = 0.95
            region_activation['corpus'] = 0.8
        elif 'analyzer' in assigned_type.lower():
            region_activation['parietal'] = 0.95
            region_activation['occipital'] = 0.8
        elif 'specialist' in assigned_type.lower():
            # Specialists focus on specific regions
            region_activation['motor'] = 0.85
            region_activation['sensory'] = 0.85

        # Apply training level multiplier
        for region in region_activation:
            region_activation[region] *= (0.3 + 0.7 * training_level)

        # Update region colors with smooth transition
        self._animate_region_colors(model_color, region_activation)

        # Highlight connectors for this model type as "active"
        self.set_active_model_type(assigned_type, model_color)

    def set_active_model_type(self, assigned_type, class_color=None):
        """Set active model type to light up the most relevant regions and connectors.
        class_color: optional color for active edges.
        """
        try:
            self.active_type = assigned_type or ''
            if class_color:
                self.active_class_color = class_color
            t = (assigned_type or '').lower()
            active_regions = set()
            if 'orchestrator' in t or 'grand' in t:
                active_regions = set(self.regions.keys())
            elif 'planner' in t or 'coder' in t:
                active_regions.update(['frontal', 'corpus'])
            elif 'research' in t or 'researcher' in t:
                active_regions.update(['temporal', 'frontal', 'corpus'])
            elif 'analy' in t or 'debug' in t:
                active_regions.update(['parietal', 'occipital'])
            elif 'browser' in t or 'sensory' in t:
                active_regions.update(['sensory', 'frontal'])
            elif 'trainer' in t or 'motor' in t:
                active_regions.update(['motor', 'corpus'])
            else:
                active_regions.update(['corpus'])

            self._active_regions = active_regions
            # Compute active edges: any edge touching an active region
            active_nodes = set(n['id'] for n in self.nodes if n['region'] in active_regions)
            self._active_edges = set()
            for (a, b) in self.edges:
                if a in active_nodes or b in active_nodes:
                    self._active_edges.add((a, b))
            # Redraw
            self._render_brain()
        except Exception:
            pass

    def _update_position_labels(self):
        """Update camera position labels"""
        try:
            azim = self.ax.azim
            elev = self.ax.elev

            self.azim_label.config(text=f"Az: {int(azim)}°")
            self.elev_label.config(text=f"El: {int(elev)}°")
            self.zoom_label.config(text=f"Zoom: {int(self.zoom_level * 100)}%")

            # Schedule next update
            self.after(100, self._update_position_labels)
        except Exception:
            pass  # Widget might be destroyed

    def _animate_region_colors(self, model_color, region_activation):
        """Smoothly animate region colors based on model activation levels"""
        # Store target colors and activation levels
        self.target_activation = region_activation
        self.model_active_color = model_color

        # Initialize current activation if not exists
        if not hasattr(self, 'current_activation'):
            self.current_activation = {region: 0.3 for region in self.regions.keys()}

        # Start animation loop
        self._color_animation_step = 0
        self._color_animation_steps = 30  # 30 frames for smooth transition
        self._animate_color_frame()

    def _animate_color_frame(self):
        """Single frame of color animation"""
        if self._color_animation_step >= self._color_animation_steps:
            # Animation complete, ensure we're at exact target
            for region_key in self.regions:
                self.current_activation[region_key] = self.target_activation.get(region_key, 0.3)
                self._apply_region_color(region_key)
            self._render_brain()
            return

        # Calculate interpolation factor (0.0 to 1.0)
        t = self._color_animation_step / self._color_animation_steps
        # Ease-in-out curve for smoother animation
        t = t * t * (3.0 - 2.0 * t)

        # Interpolate activation levels
        for region_key in self.regions:
            current = self.current_activation[region_key]
            target = self.target_activation.get(region_key, 0.3)
            self.current_activation[region_key] = current + (target - current) * t
            self._apply_region_color(region_key)

        # Render updated brain
        self._render_brain()

        # Schedule next frame
        self._color_animation_step += 1
        self.after(33, self._animate_color_frame)  # ~30 FPS

    def _apply_region_color(self, region_key):
        """Apply color to region based on activation level"""
        region = self.regions[region_key]
        activation = self.current_activation[region_key]

        # Interpolate between default color and model color
        default_color = region['default_color']

        if hasattr(self, 'model_active_color'):
            # Parse hex colors to RGB
            def hex_to_rgb(hex_color):
                hex_color = hex_color.lstrip('#')
                return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

            def rgb_to_hex(rgb):
                return '#{:02x}{:02x}{:02x}'.format(
                    int(rgb[0] * 255),
                    int(rgb[1] * 255),
                    int(rgb[2] * 255)
                )

            default_rgb = hex_to_rgb(default_color)
            model_rgb = hex_to_rgb(self.model_active_color)

            # Blend colors based on activation
            blended_rgb = tuple(
                default_rgb[i] + (model_rgb[i] - default_rgb[i]) * activation
                for i in range(3)
            )

            region['color'] = rgb_to_hex(blended_rgb)
        else:
            # No model loaded, use default
            region['color'] = default_color

    def _on_3d_mode_toggle(self):
        """Handle 3D mode toggle - enables/disables rotation and zoom controls"""
        is_3d = self.mode_3d_enabled.get()

        # Enable/disable controls based on 3D mode
        if is_3d:
            # Enable controls - restore to previous state
            # (rotation_enabled and scroll_enabled keep their checkbox states)
            pass
        else:
            # 3D mode off - disable all movement (view is frozen)
            # Controls will gray out via the get() checks in mouse handlers
            pass

        # Redraw to show any changes
        self.canvas.draw_idle()

    def reset_view(self):
        """Reset camera to default view"""
        self.ax.view_init(elev=20, azim=45)
        self.ax.set_xlim(-1, 1)
        self.ax.set_ylim(-0.8, 0.8)
        self.ax.set_zlim(-0.6, 0.6)
        self.zoom_level = 1.0
        self.canvas.draw()

    def _on_tree_select(self, event):
        """Handle 2D tree selection - zoom to selected region/component"""
        selection = self.component_tree.selection()
        if not selection:
            return

        item = selection[0]
        item_tags = self.component_tree.item(item, 'tags')

        # Get the region key
        comp_name = None
        if 'region' in item_tags:
            # Selected a region - find region key from text
            text = self.component_tree.item(item, 'text').strip()
            region_key = None
            for key, data in self.regions.items():
                if data['name'] in text:
                    region_key = key
                    break
        elif 'component' in item_tags:
            # Selected a component - get region from parent or stored value
            parent = self.component_tree.parent(item)
            if parent:
                parent_text = self.component_tree.item(parent, 'text').strip()
                region_key = None
                for key, data in self.regions.items():
                    if data['name'] in parent_text:
                        region_key = key
                        break
                # Extract component name
                comp_name = (self.component_tree.item(item, 'text') or '').strip()
            else:
                return
        else:
            return

        if region_key and region_key in self.regions:
            # Highlight target region hull
            if region_key != self.hover_region:
                self.hover_region = region_key
                self._render_brain()

            if comp_name:
                # Try to zoom to specific node for this component
                node = self._find_node_for_component(region_key, comp_name)
                if node is not None:
                    self._zoom_to_node(node)
                    # Open detailed window popup after animation
                    self.after(350, lambda n=node: self._show_node_info(n))
                    return

            # Fallback: region-level zoom and info
            self._zoom_to_region(region_key)
            self.after(320, lambda rk=region_key: self._show_region_info(rk))

    def _on_tree_hover(self, event):
        """Handle mouse hover over 2D tree - highlight nodes in 3D"""
        # Get item under cursor
        item = self.component_tree.identify_row(event.y)
        if not item:
            # Clear highlight when not hovering an item
            if self.hover_region is not None:
                self.hover_region = None
                self._render_brain()
            return

        # Determine region from item under cursor
        tags = self.component_tree.item(item, 'tags')
        region_key = None
        if 'region' in tags:
            text = self.component_tree.item(item, 'text').strip()
            for key, data in self.regions.items():
                if data['name'] in text:
                    region_key = key
                    break
        elif 'component' in tags:
            parent = self.component_tree.parent(item)
            if parent:
                parent_text = self.component_tree.item(parent, 'text').strip()
                for key, data in self.regions.items():
                    if data['name'] in parent_text:
                        region_key = key
                        break

        # Apply highlight if changed
        if region_key != self.hover_region:
            self.hover_region = region_key
            self._render_brain()

    def _zoom_to_region(self, region_key):
        """Zoom camera to focus on specific brain region"""
        if region_key not in self.regions:
            return

        region = self.regions[region_key]
        center = region['center']
        radii = region['radii']

        # Calculate viewing angles to face the region
        # Point camera towards region center
        dx, dy, dz = center

        # Calculate azimuth (rotation around Z) and elevation
        azim = np.degrees(np.arctan2(dy, dx))
        dist = np.sqrt(dx**2 + dy**2)
        elev = np.degrees(np.arctan2(dz, dist))

        # Smoothly transition to new view and zoom
        margin = 0.3
        max_radius = max(radii)
        target_limits = (
            (center[0] - max_radius - margin, center[0] + max_radius + margin),
            (center[1] - max_radius - margin, center[1] + max_radius + margin),
            (center[2] - max_radius - margin, center[2] + max_radius + margin)
        )
        self._animate_view_to(elev, azim, target_limits, steps=20)

        # Show info message
        info_text = f"Focused on: {region['name']}\n{region['subtitle']}\n\nComponents:\n"
        for comp in region['components']:
            info_text += f"  • {comp}\n"

        # Update status (could show in a label or tooltip)
        print(f"[Brain] Zoomed to {region['name']}")

    def _angle_delta(self, current, target):
        """Shortest signed angular delta from current to target (degrees)."""
        delta = (target - current + 180) % 360 - 180
        return delta

    def _animate_view_to(self, target_elev, target_azim, target_limits=None, steps=20):
        """Animate camera elevation/azimuth (and optionally axis limits) to target values."""
        try:
            start_elev = self.ax.elev
            start_azim = self.ax.azim
        except Exception:
            start_elev, start_azim = 20, 45

        de = self._angle_delta(start_elev, target_elev) / steps
        da = self._angle_delta(start_azim, target_azim) / steps

        if target_limits is not None:
            x0, x1 = self.ax.get_xlim()
            y0, y1 = self.ax.get_ylim()
            z0, z1 = self.ax.get_zlim()
            (tx0, tx1), (ty0, ty1), (tz0, tz1) = target_limits
            dx0 = (tx0 - x0) / steps
            dx1 = (tx1 - x1) / steps
            dy0 = (ty0 - y0) / steps
            dy1 = (ty1 - y1) / steps
            dz0 = (tz0 - z0) / steps
            dz1 = (tz1 - z1) / steps
        else:
            dx0 = dx1 = dy0 = dy1 = dz0 = dz1 = 0

        self._view_animating = True
        def step(i=0):
            if i >= steps:
                # Finalize
                self.ax.view_init(elev=target_elev, azim=target_azim)
                if target_limits is not None:
                    (tx0, tx1), (ty0, ty1), (tz0, tz1) = target_limits
                    self.ax.set_xlim(tx0, tx1)
                    self.ax.set_ylim(ty0, ty1)
                    self.ax.set_zlim(tz0, tz1)
                # Ensure axis marks reflect final limits
                try:
                    self._apply_axes_marks()
                except Exception:
                    pass
                self.canvas.draw_idle()
                self._view_animating = False
                return

            self.ax.view_init(elev=start_elev + de * i, azim=start_azim + da * i)
            if target_limits is not None:
                x0i, x1i = self.ax.get_xlim()
                y0i, y1i = self.ax.get_ylim()
                z0i, z1i = self.ax.get_zlim()
                self.ax.set_xlim(x0i + dx0, x1i + dx1)
                self.ax.set_ylim(y0i + dy0, y1i + dy1)
                self.ax.set_zlim(z0i + dz0, z1i + dz1)
            self.canvas.draw_idle()
            # 15ms per frame ~ 60fps; tweak for smoothness
            self.after(15, lambda: step(i + 1))

        step()
