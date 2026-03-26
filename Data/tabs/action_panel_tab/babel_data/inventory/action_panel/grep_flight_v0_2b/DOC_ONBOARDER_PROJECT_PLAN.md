# Doc-Onboarder: Documentation Intelligence & Onboarding System
**Project Type:** Side-Quest / Infrastructure
**Priority:** High (Solves fundamental workflow issue)
**Status:** Planning Phase
**Created:** 2026-01-18

---

## 🎯 Problem Statement

### Current Pain Points
1. **Context Loss Between Sessions**
   - Both user and AI start sessions with incomplete project state
   - Manual re-reading of docs required each time
   - Variables, plans, milestones scattered across files
   - No systematic way to verify "what changed since last session"

2. **Documentation Chaos**
   - .md files with unstructured information
   - Verbose language mixed with structured data
   - No clear hooks for automation
   - Manual effort to extract actionable items

3. **Workflow Gaps**
   - Create doc → manually parse → manually create tasks → manually link
   - No automated inference of document purpose
   - No systematic migration from notes → tasks → plans
   - Changes don't automatically trigger reviews

### The Insight
> "Both you and I come in from a space unrelative over many linear aspects compared to this exact project's elements and variables"

**Solution:** Create a systematic onboarding process that:
- Parses documentation for structure
- Queues items for user confirmation
- Infers relationships and purpose
- Tracks changes vs. expected state
- Provides coherent entry point each session

---

## 🏗️ System Architecture

### Core Components

#### 1. Classification Engine
**File:** `classification.json`
**Purpose:** Define parsing rules for document types

```json
{
  "document_types": {
    "plan": {
      "markers": ["## Plan", "### Phase", "- [ ]", "Deliverables:"],
      "required_fields": ["title", "phases", "deliverables"],
      "variable_pattern": "{[A-Z_]+}",
      "indentation": "markdown_standard"
    },
    "milestone": {
      "markers": ["</Milestone_", "<Milestone_", "Status:", "Complete"],
      "required_fields": ["name", "status", "backup_refs"],
      "date_format": "YYYY-MM-DD"
    },
    "task": {
      "markers": ["- [ ]", "TODO:", "TASK:"],
      "priority_indicators": ["URGENT", "HIGH", "MEDIUM", "LOW"],
      "status_pattern": "\\[( |x|>)\\]"
    },
    "note": {
      "markers": ["Note:", "Observation:", "Idea:"],
      "verbosity": "high",
      "requires_parsing": true
    }
  },
  "variable_formats": {
    "path": "/([a-zA-Z0-9/_.-]+)",
    "version": "v[0-9]+\\.[0-9]+\\.[0-9]+",
    "timestamp": "[0-9]{8}_[0-9]{6}",
    "percentage": "[0-9]+%"
  },
  "syntax_rules": {
    "indentation": {
      "list_item": 2,
      "nested_list": 2,
      "code_block": 0
    },
    "headers": {
      "h1": "#",
      "h2": "##",
      "h3": "###"
    }
  }
}
```

#### 2. Hook Detection System
**Purpose:** Extract structured hooks from markdown

**Hook Types:**
```markdown
<!-- PLAN:project_name:phase_1 -->
<!-- MILESTONE:name:status:complete -->
<!-- TASK:title:priority:high -->
<!-- VARIABLE:workspace_dir:/path/to/dir -->
<!-- ASSOCIATION:plan_id:relates_to -->
<!-- INFERENCE_NEEDED:parse_failed:verbose_section -->
```

**Auto-Detection Patterns:**
- `## Phase N:` → Plan phase marker
- `</Milestone_N>:` → Milestone marker
- `- [ ] Task name` → Task checkbox
- `**Status:** Complete` → Status field
- Code blocks with paths → Variable extraction
- Bullet lists mentioning plan variables → Association check

#### 3. Parser Engine
**Module:** `doc_parser.py`

**Responsibilities:**
1. **Scan Documentation**
   ```python
   def scan_document(doc_path: Path) -> ParsedDocument:
       - Read .md file
       - Identify document type via classification rules
       - Extract hooks (explicit and inferred)
       - Parse structured sections
       - Flag unparsable sections
   ```

