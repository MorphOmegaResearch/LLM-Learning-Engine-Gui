import logger_util
import sys
import os
from pathlib import Path
from datetime import datetime

# --- EARLY STARTUP LOGGING --- 
# Initialize logger as early as possible to capture all output
logger_util.init_logger()

# Redirect stdout/stderr to a temporary file to capture very early errors
# This file will later be merged into the main debug log

# Check if launched by wrapper script, which provides a temp log path
wrapper_temp_log_path_str = os.getenv("GEMINI_WRAPPER_TEMP_LOG")
if wrapper_temp_log_path_str:
    temp_log_path = Path(wrapper_temp_log_path_str)
    # The wrapper script already created and redirected to this file
    # We just need to ensure Python's sys.stdout/stderr are also pointing there
    # and that the original streams are saved.
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        sys.stdout = open(temp_log_path, 'a', buffering=1) # Line-buffered
        sys.stderr = open(temp_log_path, 'a', buffering=1) # Line-buffered
    except Exception as e:
        print(f"WARNING: Could not redirect early stdout/stderr to {temp_log_path}: {e}", file=original_stderr)
        sys.stdout = original_stdout
        sys.stderr = original_stderr
else:
    # Not launched by wrapper, create our own temp log
    temp_log_path = Path(logger_util.LOG_DIR) / f"startup_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    temp_log_path.parent.mkdir(parents=True, exist_ok=True)

    # Store original stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    try:
        sys.stdout = open(temp_log_path, 'a', buffering=1) # Line-buffered
        sys.stderr = open(temp_log_path, 'a', buffering=1) # Line-buffered
    except Exception as e:
        # Fallback if redirection fails (e.g., permissions)
        print(f"WARNING: Could not redirect early stdout/stderr to {temp_log_path}: {e}", file=original_stderr)
        sys.stdout = original_stdout
        sys.stderr = original_stderr

# --- END EARLY STARTUP LOGGING ---

# --- Add custom_code's site-packages to sys.path (SAFELY GATED) ---
# This is controlled by the ENABLE_CUSTOM_CODE_INTEGRATION environment variable.
# Set ENABLE_CUSTOM_CODE_INTEGRATION=true to enable.
if os.getenv("ENABLE_CUSTOM_CODE_INTEGRATION", "false").lower() == "true":
    custom_code_site_packages_path = Path(__file__).parent.parent / "Data" / "tabs" / "custom_code_tab" / "site-packages"
    if custom_code_site_packages_path.exists() and str(custom_code_site_packages_path) not in sys.path:
        sys.path.insert(0, str(custom_code_site_packages_path))
        logger_util.log_message(f"MAIN_GUI: Custom_code site-packages added to sys.path: {custom_code_site_packages_path}")
    else:
        logger_util.log_message(f"MAIN_GUI: Custom_code site-packages path not found or already in sys.path: {custom_code_site_packages_path}")
else:
    logger_util.log_message("MAIN_GUI: Custom_code integration is disabled (ENABLE_CUSTOM_CODE_INTEGRATION not 'true').")
# --- END custom_code sys.path modification ---

#!/usr/bin/env python3
"""
OpenCode Training Launcher - Modular GUI
Main window that loads isolated tab modules
"""

import tkinter as tk
from tkinter import ttk

# Import tab modules
from tabs.training_tab import TrainingTab
from tabs.models_tab import ModelsTab
from tabs.settings_tab import SettingsTab
from tabs.custom_code_tab import CustomCodeTab


