"""
CollectionsTab — Universal Entity Browser, CRUD & Taxonomy Import.
#[Mark:UNIVERSAL_CATALOG_COLLECTIONS]

Part of Project_Universal_Catalog_005.
Provides entity browsing, creation, detail view, and seed_pack taxonomy import.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import json
import datetime
from pathlib import Path

# ── Optional imports (graceful fallback) ─────────────────────────────────────
try:
    from modules.meta_learn_agriculture import (
        KnowledgeForgeApp, Entity, EntityType, HealthStatus
    )
    _KF_OK = True
except ImportError:
    _KF_OK = False

try:
    from modules.ag_importer import stream_tsv_file, filter_by_focus, populate_ag_forge_data
    _IMPORTER_OK = True
except ImportError:
    _IMPORTER_OK = False

_SEED_PACK = Path(__file__).parents[3] / "modules" / "Imports" / "seed_pack"


class CollectionsTab(ttk.Frame):
    """Entity browser with CRUD, detail panel, and taxonomy import."""

    def __init__(self, parent, app_ref=None):
        super().__init__(parent)
        self.knowledge_forge = getattr(app_ref, 'knowledge_forge', None)
        self._build_ui()
        self._refresh_tree()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ── Top toolbar ──────────────────────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky='ew', padx=5, pady=(5, 0))

        ttk.Button(toolbar, text="+ Create Entity", command=self._show_create_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Import Taxonomy", command=self._show_import_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Export JSON", command=self._export_json).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_tree).pack(side=tk.LEFT, padx=2)

        # Filter bar
        ttk.Label(toolbar, text="    Filter:").pack(side=tk.LEFT, padx=(10, 2))
        self._filter_type_var = tk.StringVar(value="All")
        type_values = ["All"]
        if _KF_OK:
            type_values += [t.value for t in EntityType]
        self._filter_type = ttk.Combobox(toolbar, textvariable=self._filter_type_var,
                                          values=type_values, state='readonly', width=15)
        self._filter_type.pack(side=tk.LEFT, padx=2)
        self._filter_type.bind("<<ComboboxSelected>>", lambda e: self._refresh_tree())

        self._filter_text_var = tk.StringVar()
        filter_entry = ttk.Entry(toolbar, textvariable=self._filter_text_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=2)
        filter_entry.bind("<Return>", lambda e: self._refresh_tree())
        ttk.Button(toolbar, text="Search", command=self._refresh_tree).pack(side=tk.LEFT, padx=2)

        # Entity count label
        self._count_label = ttk.Label(toolbar, text="")
        self._count_label.pack(side=tk.RIGHT, padx=5)

        # ── Main paned area ──────────────────────────────────────────────────
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # Left: entity tree
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        cols = ("type", "species", "health", "location")
        self._tree = ttk.Treeview(left_frame, columns=cols, show="tree headings", selectmode="browse")
        self._tree.heading("#0", text="Name")
        self._tree.heading("type", text="Type")
        self._tree.heading("species", text="Species")
        self._tree.heading("health", text="Health")
        self._tree.heading("location", text="Location")
        self._tree.column("#0", width=180)
        self._tree.column("type", width=80)
        self._tree.column("species", width=140)
        self._tree.column("health", width=70)
        self._tree.column("location", width=100)

        vsb = ttk.Scrollbar(left_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: detail panel
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)

        self._detail = scrolledtext.ScrolledText(
            right_frame, wrap=tk.WORD, font=('Consolas', 9), bg='#f8f9fa', state=tk.DISABLED
        )
        self._detail.grid(row=0, column=0, sticky='nsew')
        self._detail.tag_configure("header", font=('Consolas', 11, 'bold'), foreground='#2c3e50')
        self._detail.tag_configure("label", font=('Consolas', 9, 'bold'), foreground='#2980b9')
        self._detail.tag_configure("section", font=('Consolas', 10, 'bold'), foreground='#27ae60')

        # Map iid -> entity_id for selection
        self._iid_to_eid = {}

    # ── Tree population ──────────────────────────────────────────────────────

    def _refresh_tree(self):
        """Reload entity tree from KnowledgeForgeApp data."""
        self._tree.delete(*self._tree.get_children())
        self._iid_to_eid.clear()

        if not self.knowledge_forge:
            self._tree.insert("", "end", text="KnowledgeForge not available", values=("", "", "", ""))
            self._count_label.config(text="0 entities")
            return

        # Reload data from disk in case external changes
        try:
            self.knowledge_forge._load_data()
        except Exception:
            pass

        entities = list(self.knowledge_forge.entities.values())

        # Apply filters
        type_filter = self._filter_type_var.get()
        text_filter = self._filter_text_var.get().strip().lower()

        if type_filter != "All":
            entities = [e for e in entities if e.type.value == type_filter]
        if text_filter:
            entities = [e for e in entities
                        if text_filter in e.name.lower()
                        or text_filter in e.species.lower()
                        or text_filter in e.description.lower()
                        or any(text_filter in t.lower() for t in e.tags)]

        # Group by category
        categories = {}
        for e in entities:
            cat = e.category or "Uncategorized"
            categories.setdefault(cat, []).append(e)

        for cat in sorted(categories.keys()):
            cat_node = self._tree.insert("", "end", text=f"{cat} ({len(categories[cat])})",
                                          values=("", "", "", ""), open=True)
            for entity in sorted(categories[cat], key=lambda x: x.name):
                health = entity.health_status.value if hasattr(entity.health_status, 'value') else str(entity.health_status)
                etype = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
                iid = self._tree.insert(cat_node, "end", text=entity.name,
                                         values=(etype, entity.species, health, entity.location))
                self._iid_to_eid[iid] = entity.id

        self._count_label.config(text=f"{len(entities)} entities")

    # ── Detail panel ─────────────────────────────────────────────────────────

    def _on_select(self, event=None):
        sel = self._tree.selection()
        if not sel:
            return
        eid = self._iid_to_eid.get(sel[0])
        if not eid or not self.knowledge_forge:
            return
        entity = self.knowledge_forge.entities.get(eid)
        if not entity:
            return
        self._show_entity_detail(entity)

    def _show_entity_detail(self, entity):
        self._detail.config(state=tk.NORMAL)
        self._detail.delete(1.0, tk.END)

        etype = entity.type.value if hasattr(entity.type, 'value') else str(entity.type)
        health = entity.health_status.value if hasattr(entity.health_status, 'value') else str(entity.health_status)

        self._detail.insert(tk.END, f"{entity.name}\n", "header")
        self._detail.insert(tk.END, f"[{etype}]  ID: {entity.id}\n\n")

        self._detail.insert(tk.END, "Basic Info\n", "section")
        for label, val in [
            ("Species", entity.species), ("Breed", entity.breed),
            ("Category", entity.category), ("Location", entity.location),
            ("Health", health), ("Confidence", f"{entity.confidence_score:.0%}"),
            ("Birth Date", entity.birth_date or "—"),
            ("Acquired", entity.acquisition_date or "—"),
            ("Last Updated", entity.last_updated or "—"),
        ]:
            if val and val != "—":
                self._detail.insert(tk.END, f"  {label}: ", "label")
                self._detail.insert(tk.END, f"{val}\n")

        if entity.description:
            self._detail.insert(tk.END, f"\n  Description: ", "label")
            self._detail.insert(tk.END, f"{entity.description}\n")

        if entity.tags:
            self._detail.insert(tk.END, f"  Tags: ", "label")
            self._detail.insert(tk.END, f"{', '.join(entity.tags)}\n")

        # Health Records
        if entity.health_records:
            self._detail.insert(tk.END, f"\nHealth Records ({len(entity.health_records)})\n", "section")
            for rec in entity.health_records[-5:]:  # show last 5
                date = rec.date if hasattr(rec, 'date') else rec.get('date', '?')
                diag = rec.diagnosis if hasattr(rec, 'diagnosis') else rec.get('diagnosis', '')
                notes = rec.notes if hasattr(rec, 'notes') else rec.get('notes', '')
                self._detail.insert(tk.END, f"  [{date}] {diag or 'checkup'}")
                if notes:
                    self._detail.insert(tk.END, f" — {notes}")
                self._detail.insert(tk.END, "\n")

        # Documents
        if entity.documents:
            self._detail.insert(tk.END, f"\nDocuments ({len(entity.documents)})\n", "section")
            for doc in entity.documents:
                title = doc.title if hasattr(doc, 'title') else doc.get('title', '?')
                dtype = doc.type if hasattr(doc, 'type') else doc.get('type', '')
                self._detail.insert(tk.END, f"  {title} [{dtype}]\n")

        # Associations
        assoc_labels = [
            ("Diseases", entity.disease_associations),
            ("Parasites", entity.parasite_associations),
            ("Nutrients", entity.nutrient_associations),
            ("Locations", entity.location_associations),
            ("Offspring", entity.offspring_ids),
        ]
        has_assoc = any(v for _, v in assoc_labels)
        if has_assoc:
            self._detail.insert(tk.END, "\nAssociations\n", "section")
            for label, items in assoc_labels:
                if items:
                    self._detail.insert(tk.END, f"  {label}: ", "label")
                    self._detail.insert(tk.END, f"{', '.join(str(i) for i in items)}\n")

        self._detail.config(state=tk.DISABLED)

    # ── Create Entity dialog ─────────────────────────────────────────────────

    def _show_create_dialog(self):
        if not self.knowledge_forge:
            messagebox.showwarning("Unavailable", "KnowledgeForge not loaded.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Create Entity")
        dlg.geometry("400x420")
        dlg.transient(self)

        fields = {}
        row = 0
        for label, key, widget_type in [
            ("Name *", "name", "entry"),
            ("Type", "type", "combo"),
            ("Category", "category", "entry"),
            ("Species", "species", "entry"),
            ("Breed", "breed", "entry"),
            ("Location", "location", "entry"),
            ("Description", "description", "text"),
        ]:
            tk.Label(dlg, text=label).grid(row=row, column=0, sticky='w', padx=10, pady=3)
            if widget_type == "entry":
                var = tk.StringVar()
                ttk.Entry(dlg, textvariable=var, width=35).grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "combo":
                var = tk.StringVar(value="Animal")
                vals = [t.value for t in EntityType] if _KF_OK else ["Animal", "Plant", "Equipment"]
                cb = ttk.Combobox(dlg, textvariable=var, values=vals, state='readonly', width=32)
                cb.grid(row=row, column=1, padx=10, pady=3)
                fields[key] = var
            elif widget_type == "text":
                txt = tk.Text(dlg, height=4, width=35)
                txt.grid(row=row, column=1, padx=10, pady=3)
                fields[key] = txt
            row += 1

        def _create():
            name = fields["name"].get().strip()
            if not name:
                messagebox.showwarning("Required", "Name is required.", parent=dlg)
                return
            type_str = fields["type"].get()
            entity_type = EntityType(type_str) if _KF_OK else type_str
            desc = fields["description"].get("1.0", tk.END).strip() if isinstance(fields["description"], tk.Text) else ""
            data = {
                'name': name,
                'type': entity_type,
                'category': fields["category"].get().strip() or "General",
                'species': fields["species"].get().strip(),
                'breed': fields["breed"].get().strip(),
                'location': fields["location"].get().strip(),
                'description': desc,
            }
            try:
                eid = self.knowledge_forge.create_entity(data)
                messagebox.showinfo("Created", f"Entity created: {eid}", parent=dlg)
                dlg.destroy()
                self._refresh_tree()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(dlg, text="Create", command=_create).grid(row=row, column=0, columnspan=2, pady=15)

    # ── Import Taxonomy dialog ───────────────────────────────────────────────

    def _show_import_dialog(self):
        if not self.knowledge_forge:
            messagebox.showwarning("Unavailable", "KnowledgeForge not loaded.")
            return
        if not _IMPORTER_OK:
            messagebox.showwarning("Unavailable", "ag_importer module not available.")
            return
        if not (_SEED_PACK / "VernacularName.tsv").exists():
            messagebox.showwarning("Missing Data", f"Seed pack not found at:\n{_SEED_PACK}")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Import from Taxonomy (Catalogue of Life)")
        dlg.geometry("450x220")
        dlg.transient(self)

        tk.Label(dlg, text="Focus filter (e.g. 'Aves', 'Bovidae', 'owl'):",
                 font=('Arial', 10)).pack(padx=10, pady=(15, 5), anchor='w')
        focus_var = tk.StringVar(value="")
        ttk.Entry(dlg, textvariable=focus_var, width=40).pack(padx=10, pady=5, anchor='w')

        tk.Label(dlg, text="Domain category for imported entities:",
                 font=('Arial', 10)).pack(padx=10, pady=(10, 5), anchor='w')
        domain_var = tk.StringVar(value="Animal_Husbandry")
        ttk.Entry(dlg, textvariable=domain_var, width=40).pack(padx=10, pady=5, anchor='w')

        progress_var = tk.StringVar(value="")
        progress_label = tk.Label(dlg, textvariable=progress_var, fg='#666')
        progress_label.pack(padx=10, pady=5)

        def _do_import():
            focus = focus_var.get().strip()
            domain = domain_var.get().strip() or "General Agriculture"
            if not focus:
                messagebox.showwarning("Required", "Enter a focus filter keyword.", parent=dlg)
                return
            progress_var.set(f"Importing '{focus}' from seed_pack...")
            dlg.update_idletasks()

            def _run():
                try:
                    data_stream = stream_tsv_file(_SEED_PACK / "VernacularName.tsv")
                    filtered = filter_by_focus(data_stream, [focus])
                    business_focus = {"domain": domain, "keywords": [focus]}
                    populate_ag_forge_data(self.knowledge_forge, filtered, business_focus)
                    def _done():
                        progress_var.set("Import complete!")
                        self._refresh_tree()
                        messagebox.showinfo("Done", f"Import complete for '{focus}'.", parent=dlg)
                    dlg.after(0, _done)
                except Exception as e:
                    def _err():
                        progress_var.set(f"Error: {e}")
                        messagebox.showerror("Import Error", str(e), parent=dlg)
                    dlg.after(0, _err)

            threading.Thread(target=_run, daemon=True).start()

        ttk.Button(dlg, text="Import", command=_do_import).pack(pady=10)

    # ── Export ────────────────────────────────────────────────────────────────

    def _export_json(self):
        if not self.knowledge_forge:
            messagebox.showwarning("Unavailable", "KnowledgeForge not loaded.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="entities_export.json"
        )
        if not path:
            return
        try:
            data = {eid: e.to_dict() for eid, e in self.knowledge_forge.entities.items()}
            Path(path).write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
            messagebox.showinfo("Exported", f"Exported {len(data)} entities to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
