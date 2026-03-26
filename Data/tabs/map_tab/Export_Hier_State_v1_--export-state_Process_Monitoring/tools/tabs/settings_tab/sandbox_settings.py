"""
Sandbox Settings UI - User Controls for API Protection

Backend settings for API sandboxing with user-friendly toggles
"""

import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api_sandboxing import get_sandbox


class SandboxSettingsFrame(ttk.Frame):
    """Settings frame for API sandboxing configuration"""

    def __init__(self, parent):
        super().__init__(parent)

        self.sandbox = get_sandbox()

        self.create_ui()
        self.load_settings()

    def create_ui(self):
        """Create the sandbox settings UI"""

        # Header
        header = tk.Frame(self, bg='#ff6600', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🛡️ API SECURITY & SANDBOXING",
            font=("Arial", 12, "bold"),
            bg='#ff6600',
            fg='white'
        ).pack(side=tk.LEFT, padx=15, pady=10)

        # Description
        desc_frame = tk.Frame(self, bg='#2d2d2d')
        desc_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(
            desc_frame,
            text="⚠️ PROTECT YOUR INTELLECTUAL PROPERTY\n\n"
                 "Controls what external API models (Claude, GPT, etc.) can access.\n"
                 "Local models get full access. API models are sandboxed.",
            font=("Arial", 9),
            bg='#2d2d2d',
            fg='white',
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, padx=10, pady=10)

        # Main settings
        content = tk.Frame(self, bg='#1a1a1a')
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # Master toggle
        master_frame = tk.LabelFrame(
            content,
            text="🔐 Master Control",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        master_frame.pack(fill=tk.X, pady=(0, 15))

        self.sandbox_enabled_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            master_frame,
            text="Enable API Sandboxing (RECOMMENDED)",
            variable=self.sandbox_enabled_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 10),
            command=self.on_toggle_sandbox
        ).pack(anchor=tk.W)

        tk.Label(
            master_frame,
            text="When ENABLED: External APIs cannot access your system knowledge.\n"
                 "When DISABLED: All models get full access (DANGEROUS!).",
            bg='#2d2d2d',
            fg='#ffaa00',
            font=("Arial", 8),
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(5, 0))

        # Claude-specific settings
        claude_frame = tk.LabelFrame(
            content,
            text="🤖 Claude API Settings",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        claude_frame.pack(fill=tk.X, pady=(0, 15))

        self.claude_project_context_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            claude_frame,
            text="Allow Claude to access Living Project context",
            variable=self.claude_project_context_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        self.claude_file_context_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            claude_frame,
            text="Allow Claude to access current file context",
            variable=self.claude_file_context_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        self.claude_web_search_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            claude_frame,
            text="Allow Claude to perform web searches",
            variable=self.claude_web_search_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        tk.Label(
            claude_frame,
            text="⚠️ Claude will NEVER access sys_knowledge (your IP protection)",
            bg='#2d2d2d',
            fg='#00ff00',
            font=("Arial", 8, "bold"),
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(10, 0))

        # Other API settings
        other_frame = tk.LabelFrame(
            content,
            text="🌐 Other API Models (GPT, etc.)",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        other_frame.pack(fill=tk.X, pady=(0, 15))

        self.other_project_context_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            other_frame,
            text="Allow other APIs to access Living Project context",
            variable=self.other_project_context_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        self.other_file_context_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            other_frame,
            text="Allow other APIs to access current file context",
            variable=self.other_file_context_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        tk.Label(
            other_frame,
            text="Default: Minimal access for untrusted APIs",
            bg='#2d2d2d',
            fg='#ffaa00',
            font=("Arial", 8),
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(10, 0))

        # Logging
        log_frame = tk.LabelFrame(
            content,
            text="📊 Access Logging",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold"),
            padx=15,
            pady=15
        )
        log_frame.pack(fill=tk.X, pady=(0, 15))

        self.log_api_access_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            log_frame,
            text="Log when API models are blocked from accessing protected data",
            variable=self.log_api_access_var,
            bg='#2d2d2d',
            fg='white',
            selectcolor='#1a1a1a',
            font=("Arial", 9)
        ).pack(anchor=tk.W)

        # Status display
        status_frame = tk.Frame(content, bg='#2d2d2d', relief=tk.RIDGE, borderwidth=2)
        status_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            status_frame,
            text="Current Protection Status",
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 10, "bold")
        ).pack(pady=(10, 5))

        self.status_text = tk.Text(
            status_frame,
            height=8,
            bg='#0a0a0a',
            fg='#00ff00',
            font=("Courier", 9),
            wrap=tk.WORD
        )
        self.status_text.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Action buttons
        btn_frame = tk.Frame(content, bg='#1a1a1a')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        tk.Button(
            btn_frame,
            text="💾 Save Settings",
            command=self.save_settings,
            bg='#0066cc',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2'
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="🔄 Reset to Defaults",
            command=self.reset_defaults,
            bg='#ff8800',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2'
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="🧪 Test Sandboxing",
            command=self.test_sandboxing,
            bg='#00aa00',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2'
        ).pack(side=tk.LEFT)

    def load_settings(self):
        """Load current settings from sandbox"""
        rules = self.sandbox.rules

        # Master toggle
        self.sandbox_enabled_var.set(rules.get('sandbox_enabled', True))

        # Claude settings
        claude_rules = rules['api_models'].get('claude', {})
        self.claude_project_context_var.set(claude_rules.get('allow_project_context', True))
        self.claude_file_context_var.set(claude_rules.get('allow_file_context', True))
        self.claude_web_search_var.set(claude_rules.get('allow_web_search', True))

        # Other API settings
        other_rules = rules['api_models'].get('openai', {})
        self.other_project_context_var.set(other_rules.get('allow_project_context', False))
        self.other_file_context_var.set(other_rules.get('allow_file_context', True))

        # Logging
        self.log_api_access_var.set(rules.get('log_api_access', True))

        self.update_status()

    def save_settings(self):
        """Save settings to sandbox config"""
        rules = self.sandbox.rules

        # Master toggle
        rules['sandbox_enabled'] = self.sandbox_enabled_var.get()

        # Claude settings
        claude_rules = rules['api_models']['claude']
        claude_rules['allow_project_context'] = self.claude_project_context_var.get()
        claude_rules['allow_file_context'] = self.claude_file_context_var.get()
        claude_rules['allow_web_search'] = self.claude_web_search_var.get()

        # Other API settings
        other_rules = rules['api_models']['openai']
        other_rules['allow_project_context'] = self.other_project_context_var.get()
        other_rules['allow_file_context'] = self.other_file_context_var.get()

        # Logging
        rules['log_api_access'] = self.log_api_access_var.get()

        # Save to disk
        self.sandbox.save_rules()

        self.update_status()
        messagebox.showinfo("Saved", "Sandbox settings saved successfully!")

    def reset_defaults(self):
        """Reset to recommended defaults"""
        response = messagebox.askyesno(
            "Reset Settings",
            "Reset to recommended security defaults?\n\n"
            "This will:\n"
            "- Enable sandboxing\n"
            "- Block sys_knowledge for APIs\n"
            "- Allow Claude project access\n"
            "- Minimize other API access"
        )

        if response:
            self.sandbox_enabled_var.set(True)
            self.claude_project_context_var.set(True)
            self.claude_file_context_var.set(True)
            self.claude_web_search_var.set(True)
            self.other_project_context_var.set(False)
            self.other_file_context_var.set(True)
            self.log_api_access_var.set(True)

            self.save_settings()

    def on_toggle_sandbox(self):
        """Handle master sandbox toggle"""
        if not self.sandbox_enabled_var.get():
            response = messagebox.askyesno(
                "⚠️ WARNING",
                "DISABLING SANDBOXING IS DANGEROUS!\n\n"
                "This will allow external APIs to access your:\n"
                "- System knowledge\n"
                "- System blueprints\n"
                "- Intellectual property\n\n"
                "Are you SURE you want to disable protection?",
                icon='warning'
            )

            if not response:
                self.sandbox_enabled_var.set(True)
                return

        self.update_status()

    def update_status(self):
        """Update status display"""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)

        if self.sandbox_enabled_var.get():
            self.status_text.insert(tk.END, "🛡️ SANDBOXING ACTIVE - IP PROTECTED\n\n", 'protected')
        else:
            self.status_text.insert(tk.END, "⚠️ SANDBOXING DISABLED - UNPROTECTED!\n\n", 'danger')

        # Claude status
        self.status_text.insert(tk.END, "Claude API (Trust: ⭐⭐⭐⭐⭐):\n")
        self.status_text.insert(tk.END, f"  ✅ Project Context: {'Allowed' if self.claude_project_context_var.get() else 'Blocked'}\n")
        self.status_text.insert(tk.END, f"  ✅ File Context: {'Allowed' if self.claude_file_context_var.get() else 'Blocked'}\n")
        self.status_text.insert(tk.END, f"  🚫 System Knowledge: ALWAYS BLOCKED\n\n")

        # Other APIs
        self.status_text.insert(tk.END, "Other APIs (GPT, etc.):\n")
        self.status_text.insert(tk.END, f"  {'✅' if self.other_project_context_var.get() else '🚫'} Project Context: {'Allowed' if self.other_project_context_var.get() else 'Blocked'}\n")
        self.status_text.insert(tk.END, f"  {'✅' if self.other_file_context_var.get() else '🚫'} File Context: {'Allowed' if self.other_file_context_var.get() else 'Blocked'}\n")
        self.status_text.insert(tk.END, f"  🚫 System Knowledge: ALWAYS BLOCKED\n")

        self.status_text.tag_config('protected', foreground='#00ff00', font=("Courier", 9, "bold"))
        self.status_text.tag_config('danger', foreground='#ff0000', font=("Courier", 9, "bold"))
        self.status_text.config(state=tk.DISABLED)

    def test_sandboxing(self):
        """Test sandboxing with example data"""
        test_context = {
            'user_query': 'Test query',
            'sys_knowledge': {'secret': 'INTELLECTUAL PROPERTY'},
            'system_blueprints': {'design': 'PROPRIETARY'},
            'project_context': {'file': 'test.py'},
            'task': 'Test task'
        }

        # Test Claude
        claude_filtered = self.sandbox.filter_context("claude-sonnet-4", test_context, is_api=True)
        claude_has_sys = 'sys_knowledge' in claude_filtered

        # Test GPT
        gpt_filtered = self.sandbox.filter_context("gpt-4", test_context, is_api=True)
        gpt_has_sys = 'sys_knowledge' in gpt_filtered

        # Test local
        local_filtered = self.sandbox.filter_context("qwen2.5-coder", test_context, is_api=False)
        local_has_sys = 'sys_knowledge' in local_filtered

        result = f"""🧪 SANDBOXING TEST RESULTS

Original Context: {len(test_context)} keys
{list(test_context.keys())}

Claude API:
  Received: {len(claude_filtered)} keys
  {list(claude_filtered.keys())}
  System Knowledge: {'❌ BLOCKED' if not claude_has_sys else '⚠️ LEAKED!'}

GPT API:
  Received: {len(gpt_filtered)} keys
  {list(gpt_filtered.keys())}
  System Knowledge: {'❌ BLOCKED' if not gpt_has_sys else '⚠️ LEAKED!'}

Local Model:
  Received: {len(local_filtered)} keys
  {list(local_filtered.keys())}
  System Knowledge: {'✅ ALLOWED' if local_has_sys else '❌ BLOCKED'}

{'✅ SANDBOXING WORKING!' if not claude_has_sys and not gpt_has_sys and local_has_sys else '⚠️ PROBLEM DETECTED!'}
"""

        messagebox.showinfo("Test Results", result)


# Testing
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Sandbox Settings Test")
    root.geometry("700x800")

    frame = SandboxSettingsFrame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    root.mainloop()
