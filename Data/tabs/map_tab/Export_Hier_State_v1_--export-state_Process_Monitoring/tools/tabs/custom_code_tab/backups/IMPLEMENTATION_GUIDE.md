# Custom Code Tab - Implementation Guide

## Overview

The Custom Code tab now features a comprehensive tool management system that preserves the existing OpenCode tool infrastructure while providing GUI controls for configuration.

---

## ✅ Completed Features

### 1. **Tools Sub-Tab** (🔧 Tools)
**File:** `Data/tabs/custom_code_tab/sub_tabs/tools_tab.py`

#### Features:
- **20+ OpenCode Tools** organized by category
- **Enable/Disable toggles** for each tool
- **Risk level indicators** (color-coded)
- **Tool categories**:
  - 📂 File Operations (8 tools)
  - 🔍 Search & Discovery (3 tools)
  - ⚡ Execution (2 tools)
  - 🖥️ System (3 tools)

#### Tool List:
```python
File Operations:
- file_read (SAFE) - Read file contents
- file_write (MEDIUM) - Write/create files
- file_edit (MEDIUM) - Edit existing files
- file_copy (LOW) - Copy files
- file_move (MEDIUM) - Move/rename files
- file_delete (HIGH) - Delete files
- file_create (LOW) - Create empty files
- file_fill (MEDIUM) - Fill file with content

Search & Discovery:
- grep_search (SAFE) - Search file contents
- file_search (SAFE) - Find files by name/pattern
- directory_list (SAFE) - List directory contents

Execution:
- bash_execute (CRITICAL) - Run shell commands
- git_operations (MEDIUM) - Git commands

System:
- system_info (SAFE) - Get system information
- change_directory (LOW) - Change working directory
- resource_request (LOW) - Request system resources
```

#### Settings Persistence:
- **Location:** `Data/tabs/custom_code_tab/tool_settings.json`
- **Format:**
```json
{
  "enabled_tools": {
    "file_read": true,
    "bash_execute": false,
    ...
  }
}
```

### 2. **Custom Code Settings** (Settings → Custom Code)
**File:** `Data/tabs/settings_tab/settings_tab.py` (lines 1603-1782)

#### Features:
Three main sections with manual toggles:

**🎯 Tool Orchestrator**
- Advanced tool chaining
- Confirmation gates
- Risk assessment
- Default: **OFF** (manual enable when needed)

**🔄 Format Translators**
- JSON Format Translator (default: ON)
- YAML Format Translator (default: OFF)

**📋 Response Parsers**
- Structured Output Parser (default: ON)
- DateTime Parser (default: OFF)
- Regex Pattern Parser (default: OFF)

**⚙️ Advanced Features**
- Context Scoring (RAG optimization) - default: OFF
- Time-Sliced Generation - default: OFF
- Verification Engine (output validation) - default: OFF

#### Settings Persistence:
- **Location:** `Data/settings.json` → `custom_code` section
- **Format:**
```json
{
  "custom_code": {
    "enable_tool_orchestrator": false,
    "enable_json_translator": true,
    "enable_yaml_translator": false,
    "enable_structured_parser": true,
    "enable_datetime_parser": false,
    "enable_regex_parser": false,
    "enable_context_scorer": false,
    "enable_time_slicer": false,
    "enable_verification_engine": false
  }
}
```

---

## 🏗️ Architecture

### Integration with Existing OpenCode System

The implementation **preserves** the existing OpenCode tool system:

1. **Tools Module** (`site-packages/opencode/tools.py`)
   - All 20 tool classes remain intact
   - `BaseTool`, `FileReadTool`, `BashExecuteTool`, etc.
   - No modifications to core tool logic

2. **Tool Orchestrator** (`tool_orchestrator.py`)
   - `AdvancedToolOrchestrator` class preserved
   - Risk assessment system intact
   - Confirmation gates preserved

3. **Router** (`router.py`)
   - Intent detection preserved
   - Tool routing logic intact

### GUI Layer

The GUI acts as a **configuration layer** on top of the existing system:

```
┌─────────────────────────────────────┐
│     Custom Code Tab (GUI)           │
│  ┌───────────┬───────────────────┐  │
│  │ Chat      │ Tools   │ History │  │
│  └───────────┴───────────────────┘  │
└─────────────────────────────────────┘
              │
              ├─ Tool Settings (tool_settings.json)
              └─ Feature Settings (settings.json → custom_code)
              │
┌─────────────▼───────────────────────┐
│  OpenCode Core (Preserved)          │
│  ┌────────┬──────────┬──────────┐   │
│  │ tools  │ router   │ orchestr │   │
│  │  .py   │  .py     │  ator.py │   │
│  └────────┴──────────┴──────────┘   │
└─────────────────────────────────────┘
```

---

## 🔧 Usage Guide

### Enabling/Disabling Tools

1. Navigate to **Custom Code → Tools** tab
2. Browse tool categories
3. Toggle checkboxes for desired tools
4. Click **💾 Save Settings**
5. Settings apply immediately (no restart required)

**Default Configuration:**
- ✅ All SAFE, LOW, MEDIUM risk tools: **Enabled**
- ❌ CRITICAL risk tools (bash_execute): **Disabled**

### Enabling Advanced Features

1. Go to **Settings → Custom Code**
2. Enable desired features:
   - **Tool Orchestrator**: Only when you need intelligent tool chaining
   - **Parsers**: Based on expected response formats
   - **Advanced Features**: For specific use cases (RAG, verification, etc.)
3. Click **💾 Save Custom Code Settings**
4. Features activate on next chat interaction

**Recommendation:** Start with defaults, enable features as needed.

---

## 📊 Risk Assessment

### Tool Risk Levels

