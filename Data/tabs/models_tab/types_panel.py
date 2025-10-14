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
        print("[DEBUG] TypesPanel: __init__ called")
        self.trainee_name_var = trainee_name_var
        self.base_model_var = base_model_var
        self._variant_dirty = False
        self.catalog = config.load_type_catalog()
        print(f"[DEBUG] TypesPanel: Catalog loaded, types: {self.catalog.get('types', [])}")
        self.type_ids = [t.get("id") for t in self.catalog.get("types", [])]
        print(f"[DEBUG] TypesPanel: type_ids: {self.type_ids}")
        self.selected_type = StringVar(value=self.type_ids[0] if self.type_ids else "")
        self._current_type_id = self.selected_type.get()

        # --- Layout
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)
        print("[DEBUG] TypesPanel: Layout configured")

        # Left: list of types
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky=N+S+E+W, padx=8, pady=8)
        ttk.Label(left, text="Types").pack(anchor="w")
        self.lst = tk.Listbox(left, height=10, exportselection=False)
        self.lst.pack(fill="both", expand=True)
        for tid in self.type_ids:
            self.lst.insert(END, tid)
        self.lst.bind("<<ListboxSelect>>", self._on_select)
        self.bind("<<ModelSelected>>", self._on_model_selected) # Bind to the panel itself
        print("[DEBUG] TypesPanel: Left frame (listbox) created")

        # Right: details
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky=N+S+E+W, padx=8, pady=8)
        right.columnconfigure(0, weight=1)
        print("[DEBUG] TypesPanel: Right frame created")

        # Base model header (requested UX)
        self.base_hdr_var = tk.StringVar(value="Base Model: < Please Select Model >")
        self.lbl_base = ttk.Label(right, textvariable=self.base_hdr_var, style='Config.TLabel')
        self.lbl_base.grid(row=0, column=0, sticky="w", pady=(0,4))

        self.lbl_title = ttk.Label(right, text="Type: —", font=("TkDefaultFont", 11, "bold"))
        self.lbl_title.grid(row=1, column=0, sticky="w", pady=(0,6))

        self.txt_details = tk.Text(right, height=12, wrap="word")
        self.txt_details.grid(row=2, column=0, sticky=N+S+E+W)
        right.rowconfigure(2, weight=1)

        # Context summary (base + type)
        self.context_var = tk.StringVar(value="Base: — | Type: —")
        self.lbl_context = ttk.Label(right, textvariable=self.context_var, style='Config.TLabel')
        self.lbl_context.grid(row=3, column=0, sticky="w", pady=(4, 0))

        # --- WO-6a: Variant name input ----------------------
        self.name_frame = ttk.Frame(right)
        self.name_frame.grid(row=4, column=0, sticky="ew", pady=(6, 2))
        ttk.Label(self.name_frame, text="Variant Name:").pack(side=tk.LEFT, padx=(0,6))
        self.name_var = tk.StringVar(value="")
        self.name_entry = ttk.Entry(self.name_frame, textvariable=self.name_var, width=40)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        # Mark variant name as dirty on user edits
        try:
            self.name_entry.bind("<KeyRelease>", lambda _e: (setattr(self, "_variant_dirty", True), self._update_apply_state()))
        except Exception:
            pass
        # ----------------------------------------------------

        # Actions
        actions = ttk.Frame(right)
        actions.grid(row=5, column=0, sticky="e", pady=6)
        self.btn_apply = ttk.Button(actions, text="Apply Type Plan", style='Action.TButton', command=self._apply_plan)
        self.btn_apply.grid(row=0, column=0, padx=(0,6))
        # WO-6q: Reload Types button
        self.btn_reload = ttk.Button(actions, text="Reload Types", command=self._reload_types)
        self.btn_reload.grid(row=0, column=2, padx=(6,0))
        self.btn_view_profile = ttk.Button(actions, text="Open Model Profile", command=self._open_profile_file)
        self.btn_view_profile.grid(row=0, column=1)

        # Init selection
        if self.type_ids:
            self.lst.selection_set(0)
            self._render_details(self.type_ids[0])
            print("[DEBUG] TypesPanel: Initial selection and render details called")
        else:
            print("[DEBUG] TypesPanel: No type_ids, skipping initial selection and render details")
        # Initial button state
        self._update_apply_state()
        self._refresh_context_label()
        self._refresh_base_header()

    def set_context_getters(self, get_trainee=None, get_base_model=None):
        self._get_trainee = get_trainee or (lambda: None)
        self._get_base_model = get_base_model or (lambda: None)

    def _prefill_variant_name(self, base_model: str, type_id: str):
        try:
            import config
            # prefer derive_variant_name if present
            if hasattr(config, "derive_variant_name"):
                vid = config.derive_variant_name(base_model, type_id)
            else:
                vid = f"{(base_model or '').replace(' ', '_').replace('-Instruct','')}_{type_id}"
            if not getattr(self, "_variant_dirty", False):
                self.name_var.set(vid)
        except Exception:
            pass

    def _on_model_selected(self, event=None):
        # Diagnostics: show whether we received payload data
        try:
            has_data = bool(event and hasattr(event, "data") and event.data)
            print(f"[TypesPanel][diag] _on_model_selected: has_data={has_data}")
        except Exception:
            has_data = False

        # Primary path: parse event.data, set base and prefill
        if has_data:
            try:
                import json
                data = json.loads(event.data)
                model_name = data.get("model_name")
                model_type = data.get("model_type")
                print(f"[TypesPanel][diag] event.data parsed: model_name={model_name}, model_type={model_type}")
                if model_name:
                    self.trainee_name_var.set(model_name)
                    self.base_model_var.set(model_name)
                    self.name_var.set("")
                    self._variant_dirty = False
                    if self._current_type_id:
                        self._prefill_variant_name(self.base_model_var.get(), self._current_type_id)
            except Exception as e:
                print(f"[TypesPanel] Error handling ModelSelected event: {e}")

        # Fallback: derive base via context getter if data wasn't present or parse failed
        try:
            base = (self._get_base_model() or "").strip()
            if base:
                self.base_model_var.set(base)
                print(f"[TypesPanel][diag] fallback base from getter: {base}")
                if self._current_type_id:
                    self._prefill_variant_name(base, self._current_type_id)
        except Exception:
            pass

        # Recompute state and refresh labels
        self._update_apply_state()
        self._refresh_context_label()
        self._refresh_base_header()

    # --- internals
    def _on_select(self, _evt=None):
        sel = self.lst.curselection()
        if not sel:
            return
        tid = self.lst.get(sel[0])
        self.selected_type.set(tid)
        self._current_type_id = tid
        # Always prefill variant name when a type is selected
        self._prefill_variant_name(self.base_model_var.get(), tid)
        self._update_apply_state()
        self._render_details(tid)
        self._refresh_context_label()
        self._refresh_base_header()

    def _render_details(self, type_id: str):
        t = config.get_type_by_id(type_id) or {}
        title = f"{t.get('display_name','?')}  ({type_id})"
        skills = "\n • ".join(t.get("skills_tree", [])) or "—"
        recipes = "\n • ".join(t.get("default_training_recipes", [])) or "—"
        evals = "\n • ".join(t.get("first_evals", [])) or "—"
        self.lbl_title.config(text=f"Type: {title}")
        try:
            # config module is already imported at the top of the file
            base = (self._get_base_model() or "").strip()
            default_name = config.derive_variant_name(base, type_id)
            # Always refresh the variant name when rendering details
            if not getattr(self, "_variant_dirty", False):
                self.name_var.set(default_name)
        except Exception:
            pass
        self.txt_details.delete("1.0", END)
        self.txt_details.insert(END, f"Skills Tree:\n • {skills}\n\n")
        self.txt_details.insert(END, f"Default Training Recipes:\n • {recipes}\n\n")
        self.txt_details.insert(END, f"First Evals:\n • {evals}\n")
        self._refresh_context_label()
        self._refresh_base_header()

    def _apply_plan(self):
        import config
        # Gather context
        base_model = (self._get_base_model() or "").strip()
        type_id = self._current_type_id
        trainee_name = (self.name_var.get() or "").strip() or config.derive_variant_name(base_model, type_id)

        # 1) Save Model Profile
        mp = {
            "trainee_name": trainee_name,
            "base_model": base_model,
            "assigned_type": type_id,
            "class_level": "novice",
        }
        config.save_model_profile(trainee_name, mp)

        # 2) Upsert Training Profile from Type mapping
        config.upsert_training_profile_for_model(trainee_name, base_model, type_id)

        # 3) Toast / status
        self._status(f"Applied Type Plan: {type_id} → profile '{trainee_name}' saved.")

        # 4) Fire event with clean payload
        try:
            import json
            payload = json.dumps({
                "variant_id": trainee_name,
                "base_model": base_model,
                "type_id": type_id,
            })
            self.event_generate("<<TypePlanApplied>>", data=payload, when="tail")
            # WO-6x: Global ProfilesChanged notification
            self.event_generate("<<ProfilesChanged>>", data=payload, when="tail")
        except Exception:
            # Fallback: attach attributes if JSON event data not supported
            try:
                evt = tk.Event()
                evt.details = {"variant_id": trainee_name, "base_model": base_model, "type_id": type_id}
                self.event_generate("<<TypePlanApplied>>", when="tail")
                self.event_generate("<<ProfilesChanged>>", when="tail")
            except Exception:
                pass
        # After successful apply, reset dirty state
        self._variant_dirty = False
        self._update_apply_state()
        self._refresh_context_label()
        self._refresh_base_header()

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

    def _update_apply_state(self):
        try:
            has_base = bool((self.base_model_var.get() or "").strip())
            has_type = bool((self._current_type_id or "").strip())
            state = (tk.NORMAL if (has_base and has_type) else tk.DISABLED)
            if hasattr(self, 'btn_apply'):
                self.btn_apply.config(state=state)
            print(f"[TypesPanel][diag] _update_apply_state: has_base={has_base}, has_type={has_type}, state={'NORMAL' if state==tk.NORMAL else 'DISABLED'}")
        except Exception:
            pass

    def _refresh_context_label(self):
        try:
            base = (self.base_model_var.get() or "—").strip() or "—"
            t = (self._current_type_id or "—").strip() or "—"
            self.context_var.set(f"Base: {base} | Type: {t}")
        except Exception:
            pass

    def _refresh_base_header(self):
        try:
            base = (self.base_model_var.get() or "").strip()
            if base:
                self.base_hdr_var.set(f"Base Model: < {base} >")
            else:
                self.base_hdr_var.set("Base Model: < Please Select Model >")
        except Exception:
            pass

    # WO-6q: Reload type catalog and repopulate list, preserving selection when possible
    def _reload_types(self):
        try:
            self.catalog = config.load_type_catalog()
            self.type_ids = [t.get("id") for t in self.catalog.get("types", [])]
            # Rebuild listbox
            self.lst.delete(0, END)
            for tid in self.type_ids:
                self.lst.insert(END, tid)
            # Keep current type if still present
            cur = self._current_type_id if self._current_type_id in self.type_ids else (self.type_ids[0] if self.type_ids else "")
            if cur:
                idx = self.type_ids.index(cur)
                self.lst.selection_clear(0, END)
                self.lst.selection_set(idx)
                self.selected_type.set(cur)
                self._current_type_id = cur
                self._render_details(cur)
            self._update_apply_state()
            self._status("Types reloaded.")
        except Exception as e:
            self._status(f"Reload failed: {e}")
