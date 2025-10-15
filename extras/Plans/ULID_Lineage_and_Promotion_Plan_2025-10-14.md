# ULID Lineage + One‑GGUF + Promotion System — Implementation Plan

Status: Draft for approval
Owner: Models/Training/Eval subsystems
Date: 2025-10-14

- Goal: Align Parent → Type Variant → GGUF lineage end‑to‑end with a stable ULID serial, enforce one GGUF per Variant (current phase), and define promotion/class roadmap with UI color system.

---

## Progress Snapshot

Confirmed by user (present and working)
- Phase 1 core: ULID lineage for variants; assignment schema v2 helpers; sidecars/report metadata include lineage_id.
- Phase 2: One‑GGUF gating + tooltip; delete cleans assignments and re‑enables Create.
- Phase 3a: Runner env carries variant/lineage; output folder naming includes variant + ULID‑short; sidecar enrichment; Evaluation metadata carries lineage.
- Phase 3b:
  - Training → Model Selection: added Variant combobox (filtered by Base); auto‑select on Apply.
  - Runner header: class chip + “Lineage: <short>”; Novice mode cue when no adapters.
  - Model Profiles: adapters[] and latest_adapter updated on training save.
  - Profiles tab: Set/Clear Default Profile; default applied silently; legacy “Profile Loaded” popup removed.
- Phase 4 (partial):
  - Models → Overview: Lineage section lists Variants (Collections) with Assigned GGUF tags.
  - Levels manifests: new saves include variant_id/lineage_id/type/class when derivable; existing manifests backfilled on read.
  - Export pipeline: Level → GGUF uses manifest lineage to tag `<variant_id>:<quant>`, enforces one‑GGUF gating, and registers assignment.

Notes (2025‑10‑14, Eval testing)
- User is testing Evaluation now; tooltips and eligibility logic are in place.
- Promotion button remains disabled until thresholds are met; alerts fire once when promotion unlocks.
- Lineage section provides live shortcuts to Variants and their Assigned GGUF models for faster navigation during testing.

Pending confirmation
- Variant combobox: visual chips/lineage short in entries (optional polish).
- History tabs: richer lineage grouping and compare readiness badges.
- Promotion to Skilled: thresholds + UI stub.

---

## Phase 0 — Groundwork (Already in Codebase)

- Models Tab UX fixes
  - Assigned/Unassigned groups expand beneath their own headers (done).
  - Evaluation tab shows Parent label and accurate Selected Model “Variant → gguf:tag” (done).
  - Variant selection resolves to assigned GGUF for evaluation; GGUF selection backfills type defaults (done).

---

## Phase 1 — ULID Lineage Core

Objective: Introduce `lineage_id` (ULID) as the canonical key across Variant, Assignments, Adapters/Levels, and Evaluation.

Steps
1) ID Generation and Backfill
   - Add `ensure_lineage_id(variant_id)` in `Data/config.py`.
   - TypesPanel: on Apply, assign ULID if missing and persist to Model/Training Profiles.
   - Collections refresh: backfill any legacy profiles lacking `lineage_id` (log once per session).

2) Assignment Schema v2 (backward compatible)
   - Evolve `Data/ollama_assignments.json` to:
     - `variants[variant_id] = { lineage_id, tags: [...] }`
     - `tag_index[tag] = lineage_id`
   - Helpers: `get_assigned_tags(lineage_id)`, `get_lineage_for_tag(tag)`, `set_assignment(variant_id, tag)`, `remove_assignment(tag)`.
   - Maintain legacy reader/writer compatibility (auto‑migrate on write).

3) Writers (Sidecars + Metadata)
   - training_engine: write `.variant.json` sidecar in outputs with `{ variant_id, lineage_id, base_model, assigned_type, class_level, ts }`.
   - Levels archive: include `lineage_id` in `manifest.json`.
   - Evaluation/Baseline reports: add `metadata.lineage_id`.

Acceptance
- New Variants always have a ULID.
- Assignments use and expose lineage helpers; reverse lookup tag → lineage works.
- Sidecars and reports include `lineage_id`.

---

## Phase 2 — One‑GGUF Gating and UI

