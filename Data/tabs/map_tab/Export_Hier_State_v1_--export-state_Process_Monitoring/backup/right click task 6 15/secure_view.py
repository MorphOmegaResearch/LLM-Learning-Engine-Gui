#!/usr/bin/env python3
import os
import sys
import logging
import traceback
from datetime import datetime

# --- EMERGENCY BOOTSTRAP LOGGING ---
try:
    with open("BOOT_LOG.txt", "a") as f:
        f.write(f"\n--- Launch Attempt: {datetime.now()} ---\n")
except: pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
log_file = os.path.join(LOG_DIR, datetime.now().strftime("gui_%Y%m%d_%H%M%S.log"))

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"\n!!! FATAL CRASH !!!\n{err_msg}", file=sys.stderr)
    try: logging.critical(f"FATAL UI CRASH:\n{err_msg}")
    except: pass
    try:
        import tkinter as tk; from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("Secure View - Fatal Error", f"{exc_value}\n\nLog: {log_file}")
        root.destroy()
    except: pass

sys.excepthook = handle_exception
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    logging.critical(f"Failed to import project modules: {e}")
    raise

class SecureViewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure View")
        
        # 1. Load Config & Prefs
        self.prefs = CM.config.get('user_prefs', {})
        self.root.geometry(self.prefs.get('window_geometry', "1280x800"))
        
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
        self.manifest_path = os.path.join(self.current_dir, "manifest.json")
        
        self.setup_styles()
        self.setup_menu()
        self.setup_layout()
        
        # 3. Tooltip / Hover Setup
        self.tooltip = tk.Toplevel(self.root); self.tooltip.withdraw(); self.tooltip.overrideredirect(True)
        self.tip_label = tk.Label(self.tooltip, bg="#333333", fg="white", relief="solid", borderwidth=1, font=("Arial", 9)); self.tip_label.pack()

        # 4. Initialization
        self.apply_theme(self.prefs.get('theme', 'dark'))
        self.load_manifest()
        self.refresh_file_tree()
        self.refresh_log_list()
        self.tail_latest_log()
        
        # 5. Global Bindings
        self.root.bind("<Button-1>", self.on_global_click)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background=self.colors["sidebar"], foreground=self.colors["fg"], fieldbackground=self.colors["sidebar"])
        style.map("Treeview", background=[('selected', self.colors["accent"])])
        
        # Hier-View Specific Tags for Colors
        for tag, color in self.hier_colors.items():
            self.hier_tree.tag_configure(tag, foreground=color) if hasattr(self, 'hier_tree') else None

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
        self.left_p = ttk.Frame(self.root, width=250); self.left_p.pack(side=tk.LEFT, fill=tk.Y)
        self.tree = ttk.Treeview(self.left_p, show="tree headings"); self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        self.right_p = ttk.Frame(self.root, width=320); self.right_p.pack(side=tk.RIGHT, fill=tk.Y)
        act_f = ttk.LabelFrame(self.right_p, text="📡 Activity & Logs"); act_f.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        sel_f = ttk.Frame(act_f); sel_f.pack(fill=tk.X, padx=2, pady=2)
        self.log_selector = ttk.Combobox(sel_f, state="readonly"); self.log_selector.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.log_selector.bind("<<ComboboxSelected>>", self.on_log_selected)
        ttk.Button(sel_f, text="⟳", width=3, command=self.refresh_log_list).pack(side=tk.LEFT)
        self.log_display = tk.Text(act_f, height=15, font=('Monospace', 8), bg="black", fg="#00ff00"); self.log_display.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(self.root); self.notebook.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Hier-View
        self.hier_frame = ttk.Frame(self.notebook); self.notebook.add(self.hier_frame, text="Hier-View")
        self.hier_tree = ttk.Treeview(self.hier_frame, columns=("type", "line", "value"), show="tree headings")
        self.hier_tree.heading("#0", text="Element"); self.hier_tree.heading("type", text="Type"); self.hier_tree.heading("line", text="Line")
        self.hier_tree.pack(fill=tk.BOTH, expand=True); self.hier_tree.bind("<Double-1>", self.on_hier_double_click)

        # Editor
        self.editor_frame = ttk.Frame(self.notebook); self.notebook.add(self.editor_frame, text="Editor")
        ed_tools = ttk.Frame(self.editor_frame); ed_tools.pack(fill=tk.X)
        ttk.Button(ed_tools, text="🔍 Find", command=self.show_search_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="🛡️ Inspection", command=self.inspect_current_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(ed_tools, text="💾 Save", command=self.save_current_file).pack(side=tk.LEFT, padx=2)
        ed_c = ttk.Frame(self.editor_frame); ed_c.pack(fill=tk.BOTH, expand=True)
        self.line_canvas = tk.Canvas(ed_c, width=40, bg="#252526", highlightthickness=0); self.line_canvas.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = tk.Text(ed_c, bg="#2d2d2d", font=('Monospace', 11), wrap=tk.NONE, undo=True); self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.bind("<KeyRelease>", self.on_editor_change); self.editor.bind("<MouseWheel>", self.on_editor_scroll)
        
        self.cli_frame = ttk.Frame(self.notebook); self.notebook.add(self.cli_frame, text="CLI Output")
        self.cli_text = tk.Text(self.cli_frame, bg="black", fg="white"); self.cli_text.pack(fill=tk.BOTH, expand=True)

        self.proc_frame = ttk.Frame(self.notebook); self.notebook.add(self.proc_frame, text="Monitor")
        tf_f = ttk.LabelFrame(self.proc_frame, text="🎯 TARGET FOCUS"); tf_f.pack(fill=tk.X, padx=5, pady=5)
        self.target_label = ttk.Label(tf_f, text="No selection"); self.target_label.pack(side=tk.LEFT, padx=10)
        self.kill_btn = ttk.Button(tf_f, text="KILL", state="disabled", command=self.kill_targeted_process); self.kill_btn.pack(side=tk.RIGHT, padx=5)
        self.suspend_btn = ttk.Button(tf_f, text="SUSP", state="disabled", command=self.suspend_targeted_process); self.suspend_btn.pack(side=tk.RIGHT, padx=5)
        self.proc_tree = ttk.Treeview(self.proc_frame, columns=("pid", "cpu", "mem", "name", "cmd"), show="headings")
        self.proc_tree.heading("pid", text="PID"); self.proc_tree.heading("name", text="Name"); self.proc_tree.pack(fill=tk.BOTH, expand=True)
        self.proc_tree.bind("<<TreeviewSelect>>", self.on_proc_select); self.proc_tree.bind("<Motion>", self.on_proc_hover)
        
        # Configurable Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        for action in self.prefs.get('context_menu_actions', []):
            self.context_menu.add_command(label=action['label'], 
                                         command=lambda a=action['action']: getattr(self, a)())
        
        self.tree.bind("<Button-3>", self.show_context_menu); self.proc_tree.bind("<Button-3>", self.show_context_menu)

    def on_global_click(self, event): self.context_menu.unpost()
    def show_context_menu(self, event):
        item = event.widget.identify_row(event.y)
        if item:
            event.widget.selection_set(item); self.context_menu.widget = event.widget
            self.context_menu.post(event.x_root, event.y_root)

    def route_to_editor(self):
        w = getattr(self.context_menu, 'widget', self.tree); sel = w.selection()
        if not sel: return
        path = None
        if w == self.tree: path = self.tree.item(sel[0], "values")[0]
        else:
            pid = self.proc_tree.item(sel[0], "values")[0]
            try:
                import psutil; p = psutil.Process(int(pid))
                for a in p.cmdline(): 
                    if a.endswith('.py') and os.path.exists(a): path = os.path.abspath(a); break
            except: pass
        if path and os.path.isfile(path): self.load_file_to_editor(path)

    def route_to_hier(self): self.route_to_editor(); self.notebook.select(self.hier_frame)
    def inspect_current_file(self):
        if self.current_file: self.visualize_code(self.current_file); self.notebook.select(self.hier_frame)

    def visualize_code(self, path):
        try:
            pf = pyview.analyze_file(Path(path))
            for i in self.hier_tree.get_children(): self.hier_tree.delete(i)
            root = self.hier_tree.insert("", "end", text=pf.path.name, open=True, tags=("File",))
            
            # Use Config Colors
            if pf.imports:
                n = self.hier_tree.insert(root, "end", text="Imports", open=True)
                for im in pf.imports: self.hier_tree.insert(n, "end", text=im.name, values=("Import", im.line), tags=("Import",))
            
            if pf.elements:
                n = self.hier_tree.insert(root, "end", text="Structure", open=True)
                for el in pf.elements:
                    tag = el.kind.title()
                    p = self.hier_tree.insert(n, "end", text=el.name, values=(el.kind.upper(), el.line), tags=(tag,))
                    for ch in el.children:
                        ctag = ch.kind.title()
                        self.hier_tree.insert(p, "end", text=ch.name, values=("Method", ch.line), tags=(ctag,))
            
            if pf.strings:
                n = self.hier_tree.insert(root, "end", text="Suspicious Strings", open=False)
                for s in pf.strings: self.hier_tree.insert(n, "end", text=s.name, values=("String/IP", s.line), tags=("String/IP",))
            
            # Apply Tags from Prefs
            for tag, color in self.hier_colors.items():
                self.hier_tree.tag_configure(tag, foreground=color)
                    
        except Exception as e: logging.error(f"Hier View Error: {e}")

    def on_hier_double_click(self, event):
        sel = self.hier_tree.selection()
        if sel:
            vals = self.hier_tree.item(sel[0], "values")
            if len(vals) > 1:
                line = vals[1]
                if line:
                    self.notebook.select(self.editor_frame)
                    self.editor.mark_set("insert", f"{line}.0"); self.editor.see(f"{line}.0"); self.editor.focus_set()

    def on_editor_change(self, e=None): self.update_line_numbers(); self.apply_syntax_highlighting()
    def on_editor_scroll(self, e=None): self.update_line_numbers()
    def update_line_numbers(self):
        self.line_canvas.delete("all"); i = self.editor.index("@0,0")
        while True:
            d = self.editor.dlineinfo(i)
            if not d: break
            self.line_canvas.create_text(35, d[1], anchor="ne", text=str(i).split(".")[0], fill="#858585")
            i = self.editor.index("%s + 1line" % i)

    def apply_syntax_highlighting(self):
        for t in ["keyword", "string", "comment", "function"]:
            self.editor.tag_configure(t, foreground=self.colors.get(t, "#ffffff")); self.editor.tag_remove(t, "1.0", tk.END)
        c = self.editor.get("1.0", tk.END)
        pats = [(r'\b(def|class|if|else|import|from|return|for|while|try|except|with|as)\b', "keyword"), (r'".*?"|".*?"', "string"), (r'#.*', "comment"), (r'\b[a-zA-Z_]\w*(?=\()', "function")]
        for p, t in pats:
            for m in re.finditer(p, c): self.editor.tag_add(t, f"1.0 + {m.start()} chars", f"1.0 + {m.end()} chars")

    def apply_theme(self, theme_name):
        themes = {
            "dark": { "bg": "#1e1e1e", "fg": "#d4d4d4", "sidebar": "#252526", "accent": "#007acc", "text_bg": "#2d2d2d" },
            "light": { "bg": "#ffffff", "fg": "#000000", "sidebar": "#f3f3f3", "accent": "#007acc", "text_bg": "#ffffff" },
            "monokai": { "bg": "#272822", "fg": "#f8f8f2", "sidebar": "#1e1f1c", "accent": "#ae81ff", "text_bg": "#272822" }
        }
        cfg = themes.get(theme_name, themes["dark"]); self.colors.update(cfg); self.root.configure(bg=cfg["bg"])
        for txt in [self.editor, self.log_display, self.hier_text if hasattr(self, 'hier_text') else None]:
            if txt: txt.configure(bg=cfg["text_bg"], fg=cfg["fg"], insertbackground=cfg["fg"])
        style = ttk.Style(); style.configure("Treeview", background=cfg["sidebar"], foreground=cfg["fg"], fieldbackground=cfg["sidebar"])
        CM.config['user_prefs']['theme'] = theme_name; CM.save_config()

    def on_tree_select(self, e):
        try:
            p = self.tree.item(self.tree.selection()[0], "values")[0]
            if os.path.isfile(p):
                self.current_file = p; self.load_file_to_editor(p)
                if p.endswith('.log'):
                    fn = os.path.basename(p)
                    if fn in self.log_selector['values']: self.log_selector.set(fn); self.on_log_selected(None)
        except: pass

    def load_file_to_editor(self, p):
        try:
            with open(p, 'r', errors='ignore') as f: c = f.read()
            self.editor.delete(1.0, tk.END); self.editor.insert(tk.END, c)
            self.on_editor_change(); self.notebook.select(self.editor_frame)
            if p.endswith('.py'): self.visualize_code(p)
        except Exception as e: messagebox.showerror("Error", str(e))

    def save_current_file(self):
        if self.current_file:
            with open(self.current_file, 'w') as f: f.write(self.editor.get(1.0, tk.END))
            messagebox.showinfo("Saved", "File updated."); self.refresh_file_tree()

    def on_log_selected(self, e):
        p = os.path.join(LOG_DIR, self.log_selector.get())
        if os.path.exists(p):
            with open(p, 'r') as f: self.log_display.delete(1.0, tk.END); self.log_display.insert(tk.END, f.read())

    def refresh_log_list(self):
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.endswith('.log')], reverse=True)
        self.log_selector['values'] = ls
        if ls: self.log_selector.set(ls[0])

    def tail_latest_log(self):
        if self.log_selector.get() and self.log_selector.current() == 0: self.on_log_selected(None)
        self.root.after(5000, self.tail_latest_log)

    def on_proc_hover(self, e):
        item = self.proc_tree.identify_row(e.y)
        if item:
            v = self.proc_tree.item(item, "values")
            self.tip_label.config(text=f"PID: {v[0]} -> {v[3]}\nChain: File <-> Code <-> Socket")
            self.tooltip.deiconify(); self.tooltip.geometry(f"+{e.x_root+10}+{e.y_root+10}")
        else: self.tooltip.withdraw()

    def on_proc_select(self, e):
        try:
            v = self.proc_tree.item(self.proc_tree.selection()[0], "values")
            self.focused_pid = v[0]; self.target_label.config(text=f"TARGET: [{v[0]}] {v[3]}")
            self.kill_btn.config(state="normal"); self.suspend_btn.config(state="normal")
        except: pass

    def kill_targeted_process(self):
        import psutil
        try: psutil.Process(int(self.focused_pid)).terminate(); self.update_proc_list()
        except Exception as e: messagebox.showerror("Error", str(e))

    def suspend_targeted_process(self):
        import psutil
        try:
            p = psutil.Process(int(self.focused_pid))
            if p.status() == psutil.STATUS_STOPPED: p.resume(); self.suspend_btn.config(text="SUSP")
            else: p.suspend(); self.suspend_btn.config(text="RESM")
        except: pass

    def toggle_proc_monitor(self):
        if self.proc_active.get(): self.update_proc_list()

    def update_proc_list(self):
        import psutil; [self.proc_tree.delete(i) for i in self.proc_tree.get_children()]
        procs = []
        for p in psutil.process_iter(['pid', 'cpu_percent', 'memory_percent', 'name', 'cmdline']):
            try: procs.append((p.info['pid'], p.info['cpu_percent'], p.info['memory_percent'], p.info['name'], " ".join(p.info['cmdline'] or [])))
            except: pass
        procs.sort(key=lambda x: x[3].lower())
        for p in procs: self.proc_tree.insert('', 'end', values=p)
        if self.proc_active.get(): self.root.after(self.refresh_ms.get(), self.update_proc_list)

    def show_search_dialog(self):
        sw = tk.Toplevel(self.root); sw.title("Find"); sw.geometry("300x100")
        ent = tk.Entry(sw); ent.pack(pady=10)
        def find():
            s = ent.get(); pos = self.editor.search(s, "1.0", tk.END)
            if pos: self.editor.tag_add("sel", pos, f"{pos}+{len(s)}c"); self.editor.see(pos)
        tk.Button(sw, text="Go", command=find).pack()

    def check_integrity(self):
        v, m = CM.verify_integrity(); messagebox.showinfo("Integrity", f"{('OK' if v else 'FAIL')}\n{m}")

    def run_security_scan(self, rec=False):
        self.cli_text.delete(1.0, tk.END); self.notebook.select(self.cli_frame)
        def task():
            cmd = [sys.executable, "process_organizer.py", "--scan", self.current_dir]
            if rec: cmd.append("-r")
            res = subprocess.run(cmd, capture_output=True, text=True)
            self.root.after(0, lambda: self.cli_text.insert(tk.END, res.stdout))
        threading.Thread(target=task).start()

    def open_directory(self):
        p = filedialog.askdirectory()
        if p: self.current_dir = p; self.refresh_file_tree()

    def refresh_file_tree(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        n = self.tree.insert('', 'end', text=os.path.basename(self.current_dir), values=(self.current_dir,), open=True)
        self.add_to_tree(self.current_dir, n)

    def add_to_tree(self, path, parent):
        try:
            for item in sorted(os.listdir(path)):
                if item.startswith('.'): continue
                abs_p = os.path.join(path, item); node = self.tree.insert(parent, 'end', text=item, values=(abs_p,))
                if os.path.isdir(abs_p): self.add_to_tree(abs_p, node)
        except: pass

    def view_crash_logs(self):
        ls = sorted([f for f in os.listdir(LOG_DIR) if f.startswith('gui_')], reverse=True)
        for ln in ls:
            with open(os.path.join(LOG_DIR, ln), 'r') as f:
                if "ERROR" in f.read(): self.log_selector.set(ln); self.on_log_selected(None); return

    def load_manifest(self): pass

if __name__ == "__main__":
    try: root = tk.Tk(); app = SecureViewApp(root); root.mainloop()
    except Exception as e:
        with open("FATAL_BOOT.txt", "a") as f: f.write(f"CRASH: {e}\n{traceback.format_exc()}\n")
        sys.exit(1)