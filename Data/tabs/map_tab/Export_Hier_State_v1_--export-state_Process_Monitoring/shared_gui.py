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
from datetime import datetime

# --- Unified Logging ---
from unified_logger import get_logger, setup_exception_handler

# Initialize logger for popup dialogs
logging = get_logger("popup", console_output=True)
setup_exception_handler(logging)

logging.info("Shared GUI module loaded")

# Directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
current_dir = SCRIPT_DIR

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
        notebook.add(color_frame, text="Themes")
        
        # NEW: Hier-Colors Tab
        hier_frame = ttk.Frame(notebook)
        self.setup_hier_color_config(hier_frame)
        notebook.add(hier_frame, text="Hier-Colors")

        # NEW: Context Menu Tab
        menu_frame = ttk.Frame(notebook)
        self.setup_menu_config(menu_frame)
        notebook.add(menu_frame, text="Right-Click Actions")
        
        # Priority Settings Tab
        priority_frame = ttk.Frame(notebook)
        self.setup_priority_config(priority_frame)
        notebook.add(priority_frame, text="Priority Settings")
        
        # GUI Settings Tab
        gui_frame = ttk.Frame(notebook)
        self.setup_gui_config(gui_frame)
        notebook.add(gui_frame, text="GUI Settings")

        # NEW: Brain Map Settings Tab
        brain_frame = ttk.Frame(notebook)
        self.setup_brain_map_config(brain_frame)
        notebook.add(brain_frame, text="Brain Map")

        # NEW: Process Monitor Settings Tab
        monitor_frame = ttk.Frame(notebook)
        self.setup_proc_monitor_config(monitor_frame)
        notebook.add(monitor_frame, text="Process Monitor")

        # NEW: Layout & Tooltips Tab
        layout_frame = ttk.Frame(notebook)
        self.setup_layout_config(layout_frame)
        notebook.add(layout_frame, text="Layout & Tooltips")

        # NEW: Logging & Debug Tab
        logging_frame = ttk.Frame(notebook)
        self.setup_logging_config(logging_frame)
        notebook.add(logging_frame, text="Logging & Debug")

    def setup_brain_map_config(self, parent):
        """UI for editing Brain Map configuration."""
        from process_organizer import CM
        bm_cfg = CM.config['user_prefs'].get('brain_map', {})
        
        ttk.Label(parent, text="Brain Map & Resource Controls", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Scrollable container
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas)
        container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y")
        
        self.bm_vars = {
            "enable_debug": tk.BooleanVar(value=bm_cfg.get("enable_debug", False)),
            "auto_rotate": tk.BooleanVar(value=bm_cfg.get("auto_rotate", False)),
            "show_edges": tk.BooleanVar(value=bm_cfg.get("show_edges", True)),
            "show_labels": tk.BooleanVar(value=bm_cfg.get("show_labels", True)),
            "show_fps_overlay": tk.BooleanVar(value=bm_cfg.get("show_fps_overlay", False)),
            "high_perf_mode": tk.BooleanVar(value=bm_cfg.get("high_perf_mode", False))
        }
        
        row = 0
        ttk.Label(container, text="Rendering & Interaction", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 5))
        row += 1

        for key, var in self.bm_vars.items():
            text = key.replace('_', ' ').title()
            if key == "high_perf_mode": text = "High Perf Mode (Simplified Geometry)"
            ttk.Checkbutton(container, text=text, variable=var).grid(row=row, column=0, sticky="w", pady=2)
            row += 1
            
        ttk.Label(container, text="Sensitivity:").grid(row=row, column=0, sticky="w", pady=5)
        self.bm_sens_scale = tk.Scale(container, from_=0.1, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, length=150)
        self.bm_sens_scale.set(bm_cfg.get('sensitivity', 0.5))
        self.bm_sens_scale.grid(row=row, column=1, sticky="w", padx=5)
        row += 1

        ttk.Label(container, text="Resource Controls", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(15, 5))
        row += 1

        ttk.Label(container, text="Parented Resource Level:").grid(row=row, column=0, sticky="w", pady=5)
        self.bm_resource_scale = tk.Scale(container, from_=1, to=100, orient=tk.HORIZONTAL, length=150)
        self.bm_resource_scale.set(bm_cfg.get('resource_level', 50))
        self.bm_resource_scale.grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        ttk.Label(container, text="(Co-ordinates FPS, Refresh, and Analysis Depth)", font=("Arial", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1

        ttk.Label(container, text="Region Colors", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(15, 5))
        row += 1

        self.color_vars = {}
        region_colors = bm_cfg.get('region_colors', {})
        for region, color in region_colors.items():
            ttk.Label(container, text=f"{region}:").grid(row=row, column=0, sticky="w", pady=2)
            ent = ttk.Entry(container, width=10)
            ent.insert(0, color)
            ent.grid(row=row, column=1, sticky="w", padx=5)
            self.color_vars[region] = ent
            row += 1
        
        def save_bm_settings():
            try:
                new_cfg = CM.config['user_prefs'].get('brain_map', {})
                for k, v in self.bm_vars.items():
                    new_cfg[k] = v.get()
                
                new_cfg['sensitivity'] = float(self.bm_sens_scale.get())
                new_cfg['resource_level'] = int(self.bm_resource_scale.get())
                
                # Derive other values from resource level
                res = new_cfg['resource_level']
                new_cfg['fps_target'] = int(10 + (res / 100.0) * 50) # 10 to 60 FPS
                new_cfg['update_interval_ms'] = int(5000 - (res / 100.0) * 4500) # 5s to 0.5s
                
                # Colors
                new_colors = {reg: ent.get() for reg, ent in self.color_vars.items()}
                new_cfg['region_colors'] = new_colors
                
                CM.config['user_prefs']['brain_map'] = new_cfg
                CM.save_config()
                messagebox.showinfo("Success", "Brain Map & Resource settings saved.\nFPS and Refresh updated based on Resource Level.")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric value in configuration.")
                
        ttk.Button(parent, text="Save Settings", command=save_bm_settings).pack(pady=10)

    def setup_proc_monitor_config(self, parent):
        """UI for editing Process Monitor configuration."""
        from process_organizer import CM
        pm_cfg = CM.config['user_prefs'].get('process_monitor', {})
        filters = pm_cfg.get('filters', {})
        alerts = pm_cfg.get('alerts', {})
        
        ttk.Label(parent, text="Process Monitor Configuration", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Scrollable container
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas)
        container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y")
        
        self.pm_vars = {
            "hide_system_idle": tk.BooleanVar(value=filters.get("hide_system_idle", True)),
            "enable_notifications": tk.BooleanVar(value=alerts.get("enable_notifications", False)),
            "alert_sound": tk.BooleanVar(value=alerts.get("alert_sound", False))
        }
        
        row = 0
        ttk.Label(container, text="Filters", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 5))
        row += 1
        
        ttk.Checkbutton(container, text="Hide System Idle", variable=self.pm_vars["hide_system_idle"]).grid(row=row, column=0, sticky="w", pady=2)
        row += 1
        
        ttk.Label(container, text="Min CPU Threshold (%):").grid(row=row, column=0, sticky="w", pady=2)
        self.min_cpu_ent = ttk.Entry(container, width=10)
        self.min_cpu_ent.insert(0, str(filters.get('min_cpu_threshold', 0.1)))
        self.min_cpu_ent.grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        
        ttk.Label(container, text="Min Mem Threshold (%):").grid(row=row, column=0, sticky="w", pady=2)
        self.min_mem_ent = ttk.Entry(container, width=10)
        self.min_mem_ent.insert(0, str(filters.get('min_mem_threshold', 0.1)))
        self.min_mem_ent.grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        
        ttk.Label(container, text="Alerts", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(15, 5))
        row += 1
        
        ttk.Checkbutton(container, text="Enable Notifications", variable=self.pm_vars["enable_notifications"]).grid(row=row, column=0, sticky="w", pady=2)
        row += 1
        
        ttk.Label(container, text="CPU Alert Threshold (%):").grid(row=row, column=0, sticky="w", pady=2)
        self.cpu_alert_ent = ttk.Entry(container, width=10)
        self.cpu_alert_ent.insert(0, str(alerts.get('cpu_threshold', 80.0)))
        self.cpu_alert_ent.grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        
        ttk.Label(container, text="Mem Alert Threshold (%):").grid(row=row, column=0, sticky="w", pady=2)
        self.mem_alert_ent = ttk.Entry(container, width=10)
        self.mem_alert_ent.insert(0, str(alerts.get('mem_threshold', 85.0)))
        self.mem_alert_ent.grid(row=row, column=1, sticky="w", padx=5)
        row += 1
        
        def save_pm_settings():
            try:
                CM.config['user_prefs']['process_monitor']['filters']['hide_system_idle'] = self.pm_vars["hide_system_idle"].get()
                CM.config['user_prefs']['process_monitor']['filters']['min_cpu_threshold'] = float(self.min_cpu_ent.get())
                CM.config['user_prefs']['process_monitor']['filters']['min_mem_threshold'] = float(self.min_mem_ent.get())
                
                CM.config['user_prefs']['process_monitor']['alerts']['enable_notifications'] = self.pm_vars["enable_notifications"].get()
                CM.config['user_prefs']['process_monitor']['alerts']['cpu_threshold'] = float(self.cpu_alert_ent.get())
                CM.config['user_prefs']['process_monitor']['alerts']['mem_threshold'] = float(self.mem_alert_ent.get())
                
                CM.save_config()
                messagebox.showinfo("Success", "Process Monitor settings saved.")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric value for thresholds.")
                
        ttk.Button(parent, text="Save Monitor Settings", command=save_pm_settings).pack(pady=10)

    def setup_layout_config(self, parent):
        """UI for editing dimensions manifest and hover delay."""
        from process_organizer import CM
        prefs = CM.config.get('user_prefs', {})
        ui_dim = prefs.get('ui_dim', {})
        i_cfg = prefs.get('inspection_config', {})
        
        ttk.Label(parent, text="UI Dimensions & Tooltip Settings", font=("Arial", 10, "bold")).pack(pady=10)
        
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        self.dim_entries = {}
        row = 0
        for key, value in ui_dim.items():
            ttk.Label(container, text=f"{key.replace('_', ' ').title()}:").grid(row=row, column=0, sticky="w", pady=2)
            ent = ttk.Entry(container, width=10)
            ent.insert(0, str(value))
            ent.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.dim_entries[key] = ent
            row += 1
            
        ttk.Separator(container, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        
        ttk.Label(container, text="Hover Delay (ms):").grid(row=row, column=0, sticky="w", pady=2)
        self.hover_delay_ent = ttk.Entry(container, width=10)
        self.hover_delay_ent.insert(0, str(i_cfg.get('hover_delay', 500)))
        self.hover_delay_ent.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1

        ttk.Label(container, text="Indicator Position:").grid(row=row, column=0, sticky="w", pady=2)
        self.pos_var = tk.StringVar(value=i_cfg.get('indicator_pos', 'right'))
        pos_combo = ttk.Combobox(container, textvariable=self.pos_var, values=['top', 'bottom', 'left', 'right'], width=8)
        pos_combo.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
            
        def save_layout_settings():
            try:
                new_dim = {k: int(e.get()) for k, e in self.dim_entries.items()}
                new_delay = int(self.hover_delay_ent.get())
                new_pos = self.pos_var.get()
                
                CM.config['user_prefs']['ui_dim'] = new_dim
                CM.config['user_prefs']['inspection_config']['hover_delay'] = new_delay
                CM.config['user_prefs']['inspection_config']['indicator_pos'] = new_pos
                CM.save_config()
                messagebox.showinfo("Success", "Layout settings saved. Restart application to apply dimension changes.")
            except ValueError:
                messagebox.showerror("Error", "Invalid numeric value entered.")
            
        ttk.Button(parent, text="Save Layout Settings", command=save_layout_settings).pack(pady=10)

    def setup_logging_config(self, parent):
        """UI for editing Logging & Debug configuration."""
        from process_organizer import CM
        log_cfg = CM.config['user_prefs'].get('logging', {})
        levels = log_cfg.get('levels', {})
        
        ttk.Label(parent, text="Logging & Debug Configuration", font=("Arial", 12, "bold")).pack(pady=10)
        
        # Scrollable container
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        container = ttk.Frame(canvas)
        container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=20)
        scrollbar.pack(side="right", fill="y")
        
        row = 0
        ttk.Label(container, text="Unified Log Destination", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 5))
        row += 1
        
        dest_frame = ttk.Frame(container)
        dest_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=2)
        row += 1
        
        self.log_dest_var = tk.StringVar(value=log_cfg.get('custom_destination', ""))
        ttk.Entry(dest_frame, textvariable=self.log_dest_var, width=50).pack(side=tk.LEFT, padx=(0, 5))
        
        def browse_log_dest():
            filename = filedialog.asksaveasfilename(defaultextension=".log", 
                                                   filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")])
            if filename:
                self.log_dest_var.set(filename)
                
        ttk.Button(dest_frame, text="Browse...", command=browse_log_dest).pack(side=tk.LEFT)
        ttk.Label(container, text="(Leave blank for default /logs directory)", font=("Arial", 8, "italic")).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        
        ttk.Separator(container, orient=tk.HORIZONTAL).grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1
        
        ttk.Label(container, text="Module Logging Levels", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 5))
        row += 1
        
        self.log_level_vars = {}
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        
        for module, level in levels.items():
            ttk.Label(container, text=f"{module.title()}:").grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=level)
            combo = ttk.Combobox(container, textvariable=var, values=log_levels, width=10, state="readonly")
            combo.grid(row=row, column=1, sticky="w", padx=5, pady=2)
            self.log_level_vars[module] = var
            row += 1
            
        def save_logging_settings():
            try:
                new_dest = self.log_dest_var.get().strip()
                # Basic validation: if not empty, must be in a valid directory
                if new_dest and not os.path.isdir(os.path.dirname(os.path.abspath(new_dest))):
                    messagebox.showerror("Error", "Invalid directory for custom log destination.")
                    return
                    
                CM.config['user_prefs']['logging']['custom_destination'] = new_dest
                
                for module, var in self.log_level_vars.items():
                    CM.config['user_prefs']['logging']['levels'][module] = var.get()
                
                CM.save_config()
                messagebox.showinfo("Success", "Logging settings saved. Changes to log destination will apply on next restart.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save logging settings: {e}")
                
        ttk.Button(parent, text="Save Logging Settings", command=save_logging_settings).pack(pady=10)

    def setup_hier_color_config(self, parent):
        """UI for editing TreeView colors based on element type"""
        from process_organizer import CM
        hier_colors = CM.config['user_prefs'].get('hier_colors', {})
        
        ttk.Label(parent, text="Hierarchical Tree Colors", font=("Arial", 10, "bold")).pack(pady=10)
        
        container = ttk.Frame(parent); container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        self.color_entries = {}
        for i, (kind, color) in enumerate(hier_colors.items()):
            ttk.Label(container, text=f"{kind}:").grid(row=i, column=0, sticky="w", pady=2)
            ent = ttk.Entry(container, width=15)
            ent.insert(0, color)
            ent.grid(row=i, column=1, sticky="w", padx=5, pady=2)
            self.color_entries[kind] = ent
            
        def save_hier_colors():
            new_colors = {k: e.get() for k, e in self.color_entries.items()}
            CM.config['user_prefs']['hier_colors'] = new_colors
            CM.save_config()
            messagebox.showinfo("Success", "Hierarchical colors saved.")
            
        ttk.Button(parent, text="Save Hier-Colors", command=save_hier_colors).pack(pady=10)

    def setup_menu_config(self, parent):
        """UI for ordering and toggling right-click actions"""
        from process_organizer import CM
        actions = CM.config['user_prefs'].get('context_menu_actions', [])
        
        ttk.Label(parent, text="Right-Click Context Menu Actions", font=("Arial", 10, "bold")).pack(pady=10)
        
        self.menu_listbox = tk.Listbox(parent, height=8)
        for action in actions:
            self.menu_listbox.insert(tk.END, action['label'])
        self.menu_listbox.pack(fill=tk.X, padx=20, pady=5)
        
        btn_frame = ttk.Frame(parent); btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Move Up", command=lambda: self.move_action(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Move Down", command=lambda: self.move_action(1)).pack(side=tk.LEFT, padx=2)
        
        def save_menu():
            labels = self.menu_listbox.get(0, tk.END)
            # Reconstruct actions list based on new order of labels
            action_map = {a['label']: a['action'] for a in actions}
            new_actions = [{"label": l, "action": action_map[l]} for l in labels]
            CM.config['user_prefs']['context_menu_actions'] = new_actions
            CM.save_config()
            messagebox.showinfo("Success", "Context menu configuration saved.")

        ttk.Button(parent, text="Save Menu Config", command=save_menu).pack(pady=10)

    def move_action(self, direction):
        idx = self.menu_listbox.curselection()
        if not idx: return
        idx = idx[0]
        new_idx = idx + direction
        if 0 <= new_idx < self.menu_listbox.size():
            text = self.menu_listbox.get(idx)
            self.menu_listbox.delete(idx)
            self.menu_listbox.insert(new_idx, text)
            self.menu_listbox.selection_set(new_idx)
    
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
        """Setup GUI configuration linked to CM.config"""
        from process_organizer import CM
        prefs = CM.config.get('user_prefs', {})
        i_cfg = prefs.get('inspection_config', {})
        
        label = ttk.Label(parent, text="GUI Configuration", 
                         font=("Arial", 12, "bold"))
        label.pack(pady=10)
        
        # Configuration options
        self.gui_vars = {
            "show_line_numbers": tk.BooleanVar(value=prefs.get("show_line_numbers", True)),
            "enable_hover": tk.BooleanVar(value=i_cfg.get("enable_hover", True)),
            "sticky_bind_selection": tk.BooleanVar(value=i_cfg.get("sticky_bind_selection", True)),
            "auto_open": tk.BooleanVar(value=i_cfg.get("auto_open", True))
        }
        
        for key, var in self.gui_vars.items():
            text = key.replace('_', ' ').title()
            cb = ttk.Checkbutton(parent, text=text, variable=var)
            cb.pack(pady=2, anchor="w", padx=20)
        
        # Save button
        save_btn = ttk.Button(parent, text="Save GUI Settings", 
                             command=self.save_gui_settings)
        save_btn.pack(pady=20)
    
    def save_gui_settings(self):
        """Save GUI settings to CM.config"""
        from process_organizer import CM
        try:
            for key, var in self.gui_vars.items():
                if key in ["enable_hover", "sticky_bind_selection", "auto_open"]:
                    if 'inspection_config' not in CM.config['user_prefs']:
                        CM.config['user_prefs']['inspection_config'] = {}
                    CM.config['user_prefs']['inspection_config'][key] = var.get()
                else:
                    CM.config['user_prefs'][key] = var.get()
            
            CM.save_config()
            messagebox.showinfo("Success", "GUI settings saved.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save GUI settings: {e}")
    
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