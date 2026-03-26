"""
Base class for all GUI tabs
Provides common interface and error handling
"""

import tkinter as tk
from tkinter import ttk, messagebox
from abc import ABC, abstractmethod
from logger_util import log_message

class BaseTab(ABC):
    """Base class for modular GUI tabs"""

    def __init__(self, parent, root, style):
        """
        Initialize the tab.

        Args:
            parent: Parent frame (the notebook tab frame)
            root: Root Tkinter window
            style: ttk.Style object for theming
        """
        self.parent = parent
        self.root = root
        self.style = style
        self.initialized = False
        # Right-click infrastructure — injected at init, no bindings until explicit opt-in
        self._sub_notebooks = []        # [{'notebook': nb, 'label': str}]
        self._probe_active = False       # True while widget-inspect probe mode is running
        self._probe_bindings = []        # [(widget, bind_id)] for cleanup after probe
        self._context_pool = []         # accumulated ctx dicts from Ctrl+Right-click

    @abstractmethod
    def create_ui(self):
        """
        Create the tab UI.
        Must be implemented by subclasses.
        """
        pass

    def safe_create(self):
        """
        Safely create the tab UI with error handling and logging.
        Returns True if successful, False otherwise.
        """
        tab_name = self.__class__.__name__
        log_message(f"BASE_TAB: Attempting to create tab: {tab_name}")
        try:
            self.create_ui()
            self.initialized = True
            log_message(f"BASE_TAB: Successfully created tab: {tab_name}")
            return True
        except Exception as e:
            log_message(f"BASE_TAB ERROR: Failed to create tab: {tab_name}. Error: {e}")
            import traceback
            log_message(f"BASE_TAB TRACEBACK: {traceback.format_exc()}")
            self._show_error(e)
            return False

    def _show_error(self, error):
        """Display error message in the tab."""
        error_frame = ttk.Frame(self.parent)
        error_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=20, pady=20)
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # Use pack inside error_frame (not parent which uses grid)
        ttk.Label(
            error_frame,
            text="⚠️ Tab Failed to Load",
            font=("Arial", 16, "bold"),
            foreground="#ff6b6b"
        ).pack(pady=10)

        ttk.Label(
            error_frame,
            text=f"Error: {str(error)}",
            font=("Arial", 10),
            foreground="#ff6b6b"
        ).pack(pady=5)

        ttk.Label(
            error_frame,
            text="This tab encountered an error. Other tabs should still work.",
            font=("Arial", 9)
        ).pack(pady=5)

        def reload_tab():
            # Clear error display
            for widget in self.parent.winfo_children():
                widget.destroy()
            # Try to reload
            self.safe_create()

        ttk.Button(
            error_frame,
            text="🔄 Retry",
            command=reload_tab
        ).pack(pady=10)

    def bind_mousewheel_to_canvas(self, canvas):
        """
        Bind mousewheel scrolling to a canvas widget.
        This enables natural scrolling when hovering over the canvas.
        Works on Windows, Mac, and Linux.

        Args:
            canvas: tk.Canvas widget to bind mousewheel to
        """
        import platform
        system = platform.system()

        if system == "Linux":
            # Linux uses Button-4 (scroll up) and Button-5 (scroll down)
            def _on_mousewheel_up(event):
                canvas.yview_scroll(-1, "units")

            def _on_mousewheel_down(event):
                canvas.yview_scroll(1, "units")

            def _on_enter(event):
                canvas.bind_all("<Button-4>", _on_mousewheel_up)
                canvas.bind_all("<Button-5>", _on_mousewheel_down)

            def _on_leave(event):
                canvas.unbind_all("<Button-4>")
                canvas.unbind_all("<Button-5>")

            canvas.bind("<Enter>", _on_enter)
            canvas.bind("<Leave>", _on_leave)

        else:
            # Windows and Mac use MouseWheel event
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")

            def _on_enter(event):
                canvas.bind_all("<MouseWheel>", _on_mousewheel)

            def _on_leave(event):
                canvas.unbind_all("<MouseWheel>")

            canvas.bind("<Enter>", _on_enter)
            canvas.bind("<Leave>", _on_leave)

    def register_feature(self, feature_name, widget=None, status="active"):
        """
        Register a child feature/panel for tracking.
        Enables blame inference when features fail at runtime.
        """
        if not hasattr(self, '_registered_features'):
            self._registered_features = {}
        self._registered_features[feature_name] = {
            'status': status,
            'widget': widget,
            'tab': self.__class__.__name__
        }
        log_message(f"BASE_TAB: Registered feature '{feature_name}' in {self.__class__.__name__} [{status}]")
        if widget is not None:
            self._bind_default_right_click(widget, feature_name)

    def mark_feature_failed(self, feature_name, error=None):
        """Mark a registered feature as failed with error context."""
        if hasattr(self, '_registered_features') and feature_name in self._registered_features:
            self._registered_features[feature_name]['status'] = 'failed'
            self._registered_features[feature_name]['error'] = str(error) if error else 'Unknown'
        log_message(f"BASE_TAB: Feature '{feature_name}' FAILED in {self.__class__.__name__}: {error}")

    def get_feature_status(self):
        """Return status of all registered features for this tab."""
        return getattr(self, '_registered_features', {})

    def safe_after(self, delay, callback, *args, feature_name=None):
        """
        Wrapped version of tkinter after() that catches and logs errors.
        Use instead of self.parent.after() to capture runtime errors.
        """
        def wrapped():
            try:
                callback(*args)
            except Exception as e:
                import traceback as tb
                tab_name = self.__class__.__name__
                log_message(f"BASE_TAB RUNTIME ERROR in {tab_name}"
                           f"{f' [{feature_name}]' if feature_name else ''}: {e}")
                log_message(f"BASE_TAB TRACEBACK: {tb.format_exc()}")
                if feature_name:
                    self.mark_feature_failed(feature_name, e)
        return self.parent.after(delay, wrapped)

    def safe_command(self, callback, widget_name='unknown', feature_name=None):
        """Wrap a button/callback command with UX event logging and error capture.
        Opt-in: use as command=self.safe_command(self.do_thing, 'my_button').
        Fires #EVENT log marks and logs to UX_EVENT_LOG for baseline tracking.
        #[Mark:SAFE_COMMAND]
        """
        tab_name = self.__class__.__name__

        def _wrapped(*args, **kwargs):
            try:
                result = callback(*args, **kwargs)
                log_message_fn = getattr(__import__('logger_util'), 'log_ux_event', None)
                if log_message_fn:
                    log_message_fn(tab_name, 'callback_fired', widget_name, 'fired')
                return result
            except Exception as e:
                import traceback as tb
                try:
                    import logger_util as _lu
                    _lu.log_ux_event(tab_name, 'callback_error', widget_name, 'error', str(e))
                    _lu.log_message(f"{tab_name.upper()}: ERROR in {widget_name}: {e}")
                    _lu.log_message(f"{tab_name.upper()}: TRACEBACK: {tb.format_exc()}")
                except Exception:
                    pass
                if feature_name:
                    self.mark_feature_failed(feature_name, str(e))

        return _wrapped

    def add_context_menu(self, widget, label=None):
        """Bind a right-click context menu to any widget. Opt-in.
        Menu: Undo Change, View Blame, Risk Detail, Profile.
        Usage: self.add_context_menu(my_treeview, 'My Feature')
        #[Mark:CONTEXT_MENU]
        """
        _label = label or self.__class__.__name__
        widget.bind('<Button-3>', lambda e: self._show_context_menu(e, _label))

    def _show_context_menu(self, event, context_label):
        """Show right-click context menu at cursor position."""
        import tkinter as tk
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(
            label=f"↶ Undo Change  [{context_label}]",
            command=lambda: self._context_open_dialog(None)
        )
        menu.add_command(
            label="🔍 View Blame",
            command=lambda: self._context_open_dialog('blame_risk')
        )
        menu.add_command(
            label="⚠ Risk Detail",
            command=lambda: self._context_open_dialog('blame_risk')
        )
        menu.add_separator()
        menu.add_command(
            label="🌳 Profile",
            command=lambda: self._context_open_dialog('profile')
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _context_open_dialog(self, initial_tab=None):
        """Find the most recent change event for this tab and open UndoChangesDialog.
        Uses TAB_REGISTRY source_file to match enriched_changes.
        #[Mark:CONTEXT_MENU]
        """
        try:
            import recovery_util
            import logger_util
            import sys
            import os
            # UndoChangesDialog lives in tabs/settings_tab/undo_changes.py
            _here = os.path.dirname(__file__)
            sys.path.insert(0, os.path.dirname(_here))
            from tabs.settings_tab.undo_changes import UndoChangesDialog
        except ImportError as _e:
            from tkinter import messagebox
            messagebox.showerror("Import Error", f"Cannot load dialog: {_e}")
            return

        tab_name = self.__class__.__name__
        tab_reg = logger_util.TAB_REGISTRY.get(tab_name, {})
        source_file = tab_reg.get('source_file', '') or ''

        manifest = recovery_util.load_version_manifest()
        enriched = manifest.get('enriched_changes', {})

        # Find matching events for this source file
        src_base = source_file.split('/')[-1] if '/' in source_file else source_file
        matching = [
            (eid, ch) for eid, ch in enriched.items()
            if src_base and ch.get('file', '').endswith(src_base)
        ]
        if not matching:
            from tkinter import messagebox
            messagebox.showinfo(
                "No Changes Found",
                f"No recorded change events found for {tab_name}.\n"
                f"Source file: {src_base or '(unknown)'}\n\n"
                "Changes are recorded by the live watcher after editing files."
            )
            return

        # Use highest event number = most recent
        latest_eid = max(matching, key=lambda x: x[0])[0]
        log_message(f"CONTEXT_MENU: Opening dialog for {tab_name} → {latest_eid} (initial_tab={initial_tab})")
        UndoChangesDialog(self.parent, latest_eid, manifest, initial_tab=initial_tab)

    # -----------------------------------------------------------------------
    # Sub-notebook right-click binding (explicit opt-in per tab)
    # -----------------------------------------------------------------------

    def bind_sub_notebook(self, nb, label=''):
        """Bind right-click context menu to a sub-notebook's tab headers.
        Call once after creating any inner ttk.Notebook. Non-conflicting —
        uses add='+' so existing <<NotebookTabChanged>> bindings are preserved.
        """
        self._sub_notebooks.append({'notebook': nb, 'label': label})
        nb.bind('<Button-3>',
                lambda e, n=nb, lbl=label: self._on_sub_notebook_right_click(e, n, lbl),
                add='+')

    def _on_sub_notebook_right_click(self, event, nb, label):
        """Right-click on a sub-notebook tab header — gate for probe + context copy."""
        try:
            idx = nb.index(f"@{event.x},{event.y}")
            tab_text = nb.tab(idx, 'text')
        except Exception:
            return

        # Ctrl+Right-click → pool the context instead of showing menu
        if event.state & 0x4:
            ctx = self._build_subtab_ctx_dict(nb, idx, tab_text, label)
            self._pool_add(ctx)
            return

        # Find the content frame for this tab so probe knows its scope
        try:
            content_frame = nb.nametowidget(nb.tabs()[idx])
        except Exception:
            content_frame = None

        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(
            label=f"🔄 Refresh '{tab_text}'",
            command=lambda: self._refresh_sub_tab(nb, idx, tab_text)
        )
        menu.add_separator()
        menu.add_command(
            label=f"📋 Copy '{tab_text}' context + profile",
            command=lambda: self._copy_subtab_context(nb, idx, tab_text, label)
        )
        menu.add_separator()
        if content_frame is not None:
            if self._probe_active:
                menu.add_command(
                    label="⬛ Cancel widget inspect",
                    command=self._probe_cancel
                )
            else:
                menu.add_command(
                    label="🔍 Inspect a widget in this sub-tab…",
                    command=lambda: self._probe_enter(content_frame, tab_text)
                )
        menu.add_separator()
        menu.add_command(
            label="↶ Undo last change",
            command=lambda: self._context_open_dialog(None)
        )
        # ── Blame & Task section ──────────────────────────────────────────────
        menu.add_separator()
        blame_info = self._get_blame_context()
        inspect_ctx = self._build_subtab_ctx_dict(nb, idx, tab_text, label)
        if blame_info:
            eid  = blame_info.get('event_id', '?')
            risk = blame_info.get('risk_level', '?')
            has_bug = bool(blame_info.get('bug_id'))
            menu.add_command(
                label=f"🔗 Latest change: {eid}  [{risk}]",
                command=lambda bi=blame_info, ic=inspect_ctx: self._open_undo_dialog_for_blame(bi, 'tasks', inspect_ctx=ic)
            )
            if has_bug:
                menu.add_command(
                    label=f"🐛 Task from crash  [{blame_info['bug_id'][:12]}]",
                    command=lambda bi=blame_info, ic=inspect_ctx: self._open_undo_dialog_for_blame(bi, 'tasks', inspect_ctx=ic)
                )
        else:
            menu.add_command(label="🔗 Latest change  (none recorded)", state='disabled')
        pool_n = len(self._context_pool)
        menu.add_command(
            label=f"📦 Context pool ({pool_n})" if pool_n else "📦 Context pool  (empty)",
            command=self._show_pool_popup
        )
        # Use menu.post() — no X11 grab, WM dismisses on outside click
        menu.post(event.x_root, event.y_root)

    # -----------------------------------------------------------------------
    # Probe mode — temporary widget-inspect triggered from sub-tab gate
    # Non-conflicting: uses <ButtonPress-1> add='+', cleans up after capture
    # -----------------------------------------------------------------------

    def _probe_enter(self, frame, source_label):
        """Enter probe mode: right-click any widget to capture its full profile.
        Uses <Button-3> so button commands never execute during inspection.
        Visual banner is shown at the top of the frame while active.
        """
        if self._probe_active:
            self._probe_cancel()
        self._probe_active = True
        self._probe_source_label = source_label
        self._probe_frame = frame

        # Visual banner — small label placed at top of frame
        self._probe_banner = tk.Label(
            frame,
            text="🔍 INSPECT MODE  •  Right-click any widget to copy its profile  •  Esc = cancel",
            bg='#1a3a1a', fg='#88ff88',
            font=('Arial', 8, 'bold'),
            relief='flat', padx=6, pady=3,
            cursor='crosshair',
        )
        try:
            self._probe_banner.place(relx=0, rely=0, relwidth=1, anchor='nw')
            self._probe_banner.lift()
        except Exception:
            self._probe_banner = None

        # Bind right-click on all children — add='+' so nothing existing is removed
        def _bind_probe(widget):
            try:
                bid = widget.bind(
                    '<Button-3>',
                    lambda e, w=widget: (self._probe_capture(w), 'break')[1],
                    add='+'
                )
                self._probe_bindings.append((widget, '<Button-3>', bid))
            except Exception:
                pass
            try:
                for child in widget.winfo_children():
                    _bind_probe(child)
            except Exception:
                pass

        _bind_probe(frame)

        # Cursor on the frame itself
        try:
            frame.config(cursor='crosshair')
        except Exception:
            pass

        # ESC to cancel
        self._probe_esc_id = self.root.bind(
            '<Escape>', lambda e: self._probe_cancel(), add='+'
        )
        log_message(f"BASE_TAB: Probe ACTIVE on '{source_label}' — right-click any widget")

    def _probe_capture(self, widget):
        """Capture right-clicked widget's full profile and exit probe mode."""
        # Skip capture if the widget IS the probe banner itself
        if widget is getattr(self, '_probe_banner', None):
            return
        source_label = getattr(self, '_probe_source_label', '')
        self._probe_cancel()  # Clean up before copy so clipboard is ready
        self._copy_widget_context(widget, feature_name=None, source_label=source_label)
        try:
            _wtxt = widget.cget('text')
        except Exception:
            _wtxt = '?'
        log_message(f"BASE_TAB: Probe captured {type(widget).__name__} text={_wtxt!r}")

    def _probe_cancel(self):
        """Exit probe mode — remove banner, restore cursor, clean up all temp bindings."""
        self._probe_active = False

        # Remove banner
        try:
            if getattr(self, '_probe_banner', None):
                self._probe_banner.destroy()
                self._probe_banner = None
        except Exception:
            pass

        # Remove probe bindings
        for widget, event_name, bid in self._probe_bindings:
            try:
                widget.unbind(event_name, bid)
            except Exception:
                pass
        self._probe_bindings.clear()

        # Restore frame cursor
        try:
            if getattr(self, '_probe_frame', None):
                self._probe_frame.config(cursor='')
        except Exception:
            pass

        # Remove ESC binding
        try:
            self.root.unbind('<Escape>', getattr(self, '_probe_esc_id', None))
        except Exception:
            pass

        log_message("BASE_TAB: Probe mode exited")

    def _refresh_sub_tab(self, nb, idx, tab_text):
        """Fire refresh() for this tab and log the UX event."""
        try:
            from logger_util import log_ux_event, log_message
            tab_name = type(self).__name__
            log_ux_event(tab_name, 'sub_tab_refresh', tab_text, 'fired')
            self.refresh()
            log_message(f"BASE_TAB: Refresh OK — '{tab_text}' in {tab_name}")
        except Exception as e:
            try:
                from logger_util import log_message
                log_message(f"BASE_TAB: Refresh ERROR in {type(self).__name__}: {e}")
            except Exception:
                pass

    # -----------------------------------------------------------------------
    # Widget right-click for explicitly register_feature'd widgets
    # -----------------------------------------------------------------------

    def _bind_default_right_click(self, widget, feature_name=None):
        """Bind right-click to a widget registered via register_feature().
        add='+' — never overrides existing <Button-3> bindings in the widget.
        """
        widget.bind('<Button-3>',
                    lambda e, w=widget, fn=feature_name: self._widget_right_click(e, w, fn),
                    add='+')

    def _widget_right_click(self, event, widget, feature_name):
        """Right-click handler for explicitly registered widgets."""
        label = feature_name or type(widget).__name__
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(
            label=f"📋 Copy '{label}' context + profile",
            command=lambda: self._copy_widget_context(widget, feature_name)
        )
        menu.add_separator()
        menu.add_command(
            label="↶ Undo last change",
            command=lambda: self._context_open_dialog(None)
        )
        menu.add_command(
            label="⚙ Right-click settings…",
            command=lambda: self._context_open_dialog('profile')
        )
        menu.post(event.x_root, event.y_root)

    # -----------------------------------------------------------------------
    # Context / profile copy helpers
    # -----------------------------------------------------------------------

    def _copy_widget_context(self, widget, feature_name=None, source_label=None):
        """Copy full widget context + AST profile to clipboard as JSON."""
        import json, inspect, os, sys
        src_file = inspect.getfile(type(self))

        ctx = {
            "tab_class": type(self).__name__,
            "source_file": src_file,
            "sub_tab": source_label,
            "feature": feature_name,
            "widget_type": type(widget).__name__,
            "widget_module": type(widget).__module__,
        }

        # Widget text / value
        for attr, key in (('cget("text")', 'text'), ('get()', 'value')):
            try:
                ctx['text'] = widget.cget('text')
            except Exception:
                pass
            break
        try:
            ctx['value'] = widget.get()
        except Exception:
            pass
        try:
            ctx['content'] = widget.get('1.0', 'end').strip()[:500]
        except Exception:
            pass

        # Registered feature status
        if feature_name and hasattr(self, '_registered_features'):
            ctx['registered_status'] = (
                self._registered_features.get(feature_name, {}).get('status')
            )

        # AST profile — classes, methods with line numbers, marks, source snippets
        try:
            _data_dir = os.path.dirname(os.path.dirname(__file__))
            if _data_dir not in sys.path:
                sys.path.insert(0, _data_dir)
            from profile_util import analyze_script
            profile = analyze_script(src_file)

            # Read source lines for snippet extraction
            try:
                with open(src_file, 'r', encoding='utf-8', errors='replace') as _f:
                    _src_lines = _f.readlines()
            except Exception:
                _src_lines = []

            def _snippet(lineno, count=8):
                if not _src_lines or lineno < 1:
                    return None
                start = max(0, lineno - 1)
                return ''.join(_src_lines[start:start + count]).rstrip()

            # Full class list with methods + line numbers
            ctx['classes'] = profile.get('classes', [])

            # Methods matching feature name or widget text
            search = (feature_name or ctx.get('text') or '').lower()
            matched_methods = []
            for cls in profile.get('classes', []):
                for m_name in cls.get('methods', []):
                    if search and search in m_name.lower():
                        matched_methods.append({
                            'class': cls['name'],
                            'method': m_name,
                            'class_lineno': cls.get('lineno'),
                        })
            for fn in profile.get('functions', []):
                if search and search in fn.get('name', '').lower():
                    matched_methods.append({
                        'function': fn['name'],
                        'lineno': fn.get('lineno'),
                        'snippet': _snippet(fn.get('lineno', 0)),
                    })
            if matched_methods:
                ctx['matched_definitions'] = matched_methods

            ctx['marks'] = profile.get('marks', [])
            ctx['imports'] = profile.get('imports', [])

        except Exception as ex:
            ctx['profile_error'] = str(ex)

        self._clipboard_copy(json.dumps(ctx, indent=2, ensure_ascii=False))

    def _build_subtab_ctx_dict(self, nb, idx, tab_text, parent_label):
        """Build and return sub-tab context dict (shared by copy and pool paths)."""
        import inspect, os, sys
        src_file = inspect.getfile(type(self))
        ctx = {
            "tab_class": type(self).__name__,
            "source_file": src_file,
            "sub_notebook": parent_label,
            "sub_tab": tab_text,
            "sub_tab_index": idx,
            "total_sub_tabs": nb.index("end"),
            "all_sub_tabs": [nb.tab(i, 'text') for i in range(nb.index("end"))],
        }
        # AST profile of this tab's source
        try:
            _data_dir = os.path.dirname(os.path.dirname(__file__))
            if _data_dir not in sys.path:
                sys.path.insert(0, _data_dir)
            from profile_util import analyze_script
            profile = analyze_script(src_file)
            ctx['classes'] = profile.get('classes', [])
            ctx['marks'] = profile.get('marks', [])
            ctx['imports'] = profile.get('imports', [])
        except Exception as ex:
            ctx['profile_error'] = str(ex)
        return ctx

    def _copy_subtab_context(self, nb, idx, tab_text, parent_label):
        """Copy sub-tab context + full tab AST profile to clipboard."""
        import json
        ctx = self._build_subtab_ctx_dict(nb, idx, tab_text, parent_label)
        self._clipboard_copy(json.dumps(ctx, indent=2, ensure_ascii=False))

    def _clipboard_copy(self, text):
        """Copy text to clipboard. Returns True on success. Shows brief toast."""
        success = False
        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(text)
            success = True
        except Exception:
            try:
                import pyperclip
                pyperclip.copy(text)
                success = True
            except Exception:
                pass
        self._show_copy_toast(success, text)
        return success

    def _show_copy_toast(self, success, text=''):
        """Show a 1.5-second toast: '✅ Copied (N chars)' or '❌ Clipboard failed'."""
        try:
            toast = tk.Toplevel(self.root)
            toast.overrideredirect(True)
            toast.attributes('-topmost', True)
            rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
            rw = self.root.winfo_width()
            toast.geometry(f"+{rx + rw - 320}+{ry + 8}")
            if success:
                preview = text[:60].replace('\n', ' ')
                msg = (f"✅ Copied ({len(text)} chars)   {preview}…"
                       if len(text) > 60 else f"✅ Copied   {text[:80]}")
                bg, fg = '#1e3d1e', '#88ff88'
            else:
                msg = "❌ Clipboard copy failed"
                bg, fg = '#3d1e1e', '#ff8888'
            tk.Label(toast, text=msg, bg=bg, fg=fg,
                     font=('Arial', 9), padx=10, pady=6,
                     relief='flat', anchor='w').pack(fill='x')
            toast.after(1500, toast.destroy)
        except Exception:
            pass  # toast failure must never propagate

    def _get_blame_context(self):
        """Return most recent enriched_change dict for this tab's source file."""
        try:
            import inspect, os
            import recovery_util as ru
            src_base = os.path.basename(inspect.getfile(type(self)))
            manifest = ru.load_version_manifest()
            matching = [
                (eid, ch) for eid, ch in manifest.get('enriched_changes', {}).items()
                if os.path.basename(ch.get('file', '')) == src_base
            ]
            if not matching:
                return None
            eid, ch = max(matching, key=lambda x: x[1].get('timestamp', ''))
            ch = dict(ch)
            ch['event_id'] = eid
            active_ts = manifest.get('active_version')
            ch['bug_id'] = manifest.get('versions', {}).get(active_ts or '', {}).get('bug_id')
            ch['_manifest'] = manifest
            return ch
        except Exception:
            return None

    def _open_undo_dialog_for_blame(self, blame_info, initial_tab='tasks', inspect_ctx=None):
        """Open UndoChangesDialog pointing at the blame event."""
        import sys, os
        try:
            _data = os.path.dirname(os.path.dirname(__file__))
            if _data not in sys.path:
                sys.path.insert(0, _data)
            from tabs.settings_tab.undo_changes import UndoChangesDialog
            manifest = (blame_info.get('_manifest') or
                        __import__('recovery_util').load_version_manifest())
            UndoChangesDialog(self.parent, blame_info['event_id'], manifest,
                              initial_tab=initial_tab, inspect_ctx=inspect_ctx)
        except Exception as e:
            from logger_util import log_message
            log_message(f"BASE_TAB: Cannot open blame dialog: {e}")

    def _pool_add(self, ctx):
        """Add a context dict to the pool and show a brief badge."""
        self._context_pool.append(ctx)
        n = len(self._context_pool)
        self._show_copy_toast(
            True,
            f"[Pool +1 = {n} items]  {ctx.get('sub_tab') or ctx.get('feature') or '?'}"
        )

    def _show_pool_popup(self):
        """Show a popup listing all pooled context captures."""
        import json
        popup = tk.Toplevel(self.root)
        popup.title(f"Context Pool ({len(self._context_pool)} items)")
        popup.geometry("560x340")
        popup.configure(bg='#2b2b2b')

        listbox = tk.Listbox(popup, bg='#1e1e1e', fg='#cccccc',
                             selectbackground='#3a3a3a', font=('Courier', 9))
        listbox.pack(fill='both', expand=True, padx=8, pady=(8, 4))
        for i, c in enumerate(self._context_pool):
            label = (f"[{i+1}]  {c.get('sub_notebook','?')} › "
                     f"{c.get('sub_tab') or c.get('feature') or c.get('widget_type','?')}")
            listbox.insert('end', label)

        btn_frame = tk.Frame(popup, bg='#2b2b2b')
        btn_frame.pack(fill='x', padx=8, pady=(0, 8))

        def _copy_all():
            self._clipboard_copy(json.dumps(self._context_pool, indent=2, ensure_ascii=False))

        def _clear():
            self._context_pool.clear()
            popup.destroy()

        tk.Button(btn_frame, text='📋 Copy all as JSON', bg='#1a3a1a', fg='#88ff88',
                  command=_copy_all).pack(side='left', padx=4)
        tk.Button(btn_frame, text='🗑 Clear pool', bg='#3a1a1a', fg='#ff8888',
                  command=_clear).pack(side='left', padx=4)
        tk.Button(btn_frame, text='Close', bg='#2b2b2b', fg='#cccccc',
                  command=popup.destroy).pack(side='right', padx=4)

    def refresh(self):
        """
        Refresh tab content.
        Override in subclasses if needed.
        """
        pass