Objective: Enforce exactly one GGUF per Variant in current phase; guide user to delete before re‑creating.

Steps
1) Models → Overview (Variant view)
   - Disable “Create GGUF for Variant” when `get_assigned_tags(lineage_id)` is non‑empty.
   - Tooltip: “GGUF exists: <tag>. Delete it to re‑export.”
   - Re‑enable after deletion (listen to GGUF delete → `remove_assignment(tag)`).

2) Assigned GGUF deletion
   - On delete action, call `remove_assignment(tag)` and refresh UI; re‑enable Create button.

3) Multi‑tag legacy safety
   - If legacy variants have >1 tag, show a chooser and recommend consolidating to one (current policy).

Acceptance
- Button state reflects assignment presence accurately.
- Deleting the assigned GGUF re‑enables Create without restart.

---

## Phase 3 — Training Runner + Model Selection Alignment (3a)

Objective: Ensure Training uses lineage consistently and names outputs accordingly.

Steps
1) Runner output naming
   - Include `variant_id` (and optionally short ULID) in adapter/checkpoint folder names.
   - Always write `.variant.json` sidecar (Phase 1.3).

2) Training Profile lineage
   - Persist `lineage_id` in `Data/profiles/Training/<variant>.json`.
   - `TrainingTab.apply_plan(variant_id)` loads lineage and hydrates:
     - Model Selection → set base model.
     - Runner right‑pane → scripts/prompts/schemas per Type plan.
     - Runner settings overrides per plan.

3) Model Selection panel
   - Resolve and show base from Model Profile by `lineage_id`.
   - Guard rails: disable Apply/Run when base missing.

Acceptance
- New training runs produce lineage‑tagged outputs.
- Training tab reflects variant lineage/base correctly on Apply.

---

## Phase 3b — Novice Flow, Variant Combobox, and Adapter Policy

Objective: Make novice state first‑class (no adapters yet), add a Variant selector in Training → Model Selection, and define minimal adapter redundancy policy.

Novice detection & behavior
- Detect via lineage_id: no adapters (.variant.json) discovered for this lineage and no assigned GGUF.
- Auto behavior: train purely from Training_Data‑Sets; show a “Novice mode” cue in Runner header.

Model Selection → Variant dropdown
- Add a second combobox under “Base Model:” labeled “Variant”.
- Populates with all variants filtered by selected base (and type if applicable).
- Auto‑selects the active Training Profile’s variant on Apply.
- “Send To Training” sets both base and variant context.

Runner header lineage/class
- Show class chip (novice/skilled/…) and short ULID next to “Training Model”.

Adapter redundancy policy (initial)
- Keep the N (default 3) latest adapters per lineage; older adapters can be archived via an action.
- Model Profile enrichment: track “adapters: []” and “latest_adapter”.

Acceptance
- Variant combobox appears and tracks the active profile/base.
- Runner header displays class + lineage.
- Novice mode cue appears when appropriate; training proceeds without adapters.

---

## Phase 4 — History, Levels, and Compare

Objective: Use lineage to connect Levels and Evals to their parent Variant/Base for reliable comparisons.

Steps
1) History → Runs
   - Link runs to Variant via `.variant.json` lineage_id.
   - Show badges/color per class (see Phase 6) and a short ULID.

2) History → Levels
   - Level `manifest.json` gains `lineage_id` (done for new saves; backfilled for legacy).
   - “Export to GGUF” dialog picks quant and auto‑assigns the tag to this lineage.

3) Compare tab
   - Prefer lineage‑aware compare (Variant’s latest eval vs active Baseline of its Base).

Acceptance
- Runs/Levels render using lineage joins; compare flows handle renames.

---

### Export Pipeline Refinement (Level → GGUF)

Objective: When exporting a Level to GGUF, prefer manifest’s lineage/variant fields to drive naming and assignment.

Refinements
- Resolve context from manifest first:
  - `variant_id`, `lineage_id`, `assigned_type`, `class_level` (backfilled where possible from adapter sidecars).
- Enforce one‑GGUF per lineage:
  - If `get_assigned_tags_by_lineage(lineage_id)` returns tags, gate export or prompt to replace.
