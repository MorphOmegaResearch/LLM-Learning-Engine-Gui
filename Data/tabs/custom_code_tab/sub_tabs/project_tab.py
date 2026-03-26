"""
Project Tab — Thin BaseTab wrapper that embeds a GUILLM environment.
Each project gets its own isolated scanner, applier, chat, and modes.
Spawned by the Projects hub in custom_code_tab.py.
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class ProjectTab(BaseTab):
    """Embeds a GUILLMApp instance inside a BaseTab frame."""

    def __init__(self, parent, root, style, project_id: str, project_config: dict):
        super().__init__(parent, root, style)
        self.project_id = project_id
        self.project_config = project_config
        # "local" = scan only this tab's frame; "global" = scan entire app
        self.scan_target = project_config.get("scan_target", "local")
        self.guillm_app = None

    def create_ui(self):
        """Create the GUILLM environment inside self.parent."""
        # Route sandbox events to a separate log file for isolated debugging
        if self.project_config.get('type') == 'sandbox':
            try:
                import logger_util as _lu
                _lu.init_sandbox_log(self.project_id)
                _lu.log_sandbox_event(f"Sandbox spawn: {self.project_id} "
                                      f"tab={self.project_config.get('tab_name')} "
                                      f"version={self.project_config.get('version_ts')}")
            except Exception as _e:
                log_message(f"PROJECT_TAB: sandbox log init failed: {_e}")

        log_message(f"PROJECT_TAB: Creating GUILLM env for {self.project_id}")

        from .guillm import OllamaManager, GUIScanner, ChangeApplier, ProfileManager, GUILLMApp

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Determine what the scanner can see
        scanner_root = self.parent if self.scan_target == "local" else self.root

        # Each project gets its own isolated instances
        ollama = OllamaManager()
        scanner = GUIScanner(scanner_root)
        applier = ChangeApplier(scanner)
        profiles = ProfileManager()

        # Build the embedded GUILLM UI into our frame
        self.guillm_app = GUILLMApp.create_embedded(
            parent_frame=self.parent,
            root=self.root,
            ollama=ollama,
            scanner=scanner,
            applier=applier,
            profiles=profiles,
            project_id=self.project_id
        )

        self.register_feature(f"project_{self.project_id}", status="active")

        # Hook embedded GUILLM notebook into BaseTab probe/right-click system
        if hasattr(self.guillm_app, 'notebook'):
            self.bind_sub_notebook(self.guillm_app.notebook, label='GUILLM')

        log_message(f"PROJECT_TAB: {self.project_id} ready")

    def get_project_state(self) -> dict:
        """Return serializable state for persistence."""
        return {
            "project_id": self.project_id,
            "model": getattr(self.guillm_app, 'current_model', None) if self.guillm_app else None,
            "chat_count": len(getattr(self.guillm_app, 'chat_history', [])) if self.guillm_app else 0,
            "scan_target": self.scan_target
        }
