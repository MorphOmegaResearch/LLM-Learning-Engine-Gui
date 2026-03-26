# BERT + Chat Integration Design
**Intelligent Action Routing with Multi-Provider Chat**

---

## Current Architecture

### Components Already In Place

1. **grep_flight Chat Tab** (grep_flight_v2.py:1314-1535)
   - Input line ✅
   - Send button ✅
   - Model selector dropdown ✅
   - Session switcher (Plan/Task) ✅
   - Tool checkboxes (Grep/Read/Write) ✅
   - Messages display area ✅

2. **ChatBackend** (chat_backend.py)
   - Multi-provider support ✅
   - Ollama (Qwen, DeepSeek, Llama) ✅
   - Claude API (Sonnet, Opus, Haiku) ✅
   - Session management ✅
   - Context building ✅

3. **BERT System** (berts/bert2.py)
   - distillbart semantic routing
   - Qwen chat integration
   - Intent classification
   - BERT profile definitions (.json files)

4. **Target Context System** (target_context_system.py)
   - Action registry
   - Target type resolution
   - Compatibility checking

5. **Onboard Prober** (onboard_prober.py)
   - Script profiling
   - AST analysis
   - Capability detection

---

## Integration Vision

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INPUT                               │
│           (Chat Tab or Target Selection)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │   OPTIONAL: BERT Router     │  ← Initialization Toggle
       │   (distillbart classifier)  │     (Default: OFF)
       │   - Intent recognition      │
       │   - Action suggestions      │
       └─────────────┬───────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │   Target Context Resolver   │
       │   - File/folder type        │
       │   - Current grep_flight     │
       │     state                   │
       │   - Available actions       │
       └─────────────┬───────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │    Provider Router          │
       │    (Fallback Chain)         │
       │                             │
       │    1. Claude API            │ ← If ANTHROPIC_API_KEY set
       │       (if credits)          │
       │                             │
       │    2. Qwen via Ollama       │ ← Local fallback
       │       (local, free)         │
       │                             │
       │    3. distillbart only      │ ← Classification only
       │       (no generation)       │
       └─────────────┬───────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │   Action Executor           │
       │   - Profiled tools          │
       │   - grep_flight actions     │
       │   - Custom scripts          │
       └─────────────┬───────────────┘
                     │
                     ▼
       ┌─────────────────────────────┐
       │   Traceback UI              │
       │   - All outputs             │
       │   - Classification results  │
       │   - Chat responses          │
       │   - Action results          │
       └─────────────────────────────┘
```

---

## Key Design Principles

### 1. Additive, Non-Breaking
- **BERT routing is OPTIONAL** - toggle on/off
- Existing chat flow works unchanged
- No dependencies forced on users
- Graceful degradation everywhere

### 2. Provider Fallback Chain
```python
if claude_available and has_credits:
    use_claude_api()
elif qwen_ollama_available:
    use_qwen_local()
elif distillbart_available:
    classify_only_no_generation()
else:
    basic_keyword_routing()
```

### 3. Smart Context Injection
- Profiled tool outputs → Chat context
- Target type → Provider hints
- grep_flight state → Action suggestions
- Recent actions → Conversation history

### 4. Unified Output Routing
**Everything goes to Traceback UI:**
- Chat responses
- BERT classifications
- Action results
- Errors and warnings

---

## Data Flow Examples

### Example 1: File Syntax Check (No BERT)

```
User: Sets target.sh on "brain.py"
↓
Target Context Resolver:
  - type: file
  - is_python: true
  - default_action: "Syntax Check"
↓
Action Executor:
  - Runs: python3 -m py_compile brain.py
↓
Traceback UI:
  "✅ Syntax check passed: brain.py"
```

### Example 2: Chat with Claude (BERT enabled)

```
User (Chat): "analyze this python file for bugs"
↓
BERT Router (distillbart):
  - Intent: "debug_analysis"
  - Confidence: 0.87
  - Suggested BERT: "debug_bert"
