#!/usr/bin/env python3
"""
Tkinter Object Inspector with Scope Analysis Tool
Usage:
    python3 inspector.py              # Run the hover inspector
    python3 inspector.py --scope      # Copy and analyze a file
    python3 inspector.py -h           # Show help
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import argparse
import os
import sys
import time
import threading
import queue
import subprocess
import inspect
from pathlib import Path
import shutil
import re
from datetime import datetime
import platform

# ============================================================================
# Configuration
# ============================================================================
CONFIG = {
    'hover_delay': 0.7,  # Cooldown between hover events
    'window_opacity': 0.92,
    'window_size': (600, 400),
    'lines_per_page': 50,
    'colors': {
        'call_issue': '#FF6B6B',      # Red-like
        'calling_issue': '#4ECDC4',   # Teal
        'action_route': '#FFD166',    # Yellow
        'import_line': '#06D6A0',     # Green
        'function_def': '#118AB2',    # Blue
        'comment': '#A0A0A0',         # Gray
        'normal': '#2B2D42',          # Dark blue-gray
        'highlight': '#EF476F',       # Pink for highlighting
    },
    'font': ('Monospace', 10)
}

# ============================================================================
# CLI Argument Parser
# ============================================================================
def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Tkinter Object Inspector with Scope Analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python3 inspector.py                    # Run hover inspector
    python3 inspector.py --scope            # Open scope analysis dialog
    python3 inspector.py --scope --copy /path/to/file.py
    python3 inspector.py --monitor          # Show runtime activity monitor
        '''
    )
    
    parser.add_argument('--scope', action='store_true',
                       help='Enter scope analysis mode (opens dialog if no file specified)')
    parser.add_argument('--copy', type=str, metavar='FILE',
                       help='Copy and analyze specified file')
    parser.add_argument('--monitor', action='store_true',
                       help='Show runtime activity monitor')
    parser.add_argument('--lines', type=int, default=50,
                       help='Lines per page (default: 50)')
    
    return parser.parse_args()

# ============================================================================
# File Scope Analysis Module
# ============================================================================
class ScopeAnalyzer:
    def __init__(self):
        self.file_counter = 0
        self.log_file = "scope_analysis.log"
        
    def analyze_file(self, source_path, copy=True):
        """Copy and analyze a Python file"""
        try:
            source_path = Path(source_path).resolve()
            
            if not source_path.exists():
                return False, f"File not found: {source_path}"
            
            if not source_path.suffix == '.py':
                return False, "Only .py files are supported"
            
            # Generate copy filename
            self.file_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            copy_name = f"scoped_{timestamp}_{self.file_counter:03d}.py"
            dest_path = source_path.parent / copy_name
            
            # Copy file if requested
            if copy:
                shutil.copy2(source_path, dest_path)
                dest_info = f"Copied to: {dest_path.name}"
            else:
                dest_path = source_path
                dest_info = "Original file (no copy made)"
            
            # Analyze file
            stats = self._get_file_stats(source_path)
            analysis = self._analyze_content(source_path)
            
            # Write to log
            log_entry = self._write_log(source_path, dest_path, stats, analysis)
            
            return True, {
                'source': source_path,
                'destination': dest_path if copy else None,
                'stats': stats,
                'analysis': analysis,
                'log_entry': log_entry,
                'copy_made': copy
            }
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def _get_file_stats(self, filepath):
        """Get basic file statistics"""
        stats = os.stat(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
        
        return {
            'size_bytes': stats.st_size,
            'size_kb': stats.st_size / 1024,
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'name': filepath.name,
            'path': str(filepath.parent),
            'modified': datetime.fromtimestamp(stats.st_mtime)
        }
    
    def _analyze_content(self, filepath):
        """Analyze file content for imports, functions, etc."""
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        analysis = {
            'imports': [],
            'functions': [],
            'classes': [],
            'calls': [],
            'ui_elements': [],
            'line_details': {}
        }
        
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            analysis['line_details'][idx] = {
                'content': line.rstrip('\n'),
                'type': 'normal'
            }
            
            # Detect imports
            if stripped.startswith(('import ', 'from ')):
                analysis['imports'].append((idx, stripped))
                analysis['line_details'][idx]['type'] = 'import'
            
            # Detect function definitions
            elif stripped.startswith('def '):
                func_name = stripped[4:].split('(')[0].strip()
                analysis['functions'].append((idx, func_name))
                analysis['line_details'][idx]['type'] = 'function_def'
            
            # Detect class definitions
            elif stripped.startswith('class '):
                class_name = stripped[6:].split('(')[0].split(':')[0].strip()
                analysis['classes'].append((idx, class_name))
                analysis['line_details'][idx]['type'] = 'class_def'
            
            # Detect UI elements (tkinter)
            elif any(pattern in line for pattern in ['.pack(', '.grid(', '.place(', '=tk.', '=ttk.']):
                analysis['ui_elements'].append((idx, stripped))
                analysis['line_details'][idx]['type'] = 'ui_element'
            
            # Detect function calls
            elif re.search(r'\b[\w_]+\([^)]*\)', stripped) and not stripped.startswith('#'):
                analysis['calls'].append((idx, stripped))
        
        return analysis
    
    def _write_log(self, source, dest, stats, analysis):
        """Write analysis to log file"""
        log_entry = f"""
{'='*80}
Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Source File: {source.name}
Source Path: {source.parent}
Destination: {dest.name if hasattr(dest, 'name') else 'N/A'}
{'='*80}
File Size: {stats['size_kb']:.2f} KB ({stats['size_bytes']} bytes)
Total Lines: {stats['total_lines']}
Non-empty Lines: {stats['non_empty_lines']}
Last Modified: {stats['modified']}
{'='*80}
IMPORTS ({len(analysis['imports'])}):
{chr(10).join(f'  Line {ln}: {imp}' for ln, imp in analysis['imports'])}
{'='*80}
FUNCTIONS ({len(analysis['functions'])}):
{chr(10).join(f'  Line {ln}: def {func}' for ln, func in analysis['functions'])}
{'='*80}
CLASSES ({len(analysis['classes'])}):
{chr(10).join(f'  Line {ln}: class {cls}' for ln, cls in analysis['classes'])}
{'='*80}
UI ELEMENTS ({len(analysis['ui_elements'])}):
{chr(10).join(f'  Line {ln}: {elem}' for ln, elem in analysis['ui_elements'][:10])}
{'='*80}
"""
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        
        return log_entry

# ============================================================================
# Runtime Activity Monitor (Linux Native)
# ============================================================================
class ActivityMonitor:
    def __init__(self):
        self.is_linux = platform.system() == 'Linux'
        self.activity_queue = queue.Queue()
        self.monitoring = False
        
    def start_monitoring(self):
        """Start monitoring system activity (Linux only)"""
        if not self.is_linux:
            return False
        
        self.monitoring = True
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()
        return True
    
    def _monitor_loop(self):
        """Linux-specific activity monitoring loop"""
        try:
            # Use psutil if available, fallback to basic system calls
            try:
                import psutil
                use_psutil = True
            except ImportError:
                use_psutil = False
                # Fallback to basic ps command
                pass
            
            while self.monitoring:
                if use_psutil:
                    # Get CPU and memory info using psutil
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    self.activity_queue.put({
                        'cpu': cpu_percent,
                        'memory': memory.percent,
                        'timestamp': time.time()
                    })
                else:
                    # Basic system info (fallback)
                    self.activity_queue.put({
                        'cpu': 0,
                        'memory': 0,
                        'timestamp': time.time(),
                        'note': 'Install psutil for detailed metrics'
                    })
                time.sleep(2)
                
        except Exception as e:
            self.activity_queue.put({'error': str(e)})
    
    def stop_monitoring(self):
        self.monitoring = False
    
    def get_activity(self):
        """Get latest activity data"""
        data = {}
        while not self.activity_queue.empty():
            data = self.activity_queue.get_nowait()
        return data

# ============================================================================
# Main Hover Inspector Window
# ============================================================================
class HoverInspector:
    def __init__(self, root):
        self.root = root
        self.root.title("Tkinter Object Inspector")
        self.root.geometry(f"{CONFIG['window_size'][0]}x{CONFIG['window_size'][1]}")
        self.root.attributes('-alpha', CONFIG['window_opacity'])
        
        # Track hover state
        self.last_hover_time = 0
        self.current_widget = None
        self.hover_window = None
        self.hover_data = {}
        
        # Activity monitor
        self.monitor = ActivityMonitor()
        self.monitor.start_monitoring()
        
        # Setup UI
        self.setup_ui()
        
        # Bind hover events to all widgets
        self.bind_hover_events(self.root)
        
    def setup_ui(self):
        """Setup the main UI"""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Load Scope", command=self.load_scope_dialog)
        file_menu.add_command(label="Clear Log", command=self.clear_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Activity Monitor", command=self.show_activity_monitor)
        view_menu.add_command(label="Code Navigator", command=self.show_code_navigator)
        
        # Main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Inspector tab
        self.inspector_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inspector_frame, text="Inspector")
        
        # Widget info display
        self.info_text = scrolledtext.ScrolledText(
            self.inspector_frame, 
            height=15,
            font=CONFIG['font'],
            wrap=tk.WORD
        )
        self.info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready | Hover over any widget to inspect")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def bind_hover_events(self, widget):
        """Recursively bind hover events to all widgets"""
        widget.bind('<Enter>', self.on_widget_enter)
        widget.bind('<Leave>', self.on_widget_leave)
        
        # Bind right-click for navigation
        widget.bind('<Button-3>', self.on_right_click)
        
        # Bind mouse wheel for scrolling
        widget.bind('<MouseWheel>', self.on_mouse_wheel)
        widget.bind('<Button-4>', self.on_mouse_wheel)  # Linux scroll up
        widget.bind('<Button-5>', self.on_mouse_wheel)  # Linux scroll down
        
        # Process children
        for child in widget.winfo_children():
            self.bind_hover_events(child)
    
    def on_widget_enter(self, event):
        """Handle mouse enter event with cooldown"""
        current_time = time.time()
        if current_time - self.last_hover_time < CONFIG['hover_delay']:
            return
        
        self.last_hover_time = current_time
        self.current_widget = event.widget
        
        # Schedule hover window display
        self.root.after(100, self.show_hover_info)
    
    def on_widget_leave(self, event):
        """Handle mouse leave event"""
        if self.hover_window and self.hover_window.winfo_exists():
            self.hover_window.destroy()
            self.hover_window = None
    
    def show_hover_info(self):
        """Display hover window with widget information"""
        if not self.current_widget:
            return
        
        # Get widget info
        widget = self.current_widget
        widget_info = self.get_widget_info(widget)
        
        # Create hover window
        if self.hover_window and self.hover_window.winfo_exists():
            self.hover_window.destroy()
        
        self.hover_window = tk.Toplevel(self.root)
        self.hover_window.overrideredirect(True)
        self.hover_window.attributes('-alpha', 0.95)
        self.hover_window.configure(bg='white')
        
        # Position near mouse
        x = self.root.winfo_pointerx() + 20
        y = self.root.winfo_pointery() + 20
        self.hover_window.geometry(f"400x300+{x}+{y}")
        
        # Add content
        self.create_hover_content(widget_info)
    
    def get_widget_info(self, widget):
        """Extract information from widget"""
        info = {
            'class': widget.__class__.__name__,
            'id': str(widget),
            'children': len(widget.winfo_children()),
            'geometry': f"{widget.winfo_x()}x{widget.winfo_y()}+{widget.winfo_width()}+{widget.winfo_height()}",
            'state': widget.winfo_viewable(),
            'config': {k: v for k, v in widget.config().items() if v != ''},
            'bindings': widget.bind(),
            'callbacks': self.extract_callbacks(widget)
        }
        
        # Try to get source code location
        try:
            source_file = inspect.getfile(widget.__class__)
            info['source'] = source_file
        except:
            info['source'] = "Unknown"
        
        return info
    
    def extract_callbacks(self, widget):
        """Extract callback functions from widget"""
        callbacks = {}
        
        # Check for command attribute
        if hasattr(widget, 'command') and widget.command:
            callbacks['command'] = str(widget.command)
        
        # Check bindings
        for event in widget.bind():
            callback = widget.bind(event)
            if callback:
                callbacks[event] = str(callback)
        
        return callbacks
    
    def create_hover_content(self, widget_info):
        """Create content for hover window"""
        # Title
        title = tk.Label(
            self.hover_window,
            text=f"Widget: {widget_info['class']}",
            font=('Monospace', 11, 'bold'),
            bg='white'
        )
        title.pack(pady=(5, 0))
        
        # Info text
        info_text = scrolledtext.ScrolledText(
            self.hover_window,
            height=12,
            font=CONFIG['font']
        )
        info_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Populate info
        info_lines = [
            f"ID: {widget_info['id']}",
            f"Geometry: {widget_info['geometry']}",
            f"Children: {widget_info['children']}",
            f"Visible: {widget_info['state']}",
            f"Source: {widget_info.get('source', 'Unknown')}",
            "\nCallbacks:"
        ]
        
        for event, callback in widget_info['callbacks'].items():
            info_lines.append(f"  {event}: {callback}")
        
        info_lines.append("\nConfiguration:")
        for key, value in widget_info['config'].items():
            if isinstance(value, (list, tuple)) and value:
                info_lines.append(f"  {key}: {value[0]}")
        
        info_text.insert(1.0, '\n'.join(info_lines))
        info_text.config(state=tk.DISABLED)
        
        # Add close button
        close_btn = tk.Button(
            self.hover_window,
            text="Close",
            command=self.hover_window.destroy,
            width=10
        )
        close_btn.pack(pady=(0, 5))
    
    def on_right_click(self, event):
        """Handle right-click for navigation"""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="View Source", command=lambda: self.view_source(event.widget))
        menu.add_command(label="Show Hierarchy", command=lambda: self.show_hierarchy(event.widget))
        menu.add_command(label="Analyze Callbacks", command=lambda: self.analyze_callbacks(event.widget))
        menu.add_separator()
        menu.add_command(label="Copy Widget Info", command=lambda: self.copy_widget_info(event.widget))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def on_mouse_wheel(self, event):
        """Handle mouse wheel scrolling"""
        if self.hover_window and self.hover_window.winfo_exists():
            # Forward scroll event to hover window
            self.hover_window.event_generate('<MouseWheel>', 
                delta=(event.delta if hasattr(event, 'delta') else 
                      (1 if event.num == 4 else -1)))
    
    def view_source(self, widget):
        """View source code of widget"""
        try:
            source_file = inspect.getfile(widget.__class__)
            self.status_var.set(f"Source: {source_file}")
            
            # Load and display source
            self.display_source_code(source_file)
            
        except Exception as e:
            messagebox.showerror("Error", f"Cannot locate source: {e}")
    
    def display_source_code(self, filepath):
        """Display source code in a new tab"""
        # Create new tab for source code
        source_frame = ttk.Frame(self.notebook)
        self.notebook.add(source_frame, text=f"Source: {Path(filepath).name}")
        
        # Text widget with syntax highlighting
        text_widget = scrolledtext.ScrolledText(
            source_frame,
            font=CONFIG['font'],
            wrap=tk.NONE
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Load and colorize code
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                text_widget.insert(1.0, content)
                self.colorize_code(text_widget)
        except Exception as e:
            text_widget.insert(1.0, f"Error loading file: {e}")
    
    def colorize_code(self, text_widget):
        """Apply syntax highlighting to code"""
        content = text_widget.get(1.0, tk.END)
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            start_idx = f"{i}.0"
            end_idx = f"{i}.end"
            
            # Remove previous tags
            text_widget.tag_remove("import", start_idx, end_idx)
            text_widget.tag_remove("function_def", start_idx, end_idx)
            text_widget.tag_remove("comment", start_idx, end_idx)
            
            stripped = line.strip()
            
            # Color imports
            if stripped.startswith(('import ', 'from ')):
                text_widget.tag_add("import", start_idx, end_idx)
                text_widget.tag_config("import", 
                                      foreground=CONFIG['colors']['import_line'])
            
            # Color function definitions
            elif stripped.startswith('def '):
                text_widget.tag_add("function_def", start_idx, end_idx)
                text_widget.tag_config("function_def",
                                      foreground=CONFIG['colors']['function_def'])
            
            # Color comments
            elif stripped.startswith('#'):
                text_widget.tag_add("comment", start_idx, end_idx)
                text_widget.tag_config("comment",
                                      foreground=CONFIG['colors']['comment'])
        
        text_widget.config(state=tk.DISABLED)
    
    def show_hierarchy(self, widget):
        """Show widget hierarchy"""
        hierarchy = self.get_widget_hierarchy(widget)
        
        # Create hierarchy window
        hierarchy_win = tk.Toplevel(self.root)
        hierarchy_win.title("Widget Hierarchy")
        hierarchy_win.geometry("400x500")
        
        tree = ttk.Treeview(hierarchy_win)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # Build tree
        self.build_hierarchy_tree(tree, widget)
    
    def get_widget_hierarchy(self, widget):
        """Get widget hierarchy from root"""
        hierarchy = []
        current = widget
        
        while current:
            hierarchy.insert(0, {
                'class': current.__class__.__name__,
                'id': str(current),
                'children': len(current.winfo_children())
            })
            try:
                current = current.master
            except:
                break
        
        return hierarchy
    
    def build_hierarchy_tree(self, tree, widget, parent=""):
        """Build hierarchy tree recursively"""
        item_id = tree.insert(parent, "end", 
                            text=f"{widget.__class__.__name__} ({str(widget)})")
        
        for child in widget.winfo_children():
            self.build_hierarchy_tree(tree, child, item_id)
    
    def analyze_callbacks(self, widget):
        """Analyze callback functions"""
        callbacks = self.extract_callbacks(widget)
        
        analysis_win = tk.Toplevel(self.root)
        analysis_win.title("Callback Analysis")
        analysis_win.geometry("500x300")
        
        text = scrolledtext.ScrolledText(analysis_win)
        text.pack(fill=tk.BOTH, expand=True)
        
        if callbacks:
            text.insert(1.0, "Callback Analysis:\n\n")
            for event, callback in callbacks.items():
                text.insert(tk.END, f"Event: {event}\n")
                text.insert(tk.END, f"Callback: {callback}\n")
                text.insert(tk.END, "-" * 40 + "\n")
        else:
            text.insert(1.0, "No callbacks found")
        
        text.config(state=tk.DISABLED)
    
    def copy_widget_info(self, widget):
        """Copy widget info to clipboard"""
        info = self.get_widget_info(widget)
        info_str = f"Widget: {info['class']}\nID: {info['id']}\n"
        
        self.root.clipboard_clear()
        self.root.clipboard_append(info_str)
        self.status_var.set("Widget info copied to clipboard")
    
    def load_scope_dialog(self):
        """Open dialog to load and analyze a file"""
        filepath = filedialog.askopenfilename(
            title="Select Python File",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        
        if filepath:
            analyzer = ScopeAnalyzer()
            success, result = analyzer.analyze_file(filepath, copy=True)
            
            if success:
                messagebox.showinfo("Success", 
                    f"File analyzed and copied!\n"
                    f"Original: {result['stats']['name']}\n"
                    f"Lines: {result['stats']['total_lines']}\n"
                    f"Size: {result['stats']['size_kb']:.1f} KB\n"
                    f"Log saved to: {analyzer.log_file}")
                
                # Display the copied file
                self.display_source_code(str(result['destination']))
            else:
                messagebox.showerror("Error", result)
    
    def show_activity_monitor(self):
        """Show runtime activity monitor"""
        monitor_win = tk.Toplevel(self.root)
        monitor_win.title("Runtime Activity Monitor")
        monitor_win.geometry("400x200")
        
        # CPU label
        cpu_var = tk.StringVar(value="CPU: 0%")
        cpu_label = tk.Label(monitor_win, textvariable=cpu_var, font=('Monospace', 12))
        cpu_label.pack(pady=10)
        
        # Memory label
        mem_var = tk.StringVar(value="Memory: 0%")
        mem_label = tk.Label(monitor_win, textvariable=mem_var, font=('Monospace', 12))
        mem_label.pack(pady=10)
        
        # Update loop
        def update_monitor():
            activity = self.monitor.get_activity()
            if activity:
                if 'cpu' in activity:
                    cpu_var.set(f"CPU: {activity['cpu']}%")
                if 'memory' in activity:
                    mem_var.set(f"Memory: {activity['memory']}%")
                if 'note' in activity:
                    tk.Label(monitor_win, text=activity['note'], fg='blue').pack()
            
            monitor_win.after(2000, update_monitor)
        
        update_monitor()
    
    def show_code_navigator(self):
        """Show code navigator window"""
        nav_win = tk.Toplevel(self.root)
        nav_win.title("Code Navigator")
        nav_win.geometry("600x500")
        
        # Create notebook for pages
        nav_notebook = ttk.Notebook(nav_win)
        nav_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Add instructions
        help_frame = ttk.Frame(nav_notebook)
        nav_notebook.add(help_frame, text="Instructions")
        
        help_text = """CODE NAVIGATOR INSTRUCTIONS:

1. Hover over any widget to see its information
2. Right-click on widgets for navigation options:
   - View Source: Open the source code file
   - Show Hierarchy: Display widget parent/child relationships
   - Analyze Callbacks: Show event bindings and commands
3. Use mouse wheel to scroll through hover windows
4. File menu:
   - Load Scope: Analyze and copy Python files
   - Clear Log: Clear the scope analysis log
5. View menu:
   - Activity Monitor: Show system resource usage
   - Code Navigator: This window

Features:
- Smooth hover with cooldown
- Syntax highlighting
- File analysis and logging
- Runtime monitoring
- Widget hierarchy visualization
"""
        
        help_label = tk.Label(help_frame, text=help_text, justify=tk.LEFT, 
                            font=('Monospace', 10))
        help_label.pack(padx=10, pady=10)
    
    def clear_log(self):
        """Clear the scope analysis log"""
        try:
            with open("scope_analysis.log", 'w') as f:
                f.write("")
            self.status_var.set("Log cleared")
        except:
            self.status_var.set("Error clearing log")

# ============================================================================
# Scope Analysis GUI
# ============================================================================
class ScopeAnalysisGUI:
    def __init__(self, root, file_to_analyze=None):
        self.root = root
        self.root.title("Scope Analysis Tool")
        self.root.geometry("700x600")
        
        self.analyzer = ScopeAnalyzer()
        self.file_to_analyze = file_to_analyze
        
        self.setup_ui()
        
        if file_to_analyze:
            self.analyze_file(file_to_analyze)
    
    def setup_ui(self):
        """Setup the scope analysis UI"""
        # Top frame for file selection
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Label(top_frame, text="File Path:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.file_var = tk.StringVar()
        file_entry = ttk.Entry(top_frame, textvariable=self.file_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=(0, 5))
        
        browse_btn = ttk.Button(top_frame, text="Browse", command=self.browse_file)
        browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        analyze_btn = ttk.Button(top_frame, text="Analyze", command=self.analyze_current)
        analyze_btn.pack(side=tk.LEFT)
        
        # Analysis results frame
        results_frame = ttk.LabelFrame(self.root, text="Analysis Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Notebook for different views
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Stats tab
        stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(stats_frame, text="Statistics")
        
        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=15)
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Imports tab
        imports_frame = ttk.Frame(self.notebook)
        self.notebook.add(imports_frame, text="Imports")
        
        self.imports_text = scrolledtext.ScrolledText(imports_frame)
        self.imports_text.pack(fill=tk.BOTH, expand=True)
        
        # Functions tab
        funcs_frame = ttk.Frame(self.notebook)
        self.notebook.add(funcs_frame, text="Functions")
        
        self.funcs_text = scrolledtext.ScrolledText(funcs_frame)
        self.funcs_text.pack(fill=tk.BOTH, expand=True)
        
        # Log tab
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="Analysis Log")
        
        self.log_text = scrolledtext.ScrolledText(log_frame)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def browse_file(self):
        """Browse for a file to analyze"""
        filepath = filedialog.askopenfilename(
            title="Select Python File",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if filepath:
            self.file_var.set(filepath)
            self.analyze_file(filepath)
    
    def analyze_current(self):
        """Analyze the currently selected file"""
        filepath = self.file_var.get()
        if filepath and os.path.exists(filepath):
            self.analyze_file(filepath)
        else:
            messagebox.showerror("Error", "Please select a valid file")
    
    def analyze_file(self, filepath):
        """Analyze a file and display results"""
        success, result = self.analyzer.analyze_file(filepath, copy=True)
        
        if not success:
            messagebox.showerror("Error", result)
            return
        
        # Display statistics
        stats = result['stats']
        stats_text = f"""FILE STATISTICS:
{'='*40}
Name: {stats['name']}
Path: {stats['path']}
Size: {stats['size_kb']:.2f} KB ({stats['size_bytes']} bytes)
Total Lines: {stats['total_lines']}
Non-empty Lines: {stats['non_empty_lines']}
Last Modified: {stats['modified']}
{'='*40}
"""
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, stats_text)
        
        # Display imports
        imports = result['analysis']['imports']
        imports_text = f"IMPORTS ({len(imports)}):\n{'='*40}\n"
        for line_num, imp in imports:
            imports_text += f"Line {line_num}: {imp}\n"
        
        self.imports_text.delete(1.0, tk.END)
        self.imports_text.insert(1.0, imports_text)
        
        # Display functions
        funcs = result['analysis']['functions']
        funcs_text = f"FUNCTIONS ({len(funcs)}):\n{'='*40}\n"
        for line_num, func in funcs:
            funcs_text += f"Line {line_num}: def {func}()\n"
        
        self.funcs_text.delete(1.0, tk.END)
        self.funcs_text.insert(1.0, funcs_text)
        
        # Display log
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(1.0, result['log_entry'])
        
        self.file_var.set(filepath)
        messagebox.showinfo("Success", 
            f"Analysis complete!\n"
            f"File copied to: scoped_*.py\n"
            f"Log saved to: {self.analyzer.log_file}")

# ============================================================================
# Main Application
# ============================================================================
def main():
    args = parse_arguments()
    
    # Handle --scope mode
    if args.scope or args.copy:
        root = tk.Tk()
        
        if args.copy:
            # Analyze specified file
            app = ScopeAnalysisGUI(root, args.copy)
        else:
            # Open scope analysis dialog
            app = ScopeAnalysisGUI(root)
        
        root.mainloop()
    
    # Handle --monitor mode
    elif args.monitor:
        root = tk.Tk()
        inspector = HoverInspector(root)
        
        # Add some test widgets
        test_frame = ttk.Frame(inspector.inspector_frame)
        test_frame.pack(pady=10)
        
        ttk.Button(test_frame, text="Test Button 1", 
                  command=lambda: print("Button 1 clicked")).pack(side=tk.LEFT, padx=5)
        ttk.Button(test_frame, text="Test Button 2",
                  command=lambda: print("Button 2 clicked")).pack(side=tk.LEFT, padx=5)
        
        ttk.Entry(test_frame, width=20).pack(side=tk.LEFT, padx=5)
        
        root.mainloop()
    
    # Default mode: Hover inspector
    else:
        root = tk.Tk()
        inspector = HoverInspector(root)
        root.mainloop()

if __name__ == "__main__":
    main()