2. **Variable Extraction**
   ```python
   def extract_variables(content: str, var_format: str) -> List[Variable]:
       - Match against variable_formats from classification.json
       - Track variable occurrences
       - Build variable → document mapping
       - Flag undefined variables
   ```

3. **Verbose Language Parsing**
   ```python
   def parse_verbose_section(text: str) -> StructuredData:
       - Attempt to identify sections (problem, solution, steps)
       - Extract actionable items
       - Suggest structured format
       - Flag for user review if confidence < threshold
   ```

4. **Association Inference**
   ```python
   def infer_associations(doc: ParsedDocument, plan_db: PlanDatabase) -> List[Association]:
       - Check if doc mentions variables from existing plans
       - Calculate relevance score
       - Suggest association type (note, task, sub-plan, idea)
       - Queue for user confirmation
   ```

#### 4. Onboarding Queue UI
**Location:** grep_flight [Inventory] → [Onboarding] sub-tab

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ 📚 DOCUMENTATION ONBOARDING                             │
├─────────────────────────────────────────────────────────┤
│ Pending Review: 5 items                                 │
│                                                          │
│ ┌─ MILESTONE_3_PHASE2_COMPLETE.md ───────────────────┐ │
│ │ Type: Milestone (95% confidence)                    │ │
│ │ Detected:                                           │ │
│ │   • Status: COMPLETE ✅                             │ │
│ │   • Date: 2026-01-18                                │ │
│ │   • Files Modified: warrior_gui.py, grep_flight.py  │ │
│ │   • Association: Links to IMPLEMENTATION_PLAN.md   │ │
│ │                                                     │ │
│ │ Variables Extracted: 12                             │ │
│ │   - EXPANDED_HEIGHT, PANEL_HEIGHT, backup_manifest  │ │
│ │                                                     │ │
│ │ [✓ Confirm Milestone] [Edit] [Parse as Note]       │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─ plan_17-jan.md ─────────────────────────────────┐   │
│ │ Type: UNCERTAIN (requires review)                 │   │
│ │ Contains: Verbose notes about incoming work       │   │
│ │ Mentions: warrior_gui, default project directory  │   │
│ │                                                    │   │
│ │ Suggested Parsing:                                │   │
│ │   Section 1: "Issues identified" → Task list      │   │
│ │   Section 2: "Button routing review" → Plan phase │   │
│ │                                                    │   │
│ │ Association Check:                                │   │
│ │   Mentions variables from: IMPLEMENTATION_PLAN.md │   │
│ │   Likely: Related note or new task?               │   │
│ │                                                    │   │
│ │ [Create Tasks] [Create Plan] [Keep as Note]       │   │
│ └───────────────────────────────────────────────────┘   │
│                                                          │
│ [Process All] [Skip] [Configure Parsing Rules]          │
└─────────────────────────────────────────────────────────┘
```

#### 5. Provisions Integration
**New Sub-Tab:** [Inventory] → [Migrations]

**Purpose:** Queue confirmed items for action

```
┌─────────────────────────────────────────────────────────┐
│ 📦 PROVISIONS MIGRATIONS                                 │
├─────────────────────────────────────────────────────────┤
│ Pending Migrations: 3                                    │
│                                                          │
│ □ Create task: "Fix Browse button context"              │
│   Source: plan_17-jan.md (Section 1, Item 2)           │
│   Priority: HIGH (inferred from "needs auto-set")      │
│   Associated Plan: IMPLEMENTATION_PLAN_REVISED.md       │
│   [Migrate to Tasks] [Edit] [Cancel]                   │
│                                                          │
│ □ Create milestone: "Phase 2 Complete"                  │
│   Source: MILESTONE_3_PHASE2_COMPLETE.md                │
│   Status: COMPLETE                                       │
│   Files: warrior_gui.py (+180), grep_flight_v2.py (+230)│
│   [Migrate to Milestones] [Edit] [Cancel]              │
│                                                          │
│ □ Update plan: "Add Phase 2.4 (Profile button)"         │
│   Source: READY_FOR_PHASE2_SUMMARY.md                   │
│   Action: Add to IMPLEMENTATION_PLAN.md                 │
│   [Migrate] [Preview Changes] [Cancel]                 │
│                                                          │
│ [Migrate All] [Clear Queue] [Review Settings]           │
└─────────────────────────────────────────────────────────┘
```

#### 6. Target System Integration
**Trigger:** Right-click → [Target for Onboarding]

**Flow:**
```
User creates/modifies doc
    ↓
