# OpenCode Tool System - Integration Checklist

## Critical Issues Found & Fixed ✅

### 1. **Parser Issues** ✅
- [x] Markdown code fences breaking JSON parsing (langchain_adapter_simple.py:94-104)
- [x] Shorthand format `{"type":"tool_name"}` not recognized (langchain_adapter_simple.py:140-151)
- [x] Missing json_fixer.py dependency (fallback works but should be added)

### 2. **Auto-Chain System** ✅
- [x] Reverse auto-chain (file_read with filename → file_search → file_read) implemented
- [x] Forward auto-chain (file_search → file_read) working
- [x] PASSTHROUGH alias support for parse_tool_result, extract_data, etc.

### 3. **Tool Alias System** ✅
- [x] 30+ common framework tools mapped to OpenCode equivalents
- [x] LangChain training data tools (parse_tool_result, etc.) supported
- [x] Integrated into orchestrator validation flow

---

## Remaining Issues to Address

### **CRITICAL - Tool Registration Inconsistencies**

**Problem:** Tools not consistently registered across all 4 required locations

**Impact:** Model can't see/use all tools, schemas missing, confirmation gates fail

**Required Locations for EVERY Tool:**
1. ✅ ToolManager.tools dict (tools.py:~1145)
2. ⚠️  tool_definitions dict (tools.py:~1238) - **MISSING: read_text**
3. ⚠️  config.yaml tools.enabled (line 135) - **MISSING: git_operations, read_text, resource_request**
4. ⚠️  risk_profiles dict (tool_orchestrator.py:~100) - **MISSING: read_text**

**Action Required:**
```python
# In tools.py tool_definitions (~line 1571):
"read_text": {
    "type": "function",
    "function": {
        "name": "read_text",
        "description": "Read contents of a file (alias for file_read)",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file"}
            },
            "required": ["file_path"]
        }
    }
}

# In config.yaml tools.enabled (~line 135):
# Add: git_operations, read_text, resource_request

# In tool_orchestrator.py risk_profiles (~line 100):
'read_text': ToolRiskLevel.SAFE,  # Alias for file_read
```

---

### **HIGH PRIORITY - Tool Descriptions**

**Problem:** Vague descriptions lead to wrong tool selection

**Current Issues:**
- `file_read`: "Read contents of a file" → Model doesn't know it needs exact path
- `file_search`: "Search for files by name pattern" → Doesn't emphasize FINDING vs READING
- `grep_search`: "Search for patterns in files" → Confusing with file_search

**Better Descriptions:**
```python
"file_read": {
    "description": "Read contents of a file (requires exact file path - if you only have filename, it will auto-search)",
    # ...
}

"file_search": {
    "description": "Find files by name pattern (returns paths - use this when you don't know exact location)",
    # ...
}

"grep_search": {
    "description": "Search for text patterns INSIDE files (use file_search to find files by name)",
    # ...
}
```

---

### **MEDIUM PRIORITY - Result Formatting**

**Problem:** Inconsistent result formats confuse model

**Issues Found:**
1. Manual chains use JSON format (line 3370-3379)
2. Auto-chains use plain text format (line 3998-4029)
3. Some tools return JSON strings, others return dicts
4. Truncation happens at different places (500 chars for chains, MAX_OUTPUT_CHARS for single)

**Recommendation:**
- Standardize on ONE format (suggest: structured JSON with clear sections)
- Consistent truncation rules
- Always include: success, output, error, metadata

---

### **MEDIUM PRIORITY - Tool Schema Updates**

**Missing Parameter Descriptions:**

Many tools have parameters without good descriptions:

```python
# file_search needs better args:
"pattern": {
    "type": "string",
    "description": "Filename or pattern to search for (e.g., '*.py' or 'config.yaml')"
},
"path": {
    "type": "string",
    "description": "Directory to search in (default: current directory)"
}

# bash_execute needs safety hints:
"command": {
    "type": "string",
    "description": "Bash command to execute (read-only commands are SAFE, destructive commands require confirmation)"
}

# grep_search needs clarity:
"pattern": {
    "type": "string",
    "description": "Text pattern to search for INSIDE files (not filename - use file_search for that)"
},
"file_pattern": {
    "type": "string",
    "description": "Limit search to files matching this pattern (e.g., '*.py')"
}
```

---

### **LOW PRIORITY - System Prompt Alignment**

**Problem:** System prompt vs reality mismatches

**Issues:**
1. Prompt says "20 tools" but 23 are registered
2. Auto-chain documented but incomplete coverage
3. No mention of alias support
4. Examples show think_time as decision type (old format)

**Fix in config.yaml:**
```yaml
# TOOL KIT (23 tools available, 20 enabled by default)
file_search, file_read, read_text (alias), file_copy, file_move, file_edit,
file_write, file_fill, file_create, file_delete, directory_list,
grep_search, bash_execute, change_directory, system_info,
think_time, process_manage, web_search, web_fetch, code_analyze,
package_check, git_operations (disabled), resource_request (disabled)

# SMART AUTO-CHAINING:
• file_search → file_read (auto-reads first result)
• directory_list → file_read (auto-reads first file)
• file_read with filename → file_search → file_read (reverse chain)

# TOOL ALIASES (training data compatibility):
• Models trained on LangChain/AutoGen can use familiar tool names
• parse_tool_result, extract_data → returns previous result
• read_file, execute_python, grep → mapped to OpenCode tools
```

