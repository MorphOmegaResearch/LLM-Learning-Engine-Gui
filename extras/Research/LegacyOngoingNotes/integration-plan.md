# Training Pipeline Integration Plan
*2025-09-16 18:57 - Claude Code*

## Current Status
- ✅ **Codex completed:** Orchestrator core, launcher, evaluation harness
- ✅ **Claude completed:** Vector index, training pipeline, RAG tools, validation
- 🔄 **Next:** Wire training pipeline into orchestrator core

## Integration Tasks

### Phase 1: Connect Training to Orchestrator Core (Claude)
1. **Integrate with shared orchestrator config**
   - Connect vector_index.py to orchestrator's central JSON config
   - Hook training_pipeline.py into orchestrator's memory system
   - Wire rag_tools.py with orchestrator's tool registry

2. **Connect to evaluation harness**
   - Test training pipeline with Codex's evaluation harness at `tools/evaluate.py`
   - Ensure <5GB memory constraint is measured and enforced
   - Validate complex prompt handling

3. **Update orchestrator modules**
   - Integrate RAG wrapper with conversation_loop.py and agent_flow.py
   - Connect vector index search to orchestrator's memory store
   - Hook training data collection to orchestrator logging

### Phase 2: Joint Testing & Validation (Both)
4. **Run integrated evaluation**
   - Execute `python3 tools/evaluate.py` with training pipeline active
   - Measure memory usage with training components loaded
   - Test complex conversation flows with RAG enhancement

5. **Performance optimization**
   - Tune batch sizes and memory settings based on evaluation results
   - Optimize vector search performance within orchestrator context
   - Balance training frequency vs performance impact

### Phase 3: Documentation & Polish (Both)
6. **Update documentation**
   - Document training pipeline integration in orchestrator docs
   - Update desktop launcher configurations
   - Create user guides for training features

7. **Final validation**
   - Confirm all desktop launchers work with integrated system
   - Validate <5GB constraint maintained across all features
   - Test complete workflow: logging → vector index → training → RAG → evaluation

## File Integration Map

### Codex Files (to integrate with):
- `orchestrator/launcher.py` - Main orchestrator launcher
- `conversation_loop.py` - Main conversation handler
- `agent_flow.py` - Agent workflow management
- `tools/evaluate.py` - Evaluation harness
- Central JSON config system

### Claude Files (to be integrated):
- `vector_index.py` → Connect to orchestrator memory/logging
- `training_pipeline.py` → Connect to orchestrator config/memory
- `rag_tools.py` → Connect to orchestrator tool registry
- `validate_training.py` → Connect to evaluation harness

## Next Immediate Actions

### For Claude (Priority 1):
1. Examine Codex's orchestrator structure
2. Integrate vector_index with central config system
3. Connect training pipeline to orchestrator memory
4. Test with evaluation harness

### For Codex (When Ready):
1. Review integration points in conversation_loop.py
2. Test orchestrator performance with training components
3. Validate launcher functionality with integrated system
4. Update documentation as needed

## Success Criteria
- [ ] Training pipeline runs within orchestrator framework
- [ ] RAG enhancement works in conversation flows
- [ ] Evaluation harness confirms <5GB memory usage
- [ ] Desktop launchers work with integrated system
- [ ] Complex prompts handled effectively with RAG context

---
*Next update: After examining orchestrator structure*