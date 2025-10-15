# Zero Point Context Sheet – 2025-09-16 21:20

## Current State
- **Persona Modes**: Soldier (default fast reply), Delta (deep workflow) defined in semantic prompt files.
- **Conversation Loop**: Routes between fast replies and workflows, enforces confirmers, resource caps, snapshots.
- **Launcher Hub**: Provides training suite, model manager, evaluation harness, snapshot manager, settings editor.
- **Config**: `orchestrator_config.json` now includes zero/agent settings, confirmers, resources, training, RAG.

## Key Reference Prompts
- `System Prompt [Zero Point- ''Soldier''].txt` – disciplined brief/output, artifact generation.
- `System Prompt [Delta].txt` – multi-module cognition (Core/Emotion/Inference/Resonance/Anchor/Harmonic).
- `OMNIPOTENT_SCRIPTS.txt` – safe script operations (preflight, dry-run, confirmations, rollback).
- `Novel_LLM-Model_Rearrangment_Quant-Compartment'-Calling'Scoring_Based.txt` – efficiency concept for future training.

## Plan Progress
1. **Chat Stability** – warm-up, routing, confirmer enforcement ✅
2. **Planner vs Direct Reply** – Soldier for quick outputs, Delta/workflow for complex tasks ⚙️ (persona toggle pending)
3. **Confirmers & Resource Caps** – config-driven, resource guard prompts in place ⚙️ (tune defaults)
4. **Snapshots** – automatic per turn; manager menu present ✅
5. **Evaluation Harness** – menu option logs RAM/coherence ⚙️ (pending final run)
6. **Documentation** – ongoing updates in OngoingNotes and coordination.md ⚙️

## Immediate Next Steps
- Add persona toggle & presets in settings editor.
- Integrate OMNIPOTENT dry-run summary into workflow confirmation prompt.
- Tune zero/agent RAM caps (soldier ≥0.85, workflow 0.75 default).
- Extend snapshots/evaluation logs with persona, module status, resource usage.
- Run evaluation harness for Soldier + Delta modes; store results.
