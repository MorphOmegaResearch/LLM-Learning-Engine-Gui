"""
Unified Undo Changes Dialog
Provides comprehensive UI for viewing, analyzing, and undoing individual changes.
#[Mark:UNDO_POPUP_UNIFIED]
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import logger_util
import recovery_util


class UndoChangesDialog:
    """
    Unified dialog for managing undo operations.
    Shows change details, context, risk assessment, and undo options.
    """

    def __init__(self, parent, event_id, manifest_data, initial_tab=None, inspect_ctx=None):
        """
        Initialize undo dialog.

        Args:
            parent: Parent window
            event_id: Event ID to undo (e.g., "#[Event:0001]")
            manifest_data: Full version_manifest dict with all change data
            initial_tab: Tab name to auto-select on open (e.g., "blame_risk")
            inspect_ctx: Sub-tab context dict from base_tab._build_subtab_ctx_dict()
        """
        self.parent = parent
        self.event_id = event_id
        self.manifest = manifest_data
        self.result = None
        self.initial_tab = initial_tab
        self.inspect_ctx = inspect_ctx  # v3 — tab/feature/widget context for task enrichment

        # Extract change data
        self.change_data = self._get_change_data()
        if not self.change_data:
            messagebox.showerror("Error", f"Change data not found for {event_id}")
            return

        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Undo Change {event_id}")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)

        # Configure style
        self.dialog.configure(bg='#2b2b2b')

        # Create UI
        self._create_widgets()

        # Make modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        parent.wait_window(self.dialog)

    def _get_change_data(self):
        """Retrieve change data from manifest."""
        try:
            # Check enriched_changes first (full data)
            enriched = self.manifest.get("enriched_changes", {})
            if self.event_id not in enriched:
                logger_util.log_message(f"UNDO_DIALOG: Event {self.event_id} not in enriched_changes")
                return None

            data = enriched[self.event_id].copy()
            logger_util.log_message(f"UNDO_DIALOG: Got enriched data for {self.event_id}")

            # Check change_states for before/after content (stored as sidecar files)
            change_states = self.manifest.get("change_states", {})
            if self.event_id in change_states:
                state = change_states[self.event_id]
                data['file_path'] = state.get('file')
                # Load from sidecar files if available, fall back to inline content
                before_path = state.get('before_path')
                after_path = state.get('after_path')
                if before_path and Path(before_path).exists():
                    try:
                        data['before_content'] = Path(before_path).read_text(encoding='utf-8')
                    except Exception:
                        data['before_content'] = state.get('before_content')
                else:
                    data['before_content'] = state.get('before_content')
                if after_path and Path(after_path).exists():
                    try:
                        data['after_content'] = Path(after_path).read_text(encoding='utf-8')
                    except Exception:
                        data['after_content'] = state.get('after_content')
                else:
                    data['after_content'] = state.get('after_content')
                logger_util.log_message(f"UNDO_DIALOG: Got change_states data for {self.event_id}")
            else:
                # Fallback: scan sidecar files on disk even if manifest entry missing
                logger_util.log_message(f"UNDO_DIALOG: Event {self.event_id} not in change_states — scanning sidecar files on disk")
                states_dir = Path(__file__).parents[2] / "backup" / "change_states"
                safe_id = self.event_id.replace('#[', '').replace(']', '').replace(':', '_')
                before_path = states_dir / f"{safe_id}_before.py"
                after_path = states_dir / f"{safe_id}_after.py"
                if before_path.exists():
                    try:
                        data['before_content'] = before_path.read_text(encoding='utf-8')
                        logger_util.log_message(f"UNDO_DIALOG: Loaded before content from disk: {before_path.name} ({before_path.stat().st_size} bytes)")
                    except Exception as _re:
                        logger_util.log_message(f"UNDO_DIALOG: Failed to read {before_path}: {_re}")
                else:
                    logger_util.log_message(f"UNDO_DIALOG: No sidecar file: {before_path}")
                if after_path.exists():
                    try:
                        data['after_content'] = after_path.read_text(encoding='utf-8')
                        logger_util.log_message(f"UNDO_DIALOG: Loaded after content from disk: {after_path.name} ({after_path.stat().st_size} bytes)")
                    except Exception as _re:
                        logger_util.log_message(f"UNDO_DIALOG: Failed to read {after_path}: {_re}")
                else:
                    logger_util.log_message(f"UNDO_DIALOG: No sidecar file: {after_path}")
                # Set file_path from enriched data if not already set
                if not data.get('file_path'):
                    data['file_path'] = data.get('file', '')

            return data
        except Exception as e:
            logger_util.log_message(f"UNDO_DIALOG: Error getting change data: {e}")
            return None

    def _create_widgets(self):
        """Build dialog UI with specs, deltas, and options."""
        # Header with event info
        header_frame = tk.Frame(self.dialog, bg='#363636', height=60)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        event_label = tk.Label(
            header_frame,
            text=f"🔄 Undo: {self.change_data.get('file', 'Unknown')} | {self.change_data.get('verb', 'unknown')}",
            bg='#363636', fg='#61dafb', font=('Arial', 12, 'bold'), anchor='w'
        )
        event_label.pack(side=tk.LEFT, padx=15, pady=15)

        # Risk indicator
        risk = self.change_data.get('risk_level', 'UNKNOWN')
        risk_color = {'CRITICAL': '#ff5555', 'HIGH': '#ffaa00', 'MEDIUM': '#ffdd00', 'LOW': '#55ff55'}.get(risk, '#aaaaaa')
        risk_label = tk.Label(
            header_frame,
            text=f"Risk: {risk}",
            bg='#363636', fg=risk_color, font=('Arial', 10, 'bold'), anchor='e'
        )
        risk_label.pack(side=tk.RIGHT, padx=15, pady=15)

        # Content area
        content_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Notebook for tabs
        notebook = ttk.Notebook(content_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Specifications
        self._create_specs_tab(notebook)

        # Tab 2: Before/After (always show - displays message if content not captured)
        self._create_delta_tab(notebook)

        # Tab 3: Context
        self._create_context_tab(notebook)

        # Tab 4: Blame & Risk
        self._create_blame_risk_tab(notebook)

        # Tab 5: Debug Config
        self._create_debug_config_tab(notebook)

        # Tab 6: Profile (hierarchical object lifecycle tree)
        self._create_profile_tab(notebook)

        # Tab 7: Tasks
        tasks_frame = self._create_tasks_tab(notebook)

        # Auto-select requested tab
        if self.initial_tab == "blame_risk":
            notebook.select(notebook.tabs()[3])
        elif self.initial_tab == "debug_config":
            notebook.select(notebook.tabs()[-3])
        elif self.initial_tab == "profile":
            notebook.select(notebook.tabs()[-2])
        elif self.initial_tab == "tasks":
            notebook.select(tasks_frame)

        # Bottom: Action buttons
        button_frame = tk.Frame(self.dialog, bg='#2b2b2b')
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(
            button_frame,
            text="↶ Undo This Change Only",
            command=self._undo_single
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="↶↶ Undo Full File",
            command=self._undo_full_file
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.dialog.destroy
        ).pack(side=tk.RIGHT, padx=5)

    def _create_specs_tab(self, notebook):
        """Create specifications tab showing change details."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="📋 Specifications")

        # Specs text
        specs_text = tk.Text(
            frame, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9),
            height=25, width=90, relief=tk.FLAT
        )
        specs_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Format specs - safely handle missing data
        # Key mapping: enriched_changes uses risk_confidence/risk_reasons/feature not confidence/reasons/feature_id
        file_val = self.change_data.get('file', 'N/A')
        feature_val = self.change_data.get('feature', self.change_data.get('feature_id', 'N/A'))
        verb_val = self.change_data.get('verb', 'N/A')
        change_type_val = self.change_data.get('change_type', verb_val.upper() if verb_val != 'N/A' else 'N/A')
        timestamp_val = self.change_data.get('timestamp', 'N/A')
        user_val = self.change_data.get('user', 'System')
        risk_val = self.change_data.get('risk_level', 'UNKNOWN')
        # risk_confidence stored as float 0.0-1.0
        conf_raw = self.change_data.get('risk_confidence', self.change_data.get('confidence'))
        confidence_val = f"{float(conf_raw):.0%}" if conf_raw is not None else 'N/A'
        additions_val = self.change_data.get('additions', 0)
        deletions_val = self.change_data.get('deletions', 0)
        net_change_val = self.change_data.get('net_change', 0)
        # classes: use classes list, fall back to context_class if list empty
        classes_list = self.change_data.get('classes', [])
        if not classes_list and self.change_data.get('context_class'):
            classes_list = [self.change_data['context_class']]
        methods_list = self.change_data.get('methods', [])
        if not methods_list and self.change_data.get('context_function'):
            methods_list = [self.change_data['context_function']]
        # risk_reasons stored as risk_reasons not reasons
        reasons_list = self.change_data.get('risk_reasons', self.change_data.get('reasons', []))

        specs = f"""EVENT ID:        {self.event_id}
FILE:            {file_val}
FEATURE:         {feature_val}
CHANGE TYPE:     {verb_val} ({change_type_val})

WHEN:            {timestamp_val}
WHO:             {user_val}
WHY:             {feature_val}

RISK LEVEL:      {risk_val}
CONFIDENCE:      {confidence_val}

LINES CHANGED:   +{additions_val} / -{deletions_val}
NET CHANGE:      {net_change_val} lines

CLASSES:         {', '.join(classes_list) if classes_list else 'N/A'}
METHODS:         {', '.join(methods_list) if methods_list else 'N/A'}

RISK REASONS:
"""
        if reasons_list:
            for reason in reasons_list:
                specs += f"  • {reason}\n"
        else:
            specs += "  (No reasons recorded)\n"

        specs_text.insert(tk.END, specs)
        specs_text.config(state=tk.DISABLED)

    def _create_delta_tab(self, notebook):
        """Create before/after delta tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="📊 Before/After")

        # Before content
        before_label = tk.Label(frame, text="BEFORE", bg='#2b2b2b', fg='#55ff55', font=('Arial', 9, 'bold'))
        before_label.pack(anchor='w', padx=5, pady=(5, 0))

        before_text = tk.Text(
            frame, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 8),
            height=12, width=45, relief=tk.FLAT
        )
        before_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 2), pady=(0, 5))

        before_content = self.change_data.get('before_content', None)
        if before_content is None:
            before_display = "(before content not captured)"
        elif isinstance(before_content, str) and len(before_content) > 2000:
            before_display = before_content[:2000] + "\n... (truncated)"
        else:
            before_display = str(before_content) if before_content else "(empty)"

        before_text.insert(tk.END, before_display)
        before_text.config(state=tk.DISABLED)

        # After content
        after_label = tk.Label(frame, text="AFTER", bg='#2b2b2b', fg='#ff5555', font=('Arial', 9, 'bold'))
        after_label.pack(anchor='w', padx=5, pady=(5, 0))

        after_text = tk.Text(
            frame, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 8),
            height=12, width=45, relief=tk.FLAT
        )
        after_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 5), pady=(0, 5))

        after_content = self.change_data.get('after_content', None)
        if after_content is None:
            after_display = "(after content not captured)"
        elif isinstance(after_content, str) and len(after_content) > 2000:
            after_display = after_content[:2000] + "\n... (truncated)"
        else:
            after_display = str(after_content) if after_content else "(empty)"

        after_text.insert(tk.END, after_display)
        after_text.config(state=tk.DISABLED)

    def _create_context_tab(self, notebook):
        """Create context information tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🔗 Context")

        context_text = tk.Text(
            frame, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9),
            height=25, width=90, relief=tk.FLAT
        )
        context_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        context = f"""EXECUTION CONTEXT:
─────────────────

Function/Method: {self.change_data.get('context_function', 'N/A')}
Class:           {self.change_data.get('context_class', 'N/A')}

CHANGE VALUES:
──────────────
"""
        for i, change in enumerate(self.change_data.get('before_after_values', [])[:5], 1):
            context += f"\n  Change #{i}:\n"
            context += f"    Line: {change.get('line_number', 'N/A')}\n"
            context += f"    Before: {change.get('before_value', 'N/A')}\n"
            context += f"    After:  {change.get('after_value', 'N/A')}\n"

        if len(self.change_data.get('before_after_values', [])) > 5:
            context += f"\n  ... and {len(self.change_data.get('before_after_values', [])) - 5} more changes"

        context_text.insert(tk.END, context)
        context_text.config(state=tk.DISABLED)

    def _create_blame_risk_tab(self, notebook):
        """Create combined blame & risk analysis tab."""
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="⚠ Blame & Risk")

        blame_text = tk.Text(
            frame, bg='#1e1e1e', fg='#d4d4d4', font=('Courier', 9),
            height=25, width=90, relief=tk.FLAT
        )
        blame_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Risk assessment section
        risk_val = self.change_data.get('risk_level', 'UNKNOWN')
        conf_raw = self.change_data.get('risk_confidence', self.change_data.get('confidence'))
        confidence_val = f"{float(conf_raw):.0%}" if conf_raw is not None else 'N/A'
        risk_reasons = self.change_data.get('risk_reasons', self.change_data.get('reasons', []))

        content = f"""RISK ASSESSMENT
{'─' * 40}

Risk Level:      {risk_val}
Confidence:      {confidence_val}
File:            {self.change_data.get('file', 'Unknown')}
Change Type:     {self.change_data.get('verb', 'unknown')}

RISK FACTORS:
"""
        if risk_reasons:
            for reason in risk_reasons:
                content += f"  • {reason}\n"
        else:
            content += "  (No risk factors recorded)\n"

        # Blame analysis section
        content += f"""
BLAME ANALYSIS
{'─' * 40}

Event:           {self.event_id}
Context Class:   {self.change_data.get('context_class', 'N/A')}
Context Method:  {self.change_data.get('context_function', 'N/A')}

CLASSES TOUCHED:
"""
        classes = self.change_data.get('classes', [])
        if not classes and self.change_data.get('context_class'):
            classes = [self.change_data['context_class']]
        if classes:
            for cls in classes:
                content += f"  • {cls}\n"
        else:
            content += "  (No classes detected in diff)\n"

        content += "\nMETHODS TOUCHED:\n"
        methods = self.change_data.get('methods', [])
        if methods:
            for method in methods:
                content += f"  • {method}\n"
        else:
            content += "  (No methods detected in diff)\n"

        content += "\nIMPORTS ADDED:\n"
        imports_added = self.change_data.get('imports_added', [])
        if imports_added:
            for imp in imports_added:
                content += f"  + {imp}\n"
        else:
            content += "  (None)\n"

        content += "\nIMPORTS REMOVED:\n"
        imports_removed = self.change_data.get('imports_removed', [])
        if imports_removed:
            for imp in imports_removed:
                content += f"  - {imp}\n"
        else:
            content += "  (None)\n"

        content += f"""
CHANGE STATISTICS:
  Lines added:     +{self.change_data.get('additions', 0)}
  Lines removed:   -{self.change_data.get('deletions', 0)}
  Net change:      {self.change_data.get('net_change', 0)} lines
"""

        blame_text.insert(tk.END, content)
        blame_text.config(state=tk.DISABLED)

    def _create_debug_config_tab(self, notebook):
        """
        Debug Config tab: UI/UX/UA taxonomy with field checklist, domain classification,
        UX baseline events, and user attribution cross-reference.
        #[Mark:DEBUG_CONFIG_TAB]
        """
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🔧 Debug Config")

        debug_text = tk.Text(
            frame, bg='#1a1a2e', fg='#e0e0e0', font=('Courier', 9),
            height=25, width=90, relief=tk.FLAT
        )
        debug_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Resolve owning tab once (reused across all sections) ---
        file_path = self.change_data.get('file', '')
        owning_tab = None
        owning_tab_data = None
        # Pass 1: exact filename match
        for _tname, _reg in logger_util.TAB_REGISTRY.items():
            _src = _reg.get('source_file', '') or ''
            if file_path and (file_path.split('/')[-1] in _src or _src.endswith(file_path)):
                owning_tab = _tname
                owning_tab_data = _reg
                break
        # Pass 2: parent directory match (e.g. undo_changes.py → settings_tab)
        if not owning_tab and file_path:
            _fp_parts = file_path.replace('\\', '/').split('/')
            for _tname, _reg in logger_util.TAB_REGISTRY.items():
                _src = (_reg.get('source_file', '') or '').replace('\\', '/')
                if _src:
                    # Check if file lives in same tab directory as registered source
                    _src_dir = '/'.join(_src.split('/')[:-1])
                    _fp_dir = '/'.join(_fp_parts[:-1])
                    if _src_dir and _fp_dir and (_fp_dir.endswith(_src_dir.split('/')[-1]) or _src_dir.endswith(_fp_dir.split('/')[-1])):
                        owning_tab = _tname
                        owning_tab_data = _reg
                        break

        # ── Section A: Attribution Field Checklist ─────────────────────
        FIELD_GROUPS = {
            'Core': ['file', 'verb', 'feature', 'timestamp', 'user'],
            'Code Structure': ['classes', 'methods', 'context_class', 'context_function'],
            'Risk': ['risk_level', 'risk_confidence', 'risk_reasons'],
            'Delta': ['additions', 'deletions', 'net_change', 'before_after_values',
                      'imports_added', 'imports_removed'],
        }
        total_fields = sum(len(v) for v in FIELD_GROUPS.values())
        total_populated = 0

        content = f"ATTRIBUTION CHECKLIST\n{'─' * 50}\n"
        for group_name, fields in FIELD_GROUPS.items():
            content += f"\n{group_name}:\n"
            for f in fields:
                val = self.change_data.get(f)
                is_set = val not in (None, [], '', 0)
                if is_set:
                    total_populated += 1
                    if isinstance(val, list):
                        display = f"[{len(val)} items]"
                    else:
                        display = str(val)[:55]
                    content += f"  ✓ {f:<22} {display}\n"
                else:
                    content += f"  ✗ {f:<22} (not set)\n"
        pct = total_populated / total_fields if total_fields else 0
        content += f"\nCompleteness: {total_populated}/{total_fields} ({pct:.0%})\n"

        # ── Section B: UI Domain (TAX) ─────────────────────────────────
        content += f"\nUI DOMAIN (TAX)\n{'─' * 50}\n"
        content += f"\nOwning Tab:  {owning_tab or '(not matched to a tab)'}\n"
        if owning_tab_data:
            probe = owning_tab_data.get('execution_probe') or {}
            domain = probe.get('domain', 'unknown')
            known_issues = probe.get('domain_known_issues', [])
            signal_checks = probe.get('domain_signal_checks', [])

            content += f"Source File: {owning_tab_data.get('source_file', 'N/A')}\n"
            content += f"Tab Status:  {owning_tab_data.get('status', 'N/A')}\n"
            content += f"Domain:      {domain}\n"
            if known_issues:
                content += f"Known Issues:\n"
                for issue in known_issues:
                    content += f"  ⚠ {issue}\n"
            if signal_checks:
                content += f"Signal Checks:\n"
                for check in signal_checks:
                    content += f"  → {check}\n"

            ws = owning_tab_data.get('widget_summary') or owning_tab_data.get('widget_profile')
            if ws and isinstance(ws, dict):
                counts = ws.get('widget_counts', {})
                top = ws.get('top_level', [])
                content += f"\nWidget Inventory:\n"
                content += f"  Top-level: {', '.join(top) if top else 'N/A'}\n"
                if counts:
                    sorted_counts = dict(sorted(counts.items(), key=lambda x: -x[1]))
                    counts_str = ', '.join(f"{k}:{v}" for k, v in list(sorted_counts.items())[:8])
                    content += f"  Counts:    {counts_str}\n"

            if probe:
                p_status = probe.get('probe_status', 'N/A')
                status_icon = {'PASS': '✓', 'WARN': '⚠', 'FAIL': '✗'}.get(p_status, '?')
                ok_count = len(probe.get('methods_ok', []))
                miss_count = len(probe.get('methods_missing', []))
                content += f"\nExec Probe: {status_icon} {p_status}"
                if ok_count or miss_count:
                    content += f"  ({ok_count}/{ok_count + miss_count} methods OK)"
                content += "\n"
                blank = probe.get('blank_panels', [])
                if blank:
                    content += f"  Blank panels ({len(blank)}): {', '.join(blank[:6])}"
                    content += " ..." if len(blank) > 6 else ""
                    content += "\n"
                unbound = probe.get('callbacks_unbound', [])
                if unbound:
                    content += f"  Unbound ({len(unbound)}): {', '.join(str(u) for u in unbound[:6])}"
                    content += " ..." if len(unbound) > 6 else ""
                    content += "\n"
                if not blank and not unbound and p_status == 'PASS':
                    content += "  No blank panels, all callbacks bound.\n"
            else:
                content += "\nExec Probe: (not yet run — relaunch to populate)\n"

        # ── Section C: UX Baseline Events ─────────────────────────────
        content += f"\nUX BASELINE"
        if owning_tab:
            ux_events = [e for e in logger_util.UX_EVENT_LOG if e.get('tab') == owning_tab]
            recent = ux_events[-10:] if len(ux_events) > 10 else ux_events
            error_count = sum(1 for e in ux_events if e.get('outcome') == 'error')
            content += f" ({owning_tab} — {len(ux_events)} total, {error_count} errors)\n"
            content += f"{'─' * 50}\n"
            if recent:
                for evt in recent:
                    outcome_icon = '✓' if evt.get('outcome') == 'fired' else '✗'
                    detail = f": {evt['detail']}" if evt.get('detail') else ''
                    content += f"  {evt.get('timestamp','')}  {outcome_icon} {evt.get('widget','?'):<28} → {evt.get('outcome','?')}{detail}\n"
            else:
                content += "  (no UX events recorded — click buttons to build baseline)\n"
            # Signal check cross-reference
            if owning_tab_data:
                probe = owning_tab_data.get('execution_probe') or {}
                sig_checks = probe.get('domain_signal_checks', [])
                if sig_checks:
                    observed_widgets = {e.get('widget', '') for e in ux_events}
                    content += f"\nSignal checks: {len(sig_checks)} expected\n"
                    for sc in sig_checks:
                        # Fuzzy match: check if any observed widget name contains signal check keywords
                        matched = any(word in ' '.join(observed_widgets).lower()
                                      for word in sc.lower().split()[:2])
                        content += f"  {'✓' if matched else '?'} {sc}\n"
        else:
            content += " (no owning tab matched)\n"
            content += f"{'─' * 50}\n"
            content += "  (cannot filter UX events without owning tab)\n"

        # ── Section D: UA Attribution ──────────────────────────────────
        content += f"\nUSER ATTRIBUTION\n{'─' * 50}\n"
        enriched = self.manifest.get('enriched_changes', {})
        same_file_events = [
            eid for eid, ch in enriched.items()
            if ch.get('file') == file_path and eid != self.event_id
        ]
        content += f"\nChange file:  {file_path or '(unknown)'}\n"
        content += f"Owning Tab:   {owning_tab or '(not matched)'}"
        if owning_tab_data:
            content += f" [matched via source_file]"
        content += "\n"

        if owning_tab:
            ux_errors = [e for e in logger_util.UX_EVENT_LOG
                         if e.get('tab') == owning_tab and e.get('outcome') == 'error']
            if ux_errors:
                last_err = ux_errors[-1]
                content += f"Last UX error: {last_err.get('timestamp','')} — {last_err.get('widget','')} → {last_err.get('detail','')}\n"
            else:
                content += "Last UX error: (none observed)\n"

        content += f"Other events same file: {', '.join(sorted(same_file_events)) if same_file_events else '(none)'}\n"
        content += f"Total events this file: {len(same_file_events) + 1}\n"

        # Probable impact: if change timestamp < last UX error timestamp (same session)
        change_ts = self.change_data.get('timestamp', '')
        if owning_tab and change_ts:
            ux_errors_after = [e for e in logger_util.UX_EVENT_LOG
                               if e.get('tab') == owning_tab
                               and e.get('outcome') == 'error'
                               and e.get('timestamp', '') > change_ts[-8:]]
            if ux_errors_after:
                content += f"Probable impact: change at {change_ts[-8:]} → UX error at {ux_errors_after[0].get('timestamp','')}\n"

        # Risk bridge: link risk weight summary here
        conf_raw = self.change_data.get('risk_confidence', self.change_data.get('confidence', 0))
        conf_float = float(conf_raw) if conf_raw is not None else 0.0
        risk_reasons = self.change_data.get('risk_reasons', self.change_data.get('reasons', []))
        content += f"\nRisk:   {self.change_data.get('risk_level', 'UNKNOWN')} ({conf_float:.0%} confidence, {len(risk_reasons)} rules)\n"
        if risk_reasons:
            for r in risk_reasons[:4]:
                content += f"  ▶ {r}\n"
            if len(risk_reasons) > 4:
                content += f"  ... ({len(risk_reasons) - 4} more)\n"

        debug_text.insert(tk.END, content)
        debug_text.config(state=tk.DISABLED)

    def _create_profile_tab(self, notebook):
        """
        Profile tab: hierarchical object lifecycle tree.
        Structure: file → UI domain → UX baseline → diffs (with -history branches).
        Formalizes what Tab Manager + Latest Changes aim to show, in unified tree form.
        #[Mark:PROFILE_TAB]
        """
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="🌳 Profile")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        # PanedWindow: left=tree, right=detail
        pane = ttk.PanedWindow(frame, orient=tk.HORIZONTAL)
        pane.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Left: Profile Treeview
        tree_outer = ttk.Frame(pane)
        pane.add(tree_outer, weight=1)
        tree_outer.columnconfigure(0, weight=1)
        tree_outer.rowconfigure(0, weight=1)

        profile_tree = ttk.Treeview(tree_outer, show='tree', selectmode='browse')
        p_vsb = ttk.Scrollbar(tree_outer, orient='vertical', command=profile_tree.yview)
        profile_tree.configure(yscrollcommand=p_vsb.set)
        profile_tree.grid(row=0, column=0, sticky='nsew')
        p_vsb.grid(row=0, column=1, sticky='ns')

        profile_tree.tag_configure('file_root', foreground='#61dafb', font=('Courier', 10, 'bold'))
        profile_tree.tag_configure('domain_node', foreground='#ffcc66')
        profile_tree.tag_configure('probe_ok', foreground='#99ff99')
        profile_tree.tag_configure('probe_warn', foreground='#ffaa44')
        profile_tree.tag_configure('probe_fail', foreground='#ff4444')
        profile_tree.tag_configure('ux_node', foreground='#ff9966')
        profile_tree.tag_configure('ux_error', foreground='#ff4444')
        profile_tree.tag_configure('diff_node', foreground='#cc99ff')
        profile_tree.tag_configure('current_event', foreground='#ffff66', font=('Courier', 9, 'bold'))
        profile_tree.tag_configure('history_node', foreground='#666666')

        # Right: Detail panel
        detail_outer = ttk.Frame(pane)
        pane.add(detail_outer, weight=1)
        detail_outer.columnconfigure(0, weight=1)
        detail_outer.rowconfigure(0, weight=1)

        detail_text = tk.Text(
            detail_outer, bg='#1a1a2e', fg='#e0e0e0', font=('Courier', 9),
            relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED
        )
        d_vsb = ttk.Scrollbar(detail_outer, orient='vertical', command=detail_text.yview)
        detail_text.configure(yscrollcommand=d_vsb.set)
        detail_text.grid(row=0, column=0, sticky='nsew')
        d_vsb.grid(row=0, column=1, sticky='ns')

        # Node detail store: iid → detail string
        node_data = {}

        def set_detail(text):
            detail_text.config(state=tk.NORMAL)
            detail_text.delete('1.0', tk.END)
            detail_text.insert(tk.END, text)
            detail_text.config(state=tk.DISABLED)

        profile_tree.bind('<<TreeviewSelect>>', lambda e: set_detail(
            node_data.get(profile_tree.selection()[0] if profile_tree.selection() else '', '')
        ))

        # ── Build the profile tree ──────────────────────────────────────
        file_path = self.change_data.get('file', '')
        file_short = file_path.split('/')[-1] if '/' in file_path else file_path

        # Resolve owning tab (exact match, then parent-directory fallback)
        owning_tab = None
        owning_tab_data = None
        for _tname, _reg in logger_util.TAB_REGISTRY.items():
            _src = _reg.get('source_file', '') or ''
            if file_path and (file_short in _src or _src.endswith(file_path)):
                owning_tab = _tname
                owning_tab_data = _reg
                break
        if not owning_tab and file_path:
            _fp_parts = file_path.replace('\\', '/').split('/')
            for _tname, _reg in logger_util.TAB_REGISTRY.items():
                _src = (_reg.get('source_file', '') or '').replace('\\', '/')
                if _src:
                    _src_dir = '/'.join(_src.split('/')[:-1])
                    _fp_dir = '/'.join(_fp_parts[:-1])
                    if _src_dir and _fp_dir and (_fp_dir.endswith(_src_dir.split('/')[-1]) or _src_dir.endswith(_fp_dir.split('/')[-1])):
                        owning_tab = _tname
                        owning_tab_data = _reg
                        break

        # Root: file node
        root_text = f"📄 {file_short}"
        if owning_tab:
            root_text += f"  [{owning_tab}]"
        root_detail = (
            f"File:        {file_path}\n"
            f"Owning Tab:  {owning_tab or '(not matched)'}\n"
            f"Event:       {self.event_id}\n"
            f"Verb:        {self.change_data.get('verb', 'N/A')}\n"
            f"Feature:     {self.change_data.get('feature', 'N/A')}\n"
        )
        root_iid = profile_tree.insert('', 'end', text=root_text, tags=('file_root',), open=True)
        node_data[root_iid] = root_detail

        probe = (owning_tab_data or {}).get('execution_probe') or {}

        # UI Domain branch
        domain = probe.get('domain', 'unknown')
        known_issues = probe.get('domain_known_issues', [])
        domain_node_text = f"🏷 UI Domain: {domain}"
        domain_detail = (
            f"Domain:      {domain}\n"
            f"Known Issues: {', '.join(known_issues) if known_issues else 'none'}\n"
            f"Signal Checks: {', '.join(probe.get('domain_signal_checks', [])) or 'none'}\n"
        )
        if owning_tab_data:
            ws = owning_tab_data.get('widget_profile') or {}
            if isinstance(ws, dict):
                counts = ws.get('widget_counts', {})
                if counts:
                    domain_detail += "\nWidget Counts:\n"
                    for k, v in sorted(counts.items(), key=lambda x: -x[1])[:10]:
                        domain_detail += f"  {k}: {v}\n"
        dom_iid = profile_tree.insert(root_iid, 'end', text=domain_node_text, tags=('domain_node',))
        node_data[dom_iid] = domain_detail
        for issue in known_issues:
            iss_iid = profile_tree.insert(dom_iid, 'end', text=f"  ⚠ {issue}", tags=('probe_warn',))
            node_data[iss_iid] = f"Known Issue:\n{issue}\n\nDomain: {domain}"
        hist_dom = profile_tree.insert(dom_iid, 'end', text='  ─ history ─', tags=('history_node',))
        node_data[hist_dom] = f"Domain history accumulates across sessions.\nCurrent domain: {domain}"

        # Exec Probe branch
        p_status = probe.get('probe_status', 'N/A')
        ok = len(probe.get('methods_ok', []))
        total = ok + len(probe.get('methods_missing', []))
        probe_tag = {'PASS': 'probe_ok', 'WARN': 'probe_warn', 'FAIL': 'probe_fail'}.get(p_status, 'history_node')
        p_icon = {'PASS': '✓', 'WARN': '⚠', 'FAIL': '✗'}.get(p_status, '?')
        probe_text = f"🔧 Exec Probe: {p_icon} {p_status} ({ok}/{total} methods)"
        missing_methods = probe.get('methods_missing', [])
        blank_panels = probe.get('blank_panels', [])
        probe_detail = (
            f"Probe Status: {p_status}\n"
            f"Methods OK:  {ok}/{total}\n"
            f"Missing:     {', '.join(missing_methods) if missing_methods else 'none'}\n"
            f"Blank panels: {', '.join(blank_panels) if blank_panels else 'none'}\n"
            f"Notes:       {'; '.join(probe.get('notes', [])) or 'none'}\n"
        )
        probe_iid = profile_tree.insert(root_iid, 'end', text=probe_text, tags=(probe_tag,))
        node_data[probe_iid] = probe_detail
        for m in missing_methods[:5]:
            m_iid = profile_tree.insert(probe_iid, 'end', text=f"  ✗ {m}", tags=('probe_fail',))
            node_data[m_iid] = f"Missing method: {m}\n\nNot found on instance of {owning_tab or '?'}"
        hist_probe = profile_tree.insert(probe_iid, 'end', text='  ─ history ─', tags=('history_node',))
        node_data[hist_probe] = 'Probe history accumulates across sessions.\nCurrently stores last-launch results only.'

        # UX Baseline branch
        ux_events = [e for e in logger_util.UX_EVENT_LOG if e.get('tab') == owning_tab] if owning_tab else []
        ux_errors = [e for e in ux_events if e.get('outcome') == 'error']
        ux_text = f"⚡ UX Baseline ({len(ux_events)} events, {len(ux_errors)} errors)"
        ux_full = f"UX events for {owning_tab or '?'} (all {len(ux_events)}):\n\n"
        for ev in reversed(ux_events):
            icon = '✓' if ev.get('outcome') == 'fired' else '✗'
            ux_full += f"  {ev.get('timestamp','')}  {icon} {ev.get('widget','?')} → {ev.get('outcome','?')}"
            if ev.get('detail'):
                ux_full += f": {ev['detail']}"
            ux_full += '\n'
        ux_iid = profile_tree.insert(root_iid, 'end', text=ux_text, tags=('ux_node',))
        node_data[ux_iid] = ux_full if ux_full.strip() else '(no UX events recorded — click buttons to build baseline)'
        for ev in reversed(ux_events[-8:]):
            tag = 'ux_error' if ev.get('outcome') == 'error' else 'history_node'
            icon = '✓' if ev.get('outcome') == 'fired' else '✗'
            ev_text = f"  {ev.get('timestamp','')}  {icon} {ev.get('widget','?')}"
            ev_detail = '\n'.join(f"{k}: {v}" for k, v in ev.items())
            ev_iid = profile_tree.insert(ux_iid, 'end', text=ev_text, tags=(tag,))
            node_data[ev_iid] = ev_detail
        hist_ux = profile_tree.insert(ux_iid, 'end', text='  ─ history ─ (all)', tags=('history_node',))
        node_data[hist_ux] = ux_full if ux_full.strip() else '(no events yet)'

        # Diffs branch — all events for this file, current highlighted
        enriched = self.manifest.get('enriched_changes', {})
        file_events = [
            (eid, ch) for eid, ch in enriched.items()
            if ch.get('file', '').endswith(file_short)
        ]
        file_events.sort(key=lambda x: x[0], reverse=True)
        diff_text = f"📑 Diffs ({len(file_events)} events for {file_short})"
        diff_summary = f"All change events for {file_short}:\n\n"
        for eid, ch in file_events:
            marker = '← current' if eid == self.event_id else ''
            diff_summary += (
                f"{eid}: {ch.get('verb','?')} +{ch.get('additions',0)}/-{ch.get('deletions',0)} "
                f"[{ch.get('risk_level','?')}] {ch.get('timestamp','')} {marker}\n"
            )
        diff_iid = profile_tree.insert(root_iid, 'end', text=diff_text, tags=('diff_node',))
        node_data[diff_iid] = diff_summary
        for eid, ch in file_events[:10]:
            risk = ch.get('risk_level', 'UNKNOWN')
            risk_sym = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(risk, '⚪')
            ts = ch.get('timestamp', '')[-8:] if ch.get('timestamp') else ''
            additions = ch.get('additions', 0)
            deletions = ch.get('deletions', 0)
            is_current = eid == self.event_id
            entry_text = f"  {risk_sym} {eid}  {ts}  +{additions}/-{deletions}"
            if is_current:
                entry_text += "  ◄ current"
            entry_detail = '\n'.join(f"{k}: {v}" for k, v in ch.items() if k != 'diff_text')
            entry_tag = 'current_event' if is_current else 'diff_node'
            entry_iid = profile_tree.insert(diff_iid, 'end', text=entry_text, tags=(entry_tag,))
            node_data[entry_iid] = entry_detail

        # Blame branch — cross-reference probe failures + resolutions + parent tab context
        _blame_events = [(eid, ch) for eid, ch in file_events
                         if ch.get("probe_status") == "FAIL" or ch.get("blame_event")]
        blame_label = f"🔍 Blame ({len(_blame_events)} probe events)"
        _parent_detail = f"Parent Tab:  {owning_tab or '(not matched)'}\n"
        if owning_tab_data:
            _parent_detail += f"Source File: {owning_tab_data.get('source_file', '?')}\n"
            _parent_detail += f"Init Status: {owning_tab_data.get('status', '?')}\n"
            _init_probe = (owning_tab_data.get('execution_probe') or {}).get('probe_status', 'n/a')
            _parent_detail += f"Probe Status: {_init_probe}\n"
        _parent_detail += f"\nFile: {file_path}\nEvent: {self.event_id}\n"
        blame_iid = profile_tree.insert(root_iid, 'end', text=blame_label, tags=('domain_node',))
        node_data[blame_iid] = _parent_detail

        for eid, ch in file_events:
            if ch.get("probe_status") == "FAIL":
                _resolved = ch.get("resolved_by")
                _tag = "probe_ok" if _resolved else "probe_fail"
                _icon = "✓ fixed" if _resolved else "✗ open"
                _errors = ch.get("probe_errors", [])
                b_text = f"  {_icon} {eid}: {_errors[0][:60] if _errors else '?'}"
                b_detail = f"Event: {eid}\nProbe Status: FAIL\n"
                b_detail += f"Errors:\n" + "\n".join(f"  • {e}" for e in _errors)
                if _resolved:
                    b_detail += f"\n\nResolved by: {_resolved}\nAt: {ch.get('resolved_at', '?')}"
                b_iid = profile_tree.insert(blame_iid, 'end', text=b_text, tags=(_tag,))
                node_data[b_iid] = b_detail

        if not _blame_events:
            no_blame = profile_tree.insert(blame_iid, 'end', text="  (no probe failures recorded)", tags=('history_node',))
            node_data[no_blame] = "No probe failures detected for this file."

        # Expand all top-level branches by default
        for child in profile_tree.get_children(root_iid):
            profile_tree.item(child, open=True)

    def _undo_single(self):
        """Undo single change only."""
        try:
            logger_util.log_message(f"UNDO_DIALOG: User initiating single change undo for {self.event_id}")

            # Attempt undo
            success, message = recovery_util.undo_single_change(self.event_id)

            if success:
                messagebox.showinfo("Success", f"✓ Change undone\n\n{message}")
                logger_util.log_message(f"UNDO_DIALOG: ✓ Single change undo succeeded: {message}")
                self.result = "single_undo"
            else:
                messagebox.showerror("Failed", f"✗ Undo failed\n\n{message}")
                logger_util.log_message(f"UNDO_DIALOG: ✗ Single change undo failed: {message}")

            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Error during undo: {str(e)}")
            logger_util.log_message(f"UNDO_DIALOG: ERROR in _undo_single: {e}")

    def _undo_full_file(self):
        """Undo entire file to last backup."""
        try:
            file_path = self.change_data.get('file_path')
            if not file_path:
                messagebox.showerror("Error", "File path not available")
                return

            confirm = messagebox.askyesno(
                "Confirm Full File Undo",
                f"Undo entire file: {file_path}\n\n"
                "This will restore the file to its state from the last successful launch,\n"
                "discarding ALL changes (not just this one).\n\n"
                "Are you sure?"
            )

            if confirm:
                logger_util.log_message(f"UNDO_DIALOG: User initiating full file undo for {file_path}")
                success, message = recovery_util.undo_pending_changes()

                if success:
                    messagebox.showinfo("Success", f"✓ File undone\n\n{message}")
                    logger_util.log_message(f"UNDO_DIALOG: ✓ Full file undo succeeded: {message}")
                    self.result = "full_undo"
                else:
                    messagebox.showerror("Failed", f"✗ Undo failed\n\n{message}")
                    logger_util.log_message(f"UNDO_DIALOG: ✗ Full file undo failed: {message}")

                self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Error during undo: {str(e)}")
            logger_util.log_message(f"UNDO_DIALOG: ERROR in _undo_full_file: {e}")

    # -----------------------------------------------------------------------
    # Tasks tab (7th tab)
    # -----------------------------------------------------------------------

    def _create_tasks_tab(self, notebook):
        """7th tab: related tasks + create-task form for this change event."""
        tasks_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(tasks_frame, text="📋 Tasks")
        tasks_frame.columnconfigure(0, weight=1)
        tasks_frame.rowconfigure(0, weight=2)
        tasks_frame.rowconfigure(1, weight=1)

        # ── Top: Related tasks treeview ──────────────────────────────────────
        list_lf = tk.LabelFrame(tasks_frame, text="Related Tasks",
                                bg='#2b2b2b', fg='#cccccc')
        list_lf.grid(row=0, column=0, sticky='nsew', padx=8, pady=(8, 4))
        list_lf.rowconfigure(0, weight=1)
        list_lf.columnconfigure(0, weight=1)

        cols = ('source', 'id', 'status', 'priority', 'title')
        self._tasks_tree = ttk.Treeview(list_lf, columns=cols, show='headings', height=6)
        for col, w in (('source', 70), ('id', 110), ('status', 75), ('priority', 55), ('title', 270)):
            self._tasks_tree.heading(col, text=col.replace('_', ' ').title())
            self._tasks_tree.column(col, width=w, stretch=(col == 'title'))
        self._tasks_tree.grid(row=0, column=0, sticky='nsew')
        vsb = ttk.Scrollbar(list_lf, orient='vertical', command=self._tasks_tree.yview)
        self._tasks_tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky='ns')

        # ── Bottom: Create-task form ─────────────────────────────────────────
        form_lf = tk.LabelFrame(tasks_frame, text="Create Task from this Change",
                                bg='#2b2b2b', fg='#cccccc')
        form_lf.grid(row=1, column=0, sticky='nsew', padx=8, pady=(4, 8))
        form_lf.columnconfigure(1, weight=1)

        cd = self.change_data
        default_title = (
            f"Bug in {cd.get('file', '').split('/')[-1]}"
            if cd.get('bug_id') else
            f"Fix: {cd.get('verb', '?')} in {cd.get('file', '?').split('/')[-1]}"
        )
        default_wherein = (cd.get('context_function') or
                           cd.get('context_class') or
                           cd.get('file', '?'))
        default_desc = (
            f"Event: {self.event_id}  Risk: {cd.get('risk_level', '?')}\n"
            f"Methods: {', '.join(cd.get('methods', []))}\n"
            f"Reasons: {'; '.join(cd.get('risk_reasons', []))[:200]}"
        )

        for row_i, (lbl, key, default) in enumerate([
            ("Title",    '_t_title',   default_title),
            ("Wherein",  '_t_wherein', default_wherein),
            ("Priority", '_t_prio',   'P1'),
        ]):
            tk.Label(form_lf, text=lbl + ':', bg='#2b2b2b', fg='#aaa',
                     anchor='e', width=8).grid(row=row_i, column=0, sticky='e', padx=4, pady=2)
            var = tk.StringVar(value=default)
            setattr(self, key, var)
            tk.Entry(form_lf, textvariable=var, bg='#1e1e1e', fg='#eee',
                     insertbackground='white').grid(row=row_i, column=1,
                                                    sticky='ew', padx=4, pady=2)

        tk.Label(form_lf, text='Desc:', bg='#2b2b2b', fg='#aaa',
                 anchor='ne', width=8).grid(row=3, column=0, sticky='ne', padx=4, pady=2)
        self._t_desc = tk.Text(form_lf, height=3, bg='#1e1e1e', fg='#eee',
                               insertbackground='white', wrap='word')
        self._t_desc.insert('1.0', default_desc)
        self._t_desc.grid(row=3, column=1, sticky='ew', padx=4, pady=2)

        self._tasks_status = tk.Label(form_lf, text='', bg='#2b2b2b', fg='#88ff88', anchor='w')
        self._tasks_status.grid(row=4, column=0, columnspan=2, sticky='ew', padx=4)

        tk.Button(form_lf, text='➕ Create Task', bg='#1a3a1a', fg='#88ff88',
                  command=self._do_create_task).grid(row=4, column=1, sticky='e',
                                                     padx=4, pady=4)

        self._populate_related_tasks()
        return tasks_frame

    def _populate_related_tasks(self):
        """Populate the related tasks treeview from todos.json, checklist.json, and runtime_bugs.json."""
        self._tasks_tree.delete(*self._tasks_tree.get_children())
        plans_path = Path(__file__).parent.parent.parent / "plans"
        src_base = (self.change_data.get('file') or '').split('/')[-1]
        rows = []  # (source, id, status, priority, title)

        # ── Source 1: Data/plans/todos.json (phase-dict format) ──
        todos_path = plans_path / "todos.json"
        if todos_path.exists():
            try:
                data = json.loads(todos_path.read_text())
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}
            if 'todos' in data and isinstance(data['todos'], list):
                # legacy {"todos":[...]} — read-compat only
                task_list = data['todos']
                for t in task_list:
                    tid = t.get('task_id') or t.get('id', '?')
                    marks = t.get('marks', [])
                    wherein = t.get('wherein', '')
                    if (self.event_id in marks or
                            any(src_base and src_base in str(m) for m in marks) or
                            (src_base and src_base in wherein)):
                        rows.append(('todos', tid, t.get('status', '?'),
                                     t.get('priority', '?'), t.get('title', '?')))
            else:
                # phase-dict format: {phase_key: {task_id: task_dict}}
                for phase_tasks in data.values():
                    if not isinstance(phase_tasks, dict):
                        continue
                    for tid, t in phase_tasks.items():
                        if not isinstance(t, dict):
                            continue
                        marks = t.get('marks', [])
                        wherein = t.get('wherein', '')
                        if (self.event_id in marks or
                                any(src_base and src_base in str(m) for m in marks) or
                                (src_base and src_base in wherein)):
                            rows.append(('todos', t.get('id', tid), t.get('status', '?'),
                                         t.get('priority', '?'), t.get('title', '?')))
        else:
            logger_util.log_message(
                "UNDO_DIALOG: plans/todos.json missing — task treeview may be empty")

        # ── Source 2: Data/plans/checklist.json ──
        cl_path = plans_path / "checklist.json"
        if cl_path.exists():
            try:
                cl_data = json.loads(cl_path.read_text())
            except Exception:
                cl_data = {}
            for section_items in cl_data.values():
                items = (section_items.get('items', [])
                         if isinstance(section_items, dict) else
                         section_items if isinstance(section_items, list) else [])
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_file = item.get('file', '') or item.get('wherein', '')
                    item_id = item.get('id', '?')
                    if src_base and (src_base in item_file or src_base in item_id):
                        rows.append(('checklist', item_id,
                                     item.get('status', '?'),
                                     item.get('priority', '?'),
                                     item.get('title', item.get('name', '?'))))

        # ── Source 3: Data/plans/runtime_bugs.json ──
        rb_path = plans_path / "runtime_bugs.json"
        if rb_path.exists():
            try:
                bugs = json.loads(rb_path.read_text())
            except Exception:
                bugs = []
            if isinstance(bugs, list):
                for b in bugs:
                    if b.get('status', '').upper() != 'OPEN':
                        continue
                    msg = b.get('message', '')
                    if src_base and src_base in msg:
                        ts = b.get('timestamp', '')[:10]
                        rows.append(('runtime_bug', f"bug_{ts}",
                                     'OPEN', 'auto', msg[:60]))

        for row in rows:
            self._tasks_tree.insert('', 'end', values=row)

    def _build_expected_log_events(self, wherein):
        """Scan last 3 debug logs for patterns related to the 'wherein' file.
        Returns a list of {pattern, count_min, event_type, description} dicts
        suitable for task_context['expected_log_events'].  Zero-cost if no logs found.
        """
        import re as _re
        results = []
        try:
            basename = Path(wherein).name if wherein else ""
            if not basename:
                return results
            debug_dir = Path(__file__).parent.parent.parent / "DeBug"
            if not debug_dir.exists():
                return results
            logs = sorted(debug_dir.glob("debug_log_*.txt"), reverse=True)[:3]
            pattern_counts = {}
            for log in logs:
                try:
                    content = log.read_text(errors="replace")
                    # Count PROBE [PASS/WARN/FAIL] lines referencing any word from filename
                    stem = Path(wherein).stem  # e.g. "undo_changes"
                    for line in content.splitlines():
                        if "PROBE [" in line and stem in line:
                            k = ("PROBE [PASS]", "probe")
                            pattern_counts[k] = pattern_counts.get(k, 0) + 1
                        if "CHANGE_TRACKER" in line and basename in line:
                            k = ("CHANGE_TRACKER", "attribution")
                            pattern_counts[k] = pattern_counts.get(k, 0) + 1
                        if "LAUNCH_SUCCESS" in line:
                            k = ("LAUNCH_SUCCESS: True", "launch")
                            pattern_counts[k] = pattern_counts.get(k, 0) + 1
                except Exception:
                    pass
            for (pattern, event_type), count in pattern_counts.items():
                if count > 0:
                    results.append({
                        "pattern":     pattern,
                        "count_min":   max(1, count // max(1, len(logs))),
                        "event_type":  event_type,
                        "description": f"Expected in logs for {basename}",
                    })
        except Exception:
            pass
        return results

    def _do_create_task(self):
        """Create a new task entry in plans/todos.json (phase-dict format) + task_context sidecar."""
        from datetime import datetime
        title = self._t_title.get().strip()
        if not title:
            self._tasks_status.config(text='Title is required.', fg='#ff8888')
            return
        plans_path = Path(__file__).parent.parent.parent / "plans"
        todos_path = plans_path / "todos.json"
        now = datetime.now()
        phase_key = f"phase_new_{now.strftime('%y%m')}"

        try:
            data = json.loads(todos_path.read_text()) if todos_path.exists() else {}
            if not isinstance(data, dict) or 'todos' in data:
                # legacy format or non-dict — reset to phase-dict
                data = {}
        except Exception:
            data = {}

        phase = data.setdefault(phase_key, {})
        task_idx = len(phase) + 1
        task_id = f"task_{now.strftime('%y%m')}_{task_idx}"
        bug_id = self.change_data.get('bug_id') or ''

        task = {
            "id":            task_id,
            "title":         title,
            "priority":      self._t_prio.get().strip() or 'P1',
            "status":        "pending",
            "wherein":       self._t_wherein.get().strip(),
            "description":   self._t_desc.get('1.0', 'end').strip(),
            "marks":         [self.event_id] + ([bug_id] if bug_id else []),
            "task_ids":      [],
            "test_expectations": [],
            "created_at":    now.isoformat(),
            "updated_at":    now.isoformat(),
            "source":        "undo_dialog",
        }
        phase[task_id] = task

        try:
            todos_path.parent.mkdir(parents=True, exist_ok=True)
            todos_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            self._tasks_status.config(text=f'❌ Save failed: {e}', fg='#ff8888')
            logger_util.log_message(f"UNDO_DIALOG: _do_create_task save error: {e}")
            return

        # Write task_context sidecar with inspect_ctx enrichment (v3-B)
        try:
            ctx_dir = plans_path / "Tasks"
            ctx_dir.mkdir(exist_ok=True)
            # Build inspect_snapshot from self.inspect_ctx if available
            _inspect_snap = None
            if self.inspect_ctx:
                _inspect_snap = {
                    "tab_text":          self.inspect_ctx.get("sub_tab"),
                    "parent_label":      self.inspect_ctx.get("sub_notebook"),
                    "src_file":          self.inspect_ctx.get("source_file"),
                    "tab_class":         self.inspect_ctx.get("tab_class"),
                    "blame_event_id":    self.event_id,
                    "context_function":  self.change_data.get("context_function"),
                    "context_class":     self.change_data.get("context_class"),
                    "captured_at":       now.isoformat(),
                }
            # Build blame_risk_summary from change_data
            _risk_sum = None
            if self.change_data:
                _risk_sum = {
                    "risk_level":    self.change_data.get("risk_level"),
                    "risk_reasons":  self.change_data.get("risk_reasons", []),
                    "formatted":     (
                        f"{Path(self.change_data.get('file', '?')).name} — "
                        f"{self.change_data.get('risk_level','?')}({self.change_data.get('risk_confidence',0)}%)"
                    ),
                }
            ctx = {
                "_meta": {
                    "task_id":    task_id,
                    "title":      title,
                    "wherein":    task["wherein"],
                    "generated":  now.isoformat(),
                    "source":     "undo_dialog",
                },
                "changes": [self.event_id],
                "marks":   task["marks"],
                "expected_diffs": [],
                "expected_log_events": self._build_expected_log_events(task["wherein"]),
                "inspect_snapshot": _inspect_snap,
                "version_state": None,
                "5W_at_creation": None,
                "prior_probe_baseline": None,
                "blame_risk_summary": _risk_sum,
                "regression_policy": None,
            }
            (ctx_dir / f"task_context_{task_id}.json").write_text(json.dumps(ctx, indent=2))
        except Exception as e:
            logger_util.log_message(f"UNDO_DIALOG: task_context sidecar error: {e}")

        # L1: Write task_id back-ref into enriched_changes (list — matches activity_integration_bridge:947)
        try:
            manifest = recovery_util.load_version_manifest()
            ec = manifest.get("enriched_changes", {})
            if self.event_id in ec:
                tids = list(ec[self.event_id].get("task_ids") or [])
                if task_id not in tids:
                    tids.append(task_id)
                ec[self.event_id]["task_ids"] = tids
                recovery_util.save_version_manifest(manifest)
                logger_util.log_message(
                    f"UNDO_DIALOG: Linked {task_id} → enriched_changes[{self.event_id}].task_ids")
        except Exception as e:
            logger_util.log_message(f"UNDO_DIALOG: enriched_changes back-ref error: {e}")

        logger_util.log_message(f"UNDO_DIALOG: Created task {task_id} in {phase_key}")
        self._tasks_status.config(text=f'✅ Created {task_id}', fg='#88ff88')
        self._populate_related_tasks()
