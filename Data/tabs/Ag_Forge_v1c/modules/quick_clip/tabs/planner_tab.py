import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import json
import datetime
from pathlib import Path
import subprocess
import difflib
import threading
from queue import Queue
import hashlib

# Import Ag Knowledge Linker
try:
    from ag_utils import AgKnowledgeLinker
except ImportError:
    try:
        from ..ag_utils import AgKnowledgeLinker
    except ImportError:
        AgKnowledgeLinker = None

class PlannerSuite(tk.Frame):
    def __init__(self, parent, app_ref, base_path=None):
        super().__init__(parent)
        self.parent = parent
        self.app = app_ref # Reference to the main ClipboardAssistant app
        self.base_path = base_path or os.path.expanduser("~/PlannerSuite")
        self.marked_files = []
        self.current_context = {}
        self.diff_history = []
        
        # Initialize Ag Knowledge Linker
        self.ag_linker = AgKnowledgeLinker() if AgKnowledgeLinker else None
        
        # Create directory structure if it doesn't exist
        self.setup_directories()
        
        # Setup UI
        self.setup_ui()
        self.load_directory_structure()
        
    def setup_directories(self):
        """Create the standard directory structure"""
        directories = [
            "Epics",
            "Plans", 
            "Phases",
            "Tasks",
            "Milestones",
            "Diffs",
            "Refs"
        ]
        
        for directory in directories:
            path = os.path.join(self.base_path, directory)
            os.makedirs(path, exist_ok=True)
            
        # Create config file if it doesn't exist
        config_path = os.path.join(self.base_path, "config.json")
        if not os.path.exists(config_path):
            with open(config_path, 'w') as f:
                json.dump({
                    "file_browser": "thunar",
                    "default_editor": "xdg-open",
                    "recent_files": [],
                    "settings": {}
                }, f, indent=2)
    
    def setup_ui(self):
        """Setup the main UI layout"""
        # Main container
        main_container = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Document display
        self.left_frame = tk.Frame(main_container, bg='white', relief=tk.SUNKEN, borderwidth=2)
        main_container.add(self.left_frame, width=600)
        
        # Document display area
        self.doc_display = scrolledtext.ScrolledText(
            self.left_frame, 
            wrap=tk.WORD,
            font=('Consolas', 10),
            undo=True
        )
        self.doc_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Document controls
        doc_controls = tk.Frame(self.left_frame)
        doc_controls.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(doc_controls, text="Save", command=self.save_document).pack(side=tk.LEFT, padx=2)
        tk.Button(doc_controls, text="New", command=self.new_document).pack(side=tk.LEFT, padx=2)
        tk.Button(doc_controls, text="Clear", command=self.clear_document).pack(side=tk.LEFT, padx=2)
        
        # Right panel - Directory structure
        self.right_panel = tk.Frame(main_container)
        main_container.add(self.right_panel, width=300)
        
        # Create notebook for right panel tabs
        self.right_notebook = ttk.Notebook(self.right_panel)
        self.right_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Directory structure tab
        self.dir_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.dir_frame, text="Structure")
        
        # Create treeview for directory structure
        self.tree_frame = tk.Frame(self.dir_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbars
        tree_scroll_y = tk.Scrollbar(self.tree_frame)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        
        tree_scroll_x = tk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Create treeview
        self.tree = ttk.Treeview(
            self.tree_frame,
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
            selectmode='browse'
        )
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)
        
        # Configure tree columns
        self.tree["columns"] = ("type", "size", "full_path")
        self.tree.column("#0", width=200, minwidth=100)
        self.tree.column("type", width=60, minwidth=50)
        self.tree.column("size", width=80, minwidth=60)
        self.tree.column("full_path", width=0, stretch=tk.NO) # Hidden column
        
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("type", text="Type", anchor=tk.W)
        self.tree.heading("size", text="Size", anchor=tk.W)
        
        # Bind tree events
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Directory controls frame
        dir_controls = tk.Frame(self.dir_frame)
        dir_controls.pack(fill=tk.X, padx=5, pady=5)
        
        # Buttons for each directory
        self.dir_buttons = {}
        directories = ["Epics", "Plans", "Phases", "Tasks", "Milestones", "Diffs", "Refs"]
        
        for i, dir_name in enumerate(directories):
            btn_frame = tk.Frame(dir_controls)
            btn_frame.grid(row=i//2, column=i%2, sticky="ew", padx=2, pady=2)
            
            # Open in file browser button
            open_btn = tk.Button(
                btn_frame, 
                text=f"📂 {dir_name}",
                command=lambda d=dir_name: self.open_in_file_browser(d),
                width=15
            )
            open_btn.pack(side=tk.LEFT, padx=2)
            
            # Toggle button
            toggle_btn = tk.Button(
                btn_frame,
                text="▶",
                command=lambda d=dir_name: self.toggle_directory(d),
                width=3
            )
            toggle_btn.pack(side=tk.RIGHT, padx=2)
            self.dir_buttons[dir_name] = toggle_btn
        
        # Marked Files tab
        self.marked_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.marked_frame, text="Marked Files")
        
        # Ag Knowledge tab
        self.ag_frame = tk.Frame(self.right_notebook)
        self.right_notebook.add(self.ag_frame, text="Ag Knowledge")
        self.setup_ag_knowledge_ui()
        
        # Marked files listbox
        self.marked_listbox = tk.Listbox(self.marked_frame, selectmode=tk.EXTENDED)
        self.marked_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        marked_controls = tk.Frame(self.marked_frame)
        marked_controls.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(marked_controls, text="Add Files", command=self.mark_files).pack(side=tk.LEFT, padx=2)
        tk.Button(marked_controls, text="Remove", command=self.remove_marked).pack(side=tk.LEFT, padx=2)
        tk.Button(marked_controls, text="Run Diff", command=self.run_diff_analysis).pack(side=tk.LEFT, padx=2)
        tk.Button(marked_controls, text="Send to Editor", command=self.send_to_editor).pack(side=tk.LEFT, padx=5)
        
        # Bottom panel - Controls
        self.bottom_panel = tk.Frame(self, relief=tk.RAISED, borderwidth=1)
        self.bottom_panel.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Context controls
        context_frame = tk.LabelFrame(self.bottom_panel, text="Context & Tasking", padx=5, pady=5)
        context_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Context entry
        tk.Label(context_frame, text="Context:").pack(side=tk.LEFT, padx=2)
        self.context_entry = tk.Entry(context_frame, width=40)
        self.context_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        tk.Button(context_frame, text="Add to Task", command=self.add_to_task).pack(side=tk.LEFT, padx=2)
        tk.Button(context_frame, text="Compile Summary", command=self.compile_summary).pack(side=tk.LEFT, padx=2)
        
        # Diff controls
        diff_frame = tk.LabelFrame(self.bottom_panel, text="Diff Controls", padx=5, pady=5)
        diff_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(diff_frame, text="Add lines to diff:").pack(side=tk.LEFT, padx=2)
        self.diff_entry = tk.Entry(diff_frame, width=50)
        self.diff_entry.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        tk.Button(diff_frame, text="Add Diff", command=self.add_diff_lines).pack(side=tk.LEFT, padx=2)
        tk.Button(diff_frame, text="Scroll Marked", command=self.scroll_marked_files).pack(side=tk.LEFT, padx=2)
        
        # Task watcher controls
        watcher_frame = tk.Frame(self.bottom_panel)
        watcher_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.watcher_var = tk.BooleanVar()
        tk.Checkbutton(watcher_frame, text="Task Watcher", variable=self.watcher_var,
                      command=self.toggle_watcher).pack(side=tk.LEFT, padx=5)
        
        tk.Button(watcher_frame, text="Check Completion", command=self.check_completion).pack(side=tk.LEFT, padx=5)
        tk.Button(watcher_frame, text="Generate Report", command=self.generate_report).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_bar = tk.Label(self.bottom_panel, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
    
    def send_to_editor(self):
        """Gather content from marked files and send to the Edit & Process tab."""
        if not self.marked_files:
            messagebox.showwarning("No Files", "No files are marked. Please mark one or more files to send to the editor.")
            return

        full_content = []
        for file_path in self.marked_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                full_content.append(f"--- START OF FILE: {os.path.basename(file_path)} ---\n\n{content}\n\n--- END OF FILE: {os.path.basename(file_path)} ---")
            except Exception as e:
                full_content.append(f"--- ERROR READING FILE: {os.path.basename(file_path)} ---\n\n{str(e)}\n\n--- END OF FILE: {os.path.basename(file_path)} ---")
        
        combined_content = "\n\n".join(full_content)
        
        # Use the app reference to access the other tab
        self.app.edit_text.delete('1.0', tk.END)
        self.app.edit_text.insert('1.0', combined_content)
        self.app.notebook.select(self.app.edit_frame) # Switch to the edit tab

    def load_directory_structure(self):
        """Load the directory structure into the treeview"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add root
        root = self.tree.insert("", "end", text=os.path.basename(self.base_path), 
                               values=("Folder", "", self.base_path), open=True)
        
        # Add each directory
        for dir_name in ["Epics", "Plans", "Phases", "Tasks", "Milestones", "Diffs", "Refs"]:
            dir_path = os.path.join(self.base_path, dir_name)
            self.tree.insert(root, "end", text=dir_name, values=("Folder", "", dir_path))
    
    def toggle_directory(self, dir_name):
        """Expand or collapse a directory in the tree"""
        dir_path = os.path.join(self.base_path, dir_name)
        
        # Find the directory item in the tree
        for item in self.tree.get_children(self.tree.get_children()[0]): # Search under the root node
            if self.tree.item(item, "text") == dir_name:
                if self.tree.item(item, "open"):
                    # Clear children before closing
                    for child in self.tree.get_children(item):
                        self.tree.delete(child)
                    self.tree.item(item, open=False)
                    self.dir_buttons[dir_name].config(text="▶")
                else:
                    self.expand_directory(item, dir_path)
                    self.dir_buttons[dir_name].config(text="▼")
                break
    
    def expand_directory(self, parent_id, dir_path):
        """Expand a directory to show its contents"""
        # This method is now primarily for populating, toggle handles clearing.
        try:
            # Add files
            for item_name in sorted(os.listdir(dir_path)):
                item_path = os.path.join(dir_path, item_name)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    size_str = f"{size/1024:.1f}KB" if size > 1024 else f"{size}B"
                    
                    # Determine file type
                    if item_name.endswith('.json'):
                        file_type = "JSON"
                    elif item_name.endswith('.txt') or item_name.endswith('.md'):
                        file_type = "Text"
                    elif item_name.endswith('.py'):
                        file_type = "Python"
                    else:
                        file_type = "File"
                    
                    self.tree.insert(parent_id, "end", text=item_name, 
                                     values=(file_type, size_str, item_path))
            
            self.tree.item(parent_id, open=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load directory: {e}")
    
    def on_tree_double_click(self, event):
        """Handle double-click on tree items"""
        if not self.tree.selection():
            return
        item_id = self.tree.selection()[0]
        item_values = self.tree.item(item_id, "values")
        
        # The full_path is the 3rd value (index 2)
        if item_values and len(item_values) > 2 and item_values[2]:
            path = item_values[2]
            if os.path.isfile(path):
                self.open_file(path)
    
    def on_tree_select(self, event):
        """Handle selection in tree"""
        if not self.tree.selection():
            return
        item_id = self.tree.selection()[0]
        item_values = self.tree.item(item_id, "values")

        if item_values and len(item_values) > 2 and item_values[2]:
            path = item_values[2]
            self.status_bar.config(text=f"Selected: {os.path.basename(path)}")
    
    def open_file(self, file_path):
        """Open a file in the document display"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            self.doc_display.delete(1.0, tk.END)
            self.doc_display.insert(1.0, content)
            
            # Update Ag Knowledge links
            self.update_ag_knowledge_links(content)
            
            # Store current file info
            self.current_file = file_path
            self.status_bar.config(text=f"Opened: {os.path.basename(file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {e}")
    
    def save_document(self):
        """Save the current document"""
        if hasattr(self, 'current_file'):
            content = self.doc_display.get(1.0, tk.END)
            try:
                with open(self.current_file, 'w') as f:
                    f.write(content)
                self.status_bar.config(text=f"Saved: {os.path.basename(self.current_file)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")
        else:
            # Save as new file
            self.save_as_document()
    
    def save_as_document(self):
        """Save document as new file"""
        file_types = [
            ("Text files", "*.txt"),
            ("Markdown files", "*.md"),
            ("JSON files", "*.json"),
            ("Python files", "*.py"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.asksaveasfilename(
            initialdir=self.base_path,
            defaultextension=".txt",
            filetypes=file_types
        )
        
        if file_path:
            content = self.doc_display.get(1.0, tk.END)
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                
                self.current_file = file_path
                self.status_bar.config(text=f"Saved as: {os.path.basename(file_path)}")
                
                # Refresh tree if in our structure
                if self.base_path in file_path:
                    self.load_directory_structure()
            except Exception as e:
                messagebox.showerror("Error", f"Could not save file: {e}")
    
    def new_document(self):
        """Create a new document"""
        self.doc_display.delete(1.0, tk.END)
        self.current_file = None
        self.status_bar.config(text="New document")
    
    def clear_document(self):
        """Clear the document display"""
        if messagebox.askyesno("Clear", "Clear current document?"):
            self.doc_display.delete(1.0, tk.END)
    
    def open_in_file_browser(self, dir_name):
        """Open directory in native file browser"""
        dir_path = os.path.join(self.base_path, dir_name)
        
        try:
            # Try thunar first, then xdg-open as fallback
            subprocess.Popen(['thunar', dir_path])
        except:
            try:
                subprocess.Popen(['xdg-open', dir_path])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file browser: {e}")
    
    def mark_files(self):
        """Mark files for diff analysis"""
        file_types = [
            ("Python files", "*.py"),
            ("Text files", "*.txt"),
            ("Markdown files", "*.md"),
            ("All files", "*.*")
        ]
        
        files = filedialog.askopenfilenames(
            title="Select files to mark",
            filetypes=file_types
        )
        
        for file_path in files:
            if file_path not in self.marked_files:
                self.marked_files.append(file_path)
                self.marked_listbox.insert(tk.END, os.path.basename(file_path))
                self.marked_listbox.itemconfig(tk.END, {'fg': 'blue'})
        
        self.status_bar.config(text=f"Marked {len(files)} files")
    
    def remove_marked(self):
        """Remove selected files from marked list"""
        selected = self.marked_listbox.curselection()
        for index in reversed(selected):
            del self.marked_files[index]
            self.marked_listbox.delete(index)
    
    def run_diff_analysis(self):
        """Run diff analysis on marked files"""
        if len(self.marked_files) < 2:
            messagebox.showwarning("Diff", "Need at least 2 files for diff")
            return
        
        # Create diff window
        diff_window = tk.Toplevel(self)
        diff_window.title("Diff Analysis")
        diff_window.geometry("800x600")
        
        # Diff text area
        diff_text = scrolledtext.ScrolledText(diff_window, wrap=tk.NONE)
        diff_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Compare first two files
        try:
            with open(self.marked_files[0], 'r') as f1, open(self.marked_files[1], 'r') as f2:
                lines1 = f1.readlines()
                lines2 = f2.readlines()
            
            diff = difflib.unified_diff(
                lines1, lines2,
                fromfile=os.path.basename(self.marked_files[0]),
                tofile=os.path.basename(self.marked_files[1]),
                lineterm=''
            )
            
            diff_text.insert(1.0, '\n'.join(diff))
            
            # Store diff
            diff_content = '\n'.join(diff)
            self.save_diff_to_file(diff_content, self.marked_files[0], self.marked_files[1])
            
        except Exception as e:
            messagebox.showerror("Diff Error", f"Could not compute diff: {e}")
    
    def save_diff_to_file(self, diff_content, file1, file2):
        """Save diff to file in Diffs directory"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        diff_file = os.path.join(self.base_path, "Diffs", f"diff_{timestamp}.txt")
        
        with open(diff_file, 'w') as f:
            f.write(f"Diff between:\n{file1}\n{file2}\n\n")
            f.write(diff_content)
        
        self.diff_history.append({
            'timestamp': timestamp,
            'file1': file1,
            'file2': file2,
            'diff_file': diff_file
        })
        
        # Refresh tree
        self.load_directory_structure()
    
    def add_to_task(self):
        """Add context to current task"""
        context = self.context_entry.get()
        if context:
            task_file = os.path.join(self.base_path, "Tasks", "context_tasks.txt")
            
            with open(task_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}] {context}\n")
            
            # Update Ag Knowledge links
            self.update_ag_knowledge_links(context)
            
            self.status_bar.config(text="Context added to task")
            self.context_entry.delete(0, tk.END)
    
    def compile_summary(self):
        """Compile a summary from marked files and context"""
        if not self.marked_files:
            messagebox.showwarning("Summary", "No marked files to compile")
            return
        
        summary_window = tk.Toplevel(self)
        summary_window.title("Compiled Summary")
        summary_window.geometry("600x400")
        
        summary_text = scrolledtext.ScrolledText(summary_window, wrap=tk.WORD)
        summary_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        summary = f"Summary compiled: {datetime.datetime.now()}\n"
        summary += "=" * 50 + "\n\n"
        summary += f"Marked files ({len(self.marked_files)}):\n"
        
        for i, file_path in enumerate(self.marked_files, 1):
            summary += f"{i}. {file_path}\n"
            
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()[:10]  # First 10 lines
                    summary += "   Preview:\n"
                    for line in lines[:5]:
                        summary += f"   {line}"
                    if len(lines) > 5:
                        summary += "   ...\n"
            except:
                summary += "   [Could not read file]\n"
            
            summary += "\n"
        
        summary_text.insert(1.0, summary)
        
        # Save summary
        summary_file = os.path.join(self.base_path, "Refs", f"summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(summary_file, 'w') as f:
            f.write(summary)
        
        self.load_directory_structure()
    
    def add_diff_lines(self):
        """Add lines to diff tracking"""
        lines = self.diff_entry.get()
        if lines:
            diff_file = os.path.join(self.base_path, "Diffs", "manual_diffs.txt")
            
            with open(diff_file, 'a') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"\n[{timestamp}]\n")
                f.write(lines + "\n")
                f.write("-" * 40 + "\n")
            
            self.diff_entry.delete(0, tk.END)
            self.status_bar.config(text="Diff lines added")
    
    def scroll_marked_files(self):
        """Scroll through marked files in document display"""
        if not self.marked_files:
            messagebox.showinfo("Marked Files", "No marked files to scroll through")
            return
        
        # Create a simple viewer
        viewer_window = tk.Toplevel(self)
        viewer_window.title("Marked Files Viewer")
        viewer_window.geometry("800x500")
        
        notebook = ttk.Notebook(viewer_window)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        for file_path in self.marked_files:
            frame = tk.Frame(notebook)
            notebook.add(frame, text=os.path.basename(file_path))
            
            text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD)
            text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                text_widget.insert(1.0, content)
            except Exception as e:
                text_widget.insert(1.0, f"Error reading file: {e}")
    
    def toggle_watcher(self):
        """Toggle task completion watcher"""
        if self.watcher_var.get():
            self.status_bar.config(text="Task watcher: ON")
            # Start watcher thread (simplified)
            self.start_watcher()
        else:
            self.status_bar.config(text="Task watcher: OFF")
    
    def start_watcher(self):
        """Start file watcher thread"""
        # This is a simplified version - in production, you'd use watchdog or similar
        def watch_files():
            last_hashes = {}
            while self.watcher_var.get():
                for file_path in self.marked_files:
                    try:
                        with open(file_path, 'rb') as f:
                            file_hash = hashlib.md5(f.read()).hexdigest()
                        
                        if file_path in last_hashes:
                            if last_hashes[file_path] != file_hash:
                                print(f"File changed: {file_path}")
                                # Trigger some action
                                last_hashes[file_path] = file_hash
                        else:
                            last_hashes[file_path] = file_hash
                    except:
                        pass
                
                import time
                time.sleep(5)  # Check every 5 seconds
        
        thread = threading.Thread(target=watch_files, daemon=True)
        thread.start()
    
    def check_completion(self):
        """Check task completion status"""
        completion_window = tk.Toplevel(self)
        completion_window.title("Task Completion Check")
        completion_window.geometry("400x300")
        
        # Simple completion check
        text_widget = scrolledtext.ScrolledText(completion_window, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        report = "Task Completion Check\n"
        report += "=" * 30 + "\n\n"
        
        # Check for TODO/FIXME comments in marked Python files
        todo_count = 0
        for file_path in self.marked_files:
            if file_path.endswith('.py'):
                try:
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    
                    for i, line in enumerate(lines, 1):
                        if 'TODO' in line or 'FIXME' in line:
                            todo_count += 1
                            report += f"{os.path.basename(file_path)}:{i}: {line.strip()}\n"
                except:
                    pass
        
        report += f"\nTotal TODO/FIXME items: {todo_count}\n"
        
        text_widget.insert(1.0, report)
    
    def setup_ag_knowledge_ui(self):
        """Setup UI for Ag Knowledge tab"""
        self.ag_display = scrolledtext.ScrolledText(
            self.ag_frame,
            wrap=tk.WORD,
            font=('Arial', 10),
            bg='#f8f9fa'
        )
        self.ag_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.ag_display.config(state=tk.DISABLED)
        
        refresh_btn = tk.Button(self.ag_frame, text="🔄 Refresh Links", command=self.refresh_ag_links)
        refresh_btn.pack(fill=tk.X, padx=5, pady=2)

    def refresh_ag_links(self):
        """Manually refresh Ag Knowledge links based on current document content"""
        content = self.doc_display.get(1.0, tk.END)
        self.update_ag_knowledge_links(content)

    def update_ag_knowledge_links(self, text):
        """Scan text and update the Ag Knowledge display with hierarchical associations"""
        if not self.ag_linker:
            return

        found = self.ag_linker.scan_text(text)
        
        self.ag_display.config(state=tk.NORMAL)
        self.ag_display.delete(1.0, tk.END)
        
        if not found["entities"] and not found["diseases"] and not found["terms"]:
            self.ag_display.insert(tk.END, "No specific Ag Knowledge links found in current selection.\n\n")
            self.ag_display.insert(tk.END, "Tip: Use entity names like 'Bella' or 'Daisy' in your tasks.")
        else:
            if found["entities"]:
                self.ag_display.insert(tk.END, "--- Linked Entities ---\n", "heading")
                for entity in found["entities"]:
                    hierarchy = self.ag_linker.get_hierarchy(entity)
                    assoc = self.ag_linker.get_full_associations(entity)
                    
                    self.ag_display.insert(tk.END, f"• {entity['name']}\n", "link")
                    self.ag_display.insert(tk.END, f"  Hierarchy: {hierarchy}\n")
                    self.ag_display.insert(tk.END, f"  Health: {entity.get('health_status', 'Unknown')}\n")
                    
                    if assoc["parent"]:
                        self.ag_display.insert(tk.END, f"  Parent: {assoc['parent'].get('name', 'Unknown')}\n")
                    
                    if assoc["offspring"]:
                        off_names = ", ".join([o.get('name', 'Unknown') for o in assoc["offspring"]])
                        self.ag_display.insert(tk.END, f"  Offspring: {off_names}\n")
                    
                    if assoc["diseases"]:
                        dis_names = ", ".join([d.get('name', 'Unknown') for d in assoc["diseases"]])
                        self.ag_display.insert(tk.END, f"  History: {dis_names}\n", "error_link")

                    self.ag_display.insert(tk.END, f"  Desc: {entity.get('description', '')[:100]}...\n\n")
            
            if found["diseases"]:
                self.ag_display.insert(tk.END, "\n--- Linked Diseases ---\n", "heading")
                for disease in found["diseases"]:
                    self.ag_display.insert(tk.END, f"• {disease['name']}\n", "error_link")
                    self.ag_display.insert(tk.END, f"  Scientific: {disease.get('scientific_name', '')}\n")
                    self.ag_display.insert(tk.END, f"  Severity: {disease.get('severity', '')}\n\n")

            if found["terms"]:
                self.ag_display.insert(tk.END, "\n--- Related Terms ---\n", "heading")
                for term in found["terms"]:
                    self.ag_display.insert(tk.END, f"• {term}\n")

        # Configure tags
        self.ag_display.tag_config("heading", font=('Arial', 10, 'bold'))
        self.ag_display.tag_config("link", foreground="blue", underline=True)
        self.ag_display.tag_config("error_link", foreground="red", underline=True)
        
        self.ag_display.config(state=tk.DISABLED)

    def generate_report(self):
        """Generate a comprehensive report"""
        report_file = os.path.join(self.base_path, "Refs", f"report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        report = f"Planner Suite Report\n"
        report += "=" * 50 + "\n"
        report += f"Generated: {datetime.datetime.now()}\n\n"
        
        report += f"Base Path: {self.base_path}\n"
        report += f"Marked Files: {len(self.marked_files)}\n"
        report += f"Diff History Entries: {len(self.diff_history)}\n\n"
        
        # Directory contents summary
        report += "Directory Structure:\n"
        for dir_name in ["Epics", "Plans", "Phases", "Tasks", "Milestones", "Diffs", "Refs"]:
            dir_path = os.path.join(self.base_path, dir_name)
            try:
                count = len([f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))])
                report += f"  {dir_name}: {count} files\n"
            except:
                report += f"  {dir_name}: Error accessing\n"
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        self.status_bar.config(text=f"Report generated: {os.path.basename(report_file)}")
        self.load_directory_structure()
