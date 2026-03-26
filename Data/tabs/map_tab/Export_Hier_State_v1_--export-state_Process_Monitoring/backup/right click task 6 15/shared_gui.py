#!/usr/bin/env python3
"""
shared_gui.py - Shared Popup GUI for Tools and Configuration

Provides a shared popup interface with tabs for tools and configuration.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import traceback
import logging
from datetime import datetime

# --- Setup Logging for Popups ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_file = os.path.join(LOG_DIR, datetime.now().strftime("popup_%Y%m%d_%H%M%S.log"))
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception in Popup", exc_info=(exc_type, exc_value, exc_traceback))
    traceback.print_exception(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

current_dir = os.path.dirname(os.path.abspath(__file__))

class SharedPopupGUI:
    """Shared popup GUI for tools and configuration"""
    
    def __init__(self, parent, mode="tools"):
        self.parent = parent
        self.mode = mode  # "tools" or "config"
        
        # Create popup window
        self.window = tk.Toplevel(parent)
        self.window.title(f"Secure View - {mode.title()}")
        self.window.geometry("800x600")
        
        # Setup UI based on mode
        if mode == "tools":
            self.setup_tools_ui()
        else:
            self.setup_config_ui()
        
        # Make window modal
        self.window.transient(parent)
        self.window.grab_set()
        
        # Center window
        self.center_window()
    
    def center_window(self):
        """Center the popup window"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def setup_tools_ui(self):
        """Setup tools interface with nested sub-tabs"""
        # Create notebook
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 1. Default Tools (Built-in)
        default_frame = ttk.Frame(self.notebook)
        self.setup_default_tools(default_frame)
        self.notebook.add(default_frame, text="Default Tools")
        
        # 2. Custom Scripts (From /tools directory)
        custom_frame = ttk.Frame(self.notebook)
        self.setup_custom_tools(custom_frame)
        self.notebook.add(custom_frame, text="Local Scripts (/tools)")
        
        # 3. Security Manifest (Project View)
        manifest_frame = ttk.Frame(self.notebook)
        self.setup_tool_manager(manifest_frame)
        self.notebook.add(manifest_frame, text="Security Manifest")
    
    def setup_default_tools(self, parent):
        """Setup default tools panel"""
        # Tool categories
        categories = [
            ("Security Tools", [
                ("Integrity Check", "Check file integrity"),
                ("Security Scan", "Scan for security issues"),
                ("Process Monitor", "Monitor running processes"),
                ("Network Analyzer", "Analyze network connections")
            ]),
            ("Code Tools", [
                ("Code Visualizer", "Visualize code structure"),
                ("Dependency Check", "Check dependencies"),
                ("Code Metrics", "Show code statistics"),
                ("Linter", "Check code quality")
            ]),
            ("File Tools", [
                ("File Search", "Search in files"),
                ("Duplicate Finder", "Find duplicate files"),
                ("File Organizer", "Organize files"),
                ("Backup", "Create backup")
            ])
        ]
        
        # Create scrollable frame
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add tool categories
        row = 0
        for category_name, tools in categories:
            # Category label
            cat_label = ttk.Label(scrollable_frame, 
                                 text=category_name, 
                                 font=("Arial", 10, "bold"))
            cat_label.grid(row=row, column=0, sticky="w", padx=10, pady=(10, 5))
            row += 1
            
            # Tools in category
            for tool_name, tool_desc in tools:
                # Create tool frame
                tool_frame = ttk.Frame(scrollable_frame)
                tool_frame.grid(row=row, column=0, sticky="ew", padx=20, pady=2)
                
                # Tool button
                btn = ttk.Button(tool_frame, text=tool_name,
                                command=lambda n=tool_name: self.run_tool(n))
                btn.pack(side=tk.LEFT, padx=(0, 10))
                
                # Tool description
                desc_label = ttk.Label(tool_frame, text=tool_desc)
                desc_label.pack(side=tk.LEFT)
                
                row += 1
    
    def setup_custom_tools(self, parent):
        """Setup custom tools panel"""
        # Check for tools directory
        tools_dir = os.path.join(current_dir, "tools")
        
        if not os.path.exists(tools_dir):
            # Create tools directory
            os.makedirs(tools_dir)
            
            # Create sample tools
            sample_tools = [
                ("sample_scan.py", "#!/usr/bin/env python3\nprint('Sample scan tool')"),
                ("quick_check.sh", "#!/bin/bash\necho 'Quick check tool'"),
                ("custom_analyzer.py", "#!/usr/bin/env python3\nprint('Custom analyzer')")
            ]
            
            for filename, content in sample_tools:
                with open(os.path.join(tools_dir, filename), 'w') as f:
                    f.write(content)
        
        # List custom tools
        custom_tools = []
        for f in os.listdir(tools_dir):
            if f.endswith(('.py', '.sh', '.bat')):
                custom_tools.append(f)
        
        # Display custom tools
        if custom_tools:
            label = ttk.Label(parent, text="Custom Tools Found:", font=("Arial", 10, "bold"))
            label.pack(pady=10)
            
            for tool in sorted(custom_tools):
                btn = ttk.Button(parent, text=tool,
                                command=lambda t=tool: self.run_custom_tool(t))
                btn.pack(pady=2, padx=20, fill=tk.X)
        else:
            label = ttk.Label(parent, text="No custom tools found in /tools directory")
            label.pack(pady=50)
        
        # Add tool button
        add_btn = ttk.Button(parent, text="Add New Tool", command=self.add_new_tool)
        add_btn.pack(pady=20)
    
    def setup_tool_manager(self, parent):
        """Setup tool manager panel"""
        label = ttk.Label(parent, text="Tool Manager", font=("Arial", 12, "bold"))
        label.pack(pady=10)
        
        # Tool list
        list_frame = ttk.Frame(parent)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.tool_listbox = tk.Listbox(list_frame)
        scrollbar = ttk.Scrollbar(list_frame)
        
        self.tool_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tool_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.tool_listbox.yview)
        
        # Populate with default tools
        default_tools = [
            "Integrity Check",
            "Security Scan", 
            "Process Monitor",
            "Code Visualizer"
        ]
        
        for tool in default_tools:
            self.tool_listbox.insert(tk.END, tool)
        
        # Management buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Edit", command=self.edit_tool).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove", command=self.remove_tool).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Export", command=self.export_tools).pack(side=tk.LEFT, padx=5)
    
    def setup_config_ui(self):
        """Setup configuration interface"""
        # Create notebook
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Color Scheme Tab
        color_frame = ttk.Frame(notebook)
        self.setup_color_config(color_frame)
        notebook.add(color_frame, text="Color Scheme")
        
        # Priority Settings Tab
        priority_frame = ttk.Frame(notebook)
        self.setup_priority_config(priority_frame)
        notebook.add(priority_frame, text="Priority Settings")
        
        # GUI Settings Tab
        gui_frame = ttk.Frame(notebook)
        self.setup_gui_config(gui_frame)
        notebook.add(gui_frame, text="GUI Settings")
    
    def setup_color_config(self, parent):
        """Setup color configuration"""
        label = ttk.Label(parent, text="Color Scheme Configuration", 
                         font=("Arial", 12, "bold"))
        label.pack(pady=10)
        
        # Color scheme selector
        schemes = ["dark", "light", "monokai", "solarized", "dracula"]
        
        scheme_var = tk.StringVar(value="dark")
        
        for scheme in schemes:
            rb = ttk.Radiobutton(parent, text=scheme.title(), 
                                variable=scheme_var, value=scheme)
            rb.pack(pady=2, anchor="w", padx=20)
        
        # Preview button
        preview_btn = ttk.Button(parent, text="Preview Scheme",
                                command=lambda: self.preview_scheme(scheme_var.get()))
        preview_btn.pack(pady=10)
        
        # Apply button
        apply_btn = ttk.Button(parent, text="Apply Scheme",
                              command=lambda: self.apply_scheme(scheme_var.get()))
        apply_btn.pack(pady=5)
        
        # Custom colors section
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20, padx=20)
        
        custom_label = ttk.Label(parent, text="Custom Colors", font=("Arial", 10, "bold"))
        custom_label.pack()
        
        # Color pickers would go here (simplified for now)
        ttk.Label(parent, text="Advanced color customization coming soon...").pack(pady=20)
    
    def setup_priority_config(self, parent):
        """Setup priority configuration"""
        label = ttk.Label(parent, text="Process Priority Configuration", 
                         font=("Arial", 12, "bold"))
        label.pack(pady=10)
        
        # Priority categories
        categories = [
            ("MY SCRIPTS", "Green", 1),
            ("GPU & MEDIA", "Purple", 2),
            ("WEB & COMMS", "Blue", 3),
            ("DEV TOOLS", "Yellow", 4),
            ("TERMINALS", "Cyan", 5),
            ("SYSTEM", "Gray", 99)
        ]
        
        # Create table
        tree = ttk.Treeview(parent, columns=("color", "priority"), show="headings")
        
        tree.heading("color", text="Color")
        tree.heading("priority", text="Priority")
        
        tree.column("color", width=100)
        tree.column("priority", width=100)
        
        for category, color, priority in categories:
            tree.insert("", tk.END, values=(color, priority))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Edit button
        edit_btn = ttk.Button(parent, text="Edit Priorities", 
                             command=self.edit_priorities)
        edit_btn.pack(pady=10)
    
    def setup_gui_config(self, parent):
        """Setup GUI configuration"""
        label = ttk.Label(parent, text="GUI Configuration", 
                         font=("Arial", 12, "bold"))
        label.pack(pady=10)
        
        # Configuration options
        options = [
            ("Auto-refresh logs", tk.BooleanVar(value=True)),
            ("Show line numbers", tk.BooleanVar(value=True)),
            ("Confirm before exit", tk.BooleanVar(value=True)),
            ("Remember window size", tk.BooleanVar(value=True)),
            ("Enable tooltips", tk.BooleanVar(value=True)),
            ("Dark mode by default", tk.BooleanVar(value=True))
        ]
        
        for option_text, var in options:
            cb = ttk.Checkbutton(parent, text=option_text, variable=var)
            cb.pack(pady=2, anchor="w", padx=20)
        
        # Save button
        save_btn = ttk.Button(parent, text="Save Settings", 
                             command=self.save_gui_settings)
        save_btn.pack(pady=20)
    
    def run_tool(self, tool_name):
        """Run a default tool"""
        messagebox.showinfo("Run Tool", f"Would run: {tool_name}")
        # In actual implementation, this would trigger the tool in the main GUI
    
    def run_custom_tool(self, tool_name):
        """Run a custom tool"""
        tool_path = os.path.join(current_dir, "tools", tool_name)
        
        if os.path.exists(tool_path):
            import subprocess
            
            try:
                if tool_name.endswith('.py'):
                    subprocess.run([sys.executable, tool_path])
                elif tool_name.endswith('.sh'):
                    subprocess.run(['bash', tool_path])
                elif tool_name.endswith('.bat'):
                    subprocess.run([tool_path], shell=True)
                
                messagebox.showinfo("Success", f"Ran tool: {tool_name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to run tool: {e}")
        else:
            messagebox.showerror("Error", f"Tool not found: {tool_name}")
    
    def add_new_tool(self):
        """Add a new custom tool"""
        # Simple tool creation dialog
        dialog = tk.Toplevel(self.window)
        dialog.title("Add New Tool")
        dialog.geometry("400x300")
        
        ttk.Label(dialog, text="Tool Name:").pack(pady=5)
        name_entry = ttk.Entry(dialog, width=30)
        name_entry.pack(pady=5)
        
        ttk.Label(dialog, text="Tool Type:").pack(pady=5)
        type_var = tk.StringVar(value="python")
        type_combo = ttk.Combobox(dialog, textvariable=type_var, 
                                 values=["python", "bash", "batch"])
        type_combo.pack(pady=5)
        
        ttk.Label(dialog, text="Tool Code:").pack(pady=5)
        code_text = tk.Text(dialog, height=10)
        code_text.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        
        def save_tool():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a tool name")
                return
            
            # Add extension if missing
            extensions = {"python": ".py", "bash": ".sh", "batch": ".bat"}
            if not any(name.endswith(ext) for ext in extensions.values()):
                name += extensions.get(type_var.get(), ".py")
            
            # Save tool
            tools_dir = os.path.join(current_dir, "tools")
            tool_path = os.path.join(tools_dir, name)
            
            with open(tool_path, 'w') as f:
                f.write(code_text.get(1.0, tk.END))
            
            # Make executable if on Unix
            if hasattr(os, 'chmod'):
                os.chmod(tool_path, 0o755)
            
            messagebox.showinfo("Success", f"Tool created: {name}")
            dialog.destroy()
            
            # Refresh custom tools view
            self.setup_custom_tools(self.window.winfo_children()[0].winfo_children()[1])
        
        ttk.Button(dialog, text="Save Tool", command=save_tool).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
        
        dialog.transient(self.window)
        dialog.grab_set()
    
    def edit_tool(self):
        """Edit selected tool"""
        selection = self.tool_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tool to edit")
            return
        
        tool_name = self.tool_listbox.get(selection[0])
        messagebox.showinfo("Edit Tool", f"Would edit: {tool_name}")
    
    def remove_tool(self):
        """Remove selected tool"""
        selection = self.tool_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a tool to remove")
            return
        
        tool_name = self.tool_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm", f"Remove tool: {tool_name}?"):
            self.tool_listbox.delete(selection[0])
            messagebox.showinfo("Success", f"Removed: {tool_name}")
    
    def export_tools(self):
        """Export tools configuration"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            # Export tool configuration
            import json
            tools_config = {
                "tools": list(self.tool_listbox.get(0, tk.END)),
                "exported": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(file_path, 'w') as f:
                json.dump(tools_config, f, indent=2)
            
            messagebox.showinfo("Success", f"Tools exported to: {file_path}")
    
    def preview_scheme(self, scheme_name):
        """Preview color scheme"""
        messagebox.showinfo("Preview", f"Would preview: {scheme_name} scheme")
    
    def apply_scheme(self, scheme_name):
        """Apply color scheme to main app"""
        try:
            # Check if parent has apply_theme method (SecureViewApp)
            if hasattr(self.parent, 'app'):
                 self.parent.app.apply_theme(scheme_name)
            elif hasattr(self.parent, 'apply_theme'):
                 self.parent.apply_theme(scheme_name)
                 
            messagebox.showinfo("Success", f"Theme '{scheme_name}' applied.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply theme: {e}")
    
    def edit_priorities(self):
        """Edit priority settings"""
        messagebox.showinfo("Edit Priorities", "Priority editor coming soon")
    
    def save_gui_settings(self):
        """Save GUI settings"""
        messagebox.showinfo("Save", "GUI settings saved")

# For testing
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide main window
    
    # Test tools popup
    popup = SharedPopupGUI(root, "tools")
    
    # Test config popup
    # popup = SharedPopupGUI(root, "config")
    
    root.mainloop()