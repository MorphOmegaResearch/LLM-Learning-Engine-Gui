# Data/tabs/models_tab/types_panel.py
from tkinter import ttk, StringVar, END, N, S, E, W
import tkinter as tk
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config

class TypesPanel(ttk.Frame):
    """
    Models → Types: choose a Type for the selected trainee (Model Profile),
    preview its training recipes & first evals, and Apply Type Plan.
    """

    def __init__(self, master, *, trainee_name_var: StringVar, base_model_var: StringVar, **kw):
        super().__init__(master, **kw)
        self.trainee_name_var = trainee_name_var
        self.base_model_var = base_model_var
        self.catalog = config.load_type_catalog()
        self.type_ids = [t.get("id") for t in self.catalog.get("types", [])]
        self.selected_type = StringVar(value=self.type_ids[0] if self.type_ids else "")

        # --- Layout
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        # Left: list of types
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky=N+S+E+W, padx=8, pady=8)
        ttk.Label(left, text="Types").pack(anchor="w")
        self.lst = tk.Listbox(left, height=10, exportselection=False)
        self.lst.pack(fill="both", expand=True)
        for tid in self.type_ids:
            self.lst.insert(END, tid)
        self.lst.bind("<<ListboxSelect>>", self._on_select)

        # Right: details
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky=N+S+E+W, padx=8, pady=8)
        right.columnconfigure(0, weight=1)

        self.lbl_title = ttk.Label(right, text="Type: —", font=("TkDefaultFont", 11, "bold"))
        self.lbl_title.grid(row=0, column=0, sticky="w", pady=(0,6))

        self.txt_details = tk.Text(right, height=16, wrap="word")
        self.txt_details.grid(row=1, column=0, sticky=N+S+E+W)
        right.rowconfigure(1, weight=1)

        # Actions
        actions = ttk.Frame(right)
        actions.grid(row=2, column=0, sticky="e", pady=6)
        self.btn_apply = ttk.Button(actions, text="Apply Type Plan", command=self._apply_plan)
        self.btn_apply.grid(row=0, column=0, padx=(0,6))
        self.btn_view_profile = ttk.Button(actions, text="Open Model Profile", command=self._open_profile_file)
        self.btn_view_profile.grid(row=0, column=1)

        # Init selection
        if self.type_ids:
            self.lst.selection_set(0)
            self._render_details(self.type_ids[0])

    def set_context_getters(self, get_trainee=None, get_base_model=None):
        self._get_trainee = get_trainee or (lambda: None)
        self._get_base_model = get_base_model or (lambda: None)

    # --- internals
    def _on_select(self, _evt=None):
        sel = self.lst.curselection()
        if not sel:
            return
        tid = self.lst.get(sel[0])
        self.selected_type.set(tid)
        self._render_details(tid)

    def _render_details(self, type_id: str):
        t = config.get_type_by_id(type_id) or {}
        title = f"{t.get('display_name','?')}  ({type_id})"
        skills = "\n • ".join(t.get("skills_tree", [])) or "—"
        recipes = "\n • ".join(t.get("default_training_recipes", [])) or "—"
        evals = "\n • ".join(t.get("first_evals", [])) or "—"
        self.lbl_title.config(text=f"Type: {title}")
        self.txt_details.delete("1.0", END)
        self.txt_details.insert(END, f"Skills Tree:\n • {skills}\n\n")
        self.txt_details.insert(END, f"Default Training Recipes:\n • {recipes}\n\n")
        self.txt_details.insert(END, f"First Evals:\n • {evals}\n")

    def _apply_plan(self):
        from tkinter import messagebox
        trainee_name = (self._get_trainee() or self.trainee_name_var.get() or "").strip()
        base_model = (self._get_base_model() or self.base_model_var.get() or "").strip()
        type_id = self.selected_type.get()
        if not trainee_name or not base_model or not type_id:
            messagebox.showinfo("Types", "Select trainee name, base model, and type first.")
            return
        # Load-or-create + persist model profile
        mp = {}
        try:
            mp = config.load_model_profile(trainee_name)
        except Exception:
            mp = {"trainee_name": trainee_name, "base_model": base_model, "assigned_type": type_id}
        mp.update({
            "trainee_name": trainee_name,
            "base_model": base_model,
            "assigned_type": type_id
        })
        # Save (atomic/.bak/dir-fsync guarded)
        config.save_model_profile(trainee_name, mp)
        self._status(f"Applied Type Plan: {type_id} → profile '{trainee_name}' saved.")

        # Create/update Training Profile
        try:
            config.upsert_training_profile_for_model(trainee_name, base_model, type_id)
        except Exception as e:
            print("[Types] training profile upsert failed:", e)

        # Emit event for ModelsTab to forward to Training tab
        try:
            self.event_generate("<<TypePlanApplied>>", when="tail")
        except Exception:
            pass

    def _open_profile_file(self):
        # Non-blocking: just say where it is; OS integration can be added later.
        from pathlib import Path
        p = Path("Data/profiles/Models") / f"{self.trainee_name_var.get().strip()}.json"
        self._status(f"Model Profile path: {p}")

    def _status(self, msg: str):
        # Lightweight UX status—hook into app status bar if available
        try:
            from tkinter import messagebox
            messagebox.showinfo("Types", msg)
        except Exception:
            print("[Types]", msg)
