# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Training Tab Module
Handles training configuration, execution, and dataset management
Modular design with separated panel components
"""

from .training_tab import TrainingTab
from .runner_panel import RunnerPanel
from .category_manager_panel import CategoryManagerPanel
from .dataset_panel import DatasetPanel
from .config_panel import ConfigPanel
from .profiles_panel import ProfilesPanel
from .summary_panel import SummaryPanel

__all__ = [
    'TrainingTab',
    'RunnerPanel',
    'CategoryManagerPanel',
    'DatasetPanel',
    'ConfigPanel',
    'ProfilesPanel',
    'SummaryPanel'
]
