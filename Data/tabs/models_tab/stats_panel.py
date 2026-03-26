#!/usr/bin/env python3
"""
Stats Display Panel
Shows hierarchical stats with progressive disclosure based on class level.
Part of Section 0.5 Phase 3 - Stats UI
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional
from pathlib import Path


class StatsPanel(ttk.Frame):
    """
    Stats display panel with progressive disclosure.

    Features:
    - 4-layer hierarchical stats (raw → performance → quality → composite)
    - Class-aware visibility (higher classes see more stats)
    - Promotion gate progress bars
    - Stat history trends (sparklines)
    - Comparison vs class requirements
    """

    def __init__(self, parent, style, variant_id: Optional[str] = None):
        """
        Initialize stats panel.

        Args:
            parent: Parent widget
            style: Style object
            variant_id: Variant to display stats for
        """
        super().__init__(parent, style='Category.TFrame')

        self.style_obj = style
        self.variant_id = variant_id
        self.profile = None
        self.stats = None
        self.class_level = 'novice'

        # Create UI
        self._create_ui()

        # Load stats if variant provided
        if variant_id:
            self.load_variant(variant_id)

    def _create_ui(self):
        """Create stats panel UI."""
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(
            header_frame,
            text="📊 Statistics",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT)

        # Refresh button
        self.refresh_btn = ttk.Button(
            header_frame,
            text="🔄",
            width=3,
            command=self.refresh,
            style='Select.TButton'
        )
        self.refresh_btn.pack(side=tk.RIGHT)

        # Scrollable content
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg='#2b2b2b', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas, style='Category.TFrame')
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind canvas width to frame width
        self.canvas.bind(
            '<Configure>',
            lambda e: self.canvas.itemconfig(
                self.canvas.find_withtag("all")[0],
                width=e.width
            ) if self.canvas.find_withtag("all") else None
        )

    def load_variant(self, variant_id: str):
        """Load variant stats."""
        self.variant_id = variant_id

        try:
            from Data.config import load_model_profile

            self.profile = load_model_profile(variant_id)
            if not self.profile:
                self._show_error("Profile not found")
                return

            self.stats = self.profile.get('stats', {})
            self.class_level = self.profile.get('class_level', 'novice').lower()

            # Render stats
            self._render_stats()

        except Exception as e:
            self._show_error(f"Error loading stats: {e}")

    def _render_stats(self):
        """Render stats display."""
        # Clear existing widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not self.stats:
            ttk.Label(
                self.scrollable_frame,
                text="No stats available",
                style='Config.TLabel'
            ).pack(pady=20)
            return

        # Class info
        class_frame = ttk.Frame(self.scrollable_frame)
        class_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        ttk.Label(
            class_frame,
            text=f"Class: {self.class_level.title()}",
            font=("Arial", 10, "bold"),
            style='Config.TLabel'
        ).pack(side=tk.LEFT)

        # Progressive disclosure based on class level
        layers_to_show = self._get_visible_layers()

        # Render each layer
        for layer in layers_to_show:
            if layer in self.stats:
                self._render_stat_layer(layer, self.stats[layer])

        # Promotion gates progress (if not Grand Master)
        if self.class_level != 'grand_master':
            self._render_promotion_gates()

    def _get_visible_layers(self) -> List[str]:
        """Get stat layers visible to this class level."""
        # Progressive disclosure
        if self.class_level in ['novice']:
            return ['performance']  # Basic stats only
        elif self.class_level in ['skilled', 'adept']:
            return ['performance', 'quality']  # Add quality
        else:  # expert, master, grand_master
            return ['raw_metrics', 'performance', 'quality', 'composite']  # All

    def _render_stat_layer(self, layer_name: str, layer_data: Dict):
        """Render a stat layer."""
        if not layer_data:
            return

        # Layer header
        layer_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text=self._format_layer_name(layer_name),
            style='Config.TLabel'
        )
        layer_frame.pack(fill=tk.X, padx=10, pady=5)

        # Render stats in this layer
        for stat_name, stat_value in layer_data.items():
            self._render_stat_row(layer_frame, stat_name, stat_value)

    def _render_stat_row(self, parent, stat_name: str, stat_value: Any):
        """Render a single stat row."""
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, padx=10, pady=2)

        # Stat name
        name_label = ttk.Label(
            row_frame,
            text=self._format_stat_name(stat_name),
            style='Config.TLabel',
            width=20,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT)

        # Stat value/progress
        if isinstance(stat_value, dict):
            # Has value and grade
            value = stat_value.get('value', 0)
            grade = stat_value.get('grade', 'F')

            # Value label
            value_label = ttk.Label(
                row_frame,
                text=f"{value:.2f}" if isinstance(value, float) else str(value),
                style='Config.TLabel',
                width=10
            )
            value_label.pack(side=tk.LEFT, padx=(5, 5))

            # Grade badge
            grade_color = self._grade_to_color(grade)
            grade_label = tk.Label(
                row_frame,
                text=grade,
                bg=grade_color,
                fg='white',
                font=("Arial", 9, "bold"),
                width=4,
                relief=tk.FLAT
            )
            grade_label.pack(side=tk.LEFT, padx=(0, 5))

            # Progress bar (0-100%)
            value_percent = min(100, max(0, value * 100)) if isinstance(value, float) else 0
            self._render_progress_bar(row_frame, value_percent)

        else:
            # Simple value
            value_label = ttk.Label(
                row_frame,
                text=str(stat_value),
                style='Config.TLabel'
            )
            value_label.pack(side=tk.LEFT)

    def _render_progress_bar(self, parent, percent: float):
        """Render a progress bar."""
        bar_frame = tk.Frame(parent, bg='#1a1a1a', height=16, width=150)
        bar_frame.pack(side=tk.LEFT, padx=(5, 0))
        bar_frame.pack_propagate(False)

        # Fill bar
        fill_width = int(150 * percent / 100)
        fill_color = self._percent_to_color(percent)

        fill_bar = tk.Frame(bar_frame, bg=fill_color, height=16, width=fill_width)
        fill_bar.place(x=0, y=0)

        # Percentage text
        percent_label = tk.Label(
            bar_frame,
            text=f"{percent:.1f}%",
            bg='#1a1a1a',
            fg='white',
            font=("Arial", 8)
        )
        percent_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def _render_promotion_gates(self):
        """Render promotion gate progress."""
        try:
            from Data.class_progression import check_promotion_eligibility

            eligibility = check_promotion_eligibility(self.variant_id)
            if not eligibility:
                return

            # Gate progress section
            gates_frame = ttk.LabelFrame(
                self.scrollable_frame,
                text=f"🎯 Promotion to {eligibility.get('target_class', '?').title()}",
                style='Config.TLabel'
            )
            gates_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

            # Overall eligibility
            eligible = eligibility.get('eligible', False)
            status_color = '#4CAF50' if eligible else '#f44336'
            status_text = "✅ Eligible" if eligible else "❌ Not Eligible"

            status_label = tk.Label(
                gates_frame,
                text=status_text,
                bg=status_color,
                fg='white',
                font=("Arial", 10, "bold"),
                padx=10,
                pady=5
            )
            status_label.pack(pady=(5, 10))

            # Stat gate progress
            stat_gate_progress = eligibility.get('stat_gate_progress', 0)
            passed_gates = eligibility.get('passed_gates', [])
            total_gates = eligibility.get('total_gates', 0)

            gate_row = ttk.Frame(gates_frame)
            gate_row.pack(fill=tk.X, padx=10, pady=(0, 10))

            ttk.Label(
                gate_row,
                text=f"Stat Gates: {len(passed_gates)}/{total_gates}",
                style='Config.TLabel',
                width=25
            ).pack(side=tk.LEFT)

            self._render_progress_bar(gate_row, stat_gate_progress * 100)

            # Blockers
            blockers = eligibility.get('blockers', [])
            if blockers:
                blockers_frame = ttk.Frame(gates_frame)
                blockers_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

                ttk.Label(
                    blockers_frame,
                    text="Blockers:",
                    font=("Arial", 9, "bold"),
                    style='Config.TLabel'
                ).pack(anchor=tk.W)

                for blocker in blockers[:5]:  # Show max 5
                    ttk.Label(
                        blockers_frame,
                        text=f"  • {blocker}",
                        style='Config.TLabel',
                        wraplength=300
                    ).pack(anchor=tk.W, padx=(10, 0))

        except Exception as e:
            pass  # Silently fail if promotion check unavailable

    def _format_layer_name(self, layer_name: str) -> str:
        """Format layer name for display."""
        names = {
            'raw_metrics': '📈 Raw Metrics',
            'performance': '⚡ Performance',
            'quality': '✨ Quality',
            'composite': '🎯 Composite'
        }
        return names.get(layer_name, layer_name.replace('_', ' ').title())

    def _format_stat_name(self, stat_name: str) -> str:
        """Format stat name for display."""
        return stat_name.replace('_', ' ').title()

    def _grade_to_color(self, grade: str) -> str:
        """Convert grade to color."""
        colors = {
            'AAA': '#4CAF50',
            'AA': '#8BC34A',
            'A': '#CDDC39',
            'B': '#FFC107',
            'C': '#FF9800',
            'D': '#FF5722',
            'F': '#f44336'
        }
        return colors.get(grade, '#757575')

    def _percent_to_color(self, percent: float) -> str:
        """Convert percentage to color."""
        if percent >= 90:
            return '#4CAF50'
        elif percent >= 75:
            return '#8BC34A'
        elif percent >= 60:
            return '#FFC107'
        elif percent >= 40:
            return '#FF9800'
        else:
            return '#f44336'

    def _show_error(self, message: str):
        """Show error message."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        ttk.Label(
            self.scrollable_frame,
            text=f"Error: {message}",
            style='Config.TLabel',
            foreground='red'
        ).pack(pady=20)

    def refresh(self):
        """Refresh stats display."""
        if self.variant_id:
            self.load_variant(self.variant_id)


def create_stats_panel(parent, style, variant_id: Optional[str] = None) -> StatsPanel:
    """Create and return a stats panel."""
    return StatsPanel(parent, style, variant_id)
