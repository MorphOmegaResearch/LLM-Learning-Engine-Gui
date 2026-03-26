#!/usr/bin/env python3
"""
process_brain_viz.py - Process-Centric 3D Brain Visualization

Adapts brain_viz_3d.py for real-time process monitoring with PID-centric view.
Maps process categories to brain regions, PIDs to nodes, and detects communication.
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import Axes3D
import psutil
from datetime import datetime
from unified_logger import get_logger
from process_organizer import CM

# Import debug utilities if available
try:
    from matplotlib_debug_utils import create_debugger
    DEBUG_AVAILABLE = True
except ImportError:
    DEBUG_AVAILABLE = False

class ProcessBrainVisualization(tk.Frame):
    """3D Brain visualization for process monitoring"""

    def __init__(self, parent, process_organizer_get_category_func, enable_debug=False):
        super().__init__(parent, bg='#0a0a0a')
        self.get_category = process_organizer_get_category_func  # Function from process_organizer

        # Load config
        bm_cfg = CM.config.get('user_prefs', {}).get('brain_map', {})

        # State
        self.nodes = []  # {pid, pos, category, name, cmdline, proc_info}
        self.edges = []  # [(pid1, pid2, type), ...] where type = 'parent', 'network', 'ipc'
        self.focused_pid = None
        self.active_group = set()  # PIDs in focus cluster

        # Category mapping to brain regions
        # Maps category string to 3D position and color
        self.region_mapping = {
            " 🧠 MY SCRIPTS": {"name": "Frontal", "pos": np.array([0, 0.6, 0.2]), "color": "#FF6B6B"},
            " 🎨 GPU & MEDIA": {"name": "Occipital", "pos": np.array([0, -0.7, 0.1]), "color": "#95E1D3"},
            " 🌐 WEB & COMMS": {"name": "Temporal", "pos": np.array([0.7, 0, -0.1]), "color": "#F38181"},
            " 🛠️  DEV TOOLS": {"name": "Parietal", "pos": np.array([0, 0.1, 0.7]), "color": "#4ECDC4"},
            " 🐚 TERMINALS": {"name": "Motor", "pos": np.array([-0.7, 0.3, 0.3]), "color": "#AA96DA"},
            " ⚙️  SYSTEM / BACKGROUND": {"name": "Cerebellum", "pos": np.array([0, -0.5, -0.6]), "color": "#FFFFD2"}
        }
        
        # Override colors from config if present
        cfg_colors = bm_cfg.get('region_colors', {})
        for cat, color in cfg_colors.items():
            if cat in self.region_mapping:
                self.region_mapping[cat]['color'] = color

        # UI controls
        self.auto_rotate = tk.BooleanVar(value=bm_cfg.get("auto_rotate", False))
        self.show_edges = tk.BooleanVar(value=bm_cfg.get("show_edges", True))
        self.show_labels = tk.BooleanVar(value=bm_cfg.get("show_labels", True))
        self.show_debug = tk.BooleanVar(value=bm_cfg.get("enable_debug", enable_debug))
        self.frozen = tk.BooleanVar(value=bm_cfg.get("start_frozen", True))
        self.live_comms = tk.BooleanVar(value=bm_cfg.get("live_comms", False))
        self.high_perf = tk.BooleanVar(value=bm_cfg.get("high_perf_mode", False))
        self.resource_level = tk.IntVar(value=bm_cfg.get("resource_level", 50))
        self.fps_target = tk.IntVar(value=bm_cfg.get("fps_target", 30))
        self.refresh_rate = tk.DoubleVar(value=bm_cfg.get("update_interval_ms", 2000) / 1000.0)

        # Camera state
        self.camera_azim = 45
        self.camera_elev = 20
        self.camera_dist = 10  # Zoom factor
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        
        self.mouse_pressed = False
        self.mouse_button = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        # Interaction Config
        self.sensitivity = tk.DoubleVar(value=bm_cfg.get("sensitivity", 0.5))
        self.zoom_speed = tk.DoubleVar(value=bm_cfg.get("zoom_speed", 1.0))
        self.pan_speed = tk.DoubleVar(value=bm_cfg.get("pan_speed", 0.01))

        # Setup UI
        self.setup_ui()

        # Setup debugger if enabled and available
        self.debugger = None
        if enable_debug and DEBUG_AVAILABLE:
            bv_logger = get_logger("brain_viz")
            self.debugger = create_debugger(self.fig, self.ax, logger=bv_logger, show_overlay=True)
            self.debugger.set_fps_expectation(self.fps_target.get())
            bv_logger.info("Brain visualization debugger enabled")

        # Initial data fetch to ensure we have context even if starting frozen
        self.refresh_process_data()

        # Start update loop
        self.update_visualization()

    def setup_ui(self):
        """Setup the matplotlib 3D visualization"""
        # Row 1: Primary Toggles
        ctrl_frame = tk.Frame(self, bg='#1a1a1a')
        ctrl_frame.pack(fill=tk.X, side=tk.TOP, padx=5, pady=2)

        ttk.Checkbutton(ctrl_frame, text="Auto-Rotate", variable=self.auto_rotate).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ctrl_frame, text="Freeze State", variable=self.frozen).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ctrl_frame, text="Live Comms", variable=self.live_comms).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ctrl_frame, text="Show Edges", variable=self.show_edges).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(ctrl_frame, text="Show Labels", variable=self.show_labels).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl_frame, text="Refresh", command=self.refresh_process_data).pack(side=tk.LEFT, padx=5)

        # Add traces for immediate feedback
        self.auto_rotate.trace_add("write", lambda *a: self.render(force_redraw=False))
        self.frozen.trace_add("write", lambda *a: self.on_freeze_change())
        self.live_comms.trace_add("write", lambda *a: self.render(force_redraw=True))
        self.show_edges.trace_add("write", lambda *a: self.render(force_redraw=True))
        self.show_labels.trace_add("write", lambda *a: self.render(force_redraw=True))

        # Row 2: Advanced Controls (Perf/Resource/Sensitivity)
        ctrl_frame2 = tk.Frame(self, bg='#1a1a1a')
        ctrl_frame2.pack(fill=tk.X, side=tk.TOP, padx=5, pady=2)

        ttk.Label(ctrl_frame2, text="Level:", background='#1a1a1a', foreground='white').pack(side=tk.LEFT, padx=(5, 2))
        res_scale = tk.Scale(ctrl_frame2, from_=1, to=100, orient=tk.HORIZONTAL, variable=self.resource_level, 
                             showvalue=True, background='#1a1a1a', foreground='white', highlightthickness=0, length=100)
        res_scale.pack(side=tk.LEFT, padx=2)
        self.resource_level.trace_add("write", lambda *a: self.on_resource_change())

        ttk.Checkbutton(ctrl_frame2, text="High Perf", variable=self.high_perf).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(ctrl_frame2, text="FPS:", background='#1a1a1a', foreground='white').pack(side=tk.LEFT, padx=(10, 2))
        fps_scale = tk.Scale(ctrl_frame2, from_=1, to=60, orient=tk.HORIZONTAL, variable=self.fps_target, 
                             showvalue=True, background='#1a1a1a', foreground='white', highlightthickness=0, length=80)
        fps_scale.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl_frame2, text="Sens:", background='#1a1a1a', foreground='white').pack(side=tk.LEFT, padx=(10, 2))
        sens_scale = tk.Scale(ctrl_frame2, from_=0.1, to=2.0, resolution=0.1, orient=tk.HORIZONTAL, 
                                 variable=self.sensitivity, showvalue=True, background='#1a1a1a', 
                                 foreground='white', highlightthickness=0, length=80)
        sens_scale.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl_frame2, text="Zoom:", background='#1a1a1a', foreground='white').pack(side=tk.LEFT, padx=(10, 2))
        zoom_scale = tk.Scale(ctrl_frame2, from_=0.1, to=5.0, resolution=0.1, orient=tk.HORIZONTAL, 
                                 variable=self.zoom_speed, showvalue=True, background='#1a1a1a', 
                                 foreground='white', highlightthickness=0, length=80)
        zoom_scale.pack(side=tk.LEFT, padx=2)

        ttk.Label(ctrl_frame2, text="Pan:", background='#1a1a1a', foreground='white').pack(side=tk.LEFT, padx=(10, 2))
        pan_scale = tk.Scale(ctrl_frame2, from_=0.001, to=0.1, resolution=0.001, orient=tk.HORIZONTAL, 
                                 variable=self.pan_speed, showvalue=True, background='#1a1a1a', 
                                 foreground='white', highlightthickness=0, length=80)
        pan_scale.pack(side=tk.LEFT, padx=2)

        # Debug controls (if available)
        if DEBUG_AVAILABLE:
            ttk.Checkbutton(ctrl_frame, text="Debug Overlay", variable=self.show_debug,
                          command=self.toggle_debug).pack(side=tk.LEFT, padx=5)
            ttk.Button(ctrl_frame, text="Diagnose", command=self.run_diagnostics).pack(side=tk.LEFT, padx=5)

        # matplotlib figure
        self.fig = plt.Figure(figsize=(8, 6), facecolor='#0a0a0a')
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_facecolor('#0a0a0a')
        
        # Disable default matplotlib keyboard/mouse handlers to prevent confusion
        try:
            self.fig.canvas.mpl_disconnect(self.fig.canvas.manager.key_press_handler_id)
            self.fig.canvas.mpl_disconnect(self.fig.canvas.manager.button_press_handler_id)
        except:
            pass

        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        # Mouse interaction
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_motion)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)

    def on_scroll(self, event):
        """Handle mouse wheel for zooming with configurable speed"""
        speed = self.zoom_speed.get()
        if event.button == 'up':
            self.camera_dist = max(1, self.camera_dist - speed)
        elif event.button == 'down':
            self.camera_dist = min(100, self.camera_dist + speed)
        
        self.apply_view_limits()
        self.needs_render = True

    def apply_view_limits(self):
        """Apply zoom and pan offsets to axes with Z-panning support"""
        scale = self.camera_dist / 10.0
        # Expand panning to feel more 3D
        self.ax.set_xlim(-scale + self.pan_offset_x, scale + self.pan_offset_x)
        self.ax.set_ylim(-scale + self.pan_offset_y, scale + self.pan_offset_y)
        self.ax.set_zlim(-scale, scale)

    def on_mouse_press(self, event):
        """Handle mouse press for rotation/panning"""
        if event.inaxes == self.ax:
            self.mouse_pressed = True
            self.mouse_button = event.button
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

    def on_mouse_motion(self, event):
        """Handle mouse drag for rotation (Left) and panning (Right)"""
        if self.mouse_pressed and event.inaxes == self.ax:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            if self.mouse_button == 1: # Left Click: Rotate
                sens = self.sensitivity.get()
                self.camera_azim += dx * sens
                self.camera_elev -= dy * sens
                self.camera_elev = np.clip(self.camera_elev, -90, 90)
            
            elif self.mouse_button == 3: # Right Click: Pan (View-Relative)
                pan_sens = self.pan_speed.get()
                
                # Calculate movement vectors relative to current azim/elev
                # This creates the 'moving through data space' feel
                phi = np.radians(self.camera_azim)
                theta = np.radians(self.camera_elev)
                
                # Right/Left movement (orthogonal to view vector and Up)
                self.pan_offset_x -= (dx * np.cos(phi)) * pan_sens
                self.pan_offset_y -= (dx * np.sin(phi)) * pan_sens
                
                # Up/Down movement (relative to current elevation)
                self.pan_offset_x += (dy * np.sin(phi) * np.sin(theta)) * pan_sens
                self.pan_offset_y -= (dy * np.cos(phi) * np.sin(theta)) * pan_sens

                self.apply_view_limits()

            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.needs_render = True

    def on_mouse_release(self, event):
        self.mouse_pressed = False
        self.mouse_button = None


    def refresh_process_data(self):
        """Scan running processes and build node/edge graph"""
        self.nodes = []
        pid_to_node = {}

        # Build nodes from running processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
            try:
                pid = proc.info['pid']
                category, color, priority = self.get_category(proc)

                # Get region data
                if category not in self.region_mapping:
                    category = " ⚙️  SYSTEM / BACKGROUND"

                region = self.region_mapping[category]

                # Position: region center + small random offset
                base_pos = region['pos']
                offset = np.random.uniform(-0.15, 0.15, 3)
                pos = base_pos + offset

                # Node size based on CPU usage
                size = 30 + proc.info['cpu_percent'] * 5
                size = min(size, 200)  # clamp

                node = {
                    'pid': pid,
                    'pos': pos,
                    'category': category,
                    'name': proc.info['name'],
                    'cmdline': ' '.join(proc.info['cmdline'] or []),
                    'color': region['color'],
                    'size': size,
                    'proc': proc
                }

                self.nodes.append(node)
                pid_to_node[pid] = node

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Build edges (parent-child relationships)
        self.edges = []
        for node in self.nodes:
            try:
                proc = node['proc']
                parent = proc.parent()
                if parent and parent.pid in pid_to_node:
                    self.edges.append((node['pid'], parent.pid, 'parent'))
            except:
                pass

        # Detect network connections between processes
        self.detect_network_edges(pid_to_node)
        
        # Trigger immediate render
        self.needs_render = True
        self.force_full_redraw = True

    def detect_network_edges(self, pid_to_node):
        """Detect processes communicating via network sockets"""
        # Map listening ports to PIDs
        listeners = {}  # {port: pid}
        connectors = []  # [(pid, remote_port), ...]

        for node in self.nodes:
            try:
                proc = node['proc']
                conns = proc.connections()
                for conn in conns:
                    if conn.status == 'LISTEN' and conn.laddr:
                        listeners[conn.laddr.port] = node['pid']
                    elif conn.raddr:
                        connectors.append((node['pid'], conn.raddr.port))
            except:
                pass

        # Match connectors to listeners
        for pid, remote_port in connectors:
            if remote_port in listeners and listeners[remote_port] != pid:
                self.edges.append((pid, listeners[remote_port], 'network'))

    def on_resource_change(self):
        """Coordinate FPS and Refresh rate based on Resource Level slider"""
        res = self.resource_level.get()
        # Scale FPS from 10 to 60
        self.fps_target.set(int(10 + (res / 100.0) * 50))
        # Scale Refresh rate from 5.0s down to 0.5s
        self.refresh_rate.set(5.0 - (res / 100.0) * 4.5)
        
        # Coordinate Interaction (Higher resources = faster interaction tracking)
        self.sensitivity.set(0.1 + (res / 100.0) * 0.9)
        self.zoom_speed.set(0.5 + (res / 100.0) * 2.5)
        self.pan_speed.set(0.005 + (res / 100.0) * 0.045)

        # Update debugger expectation
        if hasattr(self, 'debugger') and self.debugger:
            self.debugger.set_fps_expectation(self.fps_target.get())
            
        logging.info(f"Resource Level adjusted to {res}: FPS={self.fps_target.get()}, Refresh={self.refresh_rate.get():.1f}s")

    def render(self, force_redraw=True):
        """Render the 3D brain visualization with performance optimizations"""
        # Start render timing
        if self.debugger:
            self.debugger.start_render()

        # Reset flag
        self.needs_render = False

        # If only camera moved and we have nodes, we can just update the view
        # However, Axes3D usually needs a full draw call for depth sorting.
        # But we only clear if data actually changed or a full refresh is requested.
        if force_redraw:
            self.ax.clear()
            self.ax.set_xlim(-1, 1)
            self.ax.set_ylim(-1, 1)
            self.ax.set_zlim(-1, 1)
            self.ax.set_facecolor('#0a0a0a')
            self.ax.grid(False)
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.ax.set_zticks([])

            # Draw edges first (behind nodes)
            if self.show_edges.get():
                for pid1, pid2, edge_type in self.edges:
                    node1 = next((n for n in self.nodes if n['pid'] == pid1), None)
                    node2 = next((n for n in self.nodes if n['pid'] == pid2), None)

                    if node1 and node2:
                        pos1, pos2 = node1['pos'], node2['pos']
                        color, alpha, lw = ('#555555', 0.3, 0.5) if edge_type == 'parent' else ('#FFD700', 0.8, 1.5)
                        self.ax.plot([pos1[0], pos2[0]], [pos1[1], pos2[1]], [pos1[2], pos2[2]],
                                    color=color, alpha=alpha, linewidth=lw)

            # Draw nodes and regions
            # Marker and antialiasing based on High Perf mode
            marker = '.' if self.high_perf.get() else 'o'
            antialiased = not self.high_perf.get()

            for node in self.nodes:
                p = node['pos']
                ec = '#00FF00' if node['pid'] in self.active_group else 'white'
                lw = 2 if node['pid'] in self.active_group else 0.5
                self.ax.scatter([p[0]], [p[1]], [p[2]], c=node['color'], s=node['size'], 
                              alpha=0.7, edgecolors=ec, linewidths=lw, marker=marker, antialiased=antialiased)

            for cat, reg in self.region_mapping.items():
                p = reg['pos']
                self.ax.scatter([p[0]], [p[1]], [p[2]], c=reg['color'], s=150, alpha=0.6, edgecolors='white')
                if self.show_labels.get():
                    self.ax.text(p[0], p[1], p[2] + 0.1, reg['name'], color='white', fontsize=8, ha='center')

        # Always apply camera view
        self.ax.view_init(elev=self.camera_elev, azim=self.camera_azim)

        # Draw the canvas
        # Use draw_idle to avoid blocking interaction
        self.canvas.draw_idle()

        # End render timing
        if self.debugger:
            self.debugger.end_render()
            if self.show_debug.get():
                self.debugger.create_debug_overlay()

    def update_visualization(self):
        """Auto-update loop (handles data refresh and auto-rotation)"""
        # Delay based on FPS target
        fps = self.fps_target.get()
        delay_ms = int(1000 / fps) if fps > 0 else 33
        
        interval = self.refresh_rate.get()

        # INTERACTION PRIORITY: If user is interacting, skip heavy data updates
        if not self.mouse_pressed:
            # 1. Refresh data periodically
            # If not frozen, refresh EVERYTHING
            if not self.frozen.get():
                if not hasattr(self, '_last_refresh') or (datetime.now() - self._last_refresh).total_seconds() > interval:
                    self.refresh_process_data()
                    self._last_refresh = datetime.now()
                    self.needs_render = True
                    self.force_full_redraw = True
            # If frozen but Live Comms is ON, only refresh network edges
            elif self.live_comms.get():
                if not hasattr(self, '_last_comms_refresh') or (datetime.now() - self._last_comms_refresh).total_seconds() > interval:
                    # We need to rebuild edges (which detects network comms)
                    # This uses the current (possibly frozen) nodes
                    pid_to_node = {n['pid']: n for n in self.nodes}
                    # Update edges list with fresh network data
                    self._refresh_only_network_edges(pid_to_node)
                    self._last_comms_refresh = datetime.now()
                    self.needs_render = True
                    self.force_full_redraw = True

        # 2. Handle auto-rotation
        if self.auto_rotate.get() and not self.mouse_pressed:
            self.camera_azim = (self.camera_azim + 1) % 360
            self.needs_render = True

        # 3. Render if needed
        if self.needs_render:
            self.render(force_redraw=self.force_full_redraw)
            self.force_full_redraw = False
        
        # Schedule next update
        self.after(delay_ms, self.update_visualization)

    def on_freeze_change(self):
        """Handle freeze toggle - refresh data if unfreezing"""
        if not self.frozen.get():
            self.refresh_process_data()
        self.needs_render = True
        self.force_full_redraw = True

    def _refresh_only_network_edges(self, pid_to_node):
        """Specifically refresh network edges while keeping nodes/parent edges frozen"""
        # Filter out old network edges, keep parent edges
        self.edges = [e for e in self.edges if e[2] != 'network']
        # Add fresh network edges
        self.detect_network_edges(pid_to_node)

    def on_mouse_press(self, event):
        """Handle mouse press for rotation"""
        if event.inaxes == self.ax:
            self.mouse_pressed = True
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y

    def on_mouse_motion(self, event):
        """Handle mouse drag for rotation with immediate feedback"""
        if self.mouse_pressed and event.inaxes == self.ax:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y

            sens = self.sensitivity.get()
            self.camera_azim += dx * sens
            self.camera_elev -= dy * sens
            self.camera_elev = np.clip(self.camera_elev, -90, 90)

            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            
            # Set flag for render in main loop
            self.needs_render = True

    def set_focused_pid(self, pid):
        """Set the PID to highlight at center"""
        self.focused_pid = pid

    def set_active_group(self, pid_set):
        """Set group of PIDs to highlight"""
        self.active_group = pid_set

    def toggle_debug(self):
        """Toggle debug overlay"""
        if not self.debugger and DEBUG_AVAILABLE:
            # Create debugger if it doesn't exist
            logger = logging.getLogger("brain_viz")
            self.debugger = create_debugger(self.fig, self.ax, logger=logger, show_overlay=False)

        if self.debugger and not self.show_debug.get():
            # Clear debug overlay
            if hasattr(self.debugger, '_debug_text'):
                self.debugger._debug_text.set_text('')

    def run_diagnostics(self):
        """Run performance diagnostics"""
        if self.debugger:
            self.debugger.diagnose_performance()
            self.debugger.suggest_optimizations()
        else:
            print("Debug mode not enabled. Enable debug overlay first.")


# ─────────────────────────────────────────────────────────────────────────────
# Testing
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simple test with debug enabled
    from process_organizer import get_category

    # Setup logging for test using unified logger
    get_logger("brain_viz_test", console_output=True)

    root = tk.Tk()
    root.title("Process Brain Visualization Test (Debug Mode)")
    root.geometry("1000x700")

    # Create visualization with debug enabled
    viz = ProcessBrainVisualization(root, get_category, enable_debug=True)
    viz.pack(fill=tk.BOTH, expand=True)

    print("\nDebug Mode Enabled!")
    print("- FPS overlay will show in top-left")
    print("- Click 'Diagnose' button for performance analysis")
    print("- Mouse events are logged")
    print("- Check console for debug info\n")

    root.mainloop()
