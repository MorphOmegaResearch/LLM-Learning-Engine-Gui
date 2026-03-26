"""
OpenCode-Compatible Browser Tools (Phase 1.6B)
================================================
Browser automation tools that inherit from BaseTool for opencode integration.

Created: 2025-10-30
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Add opencode to path
sys.path.insert(0, str(Path(__file__).parent / "site-packages"))

from opencode.tools import BaseTool, ToolResult
from opencode.config import ToolsConfig
from browser_tools import BrowserTools


class BrowserScreenshotTool(BaseTool):
    """Take screenshots of screen or regions"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, filename: Optional[str] = None,
                     region: Optional[Tuple[int, int, int, int]] = None,
                     **kwargs) -> ToolResult:
        """
        Execute screenshot capture.

        Args:
            filename: Optional filename for screenshot
            region: Optional (x, y, width, height) for partial screenshot

        Returns:
            ToolResult with screenshot path
        """
        try:
            filepath = self.browser_tools.screenshot(filename=filename, region=region)
            return ToolResult(
                success=True,
                output=f"Screenshot saved to: {filepath}",
                data={"filepath": filepath}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Screenshot failed: {str(e)}"
            )


class BrowserClickTool(BaseTool):
    """Click at screen coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, x: Optional[int] = None, y: Optional[int] = None,
                     button: str = 'left', clicks: int = 1, **kwargs) -> ToolResult:
        """
        Execute mouse click.

        Args:
            x: X coordinate (None for current position)
            y: Y coordinate (None for current position)
            button: 'left', 'right', or 'middle'
            clicks: Number of clicks

        Returns:
            ToolResult with click status
        """
        try:
            result = self.browser_tools.click(x, y, button, clicks)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Clicked {button} button {clicks} time(s) at {result['position']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Click failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Click failed: {str(e)}"
            )


class BrowserDoubleClickTool(BaseTool):
    """Double-click at screen coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, x: Optional[int] = None, y: Optional[int] = None,
                     **kwargs) -> ToolResult:
        """Execute double-click."""
        try:
            result = self.browser_tools.double_click(x, y)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Double-clicked at {result['position']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Double-click failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Double-click failed: {str(e)}"
            )


class BrowserRightClickTool(BaseTool):
    """Right-click at screen coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, x: Optional[int] = None, y: Optional[int] = None,
                     **kwargs) -> ToolResult:
        """Execute right-click."""
        try:
            result = self.browser_tools.right_click(x, y)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Right-clicked at {result['position']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Right-click failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Right-click failed: {str(e)}"
            )


class BrowserDragTool(BaseTool):
    """Drag from start to end coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, start_x: int, start_y: int, end_x: int, end_y: int,
                     duration: float = 0.5, button: str = 'left', **kwargs) -> ToolResult:
        """Execute drag operation."""
        try:
            result = self.browser_tools.drag(start_x, start_y, end_x, end_y, duration, button)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Dragged from {result['start']} to {result['end']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Drag failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Drag failed: {str(e)}"
            )


class BrowserTypeTextTool(BaseTool):
    """Type text at cursor position"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, text: str, interval: float = 0.05, **kwargs) -> ToolResult:
        """Execute text typing."""
        try:
            result = self.browser_tools.type_text(text, interval)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Typed {result['length']} characters",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Type text failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Type text failed: {str(e)}"
            )


class BrowserPressKeyTool(BaseTool):
    """Press keyboard key(s)"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, key: str, presses: int = 1, **kwargs) -> ToolResult:
        """Execute key press."""
        try:
            result = self.browser_tools.press_key(key, presses)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Pressed '{result['key']}' {result['presses']} time(s)",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Key press failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Key press failed: {str(e)}"
            )


class BrowserPressHotkeyTool(BaseTool):
    """Press hotkey combination (Ctrl+C, etc.)"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, keys: str, **kwargs) -> ToolResult:
        """
        Execute hotkey combination.

        Args:
            keys: Comma-separated keys (e.g., "ctrl,c" or "alt,tab")
        """
        try:
            key_list = [k.strip() for k in keys.split(',')]
            result = self.browser_tools.press_hotkey(*key_list)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Pressed hotkey: {result['hotkey']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Hotkey press failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Hotkey press failed: {str(e)}"
            )


class BrowserScrollTool(BaseTool):
    """Scroll mouse wheel"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, clicks: int, x: Optional[int] = None,
                     y: Optional[int] = None, **kwargs) -> ToolResult:
        """
        Execute scroll.

        Args:
            clicks: Positive for up, negative for down
            x: X coordinate to scroll at
            y: Y coordinate to scroll at
        """
        try:
            result = self.browser_tools.scroll(clicks, x, y)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Scrolled {result['direction']} {abs(clicks)} clicks at {result['position']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Scroll failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Scroll failed: {str(e)}"
            )


