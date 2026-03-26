# Custom Code Tab - Changelog

## v1.1 - Enhanced Chat Interface (2025-10-11)

### New Features

#### 1. **Mount/Dismount System**
- **Mount Button** (📌): Loads selected model into Ollama memory
  - Located in top control bar
  - Disabled after mounting
  - Background thread prevents UI freeze
  - Timeout handling (30s)

- **Dismount Button** (📍): Unloads model from active state
  - Enabled only when model is mounted
  - Immediate UI feedback
  - Clears mount status

#### 2. **Color-Coded Model Status**
- **Red (#ff6b6b)**: Model selected but not mounted
- **Green (#98c379)**: Model mounted and ready for chat
- **White (#ffffff)**: No model selected

Visual indicator provides instant feedback on model readiness.

#### 3. **Conversation History System**
- **Per-Model Persistence**: Each model maintains separate conversation history
- **History Tab** (📚): New sub-tab for managing conversations
  - View all conversations by model
  - Message count display
  - Load conversation: Switch to chat and restore history
  - Delete conversation: Remove specific model history

#### 4. **UI Improvements**
- **Stop Button Relocated**: Now positioned directly under Send button
  - Better visual grouping
  - More intuitive layout
- **Conversation Switching**: Automatically saves/loads history when changing models

### Technical Details

#### Mount/Dismount Implementation
**File:** `chat_interface_tab.py`
- Lines 230-296: Mount/dismount methods
- Uses `ollama run` command with empty input to load model
- Thread-safe UI updates via `root.after()`
- Handles timeout as success (model often loads before responding)

#### History Persistence
**File:** `chat_interface_tab.py`
- Line 30: `conversation_histories = {model_name: [messages]}`
- Lines 200-228: `set_model()` saves/loads conversation
- Lines 306-315: `redisplay_conversation()` rebuilds chat display

**File:** `custom_code_tab.py`
- Lines 95-246: History tab implementation
- Scrollable list of all conversations
- Load/Delete actions per conversation

#### Button Layout
**Before:**
```
Top: [Model Label] [Clear] [Stop]
Bottom: [Input] [Send]
```

**After:**
```
Top: [Model Label] [Mount] [Dismount] [Clear]
Bottom: [Input] [Send]
                [Stop]
```

### Usage Flow

1. **Select Model** from right panel
   - Model name turns **red** (not mounted)
   - Mount button enabled

2. **Mount Model**
   - Click 📌 Mount
   - System message shows mounting progress
   - Model name turns **green** when ready
   - Send button enabled

3. **Chat**
   - Type message, press Enter
   - Conversation persists automatically

4. **Switch Models**
   - Select different model
   - Current conversation saved automatically
   - New model conversation loaded if exists
   - Or new conversation started

5. **View History**
   - Switch to 📚 History tab
   - See all model conversations
   - Click "Load Conversation" to resume
   - Click "Delete" to remove history

6. **Dismount**
   - Click 📍 Dismount when done
   - Model name turns **red**
   - Send button disabled

### Code Changes Summary

#### Modified Files
1. **chat_interface_tab.py** (8 major changes)
   - Added `is_mounted` and `conversation_histories` state
   - Replaced ttk.Label with tk.Label for color support
   - Added mount/dismount buttons to controls
   - Relocated stop button to input area
   - Implemented `mount_model()` and `dismount_model()`
   - Enhanced `set_model()` with history management
   - Added `redisplay_conversation()` helper
   - Updated button states based on mount status

2. **custom_code_tab.py** (4 major changes)
   - Added History sub-tab to notebook
   - Implemented `create_history_tab()`
   - Added `refresh_history()` method
   - Implemented `load_conversation()` and `delete_conversation()`

### API Reference

#### Mount Model
```bash
ollama run <model-name> --verbose
# With empty stdin to just load
```

#### Color States
```python
# Not mounted / Dismounted
model_label.config(fg='#ff6b6b')  # Red

# Mounted and ready
model_label.config(fg='#98c379')  # Green

# No selection
model_label.config(fg='#ffffff')  # White
```

#### History Storage Structure
```python
conversation_histories = {
    "qwen2.5-coder": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"}
    ],
    "llama2": [
        {"role": "user", "content": "Test"},
        {"role": "assistant", "content": "Response"}
    ]
}
```

### Known Limitations

1. **Mount Timeout**: Fixed 30-second timeout
   - Large models may appear to timeout but actually loaded
   - Success assumed on timeout for better UX

2. **No Persistent Storage**: Conversations only persist in memory
   - Lost on application restart
   - Future: JSON file persistence

3. **Ollama Dismount**: No explicit unload API
   - Ollama manages memory automatically
   - Dismount is UI state only

### Future Enhancements

- [ ] Save conversations to JSON files
- [ ] Export conversation as markdown/text
- [ ] Import previous conversations
- [ ] Streaming response support
- [ ] Mount progress indicator
- [ ] Estimated mount time based on model size
- [ ] Auto-save on application close
- [ ] Search within conversation history

---

## v1.0 - Initial Release (2025-10-11)

- Basic chat interface
- Ollama model selection
- Message send/receive
- Clear chat functionality
- Tab-based architecture
