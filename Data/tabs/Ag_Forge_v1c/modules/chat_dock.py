#!/usr/bin/env python3
"""
Chat Dock - Daily Assistant UI
------------------------------
A compact, always-on desktop widget for daily agricultural and business management tasks.

Features:
- Omni-Chat: A single input for interacting with different AI systems (tasking, knowledge).
- Quick Tools: Buttons for frequent actions like adding health records or checking finances.
- Inventory Peek: A quick-view list of critical farm entities.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import subprocess
import threading
import sys
import logging
from pathlib import Path
import re
import json

# Try to import Quick Clip core utilities
try:
    from modules.quick_clip.providers import get_provider
    from modules.quick_clip.clip_task_core import TaskManager
    from modules.quick_clip.config import ConfigManager
except ImportError:
    get_provider = None
    TaskManager = None
    ConfigManager = None

# --- Global Paths ---
project_root = Path(__file__).parent.parent.resolve()

# --- Setup Logging ---
LOG_DIR = project_root / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "chat_dock.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Also print to console
    ]
)

# Add project root to sys.path to ensure imports work
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from modules.dev_tools.interactive_debug import install_debug_hooks
    logging.info("ChatDock - Interactive Debug module imported successfully.")
except ImportError as e:
    logging.error(f"ChatDock - Could not import interactive_debug: {e}")
    install_debug_hooks = None

# Import Ag_Forge data models for Health Record Dialog
try:
    from modules.meta_learn_agriculture import HealthRecord, EntityType, Entity, KnowledgeForgeApp
except ImportError as e:
    logging.error(f"ChatDock - Could not import full Ag_Forge models: {e}")
    # Define dummy classes if the import fails, to allow basic functionality
    class HealthRecord: pass
    class EntityType: ANIMAL="Animal"
    class Entity: pass
    class KnowledgeForgeApp: pass

# --- Data Models (mirrored from clip_task.py for compatibility) ---

class TaskStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    DELETED = "deleted"
    WAITING = "waiting"

@dataclass
class Task:
    id: str
    description: str
    status: TaskStatus
    created: datetime
    modified: datetime
    due: Optional[datetime] = None
    priority: str = "M"
    tags: List[str] = field(default_factory=list)
    project: str = ""

class HealthRecordDialog(simpledialog.Dialog):
    """A dialog for adding a new health record to an entity."""
    def __init__(self, parent, title, entities):
        self.entities = entities
        self.selected_entity = tk.StringVar()
        self.notes_text = None
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Select Entity (Animal):").pack(anchor=tk.W, padx=10, pady=5)
        
        # Dropdown for entity selection
        entity_names = [f"{eid}: {e.name}" for eid, e in self.entities.items() if e.type == EntityType.ANIMAL]
        self.entity_combo = ttk.Combobox(master, textvariable=self.selected_entity, values=entity_names, state="readonly", width=40)
        self.entity_combo.pack(padx=10, pady=5)
        if entity_names:
            self.entity_combo.current(0)

        ttk.Label(master, text="Health Notes:").pack(anchor=tk.W, padx=10, pady=5)
        self.notes_text = scrolledtext.ScrolledText(master, width=50, height=8, wrap=tk.WORD)
        self.notes_text.pack(padx=10, pady=10)
        
        return self.notes_text # Set initial focus

    def apply(self):
        entity_id_str = self.selected_entity.get().split(':')[0]
        notes = self.notes_text.get("1.0", tk.END).strip()
        
        if entity_id_str and notes:
            self.result = {"entity_id": entity_id_str, "notes": notes}
        else:
            self.result = None

class ChatDock(tk.Tk):
    def __init__(self):
        super().__init__()

        # Enable Debug Hooks
        if install_debug_hooks:
            install_debug_hooks(self)

        # Initialize connection to the Ag_Forge backend
        try:
            self.ag_forge_app = KnowledgeForgeApp(base_path=project_root / "knowledge_forge_data")
            logging.info("Successfully connected to Ag_Forge application.")
        except Exception as e:
            self.ag_forge_app = None
            logging.error(f"Failed to initialize KnowledgeForgeApp: {e}")
            messagebox.showerror("Error", "Could not connect to Ag_Forge data. Some features will be disabled.")

        self.title("Agri-Dock")
        self.geometry("400x650")
        
        # Define colors as instance attributes
        self.BG_COLOR = "#2E2E2E"
        self.FG_COLOR = "#FFFFFF"
        self.ACCENT_COLOR = "#4CAF50"
        self.ENTRY_BG = "#3C3C3C"

        self.configure(bg=self.BG_COLOR)

        # Chat State
        self.config_mgr = ConfigManager() if ConfigManager else None
        self.onboarding_active = False
        self.project_state = {"project_name": None, "business_focus": None, "business_strategy": None, "initial_investment": None}
        self.chat_history_data = []

        self._setup_styles()
        self._setup_ui()
        self._load_inventory()
        self._fetch_ollama_models()

    def _setup_styles(self):
        """Configure ttk styles for the dock."""
        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure(".", background=self.BG_COLOR, foreground=self.FG_COLOR, fieldbackground=self.ENTRY_BG, borderwidth=0)
        style.configure("TFrame", background=self.BG_COLOR)
        style.configure("TLabel", background=self.BG_COLOR, foreground=self.FG_COLOR, font=("Arial", 10))
        style.configure("TButton", font=("Arial", 9, "bold"), foreground=self.FG_COLOR, background=self.ACCENT_COLOR, borderwidth=0)
        style.map("TButton", background=[('active', '#45a049')])
        
        style.configure("Treeview", 
                        background=self.ENTRY_BG, 
                        foreground=self.FG_COLOR, 
                        fieldbackground=self.ENTRY_BG,
                        borderwidth=0)
        style.map("Treeview", background=[('selected', self.ACCENT_COLOR)])
        
        style.configure("Vertical.TScrollbar", background=self.BG_COLOR, troughcolor=self.ENTRY_BG)

    def _setup_ui(self):
        """Create and arrange the UI widgets."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Quick Tools ---
        tools_frame = ttk.Frame(main_frame)
        tools_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(tools_frame, text="Quick Tools", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        buttons_grid = ttk.Frame(tools_frame)
        buttons_grid.pack(fill=tk.X)
        buttons_grid.columnconfigure((0, 1), weight=1)

        ttk.Button(buttons_grid, text="Add Health Record", command=self.on_add_health_record).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(buttons_grid, text="Check Finances", command=self.on_check_finances).grid(row=0, column=1, sticky="ew")
        ttk.Button(buttons_grid, text="Next Task", command=self.on_next_task).grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5,0))
        ttk.Button(buttons_grid, text="Full Dashboard", command=self.on_open_dashboard).grid(row=1, column=1, sticky="ew", pady=(5,0))
        ttk.Button(buttons_grid, text="✨ New Project", command=self.on_start_onboarding).grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=(5,0))
        ttk.Button(buttons_grid, text="Refine UI", command=self.on_refine_ui).grid(row=2, column=1, sticky="ew", pady=(5,0))

        # --- AI Configuration (Compact) ---
        ai_cfg_frame = ttk.Frame(main_frame)
        ai_cfg_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.provider_var = tk.StringVar(value="ollama")
        self.provider_combo = ttk.Combobox(ai_cfg_frame, textvariable=self.provider_var, values=["ollama", "gemini"], width=8, state="readonly")
        self.provider_combo.pack(side=tk.LEFT, padx=2)
        
        self.model_var = tk.StringVar(value="llama2")
        self.model_combo = ttk.Combobox(ai_cfg_frame, textvariable=self.model_var, width=15)
        self.model_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(ai_cfg_frame, text="🔄", width=3, command=self._fetch_ollama_models).pack(side=tk.LEFT)
        
        self.agent_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ai_cfg_frame, text="🤖", variable=self.agent_mode_var).pack(side=tk.LEFT, padx=2)

        # --- Inventory Peek ---
        inventory_frame = ttk.Frame(main_frame)
        inventory_frame.pack(fill=tk.X, pady=(10, 10))

        ttk.Label(inventory_frame, text="Inventory Overview", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.inventory_tree = ttk.Treeview(inventory_frame, columns=("ID", "Name"), show="headings", height=5)
        self.inventory_tree.heading("ID", text="ID")
        self.inventory_tree.heading("Name", text="Name")
        self.inventory_tree.column("ID", width=80)
        self.inventory_tree.pack(fill=tk.X)

        # --- Omni-Chat ---
        chat_frame = ttk.Frame(main_frame)
        chat_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(chat_frame, text="Omni-Chat", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        self.chat_history = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, height=10, background=self.ENTRY_BG, foreground=self.FG_COLOR, font=("Arial", 9))
        self.chat_history.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.chat_history.config(state=tk.DISABLED)

        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill=tk.X)
        
        self.chat_input = ttk.Entry(input_frame, font=("Arial", 10))
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        ttk.Button(input_frame, text="Send", command=self.on_send_chat).pack(side=tk.RIGHT)
        self.chat_input.bind("<Return>", self.on_send_chat)

    def _load_inventory(self):
        """Load a preview of entities into the inventory tree."""
        if not self.ag_forge_app:
            return
            
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)
            
        # Get a few entities to show as a preview
        entities_to_show = list(self.ag_forge_app.entities.items())[:10]
        
        for entity_id, entity in entities_to_show:
            self.inventory_tree.insert("", "end", values=(entity_id, entity.name))
    
    def _fetch_ollama_models(self):
        """Fetch available models from Ollama CLI."""
        try:
            result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:] # Skip header
                models = [line.split()[0] for line in lines if line.strip()]
                if models:
                    self.model_combo['values'] = models
                    self.model_var.set(models[0])
                    logging.info(f"Fetched {len(models)} models from Ollama.")
            else:
                logging.warning("Ollama list command failed.")
        except Exception as e:
            logging.error(f"Error fetching Ollama models: {e}")

    # --- Command Handlers ---
    
    def on_add_health_record(self):
        logging.info("'Add Health Record' button clicked.")
        if not self.ag_forge_app:
            self.add_to_chat("System-Error", "Ag_Forge connection not available.")
            return

        dialog = HealthRecordDialog(self, "Add Health Record", self.ag_forge_app.entities)
        result = dialog.result
        
        if result:
            entity_id = result['entity_id']
            notes = result['notes']
            
            try:
                # Create a HealthRecord object
                record = HealthRecord(
                    date=datetime.now().strftime("%Y-%m-%d"),
                    diagnosis="General Observation", # Default diagnosis
                    notes=notes
                )
                self.ag_forge_app.add_health_record(entity_id, record)
                self.add_to_chat("System", f"Health record added for entity {entity_id}.")
                logging.info(f"Health record added for entity {entity_id} with notes: {notes}")
            except Exception as e:
                self.add_to_chat("System-Error", f"Failed to add health record: {e}")
                logging.error(f"Failed to add health record for {entity_id}: {e}")
    def on_check_finances(self):
        logging.info("'Check Finances' button clicked.")
        project_name = simpledialog.askstring("Input", "Enter the project name for the financial analysis:", parent=self)
        
        if project_name:
            logging.info(f"Starting financial analysis for project: {project_name}")
            self.add_to_chat("System", f"Triggering financial analysis for project: '{project_name}'...")
            
            # Run the brain.py workflow in a separate thread to avoid blocking the GUI
            thread = threading.Thread(target=self._run_finance_workflow, args=(project_name,))
            thread.daemon = True
            thread.start()

    def _run_finance_workflow(self, project_name: str):
        """Helper method to run the brain.py subprocess and stream its output."""
        try:
            command = [
                sys.executable, # Use the same python interpreter that's running this script
                "modules/brain.py",
                "--project",
                project_name,
                "--workflow",
                "financial_analysis"
            ]
            logging.info(f"Executing command: {' '.join(command)}")
            
            # Using Popen to capture output in real-time
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)

            # Stream stdout
            for line in process.stdout:
                self.add_to_chat("FinanceBot", line.strip())
            
            # Stream stderr
            for line in process.stderr:
                self.add_to_chat("FinanceBot-Error", line.strip())

            process.wait()
            logging.info(f"Finance workflow for '{project_name}' finished with exit code {process.returncode}.")
            if process.returncode == 0:
                self.add_to_chat("System", "Financial analysis workflow completed successfully.")
            else:
                self.add_to_chat("System", f"Financial analysis workflow finished with exit code {process.returncode}.")

        except FileNotFoundError:
            logging.error("Could not find 'modules/brain.py'.")
            self.add_to_chat("System-Error", "Could not find 'modules/brain.py'. Make sure the path is correct.")
        except Exception as e:
            logging.error(f"An error occurred in _run_finance_workflow: {e}")
            self.add_to_chat("System-Error", f"An error occurred: {e}")

    def on_next_task(self):
        logging.info("'Next Task' button clicked.")
        self.add_to_chat("System", "Fetching next priority task...")
        next_task_desc = self.fetch_next_task()
        logging.info(f"Fetched next task: {next_task_desc}")
        self.add_to_chat("Taskmaster", next_task_desc)

    def on_open_dashboard(self):
        logging.info("'Full Dashboard' button clicked.")
        self.add_to_chat("System", "Opening the main Ag_Forge application...")
        # In a real implementation, you would use subprocess to launch the main app
        # For now, we just log it.

    def on_start_onboarding(self):
        logging.info("'New Project' button clicked.")
        if self.onboarding_active:
            if not messagebox.askyesno("Confirm", "An onboarding session is already active. Restart?"):
                return
        
        self.onboarding_active = True
        self.project_state = {k: None for k in self.project_state}
        self.chat_history_data = []
        self.add_to_chat("System", "🌟 Starting new Agribusiness Onboarding sequence...")
        
        # Kick off turn 1
        self._process_onboarding_turn()

    def on_send_chat(self, event=None):
        user_message = self.chat_input.get().strip()
        if not user_message: return

        logging.info(f"User sent chat message: '{user_message}'")
        self.add_to_chat("You", user_message)
        self.chat_input.delete(0, tk.END)

        if self.onboarding_active:
            self._process_onboarding_turn(user_message)
        else:
            self._process_general_chat(user_message)

    def _process_onboarding_turn(self, user_reply=None):
        if user_reply:
            # Identify what the last question was to update state
            last_question = ""
            for turn in reversed(self.chat_history_data):
                if turn.get("role") == "reviewer":
                    last_question = turn["content"].lower()
                    break
            
            if "name of your new project" in last_question or "what is the name" in last_question:
                self.project_state["project_name"] = user_reply
            elif "primary business focus" in last_question:
                self.project_state["business_focus"] = user_reply
            elif "business strategy" in last_question:
                self.project_state["business_strategy"] = user_reply
            elif "initial investment" in last_question:
                self.project_state["initial_investment"] = user_reply
            
            self.chat_history_data.append({"role": "user", "content": user_reply})

        # Assemble Architect Prompt
        state = self.project_state
        prompt = f"""You are an expert Agribusiness Architect.
--- CURRENT ONBOARDING STATE ---
Project Name: {state['project_name'] or "Not Provided"}
Business Focus: {state['business_focus'] or "Not Provided"}
Business Strategy: {state['business_strategy'] or "Not Provided"}
Initial Investment: {state['initial_investment'] or "Not Provided"}

--- YOUR TASK ---
Guiding turn-based setup:
1. If Name missing -> Ask.
2. If Focus missing -> Ask.
3. If Strategy missing -> Ask.
4. If Investment missing -> Ask.
5. If all provided -> RECOMMEND 2-3 specific tools and include machine-readable tag:
[[PLANNER_TASKS: financial/financial_analysis.py, data_structures/tree/avl_tree.py]]

Respond ONLY with your message for the user."""

        self._call_ai(prompt, is_onboarding=True)

    def _process_general_chat(self, message):
        self.chat_history_data.append({"role": "user", "content": message})
        # Simple history-aware prompt
        full_prompt = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in self.chat_history_data])
        self._call_ai(full_prompt)

    def _call_ai(self, prompt, is_onboarding=False):
        provider_name = self.provider_var.get()
        model_name = self.model_var.get()
        
        # Mimic args for provider
        class Args: pass
        args = Args()
        args.model = model_name
        args.ollama_url = self.config_mgr.get('Endpoints', 'ollama_url', 'http://localhost:11434/api/generate') if self.config_mgr else 'http://localhost:11434/api/generate'
        args.gemini_api_key = self.config_mgr.get('Endpoints', 'gemini_api_key', '') if self.config_mgr else ''
        args.agent_mode = self.agent_mode_var.get()
        
        def run():
            try:
                provider = get_provider(provider_name)
                if not provider:
                    self.add_to_chat("System", f"Error: Provider '{provider_name}' not found.")
                    return

                response = provider.execute(prompt, args)
                self.after(0, lambda: self._handle_ai_response(response, is_onboarding))
            except Exception as e:
                self.after(0, lambda: self.add_to_chat("System", f"AI Error: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _handle_ai_response(self, response, is_onboarding):
        clean_response = response
        if "Reviewer Output:" in response:
            clean_response = response.split("---", 1)[-1].strip()

        self.add_to_chat("AI", clean_response)
        self.chat_history_data.append({"role": "reviewer", "content": clean_response})
        
        # Parse Tasks
        if "[[PLANNER_TASKS:" in clean_response:
            self._parse_and_queue_tasks(clean_response)
            if is_onboarding:
                self.onboarding_active = False
                self.add_to_chat("System", "✅ Onboarding Complete! Project tasks added to Planner.")

    def _parse_and_queue_tasks(self, text):
        if not TaskManager: return
        
        match = re.search(r"\[\[PLANNER_TASKS: (.*?)\]\]", text)
        if match:
            tasks_str = match.group(1)
            suggested = [s.strip() for s in tasks_str.split(",")]
            
            tm = TaskManager()
            proj = self.project_state.get('project_name', 'AgriProject')
            
            for script in suggested:
                tm.add_task(
                    description=f"Execute {script} for project {proj}",
                    project=proj,
                    tags=["ai-suggested", "onboarding", "dock"]
                )
            self.add_to_chat("System", f"📦 Queued {len(suggested)} tasks in Planner.")

    def add_to_chat(self, sender, message):
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.insert(tk.END, f"{sender}: {message}\n\n")
        self.chat_history.config(state=tk.DISABLED)
        self.chat_history.see(tk.END)

    def fetch_next_task(self) -> str:
        """
        Connects to the clip_task database and fetches the highest priority task.
        Priority order: High > Medium > Low
        Sorts by due date (earliest first).
        """
        db_path = Path.home() / ".config" / "ollama-planner" / "planner.db"
        if not db_path.exists():
            logging.warning("Task database not found at %s", db_path)
            return "Task database not found."

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Query for the next task:
            # - Status must be 'pending'
            # - Order by priority (H, M, L) and then by the soonest due date
            query = """
                SELECT description, due, priority
                FROM tasks
                WHERE status = 'pending'
                ORDER BY
                    CASE priority
                        WHEN 'H' THEN 1
                        WHEN 'M' THEN 2
                        WHEN 'L' THEN 3
                        ELSE 4
                    END,
                    due ASC
                LIMIT 1
            """
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()

            if result:
                description, due, priority = result
                due_str = f" (Due: {datetime.fromisoformat(due).strftime('%Y-%m-%d')})" if due else ""
                return f"Next Task (P{priority}): {description}{due_str}"
            else:
                logging.info("No pending tasks found in the database.")
                return "No pending tasks found."

        except sqlite3.Error as e:
            logging.error("Database error while fetching task: %s", e)
            return "Error accessing task database."
        except Exception as e:
            logging.error("An unexpected error occurred in fetch_next_task: %s", e)
            return "An unexpected error occurred while fetching tasks."

    def on_refine_ui(self):
        logging.info("'Refine UI' button clicked.")
        user_request = simpledialog.askstring("Refine UI", "What would you like to refine in the Chat Dock UI?", parent=self)
        
        if user_request:
            self.add_to_chat("System", f"Initiating AI review for UI refinement based on: '{user_request}'...")
            
            # Run the context_aggregator in a separate thread
            thread = threading.Thread(target=self._run_ui_refinement_workflow, args=(user_request,))
            thread.daemon = True
            thread.start()

    def _run_ui_refinement_workflow(self, user_request: str):
        """
        Helper method to run the context_aggregator.py subprocess.
        """
        try:
            target_file_path = project_root / "modules" / "chat_dock.py"
            command = [
                sys.executable, 
                str(project_root / "modules" / "dev_tools" / "context_aggregator.py"),
                "--file",
                str(target_file_path),
                "--request",
                user_request
            ]
            logging.info(f"Executing UI refinement command: {' '.join(command)}")
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)

            # Stream output back to the chat dock
            for line in process.stdout:
                self.add_to_chat("AI-Refiner", line.strip())
            for line in process.stderr:
                self.add_to_chat("AI-Refiner-Error", line.strip())

            process.wait()
            if process.returncode == 0:
                self.add_to_chat("System", "UI Refinement context generated. Check console for Gemini CLI command.")
            else:
                self.add_to_chat("System", f"UI Refinement process finished with exit code {process.returncode}.")

        except FileNotFoundError:
            self.add_to_chat("System-Error", "Could not find 'context_aggregator.py'. Make sure the path is correct.")
        except Exception as e:
            self.add_to_chat("System-Error", f"An error occurred during UI refinement: {e}")

if __name__ == "__main__":
    app = ChatDock()
    app.mainloop()
