#!/usr/bin/env python3
"""
Interactive UI Library for Terminal Applications
Provides keyboard-navigable menus, buttons, and selectable options
"""

import sys
import tty
import termios
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass

@dataclass
class MenuItem:
    """Represents a selectable menu item"""
    key: str  # Keyboard shortcut (e.g., '1', 'a', 'enter')
    label: str  # Display text
    description: str = ""  # Optional description
    icon: str = "▶"  # Icon to show when selected
    action: Optional[Callable] = None  # Function to call when selected
    value: Any = None  # Return value if selected

class InteractiveUI:
    """Interactive terminal UI with keyboard navigation"""

    # Colors and styles
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    # Icons
    ICON_CHECK = "✓"
    ICON_CROSS = "✗"
    ICON_ARROW = "→"
    ICON_BULLET = "•"
    ICON_STAR = "★"
    ICON_WARNING = "⚠"
    ICON_INFO = "ℹ"
    ICON_QUESTION = "?"
    ICON_GEAR = "⚙"
    ICON_ROCKET = "🚀"
    ICON_FOLDER = "📁"
    ICON_FILE = "📄"
    ICON_DISK = "💾"
    ICON_COMPUTER = "🖥"
    ICON_GPU = "🎮"

    @staticmethod
    def clear_screen():
        """Clear the terminal screen"""
        print("\033[2J\033[H", end="")

    @staticmethod
    def move_cursor(row: int, col: int):
        """Move cursor to specific position"""
        print(f"\033[{row};{col}H", end="")

    @staticmethod
    def hide_cursor():
        """Hide the cursor"""
        print("\033[?25l", end="")

    @staticmethod
    def show_cursor():
        """Show the cursor"""
        print("\033[?25h", end="")

    @staticmethod
    def get_key() -> str:
        """Get single keypress from user"""
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)

            # Handle arrow keys (multi-byte sequences)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        return 'up'
                    elif ch3 == 'B':
                        return 'down'
                    elif ch3 == 'C':
                        return 'right'
                    elif ch3 == 'D':
                        return 'left'
                return 'esc'

            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    @classmethod
    def header(cls, text: str, width: int = 60):
        """Print a styled header"""
        print(f"\n{cls.BOLD}{cls.CYAN}{'=' * width}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{text.center(width)}{cls.RESET}")
        print(f"{cls.BOLD}{cls.CYAN}{'=' * width}{cls.RESET}\n")

    @classmethod
    def section(cls, text: str):
        """Print a section header"""
        print(f"\n{cls.BOLD}{cls.YELLOW}{text}{cls.RESET}")

    @classmethod
    def info(cls, text: str, icon: str = None):
        """Print info message"""
        icon = icon or cls.ICON_INFO
        print(f"{cls.CYAN}{icon}  {text}{cls.RESET}")

    @classmethod
    def success(cls, text: str):
        """Print success message"""
        print(f"{cls.GREEN}{cls.ICON_CHECK}  {text}{cls.RESET}")

    @classmethod
    def error(cls, text: str):
        """Print error message"""
        print(f"{cls.RED}{cls.ICON_CROSS}  {text}{cls.RESET}")

    @classmethod
    def warning(cls, text: str):
        """Print warning message"""
        print(f"{cls.YELLOW}{cls.ICON_WARNING}  {text}{cls.RESET}")

    @classmethod
    def menu(cls, title: str, items: List[MenuItem], selected_index: int = 0) -> Optional[MenuItem]:
        """
        Display interactive menu with keyboard navigation

        Args:
            title: Menu title
            items: List of MenuItem objects
            selected_index: Initially selected item index

        Returns:
            Selected MenuItem or None if cancelled
        """
        current = selected_index

        while True:
            cls.clear_screen()
            cls.header(title)

            # Display menu items
            for i, item in enumerate(items):
                if i == current:
                    # Highlighted item
                    print(f"  {cls.BG_CYAN}{cls.BLACK} {item.icon} {item.key.upper()} {cls.RESET} "
                          f"{cls.BOLD}{item.label}{cls.RESET}")
                    if item.description:
                        print(f"      {cls.DIM}{item.description}{cls.RESET}")
                else:
                    # Normal item
                    print(f"  {cls.DIM}{item.icon}{cls.RESET} {cls.DIM}[{item.key}]{cls.RESET} {item.label}")
                    if item.description:
                        print(f"      {cls.DIM}{item.description}{cls.RESET}")
                print()

            # Instructions
            print(f"\n{cls.DIM}Use {cls.BOLD}↑↓{cls.RESET}{cls.DIM} or "
                  f"{cls.BOLD}number keys{cls.RESET}{cls.DIM} to select, "
                  f"{cls.BOLD}Enter{cls.RESET}{cls.DIM} to confirm, "
                  f"{cls.BOLD}ESC{cls.RESET}{cls.DIM} to cancel{cls.RESET}")

            # Get input
            key = cls.get_key()

            if key == 'up':
                current = (current - 1) % len(items)
            elif key == 'down':
                current = (current + 1) % len(items)
            elif key == '\r' or key == '\n':  # Enter
                selected = items[current]
                if selected.action:
                    selected.action()
                return selected
            elif key == 'esc' or key == '\x1b':
                return None
            elif key in [item.key for item in items]:
                # Direct key selection
                for i, item in enumerate(items):
                    if item.key == key:
                        if item.action:
                            item.action()
                        return item

    @classmethod
    def confirm(cls, message: str, default: bool = False) -> bool:
        """
        Ask yes/no confirmation with keyboard selection

        Args:
            message: Question to ask
            default: Default choice (True=yes, False=no)

        Returns:
            True for yes, False for no
        """
        current = 0 if default else 1

        while True:
            cls.clear_screen()
            print(f"\n{cls.BOLD}{cls.YELLOW}{cls.ICON_QUESTION}  {message}{cls.RESET}\n")

            # Yes button
            if current == 0:
                print(f"  {cls.BG_GREEN}{cls.BLACK} {cls.ICON_CHECK} YES {cls.RESET}")
            else:
                print(f"  {cls.DIM}[y]{cls.RESET} Yes")

            print()

            # No button
            if current == 1:
                print(f"  {cls.BG_RED}{cls.BLACK} {cls.ICON_CROSS} NO {cls.RESET}")
            else:
                print(f"  {cls.DIM}[n]{cls.RESET} No")

            print(f"\n{cls.DIM}Use {cls.BOLD}↑↓{cls.RESET}{cls.DIM} or "
                  f"{cls.BOLD}Y/N{cls.RESET}{cls.DIM} keys, "
                  f"{cls.BOLD}Enter{cls.RESET}{cls.DIM} to confirm{cls.RESET}")

            key = cls.get_key()

            if key == 'up' or key == 'down':
                current = 1 - current
            elif key == '\r' or key == '\n':
                return current == 0
            elif key.lower() == 'y':
                return True
            elif key.lower() == 'n':
                return False

    @classmethod
    def select_number(cls, message: str, min_val: float, max_val: float,
                     default: float, step: float = 1.0) -> float:
        """
        Interactive number input with +/- buttons

        Args:
            message: Prompt message
            min_val: Minimum value
            max_val: Maximum value
            default: Default value
            step: Increment/decrement step

        Returns:
            Selected number
        """
        current = default

        while True:
            cls.clear_screen()
            print(f"\n{cls.BOLD}{cls.CYAN}{message}{cls.RESET}\n")

            # Display current value
            print(f"  {cls.BOLD}{cls.GREEN}{current}{cls.RESET}")
            print()

            # Controls
            print(f"  {cls.DIM}[↑]{cls.RESET} Increase (+{step})")
            print(f"  {cls.DIM}[↓]{cls.RESET} Decrease (-{step})")
            print(f"  {cls.DIM}[←]{cls.RESET} Larger step (×10)")
            print(f"  {cls.DIM}[→]{cls.RESET} Smaller step (÷10)")
            print()
            print(f"  Range: {min_val} - {max_val}")

            print(f"\n{cls.DIM}Press {cls.BOLD}Enter{cls.RESET}{cls.DIM} to confirm, "
                  f"{cls.BOLD}R{cls.RESET}{cls.DIM} to reset to default{cls.RESET}")

            key = cls.get_key()

            if key == 'up':
                current = min(current + step, max_val)
            elif key == 'down':
                current = max(current - step, min_val)
            elif key == 'left':
                step = step * 10
            elif key == 'right':
                step = max(step / 10, 0.01)
            elif key == '\r' or key == '\n':
                return current
            elif key.lower() == 'r':
                current = default

    @classmethod
    def progress_bar(cls, current: int, total: int, width: int = 40,
                     label: str = "", color: str = None):
        """
        Display a progress bar

        Args:
            current: Current progress
            total: Total items
            width: Bar width in characters
            label: Optional label
            color: Color code (default: GREEN)
        """
        color = color or cls.GREEN
        percent = (current / total) * 100
        filled = int((current / total) * width)
        bar = "█" * filled + "░" * (width - filled)

        print(f"\r{label} {color}[{bar}]{cls.RESET} {percent:.1f}% ({current}/{total})", end="")

        if current >= total:
            print()  # New line when complete


