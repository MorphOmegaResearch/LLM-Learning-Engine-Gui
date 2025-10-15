# Co-op Plan – Phase 1 “0” Stabilisation (2025-09-16 21:45)

## Shared Context
- See `zero_point_project_context.md` for the original requirement list.
- `zero_point_context_sheet.md` now reflects latest progress (Soldier/Delta personas, routing, confirmers, snapshots).
- `vcm_implementation_log.md` documents Claude’s VCM architecture (currently framework only, no tiled backend).

## Goal for this block
Deliver a verifiable Phase‑1 orchestrator: “0” replies fast & coherently, can escalate to workflows, enforces confirmations/resource caps, and preserves state.

---
## Work Streams & Owners

### Codex (current session)
1. **Persona toggle & presets** (Soldier ↔ Delta) in launcher settings ✔ (base) → finish UI feedback.
2. **Workflow confirmations**: inject OMNIPOTENT dry-run summary before executing; log decision.
3. **Snapshot & evaluation metadata**: store persona, module status, resource usage; run evaluation harness in both personas (<5 GB proof).
4. **Timeout guard**: adjust zero/workflow RAM caps (0.85/0.75) and confirm real-world multi-turn resilience.

### Claude (when available)
1. **VCM backend gap**: prototype minimal tiled model view (even fake/loopback) so parity gate passes; document next steps for full Qwen tiling.
2. **Training suite integration**: finish vector index rebuild + LoRA pipeline so launcher menu items 5/6 run end-to-end (even if dependencies missing, provide graceful reports).
3. **Confirmers & resource UI**: review settings editor, ensure defaults align with safety plan; surface in documentation.

### Joint
- Align evaluation criteria (Phase‑1 pass checklist) and store results in `verify_phase1.log`.
- Prepare user playbook (`Next Stage.txt` update) covering Soldier fast mode, Delta workflow mode, confirmation workflow, snapshot restore.

---
## Timeline (short)
- **Now**: Codex executes tasks above (1–4), updates OngoingNotes with evidence.
- **Next (Claude)**: resume VCM/training pipeline tasks, note progress in `coordination.md`.
- **Together**: run evaluation harness + share RAM/coherence metrics before promoting to Phase 1.5.

Please acknowledge in `coordination.md` before making large changes to avoid collisions.
