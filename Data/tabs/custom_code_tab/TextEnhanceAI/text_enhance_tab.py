"""
TextEnhanceTab — BaseTab wrapper embedding EditorApp into custom_code_tab.
#[Mark:TEXT_ENHANCE_TAB]
"""
import tkinter as tk
from tkinter import ttk
from tabs.base_tab import BaseTab
from logger_util import log_message


class TextEnhanceTab(BaseTab):
    """Embeds EditorApp as a sub-tab of custom_code_tab."""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self._parent_tab = parent_tab
        self._editor = None

    def create_ui(self):
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)
        try:
            from .text_enhance_ai import EditorApp
            self._editor = EditorApp(self.parent)
            log_message("TEXT_ENHANCE_TAB: EditorApp embedded OK")
        except Exception as e:
            import traceback
            log_message(f"TEXT_ENHANCE_TAB: Embed failed: {e}")
            log_message(f"TEXT_ENHANCE_TAB: {traceback.format_exc()}")
            ttk.Label(self.parent, text=f"IDE unavailable:\n{e}",
                      foreground='red', justify='left').grid(
                          row=0, column=0, padx=20, pady=40, sticky='nw')
            self._editor = None

    def set_model(self, model_name, model_info=None):
        """Called by custom_code_tab.select_model() — keeps model in sync."""
        try:
            if self._editor and model_name:
                self._editor.model_var.set(model_name)
        except Exception:
            pass

    def refresh(self):
        try:
            if self._editor:
                self._editor.populate_model_menu()
        except Exception:
            pass