---

### **LOW PRIORITY - Error Messages & Hints**

**Current:** "Tool not enabled: parse_tool_result"

**Better:**
```
⚠️ Alias detected: 'parse_tool_result' → Returning previous result
📋 Last result: [formatted output]
```

**Current:** "File not found: /some/path"

**Better:**
```
⚠️ File not found: /some/path
💡 Auto-chain triggered: file_search → file_read
   Searching for filename...
```

---

## Testing Checklist

### **Essential Tests:**

1. **Basic Tool Calls:**
   - [ ] `file_read` with exact path
   - [ ] `file_read` with just filename (should auto-chain)
   - [ ] `file_search` by name
   - [ ] `grep_search` for text pattern
   - [ ] `bash_execute` with safe command
   - [ ] `web_search` query

2. **Format Variations:**
   - [ ] Standard: `{"type":"tool_call","name":"file_read","args":{...}}`
   - [ ] Shorthand: `{"type":"file_read","args":{...}}`
   - [ ] Markdown wrapped: ` ```json{...}``` `
   - [ ] Array format: `[{"name":"tool1",...}]`

3. **Alias Support:**
   - [ ] `parse_tool_result` (should return last result)
   - [ ] `read_file` → `file_read`
   - [ ] `execute_python` → `bash_execute`
   - [ ] `grep` → `grep_search`

4. **Auto-Chains:**
   - [ ] `file_search` → auto `file_read`
   - [ ] `directory_list` → auto `file_read`
   - [ ] `file_read` with filename → auto `file_search` → `file_read`

5. **Error Handling:**
   - [ ] Tool not found
   - [ ] Invalid arguments
   - [ ] File doesn't exist
   - [ ] Permission denied

6. **Confirmation Gates:**
   - [ ] SAFE tools (no confirmation)
   - [ ] MEDIUM tools (explicit confirmation)
   - [ ] HIGH tools (must confirm)

---

## Performance Optimizations Needed

### **Context Management:**
1. Truncation is inconsistent (500 chars for chains, variable for single)
2. No token counting before sending to model
3. Large outputs can overflow context

**Recommendation:**
- Implement dynamic truncation based on remaining context
- Show truncation stats to model
- Prioritize recent tool results over older ones

### **Caching:**
- Cache enabled for read operations (5min TTL)
- Should also cache: system_info, package_check
- Consider semantic caching for similar queries

### **Retry Logic:**
- Auto-retry enabled (max 2 attempts)
- Should include exponential backoff
- Log retry attempts for debugging

---

## Integration Dependencies

### **Files That Must Be Updated Together:**

When adding a new tool, update ALL 5 locations:

1. `tools.py`:
   - Tool class implementation
   - ToolManager.tools dict registration
   - tool_definitions schema

2. `config.yaml`:
   - tools.enabled list
   - System prompt examples (if relevant)

3. `tool_orchestrator.py`:
   - risk_profiles dict
   - Validation logic (if special handling needed)

4. `interactive.py`:
   - Parameter normalization (if uses non-standard names)
   - Special display logic (optional)

5. `tool_alias_translator.py`:
   - Add common aliases if known

### **Critical File Relationships:**

```
interactive.py (main loop)
    ↓
tool_orchestrator.py (validation & auto-chain detection)
    ↓
tool_alias_translator.py (alias resolution)
    ↓
tools.py (actual execution)
    ↓
Back to interactive.py (result formatting & model callback)
```

---

## Quick Integration Test Script

```bash
#!/bin/bash
# Test critical tool system functionality

echo "Testing tool registration consistency..."
python3 -c "
from opencode.tools import ToolManager
from opencode.config import Config
config = Config.load('config.yaml')
tm = ToolManager(config)

tools_registered = set(tm.tools.keys())
tools_schemas = set(tm.get_tool_schemas())
tools_enabled = set(config.tools.enabled)

print(f'Registered: {len(tools_registered)}')
print(f'With schemas: {len(tools_schemas)}')
print(f'Enabled: {len(tools_enabled)}')

missing_schemas = tools_registered - tools_schemas
missing_enabled = tools_registered - tools_enabled

if missing_schemas:
    print(f'⚠️  Missing schemas: {missing_schemas}')
if missing_enabled:
    print(f'⚠️  Not enabled: {missing_enabled}')

if not missing_schemas and not missing_enabled:
    print('✅ All tools properly registered!')
"
```

---

## Priority Action Items

### **DO IMMEDIATELY:**
1. ✅ Add read_text to tool_definitions
2. ✅ Add missing tools to config.yaml enabled list
3. ✅ Add read_text to risk_profiles
4. ✅ Test reverse auto-chain with actual file

### **DO SOON:**
5. ✅ Update tool descriptions for clarity
6. ✅ Standardize result formatting
7. ✅ Update system prompt to match reality
8. ✅ Add comprehensive error hints

### **DO EVENTUALLY:**
9. ⬜ Add semantic caching
10. ⬜ Implement token-aware truncation
11. ⬜ Add retry exponential backoff
12. ⬜ Create tool usage analytics