↓
Target Context:
  - Current target: brain.py
  - Type: file, Python
  - Available: syntax_check, lint, analyze
↓
Provider Router:
  - Check ANTHROPIC_API_KEY: ✅
  - Use: Claude Sonnet 4.5
↓
ChatBackend:
  - Context: {target: brain.py, intent: debug, tools: [Read]}
  - Send to Claude with tools
↓
Claude Response: "I'll analyze brain.py for bugs..."
  → Reads file
  → Finds 3 potential issues
  → Returns analysis
↓
Traceback UI:
  "[BERT] debug_bert (confidence: 0.87)"
  "[Claude] Analysis complete:"
  "  - Issue 1: Unhandled exception at line 42"
  "  - Issue 2: Unused variable at line 67"
  "  - Issue 3: Potential race condition at line 103"
```

### Example 3: Local Fallback (No internet)

```
User (Chat): "what functions are in this file?"
↓
BERT Router:
  - Intent: "code_analysis"
  - Suggested: "code_bert"
↓
Provider Router:
  - Check Claude: ❌ (no internet)
  - Check Qwen: ✅ (ollama running locally)
  - Use: qwen2.5-coder:3b
↓
Qwen (local):
  - Context: {target: brain.py, tools: [Read]}
  - Reads file via tool
  - Returns function list
↓
Traceback UI:
  "[Local] qwen2.5-coder:3b"
  "Functions found in brain.py:"
  "  - __init__(self)"
  "  - process_data(self, input)"
  "  - save_results(self, output_path)"
```

---

## Implementation Components

### 1. grep_flight_bert.json Profile

```json
{
  "bert_id": "grep_flight_bert",
  "name": "Grep Flight Orchestrator",
  "description": "Routes grep_flight actions with context awareness",
  "intents": [
    "file_operation",
    "search_operation",
    "chat_query",
    "debug_request",
    "analysis_request",
    "action_execution"
  ],
  "keywords": [
    "grep", "search", "find", "target", "file", "folder",
    "analyze", "check", "lint", "format", "run", "execute",
    "debug", "fix", "error", "bug"
  ],
  "data_fields": {
    "target_context": {
      "path": "string",
      "type": "file | folder",
      "is_python": "boolean",
      "available_actions": "array"
    },
    "grep_flight_state": {
      "current_pattern": "string",
      "recent_targets": "array",
      "active_tools": "array"
    },
    "action_history": {
      "last_action": "string",
      "last_result": "string",
      "timestamp": "string"
    }
  },
  "routing": {
    "file_operation": {
      "target_types": ["file"],
      "suggested_actions": ["syntax_check", "lint", "format", "run"],
      "fallback_provider": "qwen"
    },
    "search_operation": {
      "target_types": ["folder", "file"],
      "suggested_actions": ["grep", "find", "analyze"],
      "fallback_provider": "local"
    },
    "chat_query": {
      "target_types": ["any"],
      "suggested_provider": "claude",
      "fallback_provider": "qwen"
    }
  },
  "invoke_command": "bert2.py --profile grep_flight"
}
```

### 2. Enhanced ChatBackend with BERT

```python
# In chat_backend.py

