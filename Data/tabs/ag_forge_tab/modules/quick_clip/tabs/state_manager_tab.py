import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import json
import datetime
import shutil
import uuid

class StateManagerTab(ttk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent)
        self.app = app_ref
        
        # Use the main app's config, but define a section for the state manager
        self.config = self.app.config
        self.setup_config_defaults()

        self.manifest_path = os.path.join(self.config.get('State', 'base_dir'), 'manifest.json')
        self.manifest = self.load_manifest()

        self.setup_ui()
        self.refresh_lineage_view()

    def setup_config_defaults(self):
        """Ensure default settings for the State Manager exist in config.ini."""
        if not self.config.config.has_section('State'):
            self.config.config.add_section('State')
            # Default base_dir to a subdirectory within the app's location
            base_dir = os.path.join(os.path.dirname(__file__), '..', 'StateSnapshots')
            os.makedirs(base_dir, exist_ok=True)
            self.config.set('State', 'base_dir', base_dir)
            self.config.save()
        
        # Ensure snapshot_dir is set
        base_dir = self.config.get('State', 'base_dir')
        if not self.config.config.has_option('State', 'snapshot_dir'):
             snapshot_dir = os.path.join(base_dir, 'snapshots')
             os.makedirs(snapshot_dir, exist_ok=True)
             self.config.set('State', 'snapshot_dir', snapshot_dir)
             self.config.save()

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Controls Frame
        controls_frame = ttk.LabelFrame(main_frame, text="Controls")
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Button(controls_frame, text="Quick Stash (Snapshot)", command=self.perform_quick_stash).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(controls_frame, text="Restore Selected Stash", command=self.confirm_restore).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(controls_frame, text="Refresh", command=self.refresh_lineage_view).pack(side=tk.RIGHT, padx=5, pady=5)

        # Lineage/Manifest View
        lineage_frame = ttk.LabelFrame(main_frame, text="Stash Lineage (History)")
        lineage_frame.grid(row=1, column=0, sticky="nsew")
        lineage_frame.rowconfigure(0, weight=1)
        lineage_frame.columnconfigure(0, weight=1)

        self.lineage_tree = ttk.Treeview(lineage_frame, columns=("ID", "Type", "Timestamp", "Files"), show="headings")
        self.lineage_tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(lineage_frame, orient="vertical", command=self.lineage_tree.yview)
        self.lineage_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.lineage_tree.heading("ID", text="ID")
        self.lineage_tree.heading("Type", text="Type")
        self.lineage_tree.heading("Timestamp", text="Timestamp")
        self.lineage_tree.heading("Files", text="# Files")

        self.lineage_tree.column("ID", width=100, anchor="w")
        self.lineage_tree.column("Type", width=100, anchor="w")
        self.lineage_tree.column("Timestamp", width=150, anchor="w")
        self.lineage_tree.column("Files", width=50, anchor="center")

    def load_manifest(self):
        try:
            if os.path.exists(self.manifest_path):
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            return []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_manifest(self):
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save manifest: {e}")

    def refresh_lineage_view(self):
        # Clear existing items
        for item in self.lineage_tree.get_children():
            self.lineage_tree.delete(item)
        
        # Re-load and sort manifest
        self.manifest = self.load_manifest()
        sorted_manifest = sorted(self.manifest, key=lambda x: x.get('timestamp', ''), reverse=True)

        for entry in sorted_manifest:
            entry_id = entry.get('id', 'N/A')[:8] # Short ID
            entry_type = entry.get('type', 'N/A')
            timestamp = entry.get('timestamp', 'N/A')
            num_files = len(entry.get('stashed_files', []))
            self.lineage_tree.insert("", "end", values=(entry_id, entry_type, timestamp, num_files), iid=entry.get('id'))

    def perform_quick_stash(self):
        snapshot_base_dir = self.config.get('State', 'snapshot_dir')
        source_dir = os.path.dirname(self.app.root.winfo_pathname(self.app.root.winfo_id())) # Get app's dir
        
        # For this GUI app, we'll stash the entire app directory content
        target_dir_name = f"stash_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stash_target_dir = os.path.join(snapshot_base_dir, target_dir_name)
        os.makedirs(stash_target_dir, exist_ok=True)

        stashed_files = []
        try:
            # A simple stash: copy all files instead of moving them
            for item in os.listdir(source_dir):
                source_item_path = os.path.join(source_dir, item)
                # Exclude the snapshot directory itself to prevent recursion
                if os.path.abspath(source_item_path) == os.path.abspath(snapshot_base_dir):
                    continue
                
                destination_item_path = os.path.join(stash_target_dir, item)
                if os.path.isfile(source_item_path):
                    shutil.copy2(source_item_path, destination_item_path)
                    stashed_files.append(item)
                elif os.path.isdir(source_item_path):
                    shutil.copytree(source_item_path, destination_item_path)
                    stashed_files.append(item + '/')

            # Record in manifest
            stash_id = str(uuid.uuid4())
            manifest_entry = {
                'id': stash_id,
                'timestamp': datetime.datetime.now().isoformat(),
                'type': 'quick_stash',
                'source_dir': source_dir,
                'target_dir': stash_target_dir,
                'stashed_files': stashed_files
            }
            self.manifest.append(manifest_entry)
            self.save_manifest()
            self.refresh_lineage_view()
            messagebox.showinfo("Success", f"Stashed {len(stashed_files)} items to {target_dir_name}")
        except Exception as e:
            messagebox.showerror("Stash Error", f"An error occurred during stash: {e}")

    def confirm_restore(self):
        selected_items = self.lineage_tree.selection()
        if not selected_items:
            messagebox.showwarning("Warning", "No stash selected to restore.")
            return
        
        stash_id = selected_items[0]
        if messagebox.askyesno("Confirm Restore", f"Are you sure you want to restore stash {stash_id[:8]}?\nThis will overwrite current files."):
            self.perform_restore(stash_id)

    def perform_restore(self, stash_id):
        found_stash = next((entry for entry in self.manifest if entry['id'] == stash_id), None)
        if not found_stash:
            messagebox.showerror("Error", f"Stash ID '{stash_id}' not found.")
            return

        source_dir = found_stash['target_dir'] # The stash IS the source
        destination_dir = found_stash['source_dir'] # Restore to original location
        
        try:
            for item in os.listdir(source_dir):
                source_item_path = os.path.join(source_dir, item)
                destination_item_path = os.path.join(destination_dir, item)

                # Remove existing item at destination before restoring
                if os.path.isfile(destination_item_path) or os.path.islink(destination_item_path):
                    os.remove(destination_item_path)
                elif os.path.isdir(destination_item_path):
                    shutil.rmtree(destination_item_path)

                # Move from stash to destination
                shutil.move(source_item_path, destination_item_path)
            
            # Clean up manifest and empty dir
            self.manifest = [entry for entry in self.manifest if entry['id'] != stash_id]
            self.save_manifest()
            os.rmdir(source_dir)

            self.refresh_lineage_view()
            messagebox.showinfo("Success", "Restore complete. Please restart the application to see changes.")
        except Exception as e:
            messagebox.showerror("Restore Error", f"An error occurred during restore: {e}")
