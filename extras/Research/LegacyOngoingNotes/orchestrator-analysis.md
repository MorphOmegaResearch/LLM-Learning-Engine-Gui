# Orchestrator Structure Analysis
*2025-09-16 19:00 - 

## Codex's Orchestrator Architecture

### Core Structure !!LEGACY!!
```
/home/commander/open-interpreter-workspace/
├── orchestrator_config.json         # Central configuration
├── orchestrator/                    # Core package
│   ├── config.py                   # Config dataclasses
│   ├── launcher.py                 # Main launcher
│   ├── memory.py                   # Memory management
│   ├── models.py                   # Model adapters
│   ├── tools.py                    # Tool registry
│   └── logging_utils.py            # Logging system
├── conversation_loop.py            # Main conversation handler
├── agent_flow.py                   # Agent workflow
├── tools/
│   └── evaluate.py                # Evaluation harness
└── context_working/               # Logging directory
```

### Configuration System
- **Central config:** `orchestrator_config.json`
- **Memory limits:** 6 turns max, <5GB constraint
- **Models:** tinyllama-tools, ollama/gemma2-tools, phi3-tools
- **Logging:** ./context_working directory

### Key Integration Points
1. **Config system:** Dataclasses in `orchestrator/config.py`
2. **Memory management:** `orchestrator/memory.py`
3. **Tool registry:** `orchestrator/tools.py`
4. **Logging:** `orchestrator/logging_utils.py` + context_working/
5. **Evaluation:** `tools/evaluate.py` with memory monitoring

## Integration Strategy

### Phase 1: Configuration Integration
- Extend `orchestrator_config.json` with training settings
- Add TrainingConfig dataclass to `orchestrator/config.py`
- Configure vector index and training paths

### Phase 2: Memory/Logging Integration
- Connect vector_index.py to `orchestrator/logging_utils.py`
- Hook into context_working/ directory for log processing
- Integrate with `orchestrator/memory.py` for conversation history

### Phase 3: Tool Integration
- Register RAG tools in `orchestrator/tools.py`
- Hook RAG wrapper into `conversation_loop.py`
- Connect training pipeline to agent workflows

### Phase 4: Evaluation Integration
- Test memory usage with `tools/evaluate.py`
- Validate <5GB constraint with training components
- Measure RAG performance impact

## Next Actions
1. ✅ Analyzed orchestrator structure
2. 🔄 Create configuration extensions
3. 🔄 Integrate vector index with logging system
4. 🔄 Connect RAG tools to conversation loop
5. 🔄 Test with evaluation harness

---
*Ready to begin integration*