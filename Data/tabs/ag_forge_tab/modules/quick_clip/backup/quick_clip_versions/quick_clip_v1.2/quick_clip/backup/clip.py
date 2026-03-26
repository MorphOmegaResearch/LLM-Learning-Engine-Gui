import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pyperclip
import requests
import json
import threading
from datetime import datetime

class ClipboardAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("Clipboard Assistant")
        self.root.geometry("800x600")
        
        # Ollama configuration
        self.ollama_url = "http://localhost:11434/api/generate"
        self.current_model = "llama2"  # Default model
        self.models = ["llama2", "mistral", "codellama", "phi", "tinyllama"]
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
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
        
        # Quick action buttons
        quick_actions = [
            ("Summarize", "Please summarize this text concisely."),
            ("Improve Grammar", "Please fix any grammar issues and improve writing."),
            ("Explain", "Please explain this in simple terms."),
            ("Translate to Code", "Convert this to pseudocode or Python.")
        ]
        
        for action, prompt in quick_actions:
            ttk.Button(process_btn_frame, text=action,
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
        
        ttk.Button(output_btn_frame, text="🚀 Process with AI", 
                  command=self.process_with_ai).pack(side='left', padx=5)
        ttk.Button(output_btn_frame, text="📋 Copy Output", 
                  command=self.copy_output).pack(side='left', padx=5)
        ttk.Button(output_btn_frame, text="💾 Save to File", 
                  command=self.save_output).pack(side='left', padx=5)
        
        # Status label
        self.status_label = ttk.Label(output_frame, text="Ready", foreground="gray")
        self.status_label.pack(side='left', pady=5)
    
    def create_config_tab(self):
        """Create configuration tab"""
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text='⚙️ Settings')
        
        # Ollama settings frame
        settings_frame = ttk.LabelFrame(self.config_frame, text="Ollama Settings", padding=20)
        settings_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Model selection
        ttk.Label(settings_frame, text="Model:", 
                 font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        
        self.model_var = tk.StringVar(value=self.current_model)
        model_combo = ttk.Combobox(settings_frame, textvariable=self.model_var,
                                  values=self.models, state='readonly', width=20)
        model_combo.grid(row=0, column=1, padx=10, pady=5)
        model_combo.bind('<<ComboboxSelected>>', self.update_model)
        
        # Server URL
        ttk.Label(settings_frame, text="Server URL:", 
                 font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        
        self.url_var = tk.StringVar(value=self.ollama_url)
        url_entry = ttk.Entry(settings_frame, textvariable=self.url_var, width=40)
        url_entry.grid(row=1, column=1, padx=10, pady=5)
        
        # Auto-refresh interval
        ttk.Label(settings_frame, text="Auto-refresh (seconds):", 
                 font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        
        self.refresh_var = tk.StringVar(value="5")
        refresh_entry = ttk.Entry(settings_frame, textvariable=self.refresh_var, width=10)
        refresh_entry.grid(row=2, column=1, sticky='w', padx=10, pady=5)
        
        # Test connection button
        ttk.Button(settings_frame, text="🔗 Test Connection", 
                  command=self.test_connection).grid(row=3, column=0, columnspan=2, pady=20)
        
        # Connection status
        self.connection_label = ttk.Label(settings_frame, text="", foreground="gray")
        self.connection_label.grid(row=4, column=0, columnspan=2, pady=5)
        
        # Fetch available models button
        ttk.Button(settings_frame, text="🔄 Fetch Available Models", 
                  command=self.fetch_models).grid(row=5, column=0, columnspan=2, pady=10)
    
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
        
        # Combine instruction and content
        prompt = f"{instruction}\n\nContent:\n{content}"
        
        # Update status
        self.status_label.config(text="Processing...", foreground="orange")
        self.root.update()
        
        # Run in separate thread to avoid freezing GUI
        thread = threading.Thread(target=self.call_ollama, args=(prompt,))
        thread.daemon = True
        thread.start()
    
    def call_ollama(self, prompt):
        """Call Ollama API"""
        try:
            payload = {
                "model": self.current_model,
                "prompt": prompt,
                "stream": False
            }
            
            response = requests.post(self.ollama_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                output_text = result.get('response', '')
                
                # Update GUI from main thread
                self.root.after(0, self.update_output, output_text, True)
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Done! (Tokens: {result.get('total_duration', 0)/1e9:.2f}s)", 
                    foreground="green"))
            else:
                error_msg = f"Error {response.status_code}: {response.text}"
                self.root.after(0, self.update_output, error_msg, False)
                self.root.after(0, lambda: self.status_label.config(
                    text="Failed", foreground="red"))
                
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to Ollama. Make sure Ollama is running on localhost:11434"
            self.root.after(0, self.update_output, error_msg, False)
            self.root.after(0, lambda: self.status_label.config(
                text="Connection failed", foreground="red"))
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.root.after(0, self.update_output, error_msg, False)
            self.root.after(0, lambda: self.status_label.config(
                text="Error", foreground="red"))
    
    def update_output(self, text, success=True):
        """Update output display"""
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
        """Save output to file"""
        output_text = self.output_display.get('1.0', tk.END).strip()
        if output_text:
            filename = f"clipboard_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output_text)
            messagebox.showinfo("Success", f"Output saved to {filename}")
        else:
            messagebox.showwarning("Warning", "No output to save.")
    
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
            if response.status_code == 200:
                data = response.json()
                models = [model['name'] for model in data.get('models', [])]
                if models:
                    self.models = models
                    self.model_var.set(models[0])
                    self.current_model = models[0]
                    messagebox.showinfo("Success", f"Found {len(models)} models")
                else:
                    messagebox.showwarning("Warning", "No models found")
            else:
                messagebox.showerror("Error", "Failed to fetch models")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {str(e)}")
    
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