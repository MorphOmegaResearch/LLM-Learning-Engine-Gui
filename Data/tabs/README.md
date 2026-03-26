# Modular Tab System

Each tab is isolated in its own folder to prevent cascading failures.

## Structure

```
tabs/
├── base_tab.py              # Base class for all tabs
├── training_tab/            # Training configuration tab
│   ├── __init__.py
│   ├── training_tab.py      # Main tab implementation
│   ├── config.py            # Tab-specific configuration
│   └── utils.py             # Helper functions
├── models_tab/              # Models information tab
│   ├── __init__.py
│   ├── models_tab.py        # Main tab implementation
│   ├── overview_panel.py    # Overview sub-tab
│   ├── raw_info_panel.py    # Raw info sub-tab
│   ├── notes_panel.py       # Notes sub-tab
│   ├── stats_panel.py       # Stats sub-tab
│   └── utils.py             # Helper functions
```

### Benefits

1. **Isolation**: If one tab crashes, others keep working
2. **Maintainability**: Each tab's code is self-contained
3. **Testability**: Tabs can be tested independently
4. **Scalability**: Easy to add new tabs

## Adding a New Tab

1. Create a new folder: `tabs/new_tab/`
2. Add `__init__.py` and main file
3. Inherit from `BaseTab` class
4. Implement `create_ui()` method
5. Import in `tabs/__init__.py`
6. Add to main GUI notebook
