# Legacy OpenCode v1.2 - Component Exploration

## 🔍 Overview

Exploration of the legacy custom-open-code v1.2 build to identify advanced systems, parsers, translators, and optimizers for integration into the new Custom Code tab's "Adv-Settings" sub-sub-tab.

**Location:** `/home/commander/Desktop/Trainer/Data/tabs/custom_code_tab/site-packages/opencode/`

---

## 📦 **Discovered Components**

### **Category 1: Format Translators & Parsers** 🔄

#### **1. FormatTranslator** (`format_translator.py` - 18KB)
**Purpose:** Converts various tool calling formats to OpenCode's standard JSON format

**Features:**
- **Python Function Call Translation** - Converts `tool_name(arg="value")` to JSON
- **Markdown Emphasis Format** - Handles `**tool_name**` formats
- **Gemma Tools Format** - Specialized Gemma model format
- **Simple Function Format** - Basic function call detection
- **JSON Format Validation** - Ensures correct structure
- **Parameter Normalization** - Auto-corrects common parameter name mistakes (e.g., `path` → `file_path`)

**Key Methods:**
```python
FormatTranslator.translate(response: str) -> Dict
  - _try_json_format()
  - _try_markdown_emphasis_format()
  - _try_python_function_format()
  - _try_gemma_tools_format()
  - _try_simple_function_format()
  - _normalize_parameters()
```

**Settings Potential:**
- ✅ Enable/Disable format types individually
- ✅ Toggle parameter normalization
- ✅ Configure known tool aliases
- ✅ Custom format pattern matching

---

#### **2. JSON Fixer** (`json_fixer.py` - 20KB)
**Purpose:** Intelligently repairs malformed/incomplete JSON from model outputs

**Features:**
- **Smart JSON Parsing** - Handles incomplete JSON gracefully
- **Partial JSON Recovery** - Extracts valid JSON from fragments
- **Streaming JSON Support** - Works with partial responses
- **Error Recovery** - Multiple repair strategies
- **Validation** - Ensures repaired JSON is valid

**Key Methods:**
```python
smart_json_parse(text: str) -> Dict
parse_partial_json(text: str) -> Dict
```

**Settings Potential:**
- ✅ Enable/Disable auto-repair
- ✅ Repair aggressiveness level
- ✅ Validation strictness

---

#### **3. Tool Schema Validators** (`tool_schema_validator.py`, `tool_schema_validator_v2.py`)
**Purpose:** Validates tool calls against schemas before execution

**Settings Potential:**
- ✅ Enable/Disable validation
- ✅ Strict vs permissive mode
- ✅ Auto-correction of minor errors

---

### **Category 2: Tool Orchestration & Intelligence** 🎯

#### **4. AdvancedToolOrchestrator** (`tool_orchestrator.py` - 45KB)
**Purpose:** Intelligent tool chain planning, risk assessment, and confirmation gates

**Major Features:**

**A. Risk Assessment System:**
- **5 Risk Levels:** SAFE, LOW, MEDIUM, HIGH, CRITICAL
- **Dynamic Risk Scoring** - Analyzes command content (e.g., `rm -rf` = CRITICAL)
- **Risk Profiles per Tool** - Pre-configured risk levels for all 20+ tools
- **Risk Score Calculation** - Weights multiple factors

**B. Confirmation Gates:**
- **4 Gate Types:** NONE, IMPLICIT, EXPLICIT, MANDATORY
- **Context-Aware** - Adjusts based on user intent
- **Chain-Level Confirmation** - Approve entire operation chains
- **Interactive Prompts** - Rich console confirmations with details

**C. Tool Chaining:**
- **Dependency Detection** - Identifies tool dependencies
- **Parallel Execution** - Runs independent tools concurrently
- **Sequential Ordering** - Ensures proper execution order
- **Rollback Strategies** - Undo operations if chain fails

**D. Resource Management:**
- **Time Budgets** - Allocates time per tool
- **Resource Profiling** - CPU/memory constraints
- **Estimated Execution Time** - Predicts tool runtime
- **Time Slicing Integration** - Works with TimeSlicedGenerator

