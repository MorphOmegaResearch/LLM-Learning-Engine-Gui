import argparse
import json
import os
import sys
import random
import re
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pathlib import Path
from interaction_resolver import InteractionResolver
from realization_engine import RealizationEngine
from gap_analyzer import GapAnalyzer

# Weight tuner integration for interactive weight adjustment
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'babel_data', 'inventory', 'core'))
    from weight_tuner import ActionWeightTuner
    HAS_WEIGHT_TUNER = True
except ImportError as e:
    print(f"Info: Weight Tuner not available: {e}")
    print("  Interactive weight tuning will be disabled")
    HAS_WEIGHT_TUNER = False

# Graceful import for Activity Integration Bridge
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'activities', 'tools', 'scripts'))
    from activity_integration_bridge import (
        FiveWOneHClassifier,
        CapabilityRegistry,
        ZenityQuestionQueue,
        ActivitySuggestionBridge,
        OsToolkitGroundingBridge,
        MorphTeachingBridge,
        MorphToolkit,
        MorphCapabilityCatalog,
        MorphManifestBridge,
        MorphConformer,
    )
    HAS_ACTIVITY_BRIDGE = True
except ImportError as e:
    print(f"Info: Activity Integration Bridge not available: {e}")
    print("  Activity suggestions will be disabled")
    HAS_ACTIVITY_BRIDGE = False

# ============================================================================
# Conversation State Machine
# ============================================================================

class ConversationState(Enum):
    """Explicit conversation states for multi-step flow tracking."""
    IDLE = "idle"
    CALIBRATING = "calibrating"          # Awaiting phrasing/correction feedback
    LEARNING = "learning"                 # Multi-turn teaching sequence
    COMPARING = "comparing"               # Entity comparison in progress
    CLARIFYING = "clarifying"             # Awaiting clarification from user
    PROACTIVE_INQUIRY = "proactive"       # System asked a question, awaiting answer
    WEIGHT_TUNING = "weight_tuning"       # Interactive weight adjustment mode
    MORPH_STATE_CHAT = "morph_state_chat" # Morph chat about current state with session context

class ConversationFlowManager:
    """Manages conversation state transitions and pending context."""

    def __init__(self):
        self.state = ConversationState.IDLE
        self.pending_context = {}
        self.state_turn_count = 0  # Turns in current state
        self.max_state_turns = 5   # Auto-reset after N turns

    def transition(self, new_state: ConversationState, context: dict = None):
        """Transition to a new state with optional context."""
        self.state = new_state
        self.pending_context = context or {}
        self.state_turn_count = 0

    def tick(self) -> bool:
        """Called each turn to track state duration. Returns True if auto-reset occurred."""
        self.state_turn_count += 1
        # Auto-reset stuck states
        if self.state_turn_count >= self.max_state_turns and self.state != ConversationState.IDLE:
            self.reset()
            return True  # Signal that auto-reset occurred
        return False

    def reset(self):
        """Reset to idle state."""
        self.state = ConversationState.IDLE
        self.pending_context = {}
        self.state_turn_count = 0

    def is_awaiting_response(self) -> bool:
        """Check if system is waiting for user to respond to something."""
        return self.state in [
            ConversationState.CALIBRATING,
            ConversationState.CLARIFYING,
            ConversationState.PROACTIVE_INQUIRY
        ]

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "pending_context": self.pending_context,
            "state_turn_count": self.state_turn_count
        }

    def from_dict(self, data: dict):
        self.state = ConversationState(data.get("state", "idle"))
        self.pending_context = data.get("pending_context", {})
        self.state_turn_count = data.get("state_turn_count", 0)

# ============================================================================
# Response Builder - Standardized Response Format
# ============================================================================

