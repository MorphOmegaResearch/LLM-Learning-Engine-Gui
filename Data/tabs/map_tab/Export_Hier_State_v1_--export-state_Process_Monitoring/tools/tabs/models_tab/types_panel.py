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
        # Only log count, not entire catalog (prevents false bug capture)
        print(f"[DEBUG] TypesPanel: Catalog loaded, {len(self.catalog.get('types', []))} types")
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
        self.txt_details.insert(END, f"First Evals:\n • {evals}\n\n")

        # Phase 2E: Schema capability warnings
        classes_data = t.get('classes', {})
        if classes_data:
            self.txt_details.insert(END, "Schema Requirements:\n")

            # Novice/Skilled require schemas
            if 'novice' in classes_data or 'skilled' in classes_data:
                self.txt_details.insert(END, " • Novice/Skilled: Schemas REQUIRED for tool execution\n")

            # Adept makes schemas optional (schema-free testing gate)
            if 'adept' in classes_data:
                self.txt_details.insert(END, " • Adept: Schemas OPTIONAL (schema-free capability unlocked)\n")

            # Expert/Master/Grand Master operate schema-free
            schema_free_classes = [cls for cls in ['expert', 'master', 'grand_master'] if cls in classes_data]
            if schema_free_classes:
                self.txt_details.insert(END, f" • {'/'.join([c.replace('_', ' ').title() for c in schema_free_classes])}: Schema-free operation\n")

        self._refresh_context_label()
        self._refresh_base_header()

    def _apply_plan(self):
        import config
        import json
        # Gather context
        base_model = (self._get_base_model() or "").strip()
        type_id = self._current_type_id
        trainee_name = (self.name_var.get() or "").strip() or config.derive_variant_name(base_model, type_id)

        # NEW: Check for inheritance opportunities
        # Get or create lineage_id for the base model
        lineage_id = None
        try:
            # Try to find existing lineage from same base by loading profiles
            profiles = config.list_model_profiles() or []
            for p in profiles:
                if p.get('base_model') == base_model:
                    try:
                        mp0 = config.load_model_profile(p.get('variant_id')) or {}
                        lid0 = mp0.get('lineage_id')
                        if lid0:
                            lineage_id = lid0
                            break
                    except Exception:
                        continue

            # If no lineage found, will create new one
            if not lineage_id:
                import ulid
                lineage_id = str(ulid.ULID())
        except Exception:
            import ulid
            lineage_id = str(ulid.ULID())

        # Evaluate inheritance eligibility
        eligibility = config.evaluate_inheritance_eligibility(base_model, lineage_id, type_id)

        # DEBUG: Log eligibility results
        print(f"[TypesPanel] Inheritance eligibility check:")
        print(f"  - Base model: {base_model}")
        print(f"  - Lineage ID: {lineage_id}")
        print(f"  - Type: {type_id}")
        print(f"  - Eligible variants: {len(eligibility['eligible_variants'])}")
        print(f"  - Recommendation: {eligibility['recommendation']}")
        print(f"  - Reason: {eligibility['reason']}")

        mp = None
        inherited_from = None

        # Always show inheritance dialog (even if no eligible variants)
        dialog = InheritanceDecisionDialog(
            self,
            base_model=base_model,
            type_id=type_id,
            eligibility=eligibility
        )
        self.wait_window(dialog)

        if dialog.result == "inherit":
            # Build profile with inherited data
            inherited_data = dialog.selected_inheritance or {}
            inherited_from = inherited_data.get("variant_id")

            # Handle XP inheritance - support both old int and new dict formats
            inherited_xp = inherited_data.get("xp", 0)
            if isinstance(inherited_xp, dict):
                xp_total = inherited_xp.get("total", 0)
            else:
                xp_total = int(inherited_xp) if isinstance(inherited_xp, (int, float)) else 0

            mp = {
                "trainee_name": trainee_name,
                "base_model": base_model,
                "assigned_type": type_id,
                "class_level": inherited_data.get("class_level", "novice"),
                "lineage_id": lineage_id,
                "xp": {"total": xp_total, "history": []},
                "latest_eval_score": inherited_data.get("eval_score", 0.0),
                "tool_proficiency": inherited_data.get("tool_proficiency", {}),
                "inherited_from": inherited_from,
                "linked_adapters": inherited_data.get("adapters", [])
            }
            self._status(f"Inheriting from '{inherited_from}' at class '{mp['class_level']}'")
        elif dialog.result == "hybrid":
            # Hybrid type - merge multiple types
            inherited_data = dialog.selected_inheritance or {}
            variant_data = inherited_data.get("variant", {})
            inherited_from = variant_data.get("variant_id")
            hybrid_types = inherited_data.get("hybrid_types", [type_id])

            # Handle XP inheritance for hybrid - support both old int and new dict formats
            variant_xp = variant_data.get("xp", 0)
            if isinstance(variant_xp, dict):
                xp_total = variant_xp.get("total", 0)
            else:
                xp_total = int(variant_xp) if isinstance(variant_xp, (int, float)) else 0

            mp = {
                "trainee_name": trainee_name,
                "base_model": base_model,
                "assigned_type": hybrid_types,  # List for hybrids
                "class_level": inherited_data.get("inherit_class", variant_data.get("class_level", "novice")),
                "lineage_id": lineage_id,
                "xp": {"total": xp_total, "history": []},
                "latest_eval_score": variant_data.get("eval_score", 0.0),
                "tool_proficiency": variant_data.get("tool_proficiency", {}),
                "inherited_from": inherited_from,
                "linked_adapters": inherited_data.get("selected_adapters", []),
                "hybrid_meta": {
                    "types": hybrid_types,
                    "source_variant": inherited_from,
                    "created": config.get_iso_timestamp()
                }
            }
            self._status(f"Creating hybrid [{'/'.join(hybrid_types)}] from '{inherited_from}'")
        elif dialog.result == "new":
            # Fresh novice profile
            mp = self._build_fresh_profile(trainee_name, base_model, type_id, lineage_id)
        else:
            # Cancelled
            return

        # 1) Save Model Profile
        pth = config.save_model_profile(trainee_name, mp)
        try:
            # Ensure lineage_id is persisted
            config.ensure_lineage_id(trainee_name)
        except Exception:
            pass

        # 2) Upsert Training Profile from Type mapping
        config.upsert_training_profile_for_model(trainee_name, base_model, type_id)

        # 2.5) Sync Bundle Registry with new profile
        try:
            from registry.bundle_loader import sync_bundles_from_profiles
            log_message(f"TYPES_PANEL: Syncing bundle registry after Type creation: {trainee_name}")
            sync_result = sync_bundles_from_profiles(verbose=False)
            if sync_result and sync_result.get('errors'):
                log_message(f"TYPES_PANEL: Bundle sync warnings: {sync_result.get('errors')}")
            elif sync_result:
                log_message(f"TYPES_PANEL: Bundle sync complete - created={sync_result.get('bundles_created', 0)}, updated={sync_result.get('bundles_updated', 0)}")
        except Exception as exc:
            log_message(f"TYPES_PANEL: Failed to sync bundles after Type creation: {exc}")

        # 3) Toast / status
        if inherited_from:
            self._status(f"Applied Type Plan: {type_id} → '{trainee_name}' created (inherited from {inherited_from})\nSaved: {pth}")
        else:
            self._status(f"Applied Type Plan: {type_id} → profile '{trainee_name}' saved (fresh novice)\nSaved: {pth}")

        # 4) Fire event with clean payload and refresh Collections directly as fallback
        try:
            payload_dict = {
                "variant_id": trainee_name,
                "base_model": base_model,
                "type_id": type_id,
                "lineage_id": lineage_id,
                "inherited_from": inherited_from
            }
            # Add hybrid flag if this is a hybrid variant
            if isinstance(mp.get('assigned_type'), list):
                payload_dict["is_hybrid"] = True
                payload_dict["hybrid_types"] = mp.get('assigned_type', [])

            payload = json.dumps(payload_dict)
            self.event_generate("<<TypePlanApplied>>", data=payload, when="tail")
            # WO-6x: Global ProfilesChanged notification
            self.event_generate("<<ProfilesChanged>>", data=payload, when="tail")
            try:
                # Also bubble to toplevel for global listeners
                self.winfo_toplevel().event_generate("<<ProfilesChanged>>", data=payload, when="tail")
            except Exception:
                pass
        except Exception:
            # Fallback: attach attributes if JSON event data not supported
            try:
                evt = tk.Event()
                evt.details = {
                    "variant_id": trainee_name,
                    "base_model": base_model,
                    "type_id": type_id,
                    "inherited_from": inherited_from
                }
                self.event_generate("<<TypePlanApplied>>", when="tail")
                self.event_generate("<<ProfilesChanged>>", when="tail")
            except Exception:
                pass
        # Hard refresh fallback (walk up to find ModelsTab)
        try:
            parent = self
            while parent is not None:
                if hasattr(parent, 'refresh_collections_panel'):
                    parent.refresh_collections_panel()
                    break
                parent = parent.master
        except Exception:
            pass
        # After successful apply, reset dirty state
        self._variant_dirty = False
        self._update_apply_state()
        self._refresh_context_label()
        self._refresh_base_header()

    def _build_fresh_profile(self, trainee_name: str, base_model: str, type_id: str, lineage_id: str) -> dict:
        """Build a fresh novice profile with no inheritance"""
        return {
            "trainee_name": trainee_name,
            "base_model": base_model,
            "assigned_type": type_id,
            "class_level": "novice",
            "lineage_id": lineage_id,
            "xp": 0,
            "latest_eval_score": 0.0,
        }

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