**E. Operation Tracking:**
- **History Logging** - All operations recorded
- **Chain Monitoring** - Active chain status
- **Success/Failure Metrics** - Performance tracking

**Key Classes:**
```python
ToolRiskLevel(Enum)
ConfirmationGate(Enum)
ToolOperation(dataclass)
ToolChain(dataclass)
OrchestrationResult(dataclass)
AdvancedToolOrchestrator
```

**Settings Potential:**
- ✅ Enable/Disable orchestration
- ✅ Risk level thresholds
- ✅ Confirmation gate override
- ✅ Parallel execution toggle
- ✅ Rollback enable/disable
- ✅ Resource constraints (CPU threads, memory %)
- ✅ Time budget limits
- ✅ Operation history size

---

#### **5. Router** (`router.py` - 25KB)
**Purpose:** Intent detection and intelligent tool selection

**Features:**
- **Intent Classification** - Determines user goal
- **Tool Recommendation** - Suggests best tools for task
- **Multi-Tool Workflows** - Detects when multiple tools needed
- **Context-Aware Routing** - Uses conversation history

**Settings Potential:**
- ✅ Enable/Disable routing
- ✅ Confidence threshold
- ✅ Multi-tool detection sensitivity

---

### **Category 3: RAG & Context Optimization** 🧠

#### **6. ContextScorer** (`context_scorer.py` - 35KB)
**Purpose:** Adaptive context scoring for RAG optimization on consumer hardware

**Features:**

**A. C3R-L Methodology:**
- **Context Compression** - Reduces redundancy
- **Relevance Ranking** - Scores context importance
- **Resource-Aware** - Adapts to hardware limits

**B. Hardware Detection:**
- **System Memory Detection** - Auto-detects RAM
- **GPU Memory Detection** - NVIDIA/AMD support
- **Dynamic Weight Calculation** - Adjusts based on hardware

**C. Scoring Signals:**
- **Pattern Matching** - JSON structure detection
- **Duplicate Detection** - Removes redundant context
- **Complexity Analysis** - Identifies complex queries
- **Resource Requirement Prediction** - Estimates needs

**D. Adaptive Optimization:**
- **Memory Threshold Monitoring** - 85% RAM triggers optimization
- **Context History Buffer** - 1000-item deque
- **Model Response Cache** - Lightweight caching

**Key Classes:**
```python
ContextScore(dataclass)
ScoringSignal(dataclass)
AdaptiveContextScorer
```

**Settings Potential:**
- ✅ Enable/Disable context scoring
- ✅ Memory threshold (%)
- ✅ History buffer size
- ✅ Cache enable/disable
- ✅ Scoring weight adjustments
- ✅ Pattern detection toggles

---

#### **7. PreRAGOptimizer** (`pre_rag_optimizer.py` - 28KB)
**Purpose:** Advanced pre-RAG optimization with EdgeInfinite-inspired techniques

**Features:**

**A. Optimization Types:**
1. **Context Compression** - Reduces token count while preserving meaning
2. **Semantic Chunking** - Splits content into coherent chunks
3. **Query Enhancement** - Improves search queries
4. **Relevance Filtering** - Removes irrelevant content
5. **Prompt Optimization** - Optimizes prompt structure

**B. Content Type Support:**
- CODE - Function/class extraction, import optimization
- DOCUMENTATION - Section prioritization
- CONVERSATION - User/assistant separation
- SYSTEM_OUTPUT - Error/log parsing
- USER_QUERY - Intent extraction

**C. Pattern Libraries:**
- **Code Patterns:** Function definitions, imports, comments, docstrings, error handling
- **Conversation Patterns:** User queries, assistant responses, tool calls, system messages
- **Importance Indicators:** HIGH (errors, warnings), MEDIUM (functions, classes), LOW (examples, tests)

**D. Advanced Features:**
- **Semantic Coherence Scoring** (35% weight)
- **Information Density Analysis** (25% weight)
- **Context Relevance Evaluation** (20% weight)
- **Token Efficiency Optimization** (20% weight)
- **LRU Cache** - 256 items, 30-minute TTL