- Tag naming policy (suggested):
  - `${variant_id}:${quant}` or `${base}-${variant}-${level}-${quant}` (decide centrally; prefer short, stable tags).
- Assignment update:
  - After successful `ollama create`, call `config.add_ollama_assignment(variant_id, tag)`; tag_index updated. 
  - Optionally persist `exported_tag` in the level manifest for history.
- UI refresh:
  - Update Assigned list + gating; show class chip colors accordingly.

Acceptance
- Exports are lineage‑aware; assignments updated consistently; UIs reflect Assigned promptly.

---
## Phase 5 — Evaluation Integration

Objective: Normalize Evaluation to operate on lineage consistently.

Steps
1) Variant select
   - Resolve assigned GGUF via `lineage_id` (already wired) and set override for inference.
   - Include `lineage_id` in `EvaluationEngine` metadata.

2) GGUF select
   - Reverse map tag → lineage → variant; apply type defaults and parent label (already wired).

3) Baseline/Auto‑resume
   - When exporting/pulling baseline GGUF, store assignment and lineage in the index so auto‑resume can target the right GGUF.

Acceptance
- Reports include lineage; source/selected labels remain accurate for both variant and GGUF flows.

---

## Phase 6 — Promotion System + Class Colors

Objective: Define promotion criteria and apply class colors across UI.

Class taxonomy and colors
- novice → green (#51cf66)
 
---

## Phase 7 — Automated Runtime Training Loop (Custom Code → Training)

Status: Proposed (ready to implement)
Owner: Custom Code + Training + Models subsystems
Date: 2025-10-15

Overview
- When Training Mode is enabled in Custom Code, failed tool_calls or refusals generate strict training examples automatically, select them in Training, and optionally start training with a user confirm. This enables “self‑refine on the spot”.

Goals
- Zero manual file hunting: runtime data is written and selected automatically.
- Keep everything lineage/type‑aware to prevent off‑scope data.
- Provide light, interruptible UX: a small prompt to start training now; progress mirrors Runner status.

Key Components (existing to reuse)
- ToolCallLogger (runtime logs) → runtime_to_training.py (converter) → strict JSONL writer.
- TrainingTab helpers: select_jsonl_path(path) and save_active_training_profile().
- RunnerPanel.start_runner_training() for starting training.
- Lineage/assignments helpers in config.py.

Data Flow
1) Chat (Custom Code) with Training Mode ON → tool_call batch completes.
2) Detect failures/refusals; generate strict entries: messages=[{"role":"user"}, {"role":"assistant","content":"{\"type\":\"tool_call\",...}"}] with scenario auto_from_runtime::<suite/type>::<skill>.
3) Write Tools/auto_runtime_<variant>_<suite>_<ts>.jsonl (type‑scoped).
4) Emit Tk event <<RuntimeTrainingDataReady>> with {variant_id, path}.
5) TrainingTab handles event → select_jsonl_path(path); save_active_training_profile().
6) Popup asks “Train now?”; on Yes → apply_plan(variant) if needed → RunnerPanel.start_runner_training().
7) Popup mirrors Runner status text; full logs in Runner tab. On finish, offer Export + Re‑Eval (manual for MVP).

Type Scoping
- Resolve mounted model tag → lineage_id → variant_id → assigned_type.
- Only emit examples/suggestions aligned to that type’s conformer/suite to avoid off‑scope training.

Event Bridge
- Custom Code: root.event_generate("<<RuntimeTrainingDataReady>>", data=json.dumps({"variant_id": vid, "path": str(out)})).
- TrainingTab: bind to update selections and persist profile.

---

## Phase 7b — Quick Actions, Per‑Chat Tools, Pane Locks (UI polish)

Status: Complete

Scope
- Quick Actions gear in Chat (bottom‑left)
  - Compact menu: 📂 Change Working Directory, 🔧 Manage Tools, 🏋️ Training Mode (colored state)
  - Tools view: enlarged, scrollable, checkboxes mirror Tools tab; Save applies per‑chat override and prints a diff summary in Chat
