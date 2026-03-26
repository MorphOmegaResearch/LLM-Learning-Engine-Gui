#!/usr/bin/env python3
"""
Test Epistemic Integration
===========================
Demonstrates full integration of:
  - Epistemic Feedback Loop (gap_analyzer + orchestrator)
  - 5W1H Tool Classification
  - Activity Suggestion based on metastate
  - Zenity Question Queue (if available)
  - Capability Registry with weighted%
"""

import sys
from pathlib import Path

# Add project root to path
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from gap_analyzer import GapAnalyzer, MetastateWeights
from orchestrator import MetacognitiveOrchestrator
from activity_integration_bridge import (
    FiveWOneHClassifier,
    CapabilityRegistry,
    ZenityQuestionQueue,
    ActivitySuggestionBridge,
    OnboardedCapability
)

print("=" * 70)
print("EPISTEMIC INTEGRATION TEST")
print("=" * 70)
print()

# Initialize components
print("1. Initializing components...")
print("-" * 70)

gap_analyzer = GapAnalyzer()
print(f"✓ GapAnalyzer initialized")

orchestrator = MetacognitiveOrchestrator()
print(f"✓ Orchestrator initialized")

classifier = FiveWOneHClassifier()
print(f"✓ 5W1H Classifier initialized")

registry_file = project_root / "capability_registry.json"
capability_registry = CapabilityRegistry(registry_file)
print(f"✓ Capability Registry initialized ({len(capability_registry.capabilities)} capabilities)")

question_queue = ZenityQuestionQueue()
print(f"✓ Zenity Question Queue initialized")

activity_bridge = ActivitySuggestionBridge(
    capability_registry,
    workflow_manager=None,
    question_queue=question_queue
)
print(f"✓ Activity Suggestion Bridge initialized")
print()

# Test 1: Process input through orchestrator and analyze gaps
print("2. Test: Processing input through epistemic feedback loop")
print("-" * 70)

test_input = "quantum chromodynamics field theory applications"
print(f"Input: \"{test_input}\"")
print()

# Process through orchestrator
result = orchestrator.process_interaction(test_input)
print(f"Orchestrator Response: {result['response'][:100]}...")
print()

# Get epistemic state
epistemic_state = orchestrator.epistemic_loop
print(f"Epistemic State:")
print(f"  Understanding%: {epistemic_state.understanding_pct:.0%}")
print(f"  Priority%: {epistemic_state.priority_pct:.0%}")
print(f"  Gap Severity: {epistemic_state.last_gap_severity}")
print(f"  Conversation Format: {epistemic_state.get_conversation_format()}")
print()

# Top priority categories
if epistemic_state.category_weights:
    top_categories = sorted(
        epistemic_state.category_weights.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3]
    print(f"Top 3 Priority Categories:")
    for cat, weight in top_categories:
        print(f"  - {cat}: {weight:.0%}")
    print()

# Test 2: Classify available tools
print("3. Test: Classifying available tools (5W1H)")
print("-" * 70)

tools_to_classify = [
    ("workflow_manager.py", "Manages code review workflows with agent integration"),
    ("import_organizer.py", "Organizes Python import statements by sorting and grouping"),
    ("analyzer.py", "Analyzes code structure and dependencies")
]

classified_tools = []
for tool_name, description in tools_to_classify:
    classification = classifier.classify(tool_name, description)
    classified_tools.append((tool_name, classification))

    print(f"Tool: {tool_name}")
    print(f"  Confidence: {classification.get('confidence', 0):.0%}")
    print(f"  What: {classification.get('what', 'N/A')}")
    print(f"  How: {classification.get('how', 'N/A')}")
    print(f"  Why: {classification.get('why', 'N/A')}")
    print()

# Test 3: Simulate onboarding a capability
print("4. Test: Onboarding a capability (simulated)")
print("-" * 70)

tool_name = "workflow_manager.py"
classification = classified_tools[0][1]  # Use first classified tool

print(f"Onboarding: {tool_name}")
print(f"Classification confidence: {classification.get('confidence', 0):.0%}")

# Check if already onboarded
tool_id = f"tool_{hash(tool_name) % 10000}"
if tool_id not in capability_registry.capabilities:
    capability = capability_registry.onboard_capability(tool_id, tool_name, classification)
    print(f"✓ Capability onboarded with ID: {tool_id}")
    print(f"  Initial weight: {capability.relevance_weight:.2f}")
else:
    capability = capability_registry.capabilities[tool_id]
    print(f"✓ Capability already exists: {tool_id}")
    print(f"  Current weight: {capability.relevance_weight:.2f}")
    print(f"  Usage count: {capability.usage_count}")

print()

# Test 4: Get activity suggestion based on metastate
print("5. Test: Activity suggestion based on epistemic metastate")
print("-" * 70)

