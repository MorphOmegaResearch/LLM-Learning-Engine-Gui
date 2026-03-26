#!/usr/bin/env python3
"""
backup_system.py - Target Backup System for grep_flight
Provides file backup functionality with timestamp naming and traceback logging
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict


class BackupManager:
    """Manages file backup operations with timestamp tracking"""

    @staticmethod
    def generate_backup_filename(original_path: str) -> str:
        """
        Generate backup filename with timestamp

        Args:
            original_path: Original file path

        Returns:
            Backup filename in format: filename_backup_YYYYMMDD_HHMMSS.ext
        """
        path = Path(original_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Split filename and extension
        stem = path.stem
        suffix = path.suffix

        # Create backup filename
        backup_name = f"{stem}_backup_{timestamp}{suffix}"
        return backup_name

    @staticmethod
    def backup_file(source_path: str, dest_dir: Optional[str] = None) -> Optional[Dict]:
        """
        Create backup of file

        Args:
            source_path: Path to file to backup
            dest_dir: Destination directory (None = same directory as source)

        Returns:
            Dict with backup info or None on failure
        """
        try:
            source = Path(source_path)

            # Validate source exists
            if not source.exists():
                return {"success": False, "error": "Source file does not exist"}

            if not source.is_file():
                return {"success": False, "error": "Source is not a file"}

            # Determine destination directory
            if dest_dir is None:
                dest_dir_path = source.parent
            else:
                dest_dir_path = Path(dest_dir)

            # Ensure destination directory exists
            dest_dir_path.mkdir(parents=True, exist_ok=True)

            # Generate backup filename
            backup_filename = BackupManager.generate_backup_filename(str(source))
            backup_path = Path(dest_dir_path) / backup_filename

            # Perform copy
            shutil.copy2(source, backup_path)  # copy2 preserves metadata

            # Get file sizes
            source_size = source.stat().st_size
            backup_size = backup_path.stat().st_size

            return {
                "success": True,
                "source_path": str(source),
                "backup_path": str(backup_path),
                "backup_filename": backup_filename,
                "backup_dir": str(dest_dir_path),
                "source_size": source_size,
                "backup_size": backup_size,
                "timestamp": datetime.now().isoformat(),
            }

        except PermissionError as e:
            return {"success": False, "error": f"Permission denied: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Backup failed: {e}"}


class BackupConfirmationDialog(tk.Toplevel):
    """Dialog for confirming backup operation with browse option"""

    def __init__(self, parent, target_path: str, on_confirm_callback):
        print("BackupConfirmationDialog.__init__ called")
        print(f"  Parent: {parent}")
        print(f"  Target: {target_path}")

        try:
            super().__init__(parent)
            print("  Toplevel created")
        except Exception as e:
            print(f"ERROR creating Toplevel: {e}")
            import traceback

            traceback.print_exc()
            raise

        try:
            self.title("Backup Target")
            self.geometry("600x300")
            self.configure(bg="#1e1e1e")
            print("  Basic properties set")
        except Exception as e:
            print(f"ERROR setting basic properties: {e}")
            import traceback

            traceback.print_exc()

        self.target_path = target_path
        self.on_confirm = on_confirm_callback
        self.result = None
        self.backup_dir = None

        try:
            # Make dialog modal
            print("  Setting transient...")
            self.transient(parent)
            print("  Setting grab...")
            self.grab_set()
            print("  Modal setup complete")
        except Exception as e:
            print(f"Warning: Could not set dialog modality: {e}")
            import traceback

            traceback.print_exc()

        try:
            print("  Calling setup_ui...")
            self.setup_ui()
            print("  setup_ui complete")
        except Exception as e:
            print(f"ERROR setting up dialog UI: {e}")
            import traceback

            traceback.print_exc()
            messagebox.showerror(
                "Dialog Error", f"Failed to create backup dialog:\n{e}"
            )
            try:
                self.destroy()
            except:
                pass
            raise

        try:
            # Center dialog
            print("  Centering dialog...")
            self.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (600 // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (300 // 2)
            self.geometry(f"+{x}+{y}")
            print("  Dialog centered")
        except Exception as e:
            print(f"Warning: Could not center dialog: {e}")
            import traceback

            traceback.print_exc()

        print("BackupConfirmationDialog.__init__ COMPLETE")

    def setup_ui(self):
        """Setup dialog UI"""
        # Header
        header = tk.Frame(self, bg="#2b2b2b", height=50)
        header.pack(fill=tk.X, pady=(0, 20))
        header.pack_propagate(False)

        tk.Label(
            header,
            text="📦 Backup Target File",
            bg="#2b2b2b",
            fg="#ffffff",
            font=("Arial", 14, "bold"),
        ).pack(pady=10)

        # Content
        content = tk.Frame(self, bg="#1e1e1e")
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # Target info
        tk.Label(
            content,
            text="Target file resolved from target system:",
            bg="#1e1e1e",
            fg="#cccccc",
            font=("Arial", 10),
        ).pack(anchor=tk.W, pady=(0, 10))

        # Target path display
        target_frame = tk.Frame(content, bg="#2a2a2a", relief=tk.SUNKEN, bd=1)
        target_frame.pack(fill=tk.X, pady=(0, 20))

        path = Path(self.target_path)
        filename = path.name
        directory = str(path.parent)

        tk.Label(
            target_frame,
            text=f"📄 {filename}",
            bg="#2a2a2a",
            fg="#4ec9b0",
            font=("Arial", 11, "bold"),
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        tk.Label(
            target_frame,
            text=f"📁 {directory}",
            bg="#2a2a2a",
            fg="#888888",
            font=("Monospace", 9),
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Backup destination
        tk.Label(
            content,
            text="Backup destination directory:",
            bg="#1e1e1e",
            fg="#cccccc",
            font=("Arial", 10),
        ).pack(anchor=tk.W, pady=(0, 5))

        dest_frame = tk.Frame(content, bg="#1e1e1e")
        dest_frame.pack(fill=tk.X, pady=(0, 20))

        self.dest_label = tk.Label(
            dest_frame,
            text=f"[Same directory] {directory}",
            bg="#2a2a2a",
            fg="#888888",
            font=("Monospace", 9),
            anchor=tk.W,
            padx=10,
            pady=5,
            relief=tk.SUNKEN,
        )
        self.dest_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        tk.Button(
            dest_frame,
            text="Browse...",
            command=self.browse_destination,
            bg="#3c3c3c",
            fg="#ffffff",
            relief=tk.FLAT,
            padx=10,
        ).pack(side=tk.RIGHT)

        # Buttons
        button_frame = tk.Frame(self, bg="#1e1e1e")
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        tk.Button(
            button_frame,
            text="Yes - Backup Now",
            command=self.confirm_backup,
            bg="#0e639c",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=20,
            pady=8,
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            button_frame,
            text="No - Cancel",
            command=self.cancel_backup,
            bg="#5c0000",
            fg="white",
            font=("Arial", 10),
            relief=tk.FLAT,
            padx=20,
            pady=8,
        ).pack(side=tk.LEFT)

    def browse_destination(self):
        """Browse for backup destination directory"""
        try:
            # Use same directory as initial
            initial_dir = str(Path(self.target_path).parent)

            # Temporarily withdraw dialog
            try:
                self.withdraw()
                self.update_idletasks()
            except Exception as e:
                print(f"Warning: Could not withdraw dialog: {e}")

            dest = filedialog.askdirectory(
                title="Select Backup Destination Directory", initialdir=initial_dir
            )

            # Restore dialog
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception as e:
                print(f"Warning: Could not restore dialog: {e}")

            if dest:
                self.backup_dir = dest
                self.dest_label.config(text=f"[Custom] {dest}")
        except Exception as e:
            print(f"Error in browse_destination: {e}")
            messagebox.showerror(
                "Browse Error", f"Failed to browse for directory:\n{e}"
            )

    def confirm_backup(self):
        """User confirmed backup"""
        try:
            self.result = "yes"

            # If no custom directory selected, use same directory
            if self.backup_dir is None:
                self.backup_dir = str(Path(self.target_path).parent)

            # Release grab before destroying
            try:
                self.grab_release()
            except:
                pass

            self.destroy()

            # Execute callback
            if self.on_confirm:
                try:
                    self.on_confirm(self.backup_dir)
                except Exception as e:
                    print(f"Error in backup callback: {e}")
                    messagebox.showerror(
                        "Backup Error", f"Backup operation failed:\n{e}"
                    )
        except Exception as e:
            print(f"Error in confirm_backup: {e}")
            messagebox.showerror("Dialog Error", f"Failed to confirm backup:\n{e}")

    def cancel_backup(self):
        """User cancelled backup"""
        try:
            self.result = "no"
            # Release grab before destroying
            try:
                self.grab_release()
            except:
                pass
            self.destroy()
        except Exception as e:
            print(f"Error in cancel_backup: {e}")


def show_backup_dialog(parent, target_path: str, engine, add_traceback_func):
    """
    Show backup confirmation dialog and execute backup

    Args:
        parent: Parent tkinter window
        target_path: Path to file to backup
        engine: GrepSurgicalEngine instance for logging
        add_traceback_func: Function to add messages to traceback UI
    """
    print("\n=== SHOW_BACKUP_DIALOG CALLED ===")
    print(f"Target path: {target_path}")
    print(f"Parent: {parent}")
    print(f"Engine: {engine}")
    add_traceback_func("🔍 show_backup_dialog started", "DEBUG")

    try:
        # Validate inputs
        print("Validating target...")
        add_traceback_func("🔍 Validating target path...", "DEBUG")
        if not target_path:
            print("ERROR: No target path")
            messagebox.showerror("Error", "No target path provided")
            return

        if not os.path.exists(target_path):
            print(f"ERROR: Path doesn't exist: {target_path}")
            messagebox.showerror("Error", f"Target file does not exist:\n{target_path}")
            return

        if not os.path.isfile(target_path):
            print(f"ERROR: Not a file: {target_path}")
            messagebox.showerror("Error", f"Target is not a file:\n{target_path}")
            return

        print("Validation passed!")
        add_traceback_func("✅ Target validation passed", "DEBUG")

    except Exception as e:
        print(f"Error validating target: {e}")
        import traceback

        traceback.print_exc()
        add_traceback_func(f"❌ Validation error: {e}", "ERROR")
        messagebox.showerror("Validation Error", f"Failed to validate target:\n{e}")
        return

    def on_confirm(backup_dir: str):
        """Callback when user confirms backup"""
        # Log to engine
        engine.log_debug(f"🔄 Starting backup process for: {target_path}", "INFO")
        engine.log_debug(f"   Destination: {backup_dir}", "INFO")

        # Perform backup
        result = BackupManager.backup_file(target_path, backup_dir)

        if not result:
            add_traceback_func("❌ BACKUP FAILED: Unknown error", "ERROR")
            return

        if result["success"]:
            # Success!
            backup_path = result["backup_path"]
            backup_filename = result["backup_filename"]
            timestamp = result["timestamp"]

            # Log to traceback UI
            add_traceback_func(
                f"✅ BACKUP SUCCESSFUL\n"
                f"   Source: {Path(target_path).name}\n"
                f"   Backup: {backup_filename}\n"
                f"   Location: {backup_dir}\n"
                f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "SUCCESS",
            )

            # Log to engine
            engine.log_debug(
                f"✅ Backup created successfully: {backup_filename}", "SUCCESS"
            )
            engine.log_debug(f"   Full path: {backup_path}", "INFO")
            engine.log_debug(f"   Size: {result['source_size']} bytes", "INFO")

            # Show success message
            messagebox.showinfo(
                "Backup Complete",
                f"File backed up successfully!\n\n"
                f"Original: {Path(target_path).name}\n"
                f"Backup: {backup_filename}\n\n"
                f"Location: {backup_dir}",
            )

        else:
            # Failed
            error_msg = result["error"]

            # Log to traceback UI
            add_traceback_func(
                f"❌ BACKUP FAILED\n"
                f"   File: {Path(target_path).name}\n"
                f"   Error: {error_msg}",
                "ERROR",
            )

            # Log to engine
            engine.log_debug(f"❌ Backup failed: {error_msg}", "ERROR")

            # Show error message
            messagebox.showerror(
                "Backup Failed", f"Failed to create backup:\n\n{error_msg}"
            )

    # Show confirmation dialog
    try:
        print("Creating BackupConfirmationDialog...")
        add_traceback_func("🔍 Creating dialog window...", "DEBUG")
        dialog = BackupConfirmationDialog(parent, target_path, on_confirm)
        print(f"Dialog created: {dialog}")
        print(f"Dialog exists: {dialog.winfo_exists()}")
        add_traceback_func("🔍 Dialog created, waiting for user...", "DEBUG")
        print("Calling parent.wait_window...")
        parent.wait_window(dialog)
        print("wait_window returned")
        add_traceback_func("✅ Dialog interaction complete", "DEBUG")
    except Exception as e:
        print(f"Error showing backup dialog: {e}")
        import traceback

        traceback.print_exc()
        add_traceback_func(f"❌ Backup dialog error: {e}", "ERROR")
        messagebox.showerror("Dialog Error", f"Failed to show backup dialog:\n{e}")
