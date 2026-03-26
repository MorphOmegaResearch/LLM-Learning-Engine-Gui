#!/usr/bin/env python3
"""
TextEnhanceAI - Enhanced text editor with LLM integration

Features:
- Text editing with Ollama or Claude AI models
- Real-time diff display with color-coded changes
- Document generation mode
- Chat interface for quick questions
- File management and inventory system
- Automatic logging to Proposals folder

Setup:
1. For Ollama models: Install Ollama and pull models (e.g., ollama pull llama3.1:8b)
2. For Claude models: Set ANTHROPIC_API_KEY environment variable
   export ANTHROPIC_API_KEY=your_api_key_here
3. Run: python3 TextEnhanceAI.py
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog, ttk
import difflib
import re
from datetime import datetime
import os
import threading
import subprocess
import shutil
import time
import json

try:
    from ollama import Client
    try:
        # Prefer top-level list API when available
        from ollama import list as ollama_list, ListResponse
    except Exception:
        ollama_list = None
        ListResponse = None
except ImportError:
    print("Please install the ollama package (pip install ollama).")
    Client = None
    ollama_list = None
    ListResponse = None

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    print("Anthropic package not installed. Claude models will not be available.")
    Anthropic = None
    ANTHROPIC_AVAILABLE = False

# --------------
# Configuration
# --------------
INVENTORY_BASE = "Inventory"
INVENTORY_PROPOSALS = os.path.join(INVENTORY_BASE, "Proposals")
DEFAULT_CHAT_WARMUP = 120  # 2 minutes in seconds
CONFIG_FILE = "textenhance_config.json"

# Claude models available via API
CLAUDE_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-3-7-20250219",
    "claude-opus-4-5-20251101",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022"
]

# Possible Claude Code CLI credential locations
CLI_CREDENTIAL_PATHS = [
    os.path.expanduser("~/.config/claude-code/auth.json"),
    os.path.expanduser("~/.claude-code/auth.json"),
    os.path.expanduser("~/.config/anthropic/auth.json"),
]

# --------------
# Configurable prompts for each button
# --------------
PROMPTS = {
    "Grammar": "Fix grammar issues without altering the meaning.",
    "Proofread": "Proofread the text comprehensively, correcting errors and improving readability.",
    "Natural": "Refine awkward phrasing to make the text feel natural while preserving the original meaning.",
    "Streamline": "Remove unnecessary elements, clarify the message, and ensure coherence and ease of understanding.",
    "Awkward": "Fix only awkward or poorly written sentences without making other changes.",
    "Rewrite": "Rewrite the text to improve clarity, flow, and overall readability.",
    "Concise": "Make the text more concise by removing redundancy and unnecessary content.",
    "Polish": "Refine awkward words or phrases to give the text a polished and professional tone.",
    "Improve": "Enhance the text by proofreading and improving its clarity, flow, and coherence.",
}

# --------------
# Agent/Tool configuration for orchestration
# --------------
AGENT_TOOLS = {
    "Grammar": {"prompt": PROMPTS["Grammar"], "type": "text_edit", "function": "run_llm_edit"},
    "Proofread": {"prompt": PROMPTS["Proofread"], "type": "text_edit", "function": "run_llm_edit"},
    "Natural": {"prompt": PROMPTS["Natural"], "type": "text_edit", "function": "run_llm_edit"},
    "Streamline": {"prompt": PROMPTS["Streamline"], "type": "text_edit", "function": "run_llm_edit"},
    "Awkward": {"prompt": PROMPTS["Awkward"], "type": "text_edit", "function": "run_llm_edit"},
    "Rewrite": {"prompt": PROMPTS["Rewrite"], "type": "text_edit", "function": "run_llm_edit"},
    "Concise": {"prompt": PROMPTS["Concise"], "type": "text_edit", "function": "run_llm_edit"},
    "Polish": {"prompt": PROMPTS["Polish"], "type": "text_edit", "function": "run_llm_edit"},
    "Improve": {"prompt": PROMPTS["Improve"], "type": "text_edit", "function": "run_llm_edit"},
    "Translate": {"prompt": "Translate text to target language", "type": "text_edit", "function": "run_translate_prompt"},
    "Custom": {"prompt": "User-defined custom prompt", "type": "text_edit", "function": "run_custom_prompt"},
    "Orchestrator": {"prompt": "You are Claude, an AI orchestrator helping coordinate and execute tasks. You can analyze code, review changes, debug issues, and provide guidance.", "type": "meta", "function": "orchestrate"}
}

# --------------
# Custom prompt helper (avoid private tkinter APIs)
# --------------
def ask_custom_string(title, prompt, parent=None):
    """Ask for a string using the standard dialog."""
    return simpledialog.askstring(title, prompt, parent=parent)


# --------------
# Simple Tooltip class
# --------------
class ToolTip:
    """
    A simple tooltip for tkinter widgets.
    Usage: create_tooltip(widget, text='Hello!')
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.x = self.y = 0

        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.showtip()

    def leave(self, event=None):
        self.hidetip()

    def showtip(self):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() - 45
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # removes the window decorations
        tw.geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", "8", "normal")
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


def create_tooltip(widget, text):
    """Helper to attach a tooltip with given text to a widget."""
    ToolTip(widget, text)


# --------------
# Utility functions
# --------------
def ensure_inventory_dirs():
    """Create inventory directories if they don't exist."""
    os.makedirs(INVENTORY_BASE, exist_ok=True)
    os.makedirs(INVENTORY_PROPOSALS, exist_ok=True)


def load_config():
    """Load configuration from JSON file."""
    if os.path.exists(CONFIG_FILE):
        try:
            import json
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
    return {}


def save_config(config):
    """Save configuration to JSON file."""
    try:
        import json
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")


def find_claude_cli_credentials():
    """Try to find Claude Code CLI credentials."""
    import json
    for path in CLI_CREDENTIAL_PATHS:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    # Look for API key in various possible formats
                    if 'api_key' in data:
                        return data['api_key']
                    if 'apiKey' in data:
                        return data['apiKey']
                    if 'anthropic_api_key' in data:
                        return data['anthropic_api_key']
                    # Check for session token
                    if 'session_token' in data:
                        return data['session_token']
                    if 'sessionToken' in data:
                        return data['sessionToken']
            except Exception as e:
                print(f"Could not read {path}: {e}")
    return None


def get_anthropic_api_key():
    """Get Anthropic API key from various sources."""
    # 1. Check environment variable
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key, "environment variable"

    # 2. Check local config file
    config = load_config()
    if 'anthropic_api_key' in config:
        return config['anthropic_api_key'], "local config"

    # 3. Try to find Claude Code CLI credentials
    cli_key = find_claude_cli_credentials()
    if cli_key:
        return cli_key, "Claude Code CLI"

    return None, None


def detect_file_manager():
    """Detect the system file manager (prefer thunar, fallback to xdg-open)."""
    file_managers = ['thunar', 'nautilus', 'dolphin', 'pcmanfm', 'caja', 'nemo']
    for fm in file_managers:
        if shutil.which(fm):
            return fm
    # Fallback to xdg-open
    if shutil.which('xdg-open'):
        return 'xdg-open'
    return None


