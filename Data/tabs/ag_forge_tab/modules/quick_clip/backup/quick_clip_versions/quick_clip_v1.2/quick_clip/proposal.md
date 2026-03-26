# Future Development Proposal (v3)

This document outlines proposed features based on user feedback, organized into distinct tasks.

## Task 1: Directory and File Handling UX

- **Goal:** Improve the user experience related to file and directory navigation.
- **Proposals:**
    1.  **Default Home Directory:** The "Load from File" dialog should open in the user's home directory by default for easier navigation.
        -   *Implementation Notes:* Modify the `load_input` method in `clip.py`. Use `os.path.expanduser('~')` as the `initialdir` for the `filedialog.askopenfilename` call.
    2.  **Default to Clipboard:** The application will continue to default to using clipboard content on launch, which is the current, desired behavior. No changes are needed for this point.

## Task 2: Advanced Agents & Tooling

- **Goal:** Evolve the "Agents" feature into a powerful, configurable tool-using system, allowing the LLM to reason about and execute commands.
- **Proposals:**
    1.  **Working Directory Configuration:** Add a setting in the UI (likely per-agent or globally in Settings) to define a "working directory" for tools to operate in.
    2.  **Tool Schema:** An "Agent" will be defined by a "Tool Schema" in a JSON or YAML file. This schema will describe a command that can be executed.
    3.  **System Prompt Injection:** The schemas of available tools will be formatted and injected into the system prompt sent to the LLM, allowing it to reason about which tool to use and with what arguments.
    4.  **Execution Engine:** A new module will be required to parse the LLM's output, identify a tool call, and safely execute it using `subprocess`, returning the output to the LLM for the next step.
    5.  **`edit` Tool:** A special built-in tool that, when called by the LLM with a file path, will load that file's content directly into the 'Edit & Process' tab for review and modification.

## Task 3: Settings Tab Enhancements

- **Goal:** Provide more granular and user-friendly controls in the Settings tab.
- **Proposals:**
    1.  **Resolution Settings:** Add a dedicated section for window size with a dropdown of common resolutions (e.g., "850x650", "1024x768", "1280x720") and/or fields for custom width/height.
    2.  **Resource Allocation Controls:** Enhance the GPU settings with more explicit controls for resource distribution.
        -   **GPU Control Presets:** Add `[Max]`, `[Medium]`, `[Min]` buttons next to the `num_gpu` entry field to simplify setup. (`Max` offloads all possible layers, `Min` offloads a small number, etc.)
        -   **CPU/GPU Dedication:** Clarify the settings to indicate the trade-offs (e.g., high GPU usage may free up CPU resources for other tasks).
    3.  **Gemini API Integration:**
        -   Add "Google Gemini" as a provider option.
        -   When selected, show an "API Key" entry field.
        -   *Note:* Per user feedback, standard API key authentication is the initial goal. Investigating the use of local `gcloud` CLI authentication is a potential future enhancement but is complex and may be out of scope.

## Task 4: Integration of External Suites

- **Goal:** Integrate the user-provided `planner_suite.py` and `invoke_doc.py` scripts to transform the application into a more powerful, integrated development assistant.
- **Proposals:**
    1.  **Phase 1: Integrate Planner Suite:** Refactor `planner_suite.py` and embed its entire GUI as a new, fully functional "Planner" tab within the main application.
    2.  **Phase 2: Bridge Planner and Editor:** Create a workflow to send context between tabs. A "Send to Editor" button in the Planner will concatenate the content of all "marked" files and load it into the "Edit & Process" tab's input box.
    3.  **Phase 3: Implement a "Tools" Tab:** Formalize the concept from `invoke_doc.py`. Create a new "Tools" tab where external scripts can be configured as tools (via a `tools.json` schema) and executed from within the UI.
