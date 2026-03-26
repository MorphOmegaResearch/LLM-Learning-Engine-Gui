"""Method Bank sub-tab for the models tab notebook."""

from __future__ import annotations

from tkinter import ttk

try:
    from tabs.custom_code_tab.sub_tabs.components import show_method_bank
except Exception:  # pragma: no cover - optional component
    show_method_bank = None


class MethodBankTab(ttk.Frame):
    def __init__(self, parent, root):
        super().__init__(parent)
        self.root = root
        self._build_ui()

    def _build_ui(self):
        if not callable(show_method_bank):
            ttk.Label(
                self,
                text="Method Bank viewer is unavailable in this build.",
                foreground="#888888"
            ).pack(padx=20, pady=20)
            return

        ttk.Button(
            self,
            text="Open Method Bank",
            command=lambda: show_method_bank(self.root)
        ).pack(padx=20, pady=20)
