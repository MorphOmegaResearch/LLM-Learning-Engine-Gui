# Codex Plan – 2025-09-16 19:35

## Immediate Goals
1. Integrate new orchestrator core with Claude’s vector index + training pipeline drafts.
2. Extend launcher hub with menu entries for “Training Suite” and “Model Manager”.
3. Finalize documentation and instructions for running evaluation harness.

## Coordination Steps
- Confirm Claude’s status in `coordination.md` (vector_index.py & training_pipeline.py pending).
- After Claude commits pipeline scripts, wire hub options to invoke them and handle configs.
- Document updates in this folder after each milestone.

## Next Actions (Codex)
- Review `crewai-orchestrator/vector_index.py` and `training_pipeline.py` (when available).
- Add hub menu option stubs linking to training commands.
- Update evaluation harness instructions to reference trained models.

## Update 19:45
- Consolidated “ongoing notes” into `OngoingNotes/` for shared tracking.
- Added hub menu stubs for Training Suite + Model Manager.

## Update 20:00 – Feature Sweep
- Launcher hub will expose: chat, orchestrate task, view logs, training suite, model manager, evaluation harness.
- Model selection roadmap:
  * Direct `ollama/*` entries for raw completions.
  * `litellm/*` for tool-capable orchestrator jobs.
  * Add future trained adapters under `ollama/<name>-coherent` and auto-refresh configs.
- Additional features to consider:
  * Automated log rotation + vector index rebuild.
  * Shortcut to open evaluation harness with prompt override.
  * “Session archive” option to package context_working logs into Project Plans.
- Waiting on Claude’s training/vector scripts to finalize wiring and tests.

## Update 20:10
- Added Evaluation Harness option to launcher hub (menu item 7) to run `tools/evaluate.py`; services restart moved to option 8.
- Plan: run evaluation after addressing timeout behaviour with lighter worker model + warmup routine.

## Update 21:00 – Phase 1 foundations
- Rebuilt configuration loader with zero/agent/confirmers/resource sections and reset cache utility.
- Conversation loop now:
  * warms models, restores snapshots, enforces confirmers and resource caps,
  * routes between direct replies (model `0`) and agent workflows via planner,
  * logs snapshots for rollback after every turn.
- Launcher hub gained Snapshot Manager and Settings editor (model selection, confirmers, limits).
- Evaluation menu logs results via `append_log`.
- Next: run warm-up tests, adjust resource defaults, then execute evaluation harness to capture RAM + coherence evidence.

## Update 21:20 – Persona integration
- Added zero/workflow resource defaults (zero=0.85 RAM cap). Created presets (Soldier, Delta) storing zero + workflow settings.
- Launcher settings menu now lists presets for instant switching; manual edits still available.
- TODO: Use OMNIPOTENT dry-run text as part of workflow confirmation, log persona name in snapshots, and add evaluation runs per persona.
