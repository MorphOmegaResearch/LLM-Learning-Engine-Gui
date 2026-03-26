# Tool System Investigation - Findings Report

## COMPLETED INVESTIGATIONS

### Point 1: Tool Registration Consistency ✅

**Finding:** INCONSISTENT - 3 tools missing from various locations

**Details:**
- **ToolManager.tools dict:** 23 tools registered
- **tool_definitions (schemas):** 22 tools (missing `read_text`)
- **config.yaml enabled:** 20 tools (missing `git_operations`, `read_text`, `resource_request`)
- **risk_profiles:** 22 tools (missing `read_text`)

**Impact:**
- `read_text` has no schema → model never sees it
- `git_operations` and `resource_request` disabled in config despite being implemented
- Inconsistency could cause confusion about which tools are actually available

**Location References:**
- tools.py:1145 - ToolManager.tools dict
- tools.py:1238 - tool_definitions dict
- config.yaml:135 - tools.enabled list
- tool_orchestrator.py:100 - risk_profiles dict

---

### Point 2: Tool Call Detection & Parsing ✅

**Finding:** MULTI-LAYERED with fallback strategy

**Detection Flow:**
1. **Primary:** `lc_adapter.parse_and_validate()` (interactive.py:3230)
   - Strategy 1: Direct JSON parsing
   - Strategy 2: Partial JSON parsing (uses json_fixer - NOT IN SYSTEM LOCATION)
   - Strategy 3: Falls back to format_translator

2. **Fallback:** `translate_tool_call()` (interactive.py:3236)
   - Handles gorilla-style Python function calls
   - Handles various JSON formats
   - Has special logic for markdown blocks

**Issues Found:**
- json_fixer.py not in system location → Strategy 2 always fails
- lc_adapter._try_partial_json imports json_fixer but file missing
- Still works due to format_translator fallback

---

### Point 3: Tool Execution Flow ✅

**Finding:** WELL-STRUCTURED with multiple safety layers

**Execution Path:**
1. **Detection:** lc_adapter.parse_and_validate() → tool_call dict
2. **Routing:** interactive.py:3317-3318 extracts name/args
3. **Safety Layer:** _safe_execute_tool() (interactive.py:279)
   - Parameter normalization (maps common variations)
   - Live progress display with spinner
   - Error handling with traceback
4. **Manager Layer:** tool_manager.execute_tool() (tools.py:1581)
   - Validation (enabled check, exists check)
   - Argument normalization
   - Cache check (if enabled)
   - Retry logic (if enabled)
5. **Tool Layer:** Individual tool.execute() method
   - Actual work performed
   - Returns ToolResult

**Result Flow:**
- ToolResult → dict conversion in _safe_execute_tool
- Format: `{"success": bool, "output": str, "error": str|None}`

**Special Features:**
- Parameter aliases (path→file_path, filename→file_path, etc.)
- Caching for read-only operations (5min TTL)
- Retry up to 2 times on failure (if auto_retry enabled)
- change_directory propagates to all tools

---

## FINDINGS SO FAR

### Bug Fixes Applied:

**Bug 1: Shorthand format not recognized**
- Model sends: `{"type":"file_read","args":{...}}`
- lc_adapter._normalize_tool_call only checked name/tool/function fields
- Fixed: Now checks if 'type' != 'tool_call' and uses it as tool name
- File: langchain_adapter_simple.py:138-151

**Bug 2: Markdown code fences break parsing**
- Model wraps in: ` ```json{...}``` `
- lc_adapter._try_direct_json didn't strip fences
- Fixed: Strip ```json/``` markers before parsing
- File: langchain_adapter_simple.py:84-118

### Key Insights:

1. **Redundant Parsers:** Two parsing systems (lc_adapter + format_translator) with overlapping logic but different implementations

2. **Missing Dependencies:** json_fixer.py not in system location but imported by lc_adapter

3. **Hidden Aliases:** read_text is alias for file_read (format_translator.py:25) but not documented

4. **Inconsistent Tool Count:** System says "20 tools" but 23 are registered

---

## Points 4-7: Tool Chains ✅

**Finding:** COMPREHENSIVE with dual chain support + auto-chaining

**Chain Detection (Point 4):**
- **Format 1:** `{"type":"tool_chain","tools":[...]}`  (interactive.py:3241-3258)
- **Format 2:** `[{"name":"tool1",...},{"name":"tool2",...}]` (interactive.py:3260-3281)
- Both formats detected via regex, converted to standard internal format

**Individual Handling (Point 5):**
- Each tool in chain goes through _safe_execute_tool() (line 3328)
- Sequential execution with early termination on failure (line 3336-3345)
- Progress tracking: "Step X/Y: tool_name" display
- Results accumulated in chain_results list

**Auto-Chaining (Point 6):**
- **IMPLEMENTED** at interactive.py:3958-3995
- Safe chains defined in SAFE_CHAINS dict (line 3963):
  - `file_search` → `file_read` (auto-reads first result)
  - `directory_list` → `file_read` (auto-reads first file)
- Saves model calls by executing predictable follow-ups
- Marked with `[AUTO-CHAIN]` tag in results (line 4023)
- System prompt documents this (config.yaml:128-130)

**Result Communication (Point 7):**
- **Manual chains:** JSON payload with steps + summary (line 3370-3379)
  - Includes: total, completed, successful, stopped_early
  - Adds hints for failures (line 3381-3388)
  - Max 2 follow-up turns (vs 5 for single tools)
- **Auto-chains:** Plain text with both results (line 3998-4029)
  - Initial tool result
  - Chained tool result with [AUTO-CHAIN] marker
  - Combined into single model callback

**Issues:**
- No config setting for disabling auto-chains (hardcoded logic)
- Auto-chain only triggers on first result (doesn't iterate)
- Manual chains and auto-chains use different result formats

---

## IN PROGRESS: Point 8 (Confirmation Gates)

Investigating risk-based confirmation system.

---

## PENDING: Points 9-15

- Point 9: Schema vs Implementation Match
- Point 10: Tool Timing & Budgets
- Point 11: Tool Error Handling & Retry
- Point 12: Multiple Tool Detection Conflicts
- Point 13: Result Formatting Consistency
- Point 14: System Prompt vs Reality
- Point 15: Validator Integration

## LIVE ISSUES OBSERVED

**Issue: Model hallucinating non-existent tools**
- Test: "find read2.txt and describe animal inside"
- Model correctly used grep_search (wrong tool for task, but exists)
- Empty result returned
- Model then called `parse_tool_result` - DOES NOT EXIST
- Indicates system prompt or conversation context suggesting tools that aren't real