Right-click file → [Target for Onboarding]
    ↓
Set as grep_flight target
    ↓
doc_onboarder.scan_document(target)
    ↓
Add to onboarding queue
    ↓
User reviews in [Onboarding] tab
    ↓
Confirm/Edit/Categorize
    ↓
Migrate to provisions or appropriate location
    ↓
Update associations and links
```

#### 7. Inference Engine
**Module:** `inference_engine.py`

**Capabilities:**

1. **Actual vs. Expected Comparison**
   ```python
   def compare_state(actual: FileState, expected: DocumentedState) -> Diff:
       - Compare current file state vs. documented expectations
       - Flag discrepancies (file exists but not documented, vice versa)
       - Detect changes since last milestone
       - Generate "what changed" report
   ```

2. **Change Detection**
   ```python
   def detect_changes(since: datetime) -> ChangeReport:
       - Scan for modified .md files
       - Check for new variables in code
       - Identify completed tasks (checkbox changes)
       - Track milestone status updates
       - Queue all changes for review
   ```

3. **Relationship Mapping**
   ```python
   def map_relationships(doc: ParsedDocument) -> RelationshipGraph:
       - Variable mentions → Link to defining documents
       - Plan references → Link to plan files
       - File path mentions → Link to actual files
       - Task associations → Link to task system
       - Build dependency graph
   ```

---

## 🔄 Workflow Integration

### Session Start Routine

**Old Way:**
```
User: "Let's work on X"
AI: "Let me read relevant files..." (manual context gathering)
User: Waits while AI catches up
AI: Sometimes misses critical context
```

**New Way:**
```
User clicks [Start Session] button
    ↓
Doc-Onboarder runs:
  1. Scan for changes since last session
  2. Parse new/modified docs
  3. Generate onboarding queue
  4. Present summary
    ↓
User reviews queue (2-3 min):
  - "Yes, this milestone is complete"
  - "These 3 notes should be tasks"
  - "This verbose section is a plan idea"
    ↓
User confirms all → Provisions migrated
    ↓
AI loads context from structured provisions
    ↓
Both start with synchronized understanding
```

### Document Creation Flow

**After creating doc (like MILESTONE_3_PHASE2_COMPLETE.md):**
```
User: *Creates comprehensive doc*
User: Right-click → [Target for Onboarding]
    ↓
Onboarder:
  - "Detected: Milestone document"
  - "Extracted: 15 variables, 8 file references, 2 plan associations"
  - "Confidence: 95%"
  - "Suggested actions:"
    - Add to Milestones.md
    - Update backup_manifest references
    - Link to IMPLEMENTATION_PLAN.md
    ↓
User: [Confirm All] or [Review Each]
    ↓
System: Migrations complete, provisions updated
```

### Incremental Testing Integration

**Before starting implementation:**
```
User clicks current task in queue
    ↓
Onboarder shows:
  - Task description (from onboarded doc)
  - Associated files (from inference)
  - Expected changes (from plan)
  - Test checklist (from milestone)
    ↓
AI implements feature
    ↓
User tests against checklist
    ↓
AI refines based on feedback
    ↓
User marks task complete
    ↓
Onboarder updates:
  - Task status
  - File change tracking
  - Milestone progress
  - Triggers next task in queue
