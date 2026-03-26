#!/usr/bin/env python3
"""
Brain-Mapped System Visualizer
Maps system components to anatomical brain regions with live activity visualization.

Concept: The entire LLM training system represented as a living brain, with:
- Models as "consciousness kernels" in the center
- Components mapped to brain regions (frontal, parietal, temporal, occipital, motor, sensory)
- Neural pathways lighting up based on activity
- Real-time pulse effects during operations
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import math
import time


class BrainRegion:
    """Represents a brain region with associated system components."""

    def __init__(self, name: str, position: Tuple[float, float],
                 radius: float, color: str, components: List[str]):
        """
        Initialize brain region.

        Args:
            name: Region name (e.g., "Frontal Lobe")
            position: (x, y) center position (0-1 normalized)
            radius: Region radius (0-1 normalized)
            color: Base color for region
            components: List of system components in this region
        """
        self.name = name
        self.position = position
        self.radius = radius
        self.base_color = color
        self.components = components
        self.activity_level = 0.0  # 0-1
        self.recent_activity = []  # List of recent activities

    def get_current_color(self) -> str:
        """Get color based on activity level."""
        if self.activity_level == 0:
            return self.base_color

        # Blend with white based on activity
        base = self._hex_to_rgb(self.base_color)
        white = (255, 255, 255)

        blend = tuple(
            int(base[i] + (white[i] - base[i]) * self.activity_level)
            for i in range(3)
        )

        return f'#{blend[0]:02x}{blend[1]:02x}{blend[2]:02x}'

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class NeuralPathway:
    """Represents a connection between brain regions."""

    def __init__(self, source: BrainRegion, target: BrainRegion,
                 weight: float = 1.0):
        """
        Initialize neural pathway.

        Args:
            source: Source brain region
            target: Target brain region
            weight: Connection strength (0-1)
        """
        self.source = source
        self.target = target
        self.weight = weight
        self.pulse_active = False
        self.pulse_position = 0.0  # 0-1 along pathway


class BrainMapVisualizer(tk.Toplevel):
    """
    Main brain map visualization window.

    Shows the system as a living brain with:
    - Anatomical regions for different system components
    - Central kernel (selected model)
    - Neural pathways that pulse during activity
    - Color-coded health states
    """

    def __init__(self, parent, style, root_app):
        """Initialize brain map visualizer."""
        super().__init__(parent)

        self.style_obj = style
        self.root_app = root_app

        # Window setup
        self.title("🧠 System Brain Map")
        self.geometry("1200x800")
        self.configure(bg='#0a0a0a')

        # State
        self.selected_model = None
        self.regions = {}
        self.pathways = []
        self.kernel_active = False
        self.animation_running = False

        # Create UI
        self._create_ui()

        # Initialize brain regions
        self._initialize_brain_regions()

        # Start animation loop
        self._start_animation()

    def _create_ui(self):
        """Create visualization UI."""
        # Header
        header = tk.Frame(self, bg='#1a1a1a', height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🧠 Living System Brain Map",
            font=("Arial", 18, "bold"),
            bg='#1a1a1a',
            fg='white'
        ).pack(side=tk.LEFT, padx=20, pady=10)

        # Model selector button
        self.model_btn = tk.Button(
            header,
            text="Select Model to Activate",
            command=self._open_model_selector,
            bg='#4CAF50',
            fg='white',
            font=("Arial", 11, "bold"),
            padx=15,
            pady=8,
            relief=tk.FLAT,
            cursor='hand2'
        )
        self.model_btn.pack(side=tk.RIGHT, padx=20)

        # Main content
        content = tk.Frame(self, bg='#0a0a0a')
        content.pack(fill=tk.BOTH, expand=True)

        # Canvas for brain visualization
        self.canvas = tk.Canvas(
            content,
            bg='#0a0a0a',
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Info panel (right side)
        info_panel = tk.Frame(content, bg='#1a1a1a', width=300)
        info_panel.pack(side=tk.RIGHT, fill=tk.Y)
        info_panel.pack_propagate(False)

        tk.Label(
            info_panel,
            text="System Status",
            font=("Arial", 12, "bold"),
            bg='#1a1a1a',
            fg='white'
        ).pack(pady=(15, 10))

        # Model info display
        self.model_info_frame = tk.Frame(info_panel, bg='#1a1a1a')
        self.model_info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self._show_no_model_info()

        # Activity log
        tk.Label(
            info_panel,
            text="Recent Activity",
            font=("Arial", 10, "bold"),
            bg='#1a1a1a',
            fg='white'
        ).pack(pady=(10, 5))

        self.activity_log = tk.Text(
            info_panel,
            bg='#0a0a0a',
            fg='#00ff00',
            font=("Courier", 8),
            height=15,
            wrap=tk.WORD,
            relief=tk.FLAT
        )
        self.activity_log.pack(fill=tk.BOTH, padx=10, pady=5)

        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

    def _initialize_brain_regions(self):
        """Initialize anatomical brain regions with system components."""
        # Frontal Lobe (Planning/Execution) - Top Left
        self.regions['frontal'] = BrainRegion(
            name="Frontal Lobe\n(Planning)",
            position=(0.25, 0.20),
            radius=0.15,
            color='#FF6B6B',
            components=[
                'planner_agents',
                'orchestrator',
                'task_management',
                'moe_coordinator',
                'background_tasks'
            ]
        )

        # Parietal Lobe (Processing/Integration) - Top Center
        self.regions['parietal'] = BrainRegion(
            name="Parietal Lobe\n(Processing)",
            position=(0.50, 0.15),
            radius=0.12,
            color='#4ECDC4',
            components=[
                'stat_computation',
                'xp_calculator',
                'evolution_manager',
                'class_progression',
                'grade_computation'
            ]
        )

        # Occipital Lobe (Visual) - Top Right
        self.regions['occipital'] = BrainRegion(
            name="Occipital Lobe\n(Visual)",
            position=(0.75, 0.20),
            radius=0.12,
            color='#95E1D3',
            components=[
                'gui_rendering',
                'stats_visualization',
                'network_graphs',
                'brain_map_viz',
                'progress_bars'
            ]
        )

        # Temporal Lobe (Memory/Knowledge) - Middle Left
        self.regions['temporal'] = BrainRegion(
            name="Temporal Lobe\n(Memory)",
            position=(0.20, 0.50),
            radius=0.14,
            color='#F38181',
            components=[
                'rag_embeddings',
                'knowledge_bank',
                'training_data',
                'chat_history',
                'project_memory'
            ]
        )

        # Motor Cortex (Actions/Tools) - Middle Right
        self.regions['motor'] = BrainRegion(
            name="Motor Cortex\n(Actions)",
            position=(0.80, 0.50),
            radius=0.13,
            color='#AA96DA',
            components=[
                'file_operations',
                'code_execution',
                'git_operations',
                'build_compile',
                'export_operations'
            ]
        )

        # Sensory Cortex (Inputs) - Bottom Left
        self.regions['sensory'] = BrainRegion(
            name="Sensory Cortex\n(Inputs)",
            position=(0.25, 0.75),
            radius=0.11,
            color='#FCBAD3',
            components=[
                'user_prompts',
                'evaluation_results',
                'debug_logs',
                'system_events',
                'error_detection'
            ]
        )

        # Cerebellum (Coordination) - Bottom Center
        self.regions['cerebellum'] = BrainRegion(
            name="Cerebellum\n(Coordination)",
            position=(0.50, 0.78),
            radius=0.10,
            color='#FFFFD2',
            components=[
                'type_catalog',
                'variant_profiles',
                'skill_detection',
                'conformer_gating'
            ]
        )

        # Corpus Callosum (Inter-region Communication) - Bottom Right
        self.regions['corpus_callosum'] = BrainRegion(
            name="Corpus Callosum\n(Communication)",
            position=(0.75, 0.75),
            radius=0.10,
            color='#A8D8EA',
            components=[
                'config_system',
                'logger_util',
                'event_bus',
                'state_sync'
            ]
        )

        # Create pathways between regions
        self._create_neural_pathways()

    def _create_neural_pathways(self):
        """Create connections between brain regions."""
        # Major pathways
        connections = [
            ('frontal', 'parietal', 0.9),  # Planning → Processing
            ('parietal', 'motor', 0.8),     # Processing → Actions
            ('temporal', 'parietal', 0.9),  # Memory → Processing
            ('sensory', 'parietal', 0.8),   # Input → Processing
            ('frontal', 'motor', 0.7),      # Planning → Actions
            ('temporal', 'frontal', 0.6),   # Memory → Planning
            ('occipital', 'parietal', 0.7), # Visual → Processing
            ('cerebellum', 'motor', 0.8),   # Coordination → Actions
            ('corpus_callosum', 'frontal', 0.5),
            ('corpus_callosum', 'temporal', 0.5),
            ('corpus_callosum', 'motor', 0.5),
        ]

        for source_key, target_key, weight in connections:
            if source_key in self.regions and target_key in self.regions:
                pathway = NeuralPathway(
                    self.regions[source_key],
                    self.regions[target_key],
                    weight
                )
                self.pathways.append(pathway)

    def _render_brain(self):
        """Render the brain visualization."""
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()

        if w < 100 or h < 100:
            return

        # Draw neural pathways first (behind regions)
        for pathway in self.pathways:
            self._draw_pathway(pathway, w, h)

        # Draw brain regions
        for region in self.regions.values():
            self._draw_region(region, w, h)

        # Draw center kernel if model selected
        if self.selected_model:
            self._draw_kernel(w, h)

    def _draw_region(self, region: BrainRegion, canvas_w: int, canvas_h: int):
        """Draw a brain region."""
        x = region.position[0] * canvas_w
        y = region.position[1] * canvas_h
        r = region.radius * min(canvas_w, canvas_h)

        # Glow effect for active regions
        if region.activity_level > 0:
            glow_r = r * (1 + region.activity_level * 0.3)
            glow_alpha = int(region.activity_level * 100)
            self.canvas.create_oval(
                x - glow_r, y - glow_r,
                x + glow_r, y + glow_r,
                fill='',
                outline=region.base_color,
                width=3,
                tags="glow"
            )

        # Main region circle
        color = region.get_current_color()
        self.canvas.create_oval(
            x - r, y - r,
            x + r, y + r,
            fill=color,
            outline='white',
            width=2,
            tags=("region", region.name)
        )

        # Region label
        self.canvas.create_text(
            x, y,
            text=region.name,
            fill='black' if region.activity_level < 0.5 else 'white',
            font=("Arial", 9, "bold"),
            justify=tk.CENTER,
            tags="label"
        )

        # Bind click
        self.canvas.tag_bind(region.name, "<Button-1>",
                            lambda e, r=region: self._on_region_click(r))

    def _draw_pathway(self, pathway: NeuralPathway, canvas_w: int, canvas_h: int):
        """Draw a neural pathway between regions."""
        x1 = pathway.source.position[0] * canvas_w
        y1 = pathway.source.position[1] * canvas_h
        x2 = pathway.target.position[0] * canvas_w
        y2 = pathway.target.position[1] * canvas_h

        # Line thickness based on weight
        width = max(1, int(pathway.weight * 4))

        # Color based on activity
        if pathway.pulse_active:
            color = '#00ff00'
            width += 2
        else:
            color = '#333333'

        self.canvas.create_line(
            x1, y1, x2, y2,
            fill=color,
            width=width,
            tags="pathway"
        )

        # Draw pulse effect
        if pathway.pulse_active:
            # Calculate pulse position
            pulse_x = x1 + (x2 - x1) * pathway.pulse_position
            pulse_y = y1 + (y2 - y1) * pathway.pulse_position

            self.canvas.create_oval(
                pulse_x - 5, pulse_y - 5,
                pulse_x + 5, pulse_y + 5,
                fill='#00ff00',
                outline='white',
                tags="pulse"
            )

    def _draw_kernel(self, canvas_w: int, canvas_h: int):
        """Draw the central kernel (selected model)."""
        cx = 0.50 * canvas_w
        cy = 0.50 * canvas_h

        # Pulsing radius
        base_r = 30
        pulse_factor = 0.1 * math.sin(time.time() * 3)
        r = base_r * (1 + pulse_factor)

        # Outer glow
        for i in range(3):
            glow_r = r + (i + 1) * 10
            alpha = 100 - i * 30
            self.canvas.create_oval(
                cx - glow_r, cy - glow_r,
                cx + glow_r, cy + glow_r,
                fill='',
                outline='#FFD700',
                width=2,
                tags="kernel_glow"
            )

        # Inner core
        self.canvas.create_oval(
            cx - r, cy - r,
            cx + r, cy + r,
            fill='#FFD700',
            outline='white',
            width=3,
            tags="kernel"
        )

        # Model name
        if self.selected_model:
            model_name = self.selected_model.get('variant_id', 'Unknown')[:20]
            self.canvas.create_text(
                cx, cy,
                text=model_name,
                fill='black',
                font=("Arial", 10, "bold"),
                tags="kernel_label"
            )

    def _start_animation(self):
        """Start animation loop."""
        self.animation_running = True
        self._animate()

    def _animate(self):
        """Animation frame update."""
        if not self.animation_running:
            return

        # Update pathway pulses
        for pathway in self.pathways:
            if pathway.pulse_active:
                pathway.pulse_position += 0.05
                if pathway.pulse_position > 1.0:
                    pathway.pulse_active = False
                    pathway.pulse_position = 0.0

        # Decay activity levels
        for region in self.regions.values():
            if region.activity_level > 0:
                region.activity_level *= 0.95

        # Redraw
        self._render_brain()

        # Schedule next frame (60 FPS)
        self.after(16, self._animate)

    def load_model(self, model_data: Dict[str, Any]):
        """Load a model as the central kernel."""
        self.selected_model = model_data
        self.kernel_active = True

        # Update button
        model_name = model_data.get('variant_id', 'Model')
        self.model_btn.config(
            text=f"Active: {model_name[:20]}",
            bg='#2196F3'
        )

        # Show model info
        self._show_model_info(model_data)

        # Activate regions based on model capabilities
        self._activate_regions_for_model(model_data)

        # Log activity
        self._log_activity(f"Model '{model_name}' loaded as kernel")

    def _activate_regions_for_model(self, model_data: Dict[str, Any]):
        """Activate brain regions based on model's capabilities."""
        # Get model stats and features
        assigned_type = model_data.get('assigned_type', '')
        skills = model_data.get('skills', [])
        class_level = model_data.get('class_level', 'novice')

        # Activate frontal if planner/orchestrator type
        if assigned_type in ['planner', 'orchestrator']:
            self.regions['frontal'].activity_level = 0.8
            self._pulse_pathway('frontal', 'parietal')

        # Activate parietal based on class level
        class_activity = {'novice': 0.2, 'skilled': 0.4, 'adept': 0.6,
                         'expert': 0.8, 'master': 0.9, 'grand_master': 1.0}
        self.regions['parietal'].activity_level = class_activity.get(class_level, 0.2)

        # Activate temporal if has skills
        if len(skills) > 0:
            self.regions['temporal'].activity_level = min(1.0, len(skills) / 10)
            self._pulse_pathway('temporal', 'parietal')

        # Activate motor if coder type
        if assigned_type == 'coder':
            self.regions['motor'].activity_level = 0.7
            self._pulse_pathway('parietal', 'motor')

    def _pulse_pathway(self, source_key: str, target_key: str):
        """Trigger pulse animation on pathway."""
        for pathway in self.pathways:
            if (pathway.source == self.regions.get(source_key) and
                pathway.target == self.regions.get(target_key)):
                pathway.pulse_active = True
                pathway.pulse_position = 0.0
                break

    def _show_model_info(self, model_data: Dict[str, Any]):
        """Show model information in info panel."""
        for widget in self.model_info_frame.winfo_children():
            widget.destroy()

        # Model name
        name = model_data.get('variant_id', 'Unknown')
        tk.Label(
            self.model_info_frame,
            text=name,
            font=("Arial", 11, "bold"),
            bg='#1a1a1a',
            fg='#FFD700',
            wraplength=250
        ).pack(anchor=tk.W, pady=(0, 10))

        # Type and class
        model_type = model_data.get('assigned_type', 'Unknown')
        class_level = model_data.get('class_level', 'novice')

        info_text = f"""Type: {model_type}
Class: {class_level.title()}
Skills: {len(model_data.get('skills', []))}

Active Regions:
• Parietal (Processing)
"""

        if model_type in ['planner', 'orchestrator']:
            info_text += "• Frontal (Planning)\n"
        if model_type == 'coder':
            info_text += "• Motor (Actions)\n"
        if len(model_data.get('skills', [])) > 0:
            info_text += "• Temporal (Memory)\n"

        tk.Label(
            self.model_info_frame,
            text=info_text,
            font=("Courier", 9),
            bg='#1a1a1a',
            fg='#cccccc',
            justify=tk.LEFT
        ).pack(anchor=tk.W)

    def _show_no_model_info(self):
        """Show message when no model selected."""
        for widget in self.model_info_frame.winfo_children():
            widget.destroy()

        tk.Label(
            self.model_info_frame,
            text="No Model Selected",
            font=("Arial", 11, "bold"),
            bg='#1a1a1a',
            fg='#888888'
        ).pack(pady=20)

        tk.Label(
            self.model_info_frame,
            text="Select a model from the\nModels Tab to activate\nthe system brain.",
            font=("Arial", 9),
            bg='#1a1a1a',
            fg='#666666',
            justify=tk.CENTER
        ).pack()

    def _log_activity(self, message: str):
        """Log activity to activity panel."""
        timestamp = time.strftime("%H:%M:%S")
        self.activity_log.insert('1.0', f"[{timestamp}] {message}\n")

        # Keep only last 50 lines
        lines = self.activity_log.get('1.0', tk.END).split('\n')
        if len(lines) > 50:
            self.activity_log.delete('50.0', tk.END)

    def _open_model_selector(self):
        """Open model selector dialog."""
        # Import here to avoid circular dependency
        try:
            from Data import config
            profiles = config.list_model_profiles() or []

            if not profiles:
                self._log_activity("No models available")
                return

            # Create simple selector dialog
            selector = tk.Toplevel(self)
            selector.title("Select Model")
            selector.geometry("400x500")
            selector.configure(bg='#1a1a1a')

            tk.Label(
                selector,
                text="Select Model to Activate",
                font=("Arial", 12, "bold"),
                bg='#1a1a1a',
                fg='white'
            ).pack(pady=10)

            # List of models
            listbox_frame = tk.Frame(selector, bg='#1a1a1a')
            listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            scrollbar = tk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            listbox = tk.Listbox(
                listbox_frame,
                bg='#0a0a0a',
                fg='white',
                font=("Courier", 9),
                yscrollcommand=scrollbar.set
            )
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)

            # Populate
            for profile in profiles:
                variant_id = profile.get('variant_id', 'Unknown')
                model_type = profile.get('assigned_type', '?')
                listbox.insert(tk.END, f"{variant_id} ({model_type})")

            def on_select():
                selection = listbox.curselection()
                if selection:
                    idx = selection[0]
                    self.load_model(profiles[idx])
                    selector.destroy()

            tk.Button(
                selector,
                text="Activate",
                command=on_select,
                bg='#4CAF50',
                fg='white',
                font=("Arial", 10, "bold"),
                padx=20,
                pady=8
            ).pack(pady=10)

        except Exception as e:
            self._log_activity(f"Error opening selector: {e}")

    def _on_region_click(self, region: BrainRegion):
        """Handle region click - show components."""
        self._log_activity(f"Clicked: {region.name}")

        # Show region details
        details = f"\n{region.name}\n{'='*30}\n"
        details += "Components:\n"
        for comp in region.components:
            details += f"  • {comp}\n"

        self.activity_log.insert('1.0', details)

    def _on_canvas_resize(self, event):
        """Handle canvas resize."""
        self._render_brain()

    def _on_canvas_click(self, event):
        """Handle canvas click."""
        pass  # Handled by region bindings


def show_brain_map(parent, style, root_app):
    """Show brain map visualizer."""
    brain_map = BrainMapVisualizer(parent, style, root_app)
    return brain_map
