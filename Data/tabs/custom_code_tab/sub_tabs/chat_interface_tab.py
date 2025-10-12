# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
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

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


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

    def set_model(self, model_name):
        """Set the active model for chat"""
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
        self.is_mounted = False

        # Update label color to red (not mounted)
        self.model_label.config(text=model_name, fg='#ff6b6b')

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

        # Auto-mount if enabled in settings
        if self.backend_settings.get('auto_mount_model', False):
            log_message(f"CHAT_INTERFACE: Auto-mounting {model_name}")
            self.mount_model()

        # Reset session temperature
        self.session_temperature = self.backend_settings.get('temperature', 0.8)
        self.session_temperature_var.set(self.session_temperature)
        self.update_session_temp_label(self.session_temperature)

    def mount_model(self):
        """Mount the selected model in Ollama"""
        if not self.current_model:
            return

        log_message(f"CHAT_INTERFACE: Mounting model {self.current_model}...")
        self.add_message("system", f"Mounting {self.current_model}...")

        def mount_thread():
            try:
                # Call Ollama to load the model
                result = subprocess.run(
                    ["ollama", "run", self.current_model, "--verbose"],
                    input="",  # Empty input to just load the model
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
                self.root.after(0, self._on_mount_success)  # Timeout often means it loaded
            except Exception as e:
                error_msg = f"Mount error: {str(e)}"
                self.root.after(0, lambda: self._on_mount_error(error_msg))

        threading.Thread(target=mount_thread, daemon=True).start()

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
            else:
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
            self.tool_executor.initialize_tools()

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

    def get_current_system_prompt(self):
        """Get the current system prompt content"""
        prompt_file = self.system_prompts_dir / f"{self.current_system_prompt}.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r') as f:
                return f.read()
        return "You are a helpful AI assistant."

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
