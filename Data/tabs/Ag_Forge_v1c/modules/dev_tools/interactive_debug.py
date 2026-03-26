import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import functools
import traceback
import sys

def install_debug_hooks(root):
    """
    Installs advanced debug hooks (v4) with specific support for:
    - Menu Bars (walking through items)
    - Notebook Tabs (direct binding)
    - Command wrapping
    """
    sys.stderr.write("\n--- ADVANCED INTERACTIVE DEBUGGER v4 ENABLED ---\n")
    sys.stderr.write("Monitoring: Menus, Tabs, Buttons, Universal Clicks\n")
    sys.stderr.flush()

    # Keep track of wrapped widgets/items to avoid double-wrapping
    wrapped_registry = set()

    def log_action(msg, level="INFO"):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] [GUI_{level}] {msg}\n"
        sys.stdout.write(formatted_msg)
        sys.stdout.flush()
        if level in ["ERROR", "WARNING", "TRACE", "NAV"]:
            sys.stderr.write(formatted_msg)
            sys.stderr.flush()

    def debug_wrapper(source_name, command_func, *args, **kwargs):
        """Wraps a callback to catch and log errors."""
        func_name = getattr(command_func, "__name__", str(command_func))
        log_action(f"ACTION START: {source_name} -> {func_name}")
        
        try:
            result = command_func(*args, **kwargs)
            log_action(f"ACTION COMPLETE: {source_name}")
            return result
        except Exception as e:
            tb = traceback.format_exc()
            log_action(f"CRITICAL FAILURE in {source_name}:\n{tb}", "ERROR")
            try:
                messagebox.showerror(
                    "Debug Trap Caught Exception", 
                    f"Command failed in {source_name}\n\nError: {e}\n\nCheck terminal for traceback."
                )
            except:
                pass
            return None

    def hook_notebook(widget):
        """Bind directly to notebook tab change events."""
        w_id = str(widget)
        if w_id in wrapped_registry:
            return

        def on_tab_change(event):
            try:
                nb = event.widget
                select_id = nb.select()
                if select_id:
                    # Try to get the text label of the selected tab
                    index = nb.index(select_id)
                    text = nb.tab(select_id, "text")
                    log_action(f"TAB CHANGED: '{text}' (index {index}) on {nb}", "NAV")
            except Exception as e:
                log_action(f"Tab Change Error: {e}", "ERROR")

        widget.bind("<<NotebookTabChanged>>", on_tab_change, add="+")
        wrapped_registry.add(w_id)
        # log_action(f"Hooked Notebook: {widget}", "DEBUG")

    def hook_menu(widget):
        """Iterate over menu items and wrap their commands."""
        # Menus don't have a stable ID for individual items, so we check the menu widget itself
        # We re-scan menus often because items can be added dynamically.
        
        try:
            last_index = widget.index("end")
            if last_index is None:
                return
            
            for i in range(last_index + 1):
                item_id = f"{str(widget)}:item:{i}"
                if item_id in wrapped_registry:
                    continue
                
                try:
                    # Check if item has a command
                    cmd_func = widget.entrycget(i, "command")
                    label = widget.entrycget(i, "label")
                    
                    if cmd_func and callable(cmd_func) and not isinstance(cmd_func, functools.partial):
                        # Wrap it
                        wrapped = functools.partial(debug_wrapper, f"Menu: {label}", cmd_func)
                        widget.entryconfigure(i, command=wrapped)
                        wrapped_registry.add(item_id)
                        # log_action(f"Hooked Menu Item: {label}", "DEBUG")
                except:
                    pass # Item might be a separator or cascade
        except Exception:
            pass

    def scan_and_hook(widget):
        """Recursively scan widget tree."""
        widget_id = str(widget)

        # 1. Hook Notebooks
        if isinstance(widget, ttk.Notebook):
            hook_notebook(widget)

        # 2. Hook Menus
        if isinstance(widget, tk.Menu):
            hook_menu(widget)

        # 3. Hook Standard Widgets (Buttons, etc)
        if widget_id not in wrapped_registry:
            try:
                if widget.cget("command"):
                    original_command = widget.cget("command")
                    if callable(original_command):
                        # Get text identifier if possible
                        try:
                            txt = widget.cget("text") or widget_id
                        except:
                            txt = widget_id
                            
                        wrapped = functools.partial(debug_wrapper, f"Widget: {txt}", original_command)
                        widget.configure(command=wrapped)
                        wrapped_registry.add(widget_id)
            except:
                pass

        # 4. Recurse
        # Note: Menus are often children of root or toplevels, but winfo_children finds them.
        for child in widget.winfo_children():
            scan_and_hook(child)

    # Initial scan
    scan_and_hook(root)

    # High-frequency periodic re-scan (1s) to catch dynamic UI updates
    def periodic_scan():
        scan_and_hook(root)
        root.after(1000, periodic_scan)
    
    root.after(1000, periodic_scan)

    # Universal Click Logger (Passive)
    def log_universal_click(event):
        try:
            w = event.widget
            w_class = w.winfo_class()
            
            # Identify text
            text_id = ""
            try:
                text_id = w.cget("text")
                if len(text_id) > 20: text_id = text_id[:20] + "..."
            except:
                pass
            
            log_action(f"INTERACTION: Clicked [{w_class}] '{text_id}' ({w})", "TRACE")
        except:
            pass

    # Global bind
    root.bind_all("<Button-1>", log_universal_click, add="+")
