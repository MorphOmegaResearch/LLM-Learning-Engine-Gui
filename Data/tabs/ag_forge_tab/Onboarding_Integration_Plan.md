# Onboarding & Integration Phased Plan

This document outlines the phased approach to integrate the "Trusted Merit" agricultural data, create a unified "Agribusiness" onboarding workflow, and develop the "Chat Dock" daily assistance UI.

---

### Phase 1: Trusted Data Ingestion Framework

**Goal:** Establish a robust system for parsing and filtering the "Trusted Merit" data from the `modules/Imports` directory.

*   **Task 1.1: Create `modules/ag_importer.py`**
    *   **File to Add:** `modules/ag_importer.py`
    *   **Context:** This file will contain all logic for reading, parsing, and filtering the trusted taxonomic data. It will be the central hub for handling `seed_pack` and `backbone` data sources.

*   **Task 1.2: Implement Core Parsing Logic in `ag_importer.py`**
    *   **File to Modify:** `modules/ag_importer.py`
    *   **Context:** Add placeholder functions for parsing YAML (`metadata.yaml`) and TSV (`Distribution.tsv`, `VernacularName.tsv`, etc.). The TSV parsing function must be designed to process files line-by-line to handle large datasets efficiently without loading the entire file into memory.

*   **Task 1.3: Create `modules/ag_onboarding.py`**
    *   **File to Add:** `modules/ag_onboarding.py`
    *   **Context:** This new module will orchestrate the user's onboarding experience, from defining their business focus to triggering the data import.

*   **Task 1.4: Integrate Importer into Onboarding**
    *   **File to Modify:** `modules/ag_onboarding.py`
    *   **Context:** Import `ag_importer.py`. Add a function, e.g., `prompt_for_business_focus()`, that asks the user for their primary agricultural domain (like "Dairy," "Wheat," "Orchards"). This input will be stored and used as the primary filter for the importer.

---

### Phase 2: Connecting Onboarding to the Brain Module

**Goal:** Extend the `brain.py` financial orchestrator to recognize and manage "Agribusiness" projects.

*   **Task 2.1: Extend `brain.py`'s `CLIWorkflow`**
    *   **File to Modify:** `modules/ag_onboarding.py`
    *   **Context:** Define a new class, `AgWorkflow`, that inherits from `CLIWorkflow` (from `brain.py`). This allows us to reuse the core project creation and workflow logic while adding our specialized agricultural steps.
    *   **Target Snippet (Conceptual):**
        ```python
        from modules.brain import CLIWorkflow

        class AgWorkflow(CLIWorkflow):
            def __init__(self, config, ollama):
                super().__init__(config, ollama)
        ```

*   **Task 2.2: Add "Agribusiness" Project Type**
    *   **File to Modify:** `modules/ag_onboarding.py`
    *   **Context:** Override the `guided_project_setup` method within the `AgWorkflow` class. This overridden method will add "Agribusiness" to the list of selectable project types and will call our `prompt_for_business_focus()` function when selected.

*   **Task 2.3: Route to the New Agribusiness Workflow**
    *   **File to Modify:** `modules/brain.py`
    *   **Context:** In the `main()` function or argparse setup, add a new CLI flag like `--onboarding-ag` that, when used, instantiates and runs our new `AgWorkflow` instead of the default `CLIWorkflow`.
    *   **Target String for Change (Conceptual):** Locate `if __name__ == "__main__":` and the `parser = setup_argparse()` section to add the new argument and the conditional logic to call `AgWorkflow().guided_project_setup()`.

---

### Phase 3: Chat Dock Prototyping

**Goal:** Create a functional prototype of the "always-on" desktop assistant GUI.

*   **Task 3.1: Create `modules/chat_dock.py`**
    *   **File to Add:** `modules/chat_dock.py`
    *   **Context:** Create the initial file with a basic Tkinter window, setting a small, terminal-like geometry (e.g., 400x600).

*   **Task 3.2: Add UI Components to Chat Dock**
    *   **File to Modify:** `modules/chat_dock.py`
    *   **Context:** Add the primary UI elements: a scrolled text widget for chat history, a text entry for user input, a "Send" button, and placeholder buttons for "Add Health Record," "Financial Forecast," and "Next Task."

*   **Task 3.3: Make the Chat Dock Launchable**
    *   **File to Modify:** `modules/quick_clip/tools.json`
    *   **Context:** Add a new JSON object to the list that defines a tool named "Open Chat Dock" with the command `python3 ../chat_dock.py`. This will allow `quick_clip` and other tools to launch the dock.

---

### Phase 4: Full Integration and Data Population

**Goal:** Connect all the components and implement the final logic to populate the trusted data into the system.

*   **Task 4.1: Implement Data Population Logic**
    *   **File to Modify:** `modules/ag_importer.py`
    *   **Context:** Implement the function that takes the filtered taxonomic data and maps it to the `Ag_Forge` data structures. This will involve reading the TSV rows, identifying the relevant columns (e.g., `scientificName`, `vernacularName`), and creating `Entity` objects or new `Taxonomy` objects to be saved in the `knowledge_forge_data` directory.

*   **Task 4.2: Connect Chat Dock to Backend Systems**
    *   **File to Modify:** `modules/chat_dock.py`
    *   **Context:** Implement the command logic for the placeholder buttons. The "Next Task" button should query `clip_task.py`'s database. The "Financial Forecast" button should trigger a workflow from `brain.py`. The "Add Health Record" button should open a dialog that saves data for `Ag_Forge`.
