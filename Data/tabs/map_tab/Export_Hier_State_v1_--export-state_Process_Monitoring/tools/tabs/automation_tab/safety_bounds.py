"""
Safety Bounds System for GUI Automation

Prevents AI from clicking dangerous areas or performing unsafe actions.
Integrated with trust levels and task context.
"""

from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import re


class DangerLevel(Enum):
    """Danger level for UI regions"""
    SAFE = 0
    CAUTION = 1
    DANGEROUS = 2
    FORBIDDEN = 3


@dataclass
class Region:
    """A rectangular region on screen"""
    x: int
    y: int
    width: int
    height: int
    danger_level: DangerLevel
    description: str

    def contains(self, x: int, y: int) -> bool:
        """Check if point is within this region"""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)


class SafetyBounds:
    """
    Define safe/unsafe regions for GUI automation

    Trust-based enforcement:
    - Trust 1-2: Only allow SAFE regions
    - Trust 3: Allow SAFE + CAUTION (with warning)
    - Trust 4-5: Allow all except FORBIDDEN
    """

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.dangerous_regions = self._define_dangerous_regions()

    def _define_dangerous_regions(self) -> List[Region]:
        """Define dangerous screen regions"""
        regions = []

        # Top bar - system controls
        regions.append(Region(
            x=0, y=0, width=self.screen_width, height=30,
            danger_level=DangerLevel.DANGEROUS,
            description="Top system bar (power, settings, close buttons)"
        ))

        # Top-left corner - Activities/App menu
        regions.append(Region(
            x=0, y=0, width=100, height=100,
            danger_level=DangerLevel.DANGEROUS,
            description="Activities/App launcher corner"
        ))

        # Top-right corner - System menu
        regions.append(Region(
            x=self.screen_width - 150, y=0, width=150, height=80,
            danger_level=DangerLevel.DANGEROUS,
            description="System menu corner (power, logout)"
        ))

        # Bottom taskbar (if exists)
        regions.append(Region(
            x=0, y=self.screen_height - 50,
            width=self.screen_width, height=50,
            danger_level=DangerLevel.CAUTION,
            description="Bottom taskbar"
        ))

        # Left edge - may contain dock
        regions.append(Region(
            x=0, y=100, width=80, height=self.screen_height - 200,
            danger_level=DangerLevel.CAUTION,
            description="Left dock/sidebar"
        ))

        # Window close buttons (top-right of windows, approximate)
        # This is contextual and harder to define without window detection
        # We'll handle this via action validation instead

        return regions

    def check_click_safety(
        self,
        x: int,
        y: int,
        trust_level: int,
        task_context: str = ""
    ) -> Tuple[bool, DangerLevel, str]:
        """
        Check if a click is safe

        Args:
            x, y: Click coordinates
            trust_level: 1-5 trust level of the agent
            task_context: Description of current task

        Returns:
            (is_safe, danger_level, reason)
        """
        # Check all regions
        for region in self.dangerous_regions:
            if region.contains(x, y):
                # Determine if this is allowed based on trust
                if region.danger_level == DangerLevel.FORBIDDEN:
                    return (False, region.danger_level,
                           f"Forbidden region: {region.description}")

                if region.danger_level == DangerLevel.DANGEROUS:
                    if trust_level >= 4:
                        return (True, region.danger_level,
                               f"Warning: {region.description}")
                    else:
                        return (False, region.danger_level,
                               f"Dangerous region (trust {trust_level} < 4): {region.description}")

                if region.danger_level == DangerLevel.CAUTION:
                    if trust_level >= 3:
                        return (True, region.danger_level,
                               f"Caution: {region.description}")
                    else:
                        return (False, region.danger_level,
                               f"Caution region (trust {trust_level} < 3): {region.description}")

        # Not in any dangerous region
        return (True, DangerLevel.SAFE, "Safe region")

    def check_action_safety(
        self,
        action: Dict,
        trust_level: int,
        task_context: str = ""
    ) -> Tuple[bool, str]:
        """
        Check if an action is safe

        Args:
            action: Action dict with type, x, y, text, etc.
            trust_level: 1-5 trust level
            task_context: Current task description

        Returns:
            (is_safe, reason)
        """
        action_type = action.get('type')

        # Check click actions
        if action_type == 'click':
            x = action.get('x')
            y = action.get('y')

            if x is None or y is None:
                return (False, "Invalid click coordinates")

            is_safe, danger_level, reason = self.check_click_safety(
                x, y, trust_level, task_context
            )

            if not is_safe:
                return (False, reason)

            if danger_level == DangerLevel.DANGEROUS:
                return (True, f"⚠️ {reason}")

            return (True, "Safe click")

        # Check text input actions
        elif action_type == 'type':
            text = action.get('text', '')

            # Check for dangerous commands
            dangerous_patterns = [
                r'rm\s+-rf',
                r'sudo\s+rm',
                r'dd\s+if=',
                r'mkfs\.',
                r'format\s+',
                r':\(\)\{\s*:\|:&\s*\};:',  # Fork bomb
                r'curl.*\|\s*bash',
                r'wget.*\|\s*sh',
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    if trust_level >= 5:
                        return (True, f"⚠️⚠️ VERY DANGEROUS: Detected '{pattern}' but trust=5")
                    else:
                        return (False, f"Dangerous command detected: '{pattern}'")

            return (True, "Safe text input")

        # Check key press actions
        elif action_type == 'key':
            key = action.get('key', '').lower()

            # Dangerous key combos
            dangerous_keys = [
                'alt+f4',      # Close window
                'ctrl+alt+delete',  # System interrupt
                'ctrl+alt+backspace',  # Kill X server
            ]

            if key in dangerous_keys:
                if trust_level >= 4:
                    return (True, f"⚠️ Dangerous key: {key}")
                else:
                    return (False, f"Dangerous key press: {key}")

            return (True, "Safe key press")

        # Other action types are generally safe
        return (True, f"Action type '{action_type}' allowed")

    def get_safe_alternative(
        self,
        x: int,
        y: int,
        task_context: str = ""
    ) -> Optional[Tuple[int, int, str]]:
        """
        Suggest a safer alternative position if click is unsafe

        Returns:
            (new_x, new_y, reason) or None
        """
        # Check which region the click is in
        for region in self.dangerous_regions:
            if region.contains(x, y):
                # Suggest center of screen as safe alternative
                safe_x = self.screen_width // 2
                safe_y = self.screen_height // 2
                return (safe_x, safe_y,
                       f"Moved from {region.description} to center of screen")

        return None

    def add_custom_region(
        self,
        x: int, y: int, width: int, height: int,
        danger_level: DangerLevel,
        description: str
    ):
        """Add a custom dangerous region (for specific tasks)"""
        self.dangerous_regions.append(Region(
            x=x, y=y, width=width, height=height,
            danger_level=danger_level,
            description=description
        ))

    def get_safety_summary(self, trust_level: int) -> str:
        """Get a summary of safety restrictions"""
        if trust_level <= 2:
            return "🛡️ High Security: Only safe regions allowed"
        elif trust_level == 3:
            return "⚠️ Medium Security: Safe + caution regions allowed"
        elif trust_level == 4:
            return "🔓 Low Security: Most regions allowed, forbidden blocked"
        else:
            return "🚨 Minimal Security: All regions allowed except forbidden"


# Pre-configured safety profiles
SAFETY_PROFILES = {
    'strict': {
        'description': 'Maximum safety - for untrusted models',
        'trust_level': 1,
        'require_confirmation': True,
        'allow_dangerous': False,
    },
    'moderate': {
        'description': 'Balanced safety - for testing',
        'trust_level': 3,
        'require_confirmation': False,
        'allow_dangerous': False,
    },
    'relaxed': {
        'description': 'Minimal restrictions - for trusted models',
        'trust_level': 5,
        'require_confirmation': False,
        'allow_dangerous': True,
    }
}


def get_screen_dimensions() -> Tuple[int, int]:
    """Get actual screen dimensions"""
    try:
        import pyautogui
        width, height = pyautogui.size()
        return width, height
    except Exception:
        # Fallback to common resolution
        return 1920, 1080


# Example usage
if __name__ == "__main__":
    # Test safety bounds
    width, height = get_screen_dimensions()
    safety = SafetyBounds(width, height)

    print(f"Screen: {width}x{height}")
    print()

    # Test different clicks
    test_clicks = [
        (100, 20, 1, "Top bar (trust 1)"),
        (100, 20, 5, "Top bar (trust 5)"),
        (960, 540, 1, "Center screen (trust 1)"),
        (50, 50, 1, "Top-left corner (trust 1)"),
        (width - 50, 20, 3, "Top-right system menu (trust 3)"),
    ]

    for x, y, trust, desc in test_clicks:
        is_safe, danger, reason = safety.check_click_safety(x, y, trust)
        status = "✅" if is_safe else "❌"
        print(f"{status} {desc}: {reason}")

    print()
    print(safety.get_safety_summary(3))