# Example usage and testing
if __name__ == "__main__":
    ui = InteractiveUI()

    # Test header
    ui.header("Interactive UI Test")

    # Test messages
    ui.info("This is an info message", ui.ICON_INFO)
    ui.success("This is a success message")
    ui.warning("This is a warning message")
    ui.error("This is an error message")

    input("\nPress Enter to test menu...")

    # Test menu
    items = [
        MenuItem(key="1", label="Option 1", description="First option", icon=ui.ICON_STAR),
        MenuItem(key="2", label="Option 2", description="Second option", icon=ui.ICON_GEAR),
        MenuItem(key="3", label="Option 3", description="Third option", icon=ui.ICON_ROCKET),
        MenuItem(key="q", label="Quit", description="Exit menu", icon=ui.ICON_CROSS),
    ]

    result = ui.menu("Test Menu", items)

    if result:
        ui.clear_screen()
        ui.success(f"You selected: {result.label}")
    else:
        ui.info("Menu cancelled")

    input("\nPress Enter to test confirm...")

    # Test confirm
    if ui.confirm("Do you want to continue?", default=True):
        ui.success("Confirmed!")
    else:
        ui.info("Cancelled")

    input("\nPress Enter to test number selection...")

    # Test number selector
    value = ui.select_number("Select a number:", 0, 100, 10, step=5)
    ui.clear_screen()
    ui.success(f"Selected: {value}")

    input("\nPress Enter to test progress bar...")

    # Test progress bar
    ui.clear_screen()
    ui.header("Progress Test")
    import time
    for i in range(101):
        ui.progress_bar(i, 100, label="Loading")
        time.sleep(0.02)

    ui.success("All tests complete!")
