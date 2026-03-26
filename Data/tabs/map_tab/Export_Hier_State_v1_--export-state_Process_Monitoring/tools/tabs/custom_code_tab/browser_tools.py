"""
Browser Automation Tools Library (Phase 1.6B)
==============================================
Provides GUI automation capabilities using pyautogui for GUI Tester type
and Browser Agent operations.

Created: 2025-10-30
Author: LLM Learning Engine Team
"""

import pyautogui
import time
import os
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


class BrowserTools:
    """Browser and GUI automation tool collection."""

    def __init__(self, screenshot_dir: Optional[Path] = None):
        """
        Initialize browser tools.

        Args:
            screenshot_dir: Directory to save screenshots (default: Data/screenshots/)
        """
        # Set safety features
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        pyautogui.PAUSE = 0.1  # Small pause between actions

        # Screenshot directory
        if screenshot_dir is None:
            from pathlib import Path
            screenshot_dir = Path(__file__).parent.parent.parent / "screenshots"

        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()

    # ========== Screenshot Tools ==========

    def screenshot(self, filename: Optional[str] = None, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """
        Take a screenshot of the screen or specific region.

        Args:
            filename: Optional filename (auto-generated if None)
            region: Optional (x, y, width, height) tuple for partial screenshot

        Returns:
            Path to saved screenshot file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"

        filepath = self.screenshot_dir / filename

        if region:
            screenshot = pyautogui.screenshot(region=region)
        else:
            screenshot = pyautogui.screenshot()

        screenshot.save(str(filepath))
        return str(filepath)

    # ========== Mouse Movement Tools ==========

    def move_to(self, x: int, y: int, duration: float = 0.5) -> Dict[str, Any]:
        """
        Move mouse to absolute coordinates.

        Args:
            x: X coordinate
            y: Y coordinate
            duration: Time to take for movement (seconds)

        Returns:
            Status dict with success and final position
        """
        try:
            pyautogui.moveTo(x, y, duration=duration)
            final_x, final_y = pyautogui.position()
            return {
                "success": True,
                "position": (final_x, final_y),
                "target": (x, y)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def move_relative(self, x_offset: int, y_offset: int, duration: float = 0.5) -> Dict[str, Any]:
        """
        Move mouse relative to current position.

        Args:
            x_offset: Horizontal offset
            y_offset: Vertical offset
            duration: Time to take for movement (seconds)

        Returns:
            Status dict with success and final position
        """
        try:
            pyautogui.move(x_offset, y_offset, duration=duration)
            final_x, final_y = pyautogui.position()
            return {
                "success": True,
                "position": (final_x, final_y),
                "offset": (x_offset, y_offset)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_mouse_position(self) -> Tuple[int, int]:
        """Get current mouse position."""
        return pyautogui.position()

    # ========== Click Tools ==========

    def click(self, x: Optional[int] = None, y: Optional[int] = None,
              button: str = 'left', clicks: int = 1) -> Dict[str, Any]:
        """
        Click at specified position or current position.

        Args:
            x: X coordinate (None for current position)
            y: Y coordinate (None for current position)
            button: 'left', 'right', or 'middle'
            clicks: Number of clicks (1 for single, 2 for double, etc.)

        Returns:
            Status dict with success and click details
        """
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, clicks=clicks, button=button)
                position = (x, y)
            else:
                pyautogui.click(clicks=clicks, button=button)
                position = pyautogui.position()

            return {
                "success": True,
                "position": position,
                "button": button,
                "clicks": clicks
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Double-click at specified position or current position."""
        return self.click(x, y, button='left', clicks=2)

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Right-click at specified position or current position."""
        return self.click(x, y, button='right', clicks=1)

    def middle_click(self, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """Middle-click at specified position or current position."""
        return self.click(x, y, button='middle', clicks=1)

    # ========== Drag Tools ==========

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
             duration: float = 0.5, button: str = 'left') -> Dict[str, Any]:
        """
        Drag from start position to end position.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            duration: Time to take for drag (seconds)
            button: Mouse button to use ('left', 'right', 'middle')

        Returns:
            Status dict with success and drag details
        """
        try:
            # Move to start position
            pyautogui.moveTo(start_x, start_y)
            time.sleep(0.1)

            # Perform drag
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)

            final_x, final_y = pyautogui.position()
            return {
                "success": True,
                "start": (start_x, start_y),
                "end": (end_x, end_y),
                "final_position": (final_x, final_y),
                "button": button
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # ========== Keyboard Tools ==========

    def type_text(self, text: str, interval: float = 0.05) -> Dict[str, Any]:
        """
        Type text at current cursor position.

        Args:
            text: Text to type
            interval: Delay between keystrokes (seconds)

        Returns:
            Status dict with success and typed text
        """
        try:
            pyautogui.write(text, interval=interval)
            return {
                "success": True,
                "text": text,
                "length": len(text)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def press_key(self, key: str, presses: int = 1) -> Dict[str, Any]:
        """
        Press a keyboard key.

        Args:
            key: Key name (e.g., 'enter', 'tab', 'esc', 'a', etc.)
            presses: Number of times to press

        Returns:
            Status dict with success and key details
        """
        try:
            pyautogui.press(key, presses=presses)
            return {
                "success": True,
                "key": key,
                "presses": presses
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def press_hotkey(self, *keys: str) -> Dict[str, Any]:
        """
        Press a combination of keys (hotkey).

        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')

        Returns:
            Status dict with success and hotkey details
        """
        try:
            pyautogui.hotkey(*keys)
            return {
                "success": True,
                "hotkey": '+'.join(keys)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def key_down(self, key: str) -> Dict[str, Any]:
        """Hold a key down (must be released with key_up)."""
        try:
            pyautogui.keyDown(key)
            return {"success": True, "key": key, "action": "down"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def key_up(self, key: str) -> Dict[str, Any]:
        """Release a held key."""
        try:
            pyautogui.keyUp(key)
            return {"success": True, "key": key, "action": "up"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========== Scroll Tools ==========

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """
        Scroll the mouse wheel.

        Args:
            clicks: Positive for up, negative for down
            x: X coordinate to scroll at (None for current position)
            y: Y coordinate to scroll at (None for current position)

        Returns:
            Status dict with success and scroll details
        """
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
                position = (x, y)
            else:
                position = pyautogui.position()

            pyautogui.scroll(clicks)

            return {
                "success": True,
                "clicks": clicks,
                "direction": "up" if clicks > 0 else "down",
                "position": position
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def scroll_horizontal(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
        """
        Scroll horizontally (may not work on all systems).

        Args:
            clicks: Positive for right, negative for left
            x: X coordinate to scroll at
            y: Y coordinate to scroll at
        """
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
                position = (x, y)
            else:
                position = pyautogui.position()

            pyautogui.hscroll(clicks)

            return {
                "success": True,
                "clicks": clicks,
                "direction": "right" if clicks > 0 else "left",
                "position": position
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # ========== Utility Tools ==========

    def wait(self, seconds: float) -> Dict[str, Any]:
        """
        Wait for specified duration.

        Args:
            seconds: Duration to wait

        Returns:
            Status dict with success and duration
        """
        try:
            time.sleep(seconds)
            return {
                "success": True,
                "duration": seconds
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def locate_on_screen(self, image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int, int, int]]:
        """
        Locate an image on screen.

        Args:
            image_path: Path to image file to find
            confidence: Match confidence (0.0 to 1.0)

        Returns:
            (left, top, width, height) tuple if found, None otherwise
        """
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            return location
        except Exception:
            return None

    def locate_center(self, image_path: str, confidence: float = 0.9) -> Optional[Tuple[int, int]]:
        """
        Locate the center of an image on screen.

        Args:
            image_path: Path to image file to find
            confidence: Match confidence (0.0 to 1.0)

        Returns:
            (x, y) center coordinates if found, None otherwise
        """
        try:
            center = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
            return center
        except Exception:
            return None

    def get_pixel_color(self, x: int, y: int) -> Tuple[int, int, int]:
        """
        Get RGB color of pixel at coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            (R, G, B) tuple
        """
        return pyautogui.pixel(x, y)

    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution."""
        return (self.screen_width, self.screen_height)

    def is_on_screen(self, x: int, y: int) -> bool:
        """Check if coordinates are within screen bounds."""
        return pyautogui.onScreen(x, y)

    # ========== Alert/Dialog Tools ==========

    def alert(self, text: str, title: str = "Alert", button: str = "OK") -> str:
        """Show an alert dialog."""
        return pyautogui.alert(text=text, title=title, button=button)

    def confirm(self, text: str, title: str = "Confirm", buttons: List[str] = None) -> str:
        """
        Show a confirmation dialog.

        Returns:
            Button text that was clicked
        """
        if buttons is None:
            buttons = ["OK", "Cancel"]
        return pyautogui.confirm(text=text, title=title, buttons=buttons)

    def prompt(self, text: str, title: str = "Input", default: str = "") -> Optional[str]:
        """
        Show an input prompt dialog.

        Returns:
            User input string or None if cancelled
        """
        return pyautogui.prompt(text=text, title=title, default=default)

    def password(self, text: str, title: str = "Password", default: str = "", mask: str = "*") -> Optional[str]:
        """
        Show a password input dialog.

        Returns:
            Password string or None if cancelled
        """
        return pyautogui.password(text=text, title=title, default=default, mask=mask)

    # ========== Safety Tools ==========

    def set_failsafe(self, enabled: bool = True):
        """Enable/disable failsafe (move mouse to corner to abort)."""
        pyautogui.FAILSAFE = enabled

    def set_pause(self, seconds: float):
        """Set pause duration between pyautogui actions."""
        pyautogui.PAUSE = seconds

    def get_info(self) -> Dict[str, Any]:
        """Get information about current automation state."""
        return {
            "screen_size": self.get_screen_size(),
            "mouse_position": self.get_mouse_position(),
            "failsafe_enabled": pyautogui.FAILSAFE,
            "pause_duration": pyautogui.PAUSE,
            "screenshot_dir": str(self.screenshot_dir)
        }


# ========== Convenience Functions ==========

def create_browser_tools(screenshot_dir: Optional[Path] = None) -> BrowserTools:
    """
    Create and return a BrowserTools instance.

    Args:
        screenshot_dir: Optional screenshot directory

    Returns:
        Configured BrowserTools instance
    """
    return BrowserTools(screenshot_dir=screenshot_dir)


# ========== Tool Registry Metadata ==========

BROWSER_TOOL_REGISTRY = {
    "screenshot": {
        "name": "Screenshot",
        "category": "browser_basic",
        "description": "Capture screen or region as image",
        "parameters": ["filename", "region"],
        "required_level": "novice"
    },
    "click": {
        "name": "Click",
        "category": "browser_interaction",
        "description": "Click at coordinates with specified button",
        "parameters": ["x", "y", "button", "clicks"],
        "required_level": "novice"
    },
    "double_click": {
        "name": "Double Click",
        "category": "browser_interaction",
        "description": "Double-click at coordinates",
        "parameters": ["x", "y"],
        "required_level": "novice"
    },
    "right_click": {
        "name": "Right Click",
        "category": "browser_interaction",
        "description": "Right-click at coordinates",
        "parameters": ["x", "y"],
        "required_level": "skilled"
    },
    "drag": {
        "name": "Drag",
        "category": "browser_interaction",
        "description": "Drag from start to end coordinates",
        "parameters": ["start_x", "start_y", "end_x", "end_y", "duration", "button"],
        "required_level": "adept"
    },
    "type_text": {
        "name": "Type Text",
        "category": "browser_interaction",
        "description": "Type text at cursor position",
        "parameters": ["text", "interval"],
        "required_level": "novice"
    },
    "press_key": {
        "name": "Press Key",
        "category": "browser_interaction",
        "description": "Press keyboard key(s)",
        "parameters": ["key", "presses"],
        "required_level": "novice"
    },
    "press_hotkey": {
        "name": "Press Hotkey",
        "category": "browser_interaction",
        "description": "Press key combination (Ctrl+C, etc.)",
        "parameters": ["keys"],
        "required_level": "skilled"
    },
    "scroll": {
        "name": "Scroll",
        "category": "browser_interaction",
        "description": "Scroll mouse wheel at position",
        "parameters": ["clicks", "x", "y"],
        "required_level": "skilled"
    },
    "move_to": {
        "name": "Move Mouse",
        "category": "browser_interaction",
        "description": "Move mouse to absolute coordinates",
        "parameters": ["x", "y", "duration"],
        "required_level": "novice"
    },
    "wait": {
        "name": "Wait",
        "category": "system",
        "description": "Wait for specified duration",
        "parameters": ["seconds"],
        "required_level": "novice"
    },
    "locate_on_screen": {
        "name": "Locate Image",
        "category": "browser_advanced",
        "description": "Find image on screen",
        "parameters": ["image_path", "confidence"],
        "required_level": "expert"
    },
    "get_mouse_position": {
        "name": "Get Mouse Position",
        "category": "system",
        "description": "Get current mouse coordinates",
        "parameters": [],
        "required_level": "novice"
    },
    "get_pixel_color": {
        "name": "Get Pixel Color",
        "category": "browser_advanced",
        "description": "Get RGB color at coordinates",
        "parameters": ["x", "y"],
        "required_level": "expert"
    },
    "alert": {
        "name": "Show Alert",
        "category": "browser_interaction",
        "description": "Display alert dialog",
        "parameters": ["text", "title", "button"],
        "required_level": "skilled"
    },
    "confirm": {
        "name": "Show Confirmation",
        "category": "browser_interaction",
        "description": "Display confirmation dialog",
        "parameters": ["text", "title", "buttons"],
        "required_level": "skilled"
    }
}


if __name__ == "__main__":
    # Quick test
    tools = create_browser_tools()
    print("BrowserTools initialized successfully!")
    print(f"Screen size: {tools.get_screen_size()}")
    print(f"Mouse position: {tools.get_mouse_position()}")
    print(f"Info: {tools.get_info()}")
