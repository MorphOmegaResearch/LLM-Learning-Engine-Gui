"""
Custom Code Tab - Main tab for OpenCode integration
Provides chat interface and tooling features
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class CustomCodeTab(BaseTab):
    """Custom Code tab with sub-tabs for chat, tools, and project management"""

    def __init__(self, parent, root, style):
        super().__init__(parent, root, style)
        self.tab_instances = None  # Will be set by main GUI

        # Set up close handler for auto-saving chat history
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        """Create the custom code tab UI"""
        log_message("CUSTOM_CODE_TAB: Creating UI...")

        # Main layout: content area (left) and side panel (right)
        self.parent.columnconfigure(0, weight=1)  # Content area
        self.parent.columnconfigure(1, weight=0)  # Side panel
        self.parent.rowconfigure(0, weight=1)

        # Left side: Main content with sub-tabs
        content_frame = ttk.Frame(self.parent, style='Category.TFrame')
        content_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        content_frame.columnconfigure(0, weight=1)
        content_frame.rowconfigure(1, weight=1)

        # Header with title and refresh button
        header_frame = ttk.Frame(content_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)

        ttk.Label(
            header_frame,
            text="🤖 Custom Code",
            font=("Arial", 14, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_tab,
            style='Select.TButton'
        ).pack(side=tk.RIGHT, padx=5)

        # Sub-tabs notebook
        self.sub_notebook = ttk.Notebook(content_frame)
        self.sub_notebook.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)

        # Chat Interface Sub-tab
        self.chat_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.chat_tab_frame, text="💬 Chat")
        self.create_chat_tab(self.chat_tab_frame)

        # History Sub-tab
        self.history_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.history_tab_frame, text="📚 History")
        self.create_history_tab(self.history_tab_frame)

        # Tools Sub-tab
        self.tools_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.tools_tab_frame, text="🔧 Tools")
        self.create_tools_tab(self.tools_tab_frame)

        # Projects Sub-tab (placeholder for future)
        self.projects_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.projects_tab_frame, text="📁 Projects")
        self.create_placeholder_tab(self.projects_tab_frame, "Project Management")

        # Settings Sub-tab
        self.settings_tab_frame = ttk.Frame(self.sub_notebook)
        self.sub_notebook.add(self.settings_tab_frame, text="⚙️ Settings")
        self.create_settings_tab(self.settings_tab_frame)

        # Right side: Model selector (similar to Models tab)
        self.create_right_panel(self.parent)

        log_message("CUSTOM_CODE_TAB: UI created successfully")

    def create_chat_tab(self, parent):
        """Create the chat interface sub-tab"""
        # Import here to avoid circular dependencies
        from .sub_tabs.chat_interface_tab import ChatInterfaceTab

        self.chat_interface = ChatInterfaceTab(parent, self.root, self.style, self)
        self.chat_interface.safe_create()

    def create_tools_tab(self, parent):
        """Create the tools configuration sub-tab"""
        from .sub_tabs.tools_tab import ToolsTab

        self.tools_interface = ToolsTab(parent, self.root, self.style, self)
        self.tools_interface.safe_create()

    def create_settings_tab(self, parent):
        """Create the settings configuration sub-tab"""
        from .sub_tabs.settings_tab import SettingsTab

        self.settings_interface = SettingsTab(parent, self.root, self.style, self)
        self.settings_interface.safe_create()

    def create_history_tab(self, parent):
        """Create the conversation history sub-tab"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # Header
        header_frame = ttk.Frame(parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="📚 Conversation History",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self.refresh_history,
            style='Select.TButton'
        ).pack(side=tk.RIGHT)

        # History list frame with scrollbar
        list_container = ttk.Frame(parent, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.history_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.history_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.history_canvas.yview
        )
        self.history_scroll_frame = ttk.Frame(self.history_canvas, style='Category.TFrame')

        self.history_scroll_frame.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all"))
        )

        self.history_canvas_window = self.history_canvas.create_window(
            (0, 0),
            window=self.history_scroll_frame,
            anchor="nw"
        )
        self.history_canvas.configure(yscrollcommand=self.history_scrollbar.set)

        self.history_canvas.bind(
            "<Configure>",
            lambda e: self.history_canvas.itemconfig(self.history_canvas_window, width=e.width)
        )

        self.history_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.history_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for history list
        self.bind_mousewheel_to_canvas(self.history_canvas)

        # Load history
        self.refresh_history()

    def refresh_history(self):
        """Refresh the conversation history list from persistent storage"""
        log_message("CUSTOM_CODE_TAB: Refreshing history from storage...")

        # Clear existing
        for widget in self.history_scroll_frame.winfo_children():
            widget.destroy()

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            ttk.Label(
                self.history_scroll_frame,
                text="Chat history manager not initialized.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        # Get conversation histories from ChatHistoryManager
        histories = self.chat_interface.chat_history_manager.list_conversations()

        if not histories:
            ttk.Label(
                self.history_scroll_frame,
                text="No saved conversation history found.",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        def show_config(cfg):
            import json
            config_win = tk.Toplevel(self.root)
            config_win.title("Session Configuration")
            config_win.geometry("600x400")
            text = tk.Text(config_win, wrap=tk.WORD, font=("Courier", 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text.insert(tk.END, json.dumps(cfg, indent=2))
            text.config(state=tk.DISABLED)

        # Display each conversation
        for conv_summary in histories:
            session_id = conv_summary.get("session_id")
            model_name = conv_summary.get("model_name")
            msg_count = conv_summary.get("message_count")
            saved_at = conv_summary.get("saved_at")
            preview = conv_summary.get("preview")
            metadata = conv_summary.get("metadata", {})

            # Create frame for this session
            session_frame = ttk.LabelFrame(
                self.history_scroll_frame,
                text=f"📄 {session_id}",
                style='TLabelframe'
            )
            session_frame.pack(fill=tk.X, padx=5, pady=5)

            # Display info
            info_text = f"Model: {model_name} | Messages: {msg_count} | Saved: {saved_at}"
            ttk.Label(
                session_frame,
                text=info_text,
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(5, 2))

            ttk.Label(
                session_frame,
                text=f"Preview: {preview}",
                style='Config.TLabel'
            ).pack(anchor=tk.W, padx=10, pady=(0, 5))

            # Buttons
            btn_frame = ttk.Frame(session_frame, style='Category.TFrame')
            btn_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

            ttk.Button(
                btn_frame,
                text="Load Conversation",
                command=lambda s=session_id: self.load_conversation(s),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="View Config",
                command=lambda m=metadata: show_config(m),
                style='Action.TButton'
            ).pack(side=tk.LEFT, padx=(0, 5))

            ttk.Button(
                btn_frame,
                text="Delete",
                command=lambda s=session_id: self.delete_conversation(s),
                style='Select.TButton'
            ).pack(side=tk.LEFT)

    def load_conversation(self, session_id):
        """Load a conversation from history by session_id"""
        log_message(f"CUSTOM_CODE_TAB: Loading conversation {session_id}")

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        conversation = self.chat_interface.chat_history_manager.load_conversation(session_id)
        if not conversation:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to load conversation: {session_id}")
            return

        # Switch to chat tab
        self.sub_notebook.select(self.chat_tab_frame)

        # Load the conversation into the chat interface
        self.chat_interface.chat_history = conversation.get("chat_history", [])
        self.chat_interface.current_model = conversation.get("model_name")
        self.chat_interface.current_session_id = session_id
        self.chat_interface.model_label.config(text=self.chat_interface.current_model)
        self.chat_interface.redisplay_conversation()
        self.chat_interface.add_message("system", f"✓ Loaded conversation: {session_id}")

    def delete_conversation(self, session_id):
        """Delete a conversation from history by session_id"""
        from tkinter import messagebox

        if not hasattr(self, 'chat_interface') or not self.chat_interface or not self.chat_interface.chat_history_manager:
            return

        if messagebox.askyesno(
            "Delete Conversation",
            f"Are you sure you want to delete this conversation?\n\n{session_id}"
        ):
            if self.chat_interface.chat_history_manager.delete_conversation(session_id):
                messagebox.showinfo("Deleted", "Conversation deleted successfully")
                self.refresh_history()
            else:
                messagebox.showerror("Error", "Failed to delete conversation")

    def create_placeholder_tab(self, parent, title):
        """Create a placeholder tab for future features"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        container = ttk.Frame(parent, style='Category.TFrame')
        container.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)

        ttk.Label(
            container,
            text=f"🚧 {title}",
            font=("Arial", 16, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(pady=20)

        ttk.Label(
            container,
            text="This feature is planned for future development.",
            font=("Arial", 10),
            style='Config.TLabel'
        ).pack(pady=10)

    def create_right_panel(self, parent):
        """Create right side panel with model selector"""
        right_panel = ttk.Frame(parent, width=300, style='Category.TFrame')
        right_panel.grid(row=0, column=1, sticky=tk.NSEW, padx=(10, 10), pady=10)
        right_panel.grid_propagate(False)  # Maintain fixed width
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        # Header
        header = ttk.Frame(right_panel, style='Category.TFrame')
        header.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))

        ttk.Label(
            header,
            text="🤖 Ollama Models",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Button(
            header,
            text="🔄",
            command=self.refresh_model_list,
            style='Select.TButton',
            width=3
        ).pack(side=tk.RIGHT)

        # Model list frame with scrollbar
        list_container = ttk.Frame(right_panel, style='Category.TFrame')
        list_container.grid(row=1, column=0, sticky=tk.NSEW)
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        self.model_canvas = tk.Canvas(
            list_container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.model_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.model_canvas.yview
        )
        self.model_scroll_frame = ttk.Frame(self.model_canvas, style='Category.TFrame')

        self.model_scroll_frame.bind(
            "<Configure>",
            lambda e: self.model_canvas.configure(scrollregion=self.model_canvas.bbox("all"))
        )

        self.model_canvas_window = self.model_canvas.create_window(
            (0, 0),
            window=self.model_scroll_frame,
            anchor="nw"
        )
        self.model_canvas.configure(yscrollcommand=self.model_scrollbar.set)

        # Bind resize to adjust canvas window width
        self.model_canvas.bind(
            "<Configure>",
            lambda e: self.model_canvas.itemconfig(self.model_canvas_window, width=e.width)
        )

        self.model_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.model_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling for model list
        self.bind_mousewheel_to_canvas(self.model_canvas)

        # Load models
        self.refresh_model_list()

    def refresh_model_list(self):
        """Refresh the Ollama model list"""
        log_message("CUSTOM_CODE_TAB: Refreshing model list...")

        # Clear existing
        for widget in self.model_scroll_frame.winfo_children():
            widget.destroy()

        # Import config to get models
        try:
            from config import get_ollama_models
            models = get_ollama_models()
            log_message(f"CUSTOM_CODE_TAB: Found {len(models)} Ollama models")
        except Exception as e:
            log_message(f"CUSTOM_CODE_TAB ERROR: Failed to get models: {e}")
            models = []

        if not models:
            ttk.Label(
                self.model_scroll_frame,
                text="No Ollama models found",
                style='Config.TLabel'
            ).pack(pady=20, padx=10)
            return

        # Display each model as a button
        for model in models:
            model_btn = ttk.Button(
                self.model_scroll_frame,
                text=model,
                command=lambda m=model: self.select_model(m),
                style='Category.TButton'
            )
            model_btn.pack(fill=tk.X, padx=5, pady=2)

    def select_model(self, model_name):
        """Handle model selection"""
        log_message(f"CUSTOM_CODE_TAB: Model selected: {model_name}")

        # Update chat interface with selected model
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_model(model_name)

    def get_chat_interface_scores(self):
        """Get the real-time evaluation scores from the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            return self.chat_interface.get_realtime_eval_scores()
        return {}

    def set_training_mode(self, enabled):
        """Set the training mode for the chat interface"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_training_mode(enabled)

    def on_mode_changed(self, mode, params):
        """Handle mode changes from the settings tab"""
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.set_mode_parameters(mode, params)

    def on_closing(self):
        """Handle application close - save chat history"""
        log_message("CUSTOM_CODE_TAB: Application closing, saving chat history...")

        # Save chat history before closing
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.save_on_exit()

        # Close the application
        self.root.destroy()

    def refresh_tab(self):
        """Refresh the entire tab"""
        log_message("CUSTOM_CODE_TAB: Refreshing tab...")
        self.refresh_model_list()
        if hasattr(self, 'chat_interface') and self.chat_interface:
            self.chat_interface.refresh()
