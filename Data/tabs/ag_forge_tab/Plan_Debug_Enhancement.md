#[PFL:Plan_Ag_Forge_v1]
# Debug Enhancement Plan: Ag Forge Production Standard

**Date:** 2026-01-13
**Objective:** Elevate the Ag Forge suite to production-grade reliability using advanced debugging and monitoring techniques defined in the project guides.

## 1. Static Analysis & Auto-Fixing
*Reference: `rolling_debug.md`*

**Goal:** Integrate the `TkinterAnalyzer` into the development workflow to catch issues early.

### Implementation Strategy
- [ ] **Create Module:** `modules/dev_tools/tkinter_analyzer.py` containing the logic from the guide.
- [ ] **Integration:** Add a `--analyze` flag to `launch_ag_forge.py` that runs this check on the codebase before startup.
- [ ] **CI/CD Hook:** (Future) Run this automatically on commit.

**Key Checks to Enable:**
- `TKI001`: Direct `update()` misuse (causes freezes).
- `TKI002`: Missing `mainloop()` (GUI won't show).
- `BLK001`: Code formatting (Black compliance).

## 2. Runtime Monitoring ("Flight Recorder")
*Reference: `tkinker_debug.md`*

**Goal:** Detect and log application freezes or crashes that don't produce a Python traceback (e.g., X11 failures, C-level segfaults).

### Implementation Strategy
- [ ] **Watchdog Thread:** Add a separate thread in `launch_ag_forge.py` that monitors the child processes.
- [ ] **Heartbeat System:**
    *   Sub-processes write a timestamp to a shared memory file every 5 seconds.
    *   Launcher checks this; if >30s delay, assumes "Freeze" and offers to kill/restart.
- [ ] **Window State Logging:** Periodically log window geometry and state (Normal/Iconified) to help debug "disappearing window" issues.

## 3. "Safe Mode" & Recovery
*Reference: `DISPLAY_debug.md`*

**Goal:** Ensure the user can always get back to a working state.

### Implementation Strategy
- [ ] **Crash Counter:** Launcher tracks consecutive failures.
- [ ] **Safe Mode Trigger:** If >3 crashes on startup:
    *   Reset Window Geometry (clear saved state).
    *   Disable `ai_orchestrator` (run GUI only).
    *   Clear temporary cache/locks.
- [ ] **Environment Snapshot:** On crash, save `env_dump.log` capturing `DISPLAY`, `PYTHONPATH`, and loaded modules.

## 4. User Feedback Loop
- [ ] **Crash Dialog:** If a crash is caught, show a native message box (using `tkinter.messagebox` from the launcher process) asking to upload/save the log.
- [ ] **"Report Bug" Tool:** A simple form in the suite to zip up `logs/` and the current `config.json` (sanitized) for review.

## 5. Execution Roadmap
1.  **Immediate:** Implement `tkinter_analyzer.py` in `modules/dev_tools/`.
2.  **Short-term:** Add "Safe Mode" logic to `launch_ag_forge.py`.
3.  **Medium-term:** Implement the Heartbeat Watchdog.
