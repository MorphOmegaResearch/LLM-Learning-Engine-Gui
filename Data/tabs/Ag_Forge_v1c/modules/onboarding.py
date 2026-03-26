import tkinter as tk
from tkinter import ttk, messagebox
import json
import hashlib
import os
import uuid
from pathlib import Path

class OnboardingGUI:
    def __init__(self, data_root: Path, success_callback):
        self.data_root = data_root
        self.success_callback = success_callback
        
        self.root = tk.Tk()
        self.root.title("Ag Forge Onboarding")
        self.root.geometry("400x300")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self._setup_ui()
        
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Welcome to Ag Forge", font=('Arial', 14, 'bold')).pack(pady=(0, 20))
        ttk.Label(frame, text="Please set up your secure account:").pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(frame, text="Username:").pack(anchor=tk.W)
        self.user_var = tk.StringVar(value="commander")
        ttk.Entry(frame, textvariable=self.user_var).pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(frame, text="Password:").pack(anchor=tk.W)
        self.pass_var = tk.StringVar()
        self.pass_entry = ttk.Entry(frame, textvariable=self.pass_var, show="*")
        self.pass_entry.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Button(frame, text="Create Account & Initialize", 
                  command=self._initialize).pack(fill=tk.X)
        
    def _initialize(self):
        username = self.user_var.get().strip()
        password = self.pass_var.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Username and Password are required.")
            return
            
        try:
            # 1. Create directory structure
            self.data_root.mkdir(parents=True, exist_ok=True)
            (self.data_root / "knowledge").mkdir(exist_ok=True)
            (self.data_root / "data").mkdir(exist_ok=True)
            (self.data_root / "media").mkdir(exist_ok=True)
            (self.data_root / "orchestrator_context").mkdir(exist_ok=True)
            
            # 2. Hash password with salt
            salt = os.urandom(32)
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            
            # 3. Save config
            config = {
                "username": username,
                "salt": salt.hex(),
                "key": key.hex(),
                "created_at": str(uuid.uuid4()),
                "version": "1.0"
            }
            
            with open(self.data_root / "config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo("Success", "Account created and system initialized.")
            self.root.destroy()
            
            # Generate session token for immediate start
            session_token = hashlib.sha256((password + config['created_at']).encode()).hexdigest()
            self.success_callback(config, session_token)
            
        except Exception as e:
            messagebox.showerror("Initialization Error", str(e))

    def run(self):
        self.root.mainloop()

class LoginGUI:
    def __init__(self, data_root: Path, success_callback):
        self.data_root = data_root
        self.success_callback = success_callback
        
        self.root = tk.Tk()
        self.root.title("Ag Forge Login")
        self.root.geometry("350x200")
        self.root.resizable(False, False)
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self._setup_ui()
        
    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        frame = ttk.Frame(self.root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Security Required", font=('Arial', 12, 'bold')).pack(pady=(0, 10))
        
        ttk.Label(frame, text="Password:").pack(anchor=tk.W)
        self.pass_var = tk.StringVar()
        self.pass_entry = ttk.Entry(frame, textvariable=self.pass_var, show="*")
        self.pass_entry.pack(fill=tk.X, pady=(0, 20))
        self.pass_entry.bind('<Return>', lambda e: self._login())
        
        ttk.Button(frame, text="Unlock", command=self._login).pack(fill=tk.X)
        
    def _login(self):
        password = self.pass_var.get()
        
        try:
            with open(self.data_root / "config.json", "r") as f:
                config = json.load(f)
                
            salt = bytes.fromhex(config['salt'])
            stored_key = bytes.fromhex(config['key'])
            
            new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            
            if new_key == stored_key:
                self.root.destroy()
                # Create a session token (short-lived for this run)
                session_token = hashlib.sha256((password + config['created_at']).encode()).hexdigest()
                self.success_callback(config, session_token)
            else:
                messagebox.showerror("Error", "Invalid Password.")
        except Exception as e:
            messagebox.showerror("Login Error", str(e))

    def run(self):
        self.root.mainloop()