```

---

## 📋 Implementation Phases

### Phase 1: Foundation (MVP)
**Duration:** 2-3 hours
**Goal:** Basic parsing and queue system

**Deliverables:**
1. `classification.json` with basic rules
2. `doc_parser.py` with core parsing
3. Simple onboarding queue in grep_flight
4. Manual trigger: [Scan Document] button

**Features:**
- Detect milestone markers
- Extract basic variables
- Queue for confirmation
- Manual confirmation UI

### Phase 2: Intelligence
**Duration:** 3-4 hours
**Goal:** Inference and association detection

**Deliverables:**
1. `inference_engine.py`
2. Association detection
3. Verbose text parsing
4. Variable cross-referencing

**Features:**
- "This doc mentions plan X variables"
- Suggest document type when uncertain
- Parse verbose sections into structure
- Build relationship graph

### Phase 3: Automation
**Duration:** 2-3 hours
**Goal:** Target system and migrations

**Deliverables:**
1. Right-click target integration
2. [Migrations] sub-tab
3. Automated provision updates
4. Session start routine

**Features:**
- Target docs after creation
- Migrate confirmed items
- Update Milestones.md automatically
- Generate "what changed" reports

### Phase 4: Advanced
**Duration:** 3-4 hours
**Goal:** Change tracking and validation

**Deliverables:**
1. Actual vs. expected comparison
2. Change detection since last session
3. Test checklist integration
4. Incremental progress tracking

**Features:**
- Detect file changes vs. documentation
- Flag discrepancies
- Track milestone progress
- Automated test checklist generation

---

## 🎁 Benefits

### For User
✅ **Start sessions with full context** - No more re-reading docs
✅ **Systematic workflow** - Clear procedure for each task
✅ **Quality assurance** - Automated checks catch missing links
✅ **Reduced cognitive load** - System tracks state, user confirms
✅ **Better documentation** - Incentive to document properly (gets automated)

### For AI
✅ **Structured context** - No guessing about project state
✅ **Clear objectives** - Queue tells exactly what needs doing
✅ **Validation built-in** - User confirms before implementation
✅ **Change tracking** - Know exactly what changed since last time
✅ **Relationship awareness** - Understand how pieces connect

### For Both
✅ **Synchronized understanding** - Same context, same page
✅ **Incremental progress** - Test systematically as we go
✅ **Quality improvement** - Catch issues before they compound
✅ **Efficient sessions** - Less time catching up, more time building
✅ **Scalable** - System handles complexity, not humans

---

## 🛠️ Technical Specifications

### File Structure
```
/Modules/action_panel/doc_onboarder/
├── __init__.py
├── classification.json          # Parsing rules
├── doc_parser.py               # Core parsing engine
├── inference_engine.py         # Association & change detection
├── onboarding_queue.py         # Queue management
├── provisions_migrator.py      # Move items to provisions
└── ui/
    ├── onboarding_tab.py       # UI for queue review
    └── migrations_tab.py       # UI for pending migrations
```

### Integration Points

**grep_flight_v2.py:**
```python
# Add new tab
self._create_onboarding_tab()

# Add target integration
def _target_for_onboarding(self):
    if self.target_var.get():
        doc_path = Path(self.target_var.get())
        parsed = doc_parser.scan_document(doc_path)
        onboarding_queue.add(parsed)
        self._add_traceback(f"📚 Queued for onboarding: {doc_path.name}", "INFO")
```

**warrior_gui.py:**
```python
# Session start button
def start_session_with_onboarding(self):
    changes = doc_onboarder.detect_changes(since=last_session)
    # Show onboarding dialog
    OnboardingDialog(self, changes)
```

**workspace_manager.py:**
```python
# Add provisions directory for onboarded items
def get_onboarding_provisions_dir(self) -> Path:
    return self.get_inventory_dir() / "onboarding_queue"
```

### Data Models

```python
@dataclass
class ParsedDocument:
    path: Path
    doc_type: str  # plan, milestone, task, note
    confidence: float  # 0.0 - 1.0
    variables: List[Variable]
    associations: List[Association]
    sections: List[Section]
    requires_review: bool
    suggested_actions: List[Action]

@dataclass
class Variable:
    name: str
    value: str
    var_type: str  # path, version, timestamp, etc.
    occurrences: List[Location]

@dataclass
class Association:
    source_doc: Path
    target_doc: Path
    relationship: str  # mentions, extends, implements, etc.
    confidence: float
    evidence: List[str]  # Variable matches, text references, etc.

@dataclass
class OnboardingItem:
    parsed_doc: ParsedDocument
    status: str  # pending, confirmed, rejected
    user_classification: Optional[str]  # User override of doc_type
    migration_target: Optional[Path]
    notes: str