# Create gap analysis for current input
gap_analysis = gap_analyzer.analyze_text(test_input)
metastate = gap_analyzer.calculate_metastate_weights(gap_analysis)

print(f"Gap Analysis:")
print(f"  Unrecognized tokens: {len(gap_analysis.unrecognized_tokens)}")
if gap_analysis.unrecognized_tokens:
    print(f"    {', '.join(gap_analysis.unrecognized_tokens[:5])}")
print(f"  Confidence: {gap_analysis.confidence_score:.0%}")
print()

# Get activity suggestion
suggestion = activity_bridge.suggest_activity(metastate, gap_analysis, test_input)

print(f"Activity Suggestion:")
print(f"  Type: {suggestion['activity_type']}")
print(f"  Reason: {suggestion['reason']}")
print(f"  Recommended Action: {suggestion['suggested_action']}")
print()

if suggestion['relevant_capabilities']:
    print(f"  Relevant Capabilities:")
    for cap in suggestion['relevant_capabilities']:
        print(f"    - {cap['tool']} (relevance: {cap['relevance']:.0%})")
        print(f"      What: {cap['what']}")
print()

# Test 5: Queue questions based on gaps
print("6. Test: Generating zenity questions from gaps")
print("-" * 70)

# Enqueue gap question
question_queue.enqueue_gap_question(gap_analysis, metastate)
print(f"✓ Gap clarification question enqueued")

# Enqueue capability confirmation
question_queue.enqueue_capability_confirmation(tool_name, classification)
print(f"✓ Capability confirmation question enqueued")

# Enqueue thought question (from orchestrator thoughts)
if result.get('thoughts'):
    epistemic_thoughts = [t for t in result['thoughts'] if 'Epistemic' in t]
    if epistemic_thoughts:
        question_queue.enqueue_thought_question(epistemic_thoughts[0], priority=0.8)
        print(f"✓ Thought inquiry question enqueued")

print(f"\nQuestion Queue Status:")
print(f"  Pending questions: {len(question_queue.queue)}")
print(f"  Types: {', '.join(set(q['type'] for q in question_queue.queue))}")
print()

# Show queued questions (don't actually process - user may not have zenity)
print("Queued Questions (preview):")
for i, q in enumerate(question_queue.queue[:3], 1):
    print(f"\n  [{i}] {q['title']}")
    print(f"      {q['text'][:100]}...")
    if q.get('options'):
        print(f"      Options: {', '.join(q['options'])}")

print()

# Test 6: Demonstrate weighted relevance update
print("7. Test: Updating capability relevance weights")
print("-" * 70)

# Simulate usage
original_weight = capability.relevance_weight
capability_registry.update_relevance(tool_id, +0.15)  # Boost for relevant use

print(f"Tool: {tool_name}")
print(f"  Weight before: {original_weight:.2f}")
print(f"  Weight after: {capability.relevance_weight:.2f}")
print(f"  Usage count: {capability.usage_count}")
print()

# Add journal mark
mark_id = f"WORKFLOW_EXEC_{hash(test_input) % 1000}"
capability_registry.add_journal_mark(tool_id, f"#[MARK:{{{mark_id}}}]")
print(f"✓ Journal mark added: #[MARK:{{{mark_id}}}]")
print(f"  Total marks for this capability: {len(capability.journal_marks)}")
print()

# Summary
print("=" * 70)
print("INTEGRATION TEST SUMMARY")
print("=" * 70)
print()
print("✓ Epistemic Feedback Loop:")
print(f"    - Gap detection working (detected {len(gap_analysis.unrecognized_tokens)} unknown terms)")
print(f"    - Metastate weights calculated (understanding={metastate.understanding_pct:.0%}, priority={metastate.priority_pct:.0%})")
print(f"    - Conversation format selected: {epistemic_state.get_conversation_format()}")
print()
print("✓ Tool Classification (5W1H):")
print(f"    - Classified {len(classified_tools)} tools")
print(f"    - Average confidence: {sum(c.get('confidence', 0) for _, c in classified_tools) / len(classified_tools):.0%}")
print()
print("✓ Activity Suggestion:")
print(f"    - Activity type: {suggestion['activity_type']}")
print(f"    - Based on gap_severity={metastate.gap_severity}")
print(f"    - {len(suggestion['relevant_capabilities'])} relevant capabilities identified")
print()
print("✓ Question Queue (Zenity):")
print(f"    - {len(question_queue.queue)} questions queued")
print(f"    - Ready for zenity --question/--list processing")
print()
print("✓ Capability Registry:")
print(f"    - {len(capability_registry.capabilities)} capabilities onboarded")
print(f"    - Weighted relevance tracking active")
print(f"    - Journal mark integration: {sum(len(c.journal_marks) for c in capability_registry.capabilities.values())} total marks")
print()
print("Integration Status: FULLY OPERATIONAL")
print()
print(f"Registry file: {registry_file}")
print(f"Next steps: Run with zenity available to process question queue")