class ChatBackend:
    def __init__(self, ...):
        # ... existing code ...

        # NEW: BERT integration
        self.bert_router = None
        self.bert_enabled = False

    def enable_bert(self, berts_dir: Path):
        """Initialize BERT router (optional)"""
        try:
            from berts.bert2 import SemanticRouter, QwenChat

            # Load grep_flight_bert profile
            profile_path = berts_dir / "grep_flight_bert.json"
            if profile_path.exists():
                self.bert_router = SemanticRouter()
                self.bert_enabled = True
                print("[ChatBackend] BERT routing enabled")
        except Exception as e:
            print(f"[ChatBackend] BERT not available: {e}")
            self.bert_enabled = False

    def send_message(self, message: str, model: str = None, context: Dict = None):
        """Send message with optional BERT preprocessing"""

        # OPTIONAL: BERT classification
        bert_result = None
        if self.bert_enabled and self.bert_router:
            bert_result = self._classify_with_bert(message, context)

            # Enhance context with BERT insights
            if bert_result and bert_result['confidence'] > 0.7:
                context = context or {}
                context['bert_intent'] = bert_result['intent']
                context['bert_confidence'] = bert_result['confidence']
                context['suggested_actions'] = bert_result.get('suggested_actions', [])

        # Provider selection with fallback
        provider, model = self._select_provider(model, context)

        if provider == "claude":
            self._send_claude(message, model, context, bert_result)
        elif provider == "ollama":
            self._send_ollama(message, model, context, bert_result)
        else:
            # Classification only
            if bert_result:
                self._return_bert_classification(bert_result)
            else:
                self.on_error("No providers available")

    def _classify_with_bert(self, message: str, context: Dict) -> Dict:
        """Classify message intent with distillbart"""
        # Load available BERTs
        # Run semantic routing
        # Return classification result
        pass

    def _select_provider(self, requested_model: str, context: Dict) -> tuple:
        """Select best available provider"""
        # Check if Claude requested and available
        if requested_model in CLAUDE_MODELS and self.anthropic_client:
            return ("claude", requested_model)

        # Check if Ollama model requested
        if self.ollama_client and requested_model:
            available = self.get_available_models()
            if requested_model in available:
                return ("ollama", requested_model)

        # Fallback based on BERT suggestion
        if context and context.get('bert_intent'):
            intent = context['bert_intent']
            # Use routing rules from grep_flight_bert.json
            # ...

        # Default fallback
        if self.ollama_client:
            return ("ollama", "qwen2.5-coder:3b")

        return (None, None)
```

### 3. Enhanced Chat Tab UI

```python
# Add to _create_chat_tab()

# Provider selector (instead of just model)
provider_frame = tk.Frame(chat_header, bg=self.config.BG_COLOR)
provider_frame.pack(side=tk.RIGHT, padx=10)

tk.Label(provider_frame, text="Provider:", ...).pack(side=tk.LEFT)

self.chat_provider = tk.StringVar(value="Auto")
provider_menu = ttk.Combobox(provider_frame,
                            textvariable=self.chat_provider,
                            values=["Auto", "Claude API", "Qwen Local", "BERT Only"],
                            width=15, state='readonly')
provider_menu.pack(side=tk.LEFT, padx=5)

# BERT toggle
self.bert_enabled = tk.BooleanVar(value=False)
bert_toggle = tk.Checkbutton(chat_header,
                            text="🧠 BERT",
                            variable=self.bert_enabled,
                            bg=self.config.BG_COLOR,
                            fg=self.config.FG_COLOR,
                            selectcolor=self.config.BG_COLOR,
                            activebackground=self.config.BG_COLOR,
                            command=self._toggle_bert)
bert_toggle.pack(side=tk.RIGHT, padx=10)
```

### 4. Unified Traceback Output

```python
# In _send_chat_message()

# Log BERT classification to traceback
if bert_result:
    self._add_traceback(
        f"🧠 BERT Classification:\n"
        f"   Intent: {bert_result['intent']}\n"
        f"   Confidence: {bert_result['confidence']:.2f}\n"
        f"   Suggested: {', '.join(bert_result.get('suggested_actions', []))}",
        "BERT"
    )

# Log provider selection
self._add_traceback(
    f"🔌 Provider: {provider} ({model})",
    "INFO"
)

