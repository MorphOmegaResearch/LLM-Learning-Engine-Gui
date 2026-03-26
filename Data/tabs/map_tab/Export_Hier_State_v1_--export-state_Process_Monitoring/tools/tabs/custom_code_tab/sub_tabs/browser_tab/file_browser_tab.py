"""
File Browser Sub-Tab (Phase 1.6E)

File system navigation and management interface.
Provides:
- Directory tree navigation
- File listing with details
- Quick actions (open, copy path, etc.)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')


class FileBrowserTab(BaseTab):
    """File system browser and navigation"""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.current_path = Path.home()

    def create_ui(self):
        """Create the file browser UI"""
        log_message("FILE_BROWSER_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Header
        self.parent.rowconfigure(1, weight=0)  # Path bar
        self.parent.rowconfigure(2, weight=1)  # File list
        self.parent.rowconfigure(3, weight=0)  # Info bar

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="📁 File Browser",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🏠 Home",
            command=self._go_home,
            width=10
        ).pack(side=tk.RIGHT, padx=2)

        ttk.Button(
            header_frame,
            text="⬆️ Up",
            command=self._go_up,
            width=10
        ).pack(side=tk.RIGHT, padx=2)

        ttk.Button(
            header_frame,
            text="🔄 Refresh",
            command=self._refresh,
            width=10
        ).pack(side=tk.RIGHT, padx=2)

        # Path bar
        path_frame = ttk.Frame(self.parent, style='Category.TFrame')
        path_frame.grid(row=1, column=0, sticky=tk.EW, padx=10, pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Path:", style='Config.TLabel').grid(row=0, column=0, padx=(0, 5))

        self.path_entry = ttk.Entry(path_frame, font=("Consolas", 9))
        self.path_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5))
        self.path_entry.bind('<Return>', lambda e: self._navigate_to_path())

        ttk.Button(
            path_frame,
            text="Go",
            command=self._navigate_to_path,
            width=6
        ).grid(row=0, column=2)

        # File list with scrollbar
        list_container = ttk.Frame(self.parent, style='Category.TFrame')
        list_container.grid(row=2, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        # Treeview for file list
        self.file_tree = ttk.Treeview(
            list_container,
            columns=('type', 'size', 'modified'),
            show='tree headings',
            selectmode='browse'
        )

        # Configure columns
        self.file_tree.heading('#0', text='Name')
        self.file_tree.heading('type', text='Type')
        self.file_tree.heading('size', text='Size')
        self.file_tree.heading('modified', text='Modified')

        self.file_tree.column('#0', width=300)
        self.file_tree.column('type', width=80)
        self.file_tree.column('size', width=100)
        self.file_tree.column('modified', width=150)

        # Scrollbars
        vsb = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.file_tree.yview)
        hsb = ttk.Scrollbar(list_container, orient=tk.HORIZONTAL, command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.file_tree.grid(row=0, column=0, sticky=tk.NSEW)
        vsb.grid(row=0, column=1, sticky=tk.NS)
        hsb.grid(row=1, column=0, sticky=tk.EW)

        # Bind double-click to navigate
        self.file_tree.bind('<Double-Button-1>', self._on_double_click)

        # Context menu
        self.context_menu = tk.Menu(self.parent, tearoff=0)
        self.context_menu.add_command(label="Open", command=self._open_selected)
        self.context_menu.add_command(label="Copy Path", command=self._copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Properties", command=self._show_properties)

        self.file_tree.bind('<Button-3>', self._show_context_menu)

        # Info bar
        info_frame = ttk.Frame(self.parent, style='Category.TFrame')
        info_frame.grid(row=3, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        self.info_label = ttk.Label(
            info_frame,
            text="Ready",
            style='Config.TLabel',
            font=("Arial", 8)
        )
        self.info_label.pack(side=tk.LEFT)

        # Initial load
        self._refresh()

        log_message("FILE_BROWSER_TAB: UI created successfully")

    def _refresh(self):
        """Refresh file list"""
        try:
            # Clear existing items
            for item in self.file_tree.get_children():
                self.file_tree.delete(item)

            # Update path entry
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, str(self.current_path))

            # List directories first, then files
            items = []
            try:
                items = list(self.current_path.iterdir())
            except PermissionError:
                messagebox.showerror("Permission Denied", f"Cannot access: {self.current_path}")
                self._go_up()
                return

            # Sort: directories first, then by name
            dirs = sorted([i for i in items if i.is_dir()], key=lambda x: x.name.lower())
            files = sorted([i for i in items if i.is_file()], key=lambda x: x.name.lower())

            # Add directories
            for item in dirs:
                try:
                    size = "-"
                    modified = self._format_time(item.stat().st_mtime)
                    self.file_tree.insert(
                        '',
                        tk.END,
                        text=f"📁 {item.name}",
                        values=('Directory', size, modified),
                        tags=('directory',)
                    )
                except Exception:
                    pass

            # Add files
            for item in files:
                try:
                    size = self._format_size(item.stat().st_size)
                    modified = self._format_time(item.stat().st_mtime)
                    icon = self._get_file_icon(item)
                    self.file_tree.insert(
                        '',
                        tk.END,
                        text=f"{icon} {item.name}",
                        values=('File', size, modified),
                        tags=('file',)
                    )
                except Exception:
                    pass

            # Update info
            self.info_label.config(text=f"{len(dirs)} directories, {len(files)} files")
            log_message(f"FILE_BROWSER_TAB: Loaded {self.current_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load directory: {e}")
            log_message(f"FILE_BROWSER_TAB ERROR: Failed to refresh: {e}")

    def _format_size(self, size):
        """Format file size"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _format_time(self, timestamp):
        """Format timestamp"""
        from datetime import datetime
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%Y-%m-%d %H:%M')

    def _get_file_icon(self, path):
        """Get icon for file type"""
        ext = path.suffix.lower()
        icons = {
            '.py': '🐍',
            '.txt': '📄',
            '.json': '📋',
            '.md': '📝',
            '.png': '🖼️',
            '.jpg': '🖼️',
            '.jpeg': '🖼️',
            '.gif': '🖼️',
            '.zip': '📦',
            '.tar': '📦',
            '.gz': '📦',
        }
        return icons.get(ext, '📄')

    def _go_up(self):
        """Navigate to parent directory"""
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self._refresh()

    def _go_home(self):
        """Navigate to home directory"""
        self.current_path = Path.home()
        self._refresh()

    def _navigate_to_path(self):
        """Navigate to path in entry"""
        try:
            new_path = Path(self.path_entry.get()).resolve()
            if new_path.exists() and new_path.is_dir():
                self.current_path = new_path
                self._refresh()
            else:
                messagebox.showerror("Invalid Path", "Path does not exist or is not a directory")
        except Exception as e:
            messagebox.showerror("Error", f"Invalid path: {e}")

    def _on_double_click(self, event):
        """Handle double-click on item"""
        selection = self.file_tree.selection()
        if not selection:
            return

        item = self.file_tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]  # Remove icon
        path = self.current_path / name

        if path.is_dir():
            self.current_path = path
            self._refresh()
        else:
            self._open_selected()

    def _open_selected(self):
        """Open selected file"""
        selection = self.file_tree.selection()
        if not selection:
            return

        item = self.file_tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        path = self.current_path / name

        try:
            if path.is_file():
                os.startfile(str(path)) if os.name == 'nt' else os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def _copy_path(self):
        """Copy selected path to clipboard"""
        selection = self.file_tree.selection()
        if not selection:
            return

        item = self.file_tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        path = self.current_path / name

        self.root.clipboard_clear()
        self.root.clipboard_append(str(path))
        self.info_label.config(text=f"Copied: {path}")

    def _show_properties(self):
        """Show file properties"""
        selection = self.file_tree.selection()
        if not selection:
            return

        item = self.file_tree.item(selection[0])
        name = item['text'].split(' ', 1)[1]
        path = self.current_path / name

        try:
            stat = path.stat()
            info = f"Name: {path.name}\n"
            info += f"Path: {path}\n"
            info += f"Type: {'Directory' if path.is_dir() else 'File'}\n"
            info += f"Size: {self._format_size(stat.st_size)}\n"
            info += f"Modified: {self._format_time(stat.st_mtime)}\n"

            messagebox.showinfo("Properties", info)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get properties: {e}")

    def _show_context_menu(self, event):
        """Show context menu"""
        # Select item under cursor
        item = self.file_tree.identify_row(event.y)
        if item:
            self.file_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def on_show(self):
        """Called when tab becomes visible"""
        self._refresh()
