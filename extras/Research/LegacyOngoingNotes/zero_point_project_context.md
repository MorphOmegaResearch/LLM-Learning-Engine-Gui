# Zero Point Project Context - OpenCode Orchestrator "0"
**Date:** 2025-09-16
**Context Failures:** 2 major misunderstandings corrected

## PROJECT DEFINITION
**Goal:** Create "0" - an intelligent orchestrator that can chat, plan, and coordinate agent workflows locally

## CONTEXT CORRECTIONS
### Failure #1: Project Confusion
- **Mistake:** Confused OpenCode Custom TUI (working launcher) with Orchestrator UI (frozen build)
- **Reality:** Two separate projects, different capabilities, different status

### Failure #2: Hardware Dismissal
- **Mistake:** Dismissed 1.5GB constraint as "shit hardware" requiring downgrades
- **Reality:** Sophisticated VCM system designed specifically for constrained hardware optimization

## TRUE PROJECT SCOPE
**NOT building:** Enterprise-grade AI system
**IS building:** Local conversational orchestrator that works within hardware limits using VCM optimization

## PHASE 1 REQUIREMENTS ANALYSIS

### ✅ **REQUIREMENT 1: STABLE/COHERENT CHAT WITH LLM IN TUI**
**Current Status:** FAILED - timeouts on basic queries
**What's Missing:**
- Working model inference backend
- VCM system needs actual weight tiling implementation
- Connection between TUI and functional model

### ❌ **REQUIREMENT 2: HOLDS CONTEXT**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Conversation history persistence
- Context window management
- Memory efficient context handling

### ❌ **REQUIREMENT 3: CAN PLAN AND INVESTIGATE COMPLEX PROBLEMS**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Multi-step reasoning capability
- Problem decomposition system
- Investigation workflow framework

### ❌ **REQUIREMENT 4: DECIDE BETWEEN DIRECT RESPONSE vs AGENT WORKFLOW**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Decision logic for routing queries
- Agent workflow integration
- "0" intelligence to determine appropriate response method

### ❌ **REQUIREMENT 5: CONFIRMERS FOR TOOLS/AGENTS**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Confirmation system architecture
- Allow/deny backend settings
- Critical action protection

### ❌ **REQUIREMENT 6: TUI MODEL SETTINGS**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Settings interface for "0" model parameters
- Agent-specific model configuration
- Prompt/temp/etc parameter controls

### ❌ **REQUIREMENT 7: CONFIRMER SETTINGS**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Default confirmation policies
- "0" sends confirmation requests system
- User approval workflow

### ❌ **REQUIREMENT 8: BACKEND RESOURCE CAPS**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- Per-agent resource limits (75% RAM, 50%, etc.)
- Resource allocation transparency
- Adaptive resource management

### ❌ **REQUIREMENT 9: STABLE AGENTIC SAVE STATES**
**Current Status:** NOT IMPLEMENTED
**What's Missing:**
- State serialization system
- Rollback capability
- Local state persistence

## VERIFICATION OF CURRENT "0" CLAIMS

### **CLAIM:** "Third Co-op Member AI ready"
**REALITY:** ❌ Times out on "how are you"

### **CLAIM:** "Conversation AI functional"
**REALITY:** ❌ No working conversation capability

### **CLAIM:** "VCM system implemented"
**REALITY:** ⚠️ Architecture exists, no real inference backend

### **CLAIM:** "Phase 1 underway"
**REALITY:** ❌ 0 of 9 requirements met

## ACTUAL CURRENT STATE
**What Works:**
- Menu TUI system (opencode_command_center.py)
- VCM architecture framework (sophisticated but empty)
- Semantic prompt files exist

**What's Broken:**
- Core conversation capability (timeouts)
- All agent coordination features
- All Phase 1 requirements

## REAL PHASE 1-0 REQUIREMENTS
1. Get basic chat working (no timeouts)
2. Implement VCM with actual model backend
3. Add context persistence
4. Build decision routing (direct vs agent workflow)
5. Create confirmer system
6. Add TUI settings interface
7. Implement resource caps
8. Add save/rollback states
9. Enable complex problem investigation

## PHASE 1-0 PASS CRITERIA
**Minimum Viable "0":**
- Can chat without timeouts ✅
- Maintains conversation context ✅
- Can route to agent workflows when needed ✅
- Asks for confirmations on critical actions ✅
- Has configurable resource limits ✅
- Can save/restore conversation state ✅

**Current Progress:** 0/6 criteria met

## ACTION PLAN
1. Fix basic chat (implement VCM inference backend)
2. Add context management
3. Build routing decision system
4. Implement confirmer framework
5. Add resource management
6. Create state persistence
7. Test with complex problems

**Status:** Project needs fundamental implementation, not just architectural frameworks