**Key Classes:**
```python
OptimizationType(Enum)
ContentType(Enum)
OptimizationResult(dataclass)
SemanticChunk(dataclass)
PreRAGOptimizer
```

**Settings Potential:**
- ✅ Enable/Disable per optimization type
- ✅ Compression ratio target
- ✅ Chunk size limits
- ✅ Weight adjustments (semantic, density, relevance, efficiency)
- ✅ Cache settings (size, TTL)
- ✅ Content type priorities

---

#### **8. RAG Feedback Engine** (`rag_feedback_engine.py` - 23KB)
**Purpose:** Feedback loop for RAG system improvement

**Settings Potential:**
- ✅ Enable/Disable feedback collection
- ✅ Feedback aggregation frequency
- ✅ Auto-adjustment toggles

---

### **Category 4: Resource & Performance Management** ⚡

#### **9. Runtime Profiles** (`runtime_profiles.py` - 10KB)
**Purpose:** Smart resource allocation for constrained hardware

**Features:**

**4 Resource Levels:**
1. **MINIMAL (25%)** - Ultra-conservative
   - 1 thread, 3072 tokens, 20% memory
   - For 2GB+ RAM, 2+ cores

2. **BALANCED (50%)** - Typical hardware
   - Half CPU cores, 5120 tokens, 40% memory
   - For 4GB+ RAM, 4+ cores

3. **AGGRESSIVE (75%)** - High utilization
   - Most CPU cores, 8192 tokens, 60% memory
   - For 8GB+ RAM, 6+ cores

4. **MAXIMUM (100%)** - Full resources
   - All CPU cores, 16384 tokens, 80% memory
   - For 16GB+ RAM, 8+ cores

**Hardware Detection:**
- CPU core count (logical + physical)
- Total memory (GB)
- Available memory (GB)

**Key Classes:**
```python
ResourceLevel(Enum)
ResourceProfile(dataclass)
ResourceProfileManager
```

**Settings Potential:**
- ✅ Select resource level (dropdown)
- ✅ Override specific parameters (threads, memory, tokens)
- ✅ Auto-detection toggle
- ✅ Custom profiles

---

#### **10. TimeSlicedGenerator** (`time_slicer.py` - 8KB)
**Purpose:** Time-budgeted generation for responsive UIs

**Features:**
- **Slice-Based Generation** - Generate tokens in chunks
- **Sleep Between Slices** - Prevents UI freezing
- **Time Budget Management** - Allocates time per operation
- **Resource Profile Integration** - Uses runtime_profiles

**Settings Potential:**
- ✅ Enable/Disable time slicing
- ✅ Slice size (tokens per slice)
- ✅ Sleep duration (ms)
- ✅ Total time budget

---

#### **11. Quant Manager** (`quant_manager.py` - 7KB)
**Purpose:** Dynamic quantization management for model optimization

**Settings Potential:**
- ✅ Quantization level selection
- ✅ Auto-quantization based on hardware

---

### **Category 5: Quality & Verification Systems** ✅

#### **12. Verification Engine** (`verification_engine.py` - 16KB)
**Purpose:** Output validation and quality assurance

**Features:**
- **Syntax Verification** - Checks code syntax
- **Logic Validation** - Detects logical errors
- **Format Checking** - Ensures proper formatting
- **Test Execution** - Runs verification tests

**Settings Potential:**
- ✅ Enable/Disable verification
- ✅ Verification strictness
- ✅ Auto-fix minor issues
- ✅ Test execution toggle

---

#### **13. Quality Systems** (Multiple files)
- **master_quality_system.py** (21KB)
- **quality_integration.py** (13KB)
- **quality_recovery_engine.py** (23KB)

**Purpose:** Multi-layered quality assurance

**Settings Potential:**
- ✅ Quality threshold levels
- ✅ Auto-recovery enable/disable
- ✅ Integration with other systems

---

### **Category 6: Workflow & Project Management** 📋

#### **14. Adaptive Workflow Engine** (`adaptive_workflow_engine.py` - 23KB)
**Purpose:** Intelligent workflow adaptation

**Settings Potential:**
- ✅ Workflow templates
- ✅ Adaptation sensitivity

---

