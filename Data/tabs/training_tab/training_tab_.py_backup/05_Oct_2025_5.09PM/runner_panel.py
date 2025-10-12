import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure the Data directory is in the Python path for module imports
script_dir = os.path.dirname(__file__)
data_dir = os.path.abspath(os.path.join(script_dir, '..', '..', '..', 'Data'))
if data_dir not in sys.path:
    sys.path.insert(0, data_dir)

# Assuming config.py is in the Data directory
from config import DATA_DIR
from logger_util import log_message, get_log_file_path
import json

class RunnerPanel:
    """Panel for running training scripts with live output monitoring"""

    def __init__(self, parent, style, training_tab_instance):
        self.parent = parent
        self.style = style
        self.training_tab_instance = training_tab_instance
        self.process = None
        self.TRAINING_DATA_SETS_DIR = DATA_DIR.parent / "Training_Data-Sets"

        # Runner variables
        self.selected_script_var = tk.StringVar()
        self.auto_restart_var = tk.BooleanVar(value=False)
        self.run_delay_var = tk.IntVar(value=0)
        self.max_runs_var = tk.IntVar(value=1)
        self.max_time_var = tk.IntVar(value=120)  # Max training time in minutes
        self.save_checkpoints_var = tk.BooleanVar(value=True)
        self.checkpoint_interval_var = tk.IntVar(value=500)  # Steps between checkpoints
        self.early_stop_var = tk.BooleanVar(value=False)
        self.early_stop_patience_var = tk.IntVar(value=3)
        self.use_mixed_precision_var = tk.BooleanVar(value=True)
        self.gradient_accumulation_var = tk.IntVar(value=16)  # Increased to 16 for 8GB RAM
        self.warmup_steps_var = tk.IntVar(value=5)  # Reduced default to 5
        self.max_cpu_threads_var = tk.IntVar(value=2)  # Limit to 2 threads for 8GB RAM
        self.max_ram_percent_var = tk.IntVar(value=70)  # Max 70% RAM for 8GB systems
        self.current_run_count = 0
        self.script_running = False

        # Load saved defaults on startup
        self.load_runner_defaults(initial_load=True)

    def update_training_model_display(self):
        """Update the training model display based on current config."""
        if not hasattr(self.training_tab_instance, 'config_panel'):
            self.training_model_label.config(text="Not Set", foreground='#ff6b6b')
            return

        config_params = self.training_tab_instance.config_panel.get_config_params()
        model_name = config_params.get("model_name", "Not Set")

        if model_name and model_name != "Not Set":
            if "/" in model_name:
                display_name = model_name.split("/")[-1]
            else:
                display_name = model_name
            self.training_model_label.config(text=display_name, foreground='#51cf66')
        else:
            self.training_model_label.config(text="Not Set", foreground='#ff6b6b')

    def create_ui(self):
        log_message("RUNNER: create_ui called")
        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=1)

        # --- Left side: Script output display ---
        output_frame = ttk.Frame(self.parent, style='Category.TFrame')
        output_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=10, pady=10)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(1, weight=1)

        header_frame = ttk.Frame(output_frame, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, pady=5)
        ttk.Label(header_frame, text="📺 Training Output", font=("Arial", 12, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT, padx=(0, 20))
        model_display_frame = ttk.Frame(header_frame, style='Category.TFrame')
        model_display_frame.pack(side=tk.LEFT)
        ttk.Label(model_display_frame, text="Training Model:", font=("Arial", 10, "bold"), style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.training_model_label = ttk.Label(model_display_frame, text="Not Set", font=("Arial", 10), style='Config.TLabel', foreground='#ff6b6b')
        self.training_model_label.pack(side=tk.LEFT)

        self.runner_output = scrolledtext.ScrolledText(output_frame, font=("Courier", 9), wrap=tk.WORD, state=tk.DISABLED, relief='flat', borderwidth=0, highlightthickness=0, bg='#1e1e1e', fg='#00ff00')
        self.runner_output.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)

        # --- Right side: Runner controls (scrollable) ---
        controls_container = ttk.Frame(self.parent, style='Category.TFrame')
        controls_container.grid(row=0, column=1, sticky=tk.NSEW, padx=10, pady=10)
        controls_container.columnconfigure(0, weight=1)
        controls_container.rowconfigure(1, weight=1)

        controls_header = ttk.Frame(controls_container, style='Category.TFrame')
        controls_header.grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.EW, padx=5)
        ttk.Label(controls_header, text="🎮 Controls", font=("Arial", 11, "bold"), style='CategoryPanel.TLabel').pack(side=tk.LEFT)
        ttk.Button(controls_header, text="Load Defaults", command=self.load_runner_defaults, style='Select.TButton').pack(side=tk.RIGHT, padx=2)
        ttk.Button(controls_header, text="Save Defaults", command=self.save_runner_defaults, style='Select.TButton').pack(side=tk.RIGHT, padx=2)

        self.controls_canvas = tk.Canvas(controls_container, bg="#2b2b2b", highlightthickness=0)
        self.controls_canvas.bind('<Enter>', self._bind_mousewheel)
        self.controls_canvas.bind('<Leave>', self._unbind_mousewheel)
        controls_scrollbar = ttk.Scrollbar(controls_container, orient="vertical", command=self.controls_canvas.yview)
        controls_frame = ttk.Frame(self.controls_canvas, style='Category.TFrame')
        controls_frame.columnconfigure(0, weight=1)
        controls_frame.bind("<Configure>", lambda e: self.controls_canvas.configure(scrollregion=self.controls_canvas.bbox("all")))
        canvas_window = self.controls_canvas.create_window((0, 0), window=controls_frame, anchor="nw")
        self.controls_canvas.configure(yscrollcommand=controls_scrollbar.set)
        self.controls_canvas.bind("<Configure>", lambda e: self.controls_canvas.itemconfig(canvas_window, width=e.width))
        self.controls_canvas.grid(row=1, column=0, sticky='nsew')
        controls_scrollbar.grid(row=1, column=1, sticky='ns')

        current_row = 0
        time_section = ttk.LabelFrame(controls_frame, text="⏱️ Time Limits", style='TLabelframe')
        time_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        max_time_frame = ttk.Frame(time_section)
        max_time_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(max_time_frame, text="Max Time (min):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(max_time_frame, from_=1, to=1440, textvariable=self.max_time_var, width=8).pack(side=tk.LEFT)
        max_runs_frame = ttk.Frame(time_section)
        max_runs_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(max_runs_frame, text="Max Runs:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(max_runs_frame, from_=1, to=100, textvariable=self.max_runs_var, width=8).pack(side=tk.LEFT)
        delay_frame = ttk.Frame(time_section)
        delay_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(delay_frame, text="Delay (sec):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(delay_frame, from_=0, to=300, textvariable=self.run_delay_var, width=8).pack(side=tk.LEFT)

        checkpoint_section = ttk.LabelFrame(controls_frame, text="💾 Checkpoints", style='TLabelframe')
        checkpoint_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(checkpoint_section, text="Save checkpoints", variable=self.save_checkpoints_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        checkpoint_interval_frame = ttk.Frame(checkpoint_section)
        checkpoint_interval_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(checkpoint_interval_frame, text="Interval (steps):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(checkpoint_interval_frame, from_=10, to=10000, increment=10, textvariable=self.checkpoint_interval_var, width=8).pack(side=tk.LEFT)

        optimization_section = ttk.LabelFrame(controls_frame, text="⚡ Optimization", style='TLabelframe')
        optimization_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(optimization_section, text="Mixed precision (FP16)", variable=self.use_mixed_precision_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        grad_accum_frame = ttk.Frame(optimization_section)
        grad_accum_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(grad_accum_frame, text="Gradient Accum:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(grad_accum_frame, from_=1, to=32, textvariable=self.gradient_accumulation_var, width=8).pack(side=tk.LEFT)
        warmup_frame = ttk.Frame(optimization_section)
        warmup_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(warmup_frame, text="Warmup Steps:", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(warmup_frame, from_=0, to=1000, increment=10, textvariable=self.warmup_steps_var, width=8).pack(side=tk.LEFT)

        early_stop_section = ttk.LabelFrame(controls_frame, text="🛑 Early Stopping", style='TLabelframe')
        early_stop_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(early_stop_section, text="Enable early stopping", variable=self.early_stop_var, style='Category.TCheckbutton').pack(padx=10, pady=5, anchor=tk.W)
        patience_frame = ttk.Frame(early_stop_section)
        patience_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(patience_frame, text="Patience (epochs):", style='Config.TLabel', width=15).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Spinbox(patience_frame, from_=1, to=20, textvariable=self.early_stop_patience_var, width=8).pack(side=tk.LEFT)

        restart_section = ttk.LabelFrame(controls_frame, text="🔄 Auto-Restart", style='TLabelframe')
        restart_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=5); current_row += 1
        ttk.Checkbutton(restart_section, text="Auto-restart on completion", variable=self.auto_restart_var, style='Category.TCheckbutton').pack(padx=10, pady=10, anchor=tk.W)

        actions_section = ttk.LabelFrame(controls_frame, text="🎮 Actions", style='TLabelframe')
        actions_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=10); current_row += 1
        self.start_button = ttk.Button(actions_section, text="▶️ Start Training", command=self.start_runner_training, style='Action.TButton')
        self.start_button.pack(fill=tk.X, padx=10, pady=5)
        self.stop_button = ttk.Button(actions_section, text="⏹️ Stop Training", command=self.stop_runner_training, style='Select.TButton', state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(actions_section, text="🗑️ Clear Output", command=self.clear_runner_output, style='Select.TButton').pack(fill=tk.X, padx=10, pady=5)

        status_section = ttk.LabelFrame(controls_frame, text="📊 Status", style='TLabelframe')
        status_section.grid(row=current_row, column=0, sticky=tk.EW, padx=5, pady=10); current_row += 1
        self.runner_status_label = ttk.Label(status_section, text="⚪ Idle", style='Config.TLabel')
        self.runner_status_label.pack(padx=10, pady=10)
        self.runner_progress_label = ttk.Label(status_section, text="Run 0 of 0", style='Config.TLabel')
        self.runner_progress_label.pack(padx=10, pady=(0, 10))

        self.update_training_model_display()

    def start_runner_training(self):
        log_message("RUNNER: start_runner_training called")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.runner_status_label.config(text="🟢 Running")
        self.current_run_count = 0
        self.script_running = True

        self.append_runner_output(f"{ '='*60}\n")
        self.append_runner_output(f"  STARTING TRAINING SESSION\n")
        self.append_runner_output(f"{ '='*60}\n\n")

        self.append_runner_output(f"⏱️  TIME LIMITS:\n")
        self.append_runner_output(f"   • Max Training Time: {self.max_time_var.get()} minutes\n")
        self.append_runner_output(f"   • Max Runs: {self.max_runs_var.get()}\n")
        self.append_runner_output(f"   • Delay Between Runs: {self.run_delay_var.get()} seconds\n\n")
        self.append_runner_output(f"💾 CHECKPOINTS:\n")
        self.append_runner_output(f"   • Save Checkpoints: {self.save_checkpoints_var.get()}\n")
        self.append_runner_output(f"   • Checkpoint Interval: {self.checkpoint_interval_var.get()} steps\n\n")
        self.append_runner_output(f"⚡ OPTIMIZATION:\n")
        self.append_runner_output(f"   • Mixed Precision (FP16): {self.use_mixed_precision_var.get()}\n")
        self.append_runner_output(f"   • Gradient Accumulation: {self.gradient_accumulation_var.get()} steps\n")
        self.append_runner_output(f"   • Warmup Steps: {self.warmup_steps_var.get()}\n\n")
        self.append_runner_output(f"🛑 EARLY STOPPING:\n")
        self.append_runner_output(f"   • Enabled: {self.early_stop_var.get()}\n")
        if self.early_stop_var.get():
            self.append_runner_output(f"   • Patience: {self.early_stop_patience_var.get()} epochs\n")
        self.append_runner_output(f"\n")
        self.append_runner_output(f"🔄 AUTO-RESTART:\n")
        self.append_runner_output(f"   • Enabled: {self.auto_restart_var.get()}\n\n")
        self.append_runner_output(f"{ '='*60}\n\n")

        self.log_output("Starting training process...\n", "system")
        log_message("RUNNER: Attempting to get selected category and script.")

        selected_scripts = []
        for category_name, scripts in self.training_tab_instance.script_vars.items():
            for script_name, var in scripts.items():
                if var.get():
                    selected_scripts.append((category_name, script_name))

        self.log_output(f"🔍 Debug Info:\n", "system")
        self.log_output(f"   Selected scripts from right panel: {len(selected_scripts)}\n", "system")
        for cat, script in selected_scripts:
            self.log_output(f"      • {cat}/{script}\n", "system")
        self.log_output(f"\n", "system")

        if not selected_scripts:
            self.log_output("❌ Error: Please select at least one training script from the right panel.\n", "error")
            self.log_output("   Use the checkboxes in 'Training Scripts' panel →\n", "error")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.runner_status_label.config(text="🔴 Error")
            return

        selected_category, selected_script = selected_scripts[0]
        if len(selected_scripts) > 1:
            self.log_output(f"ℹ️  Note: {len(selected_scripts)} scripts selected. Running first one: {selected_script}\n\n", "system")

        script_path = self.TRAINING_DATA_SETS_DIR / selected_category / selected_script
        log_message(f"RUNNER: script_path={script_path}")

        if not script_path.exists():
            self.log_output(f"Error: Training script not found at {script_path}\n", "error")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.runner_status_label.config(text="🔴 Error")
            log_message("RUNNER: Validation failed: script_path does not exist.")
            return

        log_message("RUNNER: Attempting to get config parameters.")
        config_params = self.training_tab_instance.config_panel.get_config_params()
        log_message(f"RUNNER: config_params={config_params}")
        if not config_params:
            self.log_output("Error: Could not retrieve training configuration parameters.\n", "error")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.runner_status_label.config(text="🔴 Error")
            log_message("RUNNER: Validation failed: config_params empty.")
            return

        log_message("RUNNER: Getting selected datasets from GUI...")
        selected_data = self.training_tab_instance.get_selected_scripts()
        selected_datasets = [str(item['path']) for item in selected_data.get('jsonl_files', [])]

        if selected_datasets:
            self.log_output(f"Info: Training with {len(selected_datasets)} selected JSONL file(s).\n", "system")
            log_message(f"RUNNER: Selected datasets: {selected_datasets}")
        else:
            self.log_output("⚠️  Warning: No JSONL files selected! Training may use category defaults.\n", "warning")
            log_message("RUNNER: No datasets selected via GUI")

        log_message("RUNNER: Preparing environment variables.")
        env_vars = os.environ.copy()
        env_vars["BASE_MODEL"] = config_params.get("model_name", "")
        env_vars["TRAINING_EPOCHS"] = str(config_params.get("num_epochs", 3))
        env_vars["TRAINING_BATCH_SIZE"] = str(config_params.get("batch_size", 2))
        env_vars["TRAINING_LEARNING_RATE"] = str(config_params.get("learning_rate", 2e-4))
        env_vars["TRAINING_MAX_SEQ_LENGTH"] = str(config_params.get("max_seq_length", 2048))
        env_vars["TRAINING_LORA_R"] = str(config_params.get("lora_r", 16))
        env_vars["TRAINING_LORA_ALPHA"] = str(config_params.get("lora_alpha", 16))
        env_vars["TRAINING_DATA_FILES"] = ",".join(selected_datasets) if selected_datasets else ""

        # Pass the main log file path to the subprocess
        env_vars["GEMINI_LOG_FILE"] = get_log_file_path()

        env_vars["RUNNER_MAX_TIME"] = str(self.max_time_var.get())
        env_vars["RUNNER_SAVE_CHECKPOINTS"] = str(self.save_checkpoints_var.get())
        env_vars["RUNNER_CHECKPOINT_INTERVAL"] = str(self.checkpoint_interval_var.get())
        env_vars["RUNNER_MIXED_PRECISION"] = str(self.use_mixed_precision_var.get())
        env_vars["RUNNER_GRADIENT_ACCUMULATION"] = str(self.gradient_accumulation_var.get())
        env_vars["RUNNER_WARMUP_STEPS"] = str(self.warmup_steps_var.get())
        env_vars["RUNNER_EARLY_STOPPING"] = str(self.early_stop_var.get())
        env_vars["RUNNER_EARLY_STOPPING_PATIENCE"] = str(self.early_stop_patience_var.get())
        env_vars["RUNNER_MAX_CPU_THREADS"] = str(self.max_cpu_threads_var.get())
        env_vars["RUNNER_MAX_RAM_PERCENT"] = str(self.max_ram_percent_var.get())
        log_message("RUNNER: Environment variables prepared.")

        command = [sys.executable, str(script_path)]
        self.log_output(f"Executing command: {' '.join(command)}\n", "system")
        self.log_output(f"With environment variables:\n", "system")
        for key, value in env_vars.items():
            if key.startswith("TRAINING_") or key.startswith("RUNNER_") or key == "BASE_MODEL":
                self.log_output(f"  {key}={value}\n", "system")
        self.log_output("\n", "system")

        log_message("RUNNER: Calling _run_training_process in a new thread.")
        self.training_thread = threading.Thread(target=self._run_training_process, args=(command, env_vars))
        self.training_thread.daemon = True
        self.training_thread.start()

    def _run_training_process(self, command, env_vars):
        log_message(f"RUNNER: _run_training_process called with command: {command}")
        try:
            preexec_fn = os.setsid
            self.process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                bufsize=1, universal_newlines=True, env=env_vars, preexec_fn=preexec_fn
            )
            log_message(f"RUNNER: Subprocess started with PID: {self.process.pid}")
            for line in self.process.stdout:
                log_message(f"RUNNER STDOUT: {line.strip()}")
                self.log_output(line, "stdout")
            self.process.wait()
            log_message(f"RUNNER: Subprocess finished with return code: {self.process.returncode}")
            if self.process.returncode == 0:
                self.log_output("\nTraining process completed successfully.\n", "system")
                self.training_tab_instance.post_training_actions()
            else:
                self.log_output(f"\nTraining process failed with exit code {self.process.returncode}.\n", "error")
        except Exception as e:
            log_message(f"RUNNER ERROR: Error in _run_training_process: {e}")
            self.log_output(f"\nError running training process: {e}\n", "error")
        finally:
            self.process = None
            self.parent.after(100, lambda: self.start_button.config(state=tk.NORMAL))
            self.parent.after(100, lambda: self.stop_button.config(state=tk.DISABLED))
            self.parent.after(100, lambda: self.runner_status_label.config(text="⚪ Idle"))

    def stop_runner_training(self):
        log_message("RUNNER: stop_runner_training called")
        if self.process and self.process.poll() is None:
            self.log_output("Attempting to stop training process...\n", "system")
            try:
                os.killpg(os.getpgid(self.process.pid), subprocess.signal.SIGTERM)
                self.process.wait(timeout=5)
                self.log_output("Training process stopped.\n", "system")
                log_message("RUNNER: Training process stopped successfully.")
            except Exception as e:
                self.log_output(f"Error stopping process: {e}\n", "error")
                log_message(f"RUNNER ERROR: Error stopping process: {e}")
            finally:
                self.process = None
        else:
            self.log_output("No active training process to stop.\n", "warning")
            log_message("RUNNER: No active training process to stop.")

        self.script_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.runner_status_label.config(text="🔴 Stopped")
        self.append_runner_output("\n=== Training Stopped ===\n")

    def clear_runner_output(self):
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.delete(1.0, tk.END)
        self.runner_output.config(state=tk.DISABLED)
        log_message("RUNNER: Output cleared.")

    def log_output(self, text, tag=None):
        self.runner_output.config(state=tk.NORMAL)
        self.runner_output.insert(tk.END, text, tag)
        self.runner_output.see(tk.END)
        self.runner_output.config(state=tk.DISABLED)

    def append_runner_output(self, text):
        self.log_output(text)

    def save_runner_defaults(self):
        """Save the current runner settings to the main settings.json file."""
        settings_file = DATA_DIR / "settings.json"
        all_settings = {}
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    all_settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        runner_settings = {
            "max_time": self.max_time_var.get(), "max_runs": self.max_runs_var.get(),
            "run_delay": self.run_delay_var.get(), "save_checkpoints": self.save_checkpoints_var.get(),
            "checkpoint_interval": self.checkpoint_interval_var.get(), "early_stop": self.early_stop_var.get(),
            "early_stop_patience": self.early_stop_patience_var.get(), "use_mixed_precision": self.use_mixed_precision_var.get(),
            "gradient_accumulation": self.gradient_accumulation_var.get(), "warmup_steps": self.warmup_steps_var.get(),
            "max_cpu_threads": self.max_cpu_threads_var.get(), "max_ram_percent": self.max_ram_percent_var.get(),
            "auto_restart": self.auto_restart_var.get()
        }
        all_settings["runner_defaults"] = runner_settings

        try:
            with open(settings_file, 'w') as f:
                json.dump(all_settings, f, indent=2)
            self.log_output("✅ Runner default settings saved.\n", "system")
            log_message("RUNNER: Runner default settings saved.")
        except Exception as e:
            self.log_output(f"❌ Error saving runner defaults: {e}\n", "error")
            log_message(f"RUNNER ERROR: Could not save runner defaults: {e}")

    def load_runner_defaults(self, initial_load=False):
        """Load runner settings from settings.json."""
        log_message("RUNNER: Loading runner defaults.")
        settings_file = DATA_DIR / "settings.json"
        if not settings_file.exists():
            if not initial_load: self.log_output("ℹ️ No settings file found. Using current values.\n", "system")
            return

        try:
            with open(settings_file, 'r') as f:
                all_settings = json.load(f)
            
            runner_settings = all_settings.get("runner_defaults")
            if not runner_settings:
                if not initial_load: self.log_output("ℹ️ No runner defaults found in settings. Using current values.\n", "system")
                return

            self.max_time_var.set(runner_settings.get("max_time", self.max_time_var.get()))
            self.max_runs_var.set(runner_settings.get("max_runs", self.max_runs_var.get()))
            self.run_delay_var.set(runner_settings.get("run_delay", self.run_delay_var.get()))
            self.save_checkpoints_var.set(runner_settings.get("save_checkpoints", self.save_checkpoints_var.get()))
            self.checkpoint_interval_var.set(runner_settings.get("checkpoint_interval", self.checkpoint_interval_var.get()))
            self.early_stop_var.set(runner_settings.get("early_stop", self.early_stop_var.get()))
            self.early_stop_patience_var.set(runner_settings.get("early_stop_patience", self.early_stop_patience_var.get()))
            self.use_mixed_precision_var.set(runner_settings.get("use_mixed_precision", self.use_mixed_precision_var.get()))
            self.gradient_accumulation_var.set(runner_settings.get("gradient_accumulation", self.gradient_accumulation_var.get()))
            self.warmup_steps_var.set(runner_settings.get("warmup_steps", self.warmup_steps_var.get()))
            self.max_cpu_threads_var.set(runner_settings.get("max_cpu_threads", self.max_cpu_threads_var.get()))
            self.max_ram_percent_var.set(runner_settings.get("max_ram_percent", self.max_ram_percent_var.get()))
            self.auto_restart_var.set(runner_settings.get("auto_restart", self.auto_restart_var.get()))
            
            if not initial_load: self.log_output("✅ Runner default settings loaded.\n", "system")
            log_message("RUNNER: Successfully loaded runner defaults.")
        except Exception as e:
            if not initial_load: self.log_output(f"❌ Error loading runner defaults: {e}\n", "error")
            log_message(f"RUNNER ERROR: Could not load runner defaults: {e}")

    def _on_mousewheel(self, event):
        """Cross-platform mouse wheel scrolling for the controls canvas."""
        if event.num == 5 or event.delta < 0:
            self.controls_canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.controls_canvas.yview_scroll(-1, "units")

    def _bind_mousewheel(self, event):
        """Bind mouse wheel to the canvas when the mouse enters."""
        self.parent.bind_all("<MouseWheel>", self._on_mousewheel)
        self.parent.bind_all("<Button-4>", self._on_mousewheel)
        self.parent.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        """Unbind mouse wheel when the mouse leaves."""
        self.parent.unbind_all("<MouseWheel>")
        self.parent.unbind_all("<Button-4>")
        self.parent.unbind_all("<Button-5>")