- Pane locks and default widths
  - Left Conversations and Right Models panes have lock buttons; locked widths persist and are enforced at launch
  - While locked: sash drag + hover cursors are disabled

Files
- Chat UI: Data/tabs/custom_code_tab/sub_tabs/chat_interface_tab.py
- Custom Code layout + right panel lock: Data/tabs/custom_code_tab/custom_code_tab.py

Notes
- Quick Tools “Save” sets only the per‑chat override (session_enabled_tools) and persists it in conversation metadata; defaults (tool_settings.json and Tools tab) remain the baseline
- Training Mode toggle moved into Quick Actions; state color: green ON, red OFF

---

## Test Plan — Auto‑Training from Custom Code (strict JSON tools)

Pre‑req
- Confirm Ollama server reachable; at least one variant has an Assigned tag.
- Training_Data‑Sets/Test has strict suites (CoderNovice, Tools, ResearcherNovice, Workflows, ThinkTime/Orchestration).

Steps
1) Mount & Tools
   - Select a model from right pane → Active Model updates (class color)
   - Click Mount → expect “mounted successfully ✓”; errors report if no model selected/ollama missing
   - Open ⚙️ → 🔧; verify tool list matches Tools tab; Save → Chat logs Enabled/Disabled and changes vs defaults

2) Training Mode + Failure capture
   - ⚙️ → 🏋️ set Training ON (button turns green)
   - Trigger a refusal or failed tool_call
   - Expect: Chat logs runtime training set created; Training tab selects dataset; profile saved

3) Hands‑free training
   - Turn ON auto‑start in Settings → Training; Save Settings
   - After dataset creation → training starts; progress popup shows run and percent; “View Logs” focuses Runner

4) Export + Re‑Eval (hands‑free)
   - Ensure “Auto‑Re‑Eval” is ON for context; after training complete, export + re‑eval runs (fallback strict context applied if necessary)

5) Promotion
   - If thresholds pass, promotion unlocks; else iterate

6) Per‑chat tool overrides persistence
   - Save conversation; load it from Conversations; verify tools override restored from session_tools in metadata

Acceptance
- Quick Actions works; per‑chat tool overrides apply and persist; Auto‑Training pipeline runs end‑to‑end hands‑free when toggles are ON; pane locks persist widths across relaunch and disable sash drag while locked.

UX Details
- Settings → Training Data Collection (existing) toggles the whole feature.
- Small in‑chat popup with Yes/No; “View Logs” button focuses Training → Runner.
- Progress line in popup: mirrors Runner “Run X of Y / status”.

Persistence
- Training Profile updated on dataset selection and Runner Start (already wired in Phase 6 changes).
- Runtime JSONLs saved under Tools/ with timestamp and type; profile gets selected_scripts/prompts/schemas untouched unless user changes.

Acceptance (MVP)
- Trigger a refusal or failed tool_call in Custom Code with training mode ON.
- A Tools/auto_runtime_*.jsonl is created, appears selected in Training, and profile is saved.
- User can start training from the popup; progress mirrors; full logs in Runner.

Milestones / Tasks
1) runtime_to_training: add strict writer and per‑variant save helper.
2) Chat hook: after logging tool results in training mode, call writer and event_generate.
3) TrainingTab: add event handler for <<RuntimeTrainingDataReady>> to select + save.
4) Popup prompt + progress mirroring in Chat; button to open Runner tab.
5) (Next) Auto Export + Re‑Eval toggle wiring after training completes.

Risks / Notes
- Ensure strict format matches Eval/Training parser (assistant content is JSON string of tool_call).
- Guard with type scoping to avoid drift; label scenarios for auditability.
- Keep the loop opt‑in via the existing Training Mode toggle.