class BrowserMoveMouseTool(BaseTool):
    """Move mouse to coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, x: int, y: int, duration: float = 0.5, **kwargs) -> ToolResult:
        """Execute mouse move."""
        try:
            result = self.browser_tools.move_to(x, y, duration)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Moved mouse to {result['position']}",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Mouse move failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Mouse move failed: {str(e)}"
            )


class BrowserWaitTool(BaseTool):
    """Wait for specified duration"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, seconds: float, **kwargs) -> ToolResult:
        """Execute wait."""
        try:
            result = self.browser_tools.wait(seconds)
            if result["success"]:
                return ToolResult(
                    success=True,
                    output=f"Waited for {result['duration']} seconds",
                    data=result
                )
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=result.get("error", "Wait failed")
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Wait failed: {str(e)}"
            )


class BrowserLocateImageTool(BaseTool):
    """Locate image on screen"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, image_path: str, confidence: float = 0.9, **kwargs) -> ToolResult:
        """Execute image location."""
        try:
            location = self.browser_tools.locate_on_screen(image_path, confidence)
            if location:
                return ToolResult(
                    success=True,
                    output=f"Found image at {location}",
                    data={"location": location}
                )
            else:
                return ToolResult(
                    success=False,
                    output="Image not found on screen",
                    error="Image not found"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Image locate failed: {str(e)}"
            )


class BrowserGetMousePositionTool(BaseTool):
    """Get current mouse position"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, **kwargs) -> ToolResult:
        """Get mouse position."""
        try:
            position = self.browser_tools.get_mouse_position()
            return ToolResult(
                success=True,
                output=f"Mouse position: {position}",
                data={"position": position}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Get mouse position failed: {str(e)}"
            )


class BrowserGetPixelColorTool(BaseTool):
    """Get RGB color at screen coordinates"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, x: int, y: int, **kwargs) -> ToolResult:
        """Get pixel color."""
        try:
            color = self.browser_tools.get_pixel_color(x, y)
            return ToolResult(
                success=True,
                output=f"Pixel color at ({x}, {y}): RGB{color}",
                data={"color": color, "rgb": color}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Get pixel color failed: {str(e)}"
            )


class BrowserAlertTool(BaseTool):
    """Show alert dialog"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, text: str, title: str = "Alert", button: str = "OK",
                     **kwargs) -> ToolResult:
        """Show alert dialog."""
        try:
            result = self.browser_tools.alert(text, title, button)
            return ToolResult(
                success=True,
                output=f"Alert shown: {result}",
                data={"result": result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Alert failed: {str(e)}"
            )


class BrowserConfirmTool(BaseTool):
    """Show confirmation dialog"""

    def __init__(self, config: ToolsConfig):
        super().__init__(config)
        self.browser_tools = BrowserTools()

    async def execute(self, text: str, title: str = "Confirm",
                     buttons: Optional[list] = None, **kwargs) -> ToolResult:
        """Show confirmation dialog."""
        try:
            result = self.browser_tools.confirm(text, title, buttons)
            return ToolResult(
                success=True,
                output=f"User selected: {result}",
                data={"selection": result}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Confirm dialog failed: {str(e)}"
            )


# Export all browser tool classes
__all__ = [
    'BrowserScreenshotTool',
    'BrowserClickTool',
    'BrowserDoubleClickTool',
    'BrowserRightClickTool',
    'BrowserDragTool',
    'BrowserTypeTextTool',
    'BrowserPressKeyTool',
    'BrowserPressHotkeyTool',
    'BrowserScrollTool',
    'BrowserMoveMouseTool',
    'BrowserWaitTool',
    'BrowserLocateImageTool',
    'BrowserGetMousePositionTool',
    'BrowserGetPixelColorTool',
    'BrowserAlertTool',
    'BrowserConfirmTool',
]
