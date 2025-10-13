# Data/tabs/models_tab/overview_panel.py
from tkinter import ttk, StringVar, N, S, E, W
import tkinter as tk
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config

class OverviewPanel(ttk.Frame):
    """
    Models → Overview: base model picker and current Type/class glance.
    """
    def __init__(self, master, *, trainee_name_var: StringVar, base_model_var: StringVar, **kw):
        super().__init__(master, **kw)
        self.trainee_name_var = trainee_name_var
        self.base_model_var = base_model_var

        self.columnconfigure(1, weight=1)

        ttk.Label(self, text="Trainee Name").grid(row=0, column=0, sticky="w", padx=8, pady=(8,4))
        self.ent_name = ttk.Entry(self, textvariable=self.trainee_name_var, width=32)
        self.ent_name.grid(row=0, column=1, sticky=E+W, padx=8, pady=(8,4))

        ttk.Label(self, text="Base Model (torch/ollama id)").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.ent_model = ttk.Entry(self, textvariable=self.base_model_var, width=32)
        self.ent_model.grid(row=1, column=1, sticky=E+W, padx=8, pady=4)

        # Status fields
        self.lbl_type = ttk.Label(self, text="Assigned Type: —")
        self.lbl_type.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(8,4))
        self.lbl_class = ttk.Label(self, text="Class Level: —")
        self.lbl_class.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # Load button
        self.btn_refresh = ttk.Button(self, text="Refresh from Profile", command=self._refresh_from_profile)
        self.btn_refresh.grid(row=4, column=0, columnspan=2, sticky="e", padx=8, pady=(6,8))

    def _refresh_from_profile(self):
        name = (self.trainee_name_var.get() or "").strip()
        if not name:
            self.lbl_type.config(text="Assigned Type: —")
            self.lbl_class.config(text="Class Level: —")
            return
        try:
            mp = config.load_model_profile(name)
        except Exception:
            self.lbl_type.config(text="Assigned Type: —")
            self.lbl_class.config(text="Class Level: —")
            return
        tdisp = mp.get("assigned_type", "—")
        self.lbl_type.config(text=f"Assigned Type: {tdisp}")
        self.lbl_class.config(text=f"Class Level: {mp.get('class_level','novice')}")