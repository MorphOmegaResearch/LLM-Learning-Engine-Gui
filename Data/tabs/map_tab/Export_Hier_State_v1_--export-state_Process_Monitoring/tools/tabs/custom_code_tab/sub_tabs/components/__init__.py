"""Shared UI components for custom code sub tabs."""

try:
    from .fix_dialog import show_fix_dialog
except Exception:  # pragma: no cover - optional during bootstrap
    show_fix_dialog = None  # type: ignore

try:
    from .method_bank_viewer import show_method_bank
except Exception:  # pragma: no cover - optional during bootstrap
    show_method_bank = None  # type: ignore

__all__ = [
    "show_fix_dialog",
    "show_method_bank",
]
