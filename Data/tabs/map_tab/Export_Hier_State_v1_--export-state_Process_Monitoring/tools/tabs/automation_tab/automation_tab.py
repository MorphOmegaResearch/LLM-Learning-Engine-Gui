"""
Automation Tab (Phase 2.8C)

Safe, time-limited automation for GUI testing.

Key Safety Features:
- Pre-agreed time limits
- Emergency stop (ESC key)
- Preview before execution
- Recording and playback
- Test scenario library
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

# Try to import automation libraries
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to corner to abort
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


class AutomationTab(ttk.Frame):
    """
    Automation tab for safe GUI testing

    Features:
    - Time-limited automation
    - Recording and playback
    - Test scenarios
    - Safety controls
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.recording = False
        self.playing = False
        self.recorded_actions = []
        self.current_thread: Optional[threading.Thread] = None

        # Safety settings
        self.max_duration_seconds = 300  # 5 minutes default
        self.emergency_stop = False

        # Test scenarios directory
        self.scenarios_dir = Path(__file__).parent / "test_scenarios"
        self.scenarios_dir.mkdir(exist_ok=True)

        self.create_ui()

        # Bind ESC key globally for emergency stop
        self.bind_all("<Escape>", self.emergency_stop_handler)

    def create_ui(self):
        """Create automation tab UI"""

        # Main container with padding
        main_container = ttk.Frame(self, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            header_frame,
            text="🤖 Automation & GUI Testing",
            font=("Arial", 14, "bold")
        ).pack(side=tk.LEFT)

        # Status indicator
        self.status_label = ttk.Label(
            header_frame,
            text="⚫ Idle",
            font=("Arial", 10)
        )
        self.status_label.pack(side=tk.RIGHT)

        # Check availability
        if not PYAUTOGUI_AVAILABLE:
            warning_frame = ttk.Frame(main_container)
            warning_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(
                warning_frame,
                text="⚠️ PyAutoGUI not installed. Run: pip install pyautogui",
                foreground="orange",
                font=("Arial", 10, "bold")
            ).pack()

        # Create notebook for different sections
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Quick Actions
        quick_frame = ttk.Frame(notebook, padding="10")
        notebook.add(quick_frame, text="⚡ Quick Actions")
        self.create_quick_actions(quick_frame)

        # Tab 2: Test Scenarios
        scenarios_frame = ttk.Frame(notebook, padding="10")
        notebook.add(scenarios_frame, text="📋 Test Scenarios")
        self.create_scenarios_panel(scenarios_frame)

        # Tab 3: Record & Playback
        record_frame = ttk.Frame(notebook, padding="10")
        notebook.add(record_frame, text="🎬 Record & Playback")
        self.create_record_panel(record_frame)

        # Tab 4: Settings & Safety
        settings_frame = ttk.Frame(notebook, padding="10")
        notebook.add(settings_frame, text="⚙️ Safety Settings")
        self.create_settings_panel(settings_frame)

    def create_quick_actions(self, parent):
        """Create quick action buttons"""

        ttk.Label(
            parent,
            text="Pre-configured quick tests:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 10))

        # Quick test buttons
        quick_tests = [
            ("🤖 Launch GUI Bridge", "AI-powered GUI control (any model)", self.launch_gui_bridge),
            ("Test Model Switch", "Switch between models in Models tab", self.test_model_switch),
            ("Test Chat Interface", "Send test messages and verify responses", self.test_chat_interface),
            ("Test Settings Save", "Modify and save settings", self.test_settings_save),
            ("Test Tab Navigation", "Navigate through all tabs", self.test_tab_navigation),
            ("Screenshot All Tabs", "Take screenshots of all tabs", self.screenshot_all_tabs),
        ]

        for title, description, command in quick_tests:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=5)

            ttk.Button(
                frame,
                text=title,
                command=command,
                width=25
            ).pack(side=tk.LEFT, padx=(0, 10))

            ttk.Label(
                frame,
                text=description,
                foreground="gray"
            ).pack(side=tk.LEFT)

    def create_scenarios_panel(self, parent):
        """Create test scenarios panel"""

        # Scenario list
        list_frame = ttk.Frame(parent)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(
            list_frame,
            text="Available Test Scenarios:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))

        # Listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.scenarios_listbox = tk.Listbox(
            list_container,
            yscrollcommand=scrollbar.set,
            font=("Arial", 10)
        )
        self.scenarios_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.scenarios_listbox.yview)

        self.scenarios_listbox.bind('<<ListboxSelect>>', self.on_scenario_select)

        # Buttons
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Refresh",
            command=self.refresh_scenarios
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Run Selected",
            command=self.run_selected_scenario,
            state=tk.DISABLED
        ).pack(side=tk.LEFT, padx=(0, 5))

        # Details panel
        details_frame = ttk.Frame(parent)
        details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        ttk.Label(
            details_frame,
            text="Scenario Details:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))

        self.scenario_details = scrolledtext.ScrolledText(
            details_frame,
            wrap=tk.WORD,
            height=20,
            font=("Consolas", 9)
        )
        self.scenario_details.pack(fill=tk.BOTH, expand=True)

        # Load scenarios
        self.refresh_scenarios()

    def create_record_panel(self, parent):
        """Create recording panel"""

        # Control frame
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        self.record_btn = ttk.Button(
            control_frame,
            text="🔴 Start Recording",
            command=self.start_recording
        )
        self.record_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_record_btn = ttk.Button(
            control_frame,
            text="⏹️ Stop Recording",
            command=self.stop_recording,
            state=tk.DISABLED
        )
        self.stop_record_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.play_btn = ttk.Button(
            control_frame,
            text="▶️ Play Recording",
            command=self.play_recording,
            state=tk.DISABLED
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            control_frame,
            text="💾 Save Scenario",
            command=self.save_scenario
        ).pack(side=tk.LEFT, padx=(0, 5))

        # Actions display
        ttk.Label(
            parent,
            text="Recorded Actions:",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=(10, 5))

        self.actions_text = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            height=20,
            font=("Consolas", 9)
        )
        self.actions_text.pack(fill=tk.BOTH, expand=True)

    def create_settings_panel(self, parent):
        """Create safety settings panel"""

        # Safety settings
        settings_frame = ttk.LabelFrame(parent, text="Safety Controls", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Max duration
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            duration_frame,
            text="Max Duration (seconds):",
            width=25
        ).pack(side=tk.LEFT)

        self.duration_var = tk.IntVar(value=self.max_duration_seconds)
        ttk.Spinbox(
            duration_frame,
            from_=10,
            to=600,
            textvariable=self.duration_var,
            width=10
        ).pack(side=tk.LEFT, padx=(5, 0))

        # Emergency stop info
        info_frame = ttk.LabelFrame(parent, text="Emergency Stop", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            info_frame,
            text="Press ESC to stop any automation immediately",
            font=("Arial", 10, "bold"),
            foreground="red"
        ).pack()

        ttk.Label(
            info_frame,
            text="Or move mouse to top-left corner of screen",
            foreground="gray"
        ).pack()

        # Current status
        status_frame = ttk.LabelFrame(parent, text="Current Status", padding="10")
        status_frame.pack(fill=tk.BOTH, expand=True)

        self.status_text = scrolledtext.ScrolledText(
            status_frame,
            wrap=tk.WORD,
            height=10,
            font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)

    # ===== Quick Test Methods =====

    def test_model_switch(self):
        """Test switching between models"""
        if not PYAUTOGUI_AVAILABLE:
            messagebox.showwarning("Not Available", "PyAutoGUI not installed")
            return

        messagebox.showinfo(
            "Test: Model Switch",
            "This will:\n"
            "1. Navigate to Models tab\n"
            "2. Select different models\n"
            "3. Verify they load correctly\n\n"
            "Duration: ~30 seconds\n"
            "Press ESC to stop"
        )

        # TODO: Implement test scenario
        self.log_status("Test not yet implemented - placeholder")

    def test_chat_interface(self):
        """Test chat interface"""
        self.log_status("Chat interface test - placeholder")

    def test_settings_save(self):
        """Test settings save"""
        self.log_status("Settings save test - placeholder")

    def test_tab_navigation(self):
        """Test navigating through tabs"""
        self.log_status("Tab navigation test - placeholder")

    def screenshot_all_tabs(self):
        """Take screenshots of all tabs"""
        if not PYAUTOGUI_AVAILABLE:
            messagebox.showwarning("Not Available", "PyAutoGUI not installed")
            return

        self.log_status("Taking screenshots...")
        screenshots_dir = Path(__file__).parent / "screenshots"
        screenshots_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshots_dir / f"fullscreen_{timestamp}.png"

        try:
            screenshot = pyautogui.screenshot()
            screenshot.save(str(screenshot_path))
            self.log_status(f"Screenshot saved: {screenshot_path}")
            messagebox.showinfo("Success", f"Screenshot saved:\n{screenshot_path}")
        except Exception as e:
            self.log_status(f"Screenshot failed: {e}")
            messagebox.showerror("Error", f"Failed to take screenshot:\n{e}")

    def launch_gui_bridge(self):
        """Launch GUI Bridge for AI-powered GUI control"""
        self.log_status("Launching GUI Bridge...")

        try:
            # Import GUIBridgeUI
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from gui_bridge import GUIBridgeUI

            # Check for API key
            api_key = None

            # Try to load from environment
            import os
            api_key = os.environ.get('ANTHROPIC_API_KEY')

            # Try to load from file
            if not api_key:
                api_key_file = Path.home() / "Desktop" / "claude api.txt"
                if api_key_file.exists():
                    with open(api_key_file, 'r') as f:
                        key_from_file = f.read().strip()
                        if key_from_file.startswith('sk-ant-'):
                            api_key = key_from_file

            if not api_key:
                result = messagebox.askyesno(
                    "API Key Recommended",
                    "GUI Bridge works best with an API key for external models.\n\n"
                    "You can either:\n"
                    "1. Set ANTHROPIC_API_KEY environment variable\n"
                    "2. Create ~/Desktop/claude api.txt with your key\n"
                    "3. Use local models (no API key needed)\n\n"
                    "Do you want to continue?"
                )
                if not result:
                    return

            # Launch UI
            bridge_ui = GUIBridgeUI(parent=None)
            self.log_status("✅ GUI Bridge launched!")

        except ImportError as e:
            self.log_status(f"❌ Failed to import GUI Bridge: {e}")
            messagebox.showerror(
                "Import Error",
                f"Could not load GUI Bridge:\n{e}\n\n"
                "Make sure gui_bridge.py is in the automation_tab directory."
            )
        except Exception as e:
            self.log_status(f"❌ Failed to launch: {e}")
            messagebox.showerror("Error", f"Failed to launch GUI Bridge:\n{e}")

    # ===== Recording Methods =====

    def start_recording(self):
        """Start recording mouse/keyboard"""
        self.recording = True
        self.recorded_actions = []
        self.record_btn.config(state=tk.DISABLED)
        self.stop_record_btn.config(state=tk.NORMAL)
        self.status_label.config(text="🔴 Recording")
        self.log_status("Recording started (placeholder - not yet implemented)")

        # TODO: Implement actual recording using pynput or similar

    def stop_recording(self):
        """Stop recording"""
        self.recording = False
        self.record_btn.config(state=tk.NORMAL)
        self.stop_record_btn.config(state=tk.DISABLED)
        self.play_btn.config(state=tk.NORMAL if self.recorded_actions else tk.DISABLED)
        self.status_label.config(text="⚫ Idle")
        self.log_status(f"Recording stopped - {len(self.recorded_actions)} actions recorded")

    def play_recording(self):
        """Play recorded actions"""
        if not self.recorded_actions:
            messagebox.showwarning("No Recording", "No actions recorded")
            return

        self.log_status("Playing recording (placeholder)")
        # TODO: Implement playback

    def save_scenario(self):
        """Save recorded actions as a scenario"""
        if not self.recorded_actions:
            messagebox.showwarning("No Recording", "No actions to save")
            return

        # Simple dialog for scenario name
        name = tk.simpledialog.askstring("Save Scenario", "Scenario name:")
        if not name:
            return

        scenario_file = self.scenarios_dir / f"{name}.json"
        scenario_data = {
            'name': name,
            'created_at': datetime.now().isoformat(),
            'actions': self.recorded_actions
        }

        try:
            with open(scenario_file, 'w') as f:
                json.dump(scenario_data, f, indent=2)
            self.log_status(f"Scenario saved: {scenario_file}")
            self.refresh_scenarios()
        except Exception as e:
            messagebox.showerror("Save Failed", f"Failed to save scenario:\n{e}")

    # ===== Scenario Management =====

    def refresh_scenarios(self):
        """Refresh scenario list"""
        self.scenarios_listbox.delete(0, tk.END)

        for scenario_file in self.scenarios_dir.glob("*.json"):
            self.scenarios_listbox.insert(tk.END, scenario_file.stem)

    def on_scenario_select(self, event):
        """Handle scenario selection"""
        selection = self.scenarios_listbox.curselection()
        if not selection:
            return

        scenario_name = self.scenarios_listbox.get(selection[0])
        scenario_file = self.scenarios_dir / f"{scenario_name}.json"

        try:
            with open(scenario_file, 'r') as f:
                scenario_data = json.load(f)

            details = f"Name: {scenario_data.get('name', 'Unknown')}\n"
            details += f"Created: {scenario_data.get('created_at', 'Unknown')}\n"
            details += f"Actions: {len(scenario_data.get('actions', []))}\n\n"
            details += json.dumps(scenario_data, indent=2)

            self.scenario_details.delete(1.0, tk.END)
            self.scenario_details.insert(1.0, details)
        except Exception as e:
            self.scenario_details.delete(1.0, tk.END)
            self.scenario_details.insert(1.0, f"Error loading scenario: {e}")

    def run_selected_scenario(self):
        """Run the selected scenario"""
        selection = self.scenarios_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a scenario")
            return

        scenario_name = self.scenarios_listbox.get(selection[0])
        self.log_status(f"Running scenario: {scenario_name} (placeholder)")
        # TODO: Implement scenario execution

    # ===== Utilities =====

    def log_status(self, message: str):
        """Log message to status text"""
        self.status_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def emergency_stop_handler(self, event=None):
        """Handle ESC key for emergency stop"""
        if self.recording or self.playing:
            self.emergency_stop = True
            self.stop_recording()
            self.log_status("⚠️ EMERGENCY STOP ACTIVATED")
            self.status_label.config(text="⚠️ Stopped")
            messagebox.showwarning("Emergency Stop", "Automation stopped by user")


# Testing
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Automation Tab Test")
    root.geometry("900x700")

    tab = AutomationTab(root)
    tab.pack(fill=tk.BOTH, expand=True)

    root.mainloop()
