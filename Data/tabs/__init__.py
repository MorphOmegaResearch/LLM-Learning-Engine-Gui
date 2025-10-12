"""
Modular tab system for OpenCode Trainer GUI
Each tab is isolated to prevent cascading failures
"""

from .base_tab import BaseTab
from .training_tab.training_tab import TrainingTab
from .models_tab.models_tab import ModelsTab
from .settings_tab.settings_tab import SettingsTab

__all__ = ['BaseTab', 'TrainingTab', 'ModelsTab', 'SettingsTab']
