# Brain Visualization Configuration & Subsystem Overview

This document serves as a developer guide for the Brain Visualization component (`brain_viz_3d.py`) and its host tab (`digital_biosphere_visualizer.py`), outlining the state architecture, initializations, and controls.

## 1. Subsystems

The Brain Visualization relies on the following major components:
- **Host Tab (`digital_biosphere_visualizer.py`)**: Responsible for managing the UI tab, placing the widget, and controlling its lifecycle (loading/unloading) for resource management.
- **The Brain Engine (`brain_viz_3d.py`)**: The primary class `Brain3DVisualization` managing the rendering of the `matplotlib` 3D canvas and executing interaction logic (drag, scroll, automation ticks).

## 2. Resource Management (Init/De-init Lifecycle)

To conserve RAM and GPU resources, the heavy 3D canvas is aggressively managed by the host tab:
- **Initialization (`_brain_map_enable`)**: Invoked automatically when the user selects the "Brain Map" tab. It imports `brain_viz_3d.py` and creates a fresh instance of the canvas. During init, the class reads the `brain_viz.json` user preferences file to restore prior states.
- **De-initialization (`_brain_map_disable`)**: Triggered either explicitly by the user (via the "Unload" button) or automatically when switching away from the Brain Map tab. This destroys the widget, calls `after_cancel` on running animation loops, and cleans up references.
  - *Note on State safety*: We previously had a bug where destroying the view explicitly disabled auto-rotate (`set(False)`), accidentally overwriting user preferences. De-initialization now *only* cancels timers without modifying tracked Tkinter variables.

## 3. Configuration & State Management

State is managed by tracked Tkinter variables (e.g., `BooleanVar`, `DoubleVar`) which automatically invoke `_save_prefs` when modified. 
- **Storage Location**: `user_prefs/brain_viz.json`

### The Dual "Rotation" Controls
Historically, you might notice two distinct toggles referencing rotation. They are not in conflict; they control entirely different features:

1.  **Manual Drag Rotation (`rotation_enabled`)**: 
    - **UI Location**: Located in the main always-visible header bar labeled **"Rot"**. 
    - **Function**: Enables/disables the user's ability to click and drag the mouse to spin the 3D scene manually. It acts as an interaction lock to prevent accidental movement.
    - **Implementation**: Checked inside `_on_mouse_motion` before applying mouse deltas.

2.  **Autonomous Rotation (`auto_rotate_enabled`)**: 
    - **UI Location**: Located in the expanded "Automation" controls pane as **"Auto-Rotate"**.
    - **Function**: Starts a background timer (`_auto_rotate_tick`) that continuously spins the brain automatically without user interaction.
    - **Implementation**: Managed by `_update_auto_timers` and `_auto_rotate_tick`. It pauses dynamically if the user clicks a node (which triggers the `_view_animating` camera transition flag).

### Animation Lock Resolution
If a camera animation (e.g., smoothly panning to focus on a clicked node) is running, `_auto_rotate_tick` defers execution until `_view_animating = False`. If an animation is abruptly interrupted by the user clicking the map, the `_on_mouse_press` event explicitly breaks the lock (`_view_animating = False`) to allow auto-rotate to seamlessly resume when they let go.

## 4. Current Configuration Variables (JSON Map)
- `rotation_enabled`: (bool) User can manually drag to rotate.
- `scroll_enabled`: (bool) User can scroll to zoom.
- `invert_scroll`: (bool) Invert zoom direction.
- `mode_3d_enabled`: (bool) Overall 3D toggle.
- `auto_rotate_enabled`: (bool) Auto-spin the view via timer.
- `auto_rotate_deg_per_sec`: (float) Spin speed.
- `auto_cycle_enabled`: (bool) Auto focus on regions sequentially.
- `screensaver_enabled`: (bool) Enable idle screensaver.
- `node_alpha`, `edge_alpha`, `edge_width`: Display properties.