# Chat response already goes to chat_messages
# But also mirror to traceback for full context
self._add_traceback(
    f"💬 Chat Response:\n{response[:200]}...",
    "CHAT"
)
```

---

## Integration Steps

### Phase 1: Foundation (Non-Breaking)
1. ✅ Target context system already created
2. Add `grep_flight_bert.json` profile
3. Add BERT toggle to chat tab UI (default: OFF)
4. Add provider selector dropdown

### Phase 2: BERT Integration (Optional)
5. Import bert2.py into ChatBackend
6. Add `enable_bert()` method
7. Implement `_classify_with_bert()`
8. Wire up BERT toggle button

### Phase 3: Smart Routing
9. Implement provider fallback chain
10. Connect target context to chat context
11. Add routing rules from BERT profiles
12. Test fallback scenarios (no internet, no Ollama, etc.)

### Phase 4: Output Unification
13. Route all chat outputs to traceback
14. Add BERT classification display
15. Add provider indicators
16. Test complete flow

---

## Usage Examples

### Scenario 1: Developer with Claude Credits
```
[Chat Tab]
Provider: Auto
🧠 BERT: ✅

User: "check this file for security issues"
→ BERT: security_auditor_bert (0.91)
→ Provider: Claude Sonnet 4.5
→ Context: {target: auth.py, tools: [Read, Grep]}
→ Response: Security analysis with 3 findings
```

### Scenario 2: Offline Developer
```
[Chat Tab]
Provider: Qwen Local
🧠 BERT: ✅

User: "what classes are defined here?"
→ BERT: python_analyzer_bert (0.85)
→ Provider: qwen2.5-coder:3b (local)
→ Context: {target: models.py, tools: [Read]}
→ Response: Class structure analysis
```

### Scenario 3: Quick Action (No BERT)
```
[Target] Sets target.sh on file.py
[BERT: OFF]

→ Default Action: Syntax Check
→ Executes immediately
→ Result in traceback
```

---

## Configuration

### User Settings
```json
{
  "chat": {
    "bert_enabled": false,
    "default_provider": "auto",
    "fallback_chain": ["claude", "ollama", "bert_only"],
    "auto_context_injection": true,
    "mirror_to_traceback": true
  },
  "providers": {
    "claude": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-sonnet-4-5-20250929"
    },
    "ollama": {
      "enabled": true,
      "host": "http://localhost:11434",
      "default_model": "qwen2.5-coder:3b"
    }
  },
  "bert": {
    "profiles_dir": "berts/",
    "classification_threshold": 0.6,
    "auto_suggest_actions": true
  }
}
```

---

## Questions Resolved

Q: **"im thinking we can re-route to the users same tools per profile"**
A: ✅ Yes! BERT profiles define which tools are available per intent. grep_flight_bert.json maps intents to tool permissions.

Q: **"if ive got no internet or credits i can have the qwenchat routed"**
A: ✅ Yes! Automatic fallback chain: Claude → Qwen Local → BERT classification only.

Q: **"the grep_flight 'chat' tab ... no send-stop buttons"**
A: ✅ Send button exists (line 1397-1399). Stop button can be added. Already has input line.

Q: **"providers, claude should be there too"**
A: ✅ ChatBackend already supports Claude API (chat_backend.py:23-40). Just need to expose in UI dropdown.

Q: **"route it all to traceback"**
A: ✅ All outputs (chat, BERT, actions) routed to traceback UI via `_add_traceback()`.

Q: **"initialization button/toggle for ... profiling"**
A: ✅ BERT toggle checkbox added to chat UI. Default OFF (non-breaking).

Q: **"the call to distillbart could be changed a little and just be additive"**
A: ✅ BERT classification is optional preprocessing, doesn't replace existing flow.

Q: **"may just need to change profile data fields"**
A: ✅ Profile data fields map to grep_flight context. See `grep_flight_bert.json` design above.

---

## Next Steps

What would you like to work on first?

1. **Create grep_flight_bert.json** - Define the profile
2. **Enhance Chat Tab UI** - Add provider dropdown and BERT toggle
3. **Integrate bert2.py** - Wire up distillbart routing
4. **Test Provider Fallbacks** - Ensure graceful degradation
5. **Document for Users** - How to use BERT + Chat system

Or should we start with a smaller proof-of-concept to test the integration?
