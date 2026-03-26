# Architectural Proposal v9: The Hybrid Tool Suite

This document outlines the master architecture for the Quick Clip ecosystem, based on a "Hybrid Tool Suite" model.

## Core Principle: Co-ordination and Library-based Integration

Instead of merging all code into one application, this architecture treats `quick_clip`, `clip_task.py`, and other scripts as a suite of co-ordinating tools. `quick_clip` will serve as the primary GUI dashboard, and for advanced functionality, it will use `clip_task.py` as an **optional, importable library**. Communication is achieved through a shared database and strategic CLI calls.

## Phase 1: Refactor `clip_task.py` for Dual Use

- **Goal:** To restructure `clip_task.py` so it can function both as a standalone application and as a Python library that `quick_clip` can import.
- **Action:**
    1.  Separate the core logic of `clip_task.py` (database initialization, data models for `Task` and `OllamaProfile`, Taskwarrior functions) from its `OllamaPlannerGUI` class.
    2.  Ensure this core logic can be safely imported by another Python script without automatically launching the `clip_task` GUI. The `if __name__ == "__main__":` block will be used exclusively for its standalone launch.

## Phase 2: Implement the Optional Database Backend in `quick_clip`

- **Goal:** To upgrade `quick_clip` to use the powerful SQLite backend from `clip_task.py` when available.
- **Action:**
    1.  Create a `backend.py` module within `quick_clip`.
    2.  This module will contain a setting, `USE_DATABASE_BACKEND`, configurable in `config.ini`.
    3.  If `True`, it will `try` to `import` the database models and functions from the `clip_task` library. If the import fails, it will automatically revert to the simple, file-based `config.ini` mode and notify the user.
    4.  All data-handling parts of `quick_clip` (like loading profiles or tasks) will go through this `backend` module.

## Phase 3: GUI Overhaul & The Database-Driven Workflow

- **Goal:** To make the `quick_clip` GUI a true dashboard for the shared database and to implement the "Epic Workflow" using this new architecture.
- **Action:**
    1.  **GUI Overhaul:** When "Database Mode" is active, the "Planner" and "Tools" tabs in `quick_clip` will be replaced by the more advanced `Task Dashboard` and `Profile Management` UIs defined in `clip_task.py`.
    2.  **Database-Driven Workflow:** The "Run Workflow" button in the new Task Dashboard will trigger the following sequence:
        a. A `Task` object is created and saved to the shared SQLite database via the `backend` module.
        b. If enabled, the `backend` also calls the `taskwarrior` functions imported from the `clip_task` library.
        c. The `workflow_engine.py` is invoked as a `subprocess`, but instead of passing large amounts of context, it is only passed the ID of the new task: `python workflow_engine.py --task-id <database_task_id>`.
        d. The `workflow_engine.py` script is modified to be database-aware. It uses the `--task-id` to connect to the shared `planner.db` and retrieve all the context it needs (description, associated files, profile settings, etc.).
        e. The engine runs the full workflow, and upon completion, it **updates the task's status and results directly in the database**.
        f. The `quick_clip` GUI, which is monitoring the database for changes, sees the updated status and refreshes the Task Dashboard automatically.

This hybrid architecture provides the best of both worlds: the robustness of a shared database and the flexibility of a scriptable, CLI-driven workflow engine, all orchestrated from a clean, user-friendly dashboard.
