"""
Web Browser Sub-Tab (Phase 1.6E)

GUI automation and browser testing controls using pyautogui.
Provides interface for:
- Taking screenshots
- Mouse automation (click, drag, move)
- Keyboard automation (type, press keys)
- Element detection
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from tabs.base_tab import BaseTab
from logger_util import get_tab_logger

log_message, log_error, log_exception = get_tab_logger('custom_code')


class WebBrowserTab(BaseTab):
    """Web browser automation controls"""

    def __init__(self, parent, root, style, parent_tab=None):
        super().__init__(parent, root, style)
        self.parent_tab = parent_tab
        self.browser_tools = None

    def create_ui(self):
        """Create the web browser automation UI"""
        log_message("WEB_BROWSER_TAB: Creating UI...")

        self.parent.columnconfigure(0, weight=1)
        self.parent.rowconfigure(0, weight=0)  # Header
        self.parent.rowconfigure(1, weight=1)  # Content

        # Header
        header_frame = ttk.Frame(self.parent, style='Category.TFrame')
        header_frame.grid(row=0, column=0, sticky=tk.EW, padx=10, pady=10)

        ttk.Label(
            header_frame,
            text="🌐 Browser Automation Controls",
            font=("Arial", 12, "bold"),
            style='CategoryPanel.TLabel'
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            header_frame,
            text="🔧 Initialize Tools",
            command=self._initialize_tools,
            style='Action.TButton'
        ).pack(side=tk.RIGHT)

        # Main content area with scrollbar
        content_container = ttk.Frame(self.parent, style='Category.TFrame')
        content_container.grid(row=1, column=0, sticky=tk.NSEW, padx=10, pady=(0, 10))
        content_container.columnconfigure(0, weight=1)
        content_container.rowconfigure(0, weight=1)

        canvas = tk.Canvas(content_container, bg='#2d2d2d', highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_container, orient=tk.VERTICAL, command=canvas.yview)
        self.content_frame = ttk.Frame(canvas, style='Category.TFrame')

        self.content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.content_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        # Create control sections
        self._create_screenshot_section()
        self._create_mouse_section()
        self._create_keyboard_section()
        self._create_status_section()

        log_message("WEB_BROWSER_TAB: UI created successfully")

    def _initialize_tools(self):
        """Initialize browser tools"""
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from browser_tools import create_browser_tools

            self.browser_tools = create_browser_tools()
            info = self.browser_tools.get_info()

            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, f"✓ Browser tools initialized\n")
            self.status_text.insert(tk.END, f"Screen size: {info['screen_size']}\n")
            self.status_text.insert(tk.END, f"Mouse position: {info['mouse_position']}\n")
            self.status_text.insert(tk.END, f"Failsafe: {info['failsafe_enabled']}\n")

            messagebox.showinfo("Success", "Browser tools initialized successfully!")
            log_message("WEB_BROWSER_TAB: Browser tools initialized")

        except Exception as e:
            error_msg = f"Failed to initialize browser tools: {e}"
            self.status_text.delete(1.0, tk.END)
            self.status_text.insert(1.0, f"❌ {error_msg}\n")
            messagebox.showerror("Error", error_msg)
            log_message(f"WEB_BROWSER_TAB ERROR: {e}")

    def _create_screenshot_section(self):
        """Create screenshot controls"""
        frame = ttk.LabelFrame(self.content_frame, text="📸 Screenshot", padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(frame, text="Capture screen or region", style='Config.TLabel').pack(anchor=tk.W, pady=(0, 5))

        btn_frame = ttk.Frame(frame, style='Category.TFrame')
        btn_frame.pack(fill=tk.X)

        ttk.Button(
            btn_frame,
            text="📸 Full Screen",
            command=self._screenshot_full,
            width=15
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            btn_frame,
            text="🔲 Region",
            command=self._screenshot_region,
            width=15
        ).pack(side=tk.LEFT, padx=2)

    def _create_mouse_section(self):
        """Create mouse control section"""
        frame = ttk.LabelFrame(self.content_frame, text="🖱️ Mouse Controls", padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)

        # Mouse position display
        self.mouse_pos_label = ttk.Label(frame, text="Position: (0, 0)", style='Config.TLabel')
        self.mouse_pos_label.pack(anchor=tk.W, pady=(0, 5))

        ttk.Button(
            frame,
            text="🔄 Update Position",
            command=self._update_mouse_position,
            width=15
        ).pack(anchor=tk.W, pady=(0, 10))

        # Click controls
        ttk.Label(frame, text="Click at coordinates:", style='Config.TLabel').pack(anchor=tk.W)

        coord_frame = ttk.Frame(frame, style='Category.TFrame')
        coord_frame.pack(fill=tk.X, pady=5)

        ttk.Label(coord_frame, text="X:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.click_x_entry = ttk.Entry(coord_frame, width=10)
        self.click_x_entry.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(coord_frame, text="Y:", style='Config.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        self.click_y_entry = ttk.Entry(coord_frame, width=10)
        self.click_y_entry.pack(side=tk.LEFT)

        # Click buttons
        click_btn_frame = ttk.Frame(frame, style='Category.TFrame')
        click_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            click_btn_frame,
            text="Left Click",
            command=lambda: self._do_click('left'),
            width=12
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            click_btn_frame,
            text="Right Click",
            command=lambda: self._do_click('right'),
            width=12
        ).pack(side=tk.LEFT, padx=2)

        ttk.Button(
            click_btn_frame,
            text="Double Click",
            command=self._do_double_click,
            width=12
        ).pack(side=tk.LEFT, padx=2)

    def _create_keyboard_section(self):
        """Create keyboard control section"""
        frame = ttk.LabelFrame(self.content_frame, text="⌨️ Keyboard Controls", padding=10)
        frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(frame, text="Type text:", style='Config.TLabel').pack(anchor=tk.W, pady=(0, 5))

        type_frame = ttk.Frame(frame, style='Category.TFrame')
        type_frame.pack(fill=tk.X, pady=5)

        self.type_entry = ttk.Entry(type_frame, width=30)
        self.type_entry.pack(side=tk.LEFT, padx=(0, 5), fill=tk.X, expand=True)

        ttk.Button(
            type_frame,
            text="⌨️ Type",
            command=self._do_type_text,
            width=10
        ).pack(side=tk.LEFT)

        # Key press controls
        ttk.Label(frame, text="Press key:", style='Config.TLabel').pack(anchor=tk.W, pady=(10, 5))

        key_frame = ttk.Frame(frame, style='Category.TFrame')
        key_frame.pack(fill=tk.X)

        for key in ['enter', 'tab', 'esc', 'backspace', 'delete']:
            ttk.Button(
                key_frame,
                text=key.capitalize(),
                command=lambda k=key: self._do_press_key(k),
                width=10
            ).pack(side=tk.LEFT, padx=2)

    def _create_status_section(self):
        """Create status display section"""
        frame = ttk.LabelFrame(self.content_frame, text="📊 Status", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.status_text = tk.Text(
            frame,
            height=8,
            bg='#1e1e1e',
            fg='#cccccc',
            font=("Consolas", 9),
            wrap=tk.WORD
        )
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.insert(1.0, "Ready. Click 'Initialize Tools' to begin.\n")

    # Action methods
    def _screenshot_full(self):
        """Take full screen screenshot"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            filepath = self.browser_tools.screenshot()
            self.status_text.insert(tk.END, f"✓ Screenshot saved: {filepath}\n")
            self.status_text.see(tk.END)
            log_message(f"WEB_BROWSER_TAB: Screenshot saved to {filepath}")
        except Exception as e:
            self.status_text.insert(tk.END, f"❌ Screenshot failed: {e}\n")
            self.status_text.see(tk.END)
            log_message(f"WEB_BROWSER_TAB ERROR: Screenshot failed: {e}")

    def _screenshot_region(self):
        """Take region screenshot"""
        messagebox.showinfo("Region Screenshot", "Region screenshot feature coming soon.\nUse Full Screen for now.")

    def _update_mouse_position(self):
        """Update mouse position display"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            pos = self.browser_tools.get_mouse_position()
            self.mouse_pos_label.config(text=f"Position: {pos}")
            self.click_x_entry.delete(0, tk.END)
            self.click_x_entry.insert(0, str(pos[0]))
            self.click_y_entry.delete(0, tk.END)
            self.click_y_entry.insert(0, str(pos[1]))
        except Exception as e:
            log_message(f"WEB_BROWSER_TAB ERROR: Failed to get mouse position: {e}")

    def _do_click(self, button):
        """Perform mouse click"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            x = int(self.click_x_entry.get()) if self.click_x_entry.get() else None
            y = int(self.click_y_entry.get()) if self.click_y_entry.get() else None

            result = self.browser_tools.click(x, y, button=button)
            if result['success']:
                self.status_text.insert(tk.END, f"✓ {button.capitalize()} click at {result['position']}\n")
            else:
                self.status_text.insert(tk.END, f"❌ Click failed: {result.get('error')}\n")
            self.status_text.see(tk.END)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid X and Y coordinates")
        except Exception as e:
            self.status_text.insert(tk.END, f"❌ Click failed: {e}\n")
            self.status_text.see(tk.END)

    def _do_double_click(self):
        """Perform double click"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            x = int(self.click_x_entry.get()) if self.click_x_entry.get() else None
            y = int(self.click_y_entry.get()) if self.click_y_entry.get() else None

            result = self.browser_tools.double_click(x, y)
            if result['success']:
                self.status_text.insert(tk.END, f"✓ Double click at {result['position']}\n")
            else:
                self.status_text.insert(tk.END, f"❌ Double click failed: {result.get('error')}\n")
            self.status_text.see(tk.END)
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid X and Y coordinates")
        except Exception as e:
            self.status_text.insert(tk.END, f"❌ Double click failed: {e}\n")
            self.status_text.see(tk.END)

    def _do_type_text(self):
        """Type text"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            text = self.type_entry.get()
            if not text:
                return

            result = self.browser_tools.type_text(text)
            if result['success']:
                self.status_text.insert(tk.END, f"✓ Typed {result['length']} characters\n")
                self.type_entry.delete(0, tk.END)
            else:
                self.status_text.insert(tk.END, f"❌ Type failed: {result.get('error')}\n")
            self.status_text.see(tk.END)
        except Exception as e:
            self.status_text.insert(tk.END, f"❌ Type failed: {e}\n")
            self.status_text.see(tk.END)

    def _do_press_key(self, key):
        """Press a key"""
        if not self.browser_tools:
            messagebox.showwarning("Not Initialized", "Please initialize browser tools first")
            return

        try:
            result = self.browser_tools.press_key(key)
            if result['success']:
                self.status_text.insert(tk.END, f"✓ Pressed '{key}'\n")
            else:
                self.status_text.insert(tk.END, f"❌ Key press failed: {result.get('error')}\n")
            self.status_text.see(tk.END)
        except Exception as e:
            self.status_text.insert(tk.END, f"❌ Key press failed: {e}\n")
            self.status_text.see(tk.END)

    def on_show(self):
        """Called when tab becomes visible"""
        if self.browser_tools:
            self._update_mouse_position()
