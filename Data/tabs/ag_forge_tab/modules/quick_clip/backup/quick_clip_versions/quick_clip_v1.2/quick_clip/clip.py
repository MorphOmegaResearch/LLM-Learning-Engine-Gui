import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import pyperclip
import requests
import json
import threading
import subprocess
from datetime import datetime

from config import ConfigManager

class ClipboardAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Clipboard Assistant")

        # Load configuration
        self.config = ConfigManager()
        
        # Set window size from config
        width = self.config.getint('Window', 'width', 850)
        height = self.config.getint('Window', 'height', 650)
        self.root.geometry(f"{width}x{height}")
        
        # Ollama configuration from config
        self.ollama_url = self.config.get('Ollama', 'url', 'http://localhost:11434/api/generate')
        self.current_model = self.config.get('Ollama', 'model', 'llama2')
        self.models = [self.current_model] # Start with the configured model
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # For stopping AI processing
        self.stop_processing = threading.Event()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_read_tab()
        self.create_edit_tab()
        self.create_config_tab()
        
        # Initialize with current clipboard
        self.refresh_clipboard()
        
        # Auto-refresh timer
        self.auto_refresh = True
        self.start_auto_refresh()

        # Save settings on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_read_tab(self):
        """Create the Read tab"""
        self.read_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.read_frame, text='📋 Read')
        
        # Header
        header_frame = ttk.Frame(self.read_frame)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(header_frame, text="Clipboard Content", 
                 font=('Arial', 14, 'bold')).pack(side='left')
        
        # Auto-refresh toggle
        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(header_frame, text="Auto-refresh", 
                       variable=self.auto_refresh_var,
                       command=self.toggle_auto_refresh).pack(side='right', padx=5)
        
        # Current clipboard display
        self.clipboard_display = scrolledtext.ScrolledText(
            self.read_frame, 
            height=20,
            width=80,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.clipboard_display.pack(padx=10, pady=5, fill='both', expand=True)
        
        # Button frame
        btn_frame = ttk.Frame(self.read_frame)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="🔄 Refresh", 
                  command=self.refresh_clipboard).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🚀 Quick Process", 
                  command=self.quick_process).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="📝 Switch to Edit", 
                  command=self.switch_to_edit).pack(side='left', padx=5)
    
    def create_edit_tab(self):
        """Create the Edit tab with AI processing"""
        self.edit_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.edit_frame, text='✏️ Edit & Process')
        
        # Top frame for input
        input_frame = ttk.LabelFrame(self.edit_frame, text="Input", padding=10)
        input_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Clipboard content to process
        ttk.Label(input_frame, text="Content to process:", 
                 font=('Arial', 10, 'bold')).pack(anchor='w')
        
        self.edit_text = scrolledtext.ScrolledText(
            input_frame,
            height=10,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.edit_text.pack(fill='both', expand=True, pady=(0, 10))
        
        # Instruction input
        ttk.Label(input_frame, text="Instructions/Prompt:", 
                 font=('Arial', 10, 'bold')).pack(anchor='w')
        
        self.instruction_text = scrolledtext.ScrolledText(
            input_frame,
            height=4,
            wrap=tk.WORD,
            font=('Consolas', 10)
        )
        self.instruction_text.pack(fill='x', pady=(0, 10))
        self.instruction_text.insert('1.0', "Please analyze, improve, or process the above content.")
        
        # Process buttons frame
        process_btn_frame = ttk.Frame(input_frame)
        process_btn_frame.pack(fill='x', pady=5)
        
        ttk.Button(process_btn_frame, text="🔄 Load from Clipboard", 
                  command=self.load_to_edit).pack(side='left', padx=5)
        ttk.Button(process_btn_frame, text="📂 Load from File",
                  command=self.load_input).pack(side='left', padx=5)
        ttk.Button(process_btn_frame, text="💾 Save to File",
                  command=self.save_input).pack(side='left', padx=5)

        # Quick action buttons
        quick_actions_frame = ttk.Frame(input_frame)
        quick_actions_frame.pack(fill='x', pady=5)
        quick_actions = [
            ("Summarize", "Please summarize this text concisely."),
            ("Improve Grammar", "Please fix any grammar issues and improve writing."),
            ("Explain", "Please explain this in simple terms."),
            ("Translate to Code", "Convert this to pseudocode or Python.")
        ]
        
        for action, prompt in quick_actions:
            ttk.Button(quick_actions_frame, text=action,
                      command=lambda p=prompt: self.set_quick_prompt(p)).pack(side='left', padx=2)
        
        # Bottom frame for output
        output_frame = ttk.LabelFrame(self.edit_frame, text="AI Output", padding=10)
        output_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Output display
        self.output_display = scrolledtext.ScrolledText(
            output_frame,
            height=15,
            wrap=tk.WORD,
            font=('Consolas', 10),
            state='disabled'
        )
        self.output_display.pack(fill='both', expand=True, pady=(0, 10))
        
        # Output buttons
        output_btn_frame = ttk.Frame(output_frame)
        output_btn_frame.pack(fill='x')
        
        self.send_button = ttk.Button(output_btn_frame, text="🚀 Send", 
                  command=self.process_with_ai)
        self.send_button.pack(side='left', padx=5)
        self.stop_button = ttk.Button(output_btn_frame, text="⏹️ Stop", 
                  command=self.stop_ai_process, state='disabled')
        self.stop_button.pack(side='left', padx=5)
        ttk.Button(output_btn_frame, text="📋 Copy Output", 
                  command=self.copy_output).pack(side='left', padx=5)
        ttk.Button(output_btn_frame, text="💾 Save Output", 
                  command=self.save_output).pack(side='left', padx=5)
        
        # Status label
        self.status_label = ttk.Label(output_frame, text="Ready", foreground="gray")
        self.status_label.pack(side='left', pady=5)
    
    def create_config_tab(self):
        """Create configuration tab"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text='⚙️ Settings')

        main_container = ttk.Frame(self.config_frame)
        main_container.pack(fill='both', expand=True, padx=20, pady=10)
        main_container.columnconfigure(0, weight=1)
        
        # Ollama settings frame
        ollama_frame = ttk.LabelFrame(main_container, text="Ollama Settings", padding=15)
        ollama_frame.grid(row=0, column=0, sticky='ew', pady=(0, 10))
        ollama_frame.columnconfigure(1, weight=1)
        
        # Model selection
        ttk.Label(ollama_frame, text="Model:", 
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        
        self.model_var = tk.StringVar(value=self.current_model)
        self.model_combo = ttk.Combobox(ollama_frame, textvariable=self.model_var,
                                  values=self.models, state='readonly', width=30)
        self.model_combo.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
        self.model_combo.bind('<<ComboboxSelected>>', self.update_model)
        
        # Server URL
        ttk.Label(ollama_frame, text="Server URL:", 
                 font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        
        self.url_var = tk.StringVar(value=self.ollama_url)
        url_entry = ttk.Entry(ollama_frame, textvariable=self.url_var, width=40)
        url_entry.grid(row=1, column=1, padx=10, pady=5, sticky='ew')
        
        # Auto-refresh interval
        ttk.Label(ollama_frame, text="Clipboard Refresh (sec):", 
                 font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        
        self.refresh_var = tk.StringVar(value=self.config.get('Application', 'auto_refresh_seconds', '5'))
        refresh_entry = ttk.Entry(ollama_frame, textvariable=self.refresh_var, width=10)
        refresh_entry.grid(row=2, column=1, sticky='w', padx=10, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(ollama_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="🔗 Test Connection", 
                  command=self.test_connection).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="🔄 Fetch Available Models", 
                  command=self.fetch_models).pack(side='left', padx=5)

        # Connection status
        self.connection_label = ttk.Label(ollama_frame, text="", foreground="gray")
        self.connection_label.grid(row=4, column=0, columnspan=2, pady=5, sticky='w')

        # GPU settings frame
        gpu_frame = ttk.LabelFrame(main_container, text="GPU Settings", padding=15)
        gpu_frame.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        gpu_frame.columnconfigure(1, weight=1)

        # GPU Layers
        ttk.Label(gpu_frame, text="GPU Layers (num_gpu):", 
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        
        self.num_gpu_var = tk.StringVar(value=self.config.get('Ollama', 'num_gpu', ''))
        gpu_entry = ttk.Entry(gpu_frame, textvariable=self.num_gpu_var, width=10)
        gpu_entry.grid(row=0, column=1, sticky='w', padx=10, pady=5)
        
        # GPU Monitoring frame
        monitor_frame = ttk.LabelFrame(main_container, text="GPU Monitoring", padding=15)
        monitor_frame.grid(row=2, column=0, sticky='ew')
        monitor_frame.columnconfigure(0, weight=1)

        # GPU stats display
        self.gpu_stats_label = ttk.Label(monitor_frame, text="Click 'Refresh' to get stats.", 
                                        font=('Consolas', 10))
        self.gpu_stats_label.grid(row=0, column=0, sticky='w', pady=5)

        ttk.Button(monitor_frame, text="🔄 Refresh GPU Stats", 
                  command=self.refresh_gpu_stats).grid(row=1, column=0, pady=10, sticky='w')

        # Save button
        save_btn_frame = ttk.Frame(main_container)
        save_btn_frame.grid(row=3, column=0, sticky='e', pady=10)
        ttk.Button(save_btn_frame, text="💾 Save All Settings", 
                  command=self.save_settings).pack()
    
    def refresh_clipboard(self):
        """Refresh clipboard content in Read tab"""
        try:
            clipboard_content = pyperclip.paste()
            self.clipboard_display.delete('1.0', tk.END)
            self.clipboard_display.insert('1.0', clipboard_content)
            
            # Update timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.root.title(f"Clipboard Assistant - Last refreshed: {timestamp}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read clipboard: {str(e)}")
    
    def load_to_edit(self):
        """Load clipboard content into edit tab"""
        try:
            clipboard_content = pyperclip.paste()
            self.edit_text.delete('1.0', tk.END)
            self.edit_text.insert('1.0', clipboard_content)
            self.notebook.select(1)  # Switch to Edit tab
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load clipboard: {str(e)}")
    
    def set_quick_prompt(self, prompt):
        """Set a quick action prompt"""
        self.instruction_text.delete('1.0', tk.END)
        self.instruction_text.insert('1.0', prompt)
    
    def process_with_ai(self):
        """Send content to Ollama for processing"""
        content = self.edit_text.get('1.0', tk.END).strip()
        instruction = self.instruction_text.get('1.0', tk.END).strip()
        
        if not content:
            messagebox.showwarning("Warning", "Please enter some content to process.")
            return
        
        prompt = f"{instruction}\n\nContent:\n{content}"
        
        self.status_label.config(text="Processing...", foreground="orange")
        self.send_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.stop_processing.clear()
        self.root.update()
        
        self.output_display.config(state='normal')
        self.output_display.delete('1.0', tk.END)
        self.output_display.config(state='disabled')

        thread = threading.Thread(target=self.call_ollama, args=(prompt,))
        thread.daemon = True
        thread.start()

    def stop_ai_process(self):
        """Signal the AI processing thread to stop."""
        self.stop_processing.set()
        self.status_label.config(text="Stopping...", foreground="orange")

    def call_ollama(self, prompt):
        """Call Ollama API with streaming."""
        try:
            payload = {
                "model": self.current_model,
                "prompt": prompt,
                "stream": True
            }
            try:
                if hasattr(self, 'num_gpu_var'):
                    num_gpu = int(self.num_gpu_var.get())
                    if num_gpu > 0:
                        payload["options"] = {"num_gpu": num_gpu}
            except (ValueError, AttributeError):
                pass # Ignore if empty or not an int

            response = requests.post(self.ollama_url, json=payload, stream=True, timeout=120)
            response.raise_for_status()

            for chunk in response.iter_lines():
                if self.stop_processing.is_set():
                    self.root.after(0, lambda: self.status_label.config(text="Stopped by user", foreground="orange"))
                    break
                
                if chunk:
                    decoded_chunk = chunk.decode('utf-8')
                    try:
                        json_chunk = json.loads(decoded_chunk)
                        content = json_chunk.get('response', '')
                        self.root.after(0, self.append_output, content)

                        if json_chunk.get('done'):
                            total_duration = json_chunk.get('total_duration', 0)
                            self.root.after(0, lambda: self.status_label.config(
                                text=f"Done! ({total_duration/1e9:.2f}s)", 
                                foreground="green"))
                            break
                    except json.JSONDecodeError:
                        pass
            
        except requests.exceptions.RequestException as e:
            error_msg = f"API Error: {e}"
            self.root.after(0, self.update_output, error_msg, False)
            self.root.after(0, lambda: self.status_label.config(text="Failed", foreground="red"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, self.update_output, error_msg, False)
            self.root.after(0, lambda: self.status_label.config(text="Error", foreground="red"))
        finally:
            self.root.after(0, self.reset_processing_buttons)

    def append_output(self, text):
        """Append text to the output display."""
        self.output_display.config(state='normal')
        self.output_display.insert(tk.END, text)
        self.output_display.see(tk.END)
        self.output_display.config(state='disabled')

    def reset_processing_buttons(self):
        """Reset send/stop buttons to their initial state."""
        self.send_button.config(state='normal')
        self.stop_button.config(state='disabled')
    
    def update_output(self, text, success=True):
        """Update output display, typically for errors or full replacement."""
        self.output_display.config(state='normal')
        self.output_display.delete('1.0', tk.END)
        
        if success:
            self.output_display.insert('1.0', text)
        else:
            self.output_display.insert('1.0', f"❌ ERROR:\n{text}")
        
        self.output_display.config(state='disabled')
    
    def copy_output(self):
        """Copy output to clipboard"""
        output_text = self.output_display.get('1.0', tk.END).strip()
        if output_text:
            pyperclip.copy(output_text)
            messagebox.showinfo("Success", "Output copied to clipboard!")
        else:
            messagebox.showwarning("Warning", "No output to copy.")
    
    def save_output(self):
        """Save output to file using a file dialog."""
        output_text = self.output_display.get('1.0', tk.END).strip()
        if output_text:
            filepath = filedialog.asksaveasfilename(
                title="Save AI Output",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("Markdown files", "*.md"), ("All files", "*.*")],
                initialfile=f"clipboard_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(output_text)
                messagebox.showinfo("Success", f"Output saved to {filepath}")
        else:
            messagebox.showwarning("Warning", "No output to save.")

    def save_input(self):
        """Save input text to a file."""
        content = self.edit_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("Warning", "Input is empty.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Input saved to {filepath}")

    def load_input(self):
        """Load text from a file into the input area."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.edit_text.delete('1.0', tk.END)
            self.edit_text.insert('1.0', content)
    
    def quick_process(self):
        """Quick process from Read tab"""
        content = self.clipboard_display.get('1.0', tk.END).strip()
        if content:
            self.edit_text.delete('1.0', tk.END)
            self.edit_text.insert('1.0', content)
            self.notebook.select(1)  # Switch to Edit tab
            self.instruction_text.delete('1.0', tk.END)
            self.instruction_text.insert('1.0', "Please process this content:")
        else:
            messagebox.showwarning("Warning", "Clipboard is empty.")
    
    def switch_to_edit(self):
        """Switch to Edit tab"""
        self.notebook.select(1)
        self.load_to_edit()
    
    def update_model(self, event=None):
        """Update selected model"""
        self.current_model = self.model_var.get()

    def save_settings(self):
        """Save all current settings to the config file."""
        # Window settings
        self.config.set('Window', 'width', self.root.winfo_width())
        self.config.set('Window', 'height', self.root.winfo_height())
        
        # Ollama settings
        self.config.set('Ollama', 'url', self.url_var.get())
        self.config.set('Ollama', 'model', self.model_var.get())
        self.config.set('Ollama', 'num_gpu', self.num_gpu_var.get())

        # Application settings
        self.config.set('Application', 'auto_refresh_seconds', self.refresh_var.get())

        self.config.save()
        messagebox.showinfo("Settings Saved", "All settings have been saved to config.ini.")

    def on_closing(self):
        """Handle the window closing event."""
        self.config.set('Window', 'width', self.root.winfo_width())
        self.config.set('Window', 'height', self.root.winfo_height())
        self.config.save()
        self.root.destroy()
    
    def test_connection(self):
        """Test connection to Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                self.connection_label.config(text="✅ Connected successfully!", foreground="green")
            else:
                self.connection_label.config(text="❌ Connection failed", foreground="red")
        except Exception as e:
            self.connection_label.config(text=f"❌ Error: {str(e)}", foreground="red")
    
    def fetch_models(self):
        """Fetch available models from Ollama"""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            response.raise_for_status() # Raise an exception for bad status codes
            
            data = response.json()
            models = [model['name'] for model in data.get('models', [])]
            
            if models:
                self.models = models
                # Update combobox values
                self.model_combo['values'] = self.models
                self.model_var.set(models[0])
                self.current_model = models[0]
                messagebox.showinfo("Success", f"Found {len(models)} models.")
            else:
                messagebox.showwarning("Warning", "No models found on Ollama server.")

        except requests.exceptions.RequestException as e:
            messagebox.showerror("Connection Error", f"Failed to connect to Ollama: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {str(e)}")

    def refresh_gpu_stats(self):
        """Refresh GPU stats by running the shell script."""
        try:
            script_path = '/home/commander/Desktop/quick_clip/get_gpu_stats.sh'
            result = subprocess.run([script_path], capture_output=True, text=True, check=True, timeout=5)
            stats = result.stdout.strip()
            self.gpu_stats_label.config(text=stats, foreground="black")
        except FileNotFoundError:
            self.gpu_stats_label.config(text="Error: get_gpu_stats.sh not found.", foreground="red")
        except subprocess.CalledProcessError as e:
            self.gpu_stats_label.config(text=f"Script error: {e.stderr.strip()}", foreground="red")
        except subprocess.TimeoutExpired:
            self.gpu_stats_label.config(text="Script timed out.", foreground="red")
        except Exception as e:
            self.gpu_stats_label.config(text=f"An error occurred: {str(e)}", foreground="red")
    
    def start_auto_refresh(self):
        """Start auto-refresh timer"""
        if self.auto_refresh:
            self.refresh_clipboard()
            # Schedule next refresh
            try:
                interval = int(self.refresh_var.get()) * 1000  # Convert to milliseconds
            except:
                interval = 5000  # Default 5 seconds
            self.root.after(interval, self.start_auto_refresh)
    
    def toggle_auto_refresh(self):
        """Toggle auto-refresh"""
        self.auto_refresh = self.auto_refresh_var.get()

def main():
    root = tk.Tk()
    app = ClipboardAssistant(root)
    
    # Check for Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            messagebox.showwarning("Ollama Not Running", 
                                 "Ollama doesn't appear to be running on localhost:11434.\n"
                                 "Please ensure Ollama is installed and running.\n"
                                 "You can still use clipboard features without AI.")
    except:
        messagebox.showwarning("Ollama Not Found", 
                             "Could not connect to Ollama.\n"
                             "Install from: https://ollama.ai/\n"
                             "Then run: ollama run llama2\n\n"
                             "You can still use clipboard features without AI.")
    
    root.mainloop()

if __name__ == "__main__":
    # Install required packages if not present
    try:
        import pyperclip
        import requests
    except ImportError:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyperclip", "requests"])
        import pyperclip
        import requests
    
    main()