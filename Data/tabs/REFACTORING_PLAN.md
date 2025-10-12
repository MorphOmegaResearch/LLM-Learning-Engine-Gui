# Tab Refactoring Plan

## Current Status
- **Main GUI**: 1206 lines in `interactive_trainer_gui.py`
- **Structure Created**: Folders for `training_tab/` and `models_tab/`
- **Framework**: Base tab class with error isolation

## Refactoring Strategy

### Phase 1: Extract Training Tab (17 methods, ~600 lines)
**Methods to move to `tabs/training_tab/training_tab.py`:**
- create_category_panel
- create_category_section
- toggle_category
- create_config_panel
- create_preview_panel
- create_buttons
- select_all, deselect_all
- load_profile_from_gui, save_profile_from_gui
- update_profile_combobox
- create_new_category, create_new_subcategory
- refresh_category_panel
- update_preview, count_file
- start_training

### Phase 2: Extract Models Tab (~400 lines)
**Methods to move to `tabs/models_tab/models_tab.py`:**
- create_models_tab
- populate_model_list
- display_model_info
- create_notes_panel
- populate_notes_list
- save_note, load_note, delete_note
- create_stats_panel
- populate_stats_display

### Phase 3: Slim Main GUI (~200 lines)
**Keep in `interactive_trainer_gui.py`:**
- __init__ (setup root, style, theme)
- create_ui (header + load tabs)
- run() method

## Implementation Steps

1. Create `training_tab/training_tab.py` with BaseTab inheritance
2. Move all training methods, adjust self references
3. Create `models_tab/models_tab.py` with BaseTab inheritance
4. Move all models methods
5. Update main GUI to instantiate tab classes
6. Test each tab independently
7. Verify error isolation works

## Benefits
- Each tab in separate folder
- Crashes isolated to single tab
- Easy to add new tabs
- Clear code organization