| Risk Level | Description | Requires Confirmation | Examples |
|------------|-------------|----------------------|----------|
| SAFE | Read-only, no modifications | No | file_read, grep_search |
| LOW | Minor changes, reversible | No | file_create, file_copy |
| MEDIUM | File modifications | Optional | file_edit, file_write |
| HIGH | Destructive operations | Recommended | file_delete |
| CRITICAL | System-level changes | Mandatory | bash_execute |

### Confirmation Gates (Tool Orchestrator)

When Tool Orchestrator is enabled:

```python
ConfirmationGate.NONE      # No confirmation
ConfirmationGate.IMPLICIT  # Implied consent from context
ConfirmationGate.EXPLICIT  # User must confirm
ConfirmationGate.MANDATORY # Always requires confirmation
```

---

## 🔌 Integration Points

### Chat Interface Integration (Future)

The tools and settings are **ready for integration** with the chat interface:

```python
# In chat_interface_tab.py
from pathlib import Path
import json

def get_enabled_tools():
    """Get list of enabled tools from settings"""
    tool_settings = Path(__file__).parent.parent / "tool_settings.json"
    if tool_settings.exists():
        with open(tool_settings) as f:
            settings = json.load(f)
            return settings.get('enabled_tools', {})
    return {}

def prepare_chat_payload(message):
    """Prepare chat payload with tools"""
    enabled_tools = get_enabled_tools()

    # Filter tools based on settings
    tools = [
        tool_definition
        for tool_name, tool_definition in ALL_TOOLS.items()
        if enabled_tools.get(tool_name, False)
    ]

    return {
        "model": self.current_model,
        "messages": self.chat_history,
        "tools": tools,  # Include enabled tools
        "stream": False
    }
```

### Tool Schemas

Each tool needs a JSON schema for Ollama:

```json
{
  "type": "function",
  "function": {
    "name": "file_read",
    "description": "Read contents of a file",
    "parameters": {
      "type": "object",
      "properties": {
        "file_path": {
          "type": "string",
          "description": "Path to the file to read"
        },
        "start_line": {
          "type": "integer",
          "description": "Starting line number (optional)"
        },
        "end_line": {
          "type": "integer",
          "description": "Ending line number (optional)"
        }
      },
      "required": ["file_path"]
    }
  }
}
```

---

## 📝 Next Steps

### Phase 1: Tool Schemas (Not Yet Implemented)
- [ ] Create JSON schemas for each tool
- [ ] Store in `Data/tabs/custom_code_tab/tool_schemas/`
- [ ] Auto-generate from tool class definitions

### Phase 2: Chat Integration (Not Yet Implemented)
- [ ] Read enabled tools from settings
- [ ] Include tool definitions in chat payload
- [ ] Parse tool_calls from model response
- [ ] Execute tools using existing OpenCode classes
- [ ] Return results to model

### Phase 3: Tool Execution Handler (Not Yet Implemented)
- [ ] Tool execution wrapper
- [ ] Confirmation gate UI (for risky operations)
- [ ] Tool result formatting
- [ ] Error handling and retry logic

### Phase 4: Orchestrator Integration (Not Yet Implemented)
- [ ] Tool chain builder
- [ ] Risk assessment UI
- [ ] Parallel execution display
- [ ] Rollback mechanism

---

## 🐛 Troubleshooting

### Tools Settings Not Persisting
**Issue:** Tool settings reset after restart
**Cause:** `tool_settings.json` not being saved
**Fix:** Check file permissions on `Data/tabs/custom_code_tab/tool_settings.json`

### Advanced Features Not Working
**Issue:** Feature toggle has no effect
**Cause:** Feature not yet integrated with chat
**Status:** Settings UI complete, integration pending

### Tool Orchestrator Not Available
**Issue:** Orchestrator toggle exists but functionality missing
**Status:** Configuration UI complete, execution pending Phase 4

---

## 📚 References

### OpenCode Core Files
- `site-packages/opencode/tools.py` - Tool implementations
- `site-packages/opencode/tool_orchestrator.py` - Advanced orchestration
- `site-packages/opencode/router.py` - Intent routing
- `site-packages/opencode/confirmation_gates.py` - Confirmation system

### GUI Files
- `Data/tabs/custom_code_tab/sub_tabs/tools_tab.py` - Tools UI
- `Data/tabs/settings_tab/settings_tab.py` (lines 1603-1782) - Settings UI
- `Data/tabs/custom_code_tab/custom_code_tab.py` - Main tab

### Settings Files
- `Data/tabs/custom_code_tab/tool_settings.json` - Tool enable/disable
- `Data/settings.json` → `custom_code` section - Feature toggles

---

## 🎯 Design Principles

1. **Preserve Existing Code**: No modifications to OpenCode core
2. **Manual Control**: All advanced features disabled by default
3. **Safety First**: Critical tools disabled, confirmation gates supported
4. **Extensible**: Easy to add new tools and features
5. **User-Friendly**: Clear categorization and risk indicators

---

## 📊 Summary

**What's Working:**
- ✅ Tool configuration UI (20 tools)
- ✅ Risk level display
- ✅ Settings persistence
- ✅ Custom Code settings panel
- ✅ Feature toggles (orchestrator, parsers, translators)

**What's Not Integrated (Yet):**
- ⏳ Tool execution from chat
- ⏳ Tool schemas generation
- ⏳ Tool orchestrator execution
- ⏳ Confirmation gate UI
- ⏳ Response parsing integration

**Recommendation:**
The foundation is complete. You can now:
1. Configure which tools you want available
2. Toggle advanced features as needed
3. Ready for Phase 2: Chat integration with tool calling

Would you like me to proceed with implementing the tool schemas and chat integration next?
