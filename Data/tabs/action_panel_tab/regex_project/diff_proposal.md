# Diff Proposal: Socratic Fixes & Epistemic Infinity

This document outlines proposed structural changes to resolve the identified gaps in the "Student's" cognitive flow.

---

## 1. Epistemic Infinity Pivot
**#[Ref:Task 6.9]**
**Gap:** Curiosity decays once a core property checklist is filled.
**Proposal:** Refactor `_execute_single_interaction` to trigger a domain shift upon sequence completion.

```python
# orchestrator.py (approx line 655)
if self.sequence_completed:
    # Instead of just stopping, we pivot the resolution focus
    pivots = {"general": "domain_technical", "domain_technical": "domain_physics", "domain_physics": "domain_academic"}
    new_domain = pivots.get(self.active_domain, "domain_academic")
    self.active_domain = new_domain
    self.thought_logger.log_thought({"event": "EPISTEMIC_PIVOT", "from": self.active_domain, "to": new_domain})
```

---

## 2. Narrative Memory-Check Lookup
**#[Ref:Task 6.10]**
**Gap:** Memory queries are purely lexical/conceptual and ignore the "Narrative Self" (Journal/Dreams).
**Proposal:** Inject a runtime lookup that compares the current `entity_stack` against the `JournalSystem`.

```python
# orchestrator.py (inside _execute_single_interaction)
if HAS_VM and self.entity_stack:
    subject = self.entity_stack[0]
    # Check if this subject appears in the last 10 journal entries
    narrative_recall = any(subject in e.get('activity', '') for e in self.journal.entries[-10:])
    if narrative_recall:
        resolved["narrative_recall_detected"] = True
```

---

## 3. The "Back to X" Grace Hook
**#[Ref:Task 6.4]**
**Gap:** Topic reentry results in generic "refining logic" fallbacks.
**Proposal:** Specific realization logic for topic-shift discourse markers.

```python
# realization_engine.py (approx line 150)
if "back to" in input_text and what:
    return f"{persona_prefix}Returning focus to '{what}'. I recall our previous resolution reached a confidence of {resolved_intent.get('system_state',{}).get('confidence')}. Where shall we deepen our analysis?"
```

---

## 4. Socratic Pattern Verification
**#[Ref:Task 6.5]**
**Gap:** The student assumes patterns without confirming structural preferences.
**Proposal:** Periodic solicitation of feedback on the interaction structure itself.

```python
# realization_engine.py
if random.random() > 0.9:
    response_text += " I notice we are using a sequential data-gathering structure. Does this pattern of inquiry serve your goals, Commander?"

---

## 5. Learned Response Weights (Gratification Feedback)
**#[Ref:Task 9.3]**
**Gap:** The system doesn't "remember" which conversational tones the user likes.
**Proposal:** Increment weights for specific realization paths when `gratification_count` increases.

```python
# orchestrator.py (inside gratification detection)
if g_hits:
    last_path = self.session_history[-1].get("realization_path")
    self.format_manager.boost_weight(last_path, g_hits)
```

---

## 6. The "Logic Challenge" Pivot (Conditional Parsing)
**#[Ref:Task 9.4]**
**Gap:** "If/Then" propositions are treated as data-ingestion instead of logic tests.
**Proposal:** Detect conditional syntax (Level 4) and pivot to a comparative summary.

```python
# interaction_resolver.py (inside _determine_primary_intent)
if levels.get("level_4_syntax", {}).get("subordinate_clause"):
    if "if" in text_lower or "assume" in text_lower:
        return "LOGIC_CHALLENGE"
```

```
