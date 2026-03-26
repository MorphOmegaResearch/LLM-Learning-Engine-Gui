# Custom Code Tab

The **Custom Code Tab** provides interactive chat and tooling features for the OpenCode Trainer GUI.

## Features

### 💬 Chat Interface (Active)
- **Model Selection**: Select from available Ollama models via the right-side panel
- **Interactive Chat**: Send messages and receive responses from your selected model
- **Chat History**: Full conversation context maintained throughout the session
- **Keyboard Shortcuts**:
  - `Enter` to send message
  - `Shift+Enter` for new line
- **Controls**:
  - Clear chat history
  - Stop generation (placeholder for streaming)

### 🔧 Tools (Planned)
File operations, code analysis, and OpenCode tool integration

### 📁 Projects (Planned)
Project workspace management and code generation

## Architecture

```
custom_code_tab/
├── __init__.py              # Module exports
├── custom_code_tab.py       # Main tab with sub-tabs
├── sub_tabs/
│   ├── __init__.py
│   └── chat_interface_tab.py  # Chat UI implementation
└── README.md                # This file
```

## Design Pattern

The Custom Code tab follows the established Trainer GUI architecture:

- **Inherits from BaseTab**: Error handling and standardized initialization
- **Sub-tab Structure**: Uses ttk.Notebook for multiple sub-panels
- **Right-side Model Panel**: Mimics the Models tab design for consistency
- **Dark Theme**: Matches the application's color scheme (#2b2b2b, #1e1e1e, #61dafb)

## Integration

### Enable/Disable
The tab can be controlled via:
1. **Settings Tab** → Tab Manager → "Show Custom Code Tab"
2. **settings.json**: Set `"custom_code_tab_enabled": true/false`

### Tab Order
Configure in `settings.json`:
```json
"tab_order": [
  "training_tab",
  "models_tab",
  "custom_code_tab",
  "settings_tab"
]
```

## Chat API

The chat interface uses Ollama's HTTP API:
- **Endpoint**: `http://localhost:11434/api/chat`
- **Method**: POST with JSON payload
- **Format**:
```json
{
  "model": "model-name",
  "messages": [
    {"role": "user", "content": "message"},
    {"role": "assistant", "content": "response"}
  ],
  "stream": false
}
```

## Future Development

### Phase 1 (Completed)
- ✅ Basic tab structure with sub-tabs
- ✅ Model selector (right panel)
- ✅ Chat interface with Ollama integration
- ✅ Settings integration (enable/disable)

### Phase 2 (Planned)
- [ ] Tools sub-tab: File operations (read, write, search)
- [ ] Project management sub-tab
- [ ] Streaming responses
- [ ] Message export/import
- [ ] Chat templates

### Phase 3 (Future)
- [ ] Full OpenCode integration
- [ ] Event bus for GUI-safe operations
- [ ] Background task management
- [ ] Rich → Tkinter migration completion

## Development Notes

### Safe Integration
The tab is **disabled by default** (`custom_code_tab_enabled: false`) to ensure safe integration. Enable it when ready to use.

### Testing
Run the test script to verify imports:
```bash
cd /home/commander/Desktop/Trainer
python3 test_custom_code_tab.py
```

### Logging
All operations are logged via `logger_util.log_message()` with the `CUSTOM_CODE_TAB` prefix.

### Dependencies
- Python 3.x
- tkinter/ttk
- Ollama (for chat functionality)
- curl (for API calls)

## Contributing

When adding new features:
1. Follow the BaseTab pattern
2. Use the existing style configuration
3. Add logging for debugging
4. Update this README
