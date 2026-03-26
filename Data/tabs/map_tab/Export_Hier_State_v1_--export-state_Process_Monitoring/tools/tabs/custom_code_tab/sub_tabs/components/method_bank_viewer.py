"""Interactive viewer for method bank entries (Fixed Bugs)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import Iterable, Callable, Optional, Dict
import json


try:
    from method_bank import load_catalog
except Exception:  # pragma: no cover
    load_catalog = None


def show_method_bank(parent: tk.Misc, on_open_bug: Optional[Callable[[str], None]] = None) -> None:
    if not callable(load_catalog):
        messagebox.showinfo("Method Bank", "Method bank catalog is not available.", parent=parent)
        return

    catalog = load_catalog()
    records: Iterable = getattr(catalog, 'methods', []) if catalog else []

    dialog = tk.Toplevel(parent)
    dialog.title("Method Bank")
    dialog.geometry("780x520")
    dialog.transient(parent)
    dialog.grab_set()

    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)

    hdr = ttk.Frame(frame)
    hdr.pack(fill=tk.X)
    ttk.Label(hdr, text="Stored fix methods", style="CategoryPanel.TLabel").pack(side=tk.LEFT)

    control_row = ttk.Frame(frame)
    control_row.pack(fill=tk.X, pady=(8, 4))
    ttk.Label(control_row, text="Status:").pack(side=tk.LEFT)
    status_var = tk.StringVar(value="All")
    status_box = ttk.Combobox(control_row, textvariable=status_var, state='readonly', width=14)
    status_box.pack(side=tk.LEFT, padx=(4, 20))
    ttk.Label(control_row, text="Search:").pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(control_row, textvariable=search_var, width=32)
    search_entry.pack(side=tk.LEFT, padx=4)

    tree = ttk.Treeview(frame, columns=("bug", "action", "status", "class", "path", "ts"), show="headings", height=12)
    tree.heading("bug", text="Bug ID")
    tree.heading("action", text="Action")
    tree.heading("status", text="Status")
    tree.heading("class", text="Min Class")
    tree.heading("path", text="Path")
    tree.heading("ts", text="Timestamp")
    tree.column("bug", width=160, anchor=tk.W)
    tree.column("action", width=180, anchor=tk.W)
    tree.column("status", width=100, anchor=tk.W)
    tree.column("class", width=90, anchor=tk.W)
    tree.column("path", width=200, anchor=tk.W)
    tree.column("ts", width=120, anchor=tk.W)
    tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=scrollbar.set)

    detail = scrolledtext.ScrolledText(frame, height=10, width=40, state=tk.DISABLED, wrap=tk.WORD)
    detail.pack(fill=tk.X, pady=(6, 0))

    dataset: list[Dict[str, str]] = []
    for rec in records:
        if hasattr(rec, '__dict__'):
            data = dict(rec.__dict__)
        elif isinstance(rec, dict):
            data = dict(rec)
        else:
            data = {"value": str(rec)}
        dataset.append(data)
    if dataset:
        statuses = sorted({(rec.get("status") or "unknown").title() for rec in dataset})
    else:
        statuses = []
    status_box.configure(values=["All"] + statuses)
    try:
        status_box.current(0)
    except Exception:
        pass

    def _format_metadata(meta):
        try:
            return json.dumps(meta or {}, indent=2)
        except Exception:
            return str(meta)

    filtered = list(dataset)

    def _update_detail(_event=None):
        selection = tree.selection()
        detail.configure(state=tk.NORMAL)
        detail.delete(1.0, tk.END)
        if not selection:
            detail.insert(tk.END, "Select a method to view details.")
        else:
            rec = filtered[int(selection[0])]
            metadata = rec.get('metadata') if isinstance(rec.get('metadata'), dict) else {}
            requirements = metadata.get('requirements') if isinstance(metadata, dict) else {}
            min_class = rec.get('min_class_level') or requirements.get('min_class_level') or "(not specified)"
            required_tools = rec.get('required_tools') or requirements.get('required_tools') or []
            required_skills = rec.get('required_skills') or requirements.get('required_skills') or []
            applies_types = rec.get('applies_to_types') or requirements.get('applies_to_types') or []
            applied_block = rec.get('applied_by') if isinstance(rec.get('applied_by'), dict) else {}
            applied_class = rec.get('applied_class_level') or applied_block.get('class_level')
            applied_variant = rec.get('applied_variant') or applied_block.get('variant_id')

            info_lines = [
                f"Bug ID: {rec.get('bug_id','')}",
                f"Signature: {rec.get('signature','')}",
                f"Action: {rec.get('action_id','')}",
                f"Status: {(rec.get('status') or 'unknown').title()}",
                f"Timestamp: {rec.get('timestamp','')}",
                f"File: {rec.get('file_path','')}:{rec.get('line_number','')}",
                f"Min Class: {min_class}",
            ]
            if required_tools:
                info_lines.append(f"Required Tools: {', '.join(required_tools)}")
            if required_skills:
                info_lines.append(f"Required Skills: {', '.join(required_skills)}")
            if applies_types:
                info_lines.append(f"Applies To Types: {', '.join(applies_types)}")
            if applied_class or applied_variant:
                descriptors = []
                if applied_class:
                    descriptors.append(f"class={applied_class}")
                if applied_variant:
                    descriptors.append(f"variant={applied_variant}")
                info_lines.append(f"Captured By: {', '.join(descriptors)}")
            info_lines.extend([
                "",
                "Metadata:",
                _format_metadata(metadata) or "(none)",
            ])
            detail.insert(tk.END, "\n".join(info_lines))
        detail.configure(state=tk.DISABLED)

    def refresh_tree(*_args):
        search_text = search_var.get().lower().strip()
        status_filter = status_var.get()
        filtered.clear()
        for rec in dataset:
            status_val = (rec.get("status") or "unknown").title()
            if status_filter != "All" and status_val != status_filter:
                continue
            haystack = " ".join(str(rec.get(key, "")) for key in ("bug_id", "action_id", "file_path", "metadata"))
            if search_text and search_text not in haystack.lower():
                continue
            filtered.append(rec)
        tree.delete(*tree.get_children())
        for idx, rec in enumerate(filtered):
            metadata = rec.get('metadata') if isinstance(rec.get('metadata'), dict) else {}
            requirements = metadata.get('requirements') if isinstance(metadata, dict) else {}
            min_class = rec.get("min_class_level") or requirements.get("min_class_level") or ""
            tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    rec.get("bug_id", ""),
                    rec.get("action_id", ""),
                    (rec.get("status") or "unknown").title(),
                    min_class,
                    rec.get("file_path", ""),
                    rec.get("timestamp", ""),
                ),
            )
        _update_detail()

    refresh_tree()

    tree.bind("<<TreeviewSelect>>", _update_detail)
    search_var.trace_add('write', refresh_tree)
    status_var.trace_add('write', refresh_tree)

    def _open_selected():
        if not callable(on_open_bug):
            dialog.destroy()
            return
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Method Bank", "Select a method first.", parent=dialog)
            return
        record = filtered[int(selection[0])]
        on_open_bug(record.get("bug_id"))
        dialog.destroy()

    def _copy_selected():
        selection = tree.selection()
        if not selection:
            return
        rec = filtered[int(selection[0])]
        payload = json.dumps(rec, indent=2) if rec else ""
        root = dialog.winfo_toplevel()
        root.clipboard_clear()
        root.clipboard_append(payload)

    btn_bar = ttk.Frame(frame)
    btn_bar.pack(fill=tk.X, pady=(8, 0))
    ttk.Button(btn_bar, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
    ttk.Button(btn_bar, text="Copy", command=_copy_selected, state=tk.NORMAL if filtered else tk.DISABLED).pack(side=tk.RIGHT, padx=4)
    ttk.Button(btn_bar, text="Open Fix Dialog", command=_open_selected, state=(tk.NORMAL if filtered and on_open_bug else tk.DISABLED)).pack(side=tk.RIGHT, padx=8)

    parent_focus = search_entry if dataset else dialog
    try:
        parent_focus.focus_set()
    except Exception:
        pass
    dialog.wait_window(dialog)
