#!/usr/bin/env python3
"""
RAG Network Visualization
Interactive neural network-style visualization of knowledge graphs.
Part of Section 6 - Collections RAG Network Viz
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import math


class RAGNetworkViz(tk.Toplevel):
    """
    RAG Network Visualization window.

    Features:
    - 2D neural network rendering
    - Interactive zoom/pan
    - Node clicking for details
    - Topic filtering
    - Color-coded clusters
    """

    def __init__(self, parent, project_path: Path, style):
        """
        Initialize visualization window.

        Args:
            parent: Parent widget
            project_path: Path to project
            style: Style object
        """
        super().__init__(parent)

        self.project_path = project_path
        self.style_obj = style

        # Window setup
        self.title(f"🧠 Knowledge Network - {project_path.name}")
        self.geometry("1000x700")
        self.configure(bg='#1a1a1a')

        # Graph data
        self.graph_data = None
        self.node_positions = {}
        self.selected_node = None

        # View state
        self.zoom_level = 1.0
        self.pan_offset = [0, 0]
        self.is_panning = False
        self.pan_start = None

        # Create UI
        self._create_ui()

        # Load and render graph
        self._load_graph()

    def _create_ui(self):
        """Create visualization UI."""
        # Toolbar
        toolbar = tk.Frame(self, bg='#2d2d2d', height=50)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        # Zoom controls
        tk.Label(toolbar, text="Zoom:", bg='#2d2d2d', fg='white').pack(side=tk.LEFT, padx=(10, 5))

        tk.Button(
            toolbar,
            text="+",
            command=lambda: self._zoom(1.2),
            bg='#3d3d3d',
            fg='white',
            width=3
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            toolbar,
            text="-",
            command=lambda: self._zoom(0.8),
            bg='#3d3d3d',
            fg='white',
            width=3
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            toolbar,
            text="Reset",
            command=self._reset_view,
            bg='#3d3d3d',
            fg='white'
        ).pack(side=tk.LEFT, padx=(2, 20))

        # Refresh button
        tk.Button(
            toolbar,
            text="🔄 Refresh",
            command=self._load_graph,
            bg='#3d3d3d',
            fg='white'
        ).pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_label = tk.Label(
            toolbar,
            text="Loading...",
            bg='#2d2d2d',
            fg='#888888'
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # Main content area
        content_frame = tk.Frame(self, bg='#1a1a1a')
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for graph
        self.canvas = tk.Canvas(
            content_frame,
            bg='#0a0a0a',
            highlightthickness=0
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Detail panel
        detail_panel = tk.Frame(content_frame, bg='#2d2d2d', width=250)
        detail_panel.pack(side=tk.RIGHT, fill=tk.Y)
        detail_panel.pack_propagate(False)

        tk.Label(
            detail_panel,
            text="Node Details",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 11, "bold")
        ).pack(pady=(10, 5))

        self.detail_text = tk.Text(
            detail_panel,
            bg='#1a1a1a',
            fg='#cccccc',
            font=("Courier", 9),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    def _load_graph(self):
        """Load and build knowledge graph."""
        try:
            from Data.tabs.collections_tab.graph_builder import build_knowledge_graph

            self.status_label.config(text="Building graph...")
            self.update()

            # Build graph
            self.graph_data = build_knowledge_graph(self.project_path)

            # Calculate layout
            if self.graph_data['nodes']:
                from Data.tabs.collections_tab.graph_builder import KnowledgeGraphBuilder

                builder = KnowledgeGraphBuilder(self.project_path)
                self.node_positions = builder.calculate_layout(
                    self.graph_data['nodes'],
                    self.graph_data['edges'],
                    int(self.canvas.winfo_width() * 0.9),
                    int(self.canvas.winfo_height() * 0.9)
                )

            # Render
            self._render_graph()

            # Update status
            stats = self.graph_data.get('stats', {})
            self.status_label.config(
                text=f"Nodes: {stats.get('total_nodes', 0)} | "
                     f"Edges: {stats.get('total_edges', 0)} | "
                     f"Clusters: {stats.get('total_clusters', 0)}"
            )

        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)[:50]}")

    def _render_graph(self):
        """Render graph on canvas."""
        self.canvas.delete("all")

        if not self.graph_data or not self.graph_data['nodes']:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2,
                self.canvas.winfo_height() / 2,
                text="No knowledge graph data available",
                fill='white',
                font=("Arial", 12)
            )
            return

        # Draw edges first (so they appear behind nodes)
        self._draw_edges()

        # Draw nodes
        self._draw_nodes()

    def _draw_edges(self):
        """Draw graph edges."""
        for source_id, target_id, weight in self.graph_data['edges']:
            if source_id in self.node_positions and target_id in self.node_positions:
                x1, y1 = self._transform_point(*self.node_positions[source_id])
                x2, y2 = self._transform_point(*self.node_positions[target_id])

                # Edge thickness based on weight
                width = max(1, int(weight * 5))

                # Edge color based on weight
                color_intensity = int(weight * 255)
                color = f'#{color_intensity:02x}{color_intensity:02x}{color_intensity:02x}'

                self.canvas.create_line(
                    x1, y1, x2, y2,
                    fill=color,
                    width=width,
                    tags="edge"
                )

    def _draw_nodes(self):
        """Draw graph nodes."""
        for node in self.graph_data['nodes']:
            node_id = node['id']
            if node_id not in self.node_positions:
                continue

            x, y = self._transform_point(*self.node_positions[node_id])

            # Node size based on knowledge volume
            base_size = 8
            size = base_size + math.log(node.get('size', 100) + 1) * 2

            # Node color based on tier
            tier = node.get('tier', 0)
            colors = ['#4CAF50', '#2196F3', '#FF9800', '#f44336']
            color = colors[min(tier, 3)]

            # Draw node circle
            self.canvas.create_oval(
                x - size, y - size,
                x + size, y + size,
                fill=color,
                outline='white',
                width=2 if node_id == self.selected_node else 1,
                tags=("node", node_id)
            )

            # Node label (show on hover or if selected)
            if node_id == self.selected_node:
                label = node.get('label', node_id)[:20]
                self.canvas.create_text(
                    x, y - size - 10,
                    text=label,
                    fill='white',
                    font=("Arial", 8),
                    tags=("label", node_id)
                )

        # Bind click to nodes
        self.canvas.tag_bind("node", "<Button-1>", self._on_node_click)

    def _on_node_click(self, event):
        """Handle node click."""
        # Get clicked node
        item = self.canvas.find_closest(event.x, event.y)
        tags = self.canvas.gettags(item)

        for tag in tags:
            if tag.startswith('node_'):
                self.selected_node = tag
                self._show_node_details(tag)
                self._render_graph()  # Redraw to highlight
                break

    def _show_node_details(self, node_id: str):
        """Show details for selected node."""
        # Find node data
        node = next((n for n in self.graph_data['nodes'] if n['id'] == node_id), None)
        if not node:
            return

        # Update detail panel
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete('1.0', tk.END)

        details = f"""Node: {node['id']}