class TrainingGUI:
    """Modular training launcher with isolated tabs"""

    def __init__(self):
        # After logger_util.init_logger() has been called and LOG_FILE_PATH is set
        # Redirect stdout/stderr to the permanent debug log file
        try:
            permanent_log_path = logger_util.get_log_file_path()
            if str(temp_log_path) != permanent_log_path:
                # Close temporary redirection
                sys.stdout.close()
                sys.stderr.close()

                # Copy contents of temp log to permanent log
                with open(temp_log_path, 'r') as temp_f, open(permanent_log_path, 'a') as perm_f:
                    perm_f.write(temp_f.read())
                temp_log_path.unlink(missing_ok=True) # Delete temp file

                # Redirect to permanent log
                sys.stdout = open(permanent_log_path, 'a', buffering=1)
                sys.stderr = open(permanent_log_path, 'a', buffering=1)
        except Exception as e:
            print(f"WARNING: Could not redirect stdout/stderr to permanent log {permanent_log_path}: {e}", file=original_stderr)
            sys.stdout = original_stdout
            sys.stderr = original_stderr
        
        logger_util.log_message("==================================================")
        logger_util.log_message("MAIN_GUI: Application starting...")
        self.root = tk.Tk()
        self.root.title("OpenCode Training Launcher")

        # Set ttk theme and style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure general styles
        self._configure_styles()

        # Build UI
        self.create_ui()

        # Set shutdown hook
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _configure_styles(self):
        """Configure ttk styles for dark theme"""
        self.style.configure('.', font=('Arial', 10), background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TFrame', background='#2b2b2b', borderwidth=0)
        self.style.configure('TLabel', background='#2b2b2b', foreground='#ffffff')
        self.style.configure('TCheckbutton', background='#363636', foreground='#ffffff', indicatoron=False, relief='flat', padding=5)
        self.style.map('TCheckbutton',
                       background=[('active', '#454545'), ('selected', '#61dafb')],
                       foreground=[('active', '#ffffff'), ('selected', '#1e1e1e')])
        self.style.configure('TButton', font=('Arial', 10, 'bold'), relief='flat', borderwidth=0, padding=10)
        self.style.map('TButton',
                       background=[('active', '#454545')],
                       foreground=[('active', '#ffffff')])
        self.style.configure('TSpinbox', fieldbackground='#1e1e1e', foreground='#ffffff', background='#363636', arrowcolor='#61dafb')
        self.style.configure('TEntry', fieldbackground='#1e1e1e', foreground='#ffffff', insertcolor='#ffffff')
        self.style.configure('TLabelframe', background='#363636', foreground='#ffffff', relief='flat', borderwidth=0)
        self.style.configure('TLabelframe.Label', background='#363636', foreground='#ffffff', font=('Arial', 12, 'bold'))
        self.style.configure('TScrollbar', troughcolor='#2b2b2b', background='#61dafb', borderwidth=0, relief='flat')
        self.style.map('TScrollbar', background=[('active', '#454545')])

        # Additional styles
        self.style.configure('Header.TFrame', background='#1e1e1e')
        self.style.configure('Header.TLabel', font=("Arial", 24, "bold"), background='#1e1e1e', foreground='#61dafb')
        self.style.configure('CategoryPanel.TLabel', font=("Arial", 14, "bold"), background='#2b2b2b', foreground='#ffffff')
        self.style.configure('Category.TFrame', background='#363636', relief='flat', borderwidth=1)
        self.style.configure('Category.TCheckbutton', font=("Arial", 12, "bold"), background='#363636', foreground='#61dafb', padding=8)
        self.style.configure('Config.TLabel', background='#363636', foreground='#ffffff')
        self.style.configure('Select.TButton', font=("Arial", 9), background='#454545', foreground='#ffffff', padding=5)
        self.style.configure('Action.TButton', font=("Arial", 10, "bold"), background='#61dafb', foreground='#1e1e1e', padding=8)
        self.style.configure('Category.TRadiobutton', font=("Arial", 10), background='#363636', foreground='#ffffff', indicatoron=False, relief='flat', padding=5)

    def create_ui(self):
        """Create the GUI layout with tabs"""
        # Header
        header = ttk.Frame(self.root, height=80, style='Header.TFrame')
        header.pack(fill=tk.X, padx=0, pady=0)

        title_label = ttk.Label(
            header,
            text="🚀 OpenCode Training Launcher",
            style='Header.TLabel'
        )
        title_label.pack(pady=20)

        # Main content area - Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Load tabs
        self.load_tabs()

        # Enable tab reordering by dragging (conditional)
        if self.settings_tab and self.settings_tab.reorder_mode.get() == 'dnd':
            self.notebook.bind("<ButtonPress-1>", self._on_tab_drag_start)
            self.notebook.bind("<B1-Motion>", self._on_tab_drag_motion)
            self.notebook.bind("<ButtonRelease-1>", self._on_tab_drag_end)
            self._drag_data = {"item": None, "x": 0, "y": 0, "current_index": None, "initial_tab_id": None, "initial_x": 0, "initial_y": 0, "initial_index": None, "drag_pending": False, "after_id": None} # Initialize all drag data
            logger_util.log_message("MAIN_GUI: Tab drag-and-drop reordering is ENABLED by settings.")
        else:
            logger_util.log_message("MAIN_GUI: Tab drag-and-drop reordering is DISABLED by settings.")
            self._drag_data = {"item": None, "x": 0, "y": 0, "current_index": None, "initial_tab_id": None, "initial_x": 0, "initial_y": 0, "initial_index": None, "drag_pending": False, "after_id": None} # Initialize drag data even if disabled

    def _on_tab_drag_start(self, event):
        """Handle start of tab drag, with a delay to differentiate click from drag."""
        tab_id = None
        tab_index = None
        try:
            tab_index = self.notebook.index(f"@{event.x},{event.y}")
            tab_id = self.notebook.tabs()[tab_index]
        except tk.TclError:
            pass # Not over a tab header

        if tab_id is not None:
            self._drag_data["initial_tab_id"] = tab_id
            self._drag_data["initial_x"] = event.x
            self._drag_data["initial_y"] = event.y
            self._drag_data["initial_index"] = tab_index
            self._drag_data["drag_pending"] = True
            self._drag_data["after_id"] = self.root.after(500, self._start_drag_after_delay) # 500ms delay
            logger_util.log_message(f"MAIN_GUI: Drag initiation pending for tab: {self.notebook.tab(tab_id, 'text')}")
        else:
            logger_util.log_message(f"MAIN_GUI: Click not over a valid tab. Ignoring drag start.")
            self._drag_data["item"] = None # Ensure no drag is active
            self._drag_data["drag_pending"] = False

    def _on_tab_drag_motion(self, event):
        """Handle tab drag motion."""
        if self._drag_data.get("drag_pending", False):
            # Check for significant movement to start drag immediately
            dx = abs(event.x - self._drag_data["initial_x"])
            dy = abs(event.y - self._drag_data["initial_y"])
            if dx > 5 or dy > 5: # Threshold for movement
                self.root.after_cancel(self._drag_data["after_id"])
                self._drag_data["item"] = self._drag_data["initial_tab_id"]
                self._drag_data["current_index"] = self._drag_data["initial_index"]
                logger_util.log_message(f"MAIN_GUI: Drag initiated by movement for tab: {self.notebook.tab(self._drag_data['item'], 'text')}")
                self._drag_data["drag_pending"] = False
            else:
                return # Don't process motion if drag not yet initiated

        if self._drag_data["item"]:
            current_tab_id = self._drag_data["item"]
            current_index = self._drag_data["current_index"] # Use stored current_index
            
            # Step 6: Add timing
            import time
            current_time = time.time()
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Event timestamp: {current_time}")

            # Step 1: Isolate the Problem - Initial State
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Initial State: tabs_before_any_ops={self.notebook.tabs()}, current_index={current_index}, target_index_from_event_coords={event.x},{event.y}")
            
            # Step 1: Isolate the Problem - Initial State
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - tabs_before_any_ops={self.notebook.tabs()}")
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - current_index={current_index}, target_index_from_event_coords={event.x},{event.y}")
            
            try:
                # Get tab text before potentially forgetting it
                tab_text = self.notebook.tab(current_tab_id, 'text')
            except tk.TclError:
                # Tab might have been forgotten in a previous motion event
                logger_util.log_message(f"MAIN_GUI: Drag motion: current_tab_id '{current_tab_id}' not managed. Resetting drag.")
                self._drag_data["item"] = None
                return

            # Identify the tab under the mouse using coordinates
            try:
                target_index = self.notebook.index(f"@{event.x},{event.y}")
            except tk.TclError:
                target_index = None

            # Step 6: Add timing
            import time
            current_time = time.time()
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Event timestamp: {current_time}")

            # Step 1: Isolate the Problem
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - tabs_before_any_ops={self.notebook.tabs()}")
            logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - current_index={current_index}, target_index={target_index}")
            # tab_widget is defined later, so we'll log its existence after it's defined.

            try:
                # Get tab text before potentially forgetting it
                tab_text = self.notebook.tab(current_tab_id, 'text')
            except tk.TclError:
                # Tab might have been forgotten in a previous motion event
                logger_util.log_message(f"MAIN_GUI: Drag motion: current_tab_id '{current_tab_id}' not managed. Resetting drag.")
                self._drag_data["item"] = None
                return

            # Identify the tab under the mouse using coordinates
            try:
                target_index = self.notebook.index(f"@{event.x},{event.y}")
            except tk.TclError:
                target_index = None

            # Step 4: Verify Index Calculation
            try:
                test_index_from_coords = self.notebook.index(f"@{event.x},{event.y}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - notebook.index() returned: {test_index_from_coords}")
            except Exception as e:
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - notebook.index() failed: {e}")


            logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - current_index={current_index}, target_index={target_index}, current_tab_id={current_tab_id}")

            if target_index is not None and current_index != target_index:
                # Step 5: Add Motion Threshold (already implemented as part of the delay logic)
                # if abs(target_index - current_index) < 1: # Only reorder if we've moved at least 1 position
                #     return # Skip insignificant moves

                # Step 1: Fix the Core Logic (already implemented)
                insert_index = target_index  # Always use the original target index

                # Calculate num_tabs before forgetting the current tab
                num_tabs_before_removal = len(self.notebook.tabs())

                # Get the actual widget (frame) associated with the tab
                tab_widget = self.notebook.nametowidget(current_tab_id)
                logger_util.log_message(f"MAIN_GUI: DIAGNOSTIC - tab_widget_exists_before_forget={tab_widget.winfo_exists()}")
                
                # Remove the tab from its current position
                self.notebook.forget(current_tab_id)
                
                # Step 3: Check Tab State After Removal
                remaining_tabs = self.notebook.tabs()
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - After forget - tabs={remaining_tabs}, count={len(remaining_tabs)}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Tab widget still exists after forget: {tab_widget.winfo_exists()}")
                
                # Step 3: Check Tab State After Removal
                remaining_tabs = self.notebook.tabs()
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - After forget - tabs={remaining_tabs}, count={len(remaining_tabs)}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Tab widget still exists after forget: {tab_widget.winfo_exists()}")
                
                # Step 3: Check Tab State After Removal
                remaining_tabs = self.notebook.tabs()
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - After forget - tabs={remaining_tabs}, count={len(remaining_tabs)}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Tab widget still exists after forget: {tab_widget.winfo_exists()}")
                
                # Step 3: Check Tab State After Removal
                remaining_tabs = self.notebook.tabs()
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - After forget - tabs={remaining_tabs}, count={len(remaining_tabs)}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Tab widget still exists after forget: {tab_widget.winfo_exists()}")
                
                # Step 3: Check Tab State After Removal
                remaining_tabs = self.notebook.tabs()
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - After forget - tabs={remaining_tabs}, count={len(remaining_tabs)}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DIAGNOSTIC - Tab widget still exists after forget: {tab_widget.winfo_exists()}")

                # Step 2: Add Boundary Protection
                current_tab_count = len(self.notebook.tabs())
                logger_util.log_message(f"MAIN_GUI: BOUNDARY_DEBUG - current_tab_count={current_tab_count}, should_be_max_index={current_tab_count}")

                # Corrected boundary logic:
                if target_index >= len(self.notebook.tabs()):
                    insert_index = "end"  # Tkinter special position for "insert at end"
                    logger_util.log_message(f"MAIN_GUI: BOUNDARY_DEBUG - target_index >= current_tab_count, setting insert_index='end'")
                else:
                    insert_index = target_index
                    # Still cap for safety
                    max_valid_index = len(self.notebook.tabs()) - 1
                    if insert_index > max_valid_index:
                        insert_index = max_valid_index
                    if insert_index < 0:
                        insert_index = 0
                    logger_util.log_message(f"MAIN_GUI: BOUNDARY_DEBUG - target_index < current_tab_count, insert_index={insert_index}, max_valid_index={max_valid_index}")

                logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - After capping: insert_index={insert_index}")

                # This log now needs to be conditional or max_valid_index needs to be initialized outside the if/else
                # For now, let's move it inside the else block where max_valid_index is guaranteed to be defined
                if insert_index != "end": # Only log max_valid_index if it was actually used
                    logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - current_index={current_index}, target_index={target_index}, insert_index={insert_index}, tabs_before_forget={num_tabs_before_removal}, tabs_after_forget={len(self.notebook.tabs())}, max_valid_index={max_valid_index}")
                else:
                    logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - current_index={current_index}, target_index={target_index}, insert_index={insert_index}, tabs_before_forget={num_tabs_before_removal}, tabs_after_forget={len(self.notebook.tabs())}")

                logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - Before insert: insert_index={insert_index}, len_tabs_before_insert={len(self.notebook.tabs())}")

                # Insert the tab at the new position
                self.notebook.insert(insert_index, tab_widget, text=tab_text)
                
                # Select the reordered tab to keep it active
                self.notebook.select(tab_widget)

                logger_util.log_message(f"MAIN_GUI: Reordered tab '{tab_text}' to index {insert_index}")
                logger_util.log_message(f"MAIN_GUI: DRAG_DEBUG - tabs_after_insert={len(self.notebook.tabs())}")
                
                # Step 4: Update Index Tracking Correctly
                self._drag_data["current_index"] = insert_index # Update with the actual new position

    def _on_tab_drag_end(self, event):
        """Handle end of tab drag."""
        if self._drag_data.get("drag_pending", False):
            self.root.after_cancel(self._drag_data["after_id"])
            logger_util.log_message("MAIN_GUI: Drag pending cancelled.")
        self._drag_data = {"item": None, "x": 0, "y": 0, "current_index": None, "initial_tab_id": None, "initial_x": 0, "initial_y": 0, "initial_index": None, "drag_pending": False, "after_id": None}
        logger_util.log_message("MAIN_GUI: Tab drag ended.")

    def load_tabs(self):
        """Load all tab modules with error isolation and deterministic ordering."""
        # Always create the SettingsTab first to ensure its settings are available.
        # This instance will be used to get settings and will be placed in the notebook.
        settings_frame = ttk.Frame(self.notebook)
        self.settings_tab = SettingsTab(settings_frame, self.root, self.style, main_gui=self)
        if not self.settings_tab.safe_create():
            logger_util.log_message("MAIN_GUI: ⚠️ Settings tab failed to load during initial setup.")
            settings = {}
        else:
            settings = self.settings_tab.settings

        tab_definitions = {
            'training_tab': ('⚙️ Training', TrainingTab, 'training_tab'),
            'models_tab': ('🧠 Models', ModelsTab, 'models_tab'),
            'custom_code_tab': ('🤖 Custom Code', CustomCodeTab, 'custom_code_tab'),
            'settings_tab': ('⚙️ Settings', SettingsTab, 'settings_tab'),
        }

        available_tabs = [name for name in tab_definitions if settings.get(f"{name}_enabled", True)]

        DEFAULT_TAB_ORDER = ['training_tab', 'models_tab', 'custom_code_tab', 'settings_tab']

        def normalize_tab_order(available_tabs: list[str]) -> list[str]:
            # Start with our canonical order (minus missing)
            ordered = [t for t in DEFAULT_TAB_ORDER if t in available_tabs]
            # Insert any extra tabs (e.g., ChatInterface, Tools, etc.) before settings_tab
            extras = [t for t in available_tabs if t not in ordered]
            if 'settings_tab' in ordered:
                idx = ordered.index('settings_tab')
                ordered[idx:idx] = [t for t in extras if t != 'settings_tab']
            else:
                ordered.extend(extras)
                if 'settings_tab' in available_tabs:
                    ordered.append('settings_tab')
            # Always de-dupe
            seen, deduped = set(), []
            for t in ordered:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            return deduped

        tab_order = normalize_tab_order(available_tabs)
        settings['tab_order'] = tab_order # Update settings in memory

        # Create all tab instances
        tab_instances = {}
        for name in tab_order: # Iterate in the final order
            if name in available_tabs:
                (text, tab_class, attr) = tab_definitions[name]
                if name == 'settings_tab':
                    # Use the already created settings_tab instance and its frame
                    frame = settings_frame
                    instance = self.settings_tab
                else:
                    frame = ttk.Frame(self.notebook)
                    instance = tab_class(frame, self.root, self.style)
                    if not instance.safe_create():
                        logger_util.log_message(f"MAIN_GUI: ⚠️ {text} tab failed to load.")
                        continue # Don't add failed tabs

                tab_instances[name] = {'frame': frame, 'text': text, 'instance': instance}
                setattr(self, attr, instance)
                self.notebook.add(frame, text=text)
            else:
                logger_util.log_message(f"MAIN_GUI: {tab_definitions[name][0]} tab is disabled by user settings.")
                setattr(self, tab_definitions[name][2], None)

        # Now that all instances are created, pass tab_instances to all tabs
        for name, meta in tab_instances.items():
            try:
                meta['instance'].tab_instances = tab_instances
            except Exception:
                pass

    def run(self):
        """Start the GUI main loop"""
        self.root.mainloop()

    def on_closing(self):
        """Handle window close event."""
        logger_util.log_message("MAIN_GUI: Application shutting down.")
        # Stop any running polls
        if hasattr(self, 'settings_tab') and self.settings_tab:
            self.settings_tab.stop_log_polling()
        self.root.destroy()


    def _start_drag_after_delay(self):
        """Initiate drag if still pending after delay."""
        if self._drag_data.get("drag_pending", False):
            # Check if mouse has moved significantly (optional, but good for UX)
            # For now, just initiate if pending
            self._drag_data["item"] = self._drag_data["initial_tab_id"]
            self._drag_data["current_index"] = self._drag_data["initial_index"]
            logger_util.log_message(f"MAIN_GUI: Drag initiated after delay for tab: {self.notebook.tab(self._drag_data['item'], 'text')}")
            self._drag_data["drag_pending"] = False


if __name__ == "__main__":
    app = TrainingGUI()
    app.run()