#### **15. Agentic Project System** (`agentic_project_system.py` - 36KB)
**Purpose:** Multi-agent project coordination

**Settings Potential:**
- ✅ Agent count
- ✅ Coordination strategies

---

#### **16. Session Manager** (`session_manager.py` - 23KB)
**Purpose:** Session state and history management

**Settings Potential:**
- ✅ Session persistence
- ✅ History limits

---

### **Category 7: Advanced Tools & Utilities** 🛠️

#### **17. Complexity Analyzer** (`complexity_analyzer.py` - 14KB)
**Purpose:** Code complexity analysis

#### **18. Model Optimizer** (`model_optimizer.py` - 24KB)
**Purpose:** Model performance optimization

#### **19. Performance Benchmark System** (`performance_benchmark_system.py` - 36KB)
**Purpose:** Performance measurement and analysis

#### **20. Hardening Manager** (`hardening_manager.py` - 19KB)
**Purpose:** Security hardening for operations

---

## 🎯 **Recommended Integration Priority**

### **Phase 1: Essential Parsers & Translators** (Immediate Value)
1. ✅ **FormatTranslator** - Handle multiple model output formats
2. ✅ **JSON Fixer** - Repair broken JSON from models
3. ✅ **Tool Schema Validator** - Ensure valid tool calls

**Settings to Add:**
```json
{
  "format_translation": {
    "enabled": true,
    "formats": {
      "python_function": true,
      "markdown_emphasis": true,
      "gemma_tools": true,
      "simple_function": true
    },
    "normalize_parameters": true,
    "tool_aliases": {}
  },
  "json_repair": {
    "enabled": true,
    "aggressiveness": "medium",
    "validation": "strict"
  },
  "schema_validation": {
    "enabled": true,
    "mode": "permissive"
  }
}
```

---

### **Phase 2: Tool Intelligence** (High Impact)
1. ✅ **AdvancedToolOrchestrator** - Risk assessment, confirmation gates, chaining
2. ✅ **Router** - Intent detection and tool recommendation

**Settings to Add:**
```json
{
  "tool_orchestrator": {
    "enabled": false,
    "risk_assessment": true,
    "confirmation_gates": {
      "safe": "none",
      "low": "implicit",
      "medium": "explicit",
      "high": "explicit",
      "critical": "mandatory"
    },
    "parallel_execution": true,
    "rollback_enabled": true,
    "operation_history_size": 100
  },
  "intelligent_routing": {
    "enabled": false,
    "confidence_threshold": 0.7,
    "multi_tool_detection": true
  }
}
```

---

### **Phase 3: Resource Management** (Performance)
1. ✅ **Runtime Profiles** - Smart resource allocation
2. ✅ **TimeSlicedGenerator** - Responsive generation
3. ✅ **Quant Manager** - Model optimization

**Settings to Add:**
```json
{
  "resource_management": {
    "profile": "balanced",
    "custom_overrides": {
      "num_threads": null,
      "max_tokens": null,
      "memory_limit_mb": null
    },
    "auto_detect": true
  },
  "time_slicing": {
    "enabled": false,
    "tokens_per_slice": 32,
    "sleep_ms": 30,
    "total_budget_seconds": 300
  }
}
```

---

### **Phase 4: Context & RAG Optimization** (Advanced)
1. ✅ **ContextScorer** - Adaptive context scoring
2. ✅ **PreRAGOptimizer** - Advanced pre-RAG optimization
3. ✅ **RAG Feedback Engine** - Continuous improvement

**Settings to Add:**
```json
{
  "context_scoring": {
    "enabled": false,
    "memory_threshold_percent": 85,
    "history_buffer_size": 1000,
    "cache_enabled": true,
    "weights": {
      "semantic_coherence": 0.35,
      "information_density": 0.25,
      "context_relevance": 0.20,
      "token_efficiency": 0.20
    }
  },
  "pre_rag_optimizer": {
    "enabled": false,
    "optimizations": {
      "context_compression": true,
      "semantic_chunking": true,
      "query_enhancement": true,
      "relevance_filtering": true,
      "prompt_optimization": true
    },
    "compression_ratio_target": 0.7,
    "cache_ttl_seconds": 1800
  }
}
```