def open_file_browser(path="."):
    """Open the native file browser at the specified path."""
    fm = detect_file_manager()
    if fm:
        try:
            subprocess.Popen([fm, path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file manager: {e}")
    else:
        messagebox.showerror("Error", "No file manager found on system.")


# --------------
# Main application class
# --------------
class EditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TextEnhanceAI Editor with Local LLM - V 0.20 Enhanced")

        # ----------------------
        # 1) Set starting size and use it as the minimum
        # ----------------------
        self.root.geometry("800x600")
        self.root.minsize(800, 600)

        # 2) Initialize widgets and buttons

        # Ollama client (make sure you've installed and are running your local LLM server)
        self.ollama_client = Client() if Client else None
        self.model_name = os.getenv("TEAI_MODEL", "llama3.1:8b")

        # Anthropic client for Claude models
        self.anthropic_client = None
        self.anthropic_api_key_source = None
        if ANTHROPIC_AVAILABLE:
            api_key, source = get_anthropic_api_key()
            if api_key:
                self.anthropic_client = Anthropic(api_key=api_key)
                self.anthropic_api_key_source = source
                print(f"✓ Claude API key found from: {source}")
            else:
                print("No Claude API key found. Use 'Set API Key' button to configure.")

        # Top bar: model selection
        top_bar = tk.Frame(self.root)
        top_bar.pack(fill=tk.X, padx=5, pady=5)
        model_label = tk.Label(top_bar, text="Model:")
        model_label.pack(side=tk.LEFT, padx=(0, 2))
        self.model_var = tk.StringVar(value=self.model_name)
        self.model_optionmenu = tk.OptionMenu(top_bar, self.model_var, self.model_name)
        self.model_optionmenu.pack(side=tk.LEFT, padx=(0, 6))
        refresh_btn = tk.Button(top_bar, text="Refresh", command=self.populate_model_menu)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Claude API key button
        api_key_btn = tk.Button(top_bar, text="Set API Key", command=self.manage_api_key, fg='blue')
        api_key_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(api_key_btn, "Configure Claude API key for Claude models")

        # System Prompt Editor button
        sys_prompt_btn = tk.Button(top_bar, text="System Prompt", command=self.edit_system_prompt, fg='darkgreen')
        sys_prompt_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(sys_prompt_btn, "Edit system prompt for chat mode")

        # Debug Mode toggle
        self.debug_mode = tk.BooleanVar(value=True)  # On by default
        debug_check = tk.Checkbutton(top_bar, text="Debug", variable=self.debug_mode, fg='orange')
        debug_check.pack(side=tk.LEFT, padx=5)
        create_tooltip(debug_check, "Enable debug mode for runtime activity tracking and hover code snippets")

        # Scope Inspector toggle (microscope mode)
        self.scope_inspector_mode = tk.BooleanVar(value=False)
        scope_check = tk.Checkbutton(
            top_bar,
            text="Scope Inspector",
            variable=self.scope_inspector_mode,
            command=self.toggle_scope_inspector,
            fg='purple'
        )
        scope_check.pack(side=tk.LEFT, padx=5)
        create_tooltip(scope_check, "Enable live hover inspection - microscope for code analysis")

        # Activity tracking log (for debug mode)
        self.activity_log = []
        self.cached_scope_results = {}  # Cache for scope analysis results
        self.scope_tooltip = None  # Tooltip window for scope inspector

        # File operations
        tk.Button(top_bar, text="Load", command=self.load_file).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        tk.Button(top_bar, text="Inventory", command=self.open_inventory).pack(side=tk.LEFT, padx=2)

        # Load models initially
        self.populate_model_menu()

        # Current file tracking
        self.current_file = None

        # Doc generation options frame
        doc_frame = tk.Frame(self.root)
        doc_frame.pack(fill=tk.X, padx=5, pady=2)

        self.doc_gen_mode = tk.BooleanVar(value=False)
        tk.Checkbutton(doc_frame, text="Doc Generation Mode", variable=self.doc_gen_mode).pack(side=tk.LEFT, padx=5)

        tk.Label(doc_frame, text="Format:").pack(side=tk.LEFT, padx=5)
        self.doc_format = tk.StringVar(value="md")
        for fmt in ["md", "txt", "py"]:
            tk.Radiobutton(doc_frame, text=fmt.upper(), variable=self.doc_format, value=fmt).pack(side=tk.LEFT)

        # Create tabbed notebook interface
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # --- Editor Tab ---
        self.editor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_tab, text="Editor")
        self.setup_editor_tab()

        # --- Chat Tab ---
        self.chat_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_tab, text="Chat")
        self.setup_chat_tab()

        # --- Projects/Stash Tab ---
        self.projects_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.projects_tab, text="Stash")
        self.setup_stash_tab()

        # --- Debug Tab ---
        self.debug_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.debug_tab, text="Debug")
        self.setup_debug_tab()

        # Frame for buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        self.btn_frame = btn_frame

        # Orchestrator section (LEFT side with On/Off toggle)
        orchestrator_frame = tk.LabelFrame(btn_frame, text="Orchestrator", fg='purple', padx=5, pady=2)
        orchestrator_frame.pack(side=tk.LEFT, padx=(0, 10))

        # Orchestrator On/Off toggle
        self.orchestrator_enabled = tk.BooleanVar(value=False)
        orchestrator_toggle = tk.Checkbutton(
            orchestrator_frame,
            text="On",
            variable=self.orchestrator_enabled,
            command=self.toggle_orchestrator
        )
        orchestrator_toggle.pack(side=tk.LEFT, padx=2)
        create_tooltip(orchestrator_toggle, "Enable Orchestrator mode - routes to orchestrator_config")

        # Orchestrator button
        orchestrator_btn = tk.Button(
            orchestrator_frame,
            text="Configure",
            command=self.open_orchestrator_window,
            fg='purple'
        )
        orchestrator_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(orchestrator_btn, "Open orchestrator configuration window")

        # Separator
        separator = tk.Frame(btn_frame, width=2, bg='gray', relief=tk.SUNKEN)
        separator.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Profile buttons frame
        profile_frame = tk.Frame(btn_frame)
        profile_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Create standard editing buttons
        for label in ["Grammar", "Proofread", "Natural", "Streamline",
                      "Awkward", "Rewrite", "Concise", "Polish", "Improve"]:
            b = tk.Button(
                profile_frame,
                text=label,
                command=lambda lbl=label: self.run_llm_edit(lbl)
            )
            b.pack(side=tk.LEFT, padx=2)
            # Show the prompt in a tooltip
            create_tooltip(b, PROMPTS[label])

        # Add the Translate button BEFORE the "Custom" button
        translate_btn = tk.Button(profile_frame, text="Translate", command=self.run_translate_prompt)
        translate_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(translate_btn, "Prompt user for a target language and translate the text.")

        # Button for custom prompt
        custom_btn = tk.Button(profile_frame, text="Custom", command=self.run_custom_prompt)
        custom_btn.pack(side=tk.LEFT, padx=2)
        create_tooltip(custom_btn, "Enter your own custom instruction.")

        # Quit button
        tk.Button(
            btn_frame, text="Quit", command=self.root.quit
        ).pack(side=tk.RIGHT, padx=2)

        # Frame for apply-changes options
        self.accept_reject_frame = tk.Frame(self.root)
        self.accept_reject_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # 3) Make the Accept/Reject button text colored
        tk.Button(
            self.accept_reject_frame,
            text="Accept All Changes",
            command=self.accept_all_changes,
            fg='green'
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            self.accept_reject_frame,
            text="Reject All Changes",
            command=self.reject_all_changes,
            fg='red'
        ).pack(side=tk.LEFT, padx=2)
        
        # We store the â€œdiff-annotatedâ€ version of the text in a separate place
        # so we can choose to accept or reject changes piecewise.
        self.diff_text = ""
        self.temp_html = ""  # If you want to store a temporary HTML version

        # For scratchpad logging:
        self.scratchpad_filename = None
        self.first_change_time = None

        # Chat input frame
        chat_frame = tk.Frame(self.root)
        chat_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(chat_frame, text="Chat:").pack(side=tk.LEFT, padx=2)
        self.chat_input = tk.Entry(chat_frame)
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        self.chat_input.bind('<Return>', lambda e: self.send_chat())
        tk.Button(chat_frame, text="Send", command=self.send_chat).pack(side=tk.LEFT, padx=2)
        tk.Button(chat_frame, text="Stop Chat", command=self.stop_chat, fg='red').pack(side=tk.LEFT, padx=2)
        tk.Button(chat_frame, text="Clear Chat", command=self.clear_chat).pack(side=tk.LEFT, padx=2)

        # Chat history
        self.chat_history = []
        self.chat_running = False  # Track if chat is active

        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill=tk.X, padx=5, pady=(0,5))

    # --------------
    # Tab Setup Methods
    # --------------
    def setup_editor_tab(self):
        """Create Editor tab with split pane for document editing and diff view."""
        # Create split paned window
        paned = tk.PanedWindow(self.editor_tab, orient=tk.HORIZONTAL, sashwidth=5, sashrelief=tk.RAISED)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left pane: Document editing
        left_frame = tk.LabelFrame(paned, text="Document Editor", padx=2, pady=2)
        self.text_area = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, width=40, height=20)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        # Right pane: Diff display
        right_frame = tk.LabelFrame(paned, text="Diff View", padx=2, pady=2)
        self.diff_area = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, width=40, height=20)
        self.diff_area.pack(fill=tk.BOTH, expand=True)

        paned.add(left_frame, minsize=200)
        paned.add(right_frame, minsize=200)

    def setup_chat_tab(self):
        """Create Chat tab with session history."""
        # Session/Chat display area
        session_frame = tk.LabelFrame(self.chat_tab, text="Session / Chat History", padx=2, pady=2)
        session_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.session_area = scrolledtext.ScrolledText(session_frame, wrap=tk.WORD)
        self.session_area.pack(fill=tk.BOTH, expand=True)

    def setup_stash_tab(self):
        """Create Stash tab with inventory management GUI."""
        # Try to import stash modules from organized structure
        import sys
        modules_path = os.path.join(os.path.dirname(__file__), 'modules')
        if modules_path not in sys.path:
            sys.path.insert(0, modules_path)

        try:
            from stash import stash_script_broken
            from stash.stash_script_broken import ConfigManager
            self.config_manager = ConfigManager()
            self.create_stash_gui()
        except ImportError as e:
            error_label = tk.Label(
                self.projects_tab,
                text=f"Stash functionality not available\n{e}\nPath: {modules_path}",
                font=("Arial", 12),
                fg="red"
            )
            error_label.pack(pady=20)
            self.config_manager = None

    def create_stash_gui(self):
        """Build the stash GUI interface layout."""
        # Left side: Output area
        left_frame = tk.Frame(self.projects_tab)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Label(left_frame, text="Stash Operations Output", font=("Arial", 10, "bold")).pack()
        self.stash_output_area = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, height=20)
        self.stash_output_area.pack(fill=tk.BOTH, expand=True)

        # Right side: Controls
        right_frame = tk.Frame(self.projects_tab, width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        right_frame.pack_propagate(False)

        # Inventory Management
        inv_frame = tk.LabelFrame(right_frame, text="Inventory Management", padx=5, pady=5)
        inv_frame.pack(fill=tk.X, pady=5)

        tk.Button(inv_frame, text="Add Inventory", command=self.add_inventory_ui).pack(fill=tk.X, pady=2)
        tk.Button(inv_frame, text="List Inventories", command=self.list_inventories_ui).pack(fill=tk.X, pady=2)
        tk.Button(inv_frame, text="Tag Inventory", command=self.tag_inventory_ui).pack(fill=tk.X, pady=2)
        tk.Button(inv_frame, text="Set Base Dir (-b)", command=self.set_base_dir_ui).pack(fill=tk.X, pady=2)

        # Inventory selector
        tk.Label(inv_frame, text="Select Inventory:").pack()
        self.inventory_var = tk.StringVar(value="default")
        self.inventory_dropdown = ttk.Combobox(inv_frame, textvariable=self.inventory_var, state='readonly')
        self.inventory_dropdown.pack(fill=tk.X, pady=2)
        self.populate_inventory_dropdown()

        # [Refresh] button - prominent placement
        refresh_btn = tk.Button(inv_frame, text="[Refresh] PFC + Debug",
                               command=self.refresh_inventories_ui,
                               bg='#06D6A0', fg='white',
                               font=('Arial', 9, 'bold'))
        refresh_btn.pack(fill=tk.X, pady=5)
        create_tooltip(refresh_btn, "Run Pre-Flight Check + inventory scan + debug checks")

        # Stash Operations
        stash_frame = tk.LabelFrame(right_frame, text="Stash Operations", padx=5, pady=5)
        stash_frame.pack(fill=tk.X, pady=5)

        tk.Button(stash_frame, text="Quick Stash (-s)", command=self.perform_quick_stash_ui).pack(fill=tk.X, pady=2)
        tk.Button(stash_frame, text="View Manifest (-v)", command=self.view_manifest_ui).pack(fill=tk.X, pady=2)
        tk.Button(stash_frame, text="View Lineage (-l)", command=self.perform_lineage_ui).pack(fill=tk.X, pady=2)

        # Stash selector
        tk.Label(stash_frame, text="Select Stash to Restore:").pack()
        self.stash_var = tk.StringVar()
        self.stash_dropdown = ttk.Combobox(stash_frame, textvariable=self.stash_var, state='readonly')
        self.stash_dropdown.pack(fill=tk.X, pady=2)
        tk.Button(stash_frame, text="Restore Stash", command=self.restore_stash_ui).pack(fill=tk.X, pady=2)

        # File Browser
        browser_frame = tk.LabelFrame(right_frame, text="File Browser", padx=5, pady=5)
        browser_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Button(browser_frame, text="Browse Files", command=self.browse_stash_files).pack(fill=tk.X, pady=2)
        tk.Button(browser_frame, text="Open in Editor", command=self.open_in_editor).pack(fill=tk.X, pady=2)

        # Initialize selected file tracking
        self.selected_stash_file = None

    def setup_debug_tab(self):
        """Create Debug tab with scope inspector and code quality tools."""
        # Try to import scope module from organized structure
        import sys
        modules_path = os.path.join(os.path.dirname(__file__), 'modules')
        if modules_path not in sys.path:
            sys.path.insert(0, modules_path)

        try:
            from scope.scope import ScopeAnalyzer
            self.scope_available = True
        except ImportError as e:
            error_label = tk.Label(
                self.debug_tab,
                text=f"Scope inspector not available\n{e}\nPath: {modules_path}",
                font=("Arial", 12),
                fg="red"
            )
            error_label.pack(pady=20)
            self.scope_available = False
            return

        # Control panel at top
        control_frame = tk.Frame(self.debug_tab)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # File selector
        tk.Label(control_frame, text="Inspect File:").pack(side=tk.LEFT, padx=5)
        self.debug_file_var = tk.StringVar(value="stash_script_broken.py")
        file_dropdown = ttk.Combobox(control_frame, textvariable=self.debug_file_var, width=40)
        file_dropdown['values'] = ['stash_script_broken.py', 'stash_gui.py', 'TextEnhanceAI.py']
        file_dropdown.pack(side=tk.LEFT, padx=5)

        tk.Button(control_frame, text="Analyze", command=self.analyze_file_scope).pack(side=tk.LEFT, padx=5)
        tk.Button(control_frame, text="Run Quality Checks", command=self.run_code_quality_checks).pack(side=tk.LEFT, padx=5)

        # Results area (split pane)
        paned = tk.PanedWindow(self.debug_tab, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Top: Scope analysis results
        top_frame = tk.LabelFrame(paned, text="Scope Analysis", padx=5, pady=5)
        self.scope_output = scrolledtext.ScrolledText(top_frame, wrap=tk.WORD, height=15, font=("Courier", 9))
        self.scope_output.pack(fill=tk.BOTH, expand=True)

        # Bottom: Code quality checks output
        bottom_frame = tk.LabelFrame(paned, text="Code Quality Checks", padx=5, pady=5)
        self.quality_output = scrolledtext.ScrolledText(bottom_frame, wrap=tk.WORD, height=10, font=("Courier", 9))
        self.quality_output.pack(fill=tk.BOTH, expand=True)

        paned.add(top_frame)
        paned.add(bottom_frame)

    # --------------
    # Button callbacks
    # --------------
    def run_llm_edit(self, prompt_label):
        """Send the current text + editing prompt to the LLM and display the changes inline."""
        if not self.ollama_client:
            messagebox.showerror("Error", "Ollama client not initialized or not installed.")
            return

        user_text = self.text_area.get("1.0", tk.END).strip()
        if not user_text:
            messagebox.showinfo("Info", "Please enter text to edit.")
            return

        prompt_text = PROMPTS[prompt_label]
        self.start_llm_task(user_text, prompt_text)

    def run_custom_prompt(self):
        """Prompt user for a custom instruction, then run it."""
        if not self.ollama_client:
            messagebox.showerror("Error", "Ollama client not initialized or not installed.")
            return

        user_text = self.text_area.get("1.0", tk.END).strip()
        if not user_text:
            messagebox.showinfo("Info", "Please enter text to edit.")
            return

        # Custom prompt entry (80 chars wide)
        custom_prompt = ask_custom_string("Custom Prompt", "Enter your prompt:", parent=self.root)
        if custom_prompt:
            self.start_llm_task(user_text, custom_prompt)

    def run_translate_prompt(self):
        """
        Prompt the user for the language, then translate the text to that language.
        """
        if not self.ollama_client:
            messagebox.showerror("Error", "Ollama client not initialized or not installed.")
            return

        user_text = self.text_area.get("1.0", tk.END).strip()
        if not user_text:
            messagebox.showinfo("Info", "Please enter text to translate.")
            return

        # Ask user what language they want
        language = simpledialog.askstring("Translate", "Enter the target language:", parent=self.root)
        if language:
            # Construct a translation instruction
            translate_prompt = f"Translate the text into {language}. Return only the translated text."
            self.start_llm_task(user_text, translate_prompt)

    # --------------
    # LLM + diff logic
    # --------------
    def query_llm_and_show_diff(self, user_text, instruction):
        """Backwards-compatible: start async LLM work and update UI when done."""
        self.start_llm_task(user_text, instruction)

    def is_claude_model(self, model_name):
        """Check if the given model name is a Claude model."""
        return model_name in CLAUDE_MODELS or model_name.startswith("claude-")

    def start_llm_task(self, user_text, instruction):
        """Start the LLM call in a background thread and update UI when done."""
        selected_model = (self.model_var.get() or "").strip()
        if not selected_model:
            selected_model = self.model_name

        # Check if we need Claude or Ollama
        is_claude = self.is_claude_model(selected_model)

        if is_claude and not self.anthropic_client:
            messagebox.showerror("Error", "Claude API not available. Set ANTHROPIC_API_KEY environment variable.")
            return
        elif not is_claude and not self.ollama_client:
            messagebox.showerror("Error", "Ollama client not initialized or not installed.")
            return

        def worker():
            system_prompt = (
                "You are a helpful, concise assistant that carefully edits text "
                "based on instructions. Return only the edited text, without extra commentary."
            )

            try:
                if is_claude:
                    # Call Claude API
                    response = self.anthropic_client.messages.create(
                        model=selected_model,
                        max_tokens=2048,
                        temperature=0.7,
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": f"Instruction:\n{instruction}\n\nText:\n{user_text}"}
                        ]
                    )
                    edited_text = response.content[0].text.strip()
                else:
                    # Call Ollama
                    history = [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Instruction:\n{instruction}\n\nText:\n{user_text}"}
                    ]
                    response = self.ollama_client.chat(
                        model=selected_model,
                        messages=history,
                        options={
                            'num_predict': 2048,
                            'temperature': 0.7,
                            'top_p': 0.9,
                        },
                    )
                    if "message" in response and "content" in response["message"]:
                        edited_text = response["message"]["content"].strip()
                    else:
                        raise RuntimeError("No content received from LLM.")
            except Exception as e:
                self.root.after(0, lambda: (self.set_busy(False), messagebox.showerror("LLM Error", str(e))))
                return

            self.root.after(0, lambda: self._on_llm_result(user_text, instruction, edited_text))

        self.set_busy(True)
        self.status_var.set("Processing with LLM...")
        threading.Thread(target=worker, daemon=True).start()

    def _on_llm_result(self, user_text, instruction, edited_text):
        # If it's the first time we are modifying text, create the scratchpad
        if not self.first_change_time:
            self.first_change_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.scratchpad_filename = f"TextEnhanceAI-scratchpad_{self.first_change_time}.md"

        # Show inline diff to the text widget
        self.show_inline_diff(user_text, edited_text)

        # Log to scratchpad with bold for differences
        bold_user_text, bold_edited_text = self.generate_bold_diff(user_text, edited_text)
        self.log_to_scratchpad(
            f"#Instruction: {instruction} #\n\n"
            f"##User Text:##\n{bold_user_text}\n\n"
            f"##Edited Text:##\n{bold_edited_text}\n\n"
        )
        self.status_var.set("Ready")
        self.set_busy(False)

    def set_busy(self, busy: bool):
        """Enable/disable buttons while background work runs."""
        state = tk.DISABLED if busy else tk.NORMAL
        # Top button row
        try:
            for w in self.btn_frame.winfo_children():
                if isinstance(w, tk.Button):
                    w.config(state=state)
        except Exception:
            pass
        # Accept/Reject row
        for w in self.accept_reject_frame.winfo_children():
            if isinstance(w, tk.Button):
                try:
                    w.config(state=state)
                except Exception:
                    pass

    def get_available_models(self):
        """Return available models from /Trainer/Models (GGUF/ollama) via config, + Claude if client present."""
        models = []

        # 1) Use Trainer's config — same source as custom_code_tab right panel
        try:
            import sys, os
            # Navigate up: TextEnhanceAI/ → custom_code_tab/ → tabs/ → Data/
            _data = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            if _data not in sys.path:
                sys.path.insert(0, _data)
            from config import get_all_trained_models
            all_models = get_all_trained_models()
            models = [m['name'] for m in all_models
                      if m.get('type') in ('gguf', 'ollama')]
        except Exception:
            pass

        # 2) Fallback: scan /Trainer/Models directly for GGUF exports
        if not models:
            try:
                from pathlib import Path
                _models_dir = Path(__file__).parents[4] / 'Models'
                if _models_dir.exists():
                    for d in _models_dir.iterdir():
                        if d.is_dir():
                            _gguf_dir = d / 'exports' / 'gguf'
                            if _gguf_dir.exists():
                                for gf in _gguf_dir.glob('*.gguf'):
                                    models.append(gf.stem)
            except Exception:
                pass

        # 3) Add Claude models if Anthropic client available
        if self.anthropic_client:
            models.extend(CLAUDE_MODELS)

        return sorted(set(models)) or [self.model_name]

    def populate_model_menu(self):
        """Load models from Ollama and update the dropdown."""
        models = self.get_available_models()
        try:
            menu = self.model_optionmenu["menu"]
            menu.delete(0, "end")
            for m in models:
                menu.add_command(label=m, command=lambda v=m: self.model_var.set(v))
            if self.model_var.get() not in models:
                self.model_var.set(models[0])
        except Exception:
            if models:
                self.model_var.set(models[0])

    def show_inline_diff(self, old_text, new_text):
        """
        Compute a diff using difflib and insert inline color-coded changes
        into the text widget. Deletions in red, additions in green.
        """
        self.text_area.delete("1.0", tk.END)

        # Use SequenceMatcher for cleaner diff without verbose hint lines
        matcher = difflib.SequenceMatcher(None, old_text, new_text)

        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'equal':
                # No change - insert as-is
                self.text_area.insert(tk.END, old_text[i1:i2])
            elif opcode == 'delete':
                # Deletion - red text
                self.text_area.insert(tk.END, old_text[i1:i2], ("deletion",))
            elif opcode == 'insert':
                # Addition - green text
                self.text_area.insert(tk.END, new_text[j1:j2], ("addition",))
            elif opcode == 'replace':
                # Replace = deletion + addition
                self.text_area.insert(tk.END, old_text[i1:i2], ("deletion",))
                self.text_area.insert(tk.END, new_text[j1:j2], ("addition",))

        # Tag styles
        self.text_area.tag_config("deletion", foreground="red", overstrike=True)
        self.text_area.tag_config("addition", foreground="green")

    def generate_bold_diff(self, original_text, edited_text):
        """
        Generate two strings:
         - In the 'User Text', highlight removed words in bold
         - In the 'Edited Text', highlight added words in bold
        """
        # Preserve whitespace/newlines to retain formatting in scratchpad
        orig_tokens = re.split(r'(\s+)', original_text)
        edit_tokens = re.split(r'(\s+)', edited_text)

        diff = difflib.ndiff(orig_tokens, edit_tokens)
        user_text_bold = []
        edited_text_bold = []

        for token in diff:
            text = token[2:]
            if token.startswith("  "):
                user_text_bold.append(text)
                edited_text_bold.append(text)
            elif token.startswith("- "):
                # Removed: bold non-whitespace in user view
                if text.isspace() or text == "":
                    user_text_bold.append(text)
                else:
                    user_text_bold.append(f"**{text}**")
            elif token.startswith("+ "):
                # Added: bold non-whitespace in edited view
                if text.isspace() or text == "":
                    edited_text_bold.append(text)
                else:
                    edited_text_bold.append(f"**{text}**")

        return "".join(user_text_bold), "".join(edited_text_bold)

    # --------------
    # Accept / Reject changes
    # --------------
    def accept_all_changes(self):
        """Accept all changes by removing diff markup and using the 'plus' words only."""
        final_text = self.get_text_excluding_tag_safe("deletion")
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", final_text)

        # Log acceptance
        self.log_to_scratchpad("User accepted all changes.\n\n")

        # Save to Inventory/session_logs/ next to session history
        try:
            ensure_inventory_dirs()
            session_logs_dir = os.path.join(INVENTORY_BASE, "session_logs")
            os.makedirs(session_logs_dir, exist_ok=True)

            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.current_file:
                base_name = os.path.splitext(os.path.basename(self.current_file))[0]
                filename = f"{base_name}_accepted_{timestamp}.txt"
            else:
                filename = f"accepted_{timestamp}.txt"

            session_log_path = os.path.join(session_logs_dir, filename)

            with open(session_log_path, 'w', encoding='utf-8') as f:
                f.write(final_text)

            # Update current file to point to accepted version
            self.current_file = session_log_path

            messagebox.showinfo("Changes Accepted",
                              f"Accepted changes saved to:\n{session_log_path}\n\n"
                              "Use 'Save' button to save to your preferred location.")
            self.status_var.set(f"✓ Accepted - saved to session_logs/")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save to session_logs: {e}")

    def reject_all_changes(self):
        """Reject all changes by removing diff markup and using the 'original' words only."""
        final_text = self.get_text_excluding_tag_safe("addition")
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", final_text)

        # Log rejection
        self.log_to_scratchpad("User rejected all changes.\n\n")

    def get_text_excluding_tag(self, tag):
        """
        Helper to rebuild text from the text widget while excluding a particular tagâ€™s text.
        """
        result = ""
        idx = "1.0"
        while True:
            if float(self.text_area.index(idx)) >= float(self.text_area.index(tk.END)):
                break

            char = self.text_area.get(idx)
            current_tags = self.text_area.tag_names(idx)
            if tag not in current_tags:
                result += char

            idx = self.text_area.index(f"{idx}+1c")
            if idx == self.text_area.index(tk.END):
                break

        return result

    # --------------
    # Logging / Scratchpad
    # --------------
    def log_to_scratchpad(self, *texts):
        """Write changes and actions to the scratchpad file."""
        if not self.scratchpad_filename:
            return
        with open(self.scratchpad_filename, "a", encoding="utf-8") as f:
            for text in texts:
                f.write(text)
            f.write("\n")

    def get_text_excluding_tag_safe(self, tag):
        """Rebuild text while excluding characters belonging to a given tag."""
        result = []
        idx = "1.0"
        end_idx = self.text_area.index("end-1c")
        while self.text_area.compare(idx, "<", end_idx):
            char = self.text_area.get(idx)
            current_tags = self.text_area.tag_names(idx)
            if tag not in current_tags:
                result.append(char)
            idx = self.text_area.index(f"{idx}+1c")
        return "".join(result)

    # --------------
    # File operations
    # --------------
    def load_file(self):
        """Load a text file into the editor."""
        filetypes = [("All supported", "*.txt *.md *.py"), ("Text", "*.txt"), ("Markdown", "*.md"), ("Python", "*.py"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(title="Load File", filetypes=filetypes)
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.text_area.delete("1.0", tk.END)
                self.text_area.insert("1.0", content)
                self.current_file = filepath
                self.status_var.set(f"Loaded: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not load file: {e}")

    def save_file(self):
        """Save the current text to a file (always shows file browser)."""
        content = self.text_area.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "Nothing to save in diff view.")
            return

        # Always show file browser for coherence
        fmt = self.doc_format.get()
        default_name = os.path.basename(self.current_file) if self.current_file else f"document.{fmt}"
        filetypes = [("Text", "*.txt"), ("Markdown", "*.md"), ("Python", "*.py"), ("All files", "*.*")]
        filepath = filedialog.asksaveasfilename(
            title="Save File",
            initialfile=default_name,
            defaultextension=f".{fmt}",
            filetypes=filetypes
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.current_file = filepath
                self.status_var.set(f"Saved: {os.path.basename(filepath)}")

                # Copy to inventory if this was an accepted change
                if self.first_change_time:
                    self.copy_to_inventory(filepath)
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")

    def copy_to_inventory(self, filepath):
        """Copy file to inventory and optionally to proposals."""
        try:
            ensure_inventory_dirs()
            filename = os.path.basename(filepath)
            inventory_path = os.path.join(INVENTORY_BASE, filename)
            shutil.copy2(filepath, inventory_path)
            self.status_var.set(f"Copied to inventory: {filename}")
        except Exception as e:
            print(f"Could not copy to inventory: {e}")

    def open_inventory(self):
        """Open the inventory folder in file browser."""
        ensure_inventory_dirs()
        open_file_browser(INVENTORY_BASE)

    # --------------
    # Chat functions
    # --------------
    def send_chat(self):
        """Send a chat message to the LLM."""
        user_msg = self.chat_input.get().strip()
        if not user_msg:
            return

        selected_model = self.model_var.get() or self.model_name
        is_claude = self.is_claude_model(selected_model)

        if is_claude and not self.anthropic_client:
            messagebox.showerror("Error", "Claude API not available. Set ANTHROPIC_API_KEY.")
            return
        elif not is_claude and not self.ollama_client:
            messagebox.showerror("Error", "Ollama client not initialized.")
            return

        self.chat_input.delete(0, tk.END)
        self.chat_running = True

        # Add user message to history
        self.chat_history.append({"role": "user", "content": user_msg})

        # Show in session area (left pane)
        self.session_area.insert(tk.END, f"\n\n[You]: {user_msg}\n")
        self.session_area.see(tk.END)

        def worker():
            try:
                # Check if chat was stopped
                if not self.chat_running:
                    self.root.after(0, lambda: self.status_var.set("Chat cancelled"))
                    return

                # If doc generation mode is enabled, use doc generation prompt
                if self.doc_gen_mode.get():
                    prompt = f"Generate documentation for: {user_msg}. Return only the documentation content."
                    messages = [{"role": "user", "content": prompt}]
                    system_msg = "Generate documentation content only. Do not use tools or function calls. Return plain text."
                else:
                    # Use chat history for conversation
                    # Use custom system prompt if set, otherwise use default
                    if hasattr(self, 'custom_system_prompt') and self.custom_system_prompt:
                        system_msg = self.custom_system_prompt
                    else:
                        system_msg = "You are a helpful coding assistant. Be concise and direct. Do not use tools, function calls, or JSON responses. Answer in plain text only."
                    messages = self.chat_history

                if is_claude:
                    # Call Claude API
                    response = self.anthropic_client.messages.create(
                        model=selected_model,
                        max_tokens=2048,
                        temperature=0.7,
                        system=system_msg if system_msg else "You are a helpful assistant.",
                        messages=messages
                    )
                    ai_response = response.content[0].text.strip()
                else:
                    # Call Ollama
                    if system_msg:
                        history = [{"role": "system", "content": system_msg}] + messages
                    else:
                        history = messages
                    response = self.ollama_client.chat(
                        model=selected_model,
                        messages=history,
                        options={'num_predict': 2048, 'temperature': 0.7},
                        format='',  # Disable any special formatting
                        tools=None  # Explicitly disable tools
                    )
                    if "message" in response and "content" in response["message"]:
                        ai_response = response["message"]["content"].strip()
                    else:
                        raise RuntimeError("No response from LLM")

                self.chat_history.append({"role": "assistant", "content": ai_response})

                # If doc generation mode, save to Inventory and load to diff display
                if self.doc_gen_mode.get():
                    fmt = self.doc_format.get()
                    temp_filename = f"doc_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{fmt}"
                    temp_path = os.path.join(INVENTORY_BASE, temp_filename)

                    ensure_inventory_dirs()
                    with open(temp_path, 'w', encoding='utf-8') as f:
                        f.write(ai_response)

                    # Load into diff display (right pane)
                    self.root.after(0, lambda: self.load_doc_to_diff_display(temp_path, ai_response))

                self.root.after(0, lambda: self._display_chat_response(ai_response))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Chat Error", str(e)))
            finally:
                self.chat_running = False

        self.status_var.set("Thinking...")
        threading.Thread(target=worker, daemon=True).start()

    def _display_chat_response(self, response):
        """Display chat response in session area (left pane)."""
        self.session_area.insert(tk.END, f"[AI]: {response}\n")
        self.session_area.see(tk.END)
        self.status_var.set("Ready")

    def stop_chat(self):
        """Stop the current chat request."""
        self.chat_running = False
        self.status_var.set("Chat stopped by user")

    def clear_chat(self):
        """Clear chat history and diff view."""
        self.chat_history = []
        self.session_area.delete("1.0", tk.END)
        self.text_area.delete("1.0", tk.END)  # Also clear diff view
        self.current_file = None
        self.chat_running = False
        self.status_var.set("Chat and diff view cleared")

    def edit_system_prompt(self):
        """Open a small editor window to edit the system prompt for chat mode."""
        prompt_window = tk.Toplevel(self.root)
        prompt_window.title("System Prompt Editor")
        prompt_window.geometry("700x550")

        # Top section: Profile selector
        profile_frame = tk.LabelFrame(prompt_window, text="Profile Configuration", padx=10, pady=5)
        profile_frame.pack(fill=tk.X, padx=10, pady=5)

        # Profile selection row
        profile_select_frame = tk.Frame(profile_frame)
        profile_select_frame.pack(fill=tk.X, pady=2)

        tk.Label(profile_select_frame, text="Profile:").pack(side=tk.LEFT, padx=5)

        # Get list of available profiles from PROMPTS
        profile_names = list(PROMPTS.keys()) + ["Orchestrator", "Custom"]
        profile_var = tk.StringVar(value="Custom")

        profile_dropdown = ttk.Combobox(profile_select_frame, textvariable=profile_var, values=profile_names, state='readonly', width=20)
        profile_dropdown.pack(side=tk.LEFT, padx=5)

        # Model selection row (per-profile model assignment)
        model_select_frame = tk.Frame(profile_frame)
        model_select_frame.pack(fill=tk.X, pady=2)

        tk.Label(model_select_frame, text="Model for Profile:").pack(side=tk.LEFT, padx=5)

        # Get available models
        available_models = self.get_available_models()
        profile_model_var = tk.StringVar(value=self.model_name)

        profile_model_dropdown = ttk.Combobox(model_select_frame, textvariable=profile_model_var, values=available_models, width=30)
        profile_model_dropdown.pack(side=tk.LEFT, padx=5)

        # Label
        tk.Label(prompt_window, text="Edit System Prompt for Chat Mode:", font=("Arial", 10, "bold")).pack(pady=5)

        # Text area for editing
        prompt_text = scrolledtext.ScrolledText(prompt_window, wrap=tk.WORD, width=80, height=18)
        prompt_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        # Load current system prompt (default)
        current_prompt = "You are a helpful coding assistant. Be concise and direct. Do not use tools, function calls, or JSON responses. Answer in plain text only."
        if hasattr(self, 'custom_system_prompt'):
            current_prompt = self.custom_system_prompt

        prompt_text.insert("1.0", current_prompt)

        def load_profile():
            """Load the selected profile's prompt into the editor."""
            selected = profile_var.get()
            if selected in PROMPTS:
                profile_prompt = PROMPTS[selected]
            elif selected == "Orchestrator":
                profile_prompt = AGENT_TOOLS["Orchestrator"]["prompt"]
            else:
                profile_prompt = "You are a helpful coding assistant. Be concise and direct. Do not use tools, function calls, or JSON responses. Answer in plain text only."

            prompt_text.delete("1.0", tk.END)
            prompt_text.insert("1.0", profile_prompt)

        def load_from_file():
            """Load prompt from a text file."""
            filepath = filedialog.askopenfilename(
                title="Load Prompt from File",
                filetypes=[("Text Files", "*.txt"), ("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            if filepath:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    prompt_text.delete("1.0", tk.END)
                    prompt_text.insert("1.0", content)
                    self.status_var.set(f"Loaded prompt from {os.path.basename(filepath)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not load file: {e}")

        # Profile action buttons
        profile_btn_frame = tk.Frame(profile_frame)
        profile_btn_frame.pack(side=tk.LEFT, padx=10)

        def set_as_default():
            """Save current prompt and model as default for selected profile in agent_config.json."""
            selected = profile_var.get()
            current_text = prompt_text.get("1.0", tk.END).strip()
            selected_model = profile_model_var.get()

            try:
                # Load existing config
                config_path = "agent_config.json"
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    config = {"version": "1.0", "agents": {}, "settings": {}}

                # Update the selected profile's prompt and model
                if selected not in config["agents"]:
                    config["agents"][selected] = {
                        "type": "text_edit" if selected != "Orchestrator" else "meta",
                        "function": AGENT_TOOLS.get(selected, {}).get("function", "run_llm_edit"),
                        "enabled": True
                    }

                config["agents"][selected]["prompt"] = current_text
                config["agents"][selected]["model"] = selected_model
                config["agents"][selected]["is_default"] = True

                # Save back to file
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)

                messagebox.showinfo("Success", f"Set '{selected}' profile with model '{selected_model}' as default in agent_config.json")
                self.status_var.set(f"Default saved for {selected}: {selected_model}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save to config: {e}")

        tk.Button(profile_btn_frame, text="Load Profile", command=load_profile, fg='blue').pack(side=tk.LEFT, padx=2)
        tk.Button(profile_btn_frame, text="Load from File", command=load_from_file, fg='blue').pack(side=tk.LEFT, padx=2)
        tk.Button(profile_btn_frame, text="Set as Default", command=set_as_default, fg='darkgreen').pack(side=tk.LEFT, padx=2)

        # Tool execution section for testing
        tool_frame = tk.LabelFrame(prompt_window, text="Test Tool Execution", padx=10, pady=5)
        tool_frame.pack(fill=tk.X, padx=10, pady=5)

        def test_on_current_text():
            """Test current prompt on the main text area."""
            test_prompt = prompt_text.get("1.0", tk.END).strip()
            user_text = self.text_area.get("1.0", tk.END).strip()
            selected_model = profile_model_var.get()

            if not user_text:
                messagebox.showinfo("Info", "Main text area is empty. Please add text to test.")
                return

            if not test_prompt:
                messagebox.showinfo("Info", "Prompt is empty. Please enter a prompt to test.")
                return

            # Use the selected model for this profile
            old_model = self.model_var.get()
            self.model_var.set(selected_model)

            # Run the LLM task with the test prompt
            self.start_llm_task(user_text, test_prompt)

            # Restore original model
            self.model_var.set(old_model)

            self.status_var.set(f"Testing prompt with {selected_model}")
            prompt_window.destroy()

        def test_on_sample():
            """Test current prompt on sample text."""
            test_prompt = prompt_text.get("1.0", tk.END).strip()
            sample_text = simpledialog.askstring("Sample Text", "Enter sample text to test:", parent=prompt_window)

            if not sample_text:
                return

            if not test_prompt:
                messagebox.showinfo("Info", "Prompt is empty. Please enter a prompt to test.")
                return

            # Load sample into main text area
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", sample_text)

            # Test with selected model
            selected_model = profile_model_var.get()
            old_model = self.model_var.get()
            self.model_var.set(selected_model)

            self.start_llm_task(sample_text, test_prompt)

            self.model_var.set(old_model)
            self.status_var.set(f"Testing on sample with {selected_model}")
            prompt_window.destroy()

        tk.Label(tool_frame, text="Test the current prompt:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)

        test_btn_frame = tk.Frame(tool_frame)
        test_btn_frame.pack(fill=tk.X, pady=2)

        tk.Button(test_btn_frame, text="Test on Current Text", command=test_on_current_text, fg='purple').pack(side=tk.LEFT, padx=2)
        tk.Button(test_btn_frame, text="Test on Sample", command=test_on_sample, fg='purple').pack(side=tk.LEFT, padx=2)

        # Buttons frame
        btn_frame = tk.Frame(prompt_window)
        btn_frame.pack(pady=5)

        def save_prompt():
            """Save the edited system prompt."""
            self.custom_system_prompt = prompt_text.get("1.0", tk.END).strip()
            self.status_var.set("System prompt updated")
            prompt_window.destroy()

        def save_to_file():
            """Save the current prompt to a file."""
            filepath = filedialog.asksaveasfilename(
                title="Save Prompt to File",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("JSON Files", "*.json"), ("All Files", "*.*")]
            )
            if filepath:
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(prompt_text.get("1.0", tk.END).strip())
                    messagebox.showinfo("Saved", f"Prompt saved to {os.path.basename(filepath)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Could not save file: {e}")

        def reset_prompt():
            """Reset to default system prompt."""
            default = "You are a helpful coding assistant. Be concise and direct. Do not use tools, function calls, or JSON responses. Answer in plain text only."
            prompt_text.delete("1.0", tk.END)
            prompt_text.insert("1.0", default)

        def save_configuration():
            """Save complete configuration to agent_config.json."""
            try:
                config_path = "agent_config.json"
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                else:
                    messagebox.showwarning("Warning", "agent_config.json not found. Use 'Set as Default' first.")
                    return

                # Show current config in a message
                num_agents = len(config.get("agents", {}))
                messagebox.showinfo(
                    "Configuration Saved",
                    f"Current configuration:\n\n"
                    f"- Agents: {num_agents}\n"
                    f"- Version: {config.get('version', 'N/A')}\n"
                    f"- Config file: {config_path}\n\n"
                    f"All changes have been persisted to agent_config.json"
                )
                self.status_var.set(f"Configuration saved ({num_agents} agents)")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save configuration: {e}")

        tk.Button(btn_frame, text="Save", command=save_prompt, fg='green').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save Configuration", command=save_configuration, fg='darkblue').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save to File", command=save_to_file, fg='darkgreen').pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Reset to Default", command=reset_prompt).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cancel", command=prompt_window.destroy).pack(side=tk.LEFT, padx=5)

    # --------------
    # Orchestrator & Tool Execution
    # --------------
    def log_activity(self, message, context=None):
        """Log activity for debug mode tracking."""
        if self.debug_mode.get():
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "message": message,
                "context": context
            }
            self.activity_log.append(log_entry)

            # Also print to session area if debug mode is on AND session_area exists
            debug_msg = f"[DEBUG {timestamp}] {message}"
            if context:
                debug_msg += f" | Context: {context}"

            # CRITICAL FIX: Check if session_area exists before inserting
            if hasattr(self, 'session_area'):
                self.session_area.insert(tk.END, f"{debug_msg}\n", ("debug",))
                self.session_area.tag_config("debug", foreground="gray")
                self.session_area.see(tk.END)

    def toggle_orchestrator(self):
        """Toggle orchestrator mode - routes between agents_config and orchestrator_config."""
        if self.orchestrator_enabled.get():
            self.log_activity("Orchestrator mode enabled - routing to orchestrator_config")
            self.status_var.set("Orchestrator mode: ON")
            # Load orchestrator config if it exists
            try:
                if os.path.exists("orchestrator_config.json"):
                    with open("orchestrator_config.json", 'r', encoding='utf-8') as f:
                        orch_config = json.load(f)
                        self.status_var.set(f"Orchestrator mode: ON (loaded {len(orch_config.get('agents', {}))} agents)")
                else:
                    self.status_var.set("Orchestrator mode: ON (no config found, will use defaults)")
            except Exception as e:
                self.log_activity(f"Error loading orchestrator config: {e}")
                messagebox.showwarning("Warning", f"Could not load orchestrator config: {e}")
        else:
            self.log_activity("Orchestrator mode disabled - using agents_config")
            self.status_var.set("Orchestrator mode: OFF")

    def open_orchestrator_window(self):
        """Open orchestrator window with tool execution UI."""
        orch_window = tk.Toplevel(self.root)
        orch_window.title("Agent Orchestrator")
        orch_window.geometry("800x600")
        orch_window.transient(self.root)

        # Tool buttons frame
        tool_frame = tk.Frame(orch_window)
        tool_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(tool_frame, text="Available Tools:", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # Create buttons for each tool from AGENT_TOOLS
        for tool_name, tool_info in AGENT_TOOLS.items():
            btn = tk.Button(tool_frame, text=tool_name,
                           command=lambda tn=tool_name: self.execute_agent_tool(tn, {}, orch_window))
            btn.pack(side=tk.LEFT, padx=2)
            create_tooltip(btn, tool_info["prompt"])

        # Context/Results area
        context_frame = tk.LabelFrame(orch_window, text="Tool Context & Results", padx=5, pady=5)
        context_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        orch_text = scrolledtext.ScrolledText(context_frame, wrap=tk.WORD)
        orch_text.pack(fill=tk.BOTH, expand=True)

        # Add welcome message
        orch_text.insert("1.0", "Agent Orchestrator\n\n" + "="*50 + "\n\n")
        orch_text.insert(tk.END, "Click tool buttons above to execute, or type commands below.\n\n")
        orch_text.insert(tk.END, "Available tools:\n")
        for tool_name, tool_info in AGENT_TOOLS.items():
            orch_text.insert(tk.END, f"  • {tool_name}: {tool_info['type']}\n")

        # Input frame
        input_frame = tk.Frame(orch_window)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(input_frame, text="Command:").pack(side=tk.LEFT)
        cmd_entry = tk.Entry(input_frame)
        cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        def execute_command():
            cmd = cmd_entry.get().strip()
            if cmd:
                orch_text.insert(tk.END, f"\n> {cmd}\n")
                self.parse_and_execute_tools(cmd, orch_text)
                cmd_entry.delete(0, tk.END)

        cmd_entry.bind('<Return>', lambda e: execute_command())
        tk.Button(input_frame, text="Execute", command=execute_command).pack(side=tk.LEFT)

    def execute_agent_tool(self, tool_name, tool_args, output_widget=None):
        """Execute an individual agent tool."""
        if tool_name not in AGENT_TOOLS:
            messagebox.showerror("Error", f"Tool '{tool_name}' not found")
            return

        tool_info = AGENT_TOOLS[tool_name]
        function_name = tool_info.get("function")

        if output_widget:
            output_widget.insert(tk.END, f"\n\nExecuting tool: {tool_name}\n")
            output_widget.insert(tk.END, f"Type: {tool_info['type']}\n")
            output_widget.insert(tk.END, f"Prompt: {tool_info['prompt']}\n")
            output_widget.see(tk.END)

        # Route to appropriate function
        if function_name == "run_llm_edit":
            self.run_llm_edit(tool_name)
        elif function_name == "run_translate_prompt":
            self.run_translate_prompt()
        elif function_name == "run_custom_prompt":
            self.run_custom_prompt()
        elif function_name == "orchestrate":
            if output_widget:
                output_widget.insert(tk.END, "\nOrchestrator mode - ready for multi-step tasks\n")
                output_widget.see(tk.END)
        else:
            if output_widget:
                output_widget.insert(tk.END, f"\nFunction '{function_name}' not implemented\n")

    def parse_and_execute_tools(self, response_text, output_widget=None):
        """Parse LLM response for tool calls and execute them."""
        import json
        import re

        # Detect tool call format: {"type":"tool_call","name":"...","args":{...}}
        tool_pattern = r'\{["\']type["\']:\s*["\']tool_call["\'].*?\}'
        matches = re.findall(tool_pattern, response_text, re.DOTALL | re.IGNORECASE)

        if not matches:
            # No tool calls found, treat as regular text
            if output_widget:
                output_widget.insert(tk.END, f"\nResponse: {response_text}\n")
                output_widget.see(tk.END)
            return

        for match in matches:
            try:
                tool_data = json.loads(match)
                tool_name = tool_data.get("name")
                tool_args = tool_data.get("args", {})

                if output_widget:
                    output_widget.insert(tk.END, f"\n📞 Tool Call Detected: {tool_name}\n")
                    output_widget.insert(tk.END, f"   Args: {tool_args}\n")

                # Execute tool from AGENT_TOOLS config
                if tool_name in AGENT_TOOLS:
                    self.execute_agent_tool(tool_name, tool_args, output_widget)
                else:
                    if output_widget:
                        output_widget.insert(tk.END, f"   ⚠️  Tool '{tool_name}' not found\n")

            except json.JSONDecodeError as e:
                if output_widget:
                    output_widget.insert(tk.END, f"\n⚠️  JSON parse error: {e}\n")
                continue

    def load_doc_to_diff_display(self, filepath, content=None):
        """Load document into diff display pane (right pane) for review."""
        if content is None:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                messagebox.showerror("Error", f"Could not load doc: {e}")
                return

        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", content)
        self.current_file = filepath
        self.status_var.set(f"Loaded to diff display: {os.path.basename(filepath)}")

    # --------------
    # API Key Management
    # --------------
    def manage_api_key(self):
        """Show dialog to manage Claude API key."""
        import json

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Claude API Key")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # Status frame
        status_frame = tk.LabelFrame(dialog, text="Current Status", padx=10, pady=10)
        status_frame.pack(fill=tk.X, padx=10, pady=10)

        if self.anthropic_api_key_source:
            status_text = f"✓ API key loaded from: {self.anthropic_api_key_source}"
            status_color = "green"
        else:
            status_text = "✗ No API key configured"
            status_color = "red"

        tk.Label(status_frame, text=status_text, fg=status_color, font=("TkDefaultFont", 10, "bold")).pack()

        # API key input frame
        input_frame = tk.LabelFrame(dialog, text="Set New API Key", padx=10, pady=10)
        input_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(input_frame, text="Enter your Anthropic API key:").pack(anchor="w")
        api_key_entry = tk.Entry(input_frame, width=60, show="*")
        api_key_entry.pack(fill=tk.X, pady=5)

        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            api_key_entry.config(show="" if show_var.get() else "*")
        tk.Checkbutton(input_frame, text="Show API key", variable=show_var, command=toggle_show).pack(anchor="w")

        def save_api_key():
            new_key = api_key_entry.get().strip()
            if not new_key:
                messagebox.showerror("Error", "Please enter an API key")
                return

            # Save to config file
            config = load_config()
            config['anthropic_api_key'] = new_key
            save_config(config)

            # Reinitialize client
            if ANTHROPIC_AVAILABLE:
                try:
                    self.anthropic_client = Anthropic(api_key=new_key)
                    self.anthropic_api_key_source = "local config"
                    messagebox.showinfo("Success", "API key saved and loaded successfully!")
                    dialog.destroy()
                    self.populate_model_menu()  # Refresh models
                except Exception as e:
                    messagebox.showerror("Error", f"Invalid API key: {e}")
            else:
                messagebox.showerror("Error", "Anthropic package not installed")

        def clear_api_key():
            if messagebox.askyesno("Confirm", "Remove saved API key from config?"):
                config = load_config()
                if 'anthropic_api_key' in config:
                    del config['anthropic_api_key']
                    save_config(config)
                self.anthropic_client = None
                self.anthropic_api_key_source = None
                messagebox.showinfo("Success", "API key removed from config")
                dialog.destroy()
                self.populate_model_menu()  # Refresh models

        # Buttons
        button_frame = tk.Frame(input_frame)
        button_frame.pack(fill=tk.X, pady=10)

        tk.Button(button_frame, text="Save API Key", command=save_api_key, bg="green", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear Saved Key", command=clear_api_key, bg="orange", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Info
        info_frame = tk.Frame(dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Label(info_frame, text="Get your API key at: https://console.anthropic.com/",
                fg="blue", cursor="hand2").pack()

    # --------------
    # Stash Operations Methods
    # --------------

    def run_stash_cli(self, *args):
        """Run stash_script_broken.py with CLI arguments via subprocess.

        This ensures portability - stash module has no directory dependencies.
        Base dir hardening allows it to carry dependencies when moved.
        """
        import subprocess

        # Build path to stash script relative to this file
        stash_script = os.path.join(
            os.path.dirname(__file__),
            'modules/stash/stash_script_broken.py'
        )

        # Construct command
        cmd = ['python3', stash_script] + list(args)

        # Log command execution
        cmd_str = ' '.join(args)
        self.log_stash_output(f"\n→ Running: stash {cmd_str}\n")

        # Log to debug activity if enabled
        if hasattr(self, 'debug_mode') and self.debug_mode.get():
            self.log_activity(f"Stash CLI: {cmd_str}", "subprocess execution")

        try:
            # Run subprocess with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=os.path.dirname(stash_script)
            )

            # Display output
            if result.stdout:
                self.log_stash_output(result.stdout)
            if result.stderr:
                self.log_stash_output(f"[STDERR] {result.stderr}")

            # Check return code
            if result.returncode != 0:
                self.log_stash_output(f"[Exit code: {result.returncode}]\n")
                return False, result.stderr or "Command failed"
            else:
                self.log_stash_output("[✓ Success]\n")
                return True, result.stdout

        except subprocess.TimeoutExpired:
            msg = "[ERROR] Command timed out after 30 seconds"
            self.log_stash_output(msg)
            return False, msg
        except FileNotFoundError:
            msg = f"[ERROR] Stash script not found: {stash_script}"
            self.log_stash_output(msg)
            return False, msg
        except Exception as e:
            msg = f"[ERROR] {str(e)}"
            self.log_stash_output(msg)
            return False, str(e)

    def run_stash_pfc(self):
        """Run Pre-Flight Check to get function line numbers and relative imports."""
        self.log_stash_output("\n=== Pre-Flight Check ===\n")
        success, output = self.run_stash_cli('-h')

        # Parse PFC output for function line numbers and imports
        if success and output:
            pfc_data = {
                'functions': {},
                'imports': []
            }

            lines = output.split('\n')
            in_functions = False
            in_imports = False

            for line in lines:
                if '--- Pre-flight Check (Function Line Numbers) ---' in line:
                    in_functions = True
                    in_imports = False
                elif '--- Pre-flight Check (Relative Imports) ---' in line:
                    in_functions = False
                    in_imports = True
                elif in_functions and ':' in line and 'Line' in line:
                    # Parse: "  perform_quick_stash: Line 139"
                    parts = line.strip().split(':')
                    if len(parts) == 2:
                        func_name = parts[0].strip()
                        line_num = parts[1].replace('Line', '').strip()
                        pfc_data['functions'][func_name] = line_num
                elif in_imports and line.strip() and not line.startswith('---'):
                    pfc_data['imports'].append(line.strip())

            # Log PFC data to debug
            if hasattr(self, 'debug_mode') and self.debug_mode.get():
                self.log_activity("PFC complete",
                                 f"{len(pfc_data['functions'])} functions, {len(pfc_data['imports'])} imports")

            return pfc_data

        return None

    def add_inventory_ui(self):
        """UI callback to add new inventory via CLI."""
        name = simpledialog.askstring("Add Inventory", "Enter inventory name:", parent=self.root)
        if not name:
            return

        path = filedialog.askdirectory(title=f"Select directory for '{name}'")
        if not path:
            return

        # Call CLI: --add-inventory NAME PATH
        success, output = self.run_stash_cli('--add-inventory', name, path)

        if success:
            self.populate_inventory_dropdown()
            messagebox.showinfo("Success", f"Inventory '{name}' added")
        else:
            messagebox.showerror("Error", f"Failed to add inventory: {output}")

    def list_inventories_ui(self):
        """UI callback to list all inventories via CLI."""
        # Call CLI: --list-inventories
        self.run_stash_cli('--list-inventories')

    def perform_quick_stash_ui(self):
        """UI callback to perform quick stash via CLI."""
        # Call CLI: -s or --snapshot
        success, output = self.run_stash_cli('-s')

        if success:
            messagebox.showinfo("Stash Complete", "Quick stash operation completed")
        else:
            messagebox.showerror("Error", f"Stash operation failed")

    def perform_lineage_ui(self):
        """UI callback to view stash lineage via CLI."""
        # Call CLI: -l or --lineage
        self.run_stash_cli('-l')

    def restore_stash_ui(self):
        """UI callback to restore selected stash via CLI."""
        stash_id = self.stash_var.get()
        if not stash_id:
            messagebox.showwarning("No Stash Selected", "Please select a stash to restore")
            return

        # Confirm before restoring
        if not messagebox.askyesno("Confirm Restore", f"Restore stash '{stash_id}'?"):
            return

        # Call CLI: --restore STASH_ID
        success, output = self.run_stash_cli('--restore', stash_id)

        if success:
            messagebox.showinfo("Restore Complete", f"Stash {stash_id} has been restored")
        else:
            messagebox.showerror("Error", f"Failed to restore stash")

    def view_manifest_ui(self):
        """UI callback to view manifest via CLI."""
        # Call CLI: -v or --view (with no arg shows manifest list)
        self.run_stash_cli('-v')

    def set_base_dir_ui(self):
        """UI callback to set or view base directory via CLI."""
        # First show current base dir
        self.log_stash_output("\n=== Current Base Directory ===\n")
        self.run_stash_cli('-b')

        # Ask if user wants to change it
        if messagebox.askyesno("Change Base Dir?", "Do you want to change the base directory?"):
            new_path = filedialog.askdirectory(title="Select new base directory")
            if new_path:
                # Call CLI: -b PATH
                success, output = self.run_stash_cli('-b', new_path)
                if success:
                    messagebox.showinfo("Success", f"Base directory updated to:\n{new_path}")

    def tag_inventory_ui(self):
        """UI callback to tag an inventory via CLI."""
        # Get inventory name from dropdown or ask
        inv_name = self.inventory_var.get()
        if not inv_name or inv_name == "default":
            inv_name = simpledialog.askstring("Tag Inventory", "Enter inventory name:", parent=self.root)
            if not inv_name:
                return

        # Ask for tag
        tag = simpledialog.askstring("Add Tag", f"Enter tag for inventory '{inv_name}':", parent=self.root)
        if not tag:
            return

        # Call CLI: --tag-inventory NAME TAG
        success, output = self.run_stash_cli('--tag-inventory', inv_name, tag)

        if success:
            messagebox.showinfo("Success", f"Tag '{tag}' added to '{inv_name}'")

    def refresh_inventories_ui(self):
        """[Refresh] button - check inventories, run PFC, coordinate with debug/scope.

        This integrates:
        1. Pre-Flight Check (function lines + relative imports)
        2. List all inventories and their stashes
        3. Run debug checks (if available: ruff, black, pylint, etc.)
        4. Post results to manifest with timestamp
        5. Update scope cache if files changed
        """
        self.log_stash_output("\n" + "="*60 + "\n")
        self.log_stash_output("=== REFRESH: Inventory + PFC + Debug Check ===\n")
        self.log_stash_output("="*60 + "\n\n")

        # Log to debug activity
        if hasattr(self, 'debug_mode') and self.debug_mode.get():
            self.log_activity("Refresh started", "inventory + PFC + debug coordination")

        # Step 1: Run Pre-Flight Check
        self.log_stash_output("→ Step 1: Pre-Flight Check\n")
        pfc_data = self.run_stash_pfc()

        if pfc_data:
            self.log_stash_output(f"\n✓ PFC found {len(pfc_data['functions'])} functions\n")
            if pfc_data['imports']:
                self.log_stash_output(f"✓ PFC found {len(pfc_data['imports'])} relative imports\n")

        # Step 2: List inventories
        self.log_stash_output("\n→ Step 2: List Known Inventories\n")
        self.run_stash_cli('--list-inventories')

        # Step 3: View current manifest/stashes
        self.log_stash_output("\n→ Step 3: View Manifest\n")
        self.run_stash_cli('-v')

        # Step 4: Check for file changes in current inventory
        current_inv = self.inventory_var.get()
        if current_inv and current_inv != "default":
            self.log_stash_output(f"\n→ Step 4: Checking inventory '{current_inv}' for changes\n")
            # Could add file change detection here

        # Step 5: Run debug checks (ruff, black, pylint, etc.) if available
        self.log_stash_output("\n→ Step 5: Debug Checks\n")
        self.run_debug_checks_for_stash()

        # Step 6: Update scope cache if file is loaded
        if hasattr(self, 'current_file') and self.current_file:
            self.log_stash_output(f"\n→ Step 6: Updating scope cache for {os.path.basename(self.current_file)}\n")
            if hasattr(self, 'analyze_file_scope'):
                self.analyze_file_scope()

        self.log_stash_output("\n" + "="*60 + "\n")
        self.log_stash_output("=== REFRESH COMPLETE ===\n")
        self.log_stash_output("="*60 + "\n\n")

        # Log completion
        if hasattr(self, 'debug_mode') and self.debug_mode.get():
            self.log_activity("Refresh complete", "all checks coordinated")

        messagebox.showinfo("Refresh Complete", "Inventory refresh and checks completed")

    def run_debug_checks_for_stash(self):
        """Run debug checks (ruff, black, pylint, etc.) and log results.

        This coordinates with the stash manifest to track code quality per inventory.
        """
        import subprocess

        # Check which tools are available
        tools = {
            'ruff': 'ruff check',
            'black': 'black --check',
            'pylint': 'pylint',
            'mypy': 'mypy',
            'pyflakes': 'pyflakes'
        }

        available_tools = []

        for tool_name, tool_cmd in tools.items():
            try:
                result = subprocess.run(
                    [tool_name, '--version'],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    available_tools.append(tool_name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        if not available_tools:
            self.log_stash_output("  No debug tools found (ruff, black, pylint, mypy, pyflakes)\n")
            self.log_stash_output("  Install with: pip install ruff black pylint mypy pyflakes\n")
            return

        self.log_stash_output(f"  Available tools: {', '.join(available_tools)}\n\n")

        # Run py_compile check on current file if loaded
        if hasattr(self, 'current_file') and self.current_file:
            self.log_stash_output(f"  Checking {os.path.basename(self.current_file)}...\n")

            # Run py_compile
            try:
                import py_compile
                py_compile.compile(self.current_file, doraise=True)
                self.log_stash_output("  ✓ py_compile: No syntax errors\n")
            except py_compile.PyCompileError as e:
                self.log_stash_output(f"  ✗ py_compile: {e}\n")

            # Run available tools on current file
            for tool in available_tools:
                try:
                    cmd = tools[tool].split() + [self.current_file]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        self.log_stash_output(f"  ✓ {tool}: Passed\n")
                    else:
                        self.log_stash_output(f"  ✗ {tool}: Issues found\n")
                        if result.stdout:
                            # Show first 3 lines of output
                            lines = result.stdout.split('\n')[:3]
                            for line in lines:
                                self.log_stash_output(f"    {line}\n")

                except subprocess.TimeoutExpired:
                    self.log_stash_output(f"  ⚠ {tool}: Timeout\n")
                except Exception as e:
                    self.log_stash_output(f"  ⚠ {tool}: {e}\n")

            self.log_stash_output("\n")

    def populate_inventory_dropdown(self):
        """Populate inventory dropdown with registered inventories."""
        if not hasattr(self, 'config_manager') or not self.config_manager:
            return

        inventories = self.config_manager.config.get('inventories', {})
        names = list(inventories.keys())

        if hasattr(self, 'inventory_dropdown'):
            self.inventory_dropdown['values'] = names
            if names and not self.inventory_var.get():
                self.inventory_var.set(names[0])

    def browse_stash_files(self):
        """Open file browser to select stash files."""
        if not hasattr(self, 'config_manager') or not self.config_manager:
            messagebox.showwarning("Config Error", "ConfigManager not initialized")
            return

        # Get base directory from config
        config = self.config_manager.config
        base_dir = config.get('base_directory', os.getcwd())

        filepath = filedialog.askopenfilename(
            title="Select Stash File",
            initialdir=base_dir,
            filetypes=[
                ("All Files", "*.*"),
                ("Python Files", "*.py"),
                ("Text Files", "*.txt"),
                ("Markdown", "*.md")
            ]
        )

        if filepath:
            self.selected_stash_file = filepath
            self.log_stash_output(f"Selected: {filepath}")

    def open_in_editor(self):
        """Open selected stash file in Editor tab for viewing/editing."""
        if not hasattr(self, 'selected_stash_file'):
            self.selected_stash_file = None

        if not self.selected_stash_file or not os.path.exists(self.selected_stash_file):
            messagebox.showwarning("No File Selected", "Please select a file to open")
            return

        try:
            with open(self.selected_stash_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Switch to Editor tab
            self.notebook.select(self.editor_tab)

            # Load content into text area
            self.text_area.delete("1.0", tk.END)
            self.text_area.insert("1.0", content)

            self.status_var.set(f"Loaded: {os.path.basename(self.selected_stash_file)}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")

    def log_stash_output(self, message):
        """Log message to stash output area."""
        if hasattr(self, 'stash_output_area'):
            self.stash_output_area.insert(tk.END, f"{message}\n")
            self.stash_output_area.see(tk.END)

    # --------------
    # Debug/Scope Analysis Methods
    # --------------
    def analyze_file_scope(self):
        """Analyze selected file with ScopeAnalyzer."""
        if not hasattr(self, 'scope_available') or not self.scope_available:
            return

        filename = self.debug_file_var.get()
        filepath = self.resolve_debug_filepath(filename)

        if not filepath or not os.path.exists(filepath):
            self.scope_output.delete("1.0", tk.END)
            self.scope_output.insert("1.0", f"Error: File not found: {filename}")
            return

        self.scope_output.delete("1.0", tk.END)
        self.scope_output.insert("1.0", f"Analyzing {filename}...\n\n")

        try:
            from scope.scope import ScopeAnalyzer
            analyzer = ScopeAnalyzer()
            success, result = analyzer.analyze_file(filepath, copy=False)

            if success:
                # Parse the result to extract information
                output = f"=== Scope Analysis: {filename} ===\n\n"
                output += str(result)
                self.scope_output.insert(tk.END, output)

                # CRITICAL: Cache results for scope inspector microscope
                # Parse result string to extract structured data
                self.cached_scope_results = self.parse_scope_result(result, filepath)

                # Log caching activity
                self.log_activity(f"Scope cache updated for {filename}",
                                 f"{len(self.cached_scope_results.get('functions', []))} functions, "
                                 f"{len(self.cached_scope_results.get('classes', []))} classes")
            else:
                self.scope_output.insert(tk.END, f"Analysis failed: {result}")

        except Exception as e:
            import traceback
            self.scope_output.insert(tk.END, f"\nError during analysis: {e}\n{traceback.format_exc()}")

    def run_code_quality_checks(self):
        """Run code quality tools (ruff, black, pylint, py_compile) when debug mode is ON."""
        if not self.debug_mode.get():
            self.quality_output.delete("1.0", tk.END)
            self.quality_output.insert("1.0", "Debug mode must be ON to run quality checks")
            return

        filename = self.debug_file_var.get()
        filepath = self.resolve_debug_filepath(filename)

        if not filepath or not os.path.exists(filepath):
            self.quality_output.delete("1.0", tk.END)
            self.quality_output.insert("1.0", f"Error: File not found: {filename}")
            return

        self.quality_output.delete("1.0", tk.END)
        self.quality_output.insert("1.0", f"Running quality checks on {filename}...\n\n")

        checks = []

        # 1. py_compile (syntax check)
        try:
            import py_compile
            py_compile.compile(filepath, doraise=True)
            checks.append("✓ py_compile: No syntax errors")
        except Exception as e:
            checks.append(f"✗ py_compile: {e}")

        # 2. ruff (if available)
        try:
            result = subprocess.run(['ruff', 'check', filepath], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                checks.append("✓ ruff: No issues found")
            else:
                checks.append(f"✗ ruff:\n{result.stdout}")
        except FileNotFoundError:
            checks.append("  ruff: Not installed")
        except Exception as e:
            checks.append(f"  ruff: Error - {e}")

        # 3. black (if available)
        try:
            result = subprocess.run(['black', '--check', filepath], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                checks.append("✓ black: Formatting is correct")
            else:
                checks.append("✗ black: Would reformat")
        except FileNotFoundError:
            checks.append("  black: Not installed")
        except Exception as e:
            checks.append(f"  black: Error - {e}")

        # 4. pylint (if available, only for files with relative imports)
        if self.has_relative_imports(filepath):
            try:
                result = subprocess.run(['pylint', filepath], capture_output=True, text=True, timeout=15)
                checks.append(f"  pylint (relative imports detected):\n{result.stdout[:500]}")
            except FileNotFoundError:
                checks.append("  pylint: Not installed")
            except Exception as e:
                checks.append(f"  pylint: Error - {e}")

        self.quality_output.insert(tk.END, "\n".join(checks))

    def resolve_debug_filepath(self, filename):
        """Resolve filename to full path for debug analysis."""
        base_dir = os.path.dirname(__file__)
        if filename == "TextEnhanceAI.py":
            return os.path.join(base_dir, "TextEnhanceAI.py")
        elif filename == "stash_script_broken.py":
            return os.path.join(base_dir, "modules/stash/stash_script_broken.py")
        elif filename == "stash_gui.py":
            return os.path.join(base_dir, "modules/stash/stash_gui.py")
        return None

    def has_relative_imports(self, filepath):
        """Check if file has relative imports."""
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                return 'from .' in content or 'import .' in content
        except Exception:
            return False

    def parse_scope_result(self, result, filepath):
        """Parse scope analysis result into structured cache."""
        import re
        cache = {
            'functions': [],
            'classes': [],
            'imports': []
        }

        try:
            # Read file to extract line-by-line structure
            with open(filepath, 'r') as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line_text = line.strip()

                # Extract functions
                func_match = re.match(r'def\s+(\w+)', line_text)
                if func_match:
                    cache['functions'].append({
                        'line': line_num,
                        'name': func_match.group(1),
                        'code': line_text
                    })

                # Extract classes
                class_match = re.match(r'class\s+(\w+)', line_text)
                if class_match:
                    cache['classes'].append({
                        'line': line_num,
                        'name': class_match.group(1),
                        'code': line_text
                    })

                # Extract imports
                if re.match(r'(from|import)\s+', line_text):
                    cache['imports'].append({
                        'line': line_num,
                        'code': line_text
                    })

        except Exception as e:
            # Fallback to empty cache on error
            pass

        return cache

    # --------------
    # Scope Inspector Methods (Microscope Mode)
    # --------------
    def toggle_scope_inspector(self):
        """Enable/disable scope inspector - UI widget microscope with code popup."""
        try:
            if self.scope_inspector_mode.get():
                # Ask for target file to inspect (defaults to this module)
                # TODO: Later add inventory/stash selection prompt here
                if not hasattr(self, 'scope_target_file') or not self.scope_target_file:
                    default_file = os.path.abspath(__file__)

                    response = messagebox.askyesno(
                        "Scope Inspector - Select Target",
                        f"Inspect UI widgets in this module?\n\n{os.path.basename(default_file)}\n\n"
                        "Click 'No' to choose a different file."
                    )

                    if response:
                        self.scope_target_file = default_file
                    else:
                        chosen_file = filedialog.askopenfilename(
                            title="Select file to inspect",
                            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")],
                            initialdir=os.path.dirname(__file__)
                        )
                        if chosen_file:
                            self.scope_target_file = chosen_file
                        else:
                            self.scope_inspector_mode.set(False)
                            return

                # Save snapshot of target file for inspection
                self.save_scope_snapshot()

                # Activate UI widget hover inspector
                self.activate_ui_scope_hover()

                msg = f"✓ Scope Inspector ACTIVE - hover over UI widgets"
                self.log_activity("Scope Inspector activated", f"target: {os.path.basename(self.scope_target_file)}")

                if hasattr(self, 'stash_output_area'):
                    self.stash_output_area.insert(tk.END, f"{msg}\n")
                    self.stash_output_area.insert(tk.END, f"  Target: {os.path.basename(self.scope_target_file)}\n")
                    self.stash_output_area.see(tk.END)

                if hasattr(self, 'session_area'):
                    self.session_area.insert(tk.END, f"{msg}\n", ("info",))
                    self.session_area.tag_config("info", foreground="purple")
                    self.session_area.see(tk.END)
            else:
                self.deactivate_ui_scope_hover()
                msg = "✗ Scope Inspector deactivated"
                self.log_activity("Scope Inspector deactivated")

                if hasattr(self, 'stash_output_area'):
                    self.stash_output_area.insert(tk.END, f"{msg}\n")
                if hasattr(self, 'session_area'):
                    self.session_area.insert(tk.END, f"{msg}\n", ("info",))
        except Exception as e:
            error_msg = f"✗ Scope Inspector failed: {e}"
            if hasattr(self, 'stash_output_area'):
                self.stash_output_area.insert(tk.END, f"{error_msg}\n")
            self.scope_inspector_mode.set(False)

    def save_scope_snapshot(self):
        """Save snapshot of target file for inspection."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_name = f"scope_snapshot_{timestamp}.py"
            snapshot_dir = os.path.join(os.path.dirname(__file__), 'Inventory')
            os.makedirs(snapshot_dir, exist_ok=True)

            snapshot_path = os.path.join(snapshot_dir, snapshot_name)
            shutil.copy2(self.scope_target_file, snapshot_path)

            self.scope_snapshot_file = snapshot_path

            # Read and parse snapshot for widget detection
            with open(snapshot_path, 'r', encoding='utf-8') as f:
                self.scope_snapshot_lines = f.readlines()

            self.log_activity(f"Scope snapshot saved", f"{snapshot_name}")
            return True
        except Exception as e:
            self.log_activity(f"Failed to save snapshot: {e}", "error")
            return False

    def activate_ui_scope_hover(self):
        """Bind hover events to all UI widgets for inspection."""
        self.scope_hover_cooldown = 0  # Timestamp of last hover
        self.scope_popup = None  # Current popup window

        # Recursively bind to all widgets
        self.bind_all_widgets_for_scope(self.root)

        bound_msg = "Scope inspector bound to all widgets"
        self.log_activity(bound_msg, "hover with 2s cooldown")

    def bind_all_widgets_for_scope(self, widget):
        """Recursively bind Enter event to widget and all children."""
        try:
            widget.bind('<Enter>', self.on_ui_widget_enter, add='+')
            widget.bind('<Leave>', self.on_ui_widget_leave, add='+')

            # Recurse to children
            for child in widget.winfo_children():
                self.bind_all_widgets_for_scope(child)
        except Exception as e:
            pass  # Some widgets can't be bound

    def deactivate_ui_scope_hover(self):
        """Unbind scope hover events from all widgets."""
        try:
            self.unbind_all_widgets_for_scope(self.root)

            # Close any active popup
            if self.scope_popup and self.scope_popup.winfo_exists():
                self.scope_popup.destroy()
                self.scope_popup = None

            self.log_activity("Scope inspector unbound", "all widgets")
        except Exception as e:
            self.log_activity(f"Deactivation error: {e}", "error")

    def unbind_all_widgets_for_scope(self, widget):
        """Recursively unbind Enter event from widget and children."""
        try:
            widget.unbind('<Enter>')
            widget.unbind('<Leave>')

            for child in widget.winfo_children():
                self.unbind_all_widgets_for_scope(child)
        except:
            pass

    def on_ui_widget_enter(self, event):
        """Handle mouse enter on UI widget - show code popup with cooldown."""
        try:
            # Check cooldown (2 seconds)
            current_time = time.time()
            if current_time - self.scope_hover_cooldown < 2.0:
                return

            self.scope_hover_cooldown = current_time

            # Get widget info
            widget = event.widget
            widget_class = widget.__class__.__name__
            widget_id = str(widget)

            # Find widget in snapshot code
            widget_code, line_num = self.find_widget_in_snapshot(widget)

            if widget_code:
                # Show popup with widget info and code
                self.show_scope_popup(widget, widget_class, widget_code, line_num)
            else:
                # Show basic widget info if code not found
                self.show_scope_popup(widget, widget_class, None, None)

        except Exception as e:
            pass  # Silent fail on hover

    def on_ui_widget_leave(self, event):
        """Handle mouse leave - keep popup for a moment."""
        # Popup will auto-dismiss after timeout or manual close
        pass

    def find_widget_in_snapshot(self, widget):
        """Find widget definition in snapshot code."""
        try:
            widget_class = widget.__class__.__name__

            # Search for widget creation patterns
            patterns = [
                f'= {widget_class}(',
                f'={widget_class}(',
                f'tk.{widget_class}(',
                f'ttk.{widget_class}('
            ]

            for line_num, line in enumerate(self.scope_snapshot_lines, 1):
                for pattern in patterns:
                    if pattern in line:
                        # Found potential match - grab context (5 lines)
                        start = max(0, line_num - 2)
                        end = min(len(self.scope_snapshot_lines), line_num + 3)
                        context_lines = self.scope_snapshot_lines[start:end]
                        return ''.join(context_lines), line_num

            return None, None
        except:
            return None, None

    def show_scope_popup(self, widget, widget_class, code, line_num):
        """Display small popup window with widget info and code."""
        # Close existing popup
        if self.scope_popup and self.scope_popup.winfo_exists():
            self.scope_popup.destroy()

        # Create new popup
        self.scope_popup = tk.Toplevel(self.root)
        self.scope_popup.overrideredirect(True)  # No window decorations
        self.scope_popup.attributes('-alpha', 0.95)
        self.scope_popup.configure(bg='#2b2d42')

        # Position near mouse
        x = self.root.winfo_pointerx() + 15
        y = self.root.winfo_pointery() + 15
        self.scope_popup.geometry(f"450x250+{x}+{y}")

        # Header
        header = tk.Label(
            self.scope_popup,
            text=f"🔍 {widget_class}",
            font=('Monospace', 11, 'bold'),
            bg='#2b2d42',
            fg='#06D6A0'
        )
        header.pack(pady=5)

        # Widget info
        try:
            geometry = f"{widget.winfo_width()}x{widget.winfo_height()}"
            info_text = f"Size: {geometry} | Children: {len(widget.winfo_children())}"
            info_label = tk.Label(
                self.scope_popup,
                text=info_text,
                font=('Monospace', 8),
                bg='#2b2d42',
                fg='#EDF2F4'
            )
            info_label.pack()
        except:
            pass

        # Code section
        if code and line_num:
            line_label = tk.Label(
                self.scope_popup,
                text=f"Line {line_num}:",
                font=('Monospace', 9, 'bold'),
                bg='#2b2d42',
                fg='#FFD166'
            )
            line_label.pack(pady=(5, 0))

            code_text = scrolledtext.ScrolledText(
                self.scope_popup,
                height=8,
                font=('Monospace', 9),
                bg='#1a1b26',
                fg='#EDF2F4',
                wrap=tk.NONE
            )
            code_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            code_text.insert('1.0', code)
            code_text.config(state=tk.DISABLED)
        else:
            no_code = tk.Label(
                self.scope_popup,
                text="Code location not found in snapshot",
                font=('Monospace', 8),
                bg='#2b2d42',
                fg='#FF6B6B'
            )
            no_code.pack(pady=10)

        # Close button
        close_btn = tk.Button(
            self.scope_popup,
            text="Close",
            command=self.scope_popup.destroy,
            bg='#118AB2',
            fg='white',
            font=('Arial', 8, 'bold')
        )
        close_btn.pack(pady=(0, 5))

        # Auto-dismiss after 5 seconds
        self.scope_popup.after(5000, lambda: self.scope_popup.destroy() if self.scope_popup and self.scope_popup.winfo_exists() else None)

    def deactivate_scope_hover(self):
        """Unbind hover events."""
        if hasattr(self, 'text_area'):
            self.text_area.unbind('<Motion>')
            self.text_area.unbind('<Leave>')
        if hasattr(self, 'diff_area'):
            self.diff_area.unbind('<Motion>')
            self.diff_area.unbind('<Leave>')
        # Hide any active tooltip
        if self.scope_tooltip:
            try:
                self.scope_tooltip.destroy()
            except:
                pass
            self.scope_tooltip = None

    def on_scope_hover(self, event):
        """Handle hover over code - show live scope info."""
        try:
            # Get widget and cursor position
            widget = event.widget
            index = widget.index(f"@{event.x},{event.y}")
            line_num = int(index.split('.')[0])

            # Get current line text
            line_text = widget.get(f"{line_num}.0", f"{line_num}.end").strip()

            # Build scope info
            scope_info = self.get_scope_at_line(line_num, line_text)

            if scope_info:
                # Show tooltip with scope info
                self.show_scope_tooltip(event.x_root, event.y_root, scope_info, line_num)

                # Send to debug log if debug is on
                if self.debug_mode.get():
                    self.log_activity(f"Scope inspect L{line_num}", scope_info.get('summary', ''))

        except Exception as e:
            # Silent fail on hover errors
            pass

    def on_scope_leave(self, event):
        """Handle mouse leaving code area - hide tooltip."""
        if self.scope_tooltip:
            try:
                self.scope_tooltip.destroy()
            except:
                pass
            self.scope_tooltip = None

    def get_scope_at_line(self, line_num, line_text=''):
        """Get scope information for a specific line."""
        scope_info = {
            'line': line_num,
            'text': line_text,
            'summary': '',
            'details': []
        }

        # Check cached scope results if available
        if self.cached_scope_results:
            # Check if line is in a function
            for func in self.cached_scope_results.get('functions', []):
                if func.get('line') == line_num:
                    scope_info['summary'] = f"Function: {func.get('name')}"
                    scope_info['details'].append(f"Defined at line {line_num}")
                    return scope_info

            # Check if line is in a class
            for cls in self.cached_scope_results.get('classes', []):
                if cls.get('line') == line_num:
                    scope_info['summary'] = f"Class: {cls.get('name')}"
                    scope_info['details'].append(f"Defined at line {line_num}")
                    return scope_info

            # Check if line is an import
            for imp in self.cached_scope_results.get('imports', []):
                if imp.get('line') == line_num:
                    scope_info['summary'] = f"Import: {imp.get('code')}"
                    return scope_info

        # Quick pattern detection if no cache
        import re

        if re.match(r'\s*def\s+(\w+)', line_text):
            match = re.match(r'\s*def\s+(\w+)', line_text)
            scope_info['summary'] = f"Function: {match.group(1)}"
            scope_info['details'].append("Function definition")

        elif re.match(r'\s*class\s+(\w+)', line_text):
            match = re.match(r'\s*class\s+(\w+)', line_text)
            scope_info['summary'] = f"Class: {match.group(1)}"
            scope_info['details'].append("Class definition")

        elif re.match(r'\s*(from|import)\s+', line_text):
            scope_info['summary'] = "Import statement"
            scope_info['details'].append(line_text)

        elif '=' in line_text and not line_text.strip().startswith('#'):
            # Variable assignment
            var_name = line_text.split('=')[0].strip()
            scope_info['summary'] = f"Assignment: {var_name}"

        else:
            scope_info['summary'] = "Code execution"

        return scope_info

    def show_scope_tooltip(self, x, y, scope_info, line_num):
        """Show tooltip with scope information."""
        # Destroy existing tooltip
        if self.scope_tooltip:
            try:
                self.scope_tooltip.destroy()
            except:
                pass

        # Create new tooltip window
        self.scope_tooltip = tk.Toplevel(self.root)
        self.scope_tooltip.wm_overrideredirect(True)
        self.scope_tooltip.wm_geometry(f"+{x+10}+{y+10}")

        # Create frame with border
        frame = tk.Frame(
            self.scope_tooltip,
            background='#2b2d42',
            borderwidth=2,
            relief='solid'
        )
        frame.pack()

        # Line number header
        header = tk.Label(
            frame,
            text=f"Line {line_num}",
            background='#2b2d42',
            foreground='#FFD166',
            font=('Courier', 9, 'bold'),
            padx=5,
            pady=2
        )
        header.pack(anchor='w')

        # Summary
        if scope_info.get('summary'):
            summary = tk.Label(
                frame,
                text=scope_info['summary'],
                background='#2b2d42',
                foreground='#06D6A0',
                font=('Courier', 10, 'bold'),
                padx=5,
                pady=2
            )
            summary.pack(anchor='w')

        # Details
        if scope_info.get('details'):
            for detail in scope_info['details']:
                detail_label = tk.Label(
                    frame,
                    text=detail,
                    background='#2b2d42',
                    foreground='#EDF2F4',
                    font=('Courier', 8),
                    padx=5
                )
                detail_label.pack(anchor='w')

        # Code snippet
        if scope_info.get('text'):
            code_label = tk.Label(
                frame,
                text=f"» {scope_info['text'][:60]}{'...' if len(scope_info['text']) > 60 else ''}",
                background='#2b2d42',
                foreground='#8D99AE',
                font=('Courier', 8),
                padx=5,
                pady=2
            )
            code_label.pack(anchor='w')

        # Auto-hide after 3 seconds
        self.scope_tooltip.after(3000, lambda: self.on_scope_leave(None))


# --------------
# Main entry point
# --------------
if __name__ == "__main__":
    root = tk.Tk()
    app = EditorApp(root)
    root.mainloop()

