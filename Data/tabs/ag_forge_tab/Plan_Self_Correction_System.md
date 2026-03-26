# Plan: Ag Forge Self-Correction & Conformer System

**Date:** 2026-01-13
**Objective:** Evolve the debug ecosystem from passive logging to active interception, self-diagnosis, and automated remediation.

## 1. The "Live Event Tracer" v2 (Immediate Priority)
**Current Issue:** Passive event binding (`root.bind_all`) captures user input but misses the *internal logic* (tracebacks, missing commands, logic failures).
**Upgrade Strategy:** **Introspective Callback Wrapping**.
- **Recursive Walk:** On startup (and periodically), walk the entire Tkinter widget tree.
- **Hooking:** Identify every `Button`, `Menu`, or widget with a `command` attribute.
- **Wrapper:** Replace the original command with a `DebugWrapper`:
    1.  **Pre-Flight:** Log "ACTION START: [Widget Name] -> [Function Name]".
    2.  **Execution:** Run the original function inside a `try...except` block.
    3.  **Failure:** If it crashes, catch the exception, log the full traceback, flash a red border on the widget (visual feedback), and queue a "Bug Task".
    4.  **Success:** Log "ACTION COMPLETE".
- **Dead End Detection:** If a button has no `command` configured, bind a click event that logs "[WARNING] Dead End: Button has no function."

## 2. The "Conformer" System (Self-Check-Listing)
**Goal:** A background process that validates the application state against a "Golden Standard".

### A. Feature Checklist
- **Manifest:** A JSON file defining expected UI elements and states (e.g., "Tab 'Planner' must exist", "Button 'Save' must be enabled when text modified").
- **Validator:** A tool that runs periodically or on-demand to assert these conditions.
- **Report:** "UX Disorganization Report" – Flags crowded frames, inconsistent padding, or non-standard fonts.

### B. Auto-Fix Integration
- **Tools:** Integrate `ruff` (fast linting), `black` (formatting), and `autoflake` (cleanup).
- **Workflow:**
    1.  **Detect:** Debugger catches a crash or Conformer finds a "messy" file.
    2.  **Snapshot:** `stash_script.py` saves the current state of the target file.
    3.  **Propose:** "Button 'Save' crashed. Source: `planner_tab.py`. Action: Run linter?"
    4.  **Execute:** User clicks "Auto-Fix". System runs `ruff --fix`.
    5.  **Verify:** User re-tests. If worse, click "Rollback" to restore snapshot.

## 3. Task Integration (The "Queue")
**Goal:** Turn runtime errors into actionable work units.
- **Hook:** When `DebugWrapper` catches an exception:
    - Extract: Error type, file path, line number, local variables.
    - Create Task: "Fix ValueError in planner_tab.py:205".
    - Context: Attach the traceback and the specific widget ID that triggered it.
    - Priority: High.

## 4. Verification & Testing (User Confirmation)
**What to Expect (Post-Implementation):**
- **Disfunction Test:** You will click a button (e.g., a placeholder "Export" button).
- **Result:** Instead of silence, the terminal (and potentially a toaster popup) will scream: `[DEAD END] Widget .!frame.!button has no command assigned!` or `[CRITICAL] Command failed! Traceback logged.`
- **Organization Test:** The Conformer will report: "Widget density too high in 'Tools' tab. Suggest refactor."

## 5. Execution Steps
1.  **Rewrite `interactive_debug.py`** to implement Callback Wrapping (The "Wrapper").
2.  **Inject** this new debugger into `clip.py` and `meta_learn_agriculture.py`.
3.  **Test** by clicking existing buttons and observing the unified log stream.
