"""Reusable dialog for reviewing bug details and available fix methods."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Any, Callable, Iterable, Optional


MethodRecordLike = Any

CLASS_ORDER = ("novice", "skilled", "adept", "expert", "master")


def _normalise_method(record: MethodRecordLike) -> dict:
    if record is None:
        return {}
    if hasattr(record, "__dict__"):
        result = dict(record.__dict__)
    elif isinstance(record, dict):
        result = dict(record)
    else:
        result = {"value": str(record)}

    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    requirements = metadata.get("requirements") if isinstance(metadata, dict) else {}
    if "min_class_level" not in result and isinstance(requirements, dict):
        result["min_class_level"] = requirements.get("min_class_level")
    if "required_tools" not in result and isinstance(requirements, dict):
        result["required_tools"] = requirements.get("required_tools")
    if "required_skills" not in result and isinstance(requirements, dict):
        result["required_skills"] = requirements.get("required_skills")
    if "applies_to_types" not in result and isinstance(requirements, dict):
        result["applies_to_types"] = requirements.get("applies_to_types")
    if "applied_class_level" not in result and isinstance(metadata, dict):
        applied_by = metadata.get("applied_by")
        if isinstance(applied_by, dict):
            result["applied_class_level"] = applied_by.get("class_level")
            result["applied_variant"] = applied_by.get("variant_id")
    return result


def _normalise_class(level: Optional[str]) -> Optional[str]:
    if not level:
        return None
    value = str(level).strip().lower()
    return value if value in CLASS_ORDER else None


def _class_allows(required: Optional[str], current: Optional[str]) -> bool:
    req = _normalise_class(required)
    cur = _normalise_class(current)
    if not req or not cur:
        return True
    try:
        return CLASS_ORDER.index(cur) >= CLASS_ORDER.index(req)
    except ValueError:
        return False


def _extract_bug_class(details: dict) -> Optional[str]:
    for key in ("class_level", "agent_class", "model_class"):
        value = details.get(key)
        if isinstance(value, str):
            norm = _normalise_class(value)
            if norm:
                return norm
    return None


def show_fix_dialog(
    parent: tk.Misc,
    bug_details: dict,
    methods: Optional[Iterable[MethodRecordLike]] = None,
    *,
    on_apply_method: Optional[Callable[[dict], None]] = None,
    on_agent_assist: Optional[Callable[[], None]] = None,
    default_action_label: Optional[str] = None,
    on_default_action: Optional[Callable[[], None]] = None,
) -> None:
    """Render the fix workflow dialog."""

    if parent is None:
        raise ValueError("parent widget is required")

    dialog = tk.Toplevel(parent)
    dialog.title("Fix Bug Workflow")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.geometry("720x520")

    container = ttk.Frame(dialog, padding=12)
    container.pack(fill=tk.BOTH, expand=True)

    header = ttk.Label(container, text=_summarise_bug(bug_details), style="CategoryPanel.TLabel", anchor=tk.W, justify=tk.LEFT)
    header.pack(fill=tk.X)

    body = ttk.Frame(container)
    body.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(1, weight=1)

    ttk.Label(body, text="Stored Methods", style="Config.TLabel").grid(row=0, column=0, sticky=tk.W)
    ttk.Label(body, text="Bug Context", style="Config.TLabel").grid(row=0, column=1, sticky=tk.W)

    method_frame = ttk.Frame(body)
    method_frame.grid(row=1, column=0, sticky=tk.NSEW, padx=(0, 6))
    method_columns = ("status", "action", "class", "source")
    tree = ttk.Treeview(method_frame, columns=method_columns, show="headings", height=8)
    tree.heading("status", text="Status")
    tree.heading("action", text="Action")
    tree.heading("class", text="Min Class")
    tree.heading("source", text="Source")
    tree.column("status", width=100, anchor=tk.W)
    tree.column("action", width=180, anchor=tk.W)
    tree.column("class", width=90, anchor=tk.W)
    tree.column("source", width=140, anchor=tk.W)
    tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
    sb = ttk.Scrollbar(method_frame, orient=tk.VERTICAL, command=tree.yview)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    tree.configure(yscrollcommand=sb.set)

    method_records = []
    if methods:
        for rec in methods:
            norm = _normalise_method(rec)
            method_records.append(norm)
    current_class_level = _extract_bug_class(bug_details)
    if method_records:
        for idx, rec in enumerate(method_records):
            min_class = rec.get("min_class_level") or ""
            tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    rec.get("status", "unknown"),
                    rec.get("action_id") or rec.get("action", ""),
                    min_class,
                    rec.get("bug_id", ""),
                ),
            )
    else:
        tree.configure(height=4)
        ttk.Label(method_frame, text="No stored methods yet", foreground="#888888").pack(pady=6)

    context_text = scrolledtext.ScrolledText(body, wrap=tk.WORD, height=16)
    context_text.grid(row=1, column=1, sticky=tk.NSEW)
    context_text.insert(tk.END, _format_bug_context(bug_details))
    context_text.configure(state=tk.DISABLED)

    button_row = ttk.Frame(container)
    button_row.pack(fill=tk.X)

    def _invoke_default():
        if on_default_action:
            on_default_action()
            dialog.destroy()
        else:
            messagebox.showinfo("Fix", "No automated fix available for this action.", parent=dialog)

    def _invoke_method():
        if not on_apply_method:
            messagebox.showinfo("Method", "No method handler connected.", parent=dialog)
            return
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Method", "Select a stored method first.", parent=dialog)
            return
        record = method_records[int(selection[0])]
        required_class = record.get("min_class_level")
        if required_class and not _class_allows(required_class, current_class_level):
            messagebox.showwarning(
                "Method Locked",
                f"This method requires class level '{required_class}'. Current context is '{current_class_level or 'unknown'}'.",
                parent=dialog,
            )
            return
        on_apply_method(record)
        dialog.destroy()

    def _invoke_agent():
        if on_agent_assist:
            on_agent_assist()
            dialog.destroy()
        else:
            messagebox.showinfo("Agent", "No agent workflow connected.", parent=dialog)

    ttk.Button(button_row, text="Close", style="Select.TButton", command=dialog.destroy).pack(side=tk.RIGHT)
    ttk.Button(button_row, text="Ask Agent", command=_invoke_agent).pack(side=tk.RIGHT, padx=6)
    ttk.Button(button_row, text="Apply Stored Method", command=_invoke_method, state=(tk.NORMAL if method_records and on_apply_method else tk.DISABLED)).pack(side=tk.RIGHT, padx=6)
    ttk.Button(
        button_row,
        text=default_action_label or "Run Fix-Flow Action",
        command=_invoke_default,
        state=(tk.NORMAL if on_default_action else tk.DISABLED),
    ).pack(side=tk.LEFT)

    dialog.focus_set()
    dialog.wait_window(dialog)


def _summarise_bug(details: dict) -> str:
    if not details:
        return "Bug details unavailable"
    error = details.get("error_type") or "Unknown error"
    message = details.get("error_message") or ""
    file_path = details.get("file_path") or details.get("file") or "(unknown file)"
    line = details.get("line_number") or "?"
    return f"{error} — {file_path}:{line}\n{message}"


def _format_bug_context(details: dict) -> str:
    parts = []
    if not details:
        return ""
    context = details.get("code_context")
    if isinstance(context, dict):
        lines = context.get("lines", [])
        parts.append("Code Context:\n" + "\n".join(f"{ln.get('line_num','')}: {ln.get('content','')}" for ln in lines))
    elif isinstance(context, list):
        parts.append("Code Context:\n" + "\n".join(str(line) for line in context))
    tb = details.get("stack_trace")
    if tb:
        if isinstance(tb, list):
            parts.append("\nStack Trace:\n" + "\n".join(str(line) for line in tb))
        else:
            parts.append("\nStack Trace:\n" + str(tb))
    if details.get("metadata"):
        try:
            parts.append("\nMetadata:\n" + json.dumps(details["metadata"], indent=2))
        except Exception:
            pass
    return "\n\n".join(parts).strip()
