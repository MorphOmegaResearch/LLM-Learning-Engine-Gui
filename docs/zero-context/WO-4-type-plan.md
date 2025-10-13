# WO-4: Type Plan → Training Auto-Select (with manual override)

**Branch:** `feature/models-types-ui`
**Status:** Completed
**Date:** 2025-10-13

## Summary

Establishes an event bridge between the Types panel and Training tab, enabling automatic pre-filling of training recipes and evaluations based on a model's assigned Type. Manual override remains fully available.

## Files Modified

### Core Configuration (`Data/config.py`)
- **`get_training_plan_for_type(type_id: str) -> tuple[list[str], list[str]]`**
  Resolves training recipes and evaluations for a given type from the Type Catalog.

- **`get_training_plan_for_model(trainee_name: str) -> tuple[list[str], list[str]]`**
  Loads Model Profile and returns training plan based on `assigned_type`.

### Models Tab (`Data/tabs/models_tab/models_tab.py`)
- **Refactored `_refresh_overview()`**
  Now uses persistent OverviewPanel (no destroy/recreate), improving performance.

- **Ollama Catch-up**
  `display_model_info()` now calls `_refresh_overview()` for Ollama models, routing through OverviewPanel.

- **Event Handler: `_on_type_plan_applied()`**
  - Receives `<<TypePlanApplied>>` event from TypesPanel
  - Calls `get_training_plan_for_model()` to resolve recipes/evals
  - Forwards to Training tab via `apply_plan()` if available
  - Falls back to info messagebox if Training tab not hooked

- **Event Binding**
  Added conditional bind in `create_ui()` to wire event when `panel_types` exists.

### Types Panel (`Data/tabs/models_tab/types_panel.py`)
- **Event Emission**
  After `save_model_profile()` in `_apply_plan()`, emits `<<TypePlanApplied>>` event.

## How the Event Bridge Works

```
User clicks "Apply Type Plan" in TypesPanel
  ↓
TypesPanel saves Model Profile with assigned_type
  ↓
TypesPanel emits <<TypePlanApplied>> event
  ↓
ModelsTab._on_type_plan_applied() receives event
  ↓
Calls config.get_training_plan_for_model(trainee_name)
  ↓
Gets (recipes, evals) from Type Catalog
  ↓
Forwards to Training tab via apply_plan(recipes, evals)
  ↓
Training tab prefills selectors (manual override intact)
```

## Smoke Tests

### Headless Config Test
```bash
python3 - <<'PY'
from Data import config
name = "SmokeCoder-0_5B"
mp = {"trainee_name": name, "base_model": "torch:Qwen-0.5B", "assigned_type": "coder"}
config.save_model_profile(name, mp)
recipes, evals = config.get_training_plan_for_model(name)
print(f"Plan for {name}:")
print(f"  Recipes: {recipes}")
print(f"  Evals: {evals}")
PY
```

**Expected Output:**
```
Plan for SmokeCoder-0_5B:
  Recipes: ['recipes/coder/lora_code_instruct.json', ...]
  Evals: ['evals/coder/smoke', ...]
```

### GUI Test (Optional)
1. Open Models → Types tab
2. Select type "coder"
3. Click "Apply Type Plan"
4. Switch to Training tab
5. Verify selectors prefilled (or info dialog shown)

## Rollback Plan

No migrations or schema changes - safe revert via:
```bash
git revert HEAD
```

## Integration Points

- **Current:** Event bridge established, falls back to messagebox
- **Future (WO-4B):** Training tab adds `apply_plan(recipes, evals)` method
- **Future (WO-5):** Hybrid unlock system + color legend in Types UI

## Notes

- Manual override preserved: user can modify selectors after auto-fill
- Loosely coupled: Training tab hook is optional (graceful degradation)
- Type assignments persist in Model Profiles (atomic I/O with .bak)
