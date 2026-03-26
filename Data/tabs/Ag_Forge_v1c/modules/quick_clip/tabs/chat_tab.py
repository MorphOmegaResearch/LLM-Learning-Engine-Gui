import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import json
import os
import re
from datetime import datetime
from pathlib import Path

# Try to import providers and task manager
try:
    from providers import get_provider
    from clip_task_core import TaskManager
except ImportError:
    try:
        from ..providers import get_provider
        from ..clip_task_core import TaskManager
    except ImportError:
        get_provider = None
        TaskManager = None

class ChatTab(ttk.Frame):
    def __init__(self, parent, app_ref):
        super().__init__(parent)
        self.app = app_ref
        self.config = self.app.config
        self.history = []
        self.current_session_id = None
        
        # State for onboarding
        self.onboarding_active = False
        self.project_state = {
            "project_name": None,
            "business_focus": None,
            "business_strategy": None,
            "initial_investment": None
        }

        self.setup_ui()

    def setup_ui(self):
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Controls: Provider & Model Selection ---
        top_frame = ttk.Frame(main_container)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(top_frame, text="Provider:").pack(side=tk.LEFT, padx=5)
        self.provider_var = tk.StringVar(value="ollama")
        self.provider_combo = ttk.Combobox(top_frame, textvariable=self.provider_var, values=["ollama", "gemini"], width=10, state="readonly")
        self.provider_combo.pack(side=tk.LEFT, padx=5)
        self.provider_combo.bind("<<ComboboxSelected>>", self.on_provider_change)
        
        ttk.Label(top_frame, text="Model:").pack(side=tk.LEFT, padx=5)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(top_frame, textvariable=self.model_var, width=20)
        self.model_combo.pack(side=tk.LEFT, padx=5)
        
        # Sync with main app's models initially
        self.on_provider_change()

        # Onboarding Button
        self.onboarding_btn = ttk.Button(top_frame, text="✨ Start New Agri-Project", command=self.start_onboarding)
        self.onboarding_btn.pack(side=tk.RIGHT, padx=5)
        
        # Agent Mode Toggle
        self.agent_mode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_frame, text="🤖 Agent Mode (Mock)", variable=self.agent_mode_var).pack(side=tk.RIGHT, padx=5)

        # --- Chat Display ---
        self.chat_display = scrolledtext.ScrolledText(main_container, wrap=tk.WORD, state=tk.DISABLED, font=("Arial", 10))
        self.chat_display.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Configure tags for colors
        self.chat_display.tag_configure("user", foreground="#2196F3", font=("Arial", 10, "bold"))
        self.chat_display.tag_configure("ai", foreground="#4CAF50", font=("Arial", 10, "bold"))
        self.chat_display.tag_configure("system", foreground="gray", font=("Arial", 9, "italic"))

        # --- Input Area ---
        input_frame = ttk.Frame(main_container)
        input_frame.pack(fill=tk.X)
        
        self.chat_input = ttk.Entry(input_frame, font=("Arial", 11))
        self.chat_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.chat_input.bind("<Return>", self.send_message)
        
        self.send_btn = ttk.Button(input_frame, text="Send", command=self.send_message)
        self.send_btn.pack(side=tk.RIGHT)

    def on_provider_change(self, event=None):
        provider = self.provider_var.get()
        if provider == "ollama":
            # Use models from the main app's fetch
            models = self.app.models if hasattr(self.app, 'models') else ["llama2"]
            self.model_combo['values'] = models
            if models: self.model_var.set(models[0])
        elif provider == "gemini":
            models_str = self.config.get('Gemini', 'available_models', 'gemini-1.5-flash,gemini-1.5-pro')
            models = [m.strip() for m in models_str.split(',')]
            self.model_combo['values'] = models
            if models: self.model_var.set(self.config.get('Gemini', 'model', models[0]))

    def start_onboarding(self):
        if self.onboarding_active:
            if not messagebox.askyesno("Confirm", "An onboarding session is already active. Restart?"):
                return
        
        self.onboarding_active = True
        self.history = []
        self.project_state = {k: None for k in self.project_state}
        self.append_to_chat("System", "🌟 Starting new Agribusiness Onboarding session...")
        
        # Kick off turn 1
        self.process_onboarding_turn()

    def send_message(self, event=None):
        message = self.chat_input.get().strip()
        if not message: return
        
        self.chat_input.delete(0, tk.END)
        self.append_to_chat("You", message)
        
        if self.onboarding_active:
            self.process_onboarding_turn(message)
        else:
            # Normal chat
            self.process_general_chat(message)

    def process_onboarding_turn(self, user_reply=None):
        """Logic mirrored from brain.py handle_conversational_onboarding"""
        if user_reply:
            # Identify what the last question was to update state
            last_question = ""
            for turn in reversed(self.history):
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
            
            self.history.append({"role": "user", "content": user_reply})

        # Assemble Prompt (Mocking the context_aggregator logic)
        prompt = self.create_onboarding_prompt()
        
        # Call AI
        self.call_ai(prompt, is_onboarding=True)

    def create_onboarding_prompt(self):
        # Simplification of the Architect prompt
        state = self.project_state
        prompt = f"""You are an expert Agribusiness Architect.
---
CURRENT ONBOARDING STATE ---
Project Name: {state['project_name'] or "Not Provided"}
Business Focus: {state['business_focus'] or "Not Provided"}
Business Strategy: {state['business_strategy'] or "Not Provided"}
Initial Investment: {state['initial_investment'] or "Not Provided"}

---
YOUR TASK ---
Guiding turn-based setup:
1. If Name missing -> Ask.
2. If Focus missing -> Ask.
3. If Strategy missing -> Ask.
4. If Investment missing -> Ask.
5. If all provided -> RECOMMEND 2-3 specific tools and include machine-readable tag:
[[PLANNER_TASKS: financial/financial_analysis.py, data_structures/tree/avl_tree.py]]

Respond ONLY with your message for the user."""
        return prompt

    def process_general_chat(self, message):
        self.history.append({"role": "user", "content": message})
        # Simple history-aware prompt
        full_prompt = "\n".join([f"{t['role'].upper()}: {t['content']}" for t in self.history])
        self.call_ai(full_prompt)

    def call_ai(self, prompt, is_onboarding=False):
        provider_name = self.provider_var.get()
        model_name = self.model_var.get()
        
        # Mimic args for provider
        class Args: pass
        args = Args()
        args.model = model_name
        args.ollama_url = self.app.ollama_url
        args.gemini_api_key = self.config.get('Endpoints', 'gemini_api_key', '')
        args.agent_mode = self.agent_mode_var.get() # Use the toggle
        
        self.send_btn.config(state=tk.DISABLED)
        
        def run():
            try:
                provider = get_provider(provider_name)
                if not provider:
                    self.append_to_chat("System", f"Error: Provider '{provider_name}' not found.")
                    return

                response = provider.execute(prompt, args)
                self.app.root.after(0, lambda: self.handle_ai_response(response, is_onboarding))
            except Exception as e:
                self.app.root.after(0, lambda: self.append_to_chat("System", f"AI Error: {e}"))
            finally:
                self.app.root.after(0, lambda: self.send_btn.config(state=tk.NORMAL))

        threading.Thread(target=run, daemon=True).start()

    def handle_ai_response(self, response, is_onboarding):
        # Extract content if it's from agent-mode (Mock)
        clean_response = response
        if "Reviewer Output:" in response:
            clean_response = response.split("---", 1)[-1].strip()

        self.append_to_chat("AI", clean_response)
        self.history.append({"role": "reviewer", "content": clean_response})
        
        # Parse Tasks
        if "[[PLANNER_TASKS:" in clean_response:
            self.parse_and_queue_tasks(clean_response)
            if is_onboarding:
                self.onboarding_active = False
                self.append_to_chat("System", "✅ Onboarding Complete! Project tasks added to Planner.")

    def parse_and_queue_tasks(self, text):
        if not TaskManager: return
        
        match = re.search(r"\`\[\[PLANNER_TASKS: (.*?)\]\]\`", text)
        if match:
            tasks_str = match.group(1)
            suggested = [s.strip() for s in tasks_str.split(",")]
            
            tm = TaskManager()
            proj = self.project_state.get('project_name', 'AgriProject')
            
            for script in suggested:
                tm.add_task(
                    description=f"Execute {script} for project {proj}",
                    project=proj,
                    tags=["ai-suggested", "onboarding"]
                )
            self.append_to_chat("System", f"📦 Queued {len(suggested)} tasks in Planner.")

    def append_to_chat(self, sender, message):
        self.chat_display.config(state=tk.NORMAL)
        tag = sender.lower() if sender.lower() in ["user", "ai", "system"] else None
        self.chat_display.insert(tk.END, f"{sender}: ", tag)
        self.chat_display.insert(tk.END, f"{message}\n\n")
        self.chat_display.config(state=tk.DISABLED)
        self.chat_display.see(tk.END)