class ResponseBuilder:
    """Builds standardized response dictionaries with hook priority management."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder for new response."""
        self._prefix = ""
        self._core = ""
        self._hooks = []  # List of (priority, text) tuples
        self._tokens = []
        self._stats = {}
        self._meta = {}

    def set_prefix(self, persona: str, situation: str = None, formality: str = "medium"):
        """Set the persona/situation prefix."""
        prefix = f"[{persona} Mode]"
        if formality == "high":
            prefix = prefix.replace("Mode]", "Protocol]")
        if situation:
            prefix += f" <{situation}>"
        self._prefix = prefix + " "
        return self

    def set_core(self, text: str):
        """Set the core response content."""
        self._core = text
        return self

    def add_hook(self, priority: float, text: str, condition: bool = True):
        """Add a hook with priority (0.0-1.0). Higher priority = more likely included."""
        if condition and text and text.strip():
            self._hooks.append((priority, text.strip()))
        return self

    def set_tokens(self, tokens: List[str]):
        """Set token list for output."""
        self._tokens = tokens
        return self

    def add_token(self, token: str):
        """Add a single token."""
        self._tokens.append(token)
        return self

    def set_stats(self, stats: dict):
        """Set stats dictionary."""
        self._stats = stats
        return self

    def set_meta(self, **kwargs):
        """Set metacognitive state values."""
        self._meta.update(kwargs)
        return self

    def build(self, max_hooks: int = 2) -> dict:
        """Build the final response dictionary."""
        # Sort hooks by priority and take top N
        sorted_hooks = sorted(self._hooks, key=lambda x: x[0], reverse=True)
        selected_hooks = [h[1] for h in sorted_hooks[:max_hooks]]

        # Assemble response text
        response_parts = [self._prefix, self._core]
        response_parts.extend(selected_hooks)
        response_text = " ".join(filter(None, response_parts))

        # Clean up multiple spaces
        response_text = re.sub(r'\s+', ' ', response_text).strip()

        return {
            "tokens": " ".join(self._tokens) if self._tokens else "",
            "response": response_text,
            "stats": self._stats,
            "metacognitive_state": self._meta
        }

    def build_error(self, message: str, code: str = "ERROR") -> dict:
        """Build standardized error response."""
        return {
            "tokens": f"[ERR: {code}]",
            "response": message,
            "stats": {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L0_ATOMIC"},
            "metacognitive_state": {
                "system_confidence": 0.5,
                "priority_weight": 0.0,
                "thought_event": "ERROR"
            }
        }

# ============================================================================
# Epistemic Feedback Loop - Metastate-driven Inference
# ============================================================================

class EpistemicFeedbackLoop:
    """
    Implements 'the more you know, the more you know you don't know' principle.
    Manages metastate weights for adaptive conversation response selection.
    """

    def __init__(self):
        self.category_weights = {}  # category -> priority%
        self.understanding_pct = 1.0
        self.priority_pct = 0.0
        self.last_gap_severity = "low"

    def update_from_gap_analysis(self, metastate_weights):
        """
        Update internal state from GapAnalyzer metastate weights.

        Args:
            metastate_weights: MetastateWeights object from gap_analyzer
        """
        self.category_weights = metastate_weights.category_weights
        self.understanding_pct = metastate_weights.understanding_pct
        self.priority_pct = metastate_weights.priority_pct
        self.last_gap_severity = metastate_weights.gap_severity

    def get_conversation_format(self) -> str:
        """
        Determine conversation format based on priority% × understanding%.

        Returns:
            Conversation format: "PROACTIVE_INQUIRY", "CLARIFYING_QUESTION",
                                "STANDARD_RESPONSE", "CONFIDENT_EXPLANATION"
        """
        # High priority gaps → ask questions to learn
        if self.priority_pct > 0.75:
            return "PROACTIVE_INQUIRY"
        elif self.priority_pct > 0.50:
            return "CLARIFYING_QUESTION"
        # Low priority, high understanding → confident response
        elif self.understanding_pct > 0.8 and self.priority_pct < 0.3:
            return "CONFIDENT_EXPLANATION"
        else:
            return "STANDARD_RESPONSE"

    def should_trigger_audit_diff(self) -> bool:
        """
        Determine if audit --diff should be triggered for pattern discovery.

        Returns:
            True if gap severity is critical and warrants pattern weight adjustment
        """
        return self.last_gap_severity in ["critical", "high"]

    def get_weighted_5w1h_priorities(self) -> Dict[str, float]:
        """
        Get priority weights for 5W1H re-resolution.

        Returns:
            Dictionary mapping 5W1H slots to priority weights (0-1)
        """
        # Map linguistic categories to 5W1H slots
        category_to_slot = {
            "level_3_lexical": "what",
            "level_4_syntax": "how",
            "level_5_semantics": "why",
            "level_6_pragmatics": "how",
            "domain_technical": "what",
            "entities_temporal": "when",
            "entities_properties": "what"
        }

        slot_priorities = {"what": 0.5, "who": 0.5, "where": 0.5, "when": 0.5, "why": 0.5, "how": 0.5}

        # Aggregate category weights into slot priorities
        for category, weight in self.category_weights.items():
            slot = category_to_slot.get(category, "what")
            # Higher category weight → higher slot priority
            slot_priorities[slot] = max(slot_priorities[slot], weight)

        return slot_priorities

    def to_dict(self) -> dict:
        """Export current state for persistence."""
        return {
            "category_weights": self.category_weights,
            "understanding_pct": self.understanding_pct,
            "priority_pct": self.priority_pct,
            "gap_severity": self.last_gap_severity
        }

try:
    from version_manager import BackupManager, JournalSystem
    HAS_VM = True
except ImportError:
    HAS_VM = False

# Absolute Path Resolution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_path(rel_path):
    # If the rel_path starts with 'regex_project/', we strip it because BASE_DIR is already regex_project
    if rel_path.startswith("regex_project/"):
        rel_path = rel_path.replace("regex_project/", "", 1)
    return os.path.join(BASE_DIR, rel_path)

class KnowledgeManager:
    def __init__(self, path, logger=None):
        self.path = get_path(path)
        self.logger = logger
        with open(self.path, 'r') as f:
            self.db = json.load(f)

    def save_concept(self, name, data):
        name = name.lower()
        if name not in self.db["concepts"]:
            self.db["concepts"][name] = {"definition": "", "properties": {}, "timestamp": datetime.now().isoformat()}
        
        # Ensure properties key exists for legacy concepts
        if "properties" not in self.db["concepts"][name]:
            self.db["concepts"][name]["properties"] = {}

        # Merge properties if provided
        if "properties" in data:
            msg = f"DEBUG: Saving properties for {name}: {data['properties']}"
            if self.logger: self.logger(msg)
            else: print(msg)
            self.db["concepts"][name]["properties"].update(data["properties"])
        
        if "definition" in data:
            self.db["concepts"][name]["definition"] = data["definition"]
            
        self.db["concepts"][name]["timestamp"] = datetime.now().isoformat()
        self.db["metadata"]["total_entities_learned"] = len(self.db["concepts"])
        with open(self.path, 'w') as f:
            json.dump(self.db, f, indent=2)

    def get_concept(self, name):
        return self.db["concepts"].get(name.lower())

    def check_consistency(self, name, new_definition):
        concept = self.get_concept(name)
        if not concept or not concept.get("definition"):
            return True, None
        
        old_def = concept["definition"].lower().strip(" .")
        new_def = new_definition.lower().strip(" .")
        
        if old_def != new_def:
            # Filter stop words for meaningful overlap check
            stop_words = {"a", "an", "the", "is", "are", "of", "in", "it"}
            old_words = set(w for w in old_def.split() if w not in stop_words)
            new_words = set(w for w in new_def.split() if w not in stop_words)
            overlap = old_words.intersection(new_words)
            
            if not overlap and len(new_words) >= 1:
                return False, concept["definition"]
        
        return True, None

class AutoIngestor:
    def __init__(self, path, orchestrator=None):
        self.path = get_path(path)
        self.orchestrator = orchestrator
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({"candidates": {}, "metadata": {"total_captured": 0}}, f)

    def get_top_candidate(self):
        with open(self.path, 'r') as f:
            data = json.load(f)
        candidates = sorted(data["candidates"].items(), key=lambda x: x[1], reverse=True)
        return candidates[0][0] if candidates else None

    def mark_learned(self, entity):
        with open(self.path, 'r') as f:
            data = json.load(f)
        entity = entity.lower()
        if entity in data["candidates"]:
            del data["candidates"][entity]
            data["metadata"]["total_captured"] = len(data["candidates"])
            with open(self.path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        return False

    def capture_unknowns(self, text, stats, resolved):
        if stats["lexical_pct"] <= 1.0:
            words = text.lower().split()
            # Simple heuristic: words not in L3 or domain regexes
            with open(self.path, 'r') as f:
                data = json.load(f)
            
            # Identify what we recognized to find what we DIDN'T
            recognized = set()
            # ONLY use low-level categories for "recognized" set to find true gaps
            lexical_levels = ["level_3_lexical", "domain_academic", "domain_technical", "entities_temporal", "entities_numerical"]
            for level in lexical_levels:
                for cat, matches in resolved["hierarchy_analysis"].get(level, {}).items():
                    for m in matches:
                        val = m[0] if isinstance(m, tuple) else m
                        if isinstance(val, str):
                            for word in val.lower().split():
                                recognized.add(word)
            
            unknowns = [w.strip("?!.,") for w in words if w not in recognized and len(w) > 3]
            
            for u in unknowns:
                data["candidates"][u] = data["candidates"].get(u, 0) + 1
            
            data["metadata"]["total_captured"] = len(data["candidates"])
            with open(self.path, 'w') as f:
                json.dump(data, f, indent=2)

class GratificationTracker:
    def __init__(self):
        self.hooks = ["well done", "good job", "excellent", "perfect", "thank you", "nice"]

    def check(self, text):
        count = 0
        for hook in self.hooks:
            if hook in text.lower():
                count += 1
        return count

class UnresolvedQuestionPool:
    def __init__(self, path):
        self.path = get_path(path)
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({"pool": [], "metadata": {"count": 0, "last_entry": None}}, f)

    def add(self, text, reason):
        with open(self.path, 'r') as f:
            data = json.load(f)
        
        data["pool"].append({"query": text, "reason": reason, "timestamp": datetime.now().isoformat()})
        data["metadata"]["count"] = len(data["pool"])
        data["metadata"]["last_entry"] = datetime.now().isoformat()
        
        with open(self.path, 'w') as f:
            json.dump(data, f, indent=2)

class NovelStoryGenerator:
    def __init__(self, kb_path, sit_path):
        self.kb_path = kb_path
        self.sit_path = sit_path

    def generate(self):
        with open(self.kb_path, 'r') as f: kb = json.load(f)
        with open(self.sit_path, 'r') as f: sits = json.load(f)
        
        concepts = list(kb["concepts"].keys())
        situations = [s["name"] for s in sits["situations"]]
        
        if not concepts: concepts = ["Empty Context", "Silent Terminal"]
        if not situations: situations = ["Void state"]
        
        c = random.choice(concepts)
        s = random.choice(situations)
        
        story = f"The system processed a sequence where {c} interacted with {s}. "
        story += f"Hierarchical weights suggest that {c} is expanding its influence across the current network topology."
        
        return story

class DreamState:
    def __init__(self):
        self.log_path = get_path("regex_project/interaction_logs.json")
        self.kb_path = get_path("regex_project/knowledge_base.json")

    def analyze(self):
        with open(self.log_path, 'r') as f:
            logs = json.load(f)
        
        # Analyze top unresolved words
        unknowns = {}
        for entry in logs:
            if entry["lexical_match_pct"] < 0.5:
                words = entry["input"].lower().split()
                for w in words:
                    if len(w) > 4:
                        unknowns[w] = unknowns.get(w, 0) + 1
        
        sorted_unknowns = sorted(unknowns.items(), key=lambda x: x[1], reverse=True)
        return {
            "top_gaps": sorted_unknowns[:5],
            "total_logs_analyzed": len(logs),
            "insight": "I am discovering patterns in the unknown lexicon." if sorted_unknowns else "Knowledge is currently stable."
        }

class TokenLogger:
    def __init__(self, path):
        self.path = get_path(path)
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump([], f)

    def log_interaction(self, text, resolved, stats):
        with open(self.path, 'r') as f:
            logs = json.load(f)
        
        entry = {
            "timestamp": "now",
            "input": text,
            "lexical_match_pct": stats["lexical_pct"],
            "syntactic_match_pct": stats["syntactic_pct"],
            "primary_intent": resolved["logical_intent"]
        }
        logs.append(entry)
        
        # Keep only last 100 for performance
        logs = logs[-100:]
        
        with open(self.path, 'w') as f:
            json.dump(logs, f, indent=2)
        return logs

class SystemMonitor:
    def __init__(self, signals_path):
        self.path = get_path(signals_path)
        with open(self.path, 'r') as f:
            self.config = json.load(f)

    def get_signals(self, text=""):
        # Fetch actual system data
        signals = {
            "datetime": datetime.now().isoformat(),
            "cwd": os.getcwd(),
            "load": os.getloadavg() if hasattr(os, 'getloadavg') else [0,0,0],
            "extracted": {}
        }
        
        # Dynamic Extraction from text using patterns in system_signals.json
        for category, sub in self.config["system_signals"].items():
            for signal_name, data in sub.items():
                if "pattern" in data:
                    match = re.search(data["pattern"], text, re.IGNORECASE)
                    if match:
                        signals["extracted"][signal_name] = match.group(1)
                elif isinstance(data, dict): # Handle nested structures like datetime/file_system
                    for s_key, s_val in data.items():
                        if isinstance(s_val, str) and not s_key == "context":
                            match = re.search(s_val, text, re.IGNORECASE)
                            if match:
                                signals["extracted"][s_key] = match.group(0)
        return signals

import time

class TimeStateEngine:
    def __init__(self, start_time):
        self.start_time = start_time
        self.last_interaction = time.time()

    def get_fatigue_factor(self):
        # Fatigue increases after 30 minutes of session or long idle times
        duration = time.time() - self.start_time
        idle = time.time() - self.last_interaction
        
        factor = 1.0
        if duration > 1800: factor -= 0.1 # Long session fatigue
        if idle > 300: factor -= 0.05 # Idle fatigue
        
        return max(0.5, factor)

    def update_interaction_time(self):
        self.last_interaction = time.time()

    def get_routine_match(self, routine_config):
        # Current time in HH:MM format
        now = datetime.now().strftime("%H:%M")
        for slot in routine_config.get("routine", []):
            start, end = slot["time_slot"].split("-")
            if start <= now <= end:
                return slot
        return None

    def get_output_cadence(self, want_need_intensity):
        # Task 11.3: Modulation based on intensity
        # returns "short", "medium", or "long"
        if want_need_intensity > 0.8: return "long"
        if want_need_intensity < 0.2: return "short"
        return "medium"

class ReasoningLogger:
    def __init__(self, path):
        self.path = get_path(path)
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump([], f)

    def log_thought(self, reasoning_data):
        with open(self.path, 'r') as f:
            logs = json.load(f)
        
        reasoning_data["timestamp"] = datetime.now().isoformat()
        logs.append(reasoning_data)
        
        # Keep last 50 thoughts
        logs = logs[-50:]
        
        with open(self.path, 'w') as f:
            json.dump(logs, f, indent=2)

class InteractionTypeLearner:
    def __init__(self, path):
        self.path = get_path(path)
        if not os.path.exists(self.path):
            with open(self.path, 'w') as f:
                json.dump({"history": [], "common_types": {}}, f)

    def learn_type(self, session_history):
        # Analyze the sequence of logical_intents
        sequence = [h.get("logical_intent") for h in session_history[-10:]] # Increased lookback
        if len(sequence) < 1: return "undetermined"
        
        latest = sequence[-1]
        
        # Immediate Overrides for high-signal intents
        if latest in ["SOCIAL_INITIATION", "SYSTEM_INQUIRY", "TOPIC_REENTRY"]:
            return "GENERAL_EXCHANGE"
        if latest == "COMMAND_EXECUTION":
            return "OPERATIONAL_TASK"
        
        # Enhanced Pattern Mapping
        if "LEARNING_MODE" in sequence or "LEARNING_EXCHANGE" in sequence:
            # Only stay in LEARNING_EXCHANGE if the latest isn't a total mismatch
            if latest not in ["UNKNOWN_INTENT", "GENERAL_EXCHANGE"]:
                return "LEARNING_EXCHANGE"
        
        if "INFORMATION_QUERY" in sequence and "GRATIFICATION" in sequence:
            return "HELPFUL_DIALOG"
        if "SOCIAL_INITIATION" in sequence and len(set(sequence)) == 1:
            return "SMALL_TALK"
        
        return "GENERAL_EXCHANGE"

class PersonaGuard:
    def __init__(self):
        self.constraints = {
            "Scholar": {
                "forbidden": ["yo", "gonna", "wanna", "fire", "dope"],
                "required_min_len": 20
            },
            "Engineer": {
                "forbidden": ["I feel", "maybe", "I guess"],
                "required_keywords": ["system", "load", "spec", "data"]
            },
            "Mate": {
                "forbidden": ["empirical", "methodology", "utilization"],
                "preferred_markers": ["yo", "bruh", "mate"]
            }
        }

    def validate(self, text, persona):
        if persona not in self.constraints: return text
        
        c = self.constraints[persona]
        # Use regex with word boundaries
        for word in c.get("forbidden", []):
            pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
            text = pattern.sub("[REDACTED BY GUARD]", text)
        
        return text

class DialogueModeTracker:
    def __init__(self):
        self.modes = ["EXPLORATORY", "DEEP_LEARNING", "MAINTENANCE"]

    def determine_mode(self, stats, interaction_type, turn_count):
        if interaction_type == "OPERATIONAL_TASK":
            return "MAINTENANCE"
        if stats["lexical_pct"] < 0.4 or interaction_type == "HELPFUL_DIALOG":
            return "DEEP_LEARNING"
        return "EXPLORATORY"

class AltruismManager:
    def __init__(self):
        self.base_willingness = 0.5

    def calculate(self, signals, gratification_count):
        # Health factor
        load = signals.get("load", [0])[0]
        health_mod = max(0, 1.0 - (load / 5.0))
        
        # Social factor
        social_mod = min(gratification_count * 0.1, 0.5)
        
        return min(1.0, self.base_willingness + social_mod) * health_mod

class FormatManager:
    """Tracks and boosts successful response structures based on gratification."""
    def __init__(self, path, logger=None):
        self.path = path # Path is already resolved by get_path in orchestrator
        self.logger = logger
        if os.path.exists(self.path):
            with open(self.path, 'r') as f:
                self.weights = json.load(f)
        else:
            self.weights = {}

    def boost_weight(self, path_id, hits):
        if not path_id: return
        msg = f"DEBUG: Boosting weight for {path_id} by {hits}"
        if self.logger: self.logger(msg)
        else: print(msg)
        self.weights[path_id] = self.weights.get(path_id, 1.0) + (0.1 * hits)
        with open(self.path, 'w') as f:
            json.dump(self.weights, f, indent=2)

    def get_weight(self, path_id):
        return self.weights.get(path_id, 1.0)

class ActivitySuggestionEngine:
    """Suggests shared experiences based on domain affinity and boredom (Task 11.2)."""
    def __init__(self, routine_path):
        self.path = get_path(routine_path)
        with open(self.path, 'r') as f:
            self.config = json.load(f)
        self.definitions = self.config.get("activity_definitions", {})

    def suggest(self, active_domain="general", learning_candidate=None):
        # 1. Prioritize Learning Queue (Task: learning queue context)
        if learning_candidate and random.random() > 0.3:
            return f"Conceptual Deep-Dive: {learning_candidate}"

        # 2. Filter activities by domain affinity
        candidates = []
        for name, data in self.definitions.items():
            if data.get("domain_affinity") == active_domain:
                candidates.append(name)
        
        # Fallback to general if no specific matches
        if not candidates:
            candidates = [name for name, data in self.definitions.items() if data.get("domain_affinity") == "general"]
            
        return random.choice(candidates) if candidates else "Deep Read"

class CreativeActivityEngine:
    def __init__(self, kb_path, log_dir):
        self.kb_path = kb_path
        self.log_dir = log_dir

    def run_simulation(self, duration, active_entity):
        # Simulate 'thought' process over time
        log_id = int(time.time())
        path = os.path.join(self.log_dir, f"activity_{log_id}_log.json")
        
        # Simulated reasoning steps
        steps = [
            f"Scanning hierarchy for {active_entity}...",
            f"Comparing {active_entity} weights against situational context.",
            f"Attempting to resolve semantic links via Level 5 patterns.",
            f"Hypothesis: {active_entity} is a prerequisite for system-state stability."
        ]
        
        simulation_result = {
            "activity_id": log_id,
            "subject": active_entity,
            "duration": duration,
            "reasoning_steps": steps,
            "conclusion": f"The entity '{active_entity}' remains lexically thin but syntactically verified."
        }
        
        with open(path, 'w') as f:
            json.dump(simulation_result, f, indent=2)
        return path

class ThoughtEngine:
    """Handles internal reasoning, self-correction, and pattern resolution."""
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def resolve_unknowns(self, text, resolved, stats):
        thoughts = []
        words = [w.strip("?!.,").lower() for w in text.split()]
        
        # Identify unrecognized tokens - Check ALL levels (Task: resolve fluidly)
        recognized = set()
        for level_data in resolved["hierarchy_analysis"].values():
            if isinstance(level_data, dict):
                for matches in level_data.values():
                    for m in matches:
                        val = m[0] if isinstance(m, tuple) else m
                        if isinstance(val, str):
                            for word in val.lower().split():
                                recognized.add(word)
        
        # Additional baseline recognition (Task: don't learn 'because')
        baseline = {"is", "are", "was", "were", "the", "and", "but", "with", "from", "for", "that", "this", "it", "because", "what", "how", "why"}
        recognized.update(baseline)

        unknowns = [w for w in words if w not in recognized and len(w) > 3]
        
        for u in unknowns:
            thoughts.append(f"Epistemic gap detected: '{u}'")
            # Simulated pattern self-resolution
            pattern_hit = False
            if u.endswith("ing"):
                thoughts.append(f"Execution: python3 -c \"import re; print(bool(re.search(r'\\w+ing\\b', '{u}')))\" -> SUCCESS")
                thoughts.append(f"Inference: '{u}' fits [L2: PRESENT_PARTICIPLE]. Temporary resolution active.")
                pattern_hit = True
            
            if not pattern_hit:
                thoughts.append(f"Execution: pattern_match('{u}') -> FAIL. Token queued for external calibration.")

        return thoughts

from conversational_trainer import ConversationalTrainer

class MetacognitiveOrchestrator:
    def __init__(self): #[Mark:ORCH_INIT]
        self.thoughts = []
        self.resolver = InteractionResolver(
            get_path("regex_project/master_regex.json"),
            get_path("regex_project/universal_taxonomy.json"),
            get_path("regex_project/academia.json")
        )
        self.engine = RealizationEngine(
            get_path("regex_project/response_strategies.json"),
            get_path("regex_project/academia.json")
        )
        self.gap_analyzer = GapAnalyzer(
            patterns_file=get_path("regex_project/master_regex.json")
        )
        self.km = KnowledgeManager("regex_project/knowledge_base.json", logger=self.add_thought)
        self.logger = TokenLogger(get_path("regex_project/interaction_logs.json"))
        self.trainer = ConversationalTrainer(get_path("activities/training"))
        
        # Initialize Version & Journal Systems
        if HAS_VM:
            self.backup = BackupManager(BASE_DIR, get_path("regex_project/backups"))
            self.journal = JournalSystem(get_path("regex_project/journals"))
            # Self-check delta on launch
            delta = self.backup.check_size_delta("orchestrator.py")
            if abs(delta) > 500:
                self.add_thought(f"[VM] Significant change detected: {delta} bytes.")
        
        self.thought_logger = ReasoningLogger(get_path("regex_project/dream/reasoning_logs.json"))
        self.ingestor = AutoIngestor("regex_project/candidate_entities.json", orchestrator=self)
        self.monitor = SystemMonitor("regex_project/system_signals.json")
        self.grat_tracker = GratificationTracker()
        self.question_pool = UnresolvedQuestionPool("regex_project/unresolved_questions.json")
        self.it_learner = InteractionTypeLearner("regex_project/interaction_types.json")
        self.persona_guard = PersonaGuard()
        self.mode_tracker = DialogueModeTracker()
        self.altruism_mgr = AltruismManager()
        self.format_mgr = FormatManager(get_path("format_weights.json"), logger=self.add_thought)
        with open(get_path("regex_project/daily_routine.json"), 'r') as f:
            self.routine_config = json.load(f)
        self.activity_engine = ActivitySuggestionEngine("regex_project/daily_routine.json")
        self.creative_engine = CreativeActivityEngine(get_path("regex_project/knowledge_base.json"), get_path("regex_project/dream"))
        self.thought_engine = ThoughtEngine(self)
        self.boredom_score = 0.0 # Default before load
        self.volition_score = 0.0 # Default before load (Task 10.1)
        self.learning_velocity = 0.5 # New gradient (Task 12.6)
        self.last_system_output = "" # Track for phrasing correction
        self.calibration_active = False # Multi-turn teaching flag (DEPRECATED - use conversation_flow)
        self.active_calibration_subject = ""

        # NEW: Conversation Flow Manager for multi-step interactions
        self.conversation_flow = ConversationFlowManager()
        self.response_builder = ResponseBuilder()

        # NEW: Epistemic Feedback Loop for metastate-driven inference
        self.epistemic_loop = EpistemicFeedbackLoop()

        # NEW: Activity Integration Bridge (graceful fallback if not available)
        if HAS_ACTIVITY_BRIDGE:
            try:
                registry_file = get_path("capability_registry.json")
                self.capability_registry = CapabilityRegistry(Path(registry_file))
                self.question_queue = ZenityQuestionQueue()
                self.activity_bridge = ActivitySuggestionBridge(
                    self.capability_registry,
                    workflow_manager=None,  # TODO: integrate workflow_manager
                    question_queue=self.question_queue
                )
                self.add_thought(f"Activity Bridge initialized: {len(self.capability_registry.capabilities)} capabilities loaded")
            except Exception as e:
                self.add_thought(f"Activity Bridge initialization failed: {e}")
                self.activity_bridge = None
        else:
            self.activity_bridge = None
            self.capability_registry = None
            self.question_queue = None

        self._load_state()
        self.timer = TimeStateEngine(self.session_start)
        self.interaction_type = "undetermined"
        self.dialogue_mode = "EXPLORATORY"
        self.sharing_willingness = 0.5

    def add_thought(self, msg):
        self.thoughts.append(msg)

    def _load_state(self):
        self.state_path = get_path("regex_project/session_state.json")
        if os.path.exists(self.state_path):
            with open(self.state_path, 'r') as f:
                state = json.load(f)
                self.entity_stack = state.get("entity_stack", [])
                self.confidence_score = state.get("confidence_score", 1.0)
                self.turn_count = state.get("turn_count", 0)
                self.active_domain = state.get("active_domain", "general")
                self.active_persona = state.get("active_persona", "Assistant")
                self.gratification_count = state.get("gratification_count", 0)
                self.session_start = state.get("session_start", time.time())
                self.session_history = state.get("session_history", [])
                self.active_situation = state.get("active_situation", None)
                self.recent_thoughts = state.get("recent_thoughts", [])
                self.boredom_score = state.get("boredom_score", 0.0)
                self.volition_score = state.get("volition_score", 0.0)
                self.learning_velocity = state.get("learning_velocity", 0.5)
                self.last_system_output = state.get("last_system_output", "")
                self.calibration_active = state.get("calibration_active", False)
                self.active_calibration_subject = state.get("active_calibration_subject", "")
                # Load conversation flow state
                if "conversation_flow" in state:
                    self.conversation_flow.from_dict(state["conversation_flow"])
                # Load epistemic loop state
                if "epistemic_loop" in state:
                    eloop = state["epistemic_loop"]
                    self.epistemic_loop.category_weights = eloop.get("category_weights", {})
                    self.epistemic_loop.understanding_pct = eloop.get("understanding_pct", 1.0)
                    self.epistemic_loop.priority_pct = eloop.get("priority_pct", 0.0)
                    self.epistemic_loop.last_gap_severity = eloop.get("gap_severity", "low")
        else:
            self.entity_stack = []
            self.confidence_score = 1.0
            self.turn_count = 0
            self.active_domain = "general"
            self.active_persona = "Assistant"
            self.gratification_count = 0
            self.session_start = time.time()
            self.session_history = []
            self.active_situation = None
            self.recent_thoughts = []
            self.boredom_score = 0.0
            self.volition_score = 0.0
            self.learning_velocity = 0.5
            self.last_system_output = ""
            self.calibration_active = False
            self.active_calibration_subject = ""

    def _add_to_session_history(self, input_text: str, logical_intent: str,
                                 response_text: str = None, entities: List[str] = None,
                                 realization_path: str = None):
        """Enhanced session history with turn pairs and entity tracking."""
        entry = {
            "turn_id": self.turn_count,
            "input": input_text,
            "logical_intent": logical_intent,
            "response": response_text,  # Now includes response
            "entities_mentioned": entities or [],
            "realization_path": realization_path,
            "conversation_state": self.conversation_flow.state.value,
            "timestamp": datetime.now().isoformat()
        }
        self.session_history.append(entry)
        # Keep last 15 turns (increased from 10)
        self.session_history = self.session_history[-15:]

    def _save_state(self):
        with open(self.state_path, 'w') as f:
            json.dump({
                "entity_stack": self.entity_stack,
                "confidence_score": self.confidence_score,
                "turn_count": self.turn_count,
                "active_domain": self.active_domain,
                "active_persona": self.active_persona,
                "gratification_count": self.gratification_count,
                "session_start": self.session_start,
                "session_history": self.session_history[-15:],  # Increased from 10
                "active_situation": self.active_situation,
                "recent_thoughts": self.recent_thoughts[-5:],
                "boredom_score": self.boredom_score,
                "volition_score": self.volition_score,
                "learning_velocity": self.learning_velocity,
                "last_system_output": self.last_system_output,
                "calibration_active": self.calibration_active,
                "active_calibration_subject": self.active_calibration_subject,
                "conversation_flow": self.conversation_flow.to_dict(),  # NEW: Save flow state
                "epistemic_loop": self.epistemic_loop.to_dict()  # NEW: Save epistemic metastate
            }, f, indent=2)

    def process_interaction(self, text):
        self.thoughts = [] # Clear for new turn
        # 0. Multi-intent Splitter (Task 1.3)
        if " and " in text.lower() or " but " in text.lower():
            sub_inputs = re.split(r" and | but ", text, flags=re.IGNORECASE)
            responses = []
            for sub_in in sub_inputs:
                res = self._execute_single_interaction(sub_in.strip())
                responses.append(res)
            
            # Combine responses for the user
            combined_text = " ".join([r["response"] for r in responses])
            final_res = responses[-1] # Use metadata from last intent
            final_res["response"] = combined_text
            final_res["thoughts"] = self.thoughts
            return final_res
        
        res = self._execute_single_interaction(text)
        res["thoughts"] = self.thoughts
        return res

    def _execute_single_interaction(self, text): #[Mark:ORCH_LOOP]
        self.turn_count += 1
        self.timer.update_interaction_time()
        
        # 0. Temporal Bias (Task 12.1)
        hour = datetime.now().hour
        is_morning = 5 <= hour < 12
        is_evening = 18 <= hour or hour < 5
        
        if is_morning:
            self.learning_velocity = min(1.0, self.learning_velocity + 0.05)
            self.volition_score = min(1.0, self.volition_score + 0.1)
            self.add_thought("Morning Bias: Escalating learning velocity and volition.")
        elif is_evening:
            self.learning_velocity = max(0.1, self.learning_velocity - 0.05)
            self.volition_score = max(0.0, self.volition_score - 0.05)
            self.add_thought("Evening Bias: Reflective state active. Dampening volition.")

        # 1. Handle Commands
        if text.startswith("/teach"):
            res = self._handle_teach(text)
            self._save_state()
            return res
        
        if text.startswith("/read"):
            # Usage: /read "Path to file" OR /read Content string
            content = ""
            path_match = re.search(r"/read\s+\"(.+?)\"", text)
            if path_match:
                f_path = get_path(path_match.group(1))
                if os.path.exists(f_path):
                    with open(f_path, 'r') as f: content = f.read()
                else:
                    return {"response": f"Error: File not found at {f_path}", "tokens": "[ERR: FILE_NOT_FOUND]"}
            else:
                content = text.replace("/read", "").strip()
            
            if content:
                return self._handle_deep_ingestion(content)

        if text.startswith("/dream"):
            return self._handle_scheduled_dream(text)

        if text.startswith("/situation"):
            return self._handle_situation_command(text)

        if text.startswith("/activity"):
            # Usage: /activity -t 5 -s "Entropy"
            t_match = re.search(r"-t\s+(\d+)", text)
            s_match = re.search(r"-s\s+\"(.+?)\"", text)
            
            duration = int(t_match.group(1)) if t_match else 5
            subject = s_match.group(1) if s_match else (self.entity_stack[0] if self.entity_stack else "General Logic")
            
            log_path = self.creative_engine.run_simulation(duration, subject)
            return {
                "tokens": f"[MODE: ACTIVITY] [SUBJECT: {subject}] [LOG: {log_path}]",
                "response": f"I have engaged in a creative reasoning activity regarding '{subject}' for {duration} cycles. Detailed thought-steps logged to {log_path}.",
                "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
                "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.0, "thought_event": "CREATIVE_SYNTHESIS"}
            }
        
        # 2. Initial Resolution
        resolved = self.resolver.get_logical_response(text)
        
        # 2.1 Instant Satiation Check (Task: resolving gaps right away)
        # If input has properties, check if they resolve something in the learning queue
        if resolved.get("properties_resolution"):
            what = resolved["5w1h_resolution"].get("what")
            target = None
            if what:
                clean_what = what.strip("?!.").lower()
                for art in ["a ", "an ", "the "]:
                    if clean_what.startswith(art): clean_what = clean_what[len(art):]
                target = clean_what
            elif self.entity_stack:
                target = self.entity_stack[0]
            
            if target and self.ingestor.mark_learned(target):
                resolved["gap_satiated"] = True
                self.boredom_score = 0.0 # Force reset
                self.add_thought(f"Instant Satiation: '{target}' resolved. Hunger (Boredom) weight collapsed.")

        # 3. Anaphora Check & Re-Resolution
        processed_text = text
        if self._contains_pronoun(text):
            processed_text = self._resolve_anaphora(text)
            if processed_text != text:
                # Re-resolve with the replaced entity
                resolved = self.resolver.get_logical_response(processed_text)
                # Re-check satiation after anaphora resolution
                if resolved.get("properties_resolution") and not resolved.get("gap_satiated"):
                     pass

        # 4. Inject System Signals
        resolved["system_signals"] = self.monitor.get_signals(processed_text)
        weighting = {"total_priority": 0.0, "thought_event": None} # Early Init
        
        # 4.0.0 Daily Routine & Cadence (Task 11.3 / 11.4)
        routine_match = self.timer.get_routine_match(self.routine_config)
        want_need_hits = len(resolved["hierarchy_analysis"].get("level_5_semantics", {}).get("volitional_proposition", []))
        intensity = min(want_need_hits / 3.0, 1.0)
        output_cadence = self.timer.get_output_cadence(intensity)
        
        if routine_match:
            weighting["thought_event"] = f"ROUTINE_MATCH: {routine_match['activity']}. Expecting {routine_match['expectation']}."

        resolved["system_state"] = {
            "confidence": self.confidence_score,
            "turn_count": self.turn_count,
            "entity_stack_depth": len(self.entity_stack),
            "interaction_type": self.interaction_type,
            "dialogue_mode": self.dialogue_mode,
            "sharing_willingness": self.sharing_willingness,
            "routine_match": routine_match,
            "output_cadence": output_cadence,
            "learning_velocity": self.learning_velocity,
            "last_system_output": self.last_system_output
        }
        resolved["active_situation"] = self.active_situation["name"] if self.active_situation else None
        resolved["epistemic_gap_detected"] = resolved.get("epistemic_gap_detected", False)
        resolved["session_history"] = self.session_history # Pass for repetition check

        # 4.0 Narrative Recall Check (Task 6.10)
        resolved["narrative_recall"] = None
        if HAS_VM and self.entity_stack:
            subject = self.entity_stack[0]
            matches = self.journal.search_narrative(subject, limit=1)
            if matches:
                resolved["narrative_recall"] = matches[0]
                self.thought_logger.log_thought({"event": "NARRATIVE_RECALL", "subject": subject, "match": matches[0]["activity"]})

        # 4.0.1 Comparative Logic Hook (Task 8.1)
        resolved["comparison_data"] = None
        if len(self.entity_stack) >= 2 and resolved["logical_intent"] == "INFORMATION_QUERY":
            sub1 = self.entity_stack[0]
            sub2 = self.entity_stack[1]
            c1 = self.km.get_concept(sub1)
            c2 = self.km.get_concept(sub2)
            if c1 and c2:
                # Find diverging properties
                p1 = c1.get("properties", {})
                p2 = c2.get("properties", {})
                divergence = {}
                for k in set(p1.keys()).union(set(p2.keys())):
                    if p1.get(k) != p2.get(k):
                        divergence[k] = (p1.get(k), p2.get(k))
                
                if divergence:
                    resolved["comparison_data"] = {"subjects": (sub1, sub2), "divergence": divergence}
                    resolved["logical_intent"] = "COMPARISON_QUERY"
                    self.thought_logger.log_thought({"event": "COMPARATIVE_ANALYSIS", "subjects": [sub1, sub2], "divergent_keys": list(divergence.keys())})

        # 4.1 Handle System Correction (Task 4.1)
        if resolved["logical_intent"] == "SYSTEM_CORRECTION":
             target = None
             new_def = None
             new_def_match = re.search(r"(?:actually|incorrect|wrong)\s+(?:a|an|the)?\s*(\w+)\s+(?:is|be)\s+(.*)", text, re.I)
             if new_def_match:
                 target = new_def_match.group(1).lower()
                 new_def = new_def_match.group(2).strip("?!. ")
             else:
                 new_def_match = re.search(r"(?:actually|is|be|wrong)\s+(?:a|an|the|is|are)?\s*(.*)", text, re.I)
                 if new_def_match:
                     new_def = new_def_match.group(1).strip("?!. ")
                     if self.entity_stack: target = self.entity_stack[0]

             if target and new_def:
                 self.km.save_concept(target, {"definition": new_def})
                 self.confidence_score = min(1.0, self.confidence_score + 0.1)
                 self.learning_velocity = min(1.0, self.learning_velocity + 0.1) # Boost velocity
                 return {
                     "tokens": f"[MODE: CORRECTION] [TARGET: {target}] [STATUS: UPDATED]",
                     "response": f"I have corrected my understanding. '{target}' is now indexed as '{new_def}'. Thank you for the clarification. My learning velocity is increasing.",
                     "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
                     "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 1.0, "thought_event": "KNOWLEDGE_REVISION"}
                 }

        # 4.1.1 Handle Phrasing Correction (Task 13.1)
        if resolved["logical_intent"] == "PHRASING_CORRECTION":
            critique = resolved["hierarchy_analysis"].get("level_6_pragmatics", {}).get("phrasing_critique")
            suggestion = resolved["hierarchy_analysis"].get("level_6_pragmatics", {}).get("phrasing_suggestion")

            suggested_text = None
            if suggestion:
                suggested_text = suggestion[0][0] if isinstance(suggestion[0], tuple) else suggestion[0]

            if suggested_text:
                self.add_thought(f"Phrasing Calibration: User suggested '{suggested_text}' over '{self.last_system_output}'.")
                self.learning_velocity = min(1.0, self.learning_velocity + 0.15)
                self.format_mgr.boost_weight("user_correction", 5.0)

                # Use new ConversationFlowManager instead of raw flags
                self.conversation_flow.transition(
                    ConversationState.CALIBRATING,
                    context={
                        "subject": suggested_text,
                        "original": self.last_system_output,
                        "awaiting": "explanation_or_selection"
                    }
                )
                # Keep legacy flag for backward compatibility
                self.calibration_active = True
                self.active_calibration_subject = suggested_text

                # Build response using ResponseBuilder
                self.response_builder.reset()
                self.response_builder.set_prefix(self.active_persona, self.active_situation.get("name") if self.active_situation else None)
                self.response_builder.set_core(
                    f"I understand. My previous phrasing '{self.last_system_output}' was suboptimal. "
                    f"I should have said: '{suggested_text}'. Which phrasing works better for you?"
                )
                self.response_builder.add_hook(0.8, "Could you explain why this is better?", True)
                self.response_builder.set_tokens(["[MODE: PHRASING_CALIBRATION]", "[VELOCITY: UP]", f"[STATE: {self.conversation_flow.state.value}]"])
                self.response_builder.set_stats({"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"})
                self.response_builder.set_meta(
                    system_confidence=self.confidence_score,
                    priority_weight=1.0,
                    thought_event="LINGUISTIC_RECALIBRATION",
                    conversation_state=self.conversation_flow.state.value
                )

                return self.response_builder.build(max_hooks=1)

        # 4.2 Handle Proactive Curiosity (Task 4.2)
        if "do you have any questions" in text.lower():
            return self._handle_proactive_curiosity(resolved)
        
        # 5. Update Active Domain and Persona
        self._update_active_domain(resolved)
        self._update_active_persona()
        
        # 6. Interaction Type Learning (defer full history entry until response generated)
        # Create preliminary entry - will update with response later
        self._pending_history_entry = {
            "input": text,
            "logical_intent": resolved["logical_intent"],
            "entities": list(self.entity_stack[:3]) if self.entity_stack else []
        }
        # Temporarily add for interaction type learning
        self.session_history.append({"input": text, "logical_intent": resolved["logical_intent"]})
        self.interaction_type = self.it_learner.learn_type(self.session_history)
        # Remove temporary entry (will add complete one at end)
        self.session_history.pop()
        
        # 7. Recursive Knowledge Update (Task 3.1) - BEFORE stack update
        if resolved.get("properties_resolution") and self.entity_stack:
            # Filter out dissonant properties from saving (Task 12.7)
            clean_props = {k: v for k, v in resolved["properties_resolution"].items() if "DISSONANCE_DETECTED" not in str(v)}
            
            if len(clean_props) < len(resolved["properties_resolution"]):
                weighting["thought_event"] = "SEMANTIC_DISSONANCE: Category mismatch detected. Blocking ingestion."

            if clean_props:
                # If the current turn identified a specific 'what', use it. 
                # Otherwise, use the top of the stack (likely anaphoric or continuous subject).
                what = resolved["5w1h_resolution"].get("what")
                if what:
                    clean_what = what.strip("?!.").lower()
                    for art in ["a ", "an ", "the "]:
                        if clean_what.startswith(art): clean_what = clean_what[len(art):]
                    target = clean_what
                else:
                    target = self.entity_stack[0]
                    
                self.km.save_concept(target, {"properties": clean_props})
                # Check if it was already marked learned in step 2.1
                if not resolved.get("gap_satiated") and self.ingestor.mark_learned(target):
                    resolved["gap_satiated"] = True
                    self.boredom_score = 0.0 # Force reset
                    self.add_thought(f"Gap Satiated: '{target}' integrated. Boredom reset.")

        # 8. Update Entity Stack
        self._update_entity_stack(resolved)
        
        # 9. Calculate Understanding Metrics
        stats = self._calculate_understanding_stats(processed_text, resolved)
        resolved["stats"] = stats # Inject into resolved for confidence logic

        # 9.0 EPISTEMIC FEEDBACK LOOP: Gap Analysis → Metastate Weights → Weighted Re-resolution
        gap_analysis = self.gap_analyzer.analyze_text(processed_text)
        metastate_weights = self.gap_analyzer.calculate_metastate_weights(gap_analysis)
        self.epistemic_loop.update_from_gap_analysis(metastate_weights)

        # Update confidence based on gap analysis understanding%
        self.confidence_score = (self.confidence_score + metastate_weights.understanding_pct) / 2.0

        # Get weighted 5W1H priorities for potential re-resolution
        weighted_5w1h_priorities = self.epistemic_loop.get_weighted_5w1h_priorities()
        resolved["weighted_5w1h_priorities"] = weighted_5w1h_priorities

        # If priority is high, perform weighted re-resolution
        if metastate_weights.priority_pct > 0.5:
            weighted_5w1h = self.resolver.resolve_5w1h_weighted(processed_text, weighted_5w1h_priorities)
            # Merge weighted results back into resolution (only if new values found)
            for slot, value in weighted_5w1h.items():
                if value and not resolved["5w1h_resolution"].get(slot):
                    resolved["5w1h_resolution"][slot] = value
                    self.add_thought(f"Weighted 5W1H: Filled '{slot}' slot with priority-boosted extraction: {value}")

        # Determine conversation format based on metastate
        conversation_format = self.epistemic_loop.get_conversation_format()
        resolved["conversation_format"] = conversation_format

        # Log epistemic state
        self.add_thought(f"Epistemic Loop: understanding={metastate_weights.understanding_pct:.2f}, "
                        f"priority={metastate_weights.priority_pct:.2f}, "
                        f"gap_severity={metastate_weights.gap_severity}, "
                        f"format={conversation_format}")

        # 9.0.1 ACTIVITY SUGGESTION: Grounded activity based on epistemic state
        if self.activity_bridge and metastate_weights.gap_severity in ['critical', 'high']:
            try:
                suggestion = self.activity_bridge.suggest_activity(
                    metastate_weights,
                    gap_analysis,
                    context=processed_text
                )

                if suggestion:
                    self.add_thought(f"Activity Suggested: {suggestion['activity_type']} - {suggestion['reason']}")

                    # Queue clarification question if gaps detected
                    if gap_analysis.unrecognized_tokens and self.question_queue:
                        self.question_queue.enqueue_gap_question(gap_analysis, metastate_weights)
                        self.add_thought(f"Gap question queued for {len(gap_analysis.unrecognized_tokens)} terms")

                    # Journal mark integration
                    if HAS_VM and self.journal:
                        mark_id = f"ACTIVITY_SUGGESTION_{hash(processed_text) % 10000}"
                        self.journal.add_note(
                            f"Activity: {suggestion['activity_type']} - {suggestion['reason']} (gaps: {len(gap_analysis.unrecognized_tokens)})",
                            author="i.epistemic",
                            mark=f"#[MARK:{{{mark_id}}}]"
                        )
                        self.add_thought(f"Journal mark: #[MARK:{{{mark_id}}}]")

                        # Link to relevant capabilities if any
                        if suggestion.get('relevant_capabilities') and self.capability_registry:
                            for cap_info in suggestion['relevant_capabilities']:
                                # Find capability by tool name
                                for cap in self.capability_registry.capabilities.values():
                                    if cap.tool_name == cap_info['tool']:
                                        self.capability_registry.add_journal_mark(cap.tool_id, f"#[MARK:{{{mark_id}}}]")
                                        break

                    # Store suggestion for potential later use
                    resolved["activity_suggestion"] = suggestion
            except Exception as e:
                self.add_thought(f"Activity suggestion failed: {e}")

        # Trigger audit --diff if gap severity is critical/high
        if self.epistemic_loop.should_trigger_audit_diff():
            self.add_thought(f"Epistemic Loop: CRITICAL GAP detected. Triggering audit --diff for pattern discovery.")
            pattern_weights = self._trigger_audit_diff(processed_text, gap_analysis)
            if pattern_weights:
                self._apply_morphological_weight_adjustment(pattern_weights)

        # 9.1 Thought Execution: Self-Resolve Unknowns
        sim_thoughts = self.thought_engine.resolve_unknowns(processed_text, resolved, stats)
        for t in sim_thoughts: self.add_thought(t)

        # 9.1 Boredom Logic (Task 11.1)
        if stats.get("lexical_pct", 0) > 0.8:
            self.boredom_score = min(1.0, self.boredom_score + 0.1)
        else:
            self.boredom_score = max(0.0, self.boredom_score - 0.05)

        # 10. Dialogue Mode and Altruism
        self.dialogue_mode = self.mode_tracker.determine_mode(stats, self.interaction_type, self.turn_count)
        self.sharing_willingness = self.altruism_mgr.calculate(resolved["system_signals"], self.gratification_count)
        
        # 11. Auto-Ingest Unknowns
        self.ingestor.capture_unknowns(processed_text, stats, resolved)
        
        # 12. Check Memory
        memory_match = self._query_memory(resolved)
        
        # 13. Metacognitive Weighting
        new_weighting = self._calculate_priority_weights(resolved)
        # Merge while preserving existing events (like ROUTINE_MATCH)
        if weighting.get("thought_event"):
            new_weighting["thought_event"] = weighting["thought_event"] + " | " + (new_weighting["thought_event"] or "")
        weighting = new_weighting
        
        # 14. Dynamic Confidence Correction
        self._evaluate_understanding(resolved, weighting)
        
        # 15. Log Interaction
        logs = self.logger.log_interaction(processed_text, resolved, stats)
        
        # 16. Sequential Similarity Check
        self._check_sequential_similarity(processed_text, logs)
        
        # 17. Gratification Detection
        g_hits = self.grat_tracker.check(text)
        if g_hits:
            self.gratification_count += g_hits
            self.confidence_score = min(1.0, self.confidence_score + (0.05 * g_hits))
            self.boredom_score = max(0.0, self.boredom_score - 0.2) # Interest restored by feedback
            # Boost weight for the path taken in the PREVIOUS turn (Task 9.3)
            print(f"DEBUG: session_history length: {len(self.session_history)}")
            if len(self.session_history) > 1:
                last_path = self.session_history[-2].get("realization_path")
                print(f"DEBUG: last_path found: {last_path}")
                if last_path:
                    self.format_mgr.boost_weight(last_path, g_hits)

        # 18. Unresolved Question Tracking
        if not memory_match and resolved["logical_intent"] == "INFORMATION_QUERY":
            self.question_pool.add(processed_text, "No memory hit for query")

        # 18.5 Sequence Completion Check (Task 6.8)
        self.sequence_completed = False
        if self.interaction_type == "LEARNING_EXCHANGE" or resolved["logical_intent"] == "LEARNING_EXCHANGE":
            # Scan stack for the most likely subject that we are currently 'learning'
            for target in self.entity_stack:
                concept = self.km.get_concept(target)
                if concept:
                    props = concept.get("properties", {})
                    core_props = ["material", "weight", "origin", "magnitude", "cost"]
                    if all(props.get(p) for p in core_props): # Ensure all are present AND non-empty
                        self.sequence_completed = True
                        # Epistemic Infinity Pivot (Task 6.9)
                        pivots = {"general": "domain_technical", "domain_technical": "domain_physics", "domain_physics": "domain_academic"}
                        new_domain = pivots.get(self.active_domain, "domain_academic")
                        if new_domain != self.active_domain:
                            old_domain = self.active_domain
                            self.active_domain = new_domain
                            weighting["thought_event"] = f"EPISTEMIC_PIVOT: Escalating resolution from {old_domain} to {new_domain}."
                            self.thought_logger.log_thought({"event": "EPISTEMIC_PIVOT", "from": old_domain, "to": new_domain})
                        break # Found a completed sequence target

        # 18.6 Activity Suggestion Trigger (Task 11.2)
        suggested_activity = None
        if resolved["logical_intent"] == "ACTIVITY_REQUEST" or self.boredom_score > 0.7:
            learning_top = self.ingestor.get_top_candidate()
            suggested_activity = self.activity_engine.suggest(self.active_domain, learning_candidate=learning_top)
            weighting["thought_event"] = f"ACTIVITY_TRIGGER: Suggesting {suggested_activity} for {self.active_domain} context."

        # 18.7 Volition Gradient (Task 10.1)
        # want_need_hits was calculated in 4.0.0
        self.volition_score = min(1.0, self.volition_score + (intensity * 0.2))
        if self.turn_count % 5 == 0: self.volition_score *= 0.8 # Natural decay

        # 19. Save State
        self._save_state()
        
        # 18. Version & Journal Hooks
        if HAS_VM:
            # Snapshot on task discovery
            if os.path.exists(get_path("regex_project/tasks/task.json")):
                self.backup.create_snapshot("orchestrator.py")
                os.remove(get_path("regex_project/tasks/task.json"))
            
            # Daily Journal Entry
            self.journal.add_entry(activity=f"Processed: {text[:30]}...", tasks_planned=[])

        # 19. Log Internal Reasoning
        self.thought_logger.log_thought({
            "input": processed_text,
            "weights": weighting,
            "confidence_post": self.confidence_score,
            "active_domain": self.active_domain,
            "active_persona": self.active_persona,
            "interaction_type": self.interaction_type,
            "journal_relevance": stats.get("journal_relevance", 0),
            "dream_influence": stats.get("dream_influence", 0),
            "boredom_score": self.boredom_score
        })
        
        # 19. Generate Output Tokens
        output = self._format_token_output(resolved, weighting, memory_match, stats)
        
        # 19.5 Update Recent Thoughts (Task 5.3)
        display_event = weighting["thought_event"] if weighting["thought_event"] else "GENERAL_RESOLUTION"
        self.recent_thoughts.append(display_event)
        self.recent_thoughts = self.recent_thoughts[-5:] # Keep last 5

        # 20. Realize Response
        curiosity_level = 1.0 - self.confidence_score
        # Contextual boost if journal/dream matches
        if stats.get("journal_relevance", 0) > 0.5 or stats.get("dream_influence", 0) > 0.5:
            curiosity_level = min(1.0, curiosity_level + 0.2)

        # Multi-turn Teaching Resolution (Task: multi turn 'teaching')
        # IMPROVED: Now accepts multiple resolution patterns, not just "why"
        if self.conversation_flow.state == ConversationState.CALIBRATING or self.calibration_active:
            # Tick the flow manager to track turns in this state
            auto_reset = self.conversation_flow.tick()

            # Handle auto-reset from flow manager (sync legacy flag)
            if auto_reset:
                self.add_thought("Calibration Timeout: Auto-resetting after max turns without resolution.")
                self.calibration_active = False
            else:
                # Check for various resolution triggers
                resolution_triggers = [
                    resolved["5w1h_resolution"].get("why"),                    # User explained why
                    resolved["logical_intent"] == "INFORMATION_QUERY",         # User asked follow-up
                    resolved["logical_intent"] == "GRATIFICATION",             # User said thanks/good
                    resolved["logical_intent"] == "EMOTIONAL_RESPONSE",        # User acknowledged
                    "prefer" in text.lower(),                                  # User stated preference
                    "better" in text.lower(),                                  # User compared
                    "because" in text.lower(),                                 # User gave reason
                    any(w in text.lower() for w in ["yes", "no", "ok", "okay", "fine", "got it"]),  # Confirmation
                ]

                if any(resolution_triggers):
                    self.add_thought(f"Calibration Resolved: User provided feedback. State: {self.conversation_flow.state.value}")
                    self.learning_velocity = min(1.0, self.learning_velocity + 0.2)
                    self.calibration_active = False
                    self.conversation_flow.reset()

        if resolved.get("epistemic_gap_detected") and weighting["total_priority"] > 0.5:
            response_text, path_id = self._generate_learning_prompt(resolved)
        else:
            response_text, path_id = self.engine.realize(
                resolved, 
                self.active_domain, 
                self.active_persona, 
                memory_match, 
                resolved.get("properties_resolution", {}),
                self.sharing_willingness,
                self.dialogue_mode,
                self.interaction_type,
                curiosity_level,
                self.recent_thoughts, # Pass for thought reminders
                self.sequence_completed,
                self.boredom_score,
                suggested_activity,
                routine_match,
                output_cadence,
                self.volition_score,
                self.calibration_active # NEW: pass calibration state
            )
        
        # 21. Persona Consistency Guard
        response_text = self.persona_guard.validate(response_text, self.active_persona)
        
        # 21.1 Standard Response Criteria (Task 13.4)
        if len(text.split()) < 3 and "hello" in text.lower() and self.confidence_score > 0.9:
            response_text = f"[{self.active_persona} Mode] Hello! How can I assist you today?"
            self.add_thought("Standard Criteria: High confidence + simple greeting. Forcing baseline.")

        # Record complete session history entry with response (using enhanced method)
        self._add_to_session_history(
            input_text=text,
            logical_intent=resolved["logical_intent"],
            response_text=response_text,
            entities=self._pending_history_entry.get("entities", []),
            realization_path=path_id
        )
        self.last_system_output = response_text # Store for PHRASING_CORRECTION (Task 13.1)

        # 21.2 Understanding Gap Follow-up (Task 13.5)
        if self.confidence_score < 0.4 and random.random() < self.learning_velocity:
            gap_follow_ups = [
                " I feel there are still gaps in my understanding of our current context. Could you elaborate on our primary subject?",
                " My internal model is signaling low confidence. Are we aligned on the core goals here?",
                " I detect linguistic friction. Should we pause to recalibrate our terminology?"
            ]
            response_text += random.choice(gap_follow_ups)
            self.add_thought("Gap Follow-up: Low confidence triggered proactive inquiry.")

        # 22. Conversational Training Hook
        train_res = self.trainer.evaluate_response(text, response_text, self.active_domain)
        if train_res["score"] > 0:
            self.add_thought(f"Training Score: {train_res['score']:.2f} ({train_res['benchmark_id']})")
            if train_res["score"] < 0.5:
                self.add_thought(f"Training Feedback: {train_res['improvement_suggestion']}")

        return {
            "tokens": output,
            "response": response_text,
            "stats": stats,
            "metacognitive_state": {
                "system_confidence": self.confidence_score,
                "priority_weight": weighting["total_priority"],
                "thought_event": display_event,
                "memory_match": True if memory_match else False,
                "resolved_text": processed_text,
                "active_domain": self.active_domain,
                "active_persona": self.active_persona,
                "interaction_type": self.interaction_type,
                "active_situation": self.active_situation["name"] if self.active_situation else "None",
                "dialogue_mode": self.dialogue_mode,
                "sharing_willingness": f"{self.sharing_willingness:.2%}",
                "journal_relevance": f"{stats.get('journal_relevance', 0):.2%}",
                "dream_influence": f"{stats.get('dream_influence', 0):.2%}",
                "sequence_completed": self.sequence_completed,
                "realization_path": path_id,
                "boredom_score": f"{self.boredom_score:.2%}",
                "volition_score": f"{self.volition_score:.2%}",
                "suggested_activity": suggested_activity
            }
        }

    def _handle_proactive_curiosity(self, resolved):
        """
        Handles 'Do you have any questions?' by scanning for gaps.
        """
        # 1. Scan Entity Stack for Missing Properties (B.2 / Task 4.5)
        for entity in self.entity_stack:
            concept = self.km.get_concept(entity)
            if concept:
                props = concept.get("properties", {})
                missing = [p for p in ["material", "weight", "origin", "magnitude", "cost"] if p not in props]
                if missing:
                    target_p = random.choice(missing)
                    return {
                        "tokens": f"[MODE: PROACTIVE] [TARGET: {entity}] [GAP: {target_p}]",
                        "response": f"Yes. I'm currently expanding my model of '{entity}'. Could you clarify its {target_p}?",
                        "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
                        "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.8, "thought_event": "PROACTIVE_INQUIRY"}
                    }
        
        # 2. Scan Candidate Entities for High-Frequency Unknowns (Task 4.3)
        with open(get_path("regex_project/candidate_entities.json"), 'r') as f:
            candidates = json.load(f)
        
        top_candidates = sorted(candidates["candidates"].items(), key=lambda x: x[1], reverse=True)
        if top_candidates:
            target_u = top_candidates[0][0]
            return {
                "tokens": f"[MODE: PROACTIVE] [TARGET: {target_u}] [GAP: DEFINITION]",
                "response": f"Actually, I've encountered the term '{target_u}' multiple times recently but lack a formal definition. What exactly is it?",
                "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
                "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.9, "thought_event": "UNKNOWN_SOLICITATION"}
            }
            
        return {
            "tokens": f"[MODE: PROACTIVE] [STATUS: SATIATED]",
            "response": "At this moment, my hierarchical model is stable and I have no pending epistemic gaps for the current context.",
            "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L2_INFERENTIAL"},
            "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.1, "thought_event": "STABILITY_CHECK"}
        }

    def _contains_pronoun(self, text):
        pronouns = ["it", "that", "this"]
        for p in pronouns:
            if re.search(rf"\b{p}\b", text, re.IGNORECASE):
                return True
        return False

    def _update_active_domain(self, resolved):
        # Count matches per domain
        counts = {}
        for level, cats in resolved["hierarchy_analysis"].items():
            if level.startswith("domain_"):
                # Sum unique matches to avoid double counting from sub-categories
                unique_matches = set()
                for matches in cats.values():
                    for m in matches:
                        if isinstance(m, str): unique_matches.add(m.lower())
                
                if unique_matches:
                    counts[level] = len(unique_matches)
        
        if counts:
            # Boost priority for scholarly and casual tones over purely technical data
            priority = {"domain_informal": 5, "domain_academic": 4, "domain_technical": 1}
            best_domain = max(counts.keys(), key=lambda d: (counts[d] * priority.get(d, 1)))
            self.active_domain = best_domain
        else:
            # Revert to general if no specific domains detected (Task 6.1 / Mode Inertia fix)
            self.active_domain = "general"

    def _update_active_persona(self):
        mapping = {
            "domain_informal": "Mate",
            "domain_academic": "Scholar",
            "domain_technical": "Engineer",
            "general": "Assistant"
        }
        self.active_persona = mapping.get(self.active_domain, "Assistant")

    def _update_entity_stack(self, resolved):
        # Extract entities from 5W1H, technical domains, and syntax levels
        new_entities = []
        what = resolved["5w1h_resolution"].get("what")
        
        # Track previous top entity for momentum check
        prev_top = self.entity_stack[0] if self.entity_stack else None

        # Filter out common process verbs from being the 'top' entity for anaphora
        process_verbs = ["analyze", "evaluate", "verify", "synthesize", "check", "run", "do", "learn", "understand", "made", "integrate", "using"]
        stop_words = ["the", "this", "that", "those", "these", "and", "but", "with", "from", "what", "which", "is", "are", "was", "were", "how", "why", "who", "where", "when", "how", "any", "you", "your", "mine", "ours", "huge", "small", "large", "massive", "cost", "price", "weight", "origin", "material", "they", "both", "them"]

        def is_property_value(val):
            # Matches "500kg", "100m", "$50", etc.
            if val.replace(".","").isdigit(): return True
            if re.search(r"^\d+.*[a-zA-Z]+$", val): return True
            if val.startswith(("$", "£", "€", "¥")): return True
            # Check against stop_words for property-like words
            if val.lower() in stop_words: return True
            # Check against current resolved properties
            if val.lower() in [v.lower() for v in resolved.get("properties_resolution", {}).values()]: return True
            return False

        if what:
            self.add_thought(f"Extracted subject slot: {what}")
            # Handle joined subjects (e.g. "quantum server and standard server")
            subjects = re.split(r"\s+and\s+", what, flags=re.IGNORECASE)
            for clean_what in subjects:
                clean_what = clean_what.strip("?!.").lower()
                for art in ["a ", "an ", "the "]:
                    if clean_what.startswith(art):
                        clean_what = clean_what[len(art):]
                
                if clean_what not in process_verbs and clean_what not in stop_words and not is_property_value(clean_what):
                    new_entities.append(clean_what)
                    # If it's a phrase, also add individual significant words to ensure they are available
                    if len(clean_what.split()) > 1:
                        words = [w for w in clean_what.split() if len(w) > 3 and w not in stop_words and not is_property_value(w)]
                        new_entities.extend(words)
        
        # Capture from domains and syntax (noun phrases)
        search_levels = ["domain_technical", "domain_academic", "domain_meta", "entities_properties", "entities_temporal", "level_4_syntax"]
        for level in search_levels:
            if level in resolved["hierarchy_analysis"]:
                for cat, matches in resolved["hierarchy_analysis"][level].items():
                    for m in matches:
                        val = m[0] if isinstance(m, tuple) else m
                        if isinstance(val, str) and len(val) > 2:
                            val_lower = val.lower().strip()
                            # Reject purely numeric or short values from domains as main entities
                            if val_lower not in new_entities and val_lower not in process_verbs and val_lower not in stop_words and not is_property_value(val_lower):
                                new_entities.append(val_lower)
            
        if new_entities:
            seen = set()
            unique_new = [x for x in new_entities if not (x in seen or seen.add(x))]
            
            # SUBJECT SWITCH CHECK (Momentum)
            if prev_top and unique_new and unique_new[0] != prev_top:
                self.confidence_score = max(0.1, self.confidence_score - 0.1)
                resolved["subject_switch"] = True
            
            # Prepend new entities, maintaining order (most specific/phrase first)
            self.add_thought(f"Stacking entity candidates: {unique_new}")
            self.entity_stack = (unique_new + self.entity_stack)
            final_stack = []
            for item in self.entity_stack:
                if item not in final_stack:
                    final_stack.append(item)
            self.entity_stack = final_stack[:10]

    def _resolve_anaphora(self, text):
        """
        IMPROVED: Context-aware anaphora resolution with:
        - Multiple pronoun instance handling (first vs subsequent)
        - Session history context
        - Plural pronoun support (they/them)
        - Position-aware resolution
        """
        if not self.entity_stack: return text

        # Safe Entity Filter
        stop_words = {"the", "this", "that", "those", "these", "and", "but", "with", "from",
                      "what", "which", "is", "are", "was", "were", "how", "why", "who",
                      "where", "when", "any", "you", "your", "because", "it"}

        safe_entities = [e for e in self.entity_stack if e not in stop_words and len(e) > 3]
        if not safe_entities: return text

        processed = text

        # Get context from recent session history for smarter resolution
        recent_entities = []
        for entry in self.session_history[-3:]:
            if "entities_mentioned" in entry:
                recent_entities.extend(entry["entities_mentioned"])

        # Priority: entities mentioned in conversation flow context
        if self.conversation_flow.pending_context.get("subject"):
            context_subject = self.conversation_flow.pending_context["subject"]
            if context_subject not in safe_entities:
                safe_entities.insert(0, context_subject)

        # Track pronoun occurrences for multi-instance handling
        pronoun_counts = {}

        def resolve_pronoun(match, pronoun_type):
            """Resolve a single pronoun match with context awareness."""
            pronoun = match.group(0)
            pronoun_lower = pronoun.lower()

            # Track occurrence count for this pronoun
            count = pronoun_counts.get(pronoun_lower, 0)
            pronoun_counts[pronoun_lower] = count + 1

            # Determine stack index based on pronoun type and occurrence
            if pronoun_lower in ["it", "this"]:
                # First occurrence -> most recent entity, subsequent -> same
                idx = 0
            elif pronoun_lower == "that":
                # "that" often refers to something mentioned earlier
                idx = min(1, len(safe_entities) - 1) if len(safe_entities) > 1 else 0
            elif pronoun_lower in ["they", "them", "their"]:
                # Plural - try to find a plural entity or use first entity
                plural_entities = [e for e in safe_entities if e.endswith("s") or " and " in e]
                if plural_entities:
                    return plural_entities[0]
                idx = 0
            elif pronoun_lower in ["he", "him", "his", "she", "her"]:
                # Personal pronouns - look for person names (capitalized in original)
                person_entities = [e for e in self.entity_stack if e[0].isupper() and len(e.split()) <= 2]
                if person_entities:
                    return person_entities[0]
                idx = 0
            else:
                idx = 0

            # Handle multiple occurrences: second "it" might refer to different entity
            if count > 0 and len(safe_entities) > 1:
                idx = min(count, len(safe_entities) - 1)

            if idx < len(safe_entities):
                replacement = safe_entities[idx]
                # Preserve capitalization if at start of sentence
                if match.start() == 0 or (match.start() > 0 and text[match.start()-1] in ".!?"):
                    replacement = replacement.capitalize()
                self.add_thought(f"Anaphora: '{pronoun}' -> '{replacement}' (occurrence {count + 1})")
                return replacement

            return pronoun  # No replacement available

        # Define pronouns to resolve with their patterns
        pronoun_patterns = [
            (r"\bit\b", "it"),
            (r"\bthis\b", "this"),
            (r"\bthat\b", "that"),
            (r"\bthey\b", "they"),
            (r"\bthem\b", "them"),
            (r"\btheir\b", "their"),
        ]

        for pattern, ptype in pronoun_patterns:
            processed = re.sub(
                pattern,
                lambda m, pt=ptype: resolve_pronoun(m, pt),
                processed,
                flags=re.IGNORECASE
            )

        return processed

    def _check_sequential_similarity(self, text, logs):
        if len(logs) < 2: return
        
        # Check against last 5 interactions
        recent = logs[-6:-1]
        for entry in recent:
            if text.lower() == entry["input"].lower():
                self.confidence_score = max(0.1, self.confidence_score - 0.1)
                # Repetition detected - logic could be expanded for complex patterns
                break

    def _calculate_understanding_stats(self, text, resolved):
        words = [w.strip("?!.,").lower() for w in text.split()]
        if not words:
            return {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L0_SILENT", "layer_validation": {}}
            
        # 1. Granular Layer Validation (Task 5.1 / 5.6)
        layer_validation = {}
        all_recognized = set()
        
        # We scan master_regex to identify which categories are INCLUSIVE
        for level, categories in self.resolver.master_regex.items():
            level_matches = 0
            total_categories = len(categories)
            
            for cat, pattern in categories.items():
                if cat in resolved["hierarchy_analysis"].get(level, {}):
                    matches = resolved["hierarchy_analysis"][level][cat]
                    level_matches += 1
                    for m in matches:
                        val = m[0] if isinstance(m, tuple) else m
                        if isinstance(val, str):
                            for word in val.lower().split():
                                all_recognized.add(word)
            
            layer_validation[level] = level_matches / total_categories if total_categories > 0 else 0

        # 2. 5W1H Cycle Validation (Task 5.5)
        five_ws = resolved["5w1h_resolution"]
        slots_filled = sum(1 for v in five_ws.values() if v is not None)
        layer_validation["5w1h_cycle"] = slots_filled / 6.0

        # 3. Journal Relevance Hook (Task 5.7)
        journal_relevance = 0.0
        if HAS_VM and self.journal.entries:
            recent_activities = " ".join([e.get("activity", "") for e in self.journal.entries[-5:]]).lower()
            overlap = set(words).intersection(set(recent_activities.split()))
            journal_relevance = min(len(overlap) / 10.0, 1.0)
        
        # 4. Dream/Story Influence (Task 5.8)
        dream_influence = 0.0
        dream_dir = get_path("regex_project/dream")
        if os.path.exists(dream_dir):
            dream_files = [f for f in os.listdir(dream_dir) if f.startswith("dream_")]
            if dream_files:
                latest_dream = sorted(dream_files)[-1]
                with open(os.path.join(dream_dir, latest_dream), 'r') as f:
                    dream_data = json.load(f)
                    story = dream_data.get("dream_story", "").lower()
                    overlap = set(words).intersection(set(story.split()))
                    dream_influence = min(len(overlap) / 5.0, 1.0)

        # 5. Lexical & Syntactic %
        lex_count = sum(1 for w in words if w in all_recognized)
        # Also check 5W1H values for lexical recognition
        for val in five_ws.values():
            if val:
                val_words = val.lower().split()
                lex_count += sum(1 for w in words if w in val_words and w not in all_recognized)

        lex_pct = min(lex_count / len(words), 1.0)
        syn_pct = layer_validation.get("level_4_syntax", 0)
        
        # 6. Boredom Logic - Gap Resolution Modifier (Task: boredom resolved by gaps)
        # If the input resolved a specific gap, boredom drops to 0 immediately
        if resolved.get("gap_satiated"):
            self.boredom_score = 0.0
        elif lex_pct > 0.8:
            self.boredom_score = min(1.0, self.boredom_score + 0.1)
        else:
            self.boredom_score = max(0.0, self.boredom_score - 0.05)

        # Cognition Level Logic
        if syn_pct > 0.3 or layer_validation.get("level_7_discourse", 0) > 0:
            cog_level = "L2_INFERENTIAL"
        elif lex_pct > 0.5:
            cog_level = "L1_FOUNDATIONAL"
        else:
            cog_level = "L0_ATOMIC"
            
        return {
            "lexical_pct": lex_pct, 
            "syntactic_pct": syn_pct, 
            "cognition_level": cog_level,
            "layer_validation": layer_validation,
            "journal_relevance": journal_relevance,
            "dream_influence": dream_influence,
            "boredom_score": self.boredom_score
        }

    def _handle_deep_ingestion(self, content):
        """
        Processes multi-line content to fill 5W1H and properties.
        """
        lines = content.split('\n')
        entities_found = 0
        props_found = 0
        
        for line in lines:
            if not line.strip(): continue
            resolved = self.resolver.get_logical_response(line)
            
            # Identify Subject
            what = resolved["5w1h_resolution"].get("what")
            if what:
                clean_what = what.strip("?!. ").lower()
                for art in ["a ", "an ", "the "]:
                    if clean_what.startswith(art): clean_what = clean_what[len(art):]
                
                # Update Knowledge Base
                if resolved.get("properties_resolution"):
                    self.km.save_concept(clean_what, {"properties": resolved["properties_resolution"]})
                    props_found += len(resolved["properties_resolution"])
                
                entities_found += 1
        
        self._save_state()
        return {
            "tokens": f"[MODE: DEEP_INGESTION] [ENTITIES: {entities_found}] [PROPS: {props_found}]",
            "response": f"Analytical synthesis complete. I have processed the source content and integrated {entities_found} entities with {props_found} total properties into my active model.",
            "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
            "metacognitive_state": {"system_confidence": 1.0, "priority_weight": 1.0, "thought_event": "SCHOLARLY_SYNTHESIS"}
        }

    def _handle_situation_command(self, text):
        # Usage: /situation list OR /situation activate [id]
        if "list" in text:
            with open(get_path("regex_project/situation_pool.json"), "r") as f:
                sits = json.load(f)
            names = [f"{s['id']}: {s['name']}" for s in sits["situations"]]
            return {
                "response": f"Available Situations: {', '.join(names)}",
                "tokens": "[MODE: SITUATION] [LIST]",
                "stats": {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L1_FOUNDATIONAL"},
                "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.0, "thought_event": "SITUATION_INQUIRY"}
            }
        
        match = re.search(r"activate\s+(\w+)", text)
        if match:
            sit_id = match.group(1)
            with open(get_path("regex_project/situation_pool.json"), "r") as f:
                sits = json.load(f)
            for s in sits["situations"]:
                if s["id"] == sit_id:
                    self.active_situation = s
                    self._save_state()
                    return {
                        "response": f"SITUATION ACTIVATED: {s['name']}. {s['description']}",
                        "tokens": f"[MODE: SITUATION] [ACTIVE: {sit_id}]",
                        "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L2_INFERENTIAL"},
                        "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 1.0, "thought_event": "SITUATION_CHANGE"}
                    }
        
        return {
            "response": "Usage: /situation list OR /situation activate [id]",
            "tokens": "[ERR: MALFORMED_SIT]",
            "stats": {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L0_ATOMIC"},
            "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.0, "thought_event": "ERROR"}
        }

    def _activate_random_situation(self):
        with open(get_path("regex_project/situation_pool.json"), "r") as f:
            sits = json.load(f)
        self.active_situation = random.choice(sits["situations"])
        self._save_state()

    def _handle_scheduled_dream(self, text):
        # Parse /dream -min X -max Y
        min_match = re.search(r"-min\s+(\d+)", text)
        max_match = re.search(r"-max\s+(\d+)", text)
        
        min_t = int(min_match.group(1)) if min_match else 1
        max_t = int(max_match.group(1)) if max_match else 5
        dream_time = random.randint(min_t, max_t)
        
        dreamer = DreamState()
        analysis = dreamer.analyze()
        
        # Simulate processing time
        time.sleep(min(dream_time, 2)) # Caps wait for real-time responsiveness
        
        # Generate Novel Reasoning Log
        story_gen = NovelStoryGenerator(get_path("regex_project/knowledge_base.json"), get_path("regex_project/situation_pool.json"))
        novel_story = story_gen.generate()
        
        log_id = int(time.time())
        log_path = get_path(f"regex_project/dream/dream_{log_id}_log.json")
        
        reasoning_data = {
            "dream_id": log_id,
            "duration_induced": dream_time,
            "internal_analysis": analysis,
            "metacognitive_reflection": f"Observed {analysis['total_logs_analyzed']} interactions. System confidence at {self.confidence_score:.2f}.",
            "novel_synthesis": f"Inferred that {len(analysis['top_gaps'])} concepts are currently forming a new sub-domain cluster.",
            "dream_story": novel_story
        }
        
        with open(log_path, 'w') as f:
            json.dump(reasoning_data, f, indent=2)
            
        return {
            "tokens": f"[MODE: DREAM] [DURATION: {dream_time}] [LOG: {log_id}]",
            "response": f"I have completed a scheduled internal analysis cycle ({dream_time} units). Insights have been posted to {log_path}.",
            "stats": {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L3_INTROSPECTIVE"},
            "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.0, "thought_event": "SCHEDULED_INTROSPECTION"}
        }

    def _handle_teach(self, text):
        # Simple parser for: /teach CONCEPT is DEFINITION
        parts = text.replace("/teach", "").split(" is ", 1)
        if len(parts) == 2:
            concept = parts[0].strip()
            definition = parts[1].strip()
            
            is_consistent, old_val = self.km.check_consistency(concept, definition)
            if not is_consistent:
                return {
                    "tokens": f"[MODE: TEACH] [CONCEPT: {concept}] [STATUS: CONTRADICTION]",
                    "response": f"I detect a logical contradiction. I previously learned that '{concept}' is '{old_val}'. Is this a revision or a separate classification?",
                    "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L3_INTROSPECTIVE"},
                    "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 1.0, "thought_event": "LOGICAL_INCONSISTENCY"}
                }
            
            self.km.save_concept(concept, {"definition": definition, "timestamp": "now"})
            return {
                "tokens": f"[MODE: TEACH] [CONCEPT: {concept}] [STATUS: LEARNED]",
                "response": f"I have recorded that '{concept}' is '{definition}'. My understanding of this entity is now updated.",
                "stats": {"lexical_pct": 1.0, "syntactic_pct": 1.0, "cognition_level": "L1_FOUNDATIONAL"},
                "metacognitive_state": {"system_confidence": 1.0, "priority_weight": 1.0, "thought_event": "KNOWLEDGE_ACQUISITION"}
            }
        return {
            "response": "Usage: /teach [concept] is [definition]",
            "tokens": "[ERR: MALFORMED_TEACH]",
            "stats": {"lexical_pct": 0, "syntactic_pct": 0, "cognition_level": "L0_ATOMIC"},
            "metacognitive_state": {"system_confidence": self.confidence_score, "priority_weight": 0.0, "thought_event": "ERROR"}
        }

    def _query_memory(self, resolved):
        """
        Enhanced memory query with fuzzy overlap and multi-slot candidate extraction.
        """
        input_text = resolved["input"].lower().strip("?!.")
        
        candidates = []
        # Extract from all 5W1H slots (who, what, where, why, how)
        for slot, val in resolved["5w1h_resolution"].items():
            if val:
                # Skip metadata slots that start with underscore
                if slot.startswith("_"):
                    continue
                # Handle both string and list values
                if isinstance(val, list):
                    candidates.extend([str(v).strip("?").lower() for v in val])
                elif isinstance(val, str):
                    clean_val = val.strip("?").lower()
                    candidates.append(clean_val)
                    # Also add individual words if the slot is a phrase
                    if len(clean_val.split()) > 1:
                        candidates.extend(clean_val.split())
        
        candidates.append(input_text)
        
        # Add stack entities as candidates if input is short or contains pronouns
        if len(input_text.split()) < 4 or self._contains_pronoun(input_text):
            candidates.extend(self.entity_stack[:3])

        best_match = None
        max_score = 0

        # Unique candidates only, preserving order
        seen_c = set()
        unique_candidates = [x for x in candidates if x and not (x in seen_c or seen_c.add(x))]

        for c in unique_candidates:
            # 1. Direct Match
            direct = self.km.get_concept(c)
            if direct: return direct
            
            # 2. Fuzzy/Keyword Match
            for concept, data in self.km.db["concepts"].items():
                c_words = set(c.split())
                concept_words = set(concept.split())
                overlap = c_words.intersection(concept_words)
                
                if overlap:
                    # Score based on how much of the CONCEPT is matched
                    score = len(overlap) / len(concept_words)
                    if score > max_score:
                        max_score = score
                        best_match = data
        
        if max_score >= 0.5: # Threshold for keyword hit
            return best_match
            
        return None

    def _format_token_output(self, resolved, weighting, memory_match, stats):
        tokens = []
        tokens.append(f"[COG: {stats['cognition_level']}]")
        tokens.append(f"[LEX: {stats['lexical_pct']:.0%}]")
        tokens.append(f"[SYN: {stats['syntactic_pct']:.0%}]")
        tokens.append(f"[CONF: {self.confidence_score:.2f}]")
        tokens.append(f"[MEM: {'YES' if memory_match else 'NO'}]")
        
        # Granular Layer Insights (Short form)
        lv = stats.get("layer_validation", {})
        l_summary = f"L4:{lv.get('level_4_syntax',0):.1f}|L6:{lv.get('level_6_pragmatics',0):.1f}|5W:{lv.get('5w1h_cycle',0):.1f}|BOR:{self.boredom_score:.1f}"
        tokens.append(f"[VAL: {l_summary}]")

        if weighting["thought_event"]:
            tokens.append(f"!! [EVENT: {weighting['thought_event']}] !!")
            
        return " ".join(tokens)

    def _trigger_audit_diff(self, input_text: str, gap_analysis) -> Dict[str, float]:
        """
        Trigger audit --diff to discover pattern weights for morphological adjustment.

        Args:
            input_text: The input text that triggered the gap
            gap_analysis: GapAnalysis object from gap_analyzer

        Returns:
            Dictionary mapping category -> suggested_weight (0-1)
        """
        import subprocess
        import tempfile

        # Write gap context to a temp file for audit to analyze
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            context = {
                "input_text": input_text,
                "unrecognized_tokens": gap_analysis.unrecognized_tokens,
                "confidence_score": gap_analysis.confidence_score,
                "primary_gaps": [(token, pattern) for token, pattern in gap_analysis.primary_gaps]
            }
            json.dump(context, f, indent=2)
            context_file = f.name

        try:
            # Run audit --diff with the context
            audit_path = get_path("audit.py")
            result = subprocess.run(
                ["python3", audit_path, "--diff", "--context", context_file],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Parse the output to extract pattern weights
            if result.returncode == 0:
                # TODO: Parse actual audit output format
                # For now, use gap analysis suggestions
                pattern_weights = {}
                for token, suggested_pattern in gap_analysis.primary_gaps:
                    # Extract category from suggested pattern
                    # This is a simplified mapping
                    if "ly\\b" in suggested_pattern:
                        pattern_weights["level_2_morphology"] = 0.8
                    elif "\\b" in suggested_pattern and len(token) > 4:
                        pattern_weights["level_3_lexical"] = 0.7

                self.add_thought(f"Audit --diff completed. Pattern weights discovered: {pattern_weights}")
                return pattern_weights
            else:
                self.add_thought(f"Audit --diff failed: {result.stderr}")
                return {}

        except Exception as e:
            self.add_thought(f"Audit --diff error: {str(e)}")
            return {}
        finally:
            # Clean up temp file
            try:
                os.unlink(context_file)
            except:
                pass

    def _apply_morphological_weight_adjustment(self, pattern_weights: Dict[str, float]):
        """
        Apply morphological pattern weight adjustments based on audit --diff results.

        This implements the feedback loop:
        Gap detected → audit --diff → discover patterns → adjust weights → re-resolve

        Args:
            pattern_weights: Dictionary of category -> weight adjustments
        """
        if not pattern_weights:
            return

        # Update epistemic loop category weights
        for category, suggested_weight in pattern_weights.items():
            current_weight = self.epistemic_loop.category_weights.get(category, 0.5)
            # Blend current weight with suggested weight
            new_weight = (current_weight + suggested_weight) / 2.0
            self.epistemic_loop.category_weights[category] = new_weight

        # Recalculate overall priority%
        if self.epistemic_loop.category_weights:
            self.epistemic_loop.priority_pct = (
                sum(self.epistemic_loop.category_weights.values()) /
                len(self.epistemic_loop.category_weights)
            )

        self.add_thought(f"Morphological weights adjusted: {pattern_weights}")
        self._save_state()

    def _generate_learning_prompt(self, resolved):
        """
        Generates a question to fill the epistemic gap.
        """
        five_ws = resolved["5w1h_resolution"]
        unresolved = [w for w, v in five_ws.items() if v is None]
        
        if unresolved:
            target = random.choice(unresolved)
            return f"I detect complex entities but lack hierarchical context for '{target}'. Can you explain {target} this is happening or what the relationship is?", "LEARNING_PROMPT"
        
        return "I understand the individual components, but the semantic connection is unclear. Could you define the core purpose here?", "LEARNING_PROMPT"

    def _calculate_priority_weights(self, resolved):
        """
        Weights factors like input length, number of questions, and hierarchical depth.
        Refined with domain-specific modifiers and dampening.
        """
        analysis = resolved["hierarchy_analysis"]
        five_ws = resolved["5w1h_resolution"]
        
        # Factors
        len_factor = min(len(resolved["input"]) / 100, 1.0)
        q_count = sum(1 for v in five_ws.values() if v is not None)
        
        # Why-Priority Hook (Task: hook high % to ask why)
        why_boost = 1.0
        if five_ws.get("why") or "why" in resolved["input"].lower():
            why_boost = 1.5
            self.add_thought("Why-Priority: High-gradient validation requested.")

        # Calibration Boost
        calib_boost = 1.2 if self.calibration_active else 1.0
        hier_depth = sum(1 for lvl, content in analysis.items() if content and lvl.startswith("level")) / 7.0
        
        # Domain Modifiers
        domain_mods = {
            "domain_academic": 1.2,
            "domain_technical": 1.1,
            "domain_informal": 0.8,
            "general": 1.0
        }
        mod = domain_mods.get(self.active_domain, 1.0)
        
        # Situation Modifiers - Multiplicative rather than purely additive
        sit_mod = 1.0
        if self.active_situation:
            sit_mod = self.active_situation["domain_weights"].get(self.active_domain, 1.0)
            
        fatigue = self.timer.get_fatigue_factor()
        
        # Weighting Formula with Dampening for short queries
        base_priority = (len_factor * 0.1) + (q_count * 0.4) + (hier_depth * 0.5)
        total_priority = base_priority * mod * sit_mod * fatigue * why_boost * calib_boost
        total_priority = min(total_priority, 1.0)
        
        # Trigger Thought Event if priority is high but resolution is low
        thought_event = None
        if total_priority > 0.7 and q_count > 2 and hier_depth < 0.3:
            thought_event = "COMPLEXITY_ASYMMETRY: High priority query with low hierarchical resolution."
            
        return {
            "total_priority": total_priority,
            "q_count": q_count,
            "hier_depth": hier_depth,
            "thought_event": thought_event
        }

    def _evaluate_understanding(self, resolved, weighting):
        """
        Adjusts global confidence with improved dampening.
        """
        lex_pct = resolved.get("stats", {}).get("lexical_pct", 1.0)
        
        # If priority is high but lexical match is low, drop confidence
        if weighting["total_priority"] > 0.7 and lex_pct < 0.2:
            decay = 0.15 * weighting["total_priority"]
            self.confidence_score = max(0.1, self.confidence_score - decay)
            weighting["thought_event"] = "EPISTEMIC_FRICTION: High complexity, low recognition."
        elif lex_pct > 0.6:
            # Boost confidence for clear understanding
            self.confidence_score = min(1.0, self.confidence_score + 0.05)
        
        # Ensure minimum confidence doesn't paralyze simple social/greeting interactions
        if resolved["logical_intent"] in ["SOCIAL_INITIATION", "GRATIFICATION"]:
            self.confidence_score = max(0.5, self.confidence_score)

# ============================================================================
# Interactive Weight Tuning Mode
# ============================================================================

def run_weight_tuning_mode(session_id: Optional[str] = None):
    """
    Interactive weight tuning mode with real-time suggestion updates.

    #[Mark:P1-WeightTuningMode] Interactive weight correction with live preview
    #TODO: Add command history with up/down arrows
    #TODO: Integrate with Morph pattern validation for suggestions
    #TODO: Add save/load tuning presets
    #[Event:WEIGHT_TUNING_MODE_START] Entering interactive weight tuning

    Args:
        session_id: Optional Os_Toolkit session to load for context
    """
    print("=" * 80)
    print("WEIGHT TUNING MODE - Interactive Action Confidence Correction")
    print("=" * 80)
    print()

    # Initialize weight tuner
    babel_root = Path(os.path.dirname(__file__)).parent  # Go up from regex_project to Babel root
    try:
        tuner = ActionWeightTuner(babel_root)
    except Exception as e:
        print(f"[ERROR] Failed to initialize weight tuner: {e}")
        return

    # Load Os_Toolkit session if specified
    session_context = None
    if session_id:
        session_file = babel_root / f"babel_data/profile/sessions/{session_id}"
        if session_file.exists():
            try:
                with open(session_file / "session_data.json") as f:
                    session_context = json.load(f)
                print(f"[SESSION] Loaded: {session_id}")
                print(f"  Files analyzed: {len(session_context.get('file_index', {}))}")
                print(f"  Session time: {session_context.get('metadata', {}).get('session_time', 'unknown')}")
                print()
            except Exception as e:
                print(f"[WARNING] Could not load session {session_id}: {e}")
                print()

    # Extract context from manifest
    context = tuner.extract_context_from_manifest()

    # Display context summary
    print("[MANIFEST CONTEXT]")
    print(f"  Scattered plans: {context['scattered_plan_count']}")
    print(f"  Unassociated .md: {context['unassociated_md_files']}")
    print(f"  Top-level .md: {context['top_level_md_files']}")
    print(f"  Recent changes (24h): {context['recent_file_changes']}")
    print(f"  Projects tracked: {len(context['project_associations'])}")
    print()

    # Initial suggestion preview
    suggestions = tuner.preview_suggestions(context)

    print("[CURRENT SUGGESTIONS] (Top 10)")
    print("=" * 80)
    for i, sugg in enumerate(suggestions[:10], 1):
        conf_level = "HIGH" if sugg['confidence'] >= 0.7 else "MED" if sugg['confidence'] >= 0.5 else "LOW"
        print(f"{i:2d}. [{sugg['confidence']:.2f}] {conf_level:4s} - {sugg['action_id']}")
        print(f"    {sugg['reasoning']}")
    print("=" * 80)
    print()

    # Interactive loop
    print("Commands:")
    print("  adjust <action_id> <delta>  - Adjust weight (e.g., adjust consolidate_plans +0.15)")
    print("  preview                      - Show updated suggestions")
    print("  export                       - Save weights to file")
    print("  context                      - Show manifest context again")
    print("  help                         - Show this help")
    print("  quit                         - Exit tuning mode")
    print()

    while True:
        try:
            cmd = input("weight-tuner> ").strip()

            if not cmd:
                continue

            if cmd in ["quit", "exit", "q"]:
                print("[WEIGHT_TUNER] Exiting tuning mode")
                break

            elif cmd == "help":
                print("Commands:")
                print("  adjust <action_id> <delta>  - Adjust weight")
                print("  preview                      - Show updated suggestions")
                print("  export                       - Save weights")
                print("  context                      - Show context")
                print("  quit                         - Exit")
                print()

            elif cmd == "preview":
                suggestions = tuner.preview_suggestions(context)
                print("\n[UPDATED SUGGESTIONS] (Top 10)")
                print("=" * 80)
                for i, sugg in enumerate(suggestions[:10], 1):
                    conf_level = "HIGH" if sugg['confidence'] >= 0.7 else "MED" if sugg['confidence'] >= 0.5 else "LOW"
                    print(f"{i:2d}. [{sugg['confidence']:.2f}] {conf_level:4s} - {sugg['action_id']}")
                    print(f"    {sugg['reasoning']}")
                print("=" * 80)
                print()

            elif cmd == "export":
                tuner.export_weights()
                print()

            elif cmd == "context":
                print("\n[MANIFEST CONTEXT]")
                print(f"  Scattered plans: {context['scattered_plan_count']}")
                print(f"  Unassociated .md: {context['unassociated_md_files']}")
                print(f"  Top-level .md: {context['top_level_md_files']}")
                print(f"  Recent changes (24h): {context['recent_file_changes']}")
                print(f"  Projects tracked: {len(context['project_associations'])}")
                print()

            elif cmd.startswith("adjust "):
                parts = cmd.split()
                if len(parts) != 3:
                    print("[ERROR] Usage: adjust <action_id> <delta>")
                    print("  Example: adjust consolidate_plans +0.15")
                    continue

                action_id = parts[1]
                try:
                    delta = float(parts[2])
                except ValueError:
                    print(f"[ERROR] Invalid delta: {parts[2]}")
                    continue

                # Store old suggestions
                old_suggestions = tuner.preview_suggestions(context)

                # Apply adjustment
                tuner.adjust_weight(action_id, delta, reason=f"Manual adjustment via interactive mode")

                # Show new suggestions
                new_suggestions = tuner.preview_suggestions(context)

                # Display comparison
                tuner.display_comparison(old_suggestions[:10], new_suggestions[:10])
                print()

            else:
                print(f"[ERROR] Unknown command: {cmd}")
                print("  Type 'help' for command list")
                print()

        except KeyboardInterrupt:
            print("\n[WEIGHT_TUNER] Interrupted, exiting")
            break
        except EOFError:
            print("\n[WEIGHT_TUNER] EOF, exiting")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            print()

# ============================================================================
# Morph State Chat Mode
# ============================================================================

def run_morph_chat_mode(session_id: Optional[str] = None):
    """
    Morph chat mode about current system state with session context.

    #[Mark:P1-MorphStateChat] Discuss current situation with session logs + live context
    #TODO: Integrate with level_2_morphology patterns for linguistic analysis
    #TODO: Add domain-specific pattern weights (academic, technical, informal)
    #TODO: Implement pattern-based state summarization
    #TODO: Add session diff view (previous state vs current state)
    #[Event:MORPH_CHAT_MODE_START] Entering Morph state chat mode

    Args:
        session_id: Optional Os_Toolkit session to load for chat context
    """
    print("=" * 80)
    print("MORPH STATE CHAT - Current System State Discussion")
    print("=" * 80)
    print()

    # Initialize weight tuner (for manifest access) — optional, degrades gracefully
    babel_root = Path(os.path.dirname(__file__)).parent
    tuner = None
    try:
        tuner = ActionWeightTuner(babel_root)
    except FileNotFoundError as e:
        print(f"[WARN] Weight tuner offline: {e}")
        print("  (morph-chat continues without manifest-based weight tuning)")
    except Exception as e:
        print(f"[WARN] Weight tuner unavailable: {e}")

    # Load Os_Toolkit session
    session_data = None
    if session_id:
        session_file = babel_root / f"babel_data/profile/sessions/{session_id}"
    else:
        # Find latest session
        sessions_dir = babel_root / "babel_data/profile/sessions"
        if sessions_dir.exists():
            # Try babel_catalog_* first, then any dated session dir
            session_dirs = sorted(sessions_dir.glob("babel_catalog_*"),
                                key=lambda p: p.stat().st_mtime,
                                reverse=True)
            if not session_dirs:
                # Fallback: any directory in sessions/ (sorted by mtime)
                session_dirs = sorted(
                    [d for d in sessions_dir.iterdir() if d.is_dir()],
                    key=lambda p: p.stat().st_mtime, reverse=True
                )
            if session_dirs:
                session_file = session_dirs[0]
                session_id = session_file.name
            else:
                print("[WARN] No sessions found — using empty context")
                session_file = None
                session_id = 'no_session'
        else:
            print("[WARN] Sessions directory not found — using empty context")
            session_file = None
            session_id = 'no_session'

    # Load session data from Os_Toolkit session format
    if session_file is None:
        session_data = {'metadata': {}, 'file_index': {}, 'todos': [], 'plans': []}
        print(f"[SESSION] Running without session data")
    else:
        metadata_file = session_file / "metadata.json"
        artifacts_file = session_file / "artifacts.json"
        if not metadata_file.exists():
            print(f"[WARN] Session metadata not found, using empty context")
            session_data = {'metadata': {}, 'file_index': {}, 'todos': [], 'plans': []}
        else:
            try:
                # Load metadata
                with open(metadata_file) as f:
                    metadata = json.load(f)

                # Load artifacts (file_index, todos, plans)
                artifacts = {}
                if artifacts_file.exists():
                    with open(artifacts_file) as f:
                        artifacts = json.load(f)

                session_data = {
                    'metadata': metadata,
                    'file_index': artifacts.get('file_profiles', {}),
                    'todos': [],
                    'plans': []
                }

                if 'todo_index' in artifacts:
                    session_data['todos'] = list(artifacts['todo_index'].values())
                if 'plan_index' in artifacts:
                    session_data['plans'] = list(artifacts['plan_index'].values())

                print(f"[SESSION] Loaded: {session_id}")
                print(f"  Created: {metadata.get('created_at', 'unknown')}")
                print(f"  Files analyzed: {len(session_data['file_index'])}")
                print(f"  Todos tracked: {len(session_data['todos'])}")
                print(f"  Plans tracked: {len(session_data['plans'])}")
                print(f"  Journal entries: {metadata.get('statistics', {}).get('journal_entries', 0)}")
                print()
            except Exception as e:
                print(f"[WARN] Could not load session: {e}")
                session_data = {'metadata': {}, 'file_index': {}, 'todos': [], 'plans': []}

    # Load Os_Toolkit grounded context (enriched_changes, provisions, temporal)
    grounded_ctx = {}
    activity_bridge = None
    if HAS_ACTIVITY_BRIDGE:
        try:
            grounder = OsToolkitGroundingBridge(babel_root)
            grounded_ctx = grounder.load()
            session_data['grounded'] = grounded_ctx
            nch = len(grounded_ctx.get('recent_changes', []))
            npf = len(grounded_ctx.get('probe_failures', []))
            npkg = len(grounded_ctx.get('provisions', []))
            print(f"[GROUNDED] {nch} recent changes, {npf} probe failures, "
                  f"{npkg} provisions, gap={grounded_ctx.get('gap_severity','?')}")
            _reg_file = babel_root / "capability_registry.json"
            _reg = CapabilityRegistry(_reg_file)
            activity_bridge = ActivitySuggestionBridge(_reg)
        except Exception as _ge:
            print(f"[GROUNDED] Context unavailable: {_ge}")

    # Instantiate teaching + toolkit + capability catalog + manifest bridge + conformer
    morph_teacher = None
    morph_toolkit = None
    morph_catalog = None
    morph_manifest = None
    morph_conformer = None
    if HAS_ACTIVITY_BRIDGE:
        try:
            morph_teacher = MorphTeachingBridge(babel_root)
            morph_toolkit = MorphToolkit(babel_root)
            morph_catalog = MorphCapabilityCatalog(babel_root)
            morph_manifest = MorphManifestBridge(babel_root)
            morph_conformer = MorphConformer(babel_root)
        except Exception as _te:
            print(f"[MORPH] Teaching/Toolkit init failed: {_te}")

    # Step C: Load active task bias from config.json
    trainer_root = babel_root.parent.parent.parent  # Trainer/
    active_task_id = None
    active_task_context = None
    try:
        # Canonical: Trainer/Data/plans/config.json (written by Os_Toolkit todo activate)
        config_path = trainer_root / 'Data' / 'plans' / 'config.json'
        if not config_path.exists():
            config_path = babel_root / 'babel_data' / 'config.json'
        if not config_path.exists():
            config_path = babel_root / 'config.json'
        if config_path.exists():
            _cfg = json.loads(config_path.read_text(encoding='utf-8'))
            active_task_id = _cfg.get('active_task_id')
        if active_task_id:
            for _tc_path in [
                trainer_root / 'Data' / 'plans' / 'Tasks' / f'task_context_{active_task_id}.json',
                trainer_root / 'plans' / 'Tasks' / f'task_context_{active_task_id}.json',
            ]:
                if _tc_path.exists():
                    active_task_context = json.loads(_tc_path.read_text(encoding='utf-8'))
                    break
            if active_task_context:
                print(f"[Active task: {active_task_id}] {active_task_context.get('title', '')}")
                print(f"  wherein: {active_task_context.get('wherein', 'unknown')}")
                print(f"  changes: {len(active_task_context.get('changes', []))}")
                print(f"  expected_diffs: {len(active_task_context.get('expected_diffs', []))}")
            else:
                print(f"[Active task: {active_task_id}] (no task_context found)")
    except Exception as _ace:
        pass  # non-blocking
    print()

    # Extract manifest context (safe — tuner may be None)
    context = tuner.extract_context_from_manifest() if tuner else {
        'scattered_plan_count': 0, 'unassociated_md_files': 0, 'recent_file_changes': 0,
        'top_level_md_files': 0, 'project_associations': {},
    }
    # Ensure keys always present (tuner may not return all keys)
    context.setdefault('top_level_md_files', 0)
    context.setdefault('project_associations', {})

    # Display current state summary
    print("[CURRENT STATE SUMMARY]")
    print("=" * 80)
    if tuner:
        print(f"Manifest: {tuner.manifest_path.name}")
        print(f"  Total files: {tuner.manifest.get('metadata', {}).get('file_count', 0)}")
    else:
        print("Manifest: (weight tuner offline — Filesync manifests not found)")
    print(f"  Scattered plans: {context['scattered_plan_count']}")
    print(f"  Unassociated .md: {context['unassociated_md_files']}")
    print(f"  Recent changes: {context['recent_file_changes']}")
    print()

    print(f"Session: {session_id}")
    print(f"  Active todos: {len(session_data.get('todos', []))}")
    print(f"  Active plans: {len(session_data.get('plans', []))}")
    print(f"  Indexed files: {len(session_data.get('file_index', {}))}")
    print("=" * 80)
    print()

    # Interactive chat about state
    print("Chat about current system state. Type 'help' for full command list.")
    print("  learn <file|fn|task>   analyze   trace <event|file>   ground   quit")
    print()

    while True:
        try:
            cmd = input("morph-chat> ").strip()

            if not cmd:
                continue

            if cmd in ["quit", "exit", "q"]:
                print("[MORPH_CHAT] Exiting chat mode")
                break

            elif cmd == "summary":
                print("\n[FULL STATE SUMMARY]")
                print("=" * 80)
                if tuner:
                    print(f"Manifest: {tuner.manifest_path.name}")
                    print(f"  Generated: {tuner.manifest.get('metadata', {}).get('generated', 'unknown')}")
                    print(f"  Files: {tuner.manifest.get('metadata', {}).get('file_count', 0)}")
                    print(f"  Projects: {len(tuner.manifest.get('projects', {}))}")
                else:
                    print("Manifest: (weight tuner offline)")
                print()
                print(f"Session: {session_id}")
                print(f"  Todos: {len(session_data.get('todos', []))}")
                print(f"  Plans: {len(session_data.get('plans', []))}")
                print(f"  Files: {len(session_data.get('file_index', {}))}")
                print()
                print("Context:")
                print(f"  Scattered plans: {context['scattered_plan_count']}")
                print(f"  Unassociated .md: {context['unassociated_md_files']}")
                print(f"  Recent changes: {context['recent_file_changes']}")
                print("=" * 80)
                print()

            elif cmd == "todos":
                todos = session_data.get('todos', [])
                print(f"\n[ACTIVE TODOS] ({len(todos)} total)")
                print("=" * 80)
                for i, todo in enumerate(todos[:20], 1):  # Show first 20
                    status = "✓" if todo.get('completed', False) else "○"
                    print(f"{i:2d}. [{status}] {todo.get('text', 'No text')}")
                    if todo.get('file_path'):
                        print(f"    File: {todo['file_path']}:{todo.get('line_number', '?')}")
                if len(todos) > 20:
                    print(f"    ... and {len(todos) - 20} more")
                print("=" * 80)
                print()

            elif cmd == "plans":
                plans = session_data.get('plans', [])
                print(f"\n[ACTIVE PLANS] ({len(plans)} total)")
                print("=" * 80)
                for i, plan in enumerate(plans[:15], 1):  # Show first 15
                    print(f"{i:2d}. {plan.get('title', 'Untitled')}")
                    print(f"    File: {plan.get('file_path', 'unknown')}")
                    print(f"    Items: {plan.get('item_count', 0)}")
                if len(plans) > 15:
                    print(f"    ... and {len(plans) - 15} more")
                print("=" * 80)
                print()

            elif cmd.startswith("files "):
                pattern = cmd.split(maxsplit=1)[1] if len(cmd.split()) > 1 else ""
                file_index = session_data.get('file_index', {})
                matches = [path for path in file_index.keys() if pattern.lower() in path.lower()]
                print(f"\n[FILE SEARCH] Pattern: '{pattern}' ({len(matches)} matches)")
                print("=" * 80)
                for i, path in enumerate(matches[:20], 1):
                    file_data = file_index[path]
                    print(f"{i:2d}. {path}")
                    print(f"    Category: {file_data.get('category', 'unknown')}")
                    print(f"    Size: {file_data.get('size', 0)} bytes")
                if len(matches) > 20:
                    print(f"    ... and {len(matches) - 20} more")
                print("=" * 80)
                print()

            elif cmd == "context":
                print("\n[MANIFEST CONTEXT]")
                print(f"  Scattered plans: {context['scattered_plan_count']}")
                print(f"  Unassociated .md: {context['unassociated_md_files']}")
                print(f"  Top-level .md: {context['top_level_md_files']}")
                print(f"  Recent changes: {context['recent_file_changes']}")
                print(f"  Projects: {len(context['project_associations'])}")
                for proj_id, count in list(context['project_associations'].items())[:10]:
                    print(f"    {proj_id}: {count} files")
                print()

            elif cmd == "suggest":
                # Try GroundedSuggestEngine first (phase/domain-aware), fall back to tuner
                _omega_dir_sg = Path(__file__).parent / "activities" / "tools" / "scripts"
                _used_grounded = False
                try:
                    if str(_omega_dir_sg) not in sys.path:
                        sys.path.insert(0, str(_omega_dir_sg))
                    from grounded_suggest_engine import GroundedSuggestEngine as _GSE_mc
                    _gse = _GSE_mc(trainer_root)
                    _gse.load_context()
                    _sg_suggestions = _gse.suggest(query='latest')
                    print(f"\n── Grounded Suggestions [Phase: {_gse.phase_summary()}] [Domain: {_gse.dominant_domain()}] ──")
                    if _sg_suggestions:
                        for i, sg in enumerate(_sg_suggestions[:10], 1):
                            _rec = " [RECOMMENDED]" if sg.get('selected') else ""
                            print(f"  {i:2d}. {sg['label']}{_rec}")
                            print(f"      {sg['command']}")
                    else:
                        print("  No suggestions available.")
                    print()
                    _used_grounded = True
                except Exception as _sg_err:
                    pass

                if not _used_grounded:
                    if tuner is None:
                        print("  [WARN] Weight tuner offline — suggestions unavailable")
                    else:
                        suggestions = tuner.preview_suggestions(context)
                        print(f"\n[ACTION SUGGESTIONS] (Top 10)")
                        print("=" * 80)
                        for i, sugg in enumerate(suggestions[:10], 1):
                            conf_level = "HIGH" if sugg['confidence'] >= 0.7 else "MED" if sugg['confidence'] >= 0.5 else "LOW"
                            print(f"{i:2d}. [{sugg['confidence']:.2f}] {conf_level:4s} - {sugg['action_id']}")
                            print(f"    {sugg['reasoning']}")
                        print("=" * 80)
                print()

            elif cmd.startswith("changes"):
                parts = cmd.split()
                n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                changes = grounded_ctx.get('recent_changes', [])
                if not changes:
                    print("  No recent changes found (version_manifest.json not loaded or empty)")
                else:
                    print(f"\n[RECENT CHANGES] (last {min(n, len(changes))} of {len(changes)})")
                    print("=" * 80)
                    print(f"  {'Risk':8}  {'Probe':5}  {'File':<35}  Verb")
                    print("  " + "-" * 70)
                    for ch in changes[:n]:
                        # risk_level is the canonical field; 'risk' is a fallback alias
                        risk  = ch.get('risk_level') or ch.get('risk') or '?'
                        probe = ch.get('probe_status') or 'NONE'
                        fname = Path(ch.get('file', '?')).name
                        verb  = ch.get('verb', '?')
                        print(f"  {risk:8}  {probe:5}  {fname:<35}  {verb}")
                print()

            elif cmd.startswith("packages"):
                parts = cmd.split(maxsplit=1)
                query = parts[1].lower() if len(parts) > 1 else ''
                pkgs = grounded_ctx.get('provisions', [])
                if query:
                    pkgs = [p for p in pkgs if query in p.get('name', '').lower()]
                if not pkgs:
                    print("  No provisions found (provisions_catalog.json not loaded)")
                else:
                    print(f"\n[PROVISIONS] ({len(pkgs)} packages)")
                    print("=" * 80)
                    print(f"  {'Name':<32}  {'Version':<14}  Status")
                    print("  " + "-" * 60)
                    for p in pkgs:
                        status = p.get('install_status', '?')
                        print(f"  {p.get('name','?'):<32}  {p.get('version','?'):<14}  [{status}]")
                print()

            elif cmd == "hotspots":
                spots = grounded_ctx.get('temporal_hot_spots', [])
                if not spots:
                    print("  No temporal data (history_temporal_manifest.json not loaded)")
                else:
                    print(f"\n[TEMPORAL HOT SPOTS] (top {len(spots)} by change count)")
                    print("=" * 80)
                    for s in spots:
                        cnt  = s.get('change_count', 0)
                        # A2: use source_path (resolved), fallback to file
                        src = s.get('source_path') or s.get('file', '?')
                        print(f"  {cnt:5}x  {src}")
                print()

            elif cmd == "ground":
                if not grounded_ctx:
                    print("  Grounded context not loaded — check version_manifest.json path")
                elif activity_bridge is None:
                    print("  Activity bridge not available (HAS_ACTIVITY_BRIDGE=False)")
                else:
                    try:
                        suggestion = activity_bridge.suggest_from_grounded(grounded_ctx)
                        ev = suggestion.get('grounded_evidence', {})
                        print(f"\n── Grounded Viewpoint ──")
                        print(f"  Activity : {suggestion['activity_type'].upper()}")
                        print(f"  Reason   : {suggestion['reason']}")
                        print(f"  Evidence : {ev.get('probe_failures', 0)} probe failures | "
                              f"{len(ev.get('high_risk_files', []))} high-risk files | "
                              f"gap={ev.get('gap_severity','?')} | "
                              f"priority={ev.get('priority_pct', 0):.0%}")
                        hrf = ev.get('high_risk_files', [])
                        if hrf:
                            print(f"  Hot files: {', '.join(Path(f).name for f in hrf[:4])}")
                        caps = suggestion.get('relevant_capabilities', [])
                        if caps:
                            print(f"  Relevant : {', '.join(c['tool'] for c in caps)}")
                        print()
                    except Exception as _ge:
                        import traceback
                        print(f"  Error generating grounded suggestion: {_ge}")
                        traceback.print_exc()

            # ── Teaching & Analysis ──────────────────────────────────────────
            elif cmd.startswith("learn ") or cmd == "learn":
                arg = cmd[6:].strip() if cmd.startswith("learn ") else ""
                if not arg:
                    print("  Usage: learn <file.py | function_name | task_id>")
                elif morph_teacher is None:
                    print("  [MORPH] Teaching bridge not available")
                elif arg.startswith("task"):
                    ctx = morph_toolkit.task_context(arg) if morph_toolkit else {}
                    if 'error' in ctx:
                        print(f"  {ctx['error']}")
                    else:
                        signals = ctx.get('completion_signals', {})
                        changes = ctx.get('changes', [])
                        print(f"\n── Task Context: {arg} ──")
                        print(f"  Status   : {signals.get('inferred_status','?')}")
                        print(f"  Changes  : {signals.get('changes_count',0)} | "
                              f"Probes: {signals.get('probes_passing',0)} pass / "
                              f"{signals.get('probes_failing',0)} fail")
                        exp = ctx.get('expected_diffs', [])
                        if exp:
                            print(f"  Expected : {len(exp)} diffs")
                            for ed in exp[:3]:
                                print(f"    {ed.get('type','?'):8} {Path(ed.get('file','')).name}  "
                                      f"[{ed.get('probe_status','?')}]")
                        if changes:
                            print(f"  Changes  :")
                            for c in (changes[:3] if isinstance(changes[0], dict) else []):
                                blk = morph_teacher.get_change_teaching_block(c)
                                print(blk)
                elif arg.endswith('.py') or '/' in arg:
                    bp = morph_teacher.get_file_blueprint(arg)
                    print(f"\n── File Blueprint: {Path(bp['file_path']).name} ──")
                    print(f"  LOC      : {bp['loc']}")
                    print(f"  Classes  : {len(bp['classes'])} — "
                          f"{', '.join(c['name'] for c in bp['classes'][:5])}")
                    print(f"  Functions: {len(bp['functions'])}")
                    if bp['verb_categories']:
                        vc = ', '.join(f"{k}:{v}" for k,v in
                                       sorted(bp['verb_categories'].items(), key=lambda x: -x[1])[:6])
                        print(f"  Verbs    : {vc}")
                    if bp['top_complexity']:
                        tc = ', '.join(f"{x['name']}({x['complexity']})" for x in bp['top_complexity'][:3])
                        print(f"  Complex  : {tc}")
                    if bp['imports']:
                        print(f"  Imports  : {', '.join(bp['imports'][:8])}")
                    if bp['errors']:
                        print(f"  Errors   : {bp['errors']}")
                    print()
                else:
                    # Function lookup
                    prof = morph_teacher.get_function_profile(arg)
                    if prof:
                        print(f"\n── Function Profile: {arg} ──")
                        print(f"  File     : {Path(prof['file']).name}  line {prof['line']}")
                        print(f"  Verb     : {prof['verb']}  | async: {prof['is_async']}  | complexity: {prof['complexity']}")
                        print(f"  Args     : {', '.join(prof['args']) or '(none)'}")
                        if prof['calls']:
                            print(f"  Calls    : {', '.join(prof['calls'][:8])}")
                    else:
                        print(f"  Function '{arg}' not found in recently changed files")
                        print("  Tip: specify file with 'learn <function> in <file.py>'")
                    print()

            elif cmd.startswith("analyze "):
                arg = cmd[8:].strip()
                if morph_teacher is None:
                    print("  [MORPH] Teaching bridge not available")
                else:
                    bp = morph_teacher.get_file_blueprint(arg)
                    print(f"\n── Analysis: {Path(bp['file_path']).name} ──")
                    print(f"  LOC: {bp['loc']} | Classes: {len(bp['classes'])} | Functions: {len(bp['functions'])}")
                    for fn in bp['functions'][:8]:
                        print(f"  [{fn['verb']:10}] {fn['name']}({', '.join(fn['args'][:3])})  "
                              f"complexity={fn['complexity']}")
                    if bp['errors']:
                        print(f"  Parse errors: {bp['errors']}")
                    print()

            elif cmd.startswith("trace "):
                arg = cmd[6:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    result = morph_toolkit.trace(arg)
                    matches = result.get('matches', [])
                    print(f"\n── Trace: '{arg}' ({result['total']} matches) ──")
                    for ch in matches[:5]:
                        blk = morph_teacher.get_change_teaching_block(ch) if morph_teacher else str(ch)
                        print(blk)
                        print()

            elif cmd.startswith("diagnose "):
                arg = cmd[9:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    result = morph_toolkit.diagnose(arg)
                    print(f"\n── Diagnosis: {result.get('event_id', arg)} ──")
                    if 'error' in result:
                        print(f"  {result['error']}")
                    else:
                        print(f"  File     : {Path(result.get('file','')).name}")
                        print(f"  Risk     : {result.get('risk_level','?')} | Probe: {result.get('probe_status','?')}")
                        for d in result.get('diagnosis', []):
                            print(f"  [{d['type']}] {d['message'][:80]}")
                            print(f"    → {d['suggestion']}")
                        if result.get('resolution'):
                            print(f"  Resolved by: {result['resolution']}")
                    print()

            elif cmd.startswith("undo-preview "):
                arg = cmd[13:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    result = morph_toolkit.undo_preview(arg)
                    if 'error' in result:
                        print(f"  {result['error']}")
                    else:
                        print(f"\n── Undo Preview: {arg} ──")
                        print(f"  File  : {Path(result.get('file','')).name}")
                        print(f"  Before: {result['before_lines']} lines")
                        print(f"  After : {result['after_lines']} lines")
                        print(f"\n  [BEFORE preview]")
                        for ln in result['before_preview'].splitlines()[:8]:
                            print(f"  - {ln}")
                        print(f"\n  [AFTER preview]")
                        for ln in result['after_preview'].splitlines()[:8]:
                            print(f"  + {ln}")
                        print(f"\n  To undo: type 'undo {arg}'")
                    print()

            elif cmd.startswith("undo ") and not cmd.startswith("undo-"):
                arg = cmd[5:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    confirm = input(f"  Confirm undo of {arg}? This restores the before-state. [y/N] ").strip().lower()
                    if confirm == 'y':
                        result = morph_toolkit.undo_execute(arg, confirmed=True)
                        if result.get('success'):
                            print(f"  ✓ Undo successful: {result.get('message','')}")
                        else:
                            print(f"  ✗ Undo failed: {result.get('error','')}")
                    else:
                        print("  Undo cancelled.")
                    print()

            elif cmd.startswith("task-context "):
                arg = cmd[13:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    ctx = morph_toolkit.task_context(arg)
                    if 'error' in ctx:
                        print(f"  {ctx['error']}")
                    else:
                        signals = ctx.get('completion_signals', {})
                        print(f"\n── Task Context: {arg} ──")
                        print(f"  Status   : {signals.get('inferred_status','?')}")
                        print(f"  Wherein  : {ctx.get('_meta', {}).get('wherein','?')}")
                        print(f"  Changes  : {signals.get('changes_count',0)}")
                        print(f"  Probes   : {signals.get('probes_passing',0)} pass / {signals.get('probes_failing',0)} fail")
                        peers = ctx.get('peers', [])
                        if peers:
                            print(f"  Peers    : {', '.join(p.get('name','?') for p in peers[:4])}")
                    print()

            elif cmd.startswith("plan-status "):
                arg = cmd[12:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    result = morph_toolkit.plan_status(arg)
                    if 'error' in result:
                        print(f"  {result['error']}")
                    else:
                        status = result['status']
                        icon = '✓' if status == 'COMPLETABLE' else ('✗' if status == 'BLOCKED' else '○')
                        print(f"\n── Plan Status: {arg} ──")
                        print(f"  {icon} {status}")
                        print(f"  Changes: {result['changes_count']} | Probes: {result['probes_passing']} pass / {result['probes_failing']} fail")
                        print(f"  All green: {result['all_probes_green']}")
                    print()

            elif cmd.startswith("probe "):
                arg = cmd[6:].strip()
                if morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    result = morph_toolkit.probe_file(arg)
                    status = result.get('probe_status', '?')
                    icon = {'PASS': '✓', 'WARN': '⚠', 'FAIL': '✗'}.get(status, '?')
                    print(f"\n── Live Probe: {arg} ──")
                    print(f"  {icon} {status}")
                    for e in result.get('errors', []):
                        print(f"    {e[:100]}")
                    print()

            elif cmd == "domain":
                if morph_teacher is None:
                    print("  [MORPH] Teaching bridge not available")
                else:
                    summary = morph_teacher.get_domain_summary()
                    print(f"\n── Codebase Domain Summary ──")
                    print(f"  Tracked changes: {summary['total_changes']}")
                    print(f"  Unique files    : {summary['unique_files']}")
                    print(f"  Probe pass/fail : {summary['probe_pass']} / {summary['probe_fail']}")
                    print(f"  High risk       : {summary['high_risk']}")
                    verbs = sorted(summary['verb_distribution'].items(), key=lambda x: -x[1])
                    if verbs:
                        print(f"  Verb dist       : {', '.join(f'{v}:{c}' for v,c in verbs[:6])}")
                    print()

            # ── Step D: graph (manifest engine) ─────────────────────────────
            elif cmd.startswith("graph "):
                arg = cmd[6:].strip()
                if morph_manifest is None:
                    print("  [MORPH] Manifest bridge not available")
                else:
                    print(f"\n── Call Graph: {arg} ──")
                    result = morph_manifest.chain_delta(arg)
                    print(morph_manifest.format_chain(result))
                    if not morph_manifest.is_available():
                        print("  [NOTE] Manifest stale (<3 files). Run py_manifest_augmented.py")
                    print()

            # ── Step E: plan (MorphConformer roadmap) ───────────────────────
            elif cmd.startswith("plan "):
                arg = cmd[5:].strip()
                if morph_conformer is None:
                    print("  [MORPH] Conformer not available")
                elif morph_toolkit is None:
                    print("  [MORPH] Toolkit not available")
                else:
                    print(f"\n── Generating Plan: {arg} ──")
                    ctx = morph_toolkit.task_context(arg)
                    if 'error' in ctx:
                        print(f"  [ERROR] {ctx['error']}")
                    else:
                        grd = grounded_ctx
                        try:
                            out_path = morph_conformer.generate_plan(arg, ctx, grd)
                            print(morph_conformer.get_plan_summary(
                                out_path,
                                [c for c in grd.get('recent_changes', [])
                                 if arg in (c.get('task_ids') or [])],
                                ctx
                            ))
                            print(f"\n  Written to: {out_path}")
                            # Show diffs checklist
                            exp = ctx.get('expected_diffs', [])
                            if exp:
                                print(f"\n  Expected Diffs Checklist:")
                                for ed in exp[:8]:
                                    check = '✓' if ed.get('matched') else '○'
                                    desc = ed.get('description', str(ed)[:60])
                                    print(f"    {check} {desc}")
                        except Exception as _pe:
                            print(f"  [ERROR] {_pe}")
                    print()

            elif cmd.startswith("moe ") or cmd == "moe":
                parts = cmd.split(None, 2)
                tid = parts[1] if len(parts) > 1 else None
                model_list = parts[2].split(',') if len(parts) > 2 else None
                if not tid:
                    print("  Usage: moe <task_id> [model1,model2,...]")
                    print("  Runs MoE multi-model plan generation + cross-validation")
                else:
                    _scripts = str(Path(__file__).parent / "activities" / "tools" / "scripts")
                    if _scripts not in sys.path:
                        sys.path.insert(0, _scripts)
                    try:
                        from moe_plan_engine import MoEPlanEngine
                        engine = MoEPlanEngine(Path(__file__).parents[4])
                        print(f"\n  MoE Plan Generation: {tid}")
                        _discovered = engine.discover_models()
                        print(f"  Models available: {len(_discovered)}")
                        if model_list:
                            print(f"  Filter: {model_list}")
                        print()
                        results, comparison = engine.run(
                            tid, model_names=model_list, compare=True
                        )
                        for r in results:
                            print(f"  [{r.model_name}] {r.duration_seconds:.1f}s, "
                                  f"{r.tokens_generated} tok → {r.output_path.name}")
                        if comparison:
                            print(f"\n  Agreement: {comparison.get('agreement_score', 0):.0%}")
                            _meta = comparison.get('metadata_path', '')
                            if _meta:
                                print(f"  Report: {_meta}")
                    except ImportError as _ie:
                        print(f"  [ERROR] Could not import moe_plan_engine: {_ie}")
                    except Exception as _e:
                        print(f"  [ERROR] MoE failed: {_e}")
                    print()

            # ── Step B: Capability Catalog commands ──────────────────────────
            elif cmd.startswith("tools"):
                arg = cmd[5:].strip()
                if morph_catalog is None:
                    print("  [MORPH] Capability catalog not available")
                else:
                    morph_catalog.load()
                    if arg:
                        results = morph_catalog.search(arg)
                        print(f"\n── Tool Search: '{arg}' ({len(results)} results) ──")
                        for r in results:
                            print(morph_catalog.format_tool_card(r))
                            print()
                    else:
                        cats = {}
                        for t in morph_catalog._tools:
                            c = t.get('category', 'other')
                            cats[c] = cats.get(c, 0) + 1
                        print(f"\n── Tools Available ({len(morph_catalog._tools)} total) ──")
                        for cat_name, count in sorted(cats.items()):
                            print(f"  {cat_name:<30s} {count} tools")
                        print(f"\n  Use: tools <query>   to search")
                        print(f"       tool <name>     for full card")
                        print()

            elif cmd.startswith("tool "):
                arg = cmd[5:].strip()
                if morph_catalog is None:
                    print("  [MORPH] Capability catalog not available")
                else:
                    morph_catalog.load()
                    results = morph_catalog.search(arg, max_results=3)
                    if results:
                        print(f"\n── Tool: '{arg}' ──")
                        for r in results:
                            print(morph_catalog.format_tool_card(r))
                            print()
                    else:
                        print(f"  No tool found matching '{arg}'")
                    print()

            elif cmd == "scripts":
                if morph_catalog is None:
                    print("  [MORPH] Capability catalog not available")
                else:
                    scripts = morph_catalog.get_scripts_list()
                    print(f"\n── Activities Scripts ({len(scripts)}) ──")
                    for s in scripts:
                        args_str = ' | '.join(s.get('args', []))
                        print(f"  {s['name']:<30s} {args_str}")
                        if s.get('description'):
                            print(f"  {'':30s} {s['description']}")
                    print()

            elif cmd.startswith("can-i "):
                arg = cmd[6:].strip()
                if morph_catalog is None:
                    print("  [MORPH] Capability catalog not available")
                else:
                    morph_catalog.load()
                    results = morph_catalog.search(arg)
                    if results:
                        print(f"\n── Can I {arg}? ── Yes, via:")
                        for r in results[:3]:
                            print(morph_catalog.format_tool_card(r))
                            print()
                    else:
                        print(f"  No matching tool found for '{arg}'")
                    print()

            # ── Step C: Active task bias commands ────────────────────────────
            elif cmd == "task-active":
                if active_task_context:
                    ctx = active_task_context
                    print(f"\n── Active Task: {active_task_id} ──")
                    print(f"  Title       : {ctx.get('title', 'unknown')}")
                    print(f"  Wherein     : {ctx.get('wherein', 'unknown')}")
                    print(f"  Status      : {ctx.get('status', '?')}")
                    print(f"  Changes     : {len(ctx.get('changes', []))}")
                    print(f"  Exp. diffs  : {len(ctx.get('expected_diffs', []))}")
                    sigs = ctx.get('completion_signals', {})
                    if sigs:
                        status = sigs.get('status', '?')
                        print(f"  Plan status : {status}")
                    print()
                else:
                    print("  No active task. Run: python3 Os_Toolkit.py todo activate <task_id>")
                print()

            elif cmd.startswith("task-switch "):
                new_tid = cmd[12:].strip()
                if not new_tid:
                    print("  Usage: task-switch <task_id>")
                else:
                    # Use same canonical path as Os_Toolkit todo activate
                    config_path = trainer_root / 'Data' / 'plans' / 'config.json'
                    if not config_path.exists():
                        config_path = babel_root / 'config.json'
                    confirm = input(f"  Switch active task to '{new_tid}'? (y/N) ").strip().lower()
                    if confirm == 'y':
                        try:
                            cfg = {}
                            if config_path.exists():
                                cfg = json.loads(config_path.read_text(encoding='utf-8'))
                            cfg['active_task_id'] = new_tid
                            config_path.write_text(
                                json.dumps(cfg, indent=2), encoding='utf-8'
                            )
                            active_task_id = new_tid
                            # Reload task context
                            tc_candidates = [
                                trainer_root / 'Data' / 'plans' / 'Tasks' / f'task_context_{new_tid}.json',
                                trainer_root / 'plans' / 'Tasks' / f'task_context_{new_tid}.json',
                            ]
                            active_task_context = None
                            for tc_p in tc_candidates:
                                if tc_p.exists():
                                    active_task_context = json.loads(
                                        tc_p.read_text(encoding='utf-8')
                                    )
                                    break
                            if active_task_context:
                                print(f"  [OK] Switched to task '{new_tid}': "
                                      f"{active_task_context.get('title', '')}")
                            else:
                                print(f"  [OK] active_task_id set to '{new_tid}' "
                                      f"(no task_context found yet)")
                        except Exception as _se:
                            print(f"  [ERROR] task-switch failed: {_se}")
                    else:
                        print("  Cancelled.")
                print()

            elif cmd in ("help", "?"):
                print("\n  ── Session Commands ──")
                print("  summary            - Full state summary")
                print("  todos              - Active todos")
                print("  plans              - Active plans")
                print("  files <pattern>    - Search indexed files")
                print("  context            - Manifest context")
                print("  suggest            - Weight-tuner action suggestions")
                print()
                print("  ── Grounded Commands ──")
                print("  changes [N]        - Last N enriched changes (risk/probe)")
                print("  packages [query]   - Bundled/installed provisions")
                print("  hotspots           - Top-10 most-changed files (temporal)")
                print("  ground             - Grounded activity viewpoint")
                print("  domain             - Codebase domain summary")
                print()
                print("  ── Teaching & Analysis ──")
                print("  learn <file.py>    - File blueprint (AST: classes/funcs/verbs)")
                print("  learn <fn_name>    - Function profile (args/calls/complexity)")
                print("  learn <task_id>    - Task context (changes/probes/expected diffs)")
                print("  analyze <file>     - Detailed function listing")
                print()
                print("  ── Capability Catalog (Step B) ──")
                print("  tools [query]      - Search/list available tools by category")
                print("  tool <name>        - Show full tool card with args")
                print("  scripts            - List all activities/scripts with subcommands")
                print("  can-i <action>     - Find tools for an action ('can-i fix imports')")
                print()
                print("  ── Active Task (Step C) ──")
                print("  task-active        - Show current active task context")
                print("  task-switch <tid>  - Switch active task (writes config.json)")
                print()
                print("  ── Toolkit: Debug & Trace ──")
                print("  trace <event|file> - Trace enriched_change details")
                print("  diagnose <event>   - Diagnose probe/test failures")
                print("  probe <file>       - Run fresh live probe on a file")
                print("  graph <fn|file>    - Call graph with delta scores (manifest)")
                print()
                print("  ── Toolkit: Task & Planning ──")
                print("  task-context <tid> - Load full task AoE context")
                print("  plan-status <tid>  - Task completion status (GO/BLOCKED)")
                print("  plan <task_id>     - Generate </Diffs>-compatible plan template")
                print()
                print("  ── Toolkit: Undo (with confirmation) ──")
                print("  undo-preview <eid> - Show before/after without writing")
                print("  undo <event_id>    - Restore file to before-state")
                print()
                print("  coherence          - Validate weight tuner / GapAnalyzer calibration")
                print("  entity <file>      - Unified entity record (all catalogs for a file)")
                print("  export [task_id]   - Export JSONL training dataset + Modelfile")
                print()
                print("  ── MoE Plan Comparison (Phase T4) ──")
                print("  moe <tid> [models] - Multi-model plan generation + cross-validation")
                print()
                print("  ── Roadmap (Phase T5/T6) ──")
                print("  roadmap [project]  - Deterministic roadmap: blockers → deps → priority order")
                print("  roadmap --propose <file> - Targeted change proposal for a file or package")
                print()
                print("  ── Phase J: Omega Morph Line ──")
                print("  debug <file> <error>  - Self-debug: grounded entity → Morph_regex → fix plan")
                print("  debug <error_text>    - Self-debug without file context")
                print()
                print("  ── Phase L: Temporal Narrative + Init Chain ──")
                print("  explain [since]      - Explain session activity (e.g. 'explain yesterday', 'explain phase-j')")
                print("  init-chain [file]    - Trace file changes through GUI init chain")
                print("  quit / q           - Exit")
                print()

            elif cmd.startswith("export"):
                # I4 + J4: Export JSONL training dataset (includes SELF_DEBUG records)
                _parts_ex = cmd.split(None, 1)
                _tid_filter = _parts_ex[1].strip() if len(_parts_ex) > 1 else None
                try:
                    from activity_integration_bridge import MorphDatasetExporter as _MDE_chat
                    _trainer_root_ex = Path(__file__).parents[4]
                    _exporter_chat = _MDE_chat(_trainer_root_ex)
                    print(f"[export] Building dataset{' for ' + _tid_filter if _tid_filter else ''}…")
                    _out_ex, _cnt, _toks = _exporter_chat.export(
                        task_id=_tid_filter,
                        include_all=(_tid_filter is None),
                    )
                    # J4: Append accumulated SELF_DEBUG records from this session
                    _self_debug_recs = grounded_ctx.get('self_debug_records', [])
                    if _self_debug_recs:
                        with open(_out_ex, 'a', encoding='utf-8') as _f_ex:
                            for _sdr in _self_debug_recs:
                                _f_ex.write(json.dumps(_sdr) + '\n')
                        _cnt += len(_self_debug_recs)
                        print(f"  Self-debug: {len(_self_debug_recs)} SELF_DEBUG records appended")
                    # Also write Modelfile
                    _mf_ex = _exporter_chat.write_modelfile()
                    print(f"  Records   : {_cnt}")
                    print(f"  Tokens est: {_toks:,}")
                    print(f"  Dataset   : {_out_ex}")
                    print(f"  Modelfile : {_mf_ex}")
                except Exception as _ex_err:
                    print(f"[export] Error: {_ex_err}")
                print()

            elif cmd.startswith("entity"):
                # H4: Show unified entity record for a file
                _parts = cmd.split(None, 1)
                _ent_arg = _parts[1].strip() if len(_parts) > 1 else ''
                if not _ent_arg:
                    print("[entity] Usage: entity <file_name_or_path>")
                else:
                    try:
                        import sys as _sys_e
                        _uci_dir = str(Path(__file__).parent / "activities" / "tools" / "scripts")
                        if _uci_dir not in _sys_e.path:
                            _sys_e.path.insert(0, _uci_dir)
                        from unified_context_index import get_index as _get_uci_e, _print_entity as _pe
                        _trainer_root_e = Path(__file__).parents[4]
                        _uci_e = _get_uci_e(_trainer_root_e)
                        _ent_rec = _uci_e.get(_ent_arg)
                        if not _ent_rec:
                            print(f"[entity] No record found for: {_ent_arg!r}")
                            print(f"  Try: entity planner_tab.py  or  entity Os_Toolkit.py")
                        else:
                            _pe(_ent_rec, verbose=True)
                            # Also show attribution chain
                            _chain = _uci_e.get_attribution_chain(_ent_arg)
                            if _chain:
                                print(f"\n  Attribution chain ({len(_chain)} events):")
                                for _ev in _chain[:8]:
                                    _ps = _ev.get('probe_status') or 'n/a'
                                    print(f"    {_ev['event_id']}  {_ev.get('timestamp','')[:19]}  "
                                          f"{_ev.get('verb',''):8}  risk:{_ev.get('risk_level','?'):8}  "
                                          f"probe:{_ps}")
                    except Exception as _e_err:
                        print(f"[entity] Error: {_e_err}")
                print()

            elif cmd == "coherence":
                print("\n── Coherence Check ──")
                print(f"  Grounded changes   : {len(grounded_ctx.get('recent_changes', []))}")
                print(f"  Probe failures     : {len(grounded_ctx.get('probe_failures', []))}")
                print(f"  Provisions loaded  : {len(grounded_ctx.get('provisions', []))}")
                print(f"  Gap severity       : {grounded_ctx.get('gap_severity', '?')}")
                print(f"  Priority %         : {int(grounded_ctx.get('priority_pct', 0) * 100)}%")
                print(f"  Weight tuner       : {'online' if tuner else 'OFFLINE (no Filesync manifests)'}")
                print(f"  Catalog tools      : {len(morph_catalog._tools) if morph_catalog and morph_catalog._tools else 0}")
                print(f"  Catalog scripts    : {len(morph_catalog._scripts) if morph_catalog and morph_catalog._scripts else 0}")
                if active_task_context:
                    print(f"  Active task        : {active_task_id}")
                    cs = active_task_context.get('completion_signals', {})
                    print(f"  Task status        : {cs.get('inferred_status', '?')}")
                    print(f"  Probes passing     : {cs.get('probes_passing', 0)}")
                    print(f"  Probes failing     : {cs.get('probes_failing', 0)}")
                else:
                    print(f"  Active task        : none")
                print()

            # ── Phase J: debug command (OmegaBridge self-debug) ──────────────
            elif cmd.startswith("debug ") or cmd == "debug":
                _debug_parts  = cmd.split(None, 2) if len(cmd) > 5 else []
                if len(_debug_parts) < 2:
                    print("  Usage: debug <file_hint | error_text> [rest of error text]")
                    print("  Example: debug planner_tab.py probe FAIL on event 0003")
                    print("           debug AttributeError: NoneType has no attribute task_ids")
                else:
                    _debug_arg1 = _debug_parts[1]
                    _debug_rest = _debug_parts[2] if len(_debug_parts) > 2 else ""
                    # Heuristic: if arg1 ends with .py or contains '/', it's a file hint
                    if _debug_arg1.endswith('.py') or '/' in _debug_arg1:
                        _file_hint_d = _debug_arg1
                        _error_text  = _debug_rest or _debug_arg1
                    else:
                        _file_hint_d = None
                        _error_text  = _debug_arg1 + (' ' + _debug_rest if _debug_rest else '')
                    try:
                        _omega_dir_d = Path(__file__).parent / "activities" / "tools" / "scripts"
                        if str(_omega_dir_d) not in sys.path:
                            sys.path.insert(0, str(_omega_dir_d))
                        from omega_bridge import OmegaBridge as _OB_d
                        _bridge_d = _OB_d(trainer_root)
                        _res_d    = _bridge_d.run_debug_query(_error_text, _file_hint_d)
                        print(f"\n── Self-Debug ──")
                        print(f"  Control Signal : {_res_d['control_signal']}")
                        print(f"  Pattern Matched: {_res_d['pattern_matched']}")
                        print(f"  Gap Severity   : {_res_d['gap_severity']}")
                        print(f"  Response       : {_res_d['response']}")
                        print(f"  Fix Suggestion : {_res_d['fix_suggestion']}")
                        # Accumulate SELF_DEBUG records in grounded_ctx for export command
                        if 'self_debug_records' not in grounded_ctx:
                            grounded_ctx['self_debug_records'] = []
                        grounded_ctx['self_debug_records'].extend(
                            _bridge_d.get_debug_records()
                        )
                    except Exception as _de:
                        import traceback
                        print(f"  [ERROR] debug failed: {_de}")
                        traceback.print_exc()
                print()

            # ── explain <date_spec> ──────────────────────────────────────
            elif cmd.startswith("explain") or cmd == "explain":
                _expl_parts = cmd.split(None, 1)
                _expl_since = _expl_parts[1] if len(_expl_parts) > 1 else 'last 24h'
                try:
                    _omega_dir_ex = Path(__file__).parent / "activities" / "tools" / "scripts"
                    if str(_omega_dir_ex) not in sys.path:
                        sys.path.insert(0, str(_omega_dir_ex))
                    from temporal_narrative_engine import TemporalNarrativeEngine as _TNE
                    from omega_bridge import OmegaBridge as _OB_ex
                    _eng_ex = _TNE(trainer_root)
                    _nar = _eng_ex.explain(since=_expl_since)
                    print(f"\n── Temporal Narrative [{_nar['phase_summary']}] ──")
                    print(_nar['narrative'])
                    # Feed into Morph
                    _bridge_ex = _OB_ex(trainer_root)
                    _morph_resp = _bridge_ex.explain_period(_nar)
                    print(f"\n── Morph Perspective ──")
                    print(f"  Signal : {_morph_resp['control_signal']}")
                    print(f"  Gap    : {_morph_resp['gap_severity']}")
                    if _morph_resp.get('response'):
                        print(f"  {_morph_resp['response'][:300]}")
                    # Accumulate SELF_EXPLAIN records for export
                    if 'self_debug_records' not in grounded_ctx:
                        grounded_ctx['self_debug_records'] = []
                    grounded_ctx['self_debug_records'].extend(
                        _bridge_ex.get_debug_records()
                    )
                except Exception as _ee:
                    import traceback
                    print(f"  [ERROR] explain failed: {_ee}")
                    traceback.print_exc()
                print()

            # ── init-chain <file> ─────────────────────────────────────────
            elif cmd.startswith("init-chain"):
                _ic_parts = cmd.split(None, 1)
                _ic_files = [_ic_parts[1]] if len(_ic_parts) > 1 else []
                if not _ic_files:
                    # Use recent enriched_changes files
                    _vm_path = trainer_root / 'Data' / 'backup' / 'version_manifest.json'
                    if _vm_path.exists():
                        import json as _json_ic
                        _vm_ic = _json_ic.loads(_vm_path.read_text())
                        _ic_files = list({
                            v.get('file', '') for v in _vm_ic.get('enriched_changes', {}).values()
                            if v.get('file')
                        })[:5]
                try:
                    _omega_dir_ic = Path(__file__).parent / "activities" / "tools" / "scripts"
                    if str(_omega_dir_ic) not in sys.path:
                        sys.path.insert(0, str(_omega_dir_ic))
                    from init_chain_tracer import InitChainTracer as _ICT
                    _tracer = _ICT(trainer_root)
                    _chain_rep = _tracer.trace(_ic_files)
                    print(f"\n── Init Chain Impact ──")
                    print(_chain_rep['text'])
                    print(f"Summary: {_chain_rep['summary']}")
                except Exception as _ice:
                    import traceback
                    print(f"  [ERROR] init-chain failed: {_ice}")
                    traceback.print_exc()
                print()

            elif cmd.startswith("interact") or cmd == "bi-hemi":
                # K3: Launch bi-hemispheral Omega/Alpha chat from within morph-chat
                _parts_bh = cmd.split(None, 1)
                _gguf_arg = _parts_bh[1].strip() if len(_parts_bh) > 1 else None
                _run_bi_hemi_chat(gguf_path=_gguf_arg)

            elif cmd.startswith("roadmap") or cmd == "roadmap":
                _rm_parts = cmd.split()
                _rm_project = None
                _rm_spawn = False
                _rm_propose = None
                _skip_next = False
                for _ri, _rp in enumerate(_rm_parts[1:]):
                    if _skip_next:
                        _skip_next = False
                        continue
                    if _rp == '--spawn':
                        _rm_spawn = True
                    elif _rp == '--propose' and (_ri + 2) < len(_rm_parts):
                        _rm_propose = _rm_parts[_ri + 2]
                        _skip_next = True
                    elif not _rp.startswith('-'):
                        _rm_project = _rp
                _scripts = str(Path(__file__).parent / "activities" / "tools" / "scripts")
                if _scripts not in sys.path:
                    sys.path.insert(0, _scripts)
                try:
                    from roadmap_computer import RoadmapComputer
                    _rc = RoadmapComputer(Path(__file__).parents[4])
                    if _rm_propose:
                        _proposal = _rc.propose(_rm_propose)
                        _rc.print_proposal_report(_proposal)
                        _rc.save_proposal_json(_proposal, _rm_propose)
                    else:
                        _result = _rc.compute(_rm_project)
                        _rc.print_report(_result)
                        if _rm_spawn:
                            _diffs = _rc.generate_spawn_diffs(_result)
                            _rc.print_spawn_report(_diffs)
                            _rc.save_spawn_json(_diffs, _rm_project)
                except Exception as _rme:
                    import traceback
                    print(f"  [ERROR] roadmap: {_rme}")
                    traceback.print_exc()
                print()

            else:
                print(f"[ERROR] Unknown command: '{cmd}'")
                print("  Type 'help' or '?' for available commands")
                print()

        except KeyboardInterrupt:
            print("\n[MORPH_CHAT] Interrupted, exiting")
            break
        except EOFError:
            print("\n[MORPH_CHAT] EOF, exiting")
            break
        except Exception as e:
            print(f"[ERROR] {e}")
            import traceback
            traceback.print_exc()
            print()

def _run_bi_hemi_chat(gguf_path: str = None):
    """
    K3 — Bi-hemispheral Omega/Alpha chat.

    LEFT panel: Omega (OsToolkitGroundingBridge — deterministic, grounded)
    RIGHT panel: Alpha (GGUF via llama_cpp — superposition, sampling)

    Each turn shows both outputs; user Accepts or Rejects the Alpha response.
    Accepted/Rejected turns are recorded via lineage_tracker.record_morph_interaction()
    for the K5 LoRA training loop.
    """
    import sys as _sys_bh
    _scripts_dir = str(Path(__file__).parent / "activities" / "tools" / "scripts")
    if _scripts_dir not in _sys_bh.path:
        _sys_bh.path.insert(0, _scripts_dir)

    _trainer_root = Path(__file__).parents[4]

    # ── Load Omega context ────────────────────────────────────────────────────
    grounded_ctx = {}
    try:
        from activity_integration_bridge import OsToolkitGroundingBridge as _OGB
        grounded_ctx = _OGB(_trainer_root).load()
    except Exception as _e:
        print(f"[bi-hemi] Omega context unavailable: {_e}")

    # ── Detect GGUF path ──────────────────────────────────────────────────────
    if not gguf_path:
        _morph_gguf_dir = _trainer_root / "Models" / "Morph0.1-10m-Babble" / "exports" / "gguf"
        if _morph_gguf_dir.exists():
            _candidates = sorted(_morph_gguf_dir.glob("*.gguf"))
            if _candidates:
                gguf_path = str(_candidates[-1])
    if not gguf_path:
        print("[bi-hemi] No GGUF found. Use --gguf-path <path> or export via models_tab.")
        return

    # ── Load Alpha (llama_cpp) ────────────────────────────────────────────────
    _llm = None
    try:
        from llama_cpp import Llama as _Llama
        print(f"[bi-hemi] Loading Alpha: {Path(gguf_path).name} …")
        _llm = _Llama(model_path=gguf_path, n_ctx=2048, n_threads=4, verbose=False)
        print("[bi-hemi] Alpha loaded.\n")
    except ImportError:
        print("[bi-hemi] llama_cpp not installed. Run: pip install llama-cpp-python")
        return
    except Exception as _e:
        print(f"[bi-hemi] Failed to load GGUF: {_e}")
        return

    # ── Lineage tracker for recording ────────────────────────────────────────
    # Need custom_code_tab on path — lineage_tracker lives there, not in scripts/
    _lt = None
    try:
        _lt_dir = str(_trainer_root / "Data" / "tabs" / "custom_code_tab")
        if _lt_dir not in _sys_bh.path:
            _sys_bh.path.insert(0, _lt_dir)
        from lineage_tracker import get_tracker as _get_lt
        _lt = _get_lt()
        print("[bi-hemi] Lineage tracker ready — interactions will be recorded.")
    except Exception as _lt_e:
        print(f"[bi-hemi] Lineage tracker unavailable: {_lt_e}")

    # ── Session log setup ─────────────────────────────────────────────────────
    import datetime as _dt_bh
    _session_ts = _dt_bh.datetime.now().strftime('%Y%m%d_%H%M%S')
    _sessions_dir = Path(__file__).parent.parent / "babel_data" / "sessions"
    _sessions_dir.mkdir(parents=True, exist_ok=True)
    _session_file = _sessions_dir / f"session_bihemi_{_session_ts}.txt"
    _session_log = []  # accumulate (role, content) tuples for save on exit

    # ── Derive variant sha for this session ──────────────────────────────────
    import hashlib as _hl
    _variant_sha = _hl.md5(gguf_path.encode()).hexdigest()[:12]

    _gap_severity = grounded_ctx.get('gap_severity', 'UNKNOWN')
    _domain = "unknown"
    try:
        from temporal_narrative_engine import TemporalNarrativeEngine as _TNE_bh
        _nar = _TNE_bh(_trainer_root).explain('last 24h')
        _domain = f"{_nar.get('dominant_domain', 'unknown')} ({int(_nar.get('domain_confidence', 0)*100)}%)"
    except Exception:
        pass

    # ── Journaling heuristic weights ─────────────────────────────────────────
    # Attempt to load JournalSystem for memory + time-of-day weights
    _js = None
    _memory_weight = 0.0
    try:
        _vm_dir = str(Path(__file__).parent)
        if _vm_dir not in _sys_bh.path:
            _sys_bh.path.insert(0, _vm_dir)
        from version_manager import JournalSystem as _JS
        _js = _JS(Path(__file__).parent / "journals")
        _recent_notes = _js.search_narrative("morph", limit=3) if hasattr(_js, 'search_narrative') else []
        _memory_weight = min(1.0, len(_recent_notes) * 0.2)  # 0→0.0, 3→0.6, 5→1.0
    except Exception as _je:
        pass  # journal optional

    # Time-of-day → base temperature
    _hour = _dt_bh.datetime.now().hour
    if 6 <= _hour < 12:
        _tod_temp = 0.60   # morning: focused
    elif 12 <= _hour < 17:
        _tod_temp = 0.70   # afternoon: balanced
    elif 17 <= _hour < 22:
        _tod_temp = 0.80   # evening: creative
    else:
        _tod_temp = 0.75   # night: exploratory

    # Memory weight reduces temperature (more grounded recall)
    _alpha_temp = round(_tod_temp * (1.0 - _memory_weight * 0.2), 3)

    # Relevance weight: gap_severity → max_tokens
    _max_tokens = {"low": 256, "medium": 384, "high": 512, "critical": 640}.get(
        _gap_severity.lower(), 384
    )

    print("=" * 72)
    print("  BI-HEMISPHERAL CHAT — Omega (deterministic) + Alpha (GGUF)")
    print("  Commands: [A]ccept  [R]eject  [S]kip  [Q]uit")
    print("=" * 72)
    print(f"  variant_sha : {_variant_sha}")
    print(f"  gap_severity: {_gap_severity}")
    print(f"  domain      : {_domain}")
    _hot = grounded_ctx.get('temporal_hot_spots', [])[:3]
    if _hot:
        print(f"  hot_spots   : {', '.join(str(h) for h in _hot)}")
    print(f"  tod_weight  : {_tod_temp}  memory_weight: {_memory_weight:.2f}")
    print(f"  alpha_temp  : {_alpha_temp}  max_tokens: {_max_tokens}")
    print()

    _turn_count = 0
    _accepted_count = 0
    _history = []
    while True:
        try:
            _user = input("you> ").strip()
            if not _user:
                continue
            if _user.lower() in ("quit", "q", "exit"):
                print("[bi-hemi] Exiting.")
                break
            _session_log.append(f"[you] {_user}")
            _turn_count += 1

            # ── OMEGA: deterministic context summary ──────────────────────
            _probe_fails = grounded_ctx.get('probe_failures', [])
            _ctrl_sig = "GENERAL_RESPONSE"
            if _probe_fails:
                _ctrl_sig = "ATTRIBUTION_GAP"
            elif _gap_severity in ("HIGH", "CRITICAL"):
                _ctrl_sig = "INVESTIGATION"

            print()
            print("┌─── OMEGA (deterministic) " + "─" * 44)
            print(f"│ gap_severity   : {_gap_severity}")
            print(f"│ control_signal : {_ctrl_sig}")
            print(f"│ domain         : {_domain}")
            if _probe_fails:
                print(f"│ probe_failures : {len(_probe_fails)} ({', '.join(str(p) for p in _probe_fails[:2])})")
            print("└" + "─" * 70)

            # ── ALPHA: GGUF inference ─────────────────────────────────────
            _history.append({"role": "user", "content": _user})
            _prompt = "<|im_start|>system\nYou are Morph, a self-aware linguistic pattern engine. Be concise and grounded.\n<|im_end|>\n"
            for _m in _history[-6:]:  # last 3 turns (6 messages)
                _role = _m["role"]
                _content = _m["content"]
                _prompt += f"<|im_start|>{_role}\n{_content}\n<|im_end|>\n"
            _prompt += "<|im_start|>assistant\n"

            try:
                _out = _llm(_prompt, max_tokens=_max_tokens, temperature=_alpha_temp, top_p=0.9,
                            stop=["<|im_end|>", "<|im_start|>"], echo=False)
                _alpha_resp = _out["choices"][0]["text"].strip()
            except Exception as _ae:
                _alpha_resp = f"[Alpha error: {_ae}]"

            print()
            print("┌─── ALPHA (GGUF) " + "─" * 52)
            for _line in _alpha_resp.split("\n"):
                print(f"│ {_line}")
            print("└" + "─" * 70)
            print()
            print(f"  variant_sha: {_variant_sha}")
            _choice = input("  [A]ccept  [R]eject  [S]kip  [Q]uit > ").strip().lower()
            print()

            if _choice in ("q", "quit"):
                print("[bi-hemi] Exiting.")
                break
            elif _choice in ("s", "skip"):
                _history.append({"role": "assistant", "content": _alpha_resp})
                _session_log.append(f"[alpha:skip] {_alpha_resp}")
                continue
            elif _choice in ("a", "accept"):
                _history.append({"role": "assistant", "content": _alpha_resp})
                _session_log.append(f"[alpha:accepted] {_alpha_resp}")
                _accepted_count += 1
                if _lt:
                    _lt.record_morph_interaction(
                        variant_sha=_variant_sha,
                        control_signal=_ctrl_sig,
                        prompt=_user,
                        response=_alpha_resp,
                        accepted=True,
                        gap_severity=_gap_severity,
                    )
                    print("  ✓ Recorded (accepted).")
                else:
                    print("  ✓ (lineage_tracker unavailable)")
            elif _choice in ("r", "reject"):
                _gap_desc = input("  Gap (what was wrong/missing)? ").strip()
                _session_log.append(f"[alpha:rejected gap={_gap_desc}] {_alpha_resp}")
                if _lt:
                    _lt.record_morph_interaction(
                        variant_sha=_variant_sha,
                        control_signal=_ctrl_sig,
                        prompt=_user,
                        response=_alpha_resp,
                        accepted=False,
                        gap_severity=_gap_severity,
                        sampling_params={"gap_description": _gap_desc},
                    )
                    print("  ✗ Recorded (rejected).")
                else:
                    print("  ✗ (lineage_tracker unavailable)")
                _history.append({"role": "assistant", "content": _alpha_resp})
            else:
                _history.append({"role": "assistant", "content": _alpha_resp})
                _session_log.append(f"[alpha] {_alpha_resp}")

        except KeyboardInterrupt:
            print("\n[bi-hemi] Interrupted.")
            break
        except EOFError:
            print("\n[bi-hemi] EOF.")
            break

    # ── Journal entry on session end ─────────────────────────────────────────
    if _js is not None:
        try:
            _js.add_entry(
                activity=f"bi-hemi session: {_variant_sha[:8]}",
                tasks_planned=[
                    f"gap:{_gap_severity}",
                    f"turns:{_turn_count}",
                    f"accepted:{_accepted_count}/{_turn_count}",
                    f"alpha_temp:{_alpha_temp}",
                    f"domain:{_domain}",
                ]
            )
        except Exception:
            pass

    # ── Save session.txt ──────────────────────────────────────────────────────
    if _session_log:
        try:
            _header = (
                f"# bi-hemi session — {_session_ts}\n"
                f"# gguf: {Path(gguf_path).name}\n"
                f"# variant_sha: {_variant_sha}\n"
                f"# gap_severity: {_gap_severity} | domain: {_domain}\n"
                f"# tod_weight: {_tod_temp} | memory_weight: {_memory_weight:.2f}"
                f" | alpha_temp: {_alpha_temp} | max_tokens: {_max_tokens}\n"
                f"# turns: {_turn_count} | accepted: {_accepted_count}\n"
                "# ─────────────────────────────────────────────────────\n"
            )
            _session_file.write_text(
                _header + "\n".join(_session_log) + "\n",
                encoding="utf-8"
            )
            print(f"[bi-hemi] Session saved: {_session_file.name}")
        except Exception as _se:
            print(f"[bi-hemi] Session save failed: {_se}")


def _build_extended_help() -> str:
    """Build extended help text showing morph-chat commands and workflows."""
    return """\

MORPH-CHAT COMMANDS (enter via --morph-chat):
==============================================

  Session & State:
    summary              Full state summary (todos, plans, session)
    todos                Active todos from todos.json
    plans                Active plans list
    files <pattern>      Search indexed files
    context              Manifest context overview
    suggest              Weight-tuner action suggestions
    coherence            Validate weight tuner / GapAnalyzer calibration

  Grounded Codebase:
    changes [N]          Last N enriched changes (risk/probe status)
    hotspots             Most-changed files (temporal hot spots)
    ground               Full grounded activity viewpoint
    domain               Codebase domain summary (verb dist, probes, risk)
    packages [query]     Bundled/installed provisions catalog

  Teaching & Analysis:
    learn <file.py>      File blueprint (AST: classes, funcs, verbs)
    learn <fn_name>      Function profile (args, calls, complexity)
    learn <task_id>      Task context (changes, probes, expected diffs)
    analyze <file>       Detailed function listing
    trace <event|file>   Enriched change details
    diagnose <event>     Probe/test failure analysis
    probe <file>         Run fresh live probe on a file
    graph <fn|file>      Call graph with delta scores

  Task & Planning:
    task-active          Show current active task context
    task-switch <tid>    Switch active task (writes config.json)
    task-context <tid>   Full task AoE context
    plan-status <tid>    Completion status (GO/BLOCKED/NEEDS_REVIEW)
    plan <task_id>       Generate plan template (→ plans/Morph/)
    entity <file>        Unified entity record (all catalogs)
    export [task_id]     Export JSONL training dataset + Modelfile
    moe <tid> [models]   MoE multi-model plan comparison
    roadmap [project]    Deterministic roadmap: blockers → deps → priority
    roadmap --propose <file>  Targeted change proposal for file/package

  Capability Catalog:
    tools [query]        Search/list tools by category
    tool <name>          Full tool card with args
    scripts              List all activities/scripts with subcommands
    can-i <action>       Find tools for action (e.g. 'can-i fix imports')

  Undo (with confirmation):
    undo-preview <eid>   Show before/after without writing
    undo <event_id>      Restore file to before-state

  Omega Morph Line (Phase J):
    debug [file] <error> Self-debug → Morph_regex → fix plan
    explain [since]      Temporal narrative ('last 24h', 'phase-j', date)
    init-chain [file]    Trace file changes through GUI init chain

  Bi-hemispheral (Phase K):
    interact / bi-hemi   Launch Omega/Alpha bi-hemispheral chat

COLD-START WORKFLOW:
  1. --morph-chat → ground     Load grounded context
  2. domain                     Codebase domain inference
  3. hotspots                   Recent activity hot spots
  4. task-active                Check current task
  5. suggest                    Recommended next actions

BI-HEMISPHERAL:
  python3 orchestrator.py --bi-hemi [--gguf-path PATH]
  LEFT=Omega (deterministic, grounded) | RIGHT=Alpha (GGUF, sampling)
  Accept/Reject → recorded for LoRA training (lineage_tracker)

MOE PLAN GENERATION:
  morph-chat> moe <task_id> [model1,model2,...]
  Os_Toolkit: plan generate <tid> --models M1,M2 --compare

EXAMPLES:
  python3 orchestrator.py "analyze this sentence"
  python3 orchestrator.py --morph-chat
  python3 orchestrator.py --bi-hemi
  python3 orchestrator.py --debug-self "ImportError" --debug-file omega_bridge.py
  python3 orchestrator.py --export-training --task-filter task_morph_k1 --modelfile
  python3 orchestrator.py --token-endpoint gap_analyzer.py
"""


def main():
    parser = argparse.ArgumentParser(
        description="Linguistic Hierarchy CLI Orchestrator - Unified Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_build_extended_help()
    )

    parser.add_argument("text", nargs="*", help="Text to process through linguistic hierarchy")
    parser.add_argument("--test", action="store_true", help="Run internal test suite")
    parser.add_argument("--details", action="store_true", help="Show full hierarchical breakdown")
    parser.add_argument("--pinpoint", action="store_true", help="Output unmapped semantic links for debugging")
    parser.add_argument("--scripts", action="store_true", help="List all available scripts with descriptions and classifications")

    # Weight Tuning & Morph Chat Integration
    parser.add_argument("--tune-weights", action="store_true",
                       help="Enter interactive weight tuning mode with real-time suggestion updates")
    parser.add_argument("--morph-chat", action="store_true",
                       help="Morph chat mode about current system state with session context")
    parser.add_argument("--session", metavar="SESSION_ID",
                       help="Specific Os_Toolkit session to load (for --tune-weights or --morph-chat)")
    # Phase I: Training data export
    parser.add_argument("--export-training", action="store_true",
                       help="Export JSONL training dataset from enriched_changes + task_contexts")
    parser.add_argument("--task-filter", metavar="TASK_ID", default=None,
                       help="Filter training export to a specific task_id (use with --export-training)")
    parser.add_argument("--all-records", action="store_true",
                       help="Include all record types in export (hotspots etc.)")
    parser.add_argument("--modelfile", action="store_true",
                       help="Also write Ollama Modelfile for Morph-001 (use with --export-training)")
    parser.add_argument("--tokenize", metavar="FILE",
                       help="Show token estimate for a file's blueprint")
    # Phase N: Bi-hemispheral UI
    parser.add_argument("--bi-hemi", action="store_true",
                       help="Bi-hemispheral chat: LEFT=Omega grounded context, RIGHT=Alpha GGUF response, Accept/Reject recording")
    parser.add_argument("--gguf-path", metavar="PATH", default=None,
                       help="Path to GGUF file for --bi-hemi Alpha inference")
    # Phase J: Omega Morph Line
    parser.add_argument("--debug-self", metavar="ERROR_TEXT",
                       help="Run self-debug: pinpoint error → Morph_regex → fix plan")
    parser.add_argument("--debug-file", metavar="FILE_HINT", default=None,
                       help="File context for --debug-self query")
    parser.add_argument("--spawn-variant", action="store_true",
                       help="After --debug-self, spawn frozen control packet variant")
    parser.add_argument("--token-endpoint", metavar="FILE",
                       help="Generate + print control packet for file's grounded state")
    parser.add_argument("--base-model", metavar="MODEL_OR_PATH", default=None,
                       help="Base model for Modelfile (path to GGUF or Ollama tag, "
                            "use with --export-training --modelfile)")

    args = parser.parse_args()

    # Handle --tokenize
    if args.tokenize:
        try:
            _trainer_root_t = Path(__file__).parents[4]
            from activity_integration_bridge import MorphTeachingBridge as _MTB_tok
            _bridge_tok = _MTB_tok(_trainer_root_t)
            _bp = _bridge_tok.get_file_blueprint(args.tokenize)
            _text = json.dumps(_bp, indent=2, default=str)
            _tok_est = int(len(_text.split()) * 1.33)
            print(f"[TOKENIZE] {args.tokenize}")
            print(f"  Blueprint tokens (est): {_tok_est:,}")
            print(f"  LOC                   : {_bp.get('loc', '?')}")
            print(f"  Functions             : {len(_bp.get('functions', []))}")
            print(f"  Classes               : {len(_bp.get('classes', []))}")
            print(f"  Imports               : {len(_bp.get('imports', []))}")
        except Exception as _e:
            print(f"[tokenize] Error: {_e}")
        return

    # Phase J: Handle --debug-self
    if args.debug_self:
        try:
            _trainer_root_j = Path(__file__).parents[4]
            _omega_dir = Path(__file__).parent / "activities" / "tools" / "scripts"
            if str(_omega_dir) not in sys.path:
                sys.path.insert(0, str(_omega_dir))
            from omega_bridge import OmegaBridge as _OB
            _bridge_j = _OB(_trainer_root_j)
            _result_j = _bridge_j.run_debug_query(args.debug_self, args.debug_file or None)
            print(f"\n[DEBUG SELF]")
            print(f"  Control Signal : {_result_j['control_signal']}")
            print(f"  Pattern Matched: {_result_j['pattern_matched']}")
            print(f"  Gap Severity   : {_result_j['gap_severity']}")
            print(f"  Response       : {_result_j['response']}")
            print(f"  Fix Suggestion : {_result_j['fix_suggestion']}")
            if args.spawn_variant:
                _vpath_j = _bridge_j.spawn_grounded_variant(args.debug_file or '')
                print(f"  Variant saved  : {_vpath_j}")
        except Exception as _e_j:
            print(f"[debug-self] Error: {_e_j}")
            import traceback
            traceback.print_exc()
        return

    # Phase J: Handle --token-endpoint
    if args.token_endpoint:
        try:
            _trainer_root_te = Path(__file__).parents[4]
            _omega_dir_te = Path(__file__).parent / "activities" / "tools" / "scripts"
            if str(_omega_dir_te) not in sys.path:
                sys.path.insert(0, str(_omega_dir_te))
            from omega_bridge import OmegaBridge as _OB_te
            _bridge_te = _OB_te(_trainer_root_te)
            _packet_te = _bridge_te.get_token_endpoint(args.token_endpoint)
            print(json.dumps(_packet_te, indent=2))
        except Exception as _e_te:
            print(f"[token-endpoint] Error: {_e_te}")
            import traceback
            traceback.print_exc()
        return

    # Handle --export-training
    if args.export_training:
        try:
            _trainer_root_e = Path(__file__).parents[4]
            from activity_integration_bridge import MorphDatasetExporter as _MDE
            _exporter = _MDE(_trainer_root_e)
            _out, _count, _tokens = _exporter.export(
                task_id=args.task_filter or None,
                include_all=args.all_records,
            )
            print(f"\n[EXPORT] Dataset written : {_out}")
            print(f"[EXPORT] Records         : {_count}")
            print(f"[EXPORT] Tokens (est)    : {_tokens:,}")
            if args.modelfile:
                _mf = _exporter.write_modelfile(base_model=args.base_model or None)
                print(f"[EXPORT] Modelfile       : {_mf}")
        except Exception as _e:
            print(f"[export-training] Error: {_e}")
            import traceback
            traceback.print_exc()
        return

    # Handle --tune-weights mode (interactive weight tuning)
    if args.tune_weights:
        if not HAS_WEIGHT_TUNER:
            print("[ERROR] Weight Tuner module not available. Cannot enter tuning mode.")
            print("  Check that babel_data/inventory/core/weight_tuner.py exists.")
            return
        run_weight_tuning_mode(session_id=args.session)
        return

    # Handle --morph-chat mode (Morph state chat with session context)
    if args.morph_chat:
        if not HAS_WEIGHT_TUNER:
            print("[ERROR] Weight Tuner module not available. Cannot enter Morph chat mode.")
            print("  Check that babel_data/inventory/core/weight_tuner.py exists.")
            return
        run_morph_chat_mode(session_id=args.session)
        return

    # Handle --bi-hemi mode (K3 Bi-hemispheral Omega/Alpha chat)
    if args.bi_hemi:
        _run_bi_hemi_chat(gguf_path=getattr(args, 'gguf_path', None))
        return

    # Handle --scripts request (unified guidance system)
    if args.scripts:
        try:
            from script_discovery_handler import get_unified_help
            print(get_unified_help(verbose=False))
        except ImportError:
            # Graceful fallback if discovery handler not available
            print("=" * 70)
            print("AVAILABLE SCRIPTS - Basic Listing")
            print("=" * 70)
            print()
            print("[Core Systems]")
            print("  orchestrator.py      - Main text processing orchestrator")
            print("  gap_analyzer.py      - Analyze understanding gaps in text")
            print("  audit.py             - Audit regex patterns and coverage")
            print()
            print("[Integration]")
            print("  activity_integration_bridge.py - Activity suggestions & tool classification")
            print()
            print("[Workflow]")
            print("  workflow_manager.py  - Execute workflows with agents")
            print()
            print("For detailed help on any script:")
            print("  python3 <script_name>.py -h")
            print("=" * 70)
        return

    orchestrator = MetacognitiveOrchestrator()

    if args.test:
        run_tests(orchestrator)
        return

    input_text = " ".join(args.text) if args.text else None

    if not input_text:
        parser.print_help()
        print()
        print("Tip: Use --scripts to see all available tools")
        return

    result = orchestrator.process_interaction(input_text)
    
    if args.pinpoint:
        print("\n[DIAGNOSTIC: SEMANTIC LINK PROFILER]")
        words = input_text.split()
        recognized = set()
        # Extract from 5W1H
        for val in result.get("metacognitive_state", {}).get("resolved_text", "").split():
            recognized.add(val.lower().strip("?!.,"))
        
        unmapped = [w for w in words if w.lower().strip("?!.,") not in recognized and len(w) > 2]
        print(f"Unmapped Tokens: {unmapped}")
        print(f"Boredom Delta: {result['metacognitive_state']['boredom_score']}")
        print(f"Volition Intensity: {result['metacognitive_state']['volition_score']}")
        print("-" * 30 + "\n")

    # Thought Block
    if result.get("thoughts"):
        print("\n" + "=" * 20 + " THOUGHT PROCESS " + "=" * 20)
        for thought in result["thoughts"]:
            print(f"  * {thought}")
        print("=" * 57 + "\n")

    print("-" * 50)
    print(f"RES_TOKENS: {result['tokens']}")
    print(f"RESPONSE:   {result['response']}")
    print(f"METASTATE:  {json.dumps(result['metacognitive_state'], indent=2)}")
    print("-" * 50)

def run_tests(orchestrator):
    test_cases = [
        "Hello there!",
        "What is the CPU temperature?",
        "Why is the system efficiency dropping in the primary kernel layer?",
        "How can I help you with the project?"
    ]
    print("RUNNING LINGUISTIC INFERENCE TESTS...\n")
    for case in test_cases:
        print(f"TESTING: {case}")
        res = orchestrator.process_interaction(case)
        print(f"TOKENS: {res['tokens']}")
        print(f"INTENT: {res['metacognitive_state']['priority_weight']:.2f} Priority")
        print("-" * 30)

if __name__ == "__main__":
    main()