```

---

## 🎯 Success Criteria

### Phase 1 Success
- [ ] Parse at least 3 document types (plan, milestone, note)
- [ ] Extract variables with >80% accuracy
- [ ] Queue displays parsed items
- [ ] User can confirm/reject items
- [ ] Basic migration to provisions works

### Phase 2 Success
- [ ] Detect associations with >70% accuracy
- [ ] Parse verbose text into structured sections
- [ ] Suggest document type when uncertain
- [ ] Build relationship graph
- [ ] Show "why" for each inference

### Phase 3 Success
- [ ] Right-click target adds to queue
- [ ] Migrations sub-tab functional
- [ ] Auto-update Milestones.md on confirmation
- [ ] Session start shows changes summary
- [ ] User completes session in <5 min with onboarding

### Phase 4 Success
- [ ] Detect file changes vs. documentation
- [ ] Flag discrepancies automatically
- [ ] Track milestone progress
- [ ] Generate test checklists from plans
- [ ] Support incremental testing workflow

---

## ⚠️ Risks & Mitigations

### Risk 1: Over-Engineering
**Risk:** System becomes too complex to use
**Mitigation:**
- Start with MVP (Phase 1 only)
- Get user feedback before each phase
- Keep UI simple and intuitive
- Provide escape hatches (manual entry)

### Risk 2: Parsing Accuracy
**Risk:** False positives/negatives in document classification
**Mitigation:**
- Always show confidence score
- Allow user override
- Learn from corrections
- Provide "I don't know" option

### Risk 3: Workflow Disruption
**Risk:** Adds overhead instead of saving time
**Mitigation:**
- Make onboarding optional
- Allow skip/postpone
- Batch processing option
- Quick confirm for obvious cases

### Risk 4: Maintenance Burden
**Risk:** classification.json becomes outdated
**Mitigation:**
- Version classification rules
- Track rule effectiveness
- Suggest rule updates based on corrections
- Keep rules simple and readable

---

## 🚀 Getting Started

### Immediate Next Steps

**Option A: Start Phase 1 Now**
- Create classification.json
- Build basic doc_parser
- Add onboarding tab to grep_flight
- Test with existing docs

**Option B: Plan & Review First**
- Refine this plan together
- Prioritize features
- Define success metrics
- Schedule dedicated session

**Option C: Hybrid Approach**
- Create classification.json (20 min)
- Parse one doc type (milestone)
- Show proof of concept
- Decide whether to continue

---

## 📝 User Feedback Integration

### What User Said (Verbatim):
> "both you and i come in from a space unrelative over many linear aspects compared to this exact projects elements and variables"

**Translation:** Context loss between sessions is real problem

> "if we are working in the /versions dir, maybe i could have a button to trigger a 'doc-onboarder'"

**Translation:** Explicit trigger, not automatic - good UX instinct

> "looks for hooks in documents to queue for my confirmation"

**Translation:** Automated detection + human confirmation = right balance

> "if it cannot parse data it could push it to a tail after trying to format verbose language into sections"

**Translation:** Graceful degradation, don't fail silently

> "hook into mentions relevant to per-version plans to queue 'association-checks'"

**Translation:** Cross-reference variables across docs for relationships

> "you can work without worry and i just have to follow procedure for tasking for coherent systematic development"

**Translation:** System provides structure, reduces worry for both of us

> "we can hook in as well to the 'target' system so a user can just right click & target the docs after creation"

**Translation:** Leverage existing target system for familiar UX

> "it 'infers vs expected/marked/docd', after that the next time we start with a task, i click it, onboard it and we begin testing everything incrementally"

**Translation:** Session starts with onboarding, then systematic incremental testing

---

## 💭 Why This Is Brilliant

This solves a **meta-problem** that affects all development work:

1. **Context Persistence** - Humans and AIs both struggle with context across sessions
2. **Documentation Value** - Currently docs are write-only; this makes them read-able by automation
3. **Workflow Systematization** - Provides clear procedure instead of ad-hoc processes
4. **Quality Gates** - Automated checks before proceeding
5. **Incremental Verification** - Test as you go, catch issues early

**This is infrastructure that pays dividends forever.**

---

## 🤝 Recommendation

**My Suggestion:**
1. **Test current work first** (30 min) - Don't leave Phase 2 implementation untested
2. **Create classification.json** (20 min) - Define parsing rules for current docs
3. **Parse MILESTONE_3 as proof-of-concept** (30 min) - Show what's possible
4. **Review together** - Decide whether to proceed with full implementation

**Timeline if we proceed:**
- Phase 1 MVP: 2-3 hours
- Integration testing: 1 hour
- Phase 2-4: As needed based on Phase 1 success

**Your Call:**
This is a side-quest that would help both of us immensely. Worth it?

What do you think - should we test current work first, or dive into doc-onboarder planning?
