"""
Mode Selector Sub-Tab - Smart/Fast/Think mode selection
Controls model behavior and resource allocation for different use cases
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import log_message


class ModeSelectorTab(BaseTab):
    """Mode selection interface for Custom Code tab (Smart/Fast/Think)"""

    def __init__(self, parent, root, style, parent_tab):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.settings_file = Path(__file__).parent.parent / "mode_settings.json"
        self.settings = self.load_settings()
        self.param_vars = {}

    def create_ui(self):
        """Create the mode selector UI"""
        log_message("MODE_SELECTOR: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Header
        self.parent.rowconfigure(1, weight=1)  # Content
        self.parent.rowconfigure(2, weight=0)  # Buttons

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🎯 Mode Selection",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(
            header_frame,
            text="Choose model behavior mode",
            font=("Arial", 9),
            style='Config.TLabel'
        ).pack(side=tk.LEFT)

        # Scrollable content area
        self.create_scrollable_content()

        # Bottom buttons
        self.create_button_bar()

        # Set initial state for think time section
        self.on_mode_changed(self.mode_var.get())

        log_message("MODE_SELECTOR: UI created successfully")

    def create_scrollable_content(self):
        """Create scrollable content area with mode selection"""
        container = ttk.Frame(self.parent, style='Category.TFrame')
        container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        # Canvas for scrolling
        canvas = tk.Canvas(
            container,
            bg='#2b2b2b',
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview
        )
        self.scroll_frame = ttk.Frame(canvas, style='Category.TFrame')

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=self.scroll_frame,
            anchor="nw"
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Enable mousewheel scrolling
        self.bind_mousewheel_to_canvas(canvas)

        # Add mode selection sections
        self.create_mode_selection_section()
        self.create_mode_parameters_section()
        self.create_think_time_section()

    def create_mode_selection_section(self):
        """Mode Selection Radio Buttons"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="🎯 Select Mode",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Current mode variable
        self.mode_var = tk.StringVar(value=self.settings.get('current_mode', 'smart'))

        # Mode descriptions
        modes = [
            ("⚙️ Standard", "standard",
             "Standard settings for general use",
             "Best for: Testing without resource profiles, standard model contexts"),
            ("🚀 Fast", "fast",
             "Quick responses with minimal processing",
             "Best for: Simple queries, quick interactions, low resource usage"),
            ("🧠 Smart", "smart",
             "Balanced speed and intelligence",
             "Best for: General use, moderate complexity, balanced performance"),
            ("🤔 Think", "think",
             "Deep reasoning and thorough analysis",
             "Best for: Complex problems, detailed analysis, maximum accuracy")
        ]

        for emoji_name, mode_val, description, best_for in modes:
            # Mode frame
            mode_frame = ttk.Frame(frame, style='Category.TFrame')
            mode_frame.pack(fill=tk.X, padx=10, pady=5)

            # Radio button with emoji and name
            radio = ttk.Radiobutton(
                mode_frame,
                text=emoji_name,
                variable=self.mode_var,
                value=mode_val,
                command=lambda m=mode_val: self.on_mode_changed(m),
                style='TRadiobutton'
            )
            radio.pack(side=tk.LEFT, padx=(0, 10))

            # Description container
            desc_frame = ttk.Frame(mode_frame, style='Category.TFrame')
            desc_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ttk.Label(
                desc_frame,
                text=description,
                font=("Arial", 9, "bold"),
                style='Config.TLabel'
            ).pack(anchor=tk.W)

            ttk.Label(
                desc_frame,
                text=best_for,
                font=("Arial", 8),
                style='Config.TLabel',
                foreground='#888888'
            ).pack(anchor=tk.W)

        # Add spacing
        ttk.Label(frame, text="", style='Config.TLabel').pack(pady=5)

    def create_mode_parameters_section(self):
        """Display current mode parameters"""
        frame = ttk.LabelFrame(
            self.scroll_frame,
            text="⚙️ Mode Parameters",
            style='TLabelframe'
        )
        frame.pack(fill=tk.X, padx=10, pady=10)

        # Info label
        ttk.Label(
            frame,
            text="Parameters are automatically configured based on selected mode:",
            font=("Arial", 9),
            style='Config.TLabel'
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Parameters display frame
        self.params_frame = ttk.Frame(frame, style='Category.TFrame')
        self.params_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        # Update parameters display
        self.update_parameters_display()

    def create_think_time_section(self):
        """Think Time Configuration (only relevant for Think mode)"""
        self.think_time_frame = ttk.LabelFrame(
            self.scroll_frame,
            text="⏱️ Think Mode Time Settings",
            style='TLabelframe'
        )
        self.think_time_frame.pack(fill=tk.X, padx=10, pady=10)

        # Store reference to frame for show/hide
        frame = self.think_time_frame

        # Info label
        ttk.Label(
            frame,
            text="Configure minimum and maximum think time allowance for Think mode:",
            font=("Arial", 9),
            style='Config.TLabel'
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Settings grid
        settings_frame = ttk.Frame(frame, style='Category.TFrame')
        settings_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        # Minimum think time
        ttk.Label(
            settings_frame,
            text="Minimum Think Time (seconds):",
            font=("Arial", 9),
            style='Config.TLabel'
        ).grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)

        self.think_time_min_var = tk.StringVar(
            value=str(self.settings.get('think_time_min_seconds', 30))
        )
        ttk.Entry(
            settings_frame,
            textvariable=self.think_time_min_var,
            font=("Arial", 9),
            width=10
        ).grid(row=0, column=1, sticky=tk.W, padx=(5, 10), pady=5)

        ttk.Label(
            settings_frame,
            text="(Default: 30s)",
            font=("Arial", 8),
            style='Config.TLabel',
            foreground='#888888'
        ).grid(row=0, column=2, sticky=tk.W, pady=5)

        # Maximum think time
        ttk.Label(
            settings_frame,
            text="Maximum Think Time (seconds):",
            font=("Arial", 9),
            style='Config.TLabel'
        ).grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)

        self.think_time_max_var = tk.StringVar(
            value=str(self.settings.get('think_time_max_seconds', 300))
        )
        ttk.Entry(
            settings_frame,
            textvariable=self.think_time_max_var,
            font=("Arial", 9),
            width=10
        ).grid(row=1, column=1, sticky=tk.W, padx=(5, 10), pady=5)

        ttk.Label(
            settings_frame,
            text="(Default: 300s / 5 minutes)",
            font=("Arial", 8),
            style='Config.TLabel',
            foreground='#888888'
        ).grid(row=1, column=2, sticky=tk.W, pady=5)

        # Note label
        ttk.Label(
            frame,
            text="ℹ️ These settings only apply when Think mode is active",
            font=("Arial", 8),
            style='Config.TLabel',
            foreground='#6699cc'
        ).pack(anchor=tk.W, padx=10, pady=(0, 10))

    def update_parameters_display(self):
        """Update the parameters display based on current mode"""
        # Clear existing
        for widget in self.params_frame.winfo_children():
            widget.destroy()

        self.param_vars = {}  # Reset for the new mode

        mode = self.mode_var.get()
        # Load saved parameters or defaults
        if 'mode_parameters' in self.settings and mode in self.settings['mode_parameters']:
            params = self.settings['mode_parameters'][mode]
        else:
            params = self.get_default_mode_parameters(mode)

        # Define parameter types and controls
        param_configs = {
            'Resource Usage': {
                'type': 'choice',
                'options': ['Default', '25% (conservative)', '50% (balanced)', '75% (aggressive)']
            },
            'Max Context Tokens': {
                'type': 'numeric',
                'min': 1024,
                'max': 16384,
                'step': 512
            },
            'Generation Step': {
                'type': 'numeric_suffix',
                'suffix': 'tokens',
                'min': 8,
                'max': 128,
                'step': 8
            },
            'CPU Threads': {
                'type': 'choice',
                'options': ['Default', 'Minimal (1-2)', 'Half of available', 'Most available (n-2)']
            },
            'Token Caps (Reasoning)': {
                'type': 'numeric',
                'min': 100,
                'max': 2000,
                'step': 50
            },
            'Token Caps (Standard)': {
                'type': 'numeric',
                'min': 50,
                'max': 1000,
                'step': 50
            },
            'Token Caps (Structured)': {
                'type': 'numeric',
                'min': 50,
                'max': 500,
                'step': 25
            },
            'Quality Mode': {
                'type': 'choice',
                'options': ['Standard', 'Fast', 'Auto/Smart', 'Think (with verification)']
            },
            'Think Time': {
                'type': 'choice',
                'options': ['Dynamic (configurable)', 'Fixed', 'Adaptive']
            }
        }

        # Display each parameter
        row = 0
        for param_name, param_value in params.items():
            if param_name == 'Description':
                continue  # Skip description field

            # Parameter name
            ttk.Label(
                self.params_frame,
                text=f"{param_name}:",
                font=("Arial", 9, "bold"),
                style='Config.TLabel'
            ).grid(row=row, column=0, sticky=tk.W, padx=(10, 5), pady=5)

            # Get parameter config
            config = param_configs.get(param_name, {'type': 'text'})

            if config['type'] == 'choice':
                # Dropdown for choice parameters
                var = tk.StringVar(value=str(param_value))
                self.param_vars[param_name] = var

                combo = ttk.Combobox(
                    self.params_frame,
                    textvariable=var,
                    values=config['options'],
                    state='readonly',
                    font=("Arial", 9),
                    width=35
                )
                combo.grid(row=row, column=1, columnspan=3, sticky=tk.W, padx=(5, 10), pady=5)

            elif config['type'] in ['numeric', 'numeric_suffix']:
                # Numeric value with increment/decrement buttons
                control_frame = ttk.Frame(self.params_frame, style='Category.TFrame')
                control_frame.grid(row=row, column=1, columnspan=3, sticky=tk.W, padx=(5, 10), pady=5)

                # Extract numeric value
                numeric_value = param_value
                if config['type'] == 'numeric_suffix':
                    # Remove suffix (e.g., "24 tokens" -> 24)
                    numeric_value = str(param_value).split()[0]

                var = tk.StringVar(value=str(numeric_value))
                self.param_vars[param_name] = var

                # Decrement button
                ttk.Button(
                    control_frame,
                    text="◀",
                    width=3,
                    command=lambda v=var, cfg=config: self.decrement_value(v, cfg),
                    style='Action.TButton'
                ).pack(side=tk.LEFT, padx=(0, 2))

                # Value entry
                entry = ttk.Entry(
                    control_frame,
                    textvariable=var,
                    font=("Arial", 9),
                    width=10,
                    justify='center'
                )
                entry.pack(side=tk.LEFT, padx=2)

                # Increment button
                ttk.Button(
                    control_frame,
                    text="▶",
                    width=3,
                    command=lambda v=var, cfg=config: self.increment_value(v, cfg),
                    style='Action.TButton'
                ).pack(side=tk.LEFT, padx=(2, 5))

                # Suffix label if applicable
                if config['type'] == 'numeric_suffix':
                    ttk.Label(
                        control_frame,
                        text=config['suffix'],
                        font=("Arial", 9),
                        style='Config.TLabel'
                    ).pack(side=tk.LEFT, padx=(2, 0))

            else:
                # Text entry for other parameters
                var = tk.StringVar(value=str(param_value))
                self.param_vars[param_name] = var
                ttk.Entry(
                    self.params_frame,
                    textvariable=var,
                    font=("Arial", 9),
                    width=35
                ).grid(row=row, column=1, columnspan=3, sticky=tk.W, padx=(5, 10), pady=5)

            row += 1

    def increment_value(self, var, config):
        """Increment numeric parameter value"""
        try:
            current = int(var.get())
            step = config.get('step', 1)
            max_val = config.get('max', float('inf'))
            new_val = min(current + step, max_val)
            var.set(str(new_val))
        except ValueError:
            pass

    def decrement_value(self, var, config):
        """Decrement numeric parameter value"""
        try:
            current = int(var.get())
            step = config.get('step', 1)
            min_val = config.get('min', 0)
            new_val = max(current - step, min_val)
            var.set(str(new_val))
        except ValueError:
            pass

    def get_default_mode_parameters(self, mode):
        """Get parameters for a specific mode based on OpenCode v1.2 implementation"""
        mode_configs = {
            'standard': {
                'Resource Usage': 'Default',
                'Max Context Tokens': '4096',
                'Generation Step': '24 tokens',
                'CPU Threads': 'Default',
                'Token Caps (Reasoning)': '300',
                'Token Caps (Standard)': '200',
                'Token Caps (Structured)': '150',
                'Quality Mode': 'Standard',
                'Description': 'Standard settings for general use, without resource profiles.'
            },
            'fast': {
                'Resource Usage': '25% (conservative)',
                'Max Context Tokens': '3072',
                'Generation Step': '16 tokens',
                'CPU Threads': 'Minimal (1-2)',
                'Token Caps (Reasoning)': '200',
                'Token Caps (Standard)': '120',
                'Token Caps (Structured)': '90',
                'Quality Mode': 'Fast',
                'Description': 'Quick responses, minimal processing'
            },
            'smart': {
                'Resource Usage': '50% (balanced)',
                'Max Context Tokens': '5120',
                'Generation Step': '32 tokens',
                'CPU Threads': 'Half of available',
                'Token Caps (Reasoning)': '450',
                'Token Caps (Standard)': '300',
                'Token Caps (Structured)': '220',
                'Quality Mode': 'Auto/Smart',
                'Description': 'Balanced speed and intelligence'
            },
            'think': {
                'Resource Usage': '75% (aggressive)',
                'Max Context Tokens': '8192',
                'Generation Step': '48 tokens',
                'CPU Threads': 'Most available (n-2)',
                'Token Caps (Reasoning)': '900',
                'Token Caps (Standard)': '600',
                'Token Caps (Structured)': '350',
                'Quality Mode': 'Think (with verification)',
                'Think Time': 'Dynamic (configurable)',
                'Description': 'Deep reasoning, thorough analysis'
            }
        }

        return mode_configs.get(mode, mode_configs['smart'])

    def on_mode_changed(self, mode):
        """Handle mode change"""
        # Update parameters display
        self.update_parameters_display()

        # Show/hide think time section
        if mode == 'think':
            self.think_time_frame.pack(fill=tk.X, padx=10, pady=10)
        else:
            self.think_time_frame.pack_forget()

        # Update settings
        self.settings['current_mode'] = mode
        self.settings['mode_parameters'] = self.get_default_mode_parameters(mode)

        # Notify parent tab if it has a method to handle mode changes
        if hasattr(self.parent_tab, 'on_mode_changed'):
            self.parent_tab.on_mode_changed(mode, self.settings['mode_parameters'])

        # Notify settings tab about mode change to update Advanced settings
        # Navigate: parent_tab (custom_code_tab) → settings_interface → on_mode_changed
        if hasattr(self.parent_tab, 'settings_interface'):
            if hasattr(self.parent_tab.settings_interface, 'on_mode_changed'):
                self.parent_tab.settings_interface.on_mode_changed(mode)
                log_message(f"MODE_SELECTOR: Notified Advanced Settings of mode change to {mode}")

    def create_button_bar(self):
        """Create bottom button bar"""
        button_frame = ttk.Frame(self.parent, style='Category.TFrame')
        button_frame.grid(row=2, column=0, sticky=tk.EW, padx=10, pady=(0, 10))

        ttk.Button(
            button_frame,
            text="💾 Save Mode",
            command=self.save_settings,
            style='Action.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="↺ Reset Current to Default",
            command=self.reset_current_mode_to_default,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="🔄 Reset to Smart",
            command=self.reset_to_smart,
            style='Select.TButton'
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            button_frame,
            text="Mode settings saved to: mode_settings.json",
            style='Config.TLabel',
            font=("Arial", 8)
        ).pack(side=tk.RIGHT, padx=5)

    def load_settings(self):
        """Load mode settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    log_message("MODE_SELECTOR: Settings loaded successfully")
                    return settings
            except Exception as e:
                log_message(f"MODE_SELECTOR ERROR: Failed to load settings: {e}")

        # Return defaults
        return self.get_default_settings()

    def get_default_settings(self):
        """Get default mode settings"""
        default_mode = 'smart'
        return {
            'current_mode': default_mode,
            'mode_parameters': self.get_default_mode_parameters(default_mode),
            'think_time_min_seconds': 30,
            'think_time_max_seconds': 300
        }

    def save_settings(self):
        """Save mode settings to file"""
        try:
            # Update settings with current mode
            current_mode = self.mode_var.get()
            self.settings['current_mode'] = current_mode

            # Save parameters from the UI
            if 'mode_parameters' not in self.settings:
                self.settings['mode_parameters'] = {}

            # Process parameters and add back any suffixes
            saved_params = {}
            for key, var in self.param_vars.items():
                value = var.get()
                # Add suffix back for Generation Step
                if key == 'Generation Step' and 'tokens' not in value:
                    saved_params[key] = f"{value} tokens"
                else:
                    saved_params[key] = value

            # Add Description back from defaults
            default_params = self.get_default_mode_parameters(current_mode)
            if 'Description' in default_params:
                saved_params['Description'] = default_params['Description']

            self.settings['mode_parameters'][current_mode] = saved_params

            # Save think time settings
            try:
                self.settings['think_time_min_seconds'] = int(self.think_time_min_var.get())
                self.settings['think_time_max_seconds'] = int(self.think_time_max_var.get())
            except ValueError:
                messagebox.showwarning(
                    "Invalid Input",
                    "Think time values must be integers. Using defaults (30s min, 300s max)."
                )
                self.settings['think_time_min_seconds'] = 30
                self.settings['think_time_max_seconds'] = 300

            # Save to file
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)

            log_message("MODE_SELECTOR: Settings saved successfully")

            # Notify Advanced Settings tab about mode change AFTER save
            if hasattr(self.parent_tab, 'settings_interface'):
                if hasattr(self.parent_tab.settings_interface, 'on_mode_changed'):
                    self.parent_tab.settings_interface.on_mode_changed(current_mode)
                    log_message(f"MODE_SELECTOR: Notified Advanced Settings of mode save to {current_mode}")

            messagebox.showinfo("Mode Saved", f"Mode '{self.mode_var.get()}' has been saved successfully!")

            # Apply to chat interface if available
            self.apply_mode_to_chat()

        except Exception as e:
            error_msg = f"Failed to save mode settings: {str(e)}"
            log_message(f"MODE_SELECTOR ERROR: {error_msg}")
            messagebox.showerror("Save Error", error_msg)

    def apply_mode_to_chat(self):
        """Apply current mode settings to chat interface"""
        if hasattr(self.parent_tab, 'chat_interface') and self.parent_tab.chat_interface:
            mode = self.mode_var.get()
            params = self.settings.get('mode_parameters', {}).get(mode, self.get_default_mode_parameters(mode))

            log_message(f"MODE_SELECTOR: Applying {mode} mode to chat interface")

            # If chat interface has a method to update mode parameters
            if hasattr(self.parent_tab.chat_interface, 'set_mode_parameters'):
                self.parent_tab.chat_interface.set_mode_parameters(mode, params)

    def reset_current_mode_to_default(self):
        """Reset current mode parameters to default values"""
        current_mode = self.mode_var.get()
        mode_names = {
            'standard': 'Standard',
            'fast': 'Fast',
            'smart': 'Smart',
            'think': 'Think'
        }

        if messagebox.askyesno(
            "Reset to Default",
            f"Reset {mode_names.get(current_mode, current_mode)} mode parameters to default values?"
        ):
            # Get default parameters for current mode
            default_params = self.get_default_mode_parameters(current_mode)

            # Update the settings with defaults
            if 'mode_parameters' not in self.settings:
                self.settings['mode_parameters'] = {}
            self.settings['mode_parameters'][current_mode] = default_params

            # Refresh the display
            self.update_parameters_display()

            log_message(f"MODE_SELECTOR: {current_mode} mode reset to default")
            messagebox.showinfo("Reset Complete", f"{mode_names.get(current_mode, current_mode)} mode has been reset to default settings")

    def reset_to_smart(self):
        """Reset mode to Smart (default)"""
        if messagebox.askyesno(
            "Reset to Smart Mode",
            "Reset to Smart mode (balanced settings)?"
        ):
            self.mode_var.set('smart')
            self.on_mode_changed('smart')
            self.update_parameters_display()

            log_message("MODE_SELECTOR: Mode reset to Smart")
            messagebox.showinfo("Reset Complete", "Mode has been reset to Smart (balanced)")

    def refresh(self):
        """Refresh the mode selector tab"""
        log_message("MODE_SELECTOR: Refreshing...")
        self.settings = self.load_settings()
        self.mode_var.set(self.settings.get('current_mode', 'smart'))
        self.think_time_min_var.set(str(self.settings.get('think_time_min_seconds', 30)))
        self.think_time_max_var.set(str(self.settings.get('think_time_max_seconds', 300)))
        self.update_parameters_display()
