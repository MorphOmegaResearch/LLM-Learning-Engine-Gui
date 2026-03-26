"""
AI Assistant Dialog for TODO/Plan creation.

Provides an interactive modal dialog for AI-assisted task/plan creation
by invoking the active agent from agents_tab.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Callable, Dict, Optional, Any
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from logger_util import log_message  # noqa: E402

LOGGER = logging.getLogger(__name__)


class AIAssistantDialog:
    """
    Modal dialog for AI-assisted TODO/Plan creation.

    Workflow:
    1. User provides description/context
    2. Dialog retrieves active agent from agents_tab
    3. Agent generates structured task/plan content
    4. User reviews and applies suggestions to parent form
    """

    def __init__(
        self,
        parent: tk.Misc,
        mode: str,  # 'todo' or 'plan'
        get_active_agent_fn: Callable[[], Optional[Dict[str, Any]]],
        callback: Callable[[Dict[str, Any]], None],
        initial_context: Optional[str] = None
    ):
        """
        Args:
            parent: Parent tkinter widget
            mode: 'todo' or 'plan'
            get_active_agent_fn: Function to retrieve active agent from agents_tab
            callback: Function to apply AI suggestions to parent form
            initial_context: Optional initial prompt/context
        """
        self.parent = parent
        self.mode = mode
        self.get_active_agent_fn = get_active_agent_fn
        self.callback = callback
        self.initial_context = initial_context

        self.dialog = None
        self.prompt_text = None
        self.response_text = None
        self.generate_btn = None
        self.apply_btn = None
        self.last_response = None

        self._build_ui()

    def _build_ui(self):
        """Build the AI assistant dialog UI."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"🤖 Ask AI - {self.mode.capitalize()}")
        self.dialog.geometry("700x600")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Configure grid
        self.dialog.columnconfigure(0, weight=1)
        self.dialog.rowconfigure(1, weight=1)
        self.dialog.rowconfigure(3, weight=2)

        # Header
        header = ttk.Label(
            self.dialog,
            text=f"Describe the {self.mode} you want to create, and AI will help generate structured content.",
            wraplength=650,
            justify=tk.LEFT
        )
        header.grid(row=0, column=0, sticky=tk.EW, padx=12, pady=(12, 6))

        # Prompt section
        prompt_label = ttk.Label(self.dialog, text="Your Description:")
        prompt_label.grid(row=1, column=0, sticky=tk.NW, padx=12, pady=(6, 2))

        self.prompt_text = scrolledtext.ScrolledText(
            self.dialog,
            height=8,
            wrap=tk.WORD,
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#dcdcdc'
        )
        self.prompt_text.grid(row=2, column=0, sticky=tk.NSEW, padx=12, pady=(0, 12))

        if self.initial_context:
            self.prompt_text.insert('1.0', self.initial_context)

        # Response section
        response_label = ttk.Label(self.dialog, text="AI Suggestion:")
        response_label.grid(row=3, column=0, sticky=tk.NW, padx=12, pady=(6, 2))

        self.response_text = scrolledtext.ScrolledText(
            self.dialog,
            height=12,
            wrap=tk.WORD,
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#dcdcdc',
            state='disabled'
        )
        self.response_text.grid(row=4, column=0, sticky=tk.NSEW, padx=12, pady=(0, 12))

        # Buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.grid(row=5, column=0, sticky=tk.E, padx=12, pady=(0, 12))

        self.generate_btn = ttk.Button(
            btn_frame,
            text='✨ Generate',
            command=self._generate_response
        )
        self.generate_btn.pack(side=tk.LEFT, padx=4)

        self.apply_btn = ttk.Button(
            btn_frame,
            text='✅ Apply',
            state='disabled',
            command=self._apply_suggestion
        )
        self.apply_btn.pack(side=tk.LEFT, padx=4)

        ttk.Button(
            btn_frame,
            text='Cancel',
            command=self.dialog.destroy
        ).pack(side=tk.LEFT, padx=4)

    def _generate_response(self):
        """Generate AI response using active agent."""
        prompt = self.prompt_text.get('1.0', tk.END).strip()
        if not prompt:
            messagebox.showwarning(
                "Empty Prompt",
                "Please describe what you want to create.",
                parent=self.dialog
            )
            return

        # Get active agent
        try:
            agent = self.get_active_agent_fn()
            if not agent:
                messagebox.showwarning(
                    "No Active Agent",
                    "Please select and mount an agent in the Agents tab before using Ask AI.",
                    parent=self.dialog
                )
                return
        except Exception as exc:
            LOGGER.exception("Failed to retrieve active agent")
            messagebox.showerror(
                "Agent Error",
                f"Failed to retrieve active agent: {exc}",
                parent=self.dialog
            )
            return

        # Generate response
        self.generate_btn.configure(state='disabled', text='⏳ Generating...')
        self.response_text.configure(state='normal')
        self.response_text.delete('1.0', tk.END)
        self.response_text.insert('1.0', "Generating response...")
        self.response_text.configure(state='disabled')
        self.dialog.update()

        try:
            response = self._invoke_agent(agent, prompt)
            if response:
                self.last_response = response
                self.response_text.configure(state='normal')
                self.response_text.delete('1.0', tk.END)
                self.response_text.insert('1.0', self._format_response(response))
                self.response_text.configure(state='disabled')
                self.apply_btn.configure(state='normal')
                log_message(f"AI_ASSISTANT: Generated {self.mode} suggestion via {agent.get('name', 'agent')}")
            else:
                self.response_text.configure(state='normal')
                self.response_text.delete('1.0', tk.END)
                self.response_text.insert('1.0', "No response generated. Please try again.")
                self.response_text.configure(state='disabled')
        except Exception as exc:
            LOGGER.exception("Failed to generate AI response")
            self.response_text.configure(state='normal')
            self.response_text.delete('1.0', tk.END)
            self.response_text.insert('1.0', f"Error generating response: {exc}")
            self.response_text.configure(state='disabled')
            messagebox.showerror(
                "Generation Error",
                f"Failed to generate response: {exc}",
                parent=self.dialog
            )
        finally:
            self.generate_btn.configure(state='normal', text='✨ Generate')

    def _invoke_agent(self, agent: Dict[str, Any], prompt: str) -> Optional[Dict[str, Any]]:
        """
        Invoke the active agent with the user's prompt.

        Returns structured data for TODO or Plan creation.
        """
        # TODO: Wire to actual agent inference pipeline
        # For now, return mock structured data

        agent_name = agent.get('name', 'Unknown Agent')
        log_message(f"AI_ASSISTANT: Invoking agent {agent_name} with prompt: {prompt[:100]}...")

        if self.mode == 'todo':
            return {
                'title': f"Generated TODO from {agent_name}",
                'details': f"Based on your description:\n\n{prompt}\n\n[AI-generated detailed task breakdown will appear here]",
                'category': 'tasks',
                'priority': 'medium'
            }
        else:  # plan
            return {
                'name': f"Generated Plan from {agent_name}",
                'overview': f"Plan based on: {prompt[:200]}...",
                'objectives': "• Objective 1\n• Objective 2\n• Objective 3",
                'priority': 'medium'
            }

    def _format_response(self, response: Dict[str, Any]) -> str:
        """Format the AI response for display."""
        if self.mode == 'todo':
            return f"Title: {response.get('title', '')}\n\nDetails:\n{response.get('details', '')}"
        else:  # plan
            return f"Name: {response.get('name', '')}\n\nOverview:\n{response.get('overview', '')}\n\nObjectives:\n{response.get('objectives', '')}"

    def _apply_suggestion(self):
        """Apply the AI suggestion to the parent form."""
        if not self.last_response:
            messagebox.showwarning(
                "No Suggestion",
                "Please generate a suggestion first.",
                parent=self.dialog
            )
            return

        try:
            self.callback(self.last_response)
            log_message(f"AI_ASSISTANT: Applied {self.mode} suggestion to parent form")
            self.dialog.destroy()
        except Exception as exc:
            LOGGER.exception("Failed to apply AI suggestion")
            messagebox.showerror(
                "Apply Error",
                f"Failed to apply suggestion: {exc}",
                parent=self.dialog
            )


def show_ai_assistant(
    parent: tk.Misc,
    mode: str,
    get_active_agent_fn: Callable[[], Optional[Dict[str, Any]]],
    callback: Callable[[Dict[str, Any]], None],
    initial_context: Optional[str] = None
) -> None:
    """
    Show the AI assistant dialog.

    Args:
        parent: Parent tkinter widget
        mode: 'todo' or 'plan'
        get_active_agent_fn: Function to retrieve active agent
        callback: Function to apply AI suggestions
        initial_context: Optional initial prompt
    """
    AIAssistantDialog(parent, mode, get_active_agent_fn, callback, initial_context)
