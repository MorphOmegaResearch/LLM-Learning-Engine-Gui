# "0" Save States Usage Guide
**Updated:** 2025-09-16

## **IMPLEMENTED: Option A - Simple Save States with Rollback**

### **How It Works**
- **Auto-save:** Every conversation turn saves to "current"
- **Manual save:** Create named save points for testing
- **Rollback:** Load any previous save state instantly
- **Backup:** Auto-backup every 10 turns

### **Commands**
```
save <name>     - Save current state with custom name
load <name>     - Load saved state by name
states          - List all available save states
status          - Show current session info
clear           - Reset current conversation context
```

### **Workflow for Adverse Testing**
1. **Before risky changes:**
   ```
   save pre_routing_test
   ```

2. **Test new feature:**
   - Make changes, test functionality
   - If something breaks...

3. **Rollback instantly:**
   ```
   load pre_routing_test
   ```
   - All conversation history restored
   - Context preserved
   - Back to known good state

### **Auto-Save Behavior**
- **Current session:** Auto-saved after every response
- **Backup states:** Created every 10 conversation turns
- **File location:** `/home/commander/crewai-orchestrator/save_states/`

### **Save State Contents**
Each save state includes:
- Complete conversation history
- Context settings (limit, model config)
- Session metadata (timestamps, turn count)
- Model connection info

### **Example Usage**
```
# Start conversation
python3 working_conversation_ai.py

# Have some conversation...
0: Hello! How can I help?

# Save before testing
save stable_v1

# Test new features...
# If something breaks:
load stable_v1

# Back to working state!
```

### **File Structure**
```
save_states/
├── current.json                    # Auto-saved current session
├── stable_v1.json                 # Manual save point
├── pre_routing_test.json           # Before testing routing
├── backup_10_turns.json            # Auto-backup at 10 turns
└── backup_20_turns.json            # Auto-backup at 20 turns
```

### **Status Information**
- `current_session`: Active save state name
- `save_states_available`: Number of available saves
- `conversation_turns`: Current session length

## **Future: Version Branches (Option C)**
When ready for more complex development:
- Stable → Testing → Development branches
- Copy stable to testing before changes
- Save states within each version
- Promote testing to stable when verified

**Current Status:** Option A implemented and ready for adverse testing!