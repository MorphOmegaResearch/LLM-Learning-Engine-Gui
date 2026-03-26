#!/usr/bin/env python3
"""
Inheritance Dialog - Hybrid Variant Creation
Creates hybrid variants by combining parent variants with cross-type support.

Features:
- Cross-type hybrid creation
- Cross-lineage hybrid support
- Multi-adapter linking
- Lineage unification
- Skill merging
- Stat union computation
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
from datetime import datetime

from Data import config
# Logger import - use inline imports where needed


class InheritanceDialog(tk.Toplevel):
    """
    Dialog for creating hybrid variants through inheritance.

    Supports:
    - Single lineage hybrids (same type)
    - Cross-type hybrids (different types)
    - Cross-lineage hybrids (different base lineages)
    - Multi-adapter hybrids (multiple adapters)
    """

    def __init__(self, parent, root, style, selected_variant: Optional[str] = None):
        """
        Initialize inheritance dialog.

        Args:
            parent: Parent widget
            root: Root application window
            style: Theme/style object
            selected_variant: Optional pre-selected variant
        """
        super().__init__(parent)

        self.root_app = root
        self.style = style
        self.selected_variant = selected_variant

        # Configure window
        self.title("🧬 Create Hybrid Variant")
        self.geometry("900x750")
        self.configure(bg=self.style.get('bg_color', '#1e1e1e'))

        # Modal dialog
        self.transient(parent)
        self.grab_set()

        # Load variant profiles
        self.all_variants = self._load_all_variants()
        self.eligible_variants = self._filter_eligible_variants()

        # Selection state
        self.parent1_var = tk.StringVar()
        self.parent2_var = tk.StringVar()
        self.hybrid_name_var = tk.StringVar()
        self.hybrid_type_var = tk.StringVar()

        # UI components
        self.create_ui()

        # Pre-select if provided
        if selected_variant and selected_variant in [v['variant_id'] for v in self.eligible_variants]:
            self.parent1_var.set(selected_variant)
            self._on_parent1_selected()

        # Center window
        self._center_window()

    def _load_all_variants(self) -> List[Dict[str, Any]]:
        """Load all variant profiles."""
        try:
            profiles = config.list_model_profiles() or []
            return [p for p in profiles if p.get('variant_id')]
        except Exception:
            return []

    def _filter_eligible_variants(self) -> List[Dict[str, Any]]:
        """
        Filter variants eligible for hybrid creation.

        Requirements:
        - Class level >= Skilled (required for hybrid creation)
        - Has valid lineage_id
        - Not already a complex hybrid (optional restriction)
        """
        eligible = []

        for variant in self.all_variants:
            # Check class level requirement
            class_level = variant.get('class_level', 'novice').lower()
            if class_level not in ['skilled', 'adept', 'expert', 'master', 'grand_master']:
                continue

            # Check has lineage
            if not variant.get('lineage_id'):
                continue

            eligible.append(variant)

        return eligible

    def create_ui(self):
        """Create dialog UI."""
        # Main container
        main_frame = tk.Frame(self, bg=self.style.get('bg_color'))
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        self._create_header(main_frame)

        # Parent selection section
        self._create_parent_selection(main_frame)

        # Hybrid configuration section
        self._create_hybrid_config(main_frame)

        # Preview section
        self._create_preview_section(main_frame)

        # Action buttons
        self._create_action_buttons(main_frame)

    def _create_header(self, parent):
        """Create dialog header."""
        header_frame = tk.Frame(parent, bg='#2d2d2d', height=80)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        header_frame.pack_propagate(False)

        # Title
        title_label = tk.Label(
            header_frame,
            text="🧬 Create Hybrid Variant",
            font=("Arial", 18, "bold"),
            bg='#2d2d2d',
            fg='white'
        )
        title_label.pack(side=tk.TOP, pady=(15, 5))

        # Subtitle
        subtitle = "Combine parent variants to create hybrid with merged capabilities"
        subtitle_label = tk.Label(
            header_frame,
            text=subtitle,
            font=("Arial", 10),
            bg='#2d2d2d',
            fg='#888888'
        )
        subtitle_label.pack(side=tk.TOP)

    def _create_parent_selection(self, parent):
        """Create parent selection section."""
        section_frame = tk.LabelFrame(
            parent,
            text="Parent Selection",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 11, "bold"),
            padx=15,
            pady=15
        )
        section_frame.pack(fill=tk.X, pady=(0, 15))

        # Parent 1
        p1_frame = tk.Frame(section_frame, bg=self.style.get('bg_color'))
        p1_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            p1_frame,
            text="Parent 1:",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.parent1_combo = ttk.Combobox(
            p1_frame,
            textvariable=self.parent1_var,
            values=[v['variant_id'] for v in self.eligible_variants],
            state='readonly',
            width=40
        )
        self.parent1_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.parent1_combo.bind('<<ComboboxSelected>>', lambda e: self._on_parent1_selected())

        self.parent1_info_label = tk.Label(
            p1_frame,
            text="",
            bg=self.style.get('bg_color'),
            fg='#888888',
            font=("Arial", 9)
        )
        self.parent1_info_label.pack(side=tk.LEFT, padx=(10, 0))

        # Parent 2
        p2_frame = tk.Frame(section_frame, bg=self.style.get('bg_color'))
        p2_frame.pack(fill=tk.X)

        tk.Label(
            p2_frame,
            text="Parent 2:",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.parent2_combo = ttk.Combobox(
            p2_frame,
            textvariable=self.parent2_var,
            values=[],
            state='readonly',
            width=40
        )
        self.parent2_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.parent2_combo.bind('<<ComboboxSelected>>', lambda e: self._on_parent2_selected())

        self.parent2_info_label = tk.Label(
            p2_frame,
            text="",
            bg=self.style.get('bg_color'),
            fg='#888888',
            font=("Arial", 9)
        )
        self.parent2_info_label.pack(side=tk.LEFT, padx=(10, 0))

    def _create_hybrid_config(self, parent):
        """Create hybrid configuration section."""
        section_frame = tk.LabelFrame(
            parent,
            text="Hybrid Configuration",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 11, "bold"),
            padx=15,
            pady=15
        )
        section_frame.pack(fill=tk.X, pady=(0, 15))

        # Hybrid name
        name_frame = tk.Frame(section_frame, bg=self.style.get('bg_color'))
        name_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            name_frame,
            text="Hybrid Name:",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        name_entry = ttk.Entry(
            name_frame,
            textvariable=self.hybrid_name_var,
            width=50
        )
        name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Hybrid type
        type_frame = tk.Frame(section_frame, bg=self.style.get('bg_color'))
        type_frame.pack(fill=tk.X)

        tk.Label(
            type_frame,
            text="Hybrid Type:",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.hybrid_type_var,
            values=[],
            state='readonly',
            width=40
        )
        self.type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _create_preview_section(self, parent):
        """Create hybrid preview section."""
        section_frame = tk.LabelFrame(
            parent,
            text="Hybrid Preview",
            bg=self.style.get('bg_color'),
            fg='white',
            font=("Arial", 11, "bold"),
            padx=15,
            pady=15
        )
        section_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Preview text area
        preview_frame = tk.Frame(section_frame, bg=self.style.get('bg_color'))
        preview_frame.pack(fill=tk.BOTH, expand=True)

        self.preview_text = tk.Text(
            preview_frame,
            height=12,
            bg='#0a0a0a',
            fg='#cccccc',
            font=("Courier", 9),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(preview_frame, command=self.preview_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_text.config(yscrollcommand=scrollbar.set)

        # Initial preview
        self._update_preview()

    def _create_action_buttons(self, parent):
        """Create action buttons."""
        button_frame = tk.Frame(parent, bg=self.style.get('bg_color'))
        button_frame.pack(fill=tk.X)

        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self.destroy,
            bg='#3d3d3d',
            fg='white',
            font=("Arial", 11),
            padx=20,
            pady=8,
            relief=tk.FLAT,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Create hybrid button
        self.create_btn = tk.Button(
            button_frame,
            text="Create Hybrid",
            command=self._create_hybrid,
            bg='#4CAF50',
            fg='white',
            font=("Arial", 11, "bold"),
            padx=20,
            pady=8,
            relief=tk.FLAT,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.create_btn.pack(side=tk.RIGHT)

    def _on_parent1_selected(self):
        """Handle parent 1 selection."""
        parent1_id = self.parent1_var.get()
        if not parent1_id:
            return

        # Get parent 1 profile
        parent1 = next((v for v in self.eligible_variants if v['variant_id'] == parent1_id), None)
        if not parent1:
            return

        # Update parent 1 info
        p1_type = parent1.get('assigned_type', 'Unknown')
        p1_class = parent1.get('class_level', 'Unknown').capitalize()
        self.parent1_info_label.config(text=f"({p1_type}, {p1_class})")

        # Filter parent 2 options (exclude parent 1)
        parent2_options = [v['variant_id'] for v in self.eligible_variants if v['variant_id'] != parent1_id]
        self.parent2_combo.config(values=parent2_options)

        # Clear parent 2 selection
        self.parent2_var.set('')
        self.parent2_info_label.config(text='')

        self._update_preview()

    def _on_parent2_selected(self):
        """Handle parent 2 selection."""
        parent2_id = self.parent2_var.get()
        if not parent2_id:
            return

        # Get parent 2 profile
        parent2 = next((v for v in self.eligible_variants if v['variant_id'] == parent2_id), None)
        if not parent2:
            return

        # Update parent 2 info
        p2_type = parent2.get('assigned_type', 'Unknown')
        p2_class = parent2.get('class_level', 'Unknown').capitalize()
        self.parent2_info_label.config(text=f"({p2_type}, {p2_class})")

        # Update hybrid type options
        self._update_hybrid_type_options()

        # Generate default hybrid name
        self._generate_hybrid_name()

        # Enable create button
        self.create_btn.config(state=tk.NORMAL)

        self._update_preview()

    def _update_hybrid_type_options(self):
        """Update hybrid type dropdown based on parents."""
        parent1_id = self.parent1_var.get()
        parent2_id = self.parent2_var.get()

        if not (parent1_id and parent2_id):
            return

        parent1 = next((v for v in self.eligible_variants if v['variant_id'] == parent1_id), None)
        parent2 = next((v for v in self.eligible_variants if v['variant_id'] == parent2_id), None)

        if not (parent1 and parent2):
            return

        p1_type = parent1.get('assigned_type', '')
        p2_type = parent2.get('assigned_type', '')

        # Generate hybrid type options
        if p1_type == p2_type:
            # Same type hybrid
            hybrid_types = [p1_type]
        else:
            # Cross-type hybrid
            hybrid_types = [
                f"{p1_type}_{p2_type}",
                f"{p2_type}_{p1_type}",
                p1_type,
                p2_type
            ]

        self.type_combo.config(values=hybrid_types)
        self.hybrid_type_var.set(hybrid_types[0])

    def _generate_hybrid_name(self):
        """Generate default hybrid name."""
        parent1_id = self.parent1_var.get()
        parent2_id = self.parent2_var.get()

        if not (parent1_id and parent2_id):
            return

        # Extract base names (remove version suffixes)
        p1_base = parent1_id.split('_')[0] if '_' in parent1_id else parent1_id.split('-')[0]
        p2_base = parent2_id.split('_')[0] if '_' in parent2_id else parent2_id.split('-')[0]

        # Generate hybrid name
        hybrid_name = f"{p1_base}_{p2_base}_hybrid"
        self.hybrid_name_var.set(hybrid_name)

    def _update_preview(self):
        """Update hybrid preview."""
        self.preview_text.config(state=tk.NORMAL)
        self.preview_text.delete('1.0', tk.END)

        parent1_id = self.parent1_var.get()
        parent2_id = self.parent2_var.get()

        if not parent1_id:
            self.preview_text.insert(tk.END, "Select Parent 1 to begin...\n")
            self.preview_text.config(state=tk.DISABLED)
            return

        if not parent2_id:
            self.preview_text.insert(tk.END, "Select Parent 2 to configure hybrid...\n")
            self.preview_text.config(state=tk.DISABLED)
            return

        # Get parent profiles
        parent1 = next((v for v in self.eligible_variants if v['variant_id'] == parent1_id), None)
        parent2 = next((v for v in self.eligible_variants if v['variant_id'] == parent2_id), None)

        if not (parent1 and parent2):
            self.preview_text.config(state=tk.DISABLED)
            return

        # Generate preview
        preview = self._generate_hybrid_preview(parent1, parent2)
        self.preview_text.insert(tk.END, preview)
        self.preview_text.config(state=tk.DISABLED)

    def _generate_hybrid_preview(self, parent1: Dict, parent2: Dict) -> str:
        """Generate hybrid preview text."""
        lines = []
        lines.append("═" * 70)
        lines.append("HYBRID VARIANT PREVIEW")
        lines.append("═" * 70)
        lines.append("")

        # Basic info
        lines.append(f"Name: {self.hybrid_name_var.get() or '(not set)'}")
        lines.append(f"Type: {self.hybrid_type_var.get() or '(not set)'}")
        lines.append("")

        # Parents
        lines.append("Parents:")
        lines.append(f"  1. {parent1.get('variant_id')} ({parent1.get('assigned_type')}, {parent1.get('class_level', 'unknown').capitalize()})")
        lines.append(f"  2. {parent2.get('variant_id')} ({parent2.get('assigned_type')}, {parent2.get('class_level', 'unknown').capitalize()})")
        lines.append("")

        # Hybrid characteristics
        p1_type = parent1.get('assigned_type', '')
        p2_type = parent2.get('assigned_type', '')
        p1_lineage = parent1.get('lineage_id', '')
        p2_lineage = parent2.get('lineage_id', '')

        lines.append("Hybrid Characteristics:")
        if p1_type != p2_type:
            lines.append("  🧬 Cross-Type Hybrid")
        if p1_lineage != p2_lineage:
            lines.append("  🔗 Cross-Lineage Hybrid")

        # Merged skills
        p1_skills = parent1.get('skills', [])
        p2_skills = parent2.get('skills', [])
        merged_skills = list(set(p1_skills + p2_skills))
        lines.append(f"  📚 Merged Skills: {len(merged_skills)} (from {len(p1_skills)} + {len(p2_skills)})")

        # Class level (uses lower of two parents)
        p1_class_idx = self._get_class_index(parent1.get('class_level', 'novice'))
        p2_class_idx = self._get_class_index(parent2.get('class_level', 'novice'))
        hybrid_class_idx = min(p1_class_idx, p2_class_idx)
        hybrid_class = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master'][hybrid_class_idx]
        lines.append(f"  🎖️  Initial Class: {hybrid_class.capitalize()}")

        lines.append("")
        lines.append("Note: Hybrid will inherit merged capabilities from both parents.")
        lines.append("Stats will be unioned, and skills will be combined.")

        return "\n".join(lines)

    def _get_class_index(self, class_level: str) -> int:
        """Get index of class level."""
        classes = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master']
        try:
            return classes.index(class_level.lower())
        except ValueError:
            return 0

    def _create_hybrid(self):
        """Create hybrid variant."""
        parent1_id = self.parent1_var.get()
        parent2_id = self.parent2_var.get()
        hybrid_name = self.hybrid_name_var.get()
        hybrid_type = self.hybrid_type_var.get()

        # Validation
        if not all([parent1_id, parent2_id, hybrid_name, hybrid_type]):
            messagebox.showerror("Error", "Please fill in all fields", parent=self)
            return

        try:
            # Get parent profiles
            parent1 = next((v for v in self.eligible_variants if v['variant_id'] == parent1_id), None)
            parent2 = next((v for v in self.eligible_variants if v['variant_id'] == parent2_id), None)

            if not (parent1 and parent2):
                raise ValueError("Parent profiles not found")

            # Create hybrid profile
            hybrid_profile = self._merge_parent_profiles(parent1, parent2, hybrid_name, hybrid_type)

            # Save hybrid profile
            profile_path = config._profile_path(hybrid_name)
            with open(profile_path, 'w') as f:
                json.dump(hybrid_profile, f, indent=2)

            # Success message
            messagebox.showinfo(
                "Success",
                f"Hybrid variant '{hybrid_name}' created successfully!\n\n"
                f"Parents: {parent1_id} + {parent2_id}\n"
                f"Type: {hybrid_type}",
                parent=self
            )

            # Close dialog
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create hybrid: {e}", parent=self)

    def _merge_parent_profiles(self, parent1: Dict, parent2: Dict,
                               hybrid_name: str, hybrid_type: str) -> Dict:
        """
        Merge parent profiles into hybrid.

        Merging strategy:
        - Skills: Union of both parents
        - Stats: Union with averaged values
        - Class: Minimum of both parents
        - Lineage: Unified lineage if cross-lineage
        """
        # Start with parent 1 as base
        hybrid = dict(parent1)

        # Update basic info
        hybrid['variant_id'] = hybrid_name
        hybrid['trainee_name'] = hybrid_name
        hybrid['assigned_type'] = hybrid_type

        # Merge skills (union)
        p1_skills = set(parent1.get('skills', []))
        p2_skills = set(parent2.get('skills', []))
        hybrid['skills'] = sorted(list(p1_skills | p2_skills))

        # Class level (minimum of both)
        p1_class_idx = self._get_class_index(parent1.get('class_level', 'novice'))
        p2_class_idx = self._get_class_index(parent2.get('class_level', 'novice'))
        hybrid_class_idx = min(p1_class_idx, p2_class_idx)
        hybrid['class_level'] = ['novice', 'skilled', 'adept', 'expert', 'master', 'grand_master'][hybrid_class_idx]

        # Lineage (create unified lineage for cross-lineage hybrids)
        p1_lineage = parent1.get('lineage_id', '')
        p2_lineage = parent2.get('lineage_id', '')
        if p1_lineage != p2_lineage:
            hybrid['lineage_id'] = f"{p1_lineage}+{p2_lineage}"
            hybrid['lineage_type'] = 'cross_lineage'
        else:
            hybrid['lineage_id'] = p1_lineage
            hybrid['lineage_type'] = 'single_lineage'

        # Add hybrid metadata
        hybrid['hybrid_metadata'] = {
            'parent1': parent1.get('variant_id'),
            'parent2': parent2.get('variant_id'),
            'created_date': datetime.now().isoformat(),
            'hybrid_type': hybrid_type,
            'is_cross_type': parent1.get('assigned_type') != parent2.get('assigned_type'),
            'is_cross_lineage': p1_lineage != p2_lineage
        }

        # Reset XP (hybrid starts fresh)
        hybrid['xp'] = 0

        # Add hybrid badge
        if 'badges' not in hybrid:
            hybrid['badges'] = []
        hybrid['badges'].append('hybrid')

        return hybrid

    def _center_window(self):
        """Center window on screen."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')


# Convenience function
def show_inheritance_dialog(parent, root, style, selected_variant: Optional[str] = None):
    """Show inheritance dialog."""
    dialog = InheritanceDialog(parent, root, style, selected_variant)
    parent.wait_window(dialog)
