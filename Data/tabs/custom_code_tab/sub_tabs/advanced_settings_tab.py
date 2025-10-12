# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Advanced Settings Sub-Tab - Advanced OpenCode features configuration
Provides granular control over all 37 OpenCode v1.2 systems with collapsible categories
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class CollapsibleFrame(ttk.Frame):
    """A collapsible frame widget"""

    def __init__(self, parent, title, **kwargs):
        super().__init__(parent, **kwargs)
        self.is_expanded = tk.BooleanVar(value=False)

        # Header button
        self.toggle_btn = ttk.Button(
            self,
            text=f"▶ {title}",
            command=self.toggle,
            style='Toolbutton'
        )
        self.toggle_btn.pack(fill=tk.X, padx=5, pady=2)

        # Content frame (hidden by default)
        self.content = ttk.Frame(self, style='Category.TFrame')
        self.title = title

    def toggle(self):
        """Toggle the expanded/collapsed state"""
        if self.is_expanded.get():
            # Collapse
            self.content.pack_forget()
            self.toggle_btn.configure(text=f"▶ {self.title}")
            self.is_expanded.set(False)
        else:
            # Expand
            self.content.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            self.toggle_btn.configure(text=f"▼ {self.title}")
            self.is_expanded.set(True)


class AdvancedSettingsTab(BaseTab):
    """Advanced settings configuration for all OpenCode v1.2 features"""

    # MODE-TO-ADVANCED-SETTINGS MAPPINGS
    # Defines which advanced systems are enabled/disabled per mode
    MODE_ADVANCED_MAPPINGS = {
        'standard': {
            # Standard mode: No advanced systems, just basic functionality
            'enabled_systems': [],
            'profile': 'default'
        },
        'fast': {
            # Fast mode: Minimal systems for speed
            'enabled_systems': [
                'json_repair',           # Quick JSON fixes
                'schema_validation',     # Fast validation
                'model_selector',        # Auto-select fastest model
            ],
            'profile': 'conservative',
            'resource_percentage': 25
        },
        'smart': {
            # Smart mode: Balanced intelligence with key systems
            'enabled_systems': [
                'format_translation',    # Handle alternate formats
                'json_repair',           # Repair malformed JSON
                'schema_validation',     # Validate arguments
                'tool_orchestrator',     # Intelligent tool execution
                'intelligent_routing',   # Route to appropriate tools
                'context_scoring',       # Score context quality
                'pre_rag_optimizer',     # Optimize context
                'verification',          # Verify outputs
                'quality_assurance',     # Quality checks
                'resource_management',   # Smart resource allocation
                'model_selector',        # Context-aware model selection
                'confirmation_gates',    # Risk-based confirmations
            ],
            'profile': 'balanced',
            'resource_percentage': 50
        },
        'think': {
            # Think mode: All systems enabled for maximum quality
            'enabled_systems': [
                # Parsing & Translation
                'format_translation',
                'json_repair',
                # Tool Intelligence
                'schema_validation',
                'tool_orchestrator',
                'intelligent_routing',
                'confirmation_gates',
                # Context & RAG
                'context_scoring',
                'pre_rag_optimizer',
                'rag_feedback',
                'mvco_engine',
                # Quality & Verification
                'verification',
                'quality_assurance',
                'master_quality',
                'quality_recovery',
                # Workflow & Project
                'adaptive_workflow',
                'workflow_optimizer',
                'session_manager',
                # Model & Resource Management
                'resource_management',
                'time_slicing',
                'model_optimizer',
                'model_selector',
                'performance_benchmark',
                # Security & Policy
                'hardening_manager',
                'complexity_analyzer',
                'atomic_writer',
                'auto_policy',
                'command_policy',
            ],
            'profile': 'aggressive',
            'resource_percentage': 75
        }
    }

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.settings_file = Path(__file__).parent.parent / "advanced_settings.json"
        self.mode_settings_file = Path(__file__).parent.parent / "mode_settings.json"
        self.settings = self.load_settings()
        self.setting_vars = {}  # Store all setting variables
        self.current_mode = self.load_current_mode()

        # Load backend settings for debug logging
        try:
            backend_settings_file = Path(__file__).parent.parent / "backend_settings.json"
            if backend_settings_file.exists():
                with open(backend_settings_file, 'r') as f:
                    self.backend_settings = json.load(f)
            else:
                self.backend_settings = {}
        except Exception as e:
            log_message(f"ADV_SETTINGS: Could not load backend_settings: {e}")
            self.backend_settings = {}

    def create_ui(self):
        """Create the advanced settings UI"""
        log_message("ADV_SETTINGS: Creating UI with 37 systems...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Header
        self.parent.rowconfigure(1, weight=1)  # Scrollable content
        self.parent.rowconfigure(2, weight=0)  # Buttons

        # Header
        self.create_header()

        # Scrollable content area
        self.create_scrollable_content()

        # Bottom buttons
        self.create_button_bar()

        log_message("ADV_SETTINGS: UI created successfully")

    def load_current_mode(self):
        """Load current mode from mode_settings.json"""
        if self.mode_settings_file.exists():
            try:
                with open(self.mode_settings_file, 'r') as f:
                    mode_settings = json.load(f)
                    current_mode = mode_settings.get('current_mode', 'smart')
                    log_message(f"ADV_SETTINGS: Current mode loaded: {current_mode}")
                    return current_mode
            except Exception as e:
                log_message(f"ADV_SETTINGS ERROR: Failed to load mode: {e}")
        return 'smart'  # Default to smart mode

    def get_mode_display_name(self, mode):
        """Get display name for mode"""
        mode_names = {
            'standard': '⚙️ Standard',
            'fast': '🚀 Fast',
            'smart': '🧠 Smart',
            'think': '🤔 Think'
        }
        return mode_names.get(mode, mode.title())

    def is_system_enabled_by_mode(self, system_key):
        """Check if a system should be enabled based on current mode"""
        mode_config = self.MODE_ADVANCED_MAPPINGS.get(self.current_mode, {})
        enabled_systems = mode_config.get('enabled_systems', [])
        return system_key in enabled_systems

    def is_system_controlled_by_mode(self, system_key):
        """Check if a system is controlled by any mode (should be disabled in UI)"""
        for mode, config in self.MODE_ADVANCED_MAPPINGS.items():
            if system_key in config.get('enabled_systems', []):
                return True
        return False

    def create_header(self):
        """Create header section with mode indicator"""
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        # Title
        ttk.Label(
            header_frame,
            text="⚙️ Advanced Settings (37 Systems)",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Mode indicator
        mode_display = self.get_mode_display_name(self.current_mode)
        self.mode_indicator_label = ttk.Label(
            header_frame,
            text=f"Active Mode: {mode_display}",
            font=("Arial", 10, "bold"),
            foreground='#00ff00',
            style='CategoryPanel.TLabel'
        )
        self.mode_indicator_label.pack(side=tk.LEFT, padx=(0, 10))

        # Info label
        enabled_count = len(self.MODE_ADVANCED_MAPPINGS.get(self.current_mode, {}).get('enabled_systems', []))
        ttk.Label(
            header_frame,
            text=f"({enabled_count} systems enabled by mode)",
            font=("Arial", 9),
            foreground='#888888',
            style='Config.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Buttons on right
        ttk.Button(
            header_frame,
            text="🔄 Reset All",
            command=self.reset_to_defaults,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            header_frame,
            text="⬇ Collapse All",
            command=self.collapse_all,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

    def create_scrollable_content(self):
        """Create scrollable content area with collapsible sections"""
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        canvas = tk.Canvas(
            container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview
        )
        self.scroll_frame = ttk.Frame(canvas, style='Category.TFrame')

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling
        self.bind_mousewheel_to_canvas(canvas)

        # Store collapsible frames for collapse_all
        self.collapsible_frames = []

        # Create all sections organized by category
        self.create_parsing_category()
        self.create_tool_intelligence_category()
        self.create_context_rag_category()
        self.create_quality_verification_category()
        self.create_workflow_project_category()
        self.create_model_management_category()
        self.create_security_policy_category()
        self.create_integrations_category()

    # ========== CATEGORY 1: Parsing & Translation ==========
    def create_parsing_category(self):
        """🔄 Format Translation & JSON Repair"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="📋 CATEGORY 1: Parsing & Translation",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Format Translation
        self.create_system_section(
            category_frame,
            "format_translation",
            "🔄 Format Translation",
            "Detects and translates alternate tool call formats"
        )

        # JSON Repair
        self.create_system_section(
            category_frame,
            "json_repair",
            "🔧 JSON Auto-Repair",
            "Repairs malformed JSON in responses"
        )

    # ========== CATEGORY 2: Tool Intelligence ==========
    def create_tool_intelligence_category(self):
        """🛠️ Tool Intelligence & Orchestration"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🛠️ CATEGORY 2: Tool Intelligence & Orchestration",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Schema Validation
        self.create_system_section(
            category_frame,
            "schema_validation",
            "✓ Schema Validation",
            "Validates tool arguments before execution"
        )

        # Tool Orchestrator
        self.create_system_section(
            category_frame,
            "tool_orchestrator",
            "🎭 Tool Orchestrator",
            "Intelligent tool execution with risk assessment"
        )

        # Intelligent Router
        self.create_system_section(
            category_frame,
            "intelligent_routing",
            "🧭 Intelligent Router",
            "Routes user intents to appropriate tools"
        )

        # Confirmation Gates
        self.create_system_section(
            category_frame,
            "confirmation_gates",
            "🚦 Confirmation Gates",
            "User confirmation for risky operations"
        )

    # ========== CATEGORY 3: Context & RAG ==========
    def create_context_rag_category(self):
        """🧠 Context Management & RAG Optimization"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🧠 CATEGORY 3: Context Management & RAG",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Context Scoring
        self.create_system_section(
            category_frame,
            "context_scoring",
            "📊 Context Scorer",
            "Scores chat history quality and relevance"
        )

        # Pre-RAG Optimizer
        self.create_system_section(
            category_frame,
            "pre_rag_optimizer",
            "🎯 Pre-RAG Optimizer",
            "Optimizes context before API calls"
        )

        # RAG Feedback Engine
        self.create_system_section(
            category_frame,
            "rag_feedback",
            "🔁 RAG Feedback Engine",
            "Feedback loop for RAG quality improvement"
        )

        # MVCO Engine
        self.create_system_section(
            category_frame,
            "mvco_engine",
            "🔀 Multi-Version Context Optimizer",
            "Manages multiple context versions"
        )

    # ========== CATEGORY 4: Quality & Verification ==========
    def create_quality_verification_category(self):
        """✨ Quality Assurance & Verification"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="✨ CATEGORY 4: Quality & Verification",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Verification Engine
        self.create_system_section(
            category_frame,
            "verification",
            "🔍 Verification Engine",
            "Verifies tool outputs with auto-fix"
        )

        # Quality Assurance
        self.create_system_section(
            category_frame,
            "quality_assurance",
            "⭐ Quality Assurance",
            "Assesses response quality"
        )

        # Master Quality System
        self.create_system_section(
            category_frame,
            "master_quality",
            "👑 Master Quality System",
            "Overarching quality management"
        )

        # Quality Recovery
        self.create_system_section(
            category_frame,
            "quality_recovery",
            "🚑 Quality Recovery Engine",
            "Recovers from quality failures"
        )

    # ========== CATEGORY 5: Workflow & Project ==========
    def create_workflow_project_category(self):
        """🏗️ Workflow & Project Management"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🏗️ CATEGORY 5: Workflow & Project Management",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Adaptive Workflow
        self.create_system_section(
            category_frame,
            "adaptive_workflow",
            "🔄 Adaptive Workflow Engine",
            "Dynamically adapts workflows"
        )

        # Agentic Project
        self.create_system_section(
            category_frame,
            "agentic_project",
            "🤖 Agentic Project System",
            "Multi-agent project orchestration"
        )

        # Workflow Optimizer
        self.create_system_section(
            category_frame,
            "workflow_optimizer",
            "⚡ Workflow Optimizer",
            "Optimizes workflow execution"
        )

        # Project Store
        self.create_system_section(
            category_frame,
            "project_store",
            "💾 Project Store",
            "Project state persistence"
        )

        # Session Manager
        self.create_system_section(
            category_frame,
            "session_manager",
            "📝 Session Manager",
            "Session state and restoration"
        )

    # ========== CATEGORY 6: Model & Resource Management ==========
    def create_model_management_category(self):
        """🎛️ Model & Resource Management"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🎛️ CATEGORY 6: Model & Resource Management",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Resource Management
        self.create_system_section(
            category_frame,
            "resource_management",
            "💻 Resource Management",
            "CPU, memory, and token limits"
        )

        # Time Slicing
        self.create_system_section(
            category_frame,
            "time_slicing",
            "⏱️ Time Slicer",
            "Token-by-token generation control"
        )

        # Model Optimizer
        self.create_system_section(
            category_frame,
            "model_optimizer",
            "🎚️ Model Optimizer",
            "Optimizes model parameters"
        )

        # Model Selector
        self.create_system_section(
            category_frame,
            "model_selector",
            "🎯 Model Selector",
            "Intelligent model selection"
        )

        # Quant Manager
        self.create_system_section(
            category_frame,
            "quant_manager",
            "📦 Quantization Manager",
            "Manages model quantization"
        )

        # Performance Benchmark
        self.create_system_section(
            category_frame,
            "performance_benchmark",
            "📈 Performance Benchmark",
            "Performance monitoring and metrics"
        )

    # ========== CATEGORY 7: Security & Policy ==========
    def create_security_policy_category(self):
        """🔒 Security & Policy Management"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🔒 CATEGORY 7: Security & Policy",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # Hardening Manager
        self.create_system_section(
            category_frame,
            "hardening_manager",
            "🛡️ Hardening Manager",
            "Security hardening and scanning"
        )

        # Complexity Analyzer
        self.create_system_section(
            category_frame,
            "complexity_analyzer",
            "📐 Complexity Analyzer",
            "Analyzes code complexity"
        )

        # Atomic Writer
        self.create_system_section(
            category_frame,
            "atomic_writer",
            "⚛️ Atomic Writer",
            "Safe atomic file operations"
        )

        # Auto Policy
        self.create_system_section(
            category_frame,
            "auto_policy",
            "🤖 Auto Policy Generator",
            "Automatic policy generation"
        )

        # Command Policy
        self.create_system_section(
            category_frame,
            "command_policy",
            "📜 Command Policy Manager",
            "Command execution policies"
        )

        # Version Manager
        self.create_system_section(
            category_frame,
            "version_manager",
            "🏷️ Version Manager",
            "Version control management"
        )

    # ========== CATEGORY 8: External Integrations ==========
    def create_integrations_category(self):
        """🔌 External Integrations"""
        category_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🔌 CATEGORY 8: External Integrations",
            style='TLabelframe'
        )
        category_frame.pack(fill=tk.X, padx=5, pady=5)

        # MCP Integration
        self.create_system_section(
            category_frame,
            "mcp_integration",
            "🔗 MCP Integration",
            "Model Context Protocol client"
        )

        # MCP Server
        self.create_system_section(
            category_frame,
            "mcp_server",
            "🖥️ MCP Server",
            "MCP server wrapper"
        )

        # LangChain Adapter
        self.create_system_section(
            category_frame,
            "langchain_adapter",
            "🦜 LangChain Adapter",
            "LangChain integration"
        )

        # Instant Hooks
        self.create_system_section(
            category_frame,
            "instant_hooks",
            "⚡ Instant Hook Engine",
            "Real-time event hooks"
        )

        # Ollama Direct Client
        self.create_system_section(
            category_frame,
            "ollama_direct",
            "🦙 Ollama Direct Client",
            "Direct Ollama client (vs curl)"
        )

    def create_system_section(self, parent, key, title, description):
        """Create a collapsible section for a system"""
        collapsible = CollapsibleFrame(parent, title, style='Category.TFrame')
        collapsible.pack(fill=tk.X, padx=5, pady=2)
        self.collapsible_frames.append(collapsible)

        # Check if controlled by mode
        is_mode_controlled = self.is_system_controlled_by_mode(key)
        is_mode_enabled = self.is_system_enabled_by_mode(key)

        # Enable checkbox
        enabled_var = tk.BooleanVar(
            value=self.settings.get(key, {}).get('enabled', False)
        )
        self.setting_vars[f"{key}_enabled"] = enabled_var

        # Add mode indicator if controlled by mode
        checkbox_text = f"✓ Enable - {description}"
        if is_mode_controlled:
            if is_mode_enabled:
                checkbox_text = f"🔒 ENABLED BY MODE - {description}"
            else:
                checkbox_text = f"🔒 Controlled by Mode - {description}"

        enable_cb = ttk.Checkbutton(
            collapsible.content,
            text=checkbox_text,
            variable=enabled_var,
            style='TCheckbutton',
            state='disabled' if is_mode_controlled else 'normal'
        )
        enable_cb.pack(anchor=tk.W, padx=5, pady=5)

        # Set checkbox value based on mode if controlled
        if is_mode_controlled:
            enabled_var.set(is_mode_enabled)

        # Add mode info label if controlled
        if is_mode_controlled:
            mode_info_text = f"ℹ️ This system is automatically configured by {self.get_mode_display_name(self.current_mode)} mode"
            ttk.Label(
                collapsible.content,
                text=mode_info_text,
                font=("Arial", 8),
                foreground='#6699cc',
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=5, pady=(0, 5))

        # Create settings for this system
        settings_frame = ttk.Frame(collapsible.content, style='Category.TFrame')
        settings_frame.pack(fill=tk.X, padx=15, pady=5)

        # Load system-specific settings
        system_settings = self.settings.get(key, {})
        for setting_key, value in system_settings.items():
            if setting_key == 'enabled':
                continue

            self.create_setting_widget(settings_frame, key, setting_key, value, is_mode_controlled)

    def create_setting_widget(self, parent, system_key, setting_key, value, is_mode_controlled=False):
        """Create appropriate widget for a setting based on its type"""

        # Special handling for nested dicts - create collapsible subsection
        if isinstance(value, dict) and len(value) > 0:
            # Check if it's a nested dict with string/numeric values (not another system config)
            is_nested_config = all(isinstance(v, (str, int, float, bool, type(None))) for v in value.values())

            if is_nested_config:
                # Create collapsible frame for nested dict
                nested_frame = CollapsibleFrame(parent, setting_key.replace('_', ' ').title())
                nested_frame.pack(fill=tk.X, pady=2)
                self.collapsible_frames.append(nested_frame)

                # Create widget for each nested key-value pair
                for nested_key, nested_value in value.items():
                    self.create_nested_setting_widget(
                        nested_frame.content,
                        system_key,
                        setting_key,
                        nested_key,
                        nested_value
                    )

                if self.backend_settings.get('enable_debug_logging', False):
                    log_message(f"DEBUG ADV_SETTINGS: Created nested dict UI for {system_key}.{setting_key} with {len(value)} items")
                return

        # Standard widget creation for non-nested settings
        row_frame = ttk.Frame(parent, style='Category.TFrame')
        row_frame.pack(fill=tk.X, pady=2)

        # Label
        label_text = setting_key.replace('_', ' ').title()
        ttk.Label(
            row_frame,
            text=f"{label_text}:",
            style='Config.TLabel',
            width=30
        ).pack(side=tk.LEFT, padx=(0, 10))

        var_key = f"{system_key}_{setting_key}"

        # Widget based on value type
        if isinstance(value, bool):
            var = tk.BooleanVar(value=value)
            self.setting_vars[var_key] = var
            ttk.Checkbutton(
                row_frame,
                variable=var,
                style='TCheckbutton'
            ).pack(side=tk.LEFT)

        elif isinstance(value, (int, float)):
            var = tk.StringVar(value=str(value))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=20)
            entry.pack(side=tk.LEFT)

        elif isinstance(value, str):
            var = tk.StringVar(value=value)
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT)

        elif isinstance(value, list):
            var = tk.StringVar(value=", ".join(map(str, value)))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT)

        elif isinstance(value, dict):
            # Empty dict or non-standard nested structure - use JSON string
            var = tk.StringVar(value=json.dumps(value))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT)

        else:
            var = tk.StringVar(value=str(value))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT)

    def create_nested_setting_widget(self, parent, system_key, parent_setting_key, nested_key, nested_value):
        """Create widget for a nested dict item"""
        row_frame = ttk.Frame(parent, style='Category.TFrame')
        row_frame.pack(fill=tk.X, pady=2)

        # Label with indentation
        label_text = nested_key.replace('_', ' ').title()
        ttk.Label(
            row_frame,
            text=f"  {label_text}:",
            style='Config.TLabel',
            width=28
        ).pack(side=tk.LEFT, padx=(10, 10))

        # Variable key format: system_parentsetting_nestedkey
        var_key = f"{system_key}_{parent_setting_key}_{nested_key}"

        # Widget based on nested value type
        if isinstance(nested_value, bool):
            var = tk.BooleanVar(value=nested_value)
            self.setting_vars[var_key] = var
            ttk.Checkbutton(
                row_frame,
                variable=var,
                style='TCheckbutton'
            ).pack(side=tk.LEFT)

        elif isinstance(nested_value, (int, float)):
            var = tk.StringVar(value=str(nested_value))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=20)
            entry.pack(side=tk.LEFT)

        elif isinstance(nested_value, str):
            var = tk.StringVar(value=nested_value)
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=45)
            entry.pack(side=tk.LEFT)

        elif nested_value is None:
            var = tk.StringVar(value="null")
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=20)
            entry.pack(side=tk.LEFT)

        else:
            var = tk.StringVar(value=str(nested_value))
            self.setting_vars[var_key] = var
            entry = ttk.Entry(row_frame, textvariable=var, width=40)
            entry.pack(side=tk.LEFT)

    def collapse_all(self):
        """Collapse all sections"""
        for frame in self.collapsible_frames:
            if frame.is_expanded.get():
                frame.toggle()

    def create_button_bar(self):
        """Create bottom button bar with mode-specific save"""
        btn_frame = ttk.Frame(self.parent, style='Category.TFrame')
        btn_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        # Mode-specific save button
        mode_display = self.get_mode_display_name(self.current_mode)
        ttk.Button(
            btn_frame,
            text=f"💾 Save Advanced Settings ({mode_display})",
            command=self.save_mode_specific_settings,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="🔄 Refresh",
            command=self.refresh,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        # Info label
        ttk.Label(
            btn_frame,
            text="Mode-controlled systems are automatically managed",
            font=("Arial", 8),
            foreground='#888888',
            style='Config.TLabel'
        ).pack(side=tk.RIGHT, padx=5)

    def load_settings(self):
        """Load advanced settings from JSON"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("ADV_SETTINGS: Settings loaded")
                    return settings
            except Exception as e:
                log_message(f"ADV_SETTINGS ERROR: Failed to load settings: {e}")

        # Return default structure if file doesn't exist
        return {}

    def save_mode_specific_settings(self):
        """Save advanced settings with mode configuration applied"""
        try:
            # First, apply mode-based enabled/disabled states
            self.apply_mode_to_settings()

            # Then save all settings
            self.save_settings()

        except Exception as e:
            log_message(f"ADV_SETTINGS ERROR: Failed to save mode-specific settings: {e}")
            messagebox.showerror("Error", f"Failed to save mode-specific settings: {e}")

    def apply_mode_to_settings(self):
        """Apply current mode configuration to advanced settings"""
        mode_config = self.MODE_ADVANCED_MAPPINGS.get(self.current_mode, {})
        enabled_systems = mode_config.get('enabled_systems', [])

        # Update enabled state for all mode-controlled systems
        for system_key in self.MODE_ADVANCED_MAPPINGS.get('think', {}).get('enabled_systems', []):
            var_key = f"{system_key}_enabled"
            if var_key in self.setting_vars:
                # Set based on whether it's in current mode's enabled list
                should_enable = system_key in enabled_systems
                self.setting_vars[var_key].set(should_enable)

        # Apply resource management profile if applicable
        if 'resource_management' in enabled_systems:
            profile = mode_config.get('profile', 'balanced')
            resource_percentage = mode_config.get('resource_percentage', 50)

            # Update resource management variables
            if 'resource_management_profile' in self.setting_vars:
                self.setting_vars['resource_management_profile'].set(profile)
            if 'resource_management_resources_percentage' in self.setting_vars:
                self.setting_vars['resource_management_resources_percentage'].set(str(resource_percentage))

        log_message(f"ADV_SETTINGS: Applied {self.current_mode} mode configuration ({len(enabled_systems)} systems enabled)")

    def save_settings(self):
        """Save all settings to JSON"""
        try:
            # Build settings dict from all variables
            new_settings = {}
            nested_dict_items = {}  # Track nested dict items separately

            for var_key, var in self.setting_vars.items():
                parts = var_key.split('_')
                if len(parts) < 2:
                    continue

                # Check if this is a nested dict item (has 3+ parts)
                if len(parts) >= 3:
                    # Try to identify nested structure: system_parentsetting_nestedkey
                    # We need to check if middle part is a known nested dict setting
                    system_key = parts[0]
                    potential_parent = '_'.join(parts[1:-1])
                    nested_key = parts[-1]

                    # Store for later reconstruction
                    nest_key = f"{system_key}_{potential_parent}"
                    if nest_key not in nested_dict_items:
                        nested_dict_items[nest_key] = {}

                    # Get value based on variable type
                    if isinstance(var, tk.BooleanVar):
                        nested_dict_items[nest_key][nested_key] = var.get()
                    elif isinstance(var, tk.StringVar):
                        value_str = var.get()
                        # Handle null
                        if value_str == "null":
                            nested_dict_items[nest_key][nested_key] = None
                        # Try to parse as number
                        elif value_str.replace('.', '').replace('-', '').isdigit():
                            try:
                                if '.' in value_str:
                                    nested_dict_items[nest_key][nested_key] = float(value_str)
                                else:
                                    nested_dict_items[nest_key][nested_key] = int(value_str)
                            except:
                                nested_dict_items[nest_key][nested_key] = value_str
                        else:
                            nested_dict_items[nest_key][nested_key] = value_str
                    continue

                # Standard setting (2 parts)
                system_key = parts[0]
                setting_key = '_'.join(parts[1:])

                if system_key not in new_settings:
                    new_settings[system_key] = {}

                # Get value based on variable type
                if isinstance(var, tk.BooleanVar):
                    new_settings[system_key][setting_key] = var.get()
                elif isinstance(var, tk.StringVar):
                    value_str = var.get()
                    # Try to parse as JSON for dicts/lists
                    if value_str.startswith('{') or value_str.startswith('['):
                        try:
                            new_settings[system_key][setting_key] = json.loads(value_str)
                        except:
                            new_settings[system_key][setting_key] = value_str
                    # Try to parse as number
                    elif value_str.replace('.', '').replace('-', '').isdigit():
                        try:
                            if '.' in value_str:
                                new_settings[system_key][setting_key] = float(value_str)
                            else:
                                new_settings[system_key][setting_key] = int(value_str)
                        except:
                            new_settings[system_key][setting_key] = value_str
                    # Parse comma-separated lists
                    elif ',' in value_str:
                        new_settings[system_key][setting_key] = [x.strip() for x in value_str.split(',')]
                    else:
                        new_settings[system_key][setting_key] = value_str

            # Reconstruct nested dicts
            for nest_key, nested_items in nested_dict_items.items():
                parts = nest_key.split('_', 1)
                if len(parts) == 2:
                    system_key, parent_setting = parts
                    if system_key in new_settings:
                        new_settings[system_key][parent_setting] = nested_items

            # Save to file
            with open(self.settings_file, 'w') as f:
                json.dump(new_settings, f, indent=2)

            log_message("ADV_SETTINGS: Settings saved successfully")
            if self.backend_settings.get('enable_debug_logging', False):
                log_message(f"DEBUG ADV_SETTINGS: Saved {len(new_settings)} systems, reconstructed {len(nested_dict_items)} nested dicts")
            messagebox.showinfo("Success", "Advanced settings saved successfully!")

            # Refresh parent tab
            if hasattr(self.parent_tab, 'refresh'):
                self.parent_tab.refresh()

        except Exception as e:
            log_message(f"ADV_SETTINGS ERROR: Failed to save settings: {e}")
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def reset_to_defaults(self):
        """Reset all settings to defaults (all disabled)"""
        if messagebox.askyesno("Reset Settings", "Reset all advanced settings to defaults (all disabled)?"):
            for var_key, var in self.setting_vars.items():
                if var_key.endswith('_enabled'):
                    var.set(False)

            log_message("ADV_SETTINGS: Reset to defaults")
            messagebox.showinfo("Reset", "All advanced settings disabled. Click Save to apply.")

    def on_mode_changed(self, new_mode):
        """Called when mode changes from Mode tab"""
        log_message(f"ADV_SETTINGS: Mode changed to {new_mode}")
        self.current_mode = new_mode
        self.refresh()

    def refresh(self):
        """Refresh the settings UI"""
        log_message("ADV_SETTINGS: Refreshing...")
        self.settings = self.load_settings()
        self.current_mode = self.load_current_mode()
        # Recreate UI
        for widget in self.parent.winfo_children():
            widget.destroy()
        self.setting_vars.clear()
        self.collapsible_frames.clear()
        self.create_ui()