- skilled → blue (#61dafb)
- expert → purple (#9b59b6)
- master → orange (#ffa94d)
- artifact → deep‑red (#c92a2a)
  - Artifact: hybrid types with high stats/transferable skills; may include cameo models.

Steps
1) Class in Model Profile
   - `class_level` string with values above; default “novice”.
   - Promotion policy docs (per type) define thresholds (e.g., pass rate deltas vs baseline, JSON/schema validity, stability).

2) Promotion to Skilled (novice → skilled)
   - Trigger: button in Models → Overview (enabled when thresholds met) or manual.
   - New Skilled Variant Profile:
     - `trainee_name`: e.g., `<base>_<type><skilled>`
     - `base_model`: inherited from novice
     - `assigned_type`: copied from novice
     - `class_level`: `skilled`
     - `lineage_id`: new ULID for the Skilled variant
     - `parent_variant_id`: link to the novice variant
   - Use latest adapters linked to the novice lineage (user may pick if >1).
   - Export a new Skilled GGUF and assign to the Skilled variant lineage.
   - Collections: show both novice (green) and skilled (blue) variants; Assigned shows chips accordingly.

3) Promotion thresholds (tunable)
   - Overall pass‑rate Δ vs baseline ≥ +5%
   - JSON validity ≥ 95%, Schema validity ≥ 95%
   - No critical regressions
   - Stats tab suggests “Eligible for Promotion” when criteria met.

4) Color application
   - Collections list: color chip / left border.
   - Models → Overview: class badge with color.
   - History: class at time of run; adapters list shows `[class]`.
   - Evaluation: class color in header.

Acceptance
- Visible class colors across panels; promotion action updates UI and persisted profiles.

---

## Phase 7 — UX Polish and Tools

Steps
1) Multiple assigned tags (future)
   - If >1 tag allowed later (e.g., promotions), add quick chooser bound to lineage.

2) Lineage label in Evaluation
   - Show “Lineage: <ULID‑short>” under Parent label.

3) Reload/State
   - WO‑7a: Add Reload buttons (Collections/Profiles) without restart.
   - WO‑6j: Persist expand/collapse and last selection including `last_lineage_id`.

---

## Phase 8 — Migration and Backward Compatibility

Steps
1) Profiles backfill
   - On Collections load, add missing `lineage_id` and save.

2) Assignments read
   - Accept legacy `{ variant: [tags] }`; materialize `variants[variant]` and `tag_index` on write.

3) Graceful fallbacks
   - If lineage unknown for an old GGUF tag, fall back to name‑based heuristics; offer “Link to Variant” flow to attach lineage.

---

## Dependencies and Risks

- Dependencies
  - `ulid-py` or small internal ULID generator (or UUIDv4 if ULID unavailable; store as string).
  - No DB; JSON sidecars and indices are adequate for now.

- Risks
  - Partial migrations: mitigate via backfill on read and non‑destructive writes.
  - Legacy multiple tags: surface chooser UX and guidance.

---

## Validation Checklist

- New variant → gets ULID; Collection shows color per class.
- Create GGUF disabled when one is assigned; re‑enabled on delete.
- Training Apply hydrates Model Selection and Runner with lineage‑correct data.
- Variant combobox shows correct options filtered by base and selects the active profile.
- Novice mode cue present when no adapters; training works from datasets.
- Adapters and Levels show lineage in sidecars and manifests.
- Evaluation reports include lineage_id; labels reflect Variant/GGUF/Parent.
- Level → GGUF export prefers manifest lineage/variant; updates assignments and gating.

---

## Next Actions (Dev)

1) Implement Phase 1 (ULID core + assignments v2 + sidecars/metadata).
2) Implement Phase 2 (one‑GGUF gating in Overview + delete hook).
3) Wire Training Profile lineage and Runner sidecar write (Phase 3).
4) Add Variant combobox and Runner lineage/class header (Phase 3b). [done]
5) Add class color rendering in Collections and Overview (Phase 6.4). [done]
6) Add small “Lineage: <short>” label in Evaluation (Phase 7.2). [done]
7) Implement Export Pipeline Refinement (manifest‑driven lineage assignment).
8) Add Promotion (novice → skilled) stub with thresholds and UI.

---

## Appendix — Work‑Orders Alignment

- WO‑6b–6j: Types/Collections wiring, UI state persistence, variant lineage/badges/colors → Phases 1, 6, 7.
- WO‑6k–6z: Runner/model‑selection tightening → Phase 3.
- WO‑7a–7z: Reload buttons, post‑apply relays, Collections polish → Phase 7.