Label: {node.get('label', 'N/A')}
Type: {node.get('type', 'N/A')}
Tier: {node.get('tier', 0)}
Size: {node.get('size', 0)} bytes

Topics:
"""
        for topic in node.get('topics', []):
            details += f"  • {topic}\n"

        details += f"\nSource:\n{node.get('source', 'N/A')}"

        self.detail_text.insert('1.0', details)
        self.detail_text.config(state=tk.DISABLED)

    def _transform_point(self, x: float, y: float) -> Tuple[float, float]:
        """Transform point with zoom and pan."""
        # Apply zoom
        x *= self.zoom_level
        y *= self.zoom_level

        # Apply pan
        x += self.pan_offset[0]
        y += self.pan_offset[1]

        return (x, y)

    def _zoom(self, factor: float):
        """Zoom in/out."""
        self.zoom_level *= factor
        self.zoom_level = max(0.1, min(5.0, self.zoom_level))
        self._render_graph()

    def _reset_view(self):
        """Reset view to default."""
        self.zoom_level = 1.0
        self.pan_offset = [0, 0]
        self._render_graph()

    def _on_canvas_click(self, event):
        """Handle canvas click for panning."""
        self.is_panning = True
        self.pan_start = (event.x, event.y)

    def _on_canvas_drag(self, event):
        """Handle canvas drag."""
        if self.is_panning and self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]

            self.pan_offset[0] += dx
            self.pan_offset[1] += dy

            self.pan_start = (event.x, event.y)
            self._render_graph()

    def _on_canvas_release(self, event):
        """Handle canvas release."""
        self.is_panning = False
        self.pan_start = None

    def _on_mouse_wheel(self, event):
        """Handle mouse wheel zoom."""
        if event.delta > 0:
            self._zoom(1.1)
        else:
            self._zoom(0.9)

    def _on_canvas_resize(self, event):
        """Handle canvas resize."""
        if self.graph_data and self.graph_data['nodes']:
            self._render_graph()


def show_rag_network_viz(parent, project_path: Path, style):
    """Show RAG network visualization window."""
    viz = RAGNetworkViz(parent, project_path, style)
    return viz
