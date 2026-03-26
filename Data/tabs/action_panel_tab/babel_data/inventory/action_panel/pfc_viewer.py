#!/usr/bin/env python3
"""
PFC Viewer - Integrated Pre-Flight Check & Task Validation Interface
Displays detailed check results and requires verification of expected outcomes.
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path

class PFCViewer:
    def __init__(self, root, pfc_results, task_data=None):
        self.window = tk.Toplevel(root)
        self.window.title("Pre-Flight Check & Validation Review")
        self.window.geometry("1000x750")
        self.window.configure(bg='#1e1e1e')
        
        # Ensure it stays on top and is modal
        self.window.transient(root)
        self.window.grab_set()
        
        self.pfc_results = pfc_results
        self.task_data = task_data or {}
        self.expected_outcomes = self.task_data.get('expected_outcomes', [])
        self.result = False
        
        self._setup_ui()
        self._center_window()
        
    def _center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def _setup_ui(self):
        # Header
        header = tk.Frame(self.window, bg='#252526', pady=15)
        header.pack(fill=tk.X)
        
        pfc_status = self.pfc_results.get('overall_status', 'Unknown')
        status_color = '#4caf50' if pfc_status == 'Passed' else '#f44336'
        
        title_frame = tk.Frame(header, bg='#252526')
        title_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(title_frame, text="PRE-FLIGHT CHECK", bg='#252526', fg='#888888', 
                 font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        tk.Label(title_frame, text=f"Status: {pfc_status}", bg='#252526', fg=status_color, 
                 font=('Arial', 16, 'bold')).pack(anchor=tk.W)
        
        if self.task_data.get('title'):
            task_frame = tk.Frame(header, bg='#252526')
            task_frame.pack(side=tk.RIGHT, padx=20)
            tk.Label(task_frame, text="TASK CONTEXT", bg='#252526', fg='#888888', 
                     font=('Arial', 10, 'bold')).pack(anchor=tk.E)
            tk.Label(task_frame, text=self.task_data.get('title'), bg='#252526', fg='#4ec9b0', 
                     font=('Arial', 12)).pack(anchor=tk.E)

        # Main Paned View
        paned = ttk.PanedWindow(self.window, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Panel: Results
        results_container = tk.Frame(paned, bg='#1e1e1e')
        paned.add(results_container, weight=3)
        
        # Notebook for categorized results
        self.results_nb = ttk.Notebook(results_container)
        self.results_nb.pack(fill=tk.BOTH, expand=True)
        
        # Summary Tab
        self._add_text_tab("Summary", self._format_summary())
        
        # Tool-specific tabs
        for tool in ['ruff', 'pylint', 'pyflakes', 'py_compile']:
            if tool in self.pfc_results:
                tool_data = self.pfc_results[tool]
                if isinstance(tool_data, dict):
                    content = tool_data.get('output') or tool_data.get('error') or "No output."
                    if tool_data.get('errors'):
                        content += "\n\nERRORS:\n" + tool_data['errors']
                else:
                    content = str(tool_data)
                self._add_text_tab(tool.capitalize(), content)
        
        # Raw JSON Tab
        self._add_text_tab("Raw JSON", json.dumps(self.pfc_results, indent=2))
        
        # Right Panel: Validation
        validation_container = tk.Frame(paned, bg='#1e1e1e', padx=10)
        paned.add(validation_container, weight=2)
        
        tk.Label(validation_container, text="EXPECTED OUTCOMES", bg='#1e1e1e', fg='#e0e0e0',
                 font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 10))
        
        # Scrollable area for outcomes
        canvas = tk.Canvas(validation_container, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(validation_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.outcome_vars = []
        if not self.expected_outcomes:
            # Fallback if no outcomes defined
            self.expected_outcomes = [
                "Code is syntactically correct",
                "Functionality verified manually",
                "No regression in existing features"
            ]
            tk.Label(self.scrollable_frame, text="Default Validation Checklist:", 
                     bg='#1e1e1e', fg='#888888', font=('Arial', 9, 'italic')).pack(anchor=tk.W, pady=5)

        for outcome in self.expected_outcomes:
            frame = tk.Frame(self.scrollable_frame, bg='#1e1e1e', pady=5)
            frame.pack(fill=tk.X, anchor=tk.W)
            
            var = tk.BooleanVar(value=False)
            self.outcome_vars.append(var)
            
            cb = tk.Checkbutton(frame, text=outcome, variable=var,
                               bg='#1e1e1e', fg='#e0e0e0', selectcolor='#3c3c3c',
                               activebackground='#1e1e1e', activeforeground='#4ec9b0',
                               wraplength=350, justify=tk.LEFT, font=('Arial', 10),
                               command=self._update_complete_button)
            cb.pack(anchor=tk.W)

        # Footer
        footer = tk.Frame(self.window, bg='#252526', pady=10)
        footer.pack(fill=tk.X)
        
        self.complete_btn = tk.Button(footer, text="VERIFY & COMPLETE", 
                                     command=self._finalize,
                                     bg='#4ec9b0', fg='black', font=('Arial', 10, 'bold'),
                                     padx=30, pady=5, relief=tk.FLAT)
        self.complete_btn.pack(side=tk.RIGHT, padx=20)
        
        # Require all checks if PFC passed, otherwise warn
        self._update_complete_button()
        
        tk.Button(footer, text="CANCEL", command=self._cancel,
                  bg='#333333', fg='#e0e0e0', padx=20, relief=tk.FLAT).pack(side=tk.RIGHT, padx=5)

    def _add_text_tab(self, name, content):
        frame = tk.Frame(self.results_nb, bg='#1e1e1e')
        self.results_nb.add(frame, text=name)
        
        txt = scrolledtext.ScrolledText(frame, bg='#121212', fg='#d4d4d4',
                                       font=('Consolas', 10), borderwidth=0,
                                       padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, content)
        txt.config(state=tk.DISABLED)

    def _format_summary(self):
        summary = "PFC EXECUTION SUMMARY\n" + "="*60 + "\n\n"
        
        for key, value in self.pfc_results.items():
            if key in ['overall_status', 'ollama_models']:
                summary += f"{key.upper().replace('_', ' ')}: {value}\n"
        
        summary += "\nFILE CHECKS:\n"
        file_checks = self.pfc_results.get('file_checks', {})
        if not file_checks:
            summary += "  No specific files checked.\n"
        for filepath, results in file_checks.items():
            status = "PASSED" if results.get('passed') else "FAILED"
            summary += f"  - {filepath}: {status}\n"
            
        return summary

    def _update_complete_button(self):
        all_checked = all(var.get() for var in self.outcome_vars)
        pfc_passed = self.pfc_results.get('overall_status') == 'Passed'
        
        if pfc_passed and all_checked:
            self.complete_btn.config(state=tk.NORMAL, bg='#4ec9b0')
        elif not pfc_passed:
            self.complete_btn.config(state=tk.NORMAL, bg='#f44336', text="FORCE COMPLETE (FAIL)")
        else:
            self.complete_btn.config(state=tk.DISABLED, bg='#3c3c3c')

    def _finalize(self):
        pfc_passed = self.pfc_results.get('overall_status') == 'Passed'
        all_checked = all(var.get() for var in self.outcome_vars)
        
        if not pfc_passed:
            if not messagebox.askyesno("PFC Failed", 
                                      "Pre-flight checks have failed. Are you sure you want to mark this task as complete despite the failures?"):
                return
        
        if not all_checked:
            if not messagebox.askyesno("Validation Incomplete", 
                                      "Not all expected outcomes have been verified. Proceed?"):
                return
        
        self.result = True
        self.window.destroy()

    def _cancel(self):
        self.result = False
        self.window.destroy()

def show_pfc_results(root, pfc_results, task_data=None):
    """
    Utility function to show the PFC results and return the user's decision.
    Returns True if user confirmed completion, False otherwise.
    """
    viewer = PFCViewer(root, pfc_results, task_data)
    root.wait_window(viewer.window)
    return viewer.result

if __name__ == "__main__":
    # Test stub
    root = tk.Tk()
    root.withdraw()
    test_results = {
        "overall_status": "Passed",
        "ruff": {"output": "All clear", "returncode": 0},
        "file_checks": {"test.py": {"passed": True}}
    }
    test_task = {
        "title": "Fix the UI bug in Action Panel",
        "expected_outcomes": [
            "Button color changes on hover",
            "Traceback logs are correctly formatted",
            "No memory leak detected in animation loop"
        ]
    }
    print(f"Result: {show_pfc_results(root, test_results, test_task)}")
