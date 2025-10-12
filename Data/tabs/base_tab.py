"""
Base class for all GUI tabs
Provides common interface and error handling
"""

import tkinter as tk
from tkinter import ttk, messagebox
from abc import ABC, abstractmethod
from logger_util import log_message


class BaseTab(ABC):
    """Base class for modular GUI tabs"""

    def __init__(self, parent, root, style):
        """
        Initialize the tab.

        Args:
            parent: Parent frame (the notebook tab frame)
            root: Root Tkinter window
            style: ttk.Style object for theming
        """
        self.parent = parent
        self.root = root
        self.style = style
        self.initialized = False

    @abstractmethod
    def create_ui(self):
        """
        Create the tab UI.
        Must be implemented by subclasses.
        """
        pass

    def safe_create(self):
        """
        Safely create the tab UI with error handling and logging.
        Returns True if successful, False otherwise.
        """
        tab_name = self.__class__.__name__
        log_message(f"BASE_TAB: Attempting to create tab: {tab_name}")
        try:
            self.create_ui()
            self.initialized = True
            log_message(f"BASE_TAB: Successfully created tab: {tab_name}")
            return True
        except Exception as e:
            log_message(f"BASE_TAB ERROR: Failed to create tab: {tab_name}. Error: {e}")
            import traceback
            log_message(f"BASE_TAB TRACEBACK: {traceback.format_exc()}")
            self._show_error(e)
            return False

    def _show_error(self, error):
        """Display error message in the tab."""
        error_frame = ttk.Frame(self.parent)
        error_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Use pack inside error_frame (not parent which uses grid)
        ttk.Label(
            error_frame,
            text="⚠️ Tab Failed to Load",
            font=("Arial", 16, "bold"),
            foreground="#ff6b6b"
        ).pack(pady=10)

        ttk.Label(
            error_frame,
            text=f"Error: {str(error)}",
            font=("Arial", 10),
            foreground="#ff6b6b"
        ).pack(pady=5)

        ttk.Label(
            error_frame,
            text="This tab encountered an error. Other tabs should still work.",
            font=("Arial", 9)
        ).pack(pady=5)

        def reload_tab():
            # Clear error display
            for widget in self.parent.winfo_children():
                widget.destroy()
            # Try to reload
            self.safe_create()

        ttk.Button(
            error_frame,
            text="🔄 Retry",
            command=reload_tab
        ).pack(pady=10)

    def bind_mousewheel_to_canvas(self, canvas):
        """
        Bind mousewheel scrolling to a canvas widget.
        This enables natural scrolling when hovering over the canvas.
        Works on Windows, Mac, and Linux.

        Args:
            canvas: tk.Canvas widget to bind mousewheel to
        """
        import platform
        system = platform.system()

        if system == "Linux":
            # Linux uses Button-4 (scroll up) and Button-5 (scroll down)
            def _on_mousewheel_up(event):
                canvas.yview_scroll(-1, "units")

            def _on_mousewheel_down(event):
                canvas.yview_scroll(1, "units")

            def _on_enter(event):
                canvas.bind_all("<Button-4>", _on_mousewheel_up)
                canvas.bind_all("<Button-5>", _on_mousewheel_down)

            def _on_leave(event):
                canvas.unbind_all("<Button-4>")
                canvas.unbind_all("<Button-5>")

            canvas.bind("<Enter>", _on_enter)
            canvas.bind("<Leave>", _on_leave)

        else:
            # Windows and Mac use MouseWheel event
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")

            def _on_enter(event):
                canvas.bind_all("<MouseWheel>", _on_mousewheel)

            def _on_leave(event):
                canvas.unbind_all("<MouseWheel>")

            canvas.bind("<Enter>", _on_enter)
            canvas.bind("<Leave>", _on_leave)

    def refresh(self):
        """
        Refresh tab content.
        Override in subclasses if needed.
        """
        pass