---

### **Phase 5: Quality & Verification** (Optional)
1. ✅ **Verification Engine** - Output validation
2. ✅ **Quality Systems** - Multi-layer QA

**Settings to Add:**
```json
{
  "verification": {
    "enabled": false,
    "strictness": "medium",
    "auto_fix": true,
    "run_tests": false
  },
  "quality_assurance": {
    "enabled": false,
    "threshold": 0.8,
    "auto_recovery": true
  }
}
```

---

## 📋 **Proposed Settings Structure**

### **Adv-Settings Sub-Sub-Tab Organization:**

```
Custom Code → Chat → Settings (sub-tab) → Adv-Settings (sub-sub-tab)

┌─────────────────────────────────────────────────────┐
│ 🔄 Format Translation & Parsing                     │
│   ☑ Enable Format Translator                        │
│   ☑ Python Function Format                          │
│   ☑ Markdown Emphasis Format                        │
│   ☑ Gemma Tools Format                              │
│   ☑ Normalize Parameters                            │
│   ☑ Enable JSON Auto-Repair [Aggressiveness: ▼]    │
│   ☑ Schema Validation [Mode: Permissive ▼]         │
├─────────────────────────────────────────────────────┤
│ 🎯 Tool Intelligence                                │
│   ☐ Enable Tool Orchestrator                        │
│     ☑ Risk Assessment                               │
│     ☑ Confirmation Gates                            │
│     ☑ Parallel Execution                            │
│     ☑ Rollback on Failure                           │
│   ☐ Enable Intelligent Routing                      │
│     Confidence Threshold: [0.7  ]                   │
├─────────────────────────────────────────────────────┤
│ ⚡ Resource Management                              │
│   Resource Profile: [Balanced ▼]                    │
│   ☑ Auto-Detect Hardware                            │
│   ☐ Enable Time Slicing                             │
│     Tokens per Slice: [32   ]                       │
│     Sleep (ms): [30   ]                             │
├─────────────────────────────────────────────────────┤
│ 🧠 Context & RAG Optimization                       │
│   ☐ Enable Context Scorer                           │
│   ☐ Enable Pre-RAG Optimizer                        │
│     ☑ Context Compression                           │
│     ☑ Semantic Chunking                             │
│     ☑ Query Enhancement                             │
│     ☑ Relevance Filtering                           │
│     ☑ Prompt Optimization                           │
├─────────────────────────────────────────────────────┤
│ ✅ Quality & Verification                           │
│   ☐ Enable Verification Engine                      │
│   ☐ Enable Quality Assurance                        │
└─────────────────────────────────────────────────────┘
```

---

## 🔑 **Key Insights**

### **What We Have:**
1. **20+ Advanced Systems** ready for integration
2. **Mature, Production-Ready Code** from v1.2
3. **Well-Documented Components** with clear interfaces
4. **Modular Architecture** - Easy to enable/disable individually
5. **Hardware-Aware** - Adapts to available resources

### **Integration Complexity:**
- **Low:** Format Translator, JSON Fixer, Schema Validator
- **Medium:** Tool Orchestrator, Router, Runtime Profiles
- **High:** Context Scorer, PreRAG Optimizer, RAG Systems

### **Recommended Approach:**
1. Start with **Phase 1** (Parsers/Translators) - Immediate value, low complexity
2. Add **Phase 2** (Tool Intelligence) - High impact for tool calling
3. Implement **Phase 3** (Resource Management) - Performance boost
4. Optionally add **Phase 4 & 5** - Advanced users only

---

## 📊 **Summary**

**Total Components Discovered:** 20+ systems
**Ready for Integration:** All (with varying complexity)
**Estimated Settings Count:** 50+ configurable options
**Storage:** All in `/Data/tabs/custom_code_tab/site-packages/opencode/`

**Next Steps:**
1. ✅ Confirm which phases to implement
2. ✅ Design Adv-Settings UI layout
3. ✅ Create settings schema
4. ✅ Implement integration layer
5. ✅ Add enable/disable toggles
6. ✅ Test with real models

---

**Ready to proceed?** Let me know which phases you'd like to start with!
