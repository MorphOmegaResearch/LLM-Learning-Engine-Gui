# Integration Points & Data Flow (v7 Architecture)

This document outlines the technical integration points and data flow between the various components of the Quick Clip application, based on the v7 architectural proposal.

## 1. Core Components

- **`clip.py` (Main App):** The main GUI application window and notebook manager.
- **`config.py` (ConfigManager):** Handles reading from and writing to `config.ini`.
- **`cli_handler.py`:** Handles headless execution when CLI arguments are passed.
- **`workflow_engine.py`:** Executes sequential, recipe-driven workflows (the "Epic Workflow").
- **`providers.py`:** Abstracts interactions with AI backends (Ollama, Gemini TUI bridge).
- **`tabs/` Modules:** Each major GUI feature is encapsulated in its own tab module (`planner_tab.py`, `state_manager_tab.py`, etc.).

## 2. Data Flow for the "Epic Workflow" (GUI Version)

This details the communication path when a user initiates a workflow from the GUI.

1.  **User Action:** The user selects a "Workflow Recipe" (e.g., `summarize_and_epic.json`) from the `Combobox` in the **Planner Tab** and clicks the "Run Workflow" button.
    -   **Source:** `tabs.planner_tab.PlannerSuite.run_workflow_button`

2.  **Context Aggregation:** The `PlannerSuite` method gathers the necessary context:
    -   The path to the selected Workflow Recipe JSON.
    -   A list of file paths that are currently "marked" in the Planner's listbox.
    -   The path to the `manifest.json` from the **State Manager** tab (for rolling context).
    -   **Routing:** This information is packaged into an `args` object, mimicking the `argparse` structure.

3.  **Engine Invocation:** The `PlannerSuite` calls the main execution logic.
    -   **Routing:** `self.app.run_cli_workflow(args)` -> A new method to be added to `clip.py`'s `ClipboardAssistant` class that allows GUI components to trigger the CLI logic.

4.  **Headless Execution:** The `run_cli_workflow` method calls `handle_cli_request(args)` from `cli_handler.py`.
    -   **Source:** `clip.py`
    -   **Destination:** `cli_handler.py`

5.  **Workflow Orchestration:** `handle_cli_request` instantiates `WorkflowEngine` from `workflow_engine.py` and calls its `.run()` method.
    -   **Source:** `cli_handler.py`
    -   **Destination:** `workflow_engine.py`

6.  **AI Provider Call:** Inside its loop, the `WorkflowEngine` calls the appropriate provider.
    -   **Routing:** `workflow_engine.py` -> `get_provider(name).execute(prompt, args)` -> `providers.py`.

7.  **Resource Configuration:** The `OllamaProvider` reads resource settings from the global config object.
    -   **Routing:** `providers.py` -> `self.app.config.get('Ollama', 'num_gpu')`. The provider will need access to the app's config object.

8.  **Progress & Logging:** The `WorkflowEngine` needs to report status back to the GUI.
    -   **Integration Point:** The engine will accept a `Queue` object in its constructor. As it completes each step, it will `put()` a status update message (e.g., `{'step': 'summarize', 'status': 'COMPLETED', 'output_path': '...'}`) onto the queue.
    -   The `PlannerTab` will have a corresponding method that periodically checks this queue and updates its "Live Tasks" UI accordingly.

## 3. Key Inter-Tab Communication Points

-   **Planner -> Editor:**
    -   **Trigger:** "Send to Editor" button in `planner_tab.py`.
    -   **Action:** Calls `self.app.edit_text.insert(...)` and `self.app.notebook.select(...)` using the `app_ref` passed to its constructor.

-   **Planner -> State Manager:**
    -   **Trigger:** "Diff Against Stash..." right-click option in the Planner's file tree.
    -   **Action:** The Planner will need a reference to the `StateManagerTab` instance (`self.app.state_tab_instance`). It will call a method like `self.app.state_tab_instance.get_stash_history()` to populate a dropdown of available stashes for the diff operation.

-   **Settings -> All Components:**
    -   **Trigger:** The "Save All Settings" button in `clip.py`.
    -   **Action:** Calls `self.config.save()`. All other components read directly from the `self.config` object upon initialization or when needed, so they will pick up the new settings on the next run. Dynamic updates (without restart) are handled via `StringVar`s for settings like `num_gpu`.

## 4. CLI Integration Points

-   **`clip.py` `main()`:** The entry point. It checks `sys.argv`. If arguments are present, it bypasses all GUI initialization and calls `handle_cli_request(args)`.
-   **`--review` Flag:** If this flag is used, the `cli_handler` will, after its primary action, construct a command to re-launch `clip.py` *without* CLI args, but with a special argument that the GUI *can* parse, e.g., `python clip.py --gui-goto-tab planner --highlight-file /path/to/output.md`. The `ClipboardAssistant.__init__` will be modified to look for these special GUI-only args and perform the initial navigation.