# ===== Inheritance Decision Dialog =====

class InheritanceDecisionDialog(tk.Toplevel):
    """
    Popup dialog for choosing between inheriting from an existing variant or creating a fresh one.
    Shows available variants with their stats, conformance to gates, and available adapters.
    """

    def __init__(self, parent, base_model: str, type_id: str, eligibility: dict):
        super().__init__(parent)
        self.title("Apply Type Plan - Inheritance Decision")
        self.geometry("800x600")
        self.configure(bg='#2b2b2b')

        self.base_model = base_model
        self.type_id = type_id
        self.eligibility = eligibility
        self.result = None  # Will be "inherit", "new", or None (cancelled)
        self.selected_inheritance = None  # Will contain selected data if result == "inherit"

        # Track selected variant and options
        self.selected_variant_id = None
        self.selected_class = tk.StringVar()
        self.adapter_selections = {}  # {adapter_path: BooleanVar}

        self._create_ui()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def _create_ui(self):
        # Header
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(
            header,
            text=f"Apply Type Plan: {self.type_id}",
            font=("Arial", 14, "bold")
        ).pack(anchor=tk.W)

        ttk.Label(
            header,
            text=f"Base Model: {self.base_model}",
            font=("Arial", 10)
        ).pack(anchor=tk.W)

        ttk.Separator(self, orient='horizontal').pack(fill=tk.X, pady=5)

        # Recommendation banner
        rec_color = "#51cf66" if self.eligibility["recommendation"] == "inherit" else "#ffd43b"
        rec_frame = tk.Frame(self, bg=rec_color)
        rec_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(
            rec_frame,
            text=f"💡 {self.eligibility['reason']}",
            bg=rec_color,
            fg="#000000",
            font=("Arial", 9, "bold"),
            wraplength=750
        ).pack(padx=10, pady=5)

        # Scrollable list of variants
        list_label = ttk.Label(self, text="Available Inheritance Options:", font=("Arial", 11, "bold"))
        list_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(canvas_frame, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Display each eligible variant
        self.variant_radios = {}
        for variant in self.eligibility["eligible_variants"]:
            self._create_variant_option(scrollable_frame, variant)

        if not self.eligibility["eligible_variants"]:
            ttk.Label(
                scrollable_frame,
                text="No existing variants found. Creating a fresh novice is the only option.",
                foreground="#888888"
            ).pack(padx=20, pady=20)

        # Buttons at bottom
        ttk.Separator(self, orient='horizontal').pack(fill=tk.X, pady=5)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        self.inherit_btn = ttk.Button(
            button_frame,
            text="Inherit Type",
            style='Action.TButton',
            command=self._on_inherit
        )
        self.inherit_btn.pack(side=tk.LEFT, padx=(0, 10))

        if not self.eligibility["eligible_variants"]:
            self.inherit_btn.config(state=tk.DISABLED)

        self.new_btn = ttk.Button(
            button_frame,
            text="New Type (Fresh Novice)",
            style='Select.TButton',
            command=self._on_new
        )
        self.new_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Add Hybrid Type button (initially disabled)
        self.hybrid_btn = ttk.Button(
            button_frame,
            text="Hybrid Type",
            style='Action.TButton',
            command=self._on_hybrid,
            state=tk.DISABLED
        )
        self.hybrid_btn.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel
        ).pack(side=tk.RIGHT)

    def _create_variant_option(self, parent, variant: dict):
        """Create a radio button option for a single variant with all its details"""
        variant_id = variant["variant_id"]

        # Outer frame
        outer = ttk.Frame(parent, style='Category.TFrame', borderwidth=1, relief="solid")
        outer.pack(fill=tk.X, padx=5, pady=5)

        # Radio button row
        radio_frame = ttk.Frame(outer)
        radio_frame.pack(fill=tk.X, padx=10, pady=5)

        radio_var = tk.BooleanVar(value=False)
        radio = ttk.Radiobutton(
            radio_frame,
            text=f"{variant_id} [{variant['class_level']}]",
            variable=radio_var,
            command=lambda: self._on_variant_selected(variant_id, radio_var)
        )
        radio.pack(side=tk.LEFT)
        self.variant_radios[variant_id] = radio_var

        # Add badges for cross-type and cross-lineage
        if variant.get('cross_type'):
            tk.Label(
                radio_frame,
                text=f"[cross-type from {variant.get('assigned_type', 'unknown')}]",
                fg='#ffd43b',
                bg='#2b2b2b',
                font=("Arial", 9, "bold")
            ).pack(side=tk.LEFT, padx=(5, 2))

        if variant.get('cross_lineage'):
            tk.Label(
                radio_frame,
                text="[cross-lineage]",
                fg='#51cf66',
                bg='#2b2b2b',
                font=("Arial", 9, "bold")
            ).pack(side=tk.LEFT, padx=(5, 2))

        # Stats row
        stats_text = f"XP: {variant['xp']} | Eval: {variant['eval_score']:.1%} | Skills: {len(variant['skills_verified'])}"
        ttk.Label(
            outer,
            text=stats_text,
            font=("Arial", 9)
        ).pack(anchor=tk.W, padx=30, pady=2)

        # Tool proficiency badges
        if variant["tool_proficiency"]:
            prof_frame = ttk.Frame(outer)
            prof_frame.pack(anchor=tk.W, padx=30, pady=2)

            ttk.Label(prof_frame, text="Proficiency: ", font=("Arial", 9)).pack(side=tk.LEFT)

            grade_counts = {}
            for tool, data in variant["tool_proficiency"].items():
                grade = data.get('grade', 'F')
                grade_counts[grade] = grade_counts.get(grade, 0) + 1

            for grade in ['AAA', 'AA', 'A', 'B', 'C', 'F']:
                if grade in grade_counts:
                    colors = {
                        'AAA': '#00ff00', 'AA': '#7fff00', 'A': '#ffff00',
                        'B': '#ffa500', 'C': '#ff6347', 'F': '#ff0000'
                    }
                    tk.Label(
                        prof_frame,
                        text=f"[{grade}] x{grade_counts[grade]}",
                        fg=colors[grade],
                        bg='#2b2b2b',
                        font=("Arial", 9, "bold")
                    ).pack(side=tk.LEFT, padx=2)

        # Adapters row
        adapters = variant["adapters"]
        if adapters:
            ada_text = f"Adapters: {len(adapters)} available"
            ttk.Label(outer, text=ada_text, font=("Arial", 9)).pack(anchor=tk.W, padx=30, pady=2)

        # Conformance status
        conf = variant["conformance"]
        if conf["meets_gates"]:
            status_text = "✅ Meets all gates for current class"
            status_color = "#00ff00"
        else:
            status_text = f"⚠️ Missing: {', '.join(conf['missing'][:3])}"
            if len(conf["missing"]) > 3:
                status_text += f" (+{len(conf['missing']) - 3} more)"
            status_color = "#ffd43b"

        ttk.Label(
            outer,
            text=status_text,
            foreground=status_color,
            font=("Arial", 9)
        ).pack(anchor=tk.W, padx=30, pady=2)

        # Expandable options (class + adapters) - only shown when selected
        options_frame = ttk.Frame(outer)
        # Will be packed when variant is selected

        # Class selection dropdown
        if variant["class_level"] != "novice":
            class_select_frame = ttk.Frame(options_frame)
            class_select_frame.pack(fill=tk.X, padx=30, pady=5)

            ttk.Label(class_select_frame, text="Inherit as class:", font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 5))

            # Options: novice through current class (matches type_catalog_v2.json)
            class_hierarchy = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master']
            current_idx = class_hierarchy.index(variant["class_level"]) if variant["class_level"] in class_hierarchy else 0
            available_classes = class_hierarchy[:current_idx + 1]

            class_combo = ttk.Combobox(
                class_select_frame,
                textvariable=self.selected_class,
                values=available_classes,
                state="readonly",
                width=15
            )
            class_combo.set(variant["class_level"])
            class_combo.pack(side=tk.LEFT)

        # Adapter checkboxes
        if adapters:
            ada_select_frame = ttk.Frame(options_frame)
            ada_select_frame.pack(fill=tk.X, padx=30, pady=5)

            ttk.Label(ada_select_frame, text="Link adapters:", font=("Arial", 9, "bold")).pack(anchor=tk.W)

            for adapter in adapters:
                ada_path = adapter["path"]
                ada_var = tk.BooleanVar(value=False)
                self.adapter_selections[ada_path] = ada_var

                ttk.Checkbutton(
                    ada_select_frame,
                    text=f"{adapter['name']} [{adapter['class_level']}]",
                    variable=ada_var
                ).pack(anchor=tk.W, padx=10)

        # Store reference to options frame for show/hide
        outer._options_frame = options_frame
        outer._variant_id = variant_id

    def _on_variant_selected(self, variant_id: str, selected_var: tk.BooleanVar):
        """Handle variant radio button selection"""
        # Unselect all others
        for vid, var in self.variant_radios.items():
            if vid != variant_id:
                var.set(False)

        selected_var.set(True)
        self.selected_variant_id = variant_id

        # Find selected variant data to check if it's cross-type
        selected_variant = None
        for v in self.eligibility["eligible_variants"]:
            if v["variant_id"] == variant_id:
                selected_variant = v
                break

        # Toggle buttons based on cross-type selection
        if selected_variant and selected_variant.get('cross_type'):
            # Cross-type variant selected - enable Hybrid Type if class >= skilled
            self.inherit_btn.config(state=tk.DISABLED)
            self.new_btn.config(state=tk.DISABLED)

            # Enable Hybrid Type only if class is skilled or higher
            class_hierarchy = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master']
            current_class = selected_variant.get('class_level', 'novice')
            if current_class in class_hierarchy and class_hierarchy.index(current_class) >= 1:  # >= skilled
                self.hybrid_btn.config(state=tk.NORMAL)
            else:
                self.hybrid_btn.config(state=tk.DISABLED)
        else:
            # Normal variant - enable inherit and new, disable hybrid
            self.inherit_btn.config(state=tk.NORMAL if self.eligibility["eligible_variants"] else tk.DISABLED)
            self.new_btn.config(state=tk.NORMAL)
            self.hybrid_btn.config(state=tk.DISABLED)

        # Show/hide options frames
        for child in self.winfo_children():
            for frame in child.winfo_children():
                if hasattr(frame, '_options_frame') and hasattr(frame, '_variant_id'):
                    if frame._variant_id == variant_id:
                        frame._options_frame.pack(fill=tk.X, before=frame.winfo_children()[-1])
                    else:
                        frame._options_frame.pack_forget()

    def _on_inherit(self):
        """Handle Inherit Type button click"""
        if not self.selected_variant_id:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a variant to inherit from.")
            return

        # Find selected variant data
        selected_variant = None
        for v in self.eligibility["eligible_variants"]:
            if v["variant_id"] == self.selected_variant_id:
                selected_variant = v
                break

        if not selected_variant:
            return

        # Gather selected options
        selected_class = self.selected_class.get() or selected_variant["class_level"]
        selected_adapters = [
            path for path, var in self.adapter_selections.items()
            if var.get()
        ]

        self.selected_inheritance = {
            "variant_id": self.selected_variant_id,
            "class_level": selected_class,
            "xp": selected_variant["xp"],
            "skills": selected_variant["skills_verified"],
            "tool_proficiency": selected_variant["tool_proficiency"],
            "adapters": selected_adapters,
            "eval_score": selected_variant["eval_score"]
        }

        self.result = "inherit"
        self.destroy()

    def _on_new(self):
        """Handle New Type button click"""
        self.result = "new"
        self.destroy()

    def _on_hybrid(self):
        """Handle Hybrid Type button click - for cross-type hybrids"""
        if not self.selected_variant_id:
            from tkinter import messagebox
            messagebox.showwarning("No Selection", "Please select a cross-type variant to create hybrid from.")
            return

        # Find selected variant data
        selected_variant = None
        for v in self.eligibility["eligible_variants"]:
            if v["variant_id"] == self.selected_variant_id:
                selected_variant = v
                break

        if not selected_variant or not selected_variant.get('cross_type'):
            from tkinter import messagebox
            messagebox.showwarning("Invalid Selection", "Hybrid Type requires a cross-type variant selection.")
            return

        # Collect selected options
        self.result = "hybrid"
        self.selected_inheritance = {
            "variant": selected_variant,
            "inherit_class": self.selected_class.get() or selected_variant["class_level"],
            "selected_adapters": [
                path for path, var in self.adapter_selections.items() if var.get()
            ],
            "hybrid_types": [self.type_id, selected_variant.get('assigned_type', 'unassigned')]
        }
        self.destroy()

    def _on_cancel(self):
        """Handle Cancel button click"""
        self.result = None
        self.destroy()
