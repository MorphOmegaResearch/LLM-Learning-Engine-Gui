import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import subprocess
import threading

class ToolsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.tools_file = os.path.join(os.path.dirname(__file__), '..', 'tools.json')
        self.tools = []
        self.selected_tool_index = None

        self.load_tools()
        self.setup_ui()
        self.populate_tools_list()

    def setup_ui(self):
        # Main paned window
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side: Tools list and controls
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        list_frame = ttk.LabelFrame(left_frame, text="Available Tools")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.tools_listbox = tk.Listbox(list_frame)
        self.tools_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tools_listbox.bind('<<ListboxSelect>>', self.on_tool_select)

        tool_controls_frame = ttk.Frame(left_frame)
        tool_controls_frame.pack(fill=tk.X)
        ttk.Button(tool_controls_frame, text="Add Tool", command=self.add_tool).pack(side=tk.LEFT, padx=5)
        ttk.Button(tool_controls_frame, text="Remove Tool", command=self.remove_tool).pack(side=tk.LEFT, padx=5)

        # Right side: Tool editor and output
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=3)

        editor_frame = ttk.LabelFrame(right_frame, text="Tool Editor")
        editor_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Form fields
        form_frame = ttk.Frame(editor_frame, padding=10)
        form_frame.pack(fill=tk.X)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.name_var).grid(row=0, column=1, sticky=tk.EW, pady=2)

        ttk.Label(form_frame, text="Command:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.command_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.command_var).grid(row=1, column=1, sticky=tk.EW, pady=2)

        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.description_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.description_var).grid(row=2, column=1, sticky=tk.EW, pady=2)
        
        form_frame.columnconfigure(1, weight=1)

        editor_controls_frame = ttk.Frame(editor_frame, padding=(10,0,10,10))
        editor_controls_frame.pack(fill=tk.X)
        ttk.Button(editor_controls_frame, text="Save Tool", command=self.save_tool).pack(side=tk.LEFT)
        ttk.Button(editor_controls_frame, text="Run Tool", command=self.run_tool).pack(side=tk.RIGHT)

        # Output display
        output_frame = ttk.LabelFrame(right_frame, text="Output")
        output_frame.pack(fill=tk.BOTH, expand=True)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, state=tk.DISABLED, font=('Consolas', 9))
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def load_tools(self):
        if not os.path.exists(self.tools_file):
            # Create a default tools file with invoke_doc.py as an example
            default_tools = [
                {
                    "name": "Generate Document",
                    "command": "python /home/commander/Desktop/quick_clip/invoke_doc.py",
                    "description": "Runs a CLI script to generate a document with Ollama."
                }
            ]
            self.tools = default_tools
            self.save_tools_to_file()
        else:
            try:
                with open(self.tools_file, 'r') as f:
                    self.tools = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                messagebox.showerror("Error", "Could not load tools.json. A new one will be created.")
                self.tools = []

    def save_tools_to_file(self):
        try:
            with open(self.tools_file, 'w') as f:
                json.dump(self.tools, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save tools to tools.json: {e}")

    def populate_tools_list(self):
        self.tools_listbox.delete(0, tk.END)
        for tool in self.tools:
            self.tools_listbox.insert(tk.END, tool.get('name', 'Unnamed Tool'))

    def on_tool_select(self, event):
        selection_indices = self.tools_listbox.curselection()
        if not selection_indices:
            return
        
        self.selected_tool_index = selection_indices[0]
        tool = self.tools[self.selected_tool_index]

        self.name_var.set(tool.get('name', ''))
        self.command_var.set(tool.get('command', ''))
        self.description_var.set(tool.get('description', ''))

    def add_tool(self):
        new_tool = {
            "name": "New Tool",
            "command": "",
            "description": ""
        }
        self.tools.append(new_tool)
        self.populate_tools_list()
        self.tools_listbox.selection_set(tk.END)
        self.on_tool_select(None)

    def remove_tool(self):
        if self.selected_tool_index is None:
            messagebox.showwarning("Warning", "No tool selected to remove.")
            return
        
        if messagebox.askyesno("Confirm", "Are you sure you want to remove this tool?"):
            self.tools.pop(self.selected_tool_index)
            self.save_tools_to_file()
            self.populate_tools_list()
            self.clear_editor()
            self.selected_tool_index = None

    def save_tool(self):
        if self.selected_tool_index is None:
            messagebox.showwarning("Warning", "No tool selected to save.")
            return

        tool = self.tools[self.selected_tool_index]
        tool['name'] = self.name_var.get()
        tool['command'] = self.command_var.get()
        tool['description'] = self.description_var.get()

        self.save_tools_to_file()
        self.populate_tools_list()
        self.tools_listbox.selection_set(self.selected_tool_index)
        messagebox.showinfo("Success", "Tool saved successfully.")

    def clear_editor(self):
        self.name_var.set('')
        self.command_var.set('')
        self.description_var.set('')

    def run_tool(self):
        if self.selected_tool_index is None:
            messagebox.showwarning("Warning", "No tool selected to run.")
            return

        command = self.command_var.get()
        if not command:
            messagebox.showwarning("Warning", "Tool command is empty.")
            return

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete('1.0', tk.END)
        self.output_text.insert(tk.END, f"Running command: {command}\n\n")
        self.output_text.config(state=tk.DISABLED)

        # Run the command in a separate thread to avoid blocking the GUI
        thread = threading.Thread(target=self.execute_command, args=(command,))
        thread.daemon = True
        thread.start()

    def execute_command(self, command):
        try:
            # Using Popen to capture output in real-time
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            # Read stdout line by line
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.append_to_output(output)
            
            # Capture any remaining stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                self.append_to_output(f"\n--- STDERR ---\n{stderr_output}")

        except Exception as e:
            self.append_to_output(f"\n--- ERROR ---\nFailed to run command: {e}")

    def append_to_output(self, text):
        """Append text to the output widget from a different thread."""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
