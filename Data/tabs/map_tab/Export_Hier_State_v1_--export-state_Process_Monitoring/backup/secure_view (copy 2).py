#!/usr/bin/env python3
import os
import sys
import logging
import traceback
from datetime import datetime

# --- ERROR BOOTSTRAP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
if not os.path.exists(LOG_DIR): 
    os.makedirs(LOG_DIR)
log_file = os.path.join(LOG_DIR, datetime.now().strftime("gui_%Y%m%d_%H%M%S.log"))

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logging.critical(f"FATAL UI ERROR:\n{err}")
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Secure View Error", f"{exc_value}\n\nLog: {log_file}")
        r.destroy()
    except: 
        pass
    traceback.print_exception(exc_type, exc_value, exc_traceback)

# Official config - Clear handlers to ensure logging writes to the new file
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info("--- Secure View Application Started ---")

# Standard Imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import subprocess
import threading
import time
import re
from pathlib import Path

# Project Imports
try:
    from shared_gui import SharedPopupGUI
    from process_organizer import CM, scanner_main, C as ScannerC
    import pyview
except Exception as e:
    logging.critical(f"Module Import Error: {e}")
    raise

class SecureViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure View")
        
        # 1. State & Config
        self.prefs = CM.config.get('user_prefs', {})
        i_cfg = self.prefs.get('inspection_config', {})
        self.root.geometry(self.prefs.get('window_geometry', "1280x800"))
        
        self.hover_enabled = i_cfg.get('enable_hover', True)
        self.hover_delay = int(i_cfg.get('hover_delay', 500))
        self.indicator_pos = i_cfg.get('indicator_pos', 'right')
        self.sticky_selection = i_cfg.get('sticky_bind_selection', True)
        self.hover_job = None

        # 2. Colors & Tagging
        self.colors = {
            "bg": "#1e1e1e", "fg": "#d4d4d4", "sidebar": "#252526", "accent": "#007acc",
            "keyword": "#569cd6", "string": "#ce9178", "comment": "#6a9955", "function": "#dcdcaa",
            "variable": "#9cdcfe", "import": "#c586c0", "text_bg": "#2d2d2d", "error": "#f44336"
        }
        self.hier_colors = self.prefs.get('hier_colors', {})
        
        self.current_dir = SCRIPT_DIR
        self.current_file = None
        self.focused_pid = None
        self.refresh_ms = tk.IntVar(value=self.prefs.get('refresh_rate', 2000))
        self.proc_active = tk.BooleanVar(value=True)
        self.manifest_path = os.path.join(self.current_dir, "manifest.json")
        
        # 3. UI Components
        self.setup_styles()
        self.setup_menu()
        self.setup_layout()
        
        # 4. Tooltip / Hover Setup
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.withdraw()
        self.tooltip.overrideredirect(True)
        self.tip_label = tk.Label(self.tooltip, bg="#333333", fg="white", relief="solid", borderwidth=1, font=("Arial", 9))
        self.tip_label.pack()

        # 5. Initialization
        self.apply_theme(self.prefs.get('theme', 'dark'))
        self.load_manifest()
        self.refresh_file_tree()
        self.refresh_log_list()
        self.tail_latest_log()
        self.update_proc_list()
        
        # 6. Global Bindings
        self.root.bind("<Button-1>", self.on_global_click)
        self.root.bind("<Shift-Button-3>", self.inspect_ui_object)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background=self.colors["sidebar"], foreground=self.colors["fg"], fieldbackground=self.colors["sidebar"])
        style.map("Treeview", background=[('selected', self.colors["accent"])])

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        file_m = tk.Menu(menubar, tearoff=0)
        file_m.add_command(label="Open Directory", command=self.open_directory)
        file_m.add_command(label="Save File", command=self.save_current_file)
        file_m.add_separator()
        file_m.add_command(label="View Crash Logs", command=self.view_crash_logs)
        file_m.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_m)
        
        scan_m = tk.Menu(menubar, tearoff=0)
        scan_m.add_command(label="Quick Scan", command=lambda: self.run_security_scan(False))
        scan_m.add_command(label="Full Scan", command=lambda: self.run_security_scan(True))
        scan_m.add_command(label="View Integrity", command=self.check_integrity)
        menubar.add_cascade(label="Scans", menu=scan_m)
        
        menubar.add_command(label="Tools", command=lambda: SharedPopupGUI(self.root, "tools"))
        menubar.add_command(label="Config", command=lambda: SharedPopupGUI(self.root, "config"))
        self.root.config(menu=menubar)

    def setup_layout(self):
        # 1. Left Panel (Fixed width for Tree)
        self.left_p = ttk.Frame(self.root, width=250)
        self.left_p.pack(side=tk.LEFT, fill=tk.Y)
        self.left_p.pack_propagate(False)
        ttk.Label(self.left_p, text="📁 Project Tree", font=('Arial', 10, 'bold')).pack(pady=5)
        self.tree = ttk.Treeview(self.left_p, show="tree headings")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # 2. Right Panel (Fixed width for Logs)
        self.right_p = ttk.Frame(self.root, width=320)
        self.right_p.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_p.pack_propagate(False)
        act_f = ttk.LabelFrame(self.right_p, text="📡 Activity & Logs")
        act_f.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        sel_f = ttk.Frame(act_f)
        sel_f.pack(fill=tk.X, padx=2, pady=2)
        self.log_selector = ttk.Combobox(sel_f, state="readonly")
        self.log_selector.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.log_selector.bind("<<ComboboxSelected>>", self.on_log_selected)
        ttk.Button(sel_f, text="⟳", width=3, command=self.refresh_log_list).pack(side=tk.LEFT)
        
        self.log_display = tk.Text(act_f, height=15, font=('Monospace', 8), bg="black", fg="#00ff00")
        self.log_display.pack(fill=tk.BOTH, expand=True)
        
        # 3. Center Notebook (Fills remainder)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Hier-View Tab
        self.hier_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.hier_frame, text="Hier-View")
        self.hier_tree = ttk.Treeview(self.hier_frame, columns=("type", "line"), show="tree headings")
        self.hier_tree.heading("#0", text="Element")
        self.hier_tree.heading("type", text="Type")
        self.hier_tree.heading("line", text="Line")
        self.hier_tree.pack(fill=tk.BOTH, expand=True)
        self.hier_tree.bind("<Double-1>", self.on_hier_double_click)
        self.hier_tree.bind("<Motion>", self.on_hier_hover)
        self.hier_tree.bind("<<TreeviewSelect>>", self.on_hier_select)

        # Editor Tab
        self.editor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.editor_frame, text="Editor")
        ed_tools = ttk.Frame(self.editor_frame)
        ed_tools.pack(fill=tk.X)
        ttk.Button(ed_tools, text="🔍 Find", command=self.show_search_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="🛡️ Inspect", command=self.inspect_current_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="💾 Save", command=self.save_current_file).pack(side=tk.LEFT, padx=2)
        
        ed_c = ttk.Frame(self.editor_frame)
        ed_c.pack(fill=tk.BOTH, expand=True)
        self.line_canvas = tk.Canvas(ed_c, width=40, bg="#252526", highlightthickness=0)
        self.line_canvas.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = tk.Text(ed_c, bg="#2d2d2d", font=('Monospace', 11), wrap=tk.NONE, undo=True)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.bind("<KeyRelease>", self.on_editor_change)
        self.editor.bind("<MouseWheel>", self.on_editor_scroll)
        
        # CLI Output Tab
        self.cli_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cli_frame, text="CLI Output")
        self.cli_text = tk.Text(self.cli_frame, bg="black", fg="white", font=('Monospace', 10))
        self.cli_text.pack(fill=tk.BOTH, expand=True)
        
        # Monitor Tab
        self.proc_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.proc_frame, text="Monitor")
        tf_f = ttk.LabelFrame(self.proc_frame, text="🎯 TARGET FOCUS")
        tf_f.pack(fill=tk.X, padx=5, pady=5)
        self.target_label = ttk.Label(tf_f, text="No selection")
        self.target_label.pack(side=tk.LEFT, padx=10)
        self.kill_btn = ttk.Button(tf_f, text="KILL", state="disabled", command=self.kill_targeted_process)
        self.kill_btn.pack(side=tk.RIGHT, padx=5)
        self.suspend_btn = ttk.Button(tf_f, text="SUSP", state="disabled", command=self.suspend_targeted_process)
        self.suspend_btn.pack(side=tk.RIGHT, padx=5)
        
        self.proc_tree = ttk.Treeview(self.proc_frame, columns=("pid", "cpu", "mem", "name", "cmd"), show="headings")
        self.proc_tree.heading("pid", text="PID")
        self.proc_tree.heading("name", text="Name")
        self.proc_tree.pack(fill=tk.BOTH, expand=True)
        self.proc_tree.bind("<<TreeviewSelect>>", self.on_proc_select)
        
        # Context Menus
        self.context_menu = tk.Menu(self.root, tearoff=0)
        for action in self.prefs.get('context_menu_actions', []):
            self.context_menu.add_command(
                label=action['label'], 
                command=lambda a=action['action']: self.execute_menu_action(a)
            )
        
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.proc_tree.bind("<Button-3>", self.show_context_menu)
        self.hier_tree.bind("<Button-3>", self.show_context_menu)

    def execute_menu_action(self, action_name):
        """Safely execute a method by name from the context menu."""
        if hasattr(self, action_name):
            func = getattr(self, action_name)
            func()
        else:
            logging.error(f"Context menu action '{action_name}' not found.")

    def on_hier_select(self, event):
        """Handle sticky binding to selection if enabled."""
        if not self.sticky_selection: return
        sel = self.hier_tree.selection()
        if not sel: return
        
        item_id = sel[0]
        # Get item bounding box to position tooltip next to it
        bbox = self.hier_tree.bbox(item_id)
        if bbox:
            # bbox is (x, y, width, height) relative to widget
            x = self.hier_tree.winfo_rootx() + bbox[0] + bbox[2]
            y = self.hier_tree.winfo_rooty() + bbox[1]
            self.show_hier_tooltip(item_id, x, y, sticky=True)

    # --- Hover Logic (Hier Tab Only) ---
    def on_hier_hover(self, event):
        """Show relationship chain only on Hier-View nodes with a delay and config check."""
        if not self.hover_enabled: return
        
        # If tooltip is 'sticky' (focused), don't update on hover
        if hasattr(self, 'tooltip_focused') and self.tooltip_focused:
            return

        if self.hover_job:
            self.root.after_cancel(self.hover_job)
        
        item = self.hier_tree.identify_row(event.y)
        if item:
            # Pass event coordinates to pin the position
            self.hover_job = self.root.after(self.hover_delay, lambda: self.show_hier_tooltip(item, event.x_root, event.y_root))
        else:
            self.tooltip.withdraw()

    def get_hier_lineage(self, item_id):
        """Trace the parent path of a node in the hierarchical tree."""
        path = []
        curr = item_id
        while curr:
            text = self.hier_tree.item(curr, 'text')
            if text:
                path.insert(0, text)
            curr = self.hier_tree.parent(curr)
        return " > ".join(path)

    def show_hier_tooltip(self, item, x, y, sticky=False):
        vals = self.hier_tree.item(item, "values")
        text = self.hier_tree.item(item, "text")
        
        # Capture lineage for granular context
        lineage = self.get_hier_lineage(item)
        
        # Build granular context string
        kind = vals[0] if vals else 'Node'
        line = vals[1] if len(vals)>1 else 'N/A'
        
        chain = f"Lineage: {lineage}\n"
        chain += f"Element: {text}\nType: {kind}\nLine: {line}"
        
        if len(vals) > 2 and vals[2]:
            chain += f"\nDetails: {vals[2]}"
            
        self.tip_label.config(text=chain, justify=tk.LEFT, padx=10, pady=5)
        self.tooltip.deiconify()
        self.tooltip.update_idletasks()
        
        tw = self.tooltip.winfo_width()
        th = self.tooltip.winfo_height()
        
        # Dynamic Positioning logic
        pos = self.indicator_pos.lower()
        
        if pos == "right":
            nx, ny = x + 20, y
        elif pos == "left":
            nx, ny = x - tw - 20, y
        elif pos == "top":
            nx, ny = x, y - th - 20
        elif pos == "bottom":
            nx, ny = x, y + 40
        else:
            nx, ny = x + 20, y
            
        self.tooltip.geometry(f"+{int(nx)}+{int(ny)}")
        
        if sticky:
            self.tooltip_focused = True
            self.tip_label.config(bg="#444444", borderwidth=2)
        else:
            self.tooltip_focused = False
            self.tip_label.config(bg="#333333", borderwidth=1)

    # --- Inspector Logic ---
    def open_inspector_popup(self):
        w = getattr(self.context_menu, 'widget', None)
        if not w: return
        sel = w.selection()
        if not sel: return
        
        item_id = sel[0]
        item = w.item(item_id)
        
        # Show sticky tooltip next to context menu location
        x = getattr(self, 'last_menu_x', self.root.winfo_pointerx())
        y = getattr(self, 'last_menu_y', self.root.winfo_pointery())
        
        if w == self.hier_tree:
            self.show_hier_tooltip(item_id, x, y, sticky=True)
        else:
            lineage = ""
            if w == self.tree:
                # Simple file tree lineage
                parts = []
                curr = item_id
                while curr:
                    parts.insert(0, w.item(curr, 'text'))
                    curr = w.parent(curr)
                lineage = " / ".join(parts)
            
            msg = f"Lineage: {lineage}\n" if lineage else ""
            msg += f"Technical context for: {item['text']}\n"
            if w == self.tree:
                msg += f"File Path: {item['values'][0]}"
            elif w == self.proc_tree:
                msg += f"PID: {item['values'][0]}\nCommand: {item['values'][4]}"
            messagebox.showinfo("Security Inspector", msg)

    def export_entity_context(self):
        """Export current entity context to clipboard and a markdown file."""
        w = getattr(self.context_menu, 'widget', None)
        if not w: return
        sel = w.selection()
        if not sel: return
        
        item_id = sel[0]
        item = w.item(item_id)
        text = item['text']
        vals = item['values']
        
        ctx = f"# Entity Report: {text}\n\n"
        ctx += f"- **Source Widget**: {w.winfo_name()}\n"
        ctx += f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if w == self.hier_tree:
            ctx += f"- **Lineage**: {self.get_hier_lineage(item_id)}\n"
        
        ctx += "\n"
        
        # Extended: Match running processes
        matching_procs = []
        try:
            import psutil
            search_term = text.lower()
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmd = " ".join(p.info['cmdline'] or [])
                    if search_term in p.info['name'].lower() or search_term in cmd.lower():
                        matching_procs.append(f"- PID: {p.info['pid']} | Name: {p.info['name']} | Command: {cmd[:100]}...")
                except: pass
        except: pass

        if matching_procs:
            ctx += "## Matching Running Processes\n"
            ctx += "\n".join(matching_procs) + "\n\n"
        
        if w == self.tree:
            ctx += f"## File Information\n- **Path**: {vals[0]}\n"
        elif w == self.proc_tree:
            ctx += f"## Process Information\n- **PID**: {vals[0]}\n- **CPU**: {vals[1]}%\n- **Mem**: {vals[2]}%\n- **Command**: {vals[4]}\n"
        elif w == self.hier_tree:
            ctx += f"## Code Element\n- **Type**: {vals[0]}\n- **Line**: {vals[1]}\n"
            if len(vals) > 2: ctx += f"- **Details**: {vals[2]}\n"
            
        # Add to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(ctx)
        
        # Save to file
        filename = f"Entity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        try:
            with open(filename, 'w') as f:
                f.write(ctx)
            messagebox.showinfo("Export Success", f"Context copied to clipboard and saved to {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save file: {e}")

    def inspect_ui_object(self, event):
        w = self.root.winfo_containing(event.x_root, event.y_root)
        if w:
            info = f"Widget: {w.winfo_name()}\nClass: {w.winfo_class()}\nParent: {w.winfo_parent()}"
            messagebox.showinfo("UI Object Context", info)

    def show_context_menu(self, event):
        item = event.widget.identify_row(event.y)
        if item:
            event.widget.selection_set(item)
            self.context_menu.widget = event.widget
            self.last_menu_x = event.x_root
            self.last_menu_y = event.y_root
            self.context_menu.post(event.x_root, event.y_root)
            
            # Position tooltip dynamically relative to the menu event
            if event.widget == self.hier_tree:
                self.show_hier_tooltip(item, event.x_root, event.y_root, sticky=True)

    def on_global_click(self, event):
        self.context_menu.unpost()
        # Hide tooltip if user clicks away from a sticky one
        if hasattr(self, 'tooltip_focused') and self.tooltip_focused:
            tw = self.tooltip.winfo_width()
            th = self.tooltip.winfo_height()
            tx = self.tooltip.winfo_rootx()
            ty = self.tooltip.winfo_rooty()
            if not (tx <= event.x_root <= tx+tw and ty <= event.y_root <= ty+th):
                self.tooltip.withdraw()
                self.tooltip_focused = False

    # --- Feature Methods ---
    def route_to_editor(self):
        w = getattr(self.context_menu, 'widget', self.tree)
        sel = w.selection()
        if not sel: return
        p = None
        if w == self.tree:
            p = w.item(sel[0], "values")[0]
        elif w == self.proc_tree:
            pid = w.item(sel[0], "values")[0]
            try:
                import psutil
                proc = psutil.Process(int(pid))
                for a in proc.cmdline():
                    if a.endswith('.py') and os.path.exists(a):
                        p = os.path.abspath(a); break
            except: pass
        if p and os.path.isfile(p):
            self.load_file_to_editor(p)

    def route_to_hier(self):
        self.route_to_editor()
        self.notebook.select(self.hier_frame)

    def visualize_code(self, path):
        try:
            pf = pyview.analyze_file(Path(path))
            for i in self.hier_tree.get_children():
                self.hier_tree.delete(i)
            
            # Root file node
            root_details = f"Lines: {pf.lines} | Error: {pf.error if pf.error else 'None'}"
            root = self.hier_tree.insert("", "end", text=pf.path.name, values=("FILE", "0", root_details), open=True, tags=("File",))
            
            if pf.imports:
                n = self.hier_tree.insert(root, "end", text="Imports", values=("FOLDER", "", f"Count: {len(pf.imports)}"), open=True)
                for im in pf.imports:
                    details = f"As: {im.value}" if im.value else ""
                    self.hier_tree.insert(n, "end", text=im.name, values=("Import", im.line, details), tags=("Import",))
            
            if pf.elements:
                n = self.hier_tree.insert(root, "end", text="Structure", values=("FOLDER", "", f"Count: {len(pf.elements)}"), open=True)
                for el in pf.elements:
                    tag = el.kind.title()
                    details = f"Range: {el.line}-{el.end_line}" if el.end_line else ""
                    p = self.hier_tree.insert(n, "end", text=el.name, values=(el.kind.upper(), el.line, details), tags=(tag,))
                    for ch in el.children:
                        cdetails = f"Range: {ch.line}-{ch.end_line}" if ch.end_line else ""
                        self.hier_tree.insert(p, "end", text=ch.name, values=("METHOD", ch.line, cdetails), tags=("Method",))
            
            if hasattr(pf, 'strings') and pf.strings:
                sn = self.hier_tree.insert(root, "end", text="Suspicious Strings", values=("FOLDER", "", f"Count: {len(pf.strings)}"), open=False)
                for s in pf.strings:
                    self.hier_tree.insert(sn, "end", text=s.name[:50], values=("STRING", s.line, s.name), tags=("String/IP",))

            for t, c in self.hier_colors.items():
                self.hier_tree.tag_configure(t, foreground=c)
        except Exception as e:
            logging.error(f"Hier Error: {e}")

    def on_hier_double_click(self, event):
        sel = self.hier_tree.selection()
        if sel:
            v = self.hier_tree.item(sel[0], "values")
            if len(v) > 1 and v[1]:
                self.notebook.select(self.editor_frame)
                self.editor.mark_set("insert", f"{v[1]}.0")
                self.editor.see(f"{v[1]}.0")
                self.editor.focus_set()

    def on_editor_change(self, e=None):
        self.update_line_numbers()
        self.apply_syntax_highlighting()

    def on_editor_scroll(self, e=None):
        self.update_line_numbers()

    def update_line_numbers(self):
        self.line_canvas.delete("all")
        i = self.editor.index("@0,0")
        while True:
            d = self.editor.dlineinfo(i)
            if not d: break
            self.line_canvas.create_text(35, d[1], anchor="ne", text=str(i).split(".")[0], fill="#858585")
            i = self.editor.index("%s + 1line" % i)

    def apply_syntax_highlighting(self):
        for t in ["keyword", "string", "comment", "function"]:
            self.editor.tag_configure(t, foreground=self.colors.get(t, "#ffffff"))
            self.editor.tag_remove(t, "1.0", tk.END)
        c = self.editor.get("1.0", tk.END)
        pats = [
            (r'\b(def|class|if|else|import|from|return|for|while|try|except|with|as)\b', "keyword"),
            (r'".*?"|".*?"', "string"), (r'#.*', "comment"), (r'\b[a-zA-Z_]\w*(?=\()', "function")
        ]
        for p, t in pats:
            for m in re.finditer(p, c):
                self.editor.tag_add(t, f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars")

    def apply_theme(self, theme_name):
        themes = {
            "dark": { "bg": "#1e1e1e", "fg": "#d4d4d4", "sidebar": "#252526", "accent": "#007acc", "text_bg": "#2d2d2d" },
            "light": { "bg": "#ffffff", "fg": "#000000", "sidebar": "#f3f3f3", "accent": "#007acc", "text_bg": "#ffffff" },
            "monokai": { "bg": "#272822", "fg": "#f8f8f2", "sidebar": "#1e1f1c", "accent": "#ae81ff", "text_bg": "#272822" }
        }
        cfg = themes.get(theme_name, themes["dark"])
        self.colors.update(cfg)
        self.root.configure(bg=cfg["bg"])
        for txt in [self.editor, self.log_display, self.hier_text if hasattr(self, 'hier_text') else None]:
            if txt: txt.configure(bg=cfg["text_bg"], fg=cfg["fg"], insertbackground=cfg["fg"])
        style = ttk.Style()
        style.configure("Treeview", background=cfg["sidebar"], foreground=cfg["fg"], fieldbackground=cfg["sidebar"])
        CM.config['user_prefs']['theme'] = theme_name
        CM.save_config()

    def load_file_to_editor(self, p):
        try:
            with open(p, 'r', errors='ignore') as f:
                self.editor.delete(1.0, tk.END)
                self.editor.insert(tk.END, f.read())
            self.current_file = p
            self.on_editor_change()
            self.notebook.select(self.editor_frame)
            if p.endswith('.py'): self.visualize_code(p)
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def on_tree_select(self, e):
        try:
            p = self.tree.item(self.tree.selection()[0], "values")[0]
            if os.path.isfile(p):
                self.load_file_to_editor(p)
                if p.endswith('.log'):
                    fn = os.path.basename(p)
                    if fn in self.log_selector['values']:
                        self.log_selector.set(fn); self.on_log_selected(None)
        except: pass

    def save_current_file(self):
        if self.current_file:
            with open(self.current_file, 'w') as f:
                f.write(self.editor.get(1.0, tk.END))
            messagebox.showinfo("Saved", "File updated.")
            self.refresh_file_tree()

    def on_log_selected(self, e):
        p = os.path.join(LOG_DIR, self.log_selector.get())
        if os.path.exists(p):
            with open(p, 'r') as f:
                self.log_display.delete(1.0, tk.END)
                self.log_display.insert(tk.END, f.read())

    def refresh_log_list(self):
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.log')], reverse=True)
        self.log_selector['values'] = ls
        if ls:
            self.log_selector.set(ls[0])

    def tail_latest_log(self):
        if self.log_selector.get() and self.log_selector.current() == 0:
            self.on_log_selected(None)
        self.root.after(5000, self.tail_latest_log)

    def refresh_file_tree(self):
        [self.tree.delete(i) for i in self.tree.get_children()]
        n = self.tree.insert('', 'end', text=os.path.basename(self.current_dir), values=(self.current_dir,), open=True)
        self.add_to_tree(self.current_dir, n)

    def add_to_tree(self, path, parent):
        try:
            for item in sorted(os.listdir(path)):
                if item.startswith('.'): continue
                abs_p = os.path.join(path, item)
                node = self.tree.insert(parent, 'end', text=item, values=(abs_p,))
                if os.path.isdir(abs_p):
                    self.add_to_tree(abs_p, node)
        except: pass

    def on_proc_select(self, e):
        v = self.proc_tree.item(self.proc_tree.selection()[0], "values")
        self.focused_pid = v[0]
        self.target_label.config(text=f"TARGET: [{v[0]}] {v[3]}")
        self.kill_btn.config(state="normal")
        self.suspend_btn.config(state="normal")

    def kill_targeted_process(self):
        try:
            import psutil
            psutil.Process(int(self.focused_pid)).terminate()
            self.update_proc_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def suspend_targeted_process(self):
        try:
            import psutil
            p = psutil.Process(int(self.focused_pid))
            if p.status() == psutil.STATUS_STOPPED:
                p.resume(); self.suspend_btn.config(text="SUSP")
            else:
                p.suspend(); self.suspend_btn.config(text="RESM")
        except: pass

    def toggle_proc_monitor(self):
        if self.proc_active.get(): self.update_proc_list()

    def update_proc_list(self):
        import psutil
        [self.proc_tree.delete(i) for i in self.proc_tree.get_children()]
        procs = []
        for p in psutil.process_iter(['pid', 'cpu_percent', 'memory_percent', 'name', 'cmdline']):
            try:
                procs.append((p.info['pid'], p.info['cpu_percent'], p.info['memory_percent'], p.info['name'], " ".join(p.info['cmdline'] or [])))
            except: pass
        procs.sort(key=lambda x: x[3].lower())
        for p in procs:
            self.proc_tree.insert('', 'end', values=p)
        if self.proc_active.get():
            self.root.after(self.refresh_ms.get(), self.update_proc_list)

    def show_search_dialog(self):
        sw = tk.Toplevel(self.root)
        sw.title("Find")
        sw.geometry("300x100")
        ent = tk.Entry(sw)
        ent.pack(pady=10)
        def find():
            s = ent.get()
            pos = self.editor.search(s, "1.0", tk.END)
            if pos:
                self.editor.tag_add("sel", pos, f"{pos}+{len(s)}c")
                self.editor.see(pos)
        tk.Button(sw, text="Go", command=find).pack()

    def check_integrity(self):
        v, m = CM.verify_integrity()
        messagebox.showinfo("Integrity", f"{('OK' if v else 'FAIL')}\n{m}")

    def run_security_scan(self, rec=False):
        self.cli_text.delete(1.0, tk.END)
        self.notebook.select(self.cli_frame)
        def task():
            cmd = [sys.executable, "process_organizer.py", "--scan", self.current_dir]
            if rec: cmd.append("-r")
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.root.after(0, lambda: self.cli_text.insert(tk.END, res.stdout))
        threading.Thread(target=task).start()

    def open_directory(self):
        p = filedialog.askdirectory()
        if p:
            self.current_dir = p
            self.refresh_file_tree()

    def view_crash_logs(self):
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.startswith('gui_')], reverse=True)
        for ln in ls:
            with open(os.path.join(LOG_DIR, ln), 'r') as f:
                if "ERROR" in f.read():
                    self.log_selector.set(ln)
                    self.on_log_selected(None)
                    return

    def inspect_current_file(self):
        if self.current_file:
            self.visualize_code(self.current_file)
            self.notebook.select(self.hier_frame)

    def load_manifest(self): 
        pass

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = SecureViewApp(root)
        root.mainloop()
    except Exception as e:
        with open("FATAL_BOOT.txt", "a") as f:
            f.write(f"CRASH: {e}\n{traceback.format_exc()}\n")
        sys.exit(1)