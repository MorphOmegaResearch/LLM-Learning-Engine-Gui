"""
Emergency Control Panel for AI Automation

Floating window that stays on top during automation sessions.
Provides emergency stop, pause, chat, and voice control.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional, Callable
from datetime import datetime


class EmergencyControlPanel(tk.Toplevel):
    """
    Floating control panel for monitoring and controlling AI automation

    Features:
    - Always on top
    - Pause/Stop controls
    - Live chat with agent
    - Voice mute toggle
    - Trust level display
    - Emergency instructions
    """

    def __init__(self, parent, agent_name: str, trust_level: int = 3):
        super().__init__(parent)

        self.agent_name = agent_name
        self.trust_level = trust_level  # 1-5 stars

        # State
        self.paused = False
        self.stopped = False
        self.voice_muted = True  # Default muted (people asleep!)

        # Callbacks
        self.on_pause: Optional[Callable] = None
        self.on_stop: Optional[Callable] = None
        self.on_instruction: Optional[Callable] = None
        self.on_voice_toggle: Optional[Callable] = None

        self.setup_window()
        self.create_ui()

    def setup_window(self):
        """Configure window properties"""
        self.title("🛡️ Agent Control")
        self.geometry("350x500")

        # Always on top
        self.attributes('-topmost', True)

        # Position in top-right corner
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        x = screen_w - 370
        y = 20
        self.geometry(f"+{x}+{y}")

        # Prevent accidental close
        self.protocol("WM_DELETE_WINDOW", self.on_close_attempt)

        self.configure(bg='#1a1a1a')

    def create_ui(self):
        """Create control panel UI"""

        # Header
        header = tk.Frame(self, bg='#cc0000', height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🛡️ AGENT CONTROL",
            font=("Arial", 12, "bold"),
            bg='#cc0000',
            fg='white'
        ).pack(pady=5)

        # Agent info
        info_frame = tk.Frame(header, bg='#cc0000')
        info_frame.pack(fill=tk.X, padx=10)

        tk.Label(
            info_frame,
            text=f"Agent: {self.agent_name}",
            font=("Arial", 9),
            bg='#cc0000',
            fg='white'
        ).pack(side=tk.LEFT)

        # Trust stars
        stars = "⭐" * self.trust_level + "☆" * (5 - self.trust_level)
        tk.Label(
            info_frame,
            text=stars,
            font=("Arial", 9),
            bg='#cc0000',
            fg='white'
        ).pack(side=tk.RIGHT)

        # Content
        content = tk.Frame(self, bg='#1a1a1a')
        content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status
        self.status_label = tk.Label(
            content,
            text="⚪ Waiting to start...",
            font=("Arial", 10, "bold"),
            bg='#1a1a1a',
            fg='#ffaa00'
        )
        self.status_label.pack(pady=(0, 10))

        # Control buttons
        btn_frame = tk.Frame(content, bg='#1a1a1a')
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.pause_btn = tk.Button(
            btn_frame,
            text="⏸️ PAUSE",
            command=self.toggle_pause,
            bg='#ff8800',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2'
        )
        self.pause_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        tk.Button(
            btn_frame,
            text="⏹️ STOP",
            command=self.emergency_stop,
            bg='#cc0000',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2'
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Voice toggle
        voice_frame = tk.Frame(content, bg='#1a1a1a')
        voice_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(
            voice_frame,
            text="🎤 Voice:",
            bg='#1a1a1a',
            fg='white',
            font=("Arial", 9)
        ).pack(side=tk.LEFT, padx=(0, 5))

        self.voice_btn = tk.Button(
            voice_frame,
            text="🔇 MUTED",
            command=self.toggle_voice,
            bg='#555555',
            fg='white',
            font=("Arial", 9, "bold"),
            cursor='hand2',
            width=12
        )
        self.voice_btn.pack(side=tk.LEFT)

        # Chat section
        tk.Label(
            content,
            text="💬 Chat with Agent:",
            bg='#1a1a1a',
            fg='white',
            font=("Arial", 9, "bold"),
            anchor=tk.W
        ).pack(fill=tk.X, pady=(5, 3))

        # Chat log
        self.chat_log = scrolledtext.ScrolledText(
            content,
            height=10,
            bg='#0a0a0a',
            fg='#00ff00',
            font=("Consolas", 8),
            wrap=tk.WORD
        )
        self.chat_log.pack(fill=tk.BOTH, expand=True)
        self.chat_log.config(state=tk.DISABLED)

        # Input
        input_frame = tk.Frame(content, bg='#1a1a1a')
        input_frame.pack(fill=tk.X, pady=(5, 0))

        self.input_entry = tk.Entry(
            input_frame,
            bg='#2d2d2d',
            fg='white',
            font=("Arial", 9),
            insertbackground='white'
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.input_entry.bind('<Return>', lambda e: self.send_instruction())

        tk.Button(
            input_frame,
            text="➤",
            command=self.send_instruction,
            bg='#0066cc',
            fg='white',
            font=("Arial", 9, "bold"),
            cursor='hand2',
            width=3
        ).pack(side=tk.LEFT)

        # Initial messages
        self.log_chat("SYSTEM", "Emergency controls active")
        self.log_chat("SYSTEM", "Press ESC or click STOP to abort")
        self.log_chat("SYSTEM", f"Voice: MUTED (people asleep)")

    def log_chat(self, sender: str, message: str):
        """Add message to chat log"""
        self.chat_log.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if sender == "SYSTEM":
            prefix = f"[{timestamp}] 🛡️ "
            self.chat_log.insert(tk.END, prefix, 'system')
        elif sender == "USER":
            prefix = f"[{timestamp}] 👤 "
            self.chat_log.insert(tk.END, prefix, 'user')
        elif sender == "AGENT":
            prefix = f"[{timestamp}] 🤖 "
            self.chat_log.insert(tk.END, prefix, 'agent')
        else:
            prefix = f"[{timestamp}] "
            self.chat_log.insert(tk.END, prefix)

        self.chat_log.insert(tk.END, f"{message}\n")
        self.chat_log.see(tk.END)
        self.chat_log.config(state=tk.DISABLED)

        # Configure tags
        self.chat_log.tag_config('system', foreground='#ffaa00')
        self.chat_log.tag_config('user', foreground='#00bfff')
        self.chat_log.tag_config('agent', foreground='#00ff00')

    def update_status(self, status: str, color: str = '#ffaa00'):
        """Update status display"""
        self.status_label.config(text=status, fg=color)

    def toggle_pause(self):
        """Pause/Resume automation"""
        self.paused = not self.paused

        if self.paused:
            self.pause_btn.config(text="▶️ RESUME", bg='#00cc00')
            self.update_status("⏸️ PAUSED", '#ff8800')
            self.log_chat("SYSTEM", "Agent PAUSED by user")
        else:
            self.pause_btn.config(text="⏸️ PAUSE", bg='#ff8800')
            self.update_status("🟢 RUNNING", '#00ff00')
            self.log_chat("SYSTEM", "Agent RESUMED")

        if self.on_pause:
            self.on_pause(self.paused)

    def emergency_stop(self):
        """Emergency stop - abort everything"""
        if not self.stopped:
            self.stopped = True
            self.update_status("🛑 STOPPED", '#cc0000')
            self.log_chat("SYSTEM", "EMERGENCY STOP activated!")

            # Disable controls
            self.pause_btn.config(state=tk.DISABLED)

            if self.on_stop:
                self.on_stop()

    def toggle_voice(self):
        """Toggle voice output"""
        self.voice_muted = not self.voice_muted

        if self.voice_muted:
            self.voice_btn.config(text="🔇 MUTED", bg='#555555')
            self.log_chat("SYSTEM", "Voice MUTED")
        else:
            self.voice_btn.config(text="🔊 ACTIVE", bg='#0066cc')
            self.log_chat("SYSTEM", "Voice ACTIVE")

        if self.on_voice_toggle:
            self.on_voice_toggle(not self.voice_muted)

    def send_instruction(self):
        """Send instruction to agent"""
        instruction = self.input_entry.get().strip()
        if not instruction:
            return

        self.input_entry.delete(0, tk.END)
        self.log_chat("USER", instruction)

        # Handle special commands
        if instruction.lower() == "stop":
            self.emergency_stop()
        elif instruction.lower() == "pause":
            if not self.paused:
                self.toggle_pause()
        elif instruction.lower() == "resume":
            if self.paused:
                self.toggle_pause()
        else:
            # Pass to agent
            if self.on_instruction:
                self.on_instruction(instruction)
                self.log_chat("SYSTEM", "Instruction sent to agent")

    def on_close_attempt(self):
        """Prevent accidental close"""
        # Show confirmation
        from tkinter import messagebox
        response = messagebox.askyesno(
            "Close Control Panel?",
            "This will STOP the automation.\n\nContinue?",
            parent=self
        )

        if response:
            self.emergency_stop()
            self.destroy()


# Testing
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    panel = EmergencyControlPanel(root, "Claude Sonnet 4", trust_level=5)

    # Test callbacks
    panel.on_pause = lambda paused: print(f"Paused: {paused}")
    panel.on_stop = lambda: print("STOPPED!")
    panel.on_instruction = lambda inst: print(f"Instruction: {inst}")
    panel.on_voice_toggle = lambda active: print(f"Voice: {active}")

    # Simulate activity
    def simulate():
        panel.update_status("🟢 WORKING...", '#00ff00')
        panel.log_chat("AGENT", "Taking screenshot...")
        panel.after(2000, lambda: panel.log_chat("AGENT", "Analyzing..."))
        panel.after(4000, lambda: panel.log_chat("AGENT", "Clicking button..."))

    panel.after(1000, simulate)

    panel.mainloop()
