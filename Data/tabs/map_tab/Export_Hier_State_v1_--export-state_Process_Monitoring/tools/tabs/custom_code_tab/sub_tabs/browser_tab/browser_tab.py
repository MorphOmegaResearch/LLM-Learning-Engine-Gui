"""
Browser Tab (Phase 1.6E)

Main browser automation tab with two sub-tabs:
1. Web Browser: GUI automation and testing controls
2. File Browser: File system navigation and management
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')

# Import sub-tabs
from .web_browser_tab import WebBrowserTab
from .file_browser_tab import FileBrowserTab


class BrowserTab(BaseTab):
    """Main browser tab with Web Browser and File Browser sub-tabs"""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab

    def create_ui(self):
        """Create the browser tab UI with sub-tabs"""
        log_message("BROWSER_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Create notebook for sub-tabs
        self.sub_notebook = ttk.Notebook(self.parent)
        self.sub_notebook.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)

        # Create sub-tab frames
        self.web_browser_frame = ttk.Frame(self.sub_notebook, style='Category.TFrame')
        self.file_browser_frame = ttk.Frame(self.sub_notebook, style='Category.TFrame')

        # Add to notebook
        self.sub_notebook.add(self.web_browser_frame, text="🌐 Web Browser")
        self.sub_notebook.add(self.file_browser_frame, text="📁 File Browser")

        # Initialize sub-tabs
        try:
            self.web_browser_tab = WebBrowserTab(
                self.web_browser_frame,
                self.root,
                self.style,
                parent_tab=self
            )
            self.web_browser_tab.create_ui()
            log_message("BROWSER_TAB: Web Browser sub-tab created")
        except Exception as e:
            log_message(f"BROWSER_TAB ERROR: Failed to create Web Browser tab: {e}")
            ttk.Label(
                self.web_browser_frame,
                text=f"Error loading Web Browser: {e}",
                foreground="#ff6b6b"
            ).pack(pady=20)

        try:
            self.file_browser_tab = FileBrowserTab(
                self.file_browser_frame,
                self.root,
                self.style,
                parent_tab=self
            )
            self.file_browser_tab.create_ui()
            log_message("BROWSER_TAB: File Browser sub-tab created")
        except Exception as e:
            log_message(f"BROWSER_TAB ERROR: Failed to create File Browser tab: {e}")
            ttk.Label(
                self.file_browser_frame,
                text=f"Error loading File Browser: {e}",
                foreground="#ff6b6b"
            ).pack(pady=20)

        log_message("BROWSER_TAB: UI created successfully")

    def on_show(self):
        """Called when tab becomes visible"""
        log_message("BROWSER_TAB: Tab shown")
        # Refresh sub-tabs if needed
        if hasattr(self, 'web_browser_tab') and hasattr(self.web_browser_tab, 'on_show'):
            self.web_browser_tab.on_show()
        if hasattr(self, 'file_browser_tab') and hasattr(self.file_browser_tab, 'on_show'):
            self.file_browser_tab.on_show()

    def on_hide(self):
        """Called when tab becomes hidden"""
        log_message("BROWSER_TAB: Tab hidden")
