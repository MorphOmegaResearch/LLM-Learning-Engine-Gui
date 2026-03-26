#!/usr/bin/env python3
"""
Activity Integration Bridge
============================
Bridges epistemic feedback loop, tool onboarding, workflow management, and user interaction
via zenity prompts. Implements grounded activity suggestion based on metastate and gap analysis.

Architecture:
    Input Text → Gap Analysis → Metastate Weights
        ↓
    Activity Suggestion (based on priority% × understanding%)
        ↓
    [IF user_confirmation_needed] → Zenity Question Queue
        ↓
    Tool Capability Matching (from onboarded tools)
        ↓
    Workflow Execution + Journal Logging
        ↓
    Metastate Update → Next iteration

Integration Points:
    - orchestrator.py: EpistemicFeedbackLoop
    - gap_analyzer.py: MetastateWeights
    - onboarder.py: ToolMetadata
    - workflow_manager.py: WorkflowManager + zenity
    - Journal system: Event logging with #[MARK:{}] refs
"""

import os
import sys
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import datetime

# Graceful import handling
try:
    # Add parent directory to path (regex_project/)
    # scripts/ -> tools/ -> activities/ -> regex_project/
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    sys.path.insert(0, str(project_root))

    from gap_analyzer import GapAnalyzer, MetastateWeights, GapAnalysis
    # EpistemicFeedbackLoop is imported lazily to avoid circular import:
    # orchestrator.py imports activity_integration_bridge at startup,
    # so importing orchestrator here would create a circular dependency.
    # EpistemicFeedbackLoop is only used in ActivitySuggestionBridge._feedback_loop()
    # which can import it on-demand.
    EpistemicFeedbackLoop = None  # will be imported lazily when needed
    HAS_ORCHESTRATOR = True
except ImportError as e:
    HAS_ORCHESTRATOR = False

    # Define stub classes for graceful degradation
    MetastateWeights = type('MetastateWeights', (), {})
    GapAnalysis = type('GapAnalysis', (), {})

try:
    from onboarder import ToolMetadata, ToolCategory
    HAS_ONBOARDER = True
except ImportError:
    print("Warning: Could not import onboarder components")
    HAS_ONBOARDER = False

try:
    from workflow_manager import WorkflowManager, WorkflowType
    HAS_WORKFLOW_MANAGER = True
except ImportError:
    print("Warning: Could not import workflow_manager components")
    HAS_WORKFLOW_MANAGER = False


# =============================================================================
# 5W1H Tool Classifier
# =============================================================================

class FiveWOneHClassifier:
    """
    Classifies tools using 5W1H framework based on baseline schema.
    Integrated with morphological gap handling.
    """

    def __init__(self, config_dir: Path = None):
        """
        Initialize classifier with baseline schemas.
        Gracefully handles missing config files.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent

        self.config_dir = config_dir
        self.baseline = self._load_json('baseline_5w1h_classification.json')
        self.patterns = self._load_json('regex_pattern_library.json')
        self.gap_instructions = self._load_json('morphological_gap_instructions.json')

        # Check if essential data loaded
        self.has_baseline = bool(self.baseline.get('dimensions'))
        if not self.has_baseline:
            print(f"Warning: No baseline schema loaded from {config_dir}")
            print("  Classification will return minimal results")

    def _load_json(self, filename: str) -> Dict:
        """Load JSON configuration file"""
        filepath = self.config_dir / filename
        if filepath.exists():
            with open(filepath, 'r') as f:
                return json.load(f)
        return {}

    def classify(self, tool_name: str, file_content: str = "", tool_metadata: Any = None) -> Dict[str, Any]:
        """
        Classify a tool using 5W1H dimensions.

        Args:
            tool_name: Name of the tool (filename)
            file_content: Source code content for context inference
            tool_metadata: Optional ToolMetadata object for enhanced classification

        Returns:
            Dictionary with 5W1H classification and confidence score.
            Returns minimal classification if baseline data missing.
        """
        # Graceful fallback: if no baseline, return minimal classification
        if not self.has_baseline:
            return {
                'what': 'unknown',
                'where': 'unknown',
                'when': 'unknown',
                'why': 'unknown',
                'which': 'unknown',
                'how': 'unknown',
                'confidence': 0.0,
                'tokens': [],
                'context_hints': {},
                '_fallback': 'no_baseline_data'
            }

        # Step 1: Lexical analysis
        tokens = self._tokenize(tool_name)

        # Step 2: Context inference from file content
        context = self._infer_context(file_content, tool_metadata)

        # Step 3: Pattern matching for each dimension
        classification = {}
        for dimension in ['what', 'where', 'when', 'why', 'which', 'how']:
            classification[dimension] = self._classify_dimension(
                dimension, tokens, context
            )

        # Step 4: Gap handling
        classification = self._handle_gaps(classification, tokens, context)

        # Step 5: Confidence scoring
        classification['confidence'] = self._calculate_confidence(classification)
        classification['tokens'] = tokens
        classification['context_hints'] = context

        return classification

    def _tokenize(self, tool_name: str) -> List[str]:
        """Tokenize tool name into base words"""
        # Remove file extension
        name = Path(tool_name).stem

        # Split on common separators
        tokens = re.split(r'[_\-\.]', name)

        # Handle camelCase by inserting separators
        expanded = []
        for token in tokens:
            # Split camelCase: "PathFixer" -> ["Path", "Fixer"]
            split_camel = re.sub('([a-z])([A-Z])', r'\1 \2', token).split()
            expanded.extend(split_camel)

        # Normalize to lowercase and remove common suffixes
        normalized = []
        for token in expanded:
            token_lower = token.lower()
            # Strip common suffixes: -er, -or, -ar, -ing, -ed
            for suffix in ['er', 'or', 'ar', 'ing', 'ed']:
                if token_lower.endswith(suffix) and len(token_lower) > len(suffix) + 2:
                    token_lower = token_lower[:-len(suffix)]
                    break
            normalized.append(token_lower)

        return normalized

    def _infer_context(self, file_content: str, tool_metadata: Any) -> Dict[str, Any]:
        """Infer context from file content and metadata"""
        context = {
            'has_argparse': False,
            'has_tkinter': False,
            'has_os_path': False,
            'has_datetime': False,
            'has_json_xml': False,
            'has_regex': False,
            'imports': [],
            'description': ''
        }

        if not file_content:
            return context

        # Check imports
        if 'import argparse' in file_content or 'from argparse' in file_content:
            context['has_argparse'] = True
        if 'import tkinter' in file_content or 'from tkinter' in file_content:
            context['has_tkinter'] = True
        if 'import os' in file_content or 'from os' in file_content or 'from pathlib' in file_content:
            context['has_os_path'] = True
        if 'import datetime' in file_content or 'from datetime' in file_content:
            context['has_datetime'] = True
        if 'import json' in file_content or 'import xml' in file_content:
            context['has_json_xml'] = True
        if 'import re' in file_content or 'from re' in file_content:
            context['has_regex'] = True

        # Extract docstring
        docstring_match = re.search(r'"""(.+?)"""', file_content, re.DOTALL)
        if docstring_match:
            context['description'] = docstring_match.group(1).strip()

        # Use tool_metadata if available
        if tool_metadata and hasattr(tool_metadata, 'description'):
            context['description'] = tool_metadata.description

        return context

    def _classify_dimension(self, dimension: str, tokens: List[str], context: Dict) -> str:
        """Classify a single 5W1H dimension"""
        if dimension not in self.baseline.get('dimensions', {}):
            return "unknown"

        dim_config = self.baseline['dimensions'][dimension]

        # Try regex pattern matching
        for pattern in dim_config.get('regex_patterns', []):
            for token in tokens:
                if re.search(pattern, token, re.IGNORECASE):
                    # Match found - return description based on pattern
                    return self._get_description_from_pattern(pattern, dimension, token)

        # Try lexical markers
        for marker in dim_config.get('lexical_markers', []):
            if marker in context.get('description', '').lower():
                return f"involves {marker}"

        # Fallback to context-based inference
        return self._infer_from_context(dimension, context, tokens)

    def _get_description_from_pattern(self, pattern: str, dimension: str, token: str) -> str:
        """Generate human-readable description from pattern match"""
        # Use tool type mappings if available
        for tool_type, mappings in self.baseline.get('tool_type_mappings', {}).items():
            if tool_type in token:
                return mappings.get(dimension, f"{token} (type: {tool_type})")

        # Generic description based on dimension
        if dimension == 'what':
            return f"{token}s data or files"
        elif dimension == 'where':
            return f"in {token} environment"
        elif dimension == 'when':
            return f"during {token} phase"
        elif dimension == 'why':
            return f"to {token}"
        elif dimension == 'which':
            return f"{token} artifacts"
        elif dimension == 'how':
            return f"using {token}"

        return token

    def _infer_from_context(self, dimension: str, context: Dict, tokens: List[str]) -> str:
        """Infer dimension value from context heuristics"""
        # Apply heuristics from morphological gap instructions
        heuristics = self.gap_instructions.get('instructions', {}).get('step_2_context_inference', {}).get('heuristics', {})

        if dimension == 'what' and context.get('has_argparse'):
            return "CLI tool/utility"
        elif dimension == 'where' and context.get('has_os_path'):
            return "filesystem/directory operations"
        elif dimension == 'when' and context.get('has_datetime'):
            return "time-aware/scheduled operations"
        elif dimension == 'which' and context.get('has_json_xml'):
            return "structured data (JSON/XML)"
        elif dimension == 'how' and context.get('has_regex'):
            return "pattern matching/regex"

        # Default based on tokens
        if tokens:
            return f"related to {' '.join(tokens)}"

        return "not determined"

    def _handle_gaps(self, classification: Dict, tokens: List[str], context: Dict) -> Dict:
        """Handle morphological gaps in classification"""
        gap_types = self.baseline.get('morphological_gaps', {}).get('detection_patterns', [])

        for gap_spec in gap_types:
            gap_type = gap_spec.get('gap_type')
            pattern = gap_spec.get('pattern')

            # Check if any token matches gap pattern
            for token in tokens:
                if re.search(pattern, token):
                    # Apply suggestion
                    suggestion = gap_spec.get('suggestion', '')
                    # Could enhance classification based on gap handling
                    classification['_gaps_detected'] = classification.get('_gaps_detected', [])
                    classification['_gaps_detected'].append({
                        'type': gap_type,
                        'token': token,
                        'suggestion': suggestion
                    })

        return classification

    def _calculate_confidence(self, classification: Dict) -> float:
        """Calculate overall confidence score for classification"""
        determined_count = sum(
            1 for dim in ['what', 'where', 'when', 'why', 'which', 'how']
            if classification.get(dim) != "not determined" and classification.get(dim) != "unknown"
        )

        base_confidence = determined_count / 6.0

        # Boost if no gaps detected
        if '_gaps_detected' not in classification or len(classification['_gaps_detected']) == 0:
            base_confidence = min(1.0, base_confidence + 0.1)

        return round(base_confidence, 2)


# =============================================================================
# Capability Registry
# =============================================================================

@dataclass
class OnboardedCapability:
    """Represents a tool capability that has been onboarded by the user"""
    tool_id: str
    tool_name: str
    classification: Dict[str, Any]
    relevance_weight: float = 0.5  # Initial weight
    usage_count: int = 0
    last_used: Optional[str] = None
    confirmed_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    journal_marks: List[str] = field(default_factory=list)  # #[MARK:{}] references


class CapabilityRegistry:
    """
    Manages onboarded tool capabilities with weighted relevance.
    Integrates with journal system for #[MARK:{}] references.
    """

    def __init__(self, registry_file: Path):
        self.registry_file = registry_file
        self.capabilities: Dict[str, OnboardedCapability] = {}
        self._load_registry()

    def _load_registry(self):
        """Load capabilities from JSON file"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r') as f:
                data = json.load(f)
                for tool_id, cap_data in data.items():
                    self.capabilities[tool_id] = OnboardedCapability(**cap_data)

    def _save_registry(self):
        """
        Save capabilities to JSON file.
        Gracefully handles write errors.
        """
        try:
            data = {
                tool_id: asdict(cap)
                for tool_id, cap in self.capabilities.items()
            }
            # Ensure parent directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save capability registry: {e}")
            print(f"  Registry file: {self.registry_file}")
            # Continue without saving

    def onboard_capability(self, tool_id: str, tool_name: str, classification: Dict) -> OnboardedCapability:
        """Onboard a new capability after user confirmation"""
        capability = OnboardedCapability(
            tool_id=tool_id,
            tool_name=tool_name,
            classification=classification,
            relevance_weight=0.5
        )
        self.capabilities[tool_id] = capability
        self._save_registry()
        return capability

    def update_relevance(self, tool_id: str, weight_delta: float):
        """Update relevance weight based on usage or context"""
        if tool_id in self.capabilities:
            cap = self.capabilities[tool_id]
            cap.relevance_weight = max(0.0, min(1.0, cap.relevance_weight + weight_delta))
            cap.usage_count += 1
            cap.last_used = datetime.datetime.now().isoformat()
            self._save_registry()

    def add_journal_mark(self, tool_id: str, mark: str):
        """Add journal #[MARK:{}] reference to capability"""
        if tool_id in self.capabilities:
            self.capabilities[tool_id].journal_marks.append(mark)
            self._save_registry()

    def get_relevant_capabilities(self, context: str, top_n: int = 5) -> List[OnboardedCapability]:
        """
        Get most relevant capabilities for given context.
        Ranks by relevance_weight and classification match.
        """
        scored_caps = []

        for cap in self.capabilities.values():
            # Calculate relevance score
            score = cap.relevance_weight

            # Boost if classification matches context keywords
            for dim_value in cap.classification.values():
                if isinstance(dim_value, str) and dim_value.lower() in context.lower():
                    score += 0.2

            scored_caps.append((score, cap))

        # Sort by score descending
        scored_caps.sort(key=lambda x: x[0], reverse=True)

        return [cap for score, cap in scored_caps[:top_n]]


# =============================================================================
# Zenity Question Queue
# =============================================================================

class ZenityQuestionQueue:
    """
    Manages queue of questions to ask user via zenity.
    Questions are triggered by gaps, thoughts, and metastate analysis.
    """

    def __init__(self):
        self.queue: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []

    def enqueue_gap_question(self, gap_analysis: 'GapAnalysis', metastate: 'MetastateWeights'):
        """Create question from gap analysis"""
        if not gap_analysis.unrecognized_tokens:
            return

        # Create question about unrecognized tokens
        question = {
            'type': 'gap_clarification',
            'title': f'Gap Detected (severity: {metastate.gap_severity})',
            'text': f'I encountered {len(gap_analysis.unrecognized_tokens)} unrecognized term(s):\n\n' +
                    '\n'.join(f'- {token}' for token in gap_analysis.unrecognized_tokens[:5]) +
                    f'\n\nShould I attempt to learn about these terms?',
            'options': ['Yes, learn about them', 'No, skip for now', 'Add to knowledge base manually'],
            'context': {
                'tokens': gap_analysis.unrecognized_tokens,
                'confidence': gap_analysis.confidence_score,
                'severity': metastate.gap_severity
            }
        }
        self.queue.append(question)

    def enqueue_thought_question(self, thought: str, priority: float = 0.5):
        """Create question from system thought"""
        question = {
            'type': 'thought_inquiry',
            'title': f'System Reflection (priority: {priority:.2f})',
            'text': f'Internal thought:\n\n"{thought}"\n\nWould you like to explore this further?',
            'options': ['Yes, tell me more', 'No, continue'],
            'context': {
                'thought': thought,
                'priority': priority
            }
        }
        self.queue.append(question)

    def enqueue_capability_confirmation(self, tool_name: str, classification: Dict):
        """Confirm onboarding of a capability"""
        confidence = classification.get('confidence', 0.0)

        desc_lines = [f"Tool: {tool_name}", f"Confidence: {confidence:.0%}", ""]
        for dim in ['what', 'where', 'when', 'why', 'which', 'how']:
            if dim in classification:
                desc_lines.append(f"{dim.upper()}: {classification[dim]}")

        question = {
            'type': 'capability_onboarding',
            'title': 'Onboard Tool Capability?',
            'text': '\n'.join(desc_lines) + '\n\nWould you like to onboard this capability?',
            'options': ['Yes, onboard it', 'No, skip', 'Show more details'],
            'context': {
                'tool_name': tool_name,
                'classification': classification
            }
        }
        self.queue.append(question)

    def process_queue(self, max_questions: int = 3) -> List[Dict[str, Any]]:
        """
        Process queued questions using zenity.
        Returns list of responses.
        """
        if not self._has_zenity():
            print("Zenity not available - skipping questions")
            return []

        processed = []
        for question in self.queue[:max_questions]:
            response = self._show_zenity_question(question)
            if response:
                processed.append({
                    'question': question,
                    'response': response,
                    'timestamp': datetime.datetime.now().isoformat()
                })

        # Remove processed questions
        self.queue = self.queue[max_questions:]
        self.responses.extend(processed)

        return processed

    def _has_zenity(self) -> bool:
        """Check if zenity is available"""
        try:
            subprocess.run(['which', 'zenity'], capture_output=True, check=True)
            return True
        except:
            return False

    def _show_zenity_question(self, question: Dict) -> Optional[str]:
        """Show zenity question dialog and return response"""
        try:
            if question.get('options'):
                # List selection
                cmd = ['zenity', '--list', '--title', question['title'],
                       '--text', question['text'], '--column', 'Options']
                cmd.extend(question['options'])

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    return result.stdout.strip()
            else:
                # Yes/No question
                result = subprocess.run([
                    'zenity', '--question',
                    '--title', question['title'],
                    '--text', question['text']
                ], timeout=60)
                return 'yes' if result.returncode == 0 else 'no'
        except Exception as e:
            print(f"Zenity error: {e}")
            return None


# =============================================================================
# Activity Suggestion Bridge
# =============================================================================

class ActivitySuggestionBridge:
    """
    Bridges epistemic metastate with activity suggestions.
    Integrates with workflow manager and capability registry.
    """

    def __init__(self, capability_registry: CapabilityRegistry,
                 workflow_manager=None, question_queue: ZenityQuestionQueue = None):
        self.capabilities = capability_registry
        self.workflow_manager = workflow_manager
        self.question_queue = question_queue or ZenityQuestionQueue()

    def suggest_activity(self, metastate: 'MetastateWeights',
                        gap_analysis: 'GapAnalysis',
                        context: str = "") -> Optional[Dict]:
        """
        Suggest activity based on metastate and gap analysis.

        Returns activity suggestion with grounded context.
        Gracefully handles case when no capabilities are available.
        """
        # Determine activity type based on gap severity and priority
        if metastate.gap_severity in ['critical', 'high']:
            activity_type = 'learning'
            reason = f"Critical knowledge gap detected (understanding: {metastate.understanding_pct:.0%})"
        elif metastate.priority_pct > 0.7:
            activity_type = 'investigation'
            reason = f"High priority areas need attention (priority: {metastate.priority_pct:.0%})"
        elif metastate.understanding_pct > 0.8:
            activity_type = 'application'
            reason = f"Good understanding - time to apply knowledge"
        else:
            activity_type = 'consolidation'
            reason = f"Moderate understanding - consolidate learning"

        # Get relevant capabilities
        relevant_caps = self.capabilities.get_relevant_capabilities(context, top_n=3)

        # Build suggestion
        suggestion = {
            'activity_type': activity_type,
            'reason': reason,
            'metastate': {
                'understanding': metastate.understanding_pct,
                'priority': metastate.priority_pct,
                'gap_severity': metastate.gap_severity
            },
            'relevant_capabilities': [
                {
                    'tool': cap.tool_name,
                    'relevance': cap.relevance_weight,
                    'what': cap.classification.get('what', 'unknown')
                }
                for cap in relevant_caps
            ],
            'suggested_action': metastate.recommended_action,
            'unrecognized_terms': gap_analysis.unrecognized_tokens[:5]
        }

        return suggestion

    def suggest_from_grounded(self, grounded_context: dict) -> dict:
        """
        Generate an activity suggestion from Os_Toolkit grounded context
        (enriched_changes, probe failures, provisions) rather than the
        linguistic MetastateWeights pipeline.
        """
        gap_severity   = grounded_context.get('gap_severity', 'low')
        priority_pct   = grounded_context.get('priority_pct', 0.0)
        probe_failures = grounded_context.get('probe_failures', [])
        high_risk      = grounded_context.get('high_risk_files', [])

        if gap_severity == 'critical' or len(probe_failures) > 5:
            activity_type = 'investigation'
            reason = (f"{len(probe_failures)} probe failures detected "
                      f"— investigate broken files first")
        elif gap_severity == 'high' or priority_pct > 0.5:
            activity_type = 'application'
            reason = (f"{len(high_risk)} HIGH/CRITICAL risk changes "
                      f"need review and testing")
        elif priority_pct > 0.3:
            activity_type = 'consolidation'
            reason = "Moderate change activity — consolidate and document recent work"
        else:
            activity_type = 'learning'
            reason = "Low activity — good time to explore bundled provisions or plan next steps"

        ctx_str = " ".join(high_risk[:5])
        relevant_caps = self.capabilities.get_relevant_capabilities(ctx_str, top_n=3)

        return {
            'activity_type': activity_type,
            'reason': reason,
            'grounded_evidence': {
                'probe_failures': len(probe_failures),
                'high_risk_files': high_risk[:5],
                'gap_severity': gap_severity,
                'priority_pct': round(priority_pct, 2),
            },
            'relevant_capabilities': [
                {'tool': c.tool_name, 'relevance': c.relevance_weight}
                for c in relevant_caps
            ],
        }

    def execute_suggested_activity(self, suggestion: Dict, auto_confirm: bool = False) -> bool:
        """
        Execute suggested activity, optionally prompting user via zenity.
        """
        if not auto_confirm and self.question_queue:
            # Ask user confirmation
            question = {
                'type': 'activity_suggestion',
                'title': f'Activity Suggestion: {suggestion["activity_type"]}',
                'text': f'{suggestion["reason"]}\n\n' +
                        f'Suggested action: {suggestion["suggested_action"]}\n\n' +
                        'Proceed with this activity?',
                'options': ['Yes, proceed', 'No, skip', 'Show details']
            }
            self.question_queue.queue.append(question)
            responses = self.question_queue.process_queue(max_questions=1)

            if not responses or 'Yes' not in responses[0].get('response', ''):
                return False

        # Execute activity
        print(f"\nExecuting activity: {suggestion['activity_type']}")
        print(f"Reason: {suggestion['reason']}")
        print(f"Action: {suggestion['suggested_action']}")

        if suggestion['relevant_capabilities']:
            print("\nRelevant capabilities:")
            for cap in suggestion['relevant_capabilities']:
                print(f"  - {cap['tool']} (relevance: {cap['relevance']:.0%})")

        # TODO: Integrate with workflow_manager if available
        if self.workflow_manager and HAS_WORKFLOW_MANAGER:
            # Execute workflow based on activity type
            pass

        return True


# =============================================================================
# MorphTeachingBridge — Python-aware knowledge layer for Morph
# =============================================================================

class MorphTeachingBridge:
    """
    Serializes Python code knowledge into structured teaching context blocks
    for Morph's chat loop.

    Uses direct AST parsing (no 800MB manifest dependency) for file/function
    blueprints, and enriched_changes from version_manifest for change context.
    """

    # Verb categories inferred from function name prefixes
    _VERB_PREFIXES = {
        'get': 'READ', 'load': 'READ', 'fetch': 'READ', 'read': 'READ', 'find': 'READ',
        'set': 'UPDATE', 'update': 'UPDATE', 'modify': 'UPDATE', 'edit': 'UPDATE',
        'save': 'CREATE', 'write': 'CREATE', 'create': 'CREATE', 'build': 'CREATE',
        'add': 'CREATE', 'insert': 'CREATE', 'append': 'CREATE',
        'delete': 'DELETE', 'remove': 'DELETE', 'clear': 'DELETE', 'reset': 'DELETE',
        'validate': 'VALIDATE', 'check': 'VALIDATE', 'verify': 'VALIDATE', 'is_': 'VALIDATE',
        'has_': 'VALIDATE',
        'convert': 'CONVERT', 'parse': 'CONVERT', 'format': 'CONVERT', 'encode': 'CONVERT',
        'calculate': 'CALCULATE', 'compute': 'CALCULATE', 'count': 'CALCULATE',
        'run': 'CONTROL', 'start': 'CONTROL', 'stop': 'CONTROL', 'handle': 'CONTROL',
        'process': 'CONTROL', 'execute': 'CONTROL', 'dispatch': 'CONTROL',
    }

    _SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB guard

    def __init__(self, babel_root: Path):
        babel_root = Path(babel_root).resolve()
        if babel_root.name == 'babel_data':
            self._apt = babel_root.parent
        else:
            self._apt = babel_root
        self._trainer_root = self._apt.parent.parent.parent  # Trainer/
        self._vm_cache = None  # cached version_manifest enriched_changes

    def _resolve_file(self, file_hint: str) -> Optional[Path]:
        """Find a file by name/partial path under Trainer/.
        Also accepts backup-key format (Data_tabs_..._file.py).
        Builds a name index on first call and caches it.
        """
        hint = file_hint.strip()
        # A2: If hint looks like a backup filename key, try to resolve via name index
        if hint.startswith('Data_') and '_' in hint:
            idx = OsToolkitGroundingBridge._build_name_index(self._trainer_root)
            resolved = OsToolkitGroundingBridge._backup_key_to_source_path(hint, idx)
            hint = resolved  # may still be the heuristic fallback
        # Direct absolute
        if Path(hint).is_file():
            return Path(hint)
        # Relative to Trainer
        candidate = self._trainer_root / hint
        if candidate.is_file():
            return candidate
        # Basename search under Trainer/Data (using name index for speed)
        idx = OsToolkitGroundingBridge._build_name_index(self._trainer_root)
        basename = Path(hint).name
        if basename in idx:
            return self._trainer_root / idx[basename]
        return None

    def _infer_verb(self, name: str) -> str:
        nl = name.lower()
        for prefix, verb in self._VERB_PREFIXES.items():
            if nl.startswith(prefix):
                return verb
        return 'CONTROL'

    def get_file_blueprint(self, file_hint: str) -> dict:
        """
        Returns a 6W1H-style blueprint for a file via direct AST parsing.
        Keys: file_path, classes, functions, imports, verb_categories,
              top_complexity, loc, errors
        """
        import ast as _ast

        result = {
            'file_path': file_hint,
            'classes': [],
            'functions': [],
            'imports': [],
            'verb_categories': {},
            'top_complexity': [],
            'loc': 0,
            'errors': [],
        }

        fp = self._resolve_file(file_hint)
        if fp is None:
            result['errors'].append(f"File not found: {file_hint}")
            return result

        result['file_path'] = str(fp)
        try:
            source = fp.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            result['errors'].append(str(e))
            return result

        result['loc'] = source.count('\n') + 1

        try:
            tree = _ast.parse(source, filename=str(fp))
        except SyntaxError as e:
            result['errors'].append(f"SyntaxError: {e}")
            return result

        classes, functions, imports = [], [], []
        verb_counts: Dict[str, int] = {}
        complexity_items = []

        for node in _ast.walk(tree):
            if isinstance(node, _ast.ClassDef):
                methods = [n.name for n in _ast.walk(node) if isinstance(n, _ast.FunctionDef)]
                classes.append({'name': node.name, 'line': node.lineno, 'methods': methods[:8]})

            elif isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                verb = self._infer_verb(node.name)
                verb_counts[verb] = verb_counts.get(verb, 0) + 1
                # Rough complexity: count If/For/While/Try nodes inside
                sub_nodes = list(_ast.walk(node))
                complexity = sum(1 for n in sub_nodes
                                 if isinstance(n, (_ast.If, _ast.For, _ast.While,
                                                   _ast.Try, _ast.ExceptHandler)))
                args = [a.arg for a in node.args.args]
                functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': args[:6],
                    'verb': verb,
                    'complexity': complexity,
                    'is_async': isinstance(node, _ast.AsyncFunctionDef),
                })
                complexity_items.append((complexity, node.name))

            elif isinstance(node, (_ast.Import, _ast.ImportFrom)):
                if isinstance(node, _ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    mod = node.module or ''
                    imports.append(mod)

        result['classes'] = classes
        result['functions'] = functions
        result['imports'] = sorted(set(imports))
        result['verb_categories'] = verb_counts
        # Top-5 most complex functions
        complexity_items.sort(reverse=True)
        result['top_complexity'] = [{'name': n, 'complexity': c}
                                     for c, n in complexity_items[:5]]
        return result

    def get_function_profile(self, function_name: str,
                              file_hint: Optional[str] = None) -> Optional[dict]:
        """
        Returns profile for a specific function. Searches file_hint if given,
        otherwise scans enriched_changes for recently modified files.
        """
        import ast as _ast

        candidates = []
        if file_hint:
            fp = self._resolve_file(file_hint)
            if fp:
                candidates.append(fp)
        else:
            # Search recently changed files from enriched_changes
            vm = self._load_version_manifest()
            for ch in list(vm.values())[:30]:
                f = ch.get('file', '')
                fp = self._resolve_file(f)
                if fp and fp.suffix == '.py':
                    candidates.append(fp)

        for fp in candidates:
            try:
                source = fp.read_text(encoding='utf-8', errors='replace')
                tree = _ast.parse(source, filename=str(fp))
            except Exception:
                continue
            for node in _ast.walk(tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                    if node.name == function_name:
                        args = [a.arg for a in node.args.args]
                        sub = list(_ast.walk(node))
                        complexity = sum(1 for n in sub
                                         if isinstance(n, (_ast.If, _ast.For, _ast.While,
                                                            _ast.Try, _ast.ExceptHandler)))
                        calls = []
                        for n in _ast.walk(node):
                            if isinstance(n, _ast.Call):
                                if isinstance(n.func, _ast.Attribute):
                                    calls.append(n.func.attr)
                                elif isinstance(n.func, _ast.Name):
                                    calls.append(n.func.id)
                        return {
                            'name': function_name,
                            'file': str(fp),
                            'line': node.lineno,
                            'args': args,
                            'verb': self._infer_verb(function_name),
                            'complexity': complexity,
                            'is_async': isinstance(node, _ast.AsyncFunctionDef),
                            'calls': list(set(calls))[:10],
                        }
        return None

    def get_change_teaching_block(self, enriched_change: dict) -> str:
        """Formats a single enriched_change into a readable teaching block."""
        fname = Path(enriched_change.get('file', '?')).name
        risk = enriched_change.get('risk_level', '?')
        probe = enriched_change.get('probe_status', '?') or '?'
        verb = enriched_change.get('verb', '?')
        methods = ', '.join(enriched_change.get('methods', [])[:5]) or '—'
        ctx_fn = enriched_change.get('context_function', '')
        ctx_cls = enriched_change.get('context_class', '')
        ctx = f"{ctx_cls}.{ctx_fn}" if ctx_cls else ctx_fn or '(global)'
        adds = enriched_change.get('additions', 0) or enriched_change.get('net_change', 0)
        dels = enriched_change.get('deletions', 0)
        imports = ', '.join(enriched_change.get('imports_added', [])[:4]) or '—'
        task_ids = ', '.join(enriched_change.get('task_ids') or []) or '—'
        eid = enriched_change.get('event_id', '?')

        lines = [
            f"  EVENT  : {eid}  ({verb})",
            f"  FILE   : {fname}  [risk:{risk} | probe:{probe}]",
            f"  CONTEXT: {ctx}",
            f"  CHANGED: {methods}",
            f"  DIFF   : +{adds} / -{dels} lines",
            f"  IMPORTS: {imports}",
            f"  TASKS  : {task_ids}",
        ]

        # Show first 2 before/after values if available
        bav = enriched_change.get('before_after_values', [])[:2]
        for item in bav:
            ln = item.get('line_number', '?')
            bv = (item.get('before_value') or '').strip()[:60]
            av = (item.get('after_value') or '').strip()[:60]
            if bv or av:
                lines.append(f"  LINE {ln:>4}: {bv!r} → {av!r}")

        probe_errs = enriched_change.get('probe_errors', [])[:2]
        for pe in probe_errs:
            lines.append(f"  PROBE ERR: {pe[:80]}")

        return '\n'.join(lines)

    def get_domain_summary(self) -> dict:
        """Returns codebase summary from enriched_changes (fast, no 800MB read)."""
        vm = self._load_version_manifest()
        total = len(vm)
        probe_fail = sum(1 for c in vm.values() if c.get('probe_status') == 'fail')
        probe_pass = sum(1 for c in vm.values() if c.get('probe_status') == 'PASS')
        high_risk = sum(1 for c in vm.values()
                        if c.get('risk_level', '') in ('HIGH', 'CRITICAL'))
        unique_files = len({c.get('file', '') for c in vm.values()})
        all_verbs = [c.get('verb', '') for c in vm.values() if c.get('verb')]
        verb_counts: Dict[str, int] = {}
        for v in all_verbs:
            verb_counts[v] = verb_counts.get(v, 0) + 1

        return {
            'total_changes': total,
            'unique_files': unique_files,
            'probe_pass': probe_pass,
            'probe_fail': probe_fail,
            'high_risk': high_risk,
            'verb_distribution': verb_counts,
        }

    def _load_version_manifest(self) -> dict:
        """Load enriched_changes from version_manifest.json (cached)."""
        if self._vm_cache is not None:
            return self._vm_cache
        vm_path = self._trainer_root / 'Data' / 'backup' / 'version_manifest.json'
        if not vm_path.exists():
            return {}
        try:
            if vm_path.stat().st_size > self._SIZE_LIMIT:
                return {}
            import json as _json
            data = _json.loads(vm_path.read_text(encoding='utf-8'))
            self._vm_cache = data.get('enriched_changes', {})
        except Exception:
            self._vm_cache = {}
        return self._vm_cache


# =============================================================================
# MorphToolkit — Programmatic coding assistant tools for Morph
# =============================================================================

class MorphToolkit:
    """
    Programmatic toolkit for Morph's coding assistant commands.
    All methods are try/except guarded — Morph never crashes from tool failure.
    Write operations (undo) require explicit confirmation.
    """

    def __init__(self, babel_root: Path):
        babel_root = Path(babel_root).resolve()
        if babel_root.name == 'babel_data':
            self._apt = babel_root.parent
        else:
            self._apt = babel_root
        self._trainer_root = self._apt.parent.parent.parent
        self._teaching = MorphTeachingBridge(babel_root)
        self._grounder = OsToolkitGroundingBridge(babel_root)
        self._grounded_cache: Optional[dict] = None

    def _get_grounded(self) -> dict:
        if self._grounded_cache is None:
            self._grounded_cache = self._grounder.load()
        return self._grounded_cache

    def trace(self, query: str) -> dict:
        """
        Trace an event_id or file → returns matching enriched_change dicts.
        query: '#[Event:0030]' or 'Os_Toolkit.py' or partial file path
        """
        grounded = self._get_grounded()
        changes = grounded.get('recent_changes', [])
        query_lower = query.lower().strip('#').strip()

        results = []
        for ch in changes:
            eid = ch.get('event_id', '')
            fpath = ch.get('file', '')
            fname = Path(fpath).name.lower()
            if (query_lower in eid.lower() or
                    query_lower in fpath.lower() or
                    query_lower in fname):
                results.append(ch)
        return {'query': query, 'matches': results, 'total': len(results)}

    def diagnose(self, event_id: str) -> dict:
        """
        Diagnose probe/test failures for an event_id.
        Returns structured diagnosis with error type + suggested fix path.
        """
        grounded = self._get_grounded()
        changes = grounded.get('recent_changes', [])
        target = None
        for ch in changes:
            if event_id.lower() in ch.get('event_id', '').lower():
                target = ch
                break

        if target is None:
            return {'event_id': event_id, 'error': 'Event not found in recent changes'}

        probe_errs = target.get('probe_errors', []) or []
        test_errs = target.get('test_errors', []) or []
        all_errs = probe_errs + test_errs

        # Classify error types
        diagnosis = []
        for err in all_errs[:5]:
            err_lower = err.lower()
            if 'importerror' in err_lower or 'modulenotfound' in err_lower:
                diagnosis.append({
                    'type': 'ImportError',
                    'message': err[:120],
                    'suggestion': 'Check imports_added field; run: pip install <missing_module>',
                })
            elif 'attributeerror' in err_lower:
                diagnosis.append({
                    'type': 'AttributeError',
                    'message': err[:120],
                    'suggestion': 'Check class/method names in context_class/context_function',
                })
            elif 'syntaxerror' in err_lower or 'indentation' in err_lower:
                diagnosis.append({
                    'type': 'SyntaxError',
                    'message': err[:120],
                    'suggestion': 'Check before_after_values for indentation changes',
                })
            else:
                diagnosis.append({
                    'type': 'RuntimeError',
                    'message': err[:120],
                    'suggestion': f"Inspect {Path(target.get('file','')).name} at context: {target.get('context_function','')}",
                })

        return {
            'event_id': target.get('event_id'),
            'file': target.get('file'),
            'risk_level': target.get('risk_level'),
            'probe_status': target.get('probe_status'),
            'diagnosis': diagnosis,
            'resolution': target.get('blame_event'),  # If this was fixed by another event
            'methods_changed': target.get('methods', []),
        }

    def undo_preview(self, event_id: str) -> dict:
        """
        Show before/after content for an event WITHOUT writing anything.
        Reads from version_manifest change_states.
        """
        vm_path = self._trainer_root / 'Data' / 'backup' / 'version_manifest.json'
        if not vm_path.exists():
            return {'error': 'version_manifest.json not found'}
        try:
            import json as _json
            manifest = _json.loads(vm_path.read_text(encoding='utf-8'))
        except Exception as e:
            return {'error': f'Failed to read manifest: {e}'}

        change_states = manifest.get('change_states', {})
        state = change_states.get(event_id)
        if not state:
            return {'error': f'No change_state for event: {event_id}'}

        # Try sidecar files first
        before_content = state.get('before_content', '')
        after_content = state.get('after_content', '')
        before_path = state.get('before_path', '')
        after_path = state.get('after_path', '')

        if before_path and Path(before_path).exists():
            try:
                before_content = Path(before_path).read_text(encoding='utf-8')[:3000]
            except Exception:
                pass
        if after_path and Path(after_path).exists():
            try:
                after_content = Path(after_path).read_text(encoding='utf-8')[:3000]
            except Exception:
                pass

        return {
            'event_id': event_id,
            'file': state.get('file', ''),
            'before_lines': len((before_content or '').splitlines()),
            'after_lines': len((after_content or '').splitlines()),
            'before_preview': (before_content or '')[:500],
            'after_preview': (after_content or '')[:500],
        }

    def undo_execute(self, event_id: str, confirmed: bool = False) -> dict:
        """
        Undo a specific change. Requires confirmed=True.
        Calls recovery_util.undo_single_change().
        """
        if not confirmed:
            return {'error': 'Confirmation required. Pass confirmed=True to proceed.'}
        try:
            import sys as _sys
            _sys.path.insert(0, str(self._trainer_root / 'Data'))
            import recovery_util as _ru
            success, msg = _ru.undo_single_change(event_id)
            return {'success': success, 'message': msg, 'event_id': event_id}
        except Exception as e:
            import traceback
            return {'error': str(e), 'traceback': traceback.format_exc()}

    def task_context(self, task_id: str) -> dict:
        """Load task_context_{tid}.json from plans/Tasks/."""
        tasks_dir = self._trainer_root / 'Data' / 'plans' / 'Tasks'
        candidate = tasks_dir / f'task_context_{task_id}.json'
        if not candidate.exists():
            # Try without 'task_' prefix
            for f in tasks_dir.glob(f'*{task_id}*.json') if tasks_dir.exists() else []:
                candidate = f
                break
        if not candidate.exists():
            return {'error': f'task_context not found for: {task_id}'}
        try:
            import json as _json
            return _json.loads(candidate.read_text(encoding='utf-8'))
        except Exception as e:
            return {'error': str(e)}

    def plan_status(self, task_id: str) -> dict:
        """Returns GO/BLOCKED/NEEDS_REVIEW from task completion_signals."""
        ctx = self.task_context(task_id)
        if 'error' in ctx:
            return ctx
        signals = ctx.get('completion_signals', {})
        status = signals.get('inferred_status', 'NO_EVIDENCE')
        return {
            'task_id': task_id,
            'status': status,
            'changes_count': signals.get('changes_count', 0),
            'probes_passing': signals.get('probes_passing', 0),
            'probes_failing': signals.get('probes_failing', 0),
            'all_probes_green': signals.get('all_probes_green', False),
        }

    def probe_file(self, file_hint: str) -> dict:
        """Run a fresh import probe on a file via importlib.util.exec_module."""
        import importlib.util as _ilu
        import sys as _sys

        fp = self._teaching._resolve_file(file_hint)
        if fp is None:
            return {'error': f'File not found: {file_hint}'}

        result = {'file': str(fp), 'probe_status': 'UNKNOWN', 'errors': []}
        try:
            import py_compile as _pc
            _pc.compile(str(fp), doraise=True)
        except Exception as e:
            result['probe_status'] = 'FAIL'
            result['errors'].append(f'SyntaxError: {e}')
            return result

        try:
            spec = _ilu.spec_from_file_location('_morph_probe', str(fp))
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            result['probe_status'] = 'PASS'
        except (ImportError, ModuleNotFoundError) as e:
            result['probe_status'] = 'WARN'
            result['errors'].append(f'ImportWarn: {e}')
        except Exception as e:
            result['probe_status'] = 'FAIL'
            result['errors'].append(f'ExecProbe: {e}')
        return result


# =============================================================================
# Main Integration Function
# =============================================================================

def integrate_with_orchestrator(orchestrator_instance, config_dir: Path = None):
    """
    Main integration function to wire up all components.

    Args:
        orchestrator_instance: Instance of MetacognitiveOrchestrator
        config_dir: Directory containing JSON configs
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent

    # Initialize components
    classifier = FiveWOneHClassifier(config_dir)
    registry_file = config_dir.parent.parent / "capability_registry.json"
    capability_registry = CapabilityRegistry(registry_file)
    question_queue = ZenityQuestionQueue()
    activity_bridge = ActivitySuggestionBridge(capability_registry, question_queue=question_queue)

    print("✓ Activity Integration Bridge initialized")
    print(f"  - 5W1H Classifier: {len(classifier.baseline.get('dimensions', {}))} dimensions")
    print(f"  - Capability Registry: {len(capability_registry.capabilities)} onboarded capabilities")
    print(f"  - Question Queue: Ready")

    return {
        'classifier': classifier,
        'capability_registry': capability_registry,
        'question_queue': question_queue,
        'activity_bridge': activity_bridge
    }


class OsToolkitGroundingBridge:
    """
    Extracts grounded codebase facts from Os_Toolkit data stores.
    Reads enriched_changes, provisions_catalog, and temporal manifests
    to produce a structured context dict usable by ActivitySuggestionBridge.
    """

    _SIZE_LIMIT = 50 * 1024 * 1024  # 50 MB guard (same as Os_Toolkit)

    def __init__(self, babel_root: Path):
        # Resolve to absolute so parent traversals are unambiguous
        babel_root = Path(babel_root).resolve()
        # babel_root may be .../action_panel_tab/babel_data  OR  .../action_panel_tab/
        if babel_root.name == "babel_data":
            self._apt = babel_root.parent
            self.babel_root = babel_root
        else:
            self._apt = babel_root
            self.babel_root = babel_root / "babel_data"

    def load(self) -> dict:
        """
        Returns a grounded_context dict with keys:
          recent_changes     - List[dict] from enriched_changes (last 72 h)
          probe_failures     - List[dict] entries where probe_status == 'fail'
          high_risk_files    - List[str] files with risk in ('HIGH', 'CRITICAL')
          provisions         - List[dict] from provisions_catalog.json
          temporal_hot_spots - List[dict] top-10 files by change_count
          gap_severity       - 'critical' | 'high' | 'low'
          priority_pct       - float 0.0–1.0
        """
        ctx = {
            'recent_changes': [],
            'probe_failures': [],
            'high_risk_files': [],
            'provisions': [],
            'temporal_hot_spots': [],
            'gap_severity': 'low',
            'priority_pct': 0.0,
        }
        self._load_enriched_changes(ctx)
        self._load_provisions(ctx)
        self._load_temporal_hotspots(ctx)
        return ctx

    def _load_enriched_changes(self, ctx: dict) -> None:
        # version_manifest.json lives at Trainer/Data/backup/
        vm_path = self._apt.parent.parent.parent / "Data" / "backup" / "version_manifest.json"
        if not vm_path.exists():
            return
        try:
            if vm_path.stat().st_size > self._SIZE_LIMIT:
                return
            import json as _json
            data = _json.loads(vm_path.read_text(encoding='utf-8'))
        except Exception:
            return

        ec = data.get('enriched_changes', {})
        if not ec:
            return

        import datetime as _dt
        cutoff = _dt.datetime.now() - _dt.timedelta(hours=72)

        recent = []
        for eid, ch in ec.items():
            ts_str = ch.get('timestamp', '')
            try:
                ts = _dt.datetime.fromisoformat(ts_str)
                if ts < cutoff:
                    continue
            except Exception:
                pass  # keep if timestamp unparseable
            # A1: normalize probe_status so None never displays as '?'
            ch['probe_status'] = (ch.get('probe_status') or 'NONE').upper()
            recent.append(ch)

        recent.sort(key=lambda c: c.get('timestamp', ''), reverse=True)
        ctx['recent_changes'] = recent

        ctx['probe_failures'] = [c for c in recent if c.get('probe_status') in ('FAIL', 'ERROR')]
        ctx['high_risk_files'] = list({
            c.get('file', '') for c in recent
            if c.get('risk_level', '') in ('HIGH', 'CRITICAL') and c.get('file')
        })

        nf = len(ctx['probe_failures'])
        ctx['gap_severity'] = 'critical' if nf > 3 else ('high' if nf > 0 else 'low')
        nr = len(recent)
        nh = len(ctx['high_risk_files'])
        ctx['priority_pct'] = min(1.0, nh / nr) if nr else 0.0

    def _load_provisions(self, ctx: dict) -> None:
        prov_path = self.babel_root / "inventory" / "provisions_catalog.json"
        if not prov_path.exists():
            return
        try:
            import json as _json
            ctx['provisions'] = _json.loads(
                prov_path.read_text(encoding='utf-8')
            ).get('packages', [])
        except Exception:
            pass

    @staticmethod
    def _backup_key_to_source_path(key: str, name_index: Optional[dict] = None) -> str:
        """
        A2: Convert temporal manifest backup filename key to a source-relative path.
        Keys look like: Data_tabs_ag_forge_tab_modules_quick_clip_tabs_planner_tab.py

        name_index: optional pre-built {basename: relative_path} map for fast lookup.
        Falls back to prefix-based heuristic when index not provided or miss.
        """
        for ext in ('.py', '.json', '.md', '.txt'):
            if key.endswith(ext):
                stem = key[:-len(ext)]
                # Try progressively longer name suffixes (last 1, 2, 3 underscore segments)
                if name_index is not None:
                    parts = stem.split('_')
                    for n in range(1, min(4, len(parts) + 1)):
                        candidate_name = '_'.join(parts[-n:]) + ext
                        if candidate_name in name_index:
                            return name_index[candidate_name]
                break

        # Fallback: replace known top-level prefix only
        for prefix in ('Data_tabs_', 'Data_plans_', 'Data_backup_', 'Data_'):
            if key.startswith(prefix):
                top = prefix.rstrip('_').replace('_', '/')
                rest = key[len(prefix):]
                return top + '/' + rest
        return key

    @staticmethod
    def _build_name_index(trainer_root: Path) -> dict:
        """
        Build {basename → relative_path} index by walking Trainer/Data once.
        Used by _backup_key_to_source_path for O(1) lookup per hotspot entry.
        Only indexes the primary source file (skips backup/archive directories).
        """
        import os as _os
        import re as _re
        _SKIP_DIRS = frozenset((
            '__pycache__', '.git', 'change_states', 'archive', 'node_modules',
            'backup', 'Provisions', 'pymanifest',
        ))
        _BACKUP_PAT = _re.compile(r'backup|_bak|_old|_copy|_v\d|export|static|examples',
                                  _re.IGNORECASE)
        index = {}
        data_root = Path(trainer_root) / 'Data'
        if not data_root.exists():
            return index
        for root, dirs, files in _os.walk(str(data_root)):
            dirs[:] = [d for d in dirs
                       if d not in _SKIP_DIRS and not _BACKUP_PAT.search(d)]
            for f in files:
                # Don't overwrite — first (shallowest) hit wins
                if f not in index:
                    rel = _os.path.relpath(_os.path.join(root, f), str(trainer_root))
                    index[f] = rel
        return index

    def _load_temporal_hotspots(self, ctx: dict) -> None:
        tm_path = (self.babel_root / "timeline" / "manifests" /
                   "history_temporal_manifest.json")
        if not tm_path.exists():
            return
        try:
            if tm_path.stat().st_size > self._SIZE_LIMIT:
                return
            import json as _json
            data = _json.loads(tm_path.read_text(encoding='utf-8'))
        except Exception:
            return

        # Manifest structure: {"profiles": {filepath: {...}, ...}, ...}
        # A2: build name index once (single os.walk) for fast O(1) per-entry lookup
        trainer_root = self._apt.parent.parent.parent  # Trainer/
        name_index = self._build_name_index(trainer_root)
        raw = data.get('profiles', data)
        if isinstance(raw, dict):
            # Dict keyed by backup filename; values have backup_count / activity_score
            items = [
                {
                    'file': fp,
                    'source_path': self._backup_key_to_source_path(fp, name_index),
                    'change_count': max(
                        prof.get('backup_count', 0),
                        int(prof.get('activity_score', 0))
                    )
                }
                for fp, prof in raw.items()
            ]
        elif isinstance(raw, list):
            def _count(p):
                return (p.get('change_count') or p.get('backup_count') or
                        p.get('modification_count') or 0)
            items = [
                {
                    'file': p.get('file', p.get('path', '')),
                    'source_path': self._backup_key_to_source_path(
                        p.get('file', p.get('path', '')), name_index
                    ),
                    'change_count': _count(p)
                }
                for p in raw
            ]
        else:
            return

        items.sort(key=lambda x: x['change_count'], reverse=True)
        ctx['temporal_hot_spots'] = items[:10]


# =============================================================================
# MorphCapabilityCatalog — Step B: tool awareness for morph-chat
# =============================================================================

class MorphCapabilityCatalog:
    """
    Loads consolidated_menu.json + activities/scripts list.
    Provides relevance-ranked tool suggestions for morph-chat commands:
    tools, scripts, tool <name>, can-i <action>
    """

    # Verb → tool category affinity for suggest_tools_for_change()
    _VERB_AFFINITY = {
        'import':  'import',
        'fix':     'path',
        'path':    'path',
        'analyze': 'analysis',
        'scan':    'analysis',
        'diff':    'analysis',
        'patch':   'analysis',
    }

    def __init__(self, babel_root: Path):
        babel_root = Path(babel_root).resolve()
        if babel_root.name == 'babel_data':
            self._apt = babel_root.parent
            self._babel = babel_root
        else:
            self._apt = babel_root
            self._babel = babel_root / 'babel_data'
        self._tools: list = []    # consolidated_menu entries
        self._scripts: list = []  # activities/scripts entries
        self._loaded = False

    def load(self) -> None:
        """Load consolidated_menu.json and scan activities/scripts/*.py."""
        if self._loaded:
            return
        self._load_menu()
        self._load_scripts()
        self._loaded = True

    def _load_menu(self) -> None:
        menu_path = self._babel / 'inventory' / 'consolidated_menu.json'
        if not menu_path.exists():
            return
        try:
            data = json.loads(menu_path.read_text(encoding='utf-8'))
            all_tools = data.get('tools', [])
            # Filter out seed-copy artifacts from menu
            self._tools = [
                t for t in all_tools
                if 'seed' not in t.get('display_name', '').lower()
                and '_seed' not in t.get('tool_id', '').lower()
                and 'seed' not in t.get('command', '').lower()
            ]
        except Exception:
            pass

    def _load_scripts(self) -> None:
        scripts_dir = (self._apt / 'regex_project' / 'activities' /
                       'tools' / 'scripts')
        if not scripts_dir.exists():
            return
        seen_stems = set()
        for fp in sorted(scripts_dir.glob('*.py')):
            if fp.name.startswith('_'):
                continue
            # Skip seed copies (e.g. import_organizer_seed*.py)
            if '_seed' in fp.stem:
                continue
            # Skip duplicates (shouldn't happen, but defensive)
            if fp.stem in seen_stems:
                continue
            seen_stems.add(fp.stem)
            entry = {'name': fp.stem, 'path': str(fp), 'args': []}
            # Extract argparse subcommands from docstring or argparse usage
            try:
                src = fp.read_text(encoding='utf-8', errors='replace')
                # Find add_parser / add_subparsers calls to get subcommand names
                subs = re.findall(r"add_parser\(['\"]([^'\"]+)['\"]", src)
                if not subs:
                    # Try 'choices' in argparse
                    subs = re.findall(r"choices\s*=\s*\[([^\]]+)\]", src)
                entry['args'] = subs[:8]  # cap at 8
                # First docstring line as description
                m = re.search(r'^"""(.+?)"""', src[:500], re.DOTALL)
                if m:
                    entry['description'] = m.group(1).strip().split('\n')[0][:80]
            except Exception:
                pass
            self._scripts.append(entry)

    def _score_tool(self, tool: dict, tokens: list) -> int:
        score = 0
        name = (tool.get('display_name', '') + ' ' +
                tool.get('category', '') + ' ' +
                tool.get('tool_id', '')).lower()
        command = tool.get('command', '').lower()
        args_text = ' '.join(
            a.get('name', '') + ' ' + a.get('help', '')
            for a in tool.get('arguments', [])
        ).lower()
        for tok in tokens:
            if tok in name:
                score += 3
            if tok in command:
                score += 2
            if tok in args_text:
                score += 1
        return score

    def search(self, query: str, max_results: int = 5) -> list:
        """Relevance-ranked search across consolidated_menu tools + scripts."""
        self.load()
        tokens = re.split(r'[\s_\-]+', query.lower())
        tokens = [t for t in tokens if len(t) >= 2]

        results = []
        seen_ids = set()
        for tool in self._tools:
            # Deduplicate on display_name + command combination
            tid = f"{tool.get('display_name', '')}|{tool.get('command', '')}"
            if tid in seen_ids:
                continue
            s = self._score_tool(tool, tokens)
            if s > 0:
                seen_ids.add(tid)
                results.append((s, 'menu', tool))

        for script in self._scripts:
            sname = script.get('name', '')
            if sname in seen_ids:
                continue
            sc = 0
            name = (sname + ' ' + ' '.join(script.get('args', []))).lower()
            for tok in tokens:
                if tok in name:
                    sc += 3
                if any(tok in a for a in script.get('args', [])):
                    sc += 2
            if sc > 0:
                seen_ids.add(sname)
                results.append((sc, 'script', script))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:max_results]

    def format_tool_card(self, item: tuple) -> str:
        """Format a search result (score, kind, data) into a readable card."""
        _, kind, data = item
        if kind == 'menu':
            args_summary = ' | '.join(
                a.get('name', '?') + (' *' if a.get('required') else '')
                for a in data.get('arguments', [])[:6]
            )
            return (
                f"[TOOL] {data.get('display_name', data.get('tool_id', '?'))}\n"
                f"  command  : {data.get('command', '?')}\n"
                f"  category : {data.get('category', '?')}\n"
                f"  args     : {args_summary or '(none)'}"
            )
        else:
            args_summary = ' | '.join(data.get('args', []))
            return (
                f"[SCRIPT] {data.get('name', '?')}\n"
                f"  path     : {data.get('path', '?')}\n"
                f"  subcommands: {args_summary or '?'}\n"
                f"  about    : {data.get('description', '')}"
            )

    def get_scripts_list(self) -> list:
        """Return all activities/scripts entries."""
        self.load()
        return self._scripts

    def suggest_tools_for_change(self, enriched_change: dict) -> list:
        """
        Return ranked tool suggestions for a given enriched_change.
        Boosts tools whose category matches the change verb/probe_errors.
        """
        self.load()
        verb = (enriched_change.get('verb') or '').lower()
        query_parts = [verb]
        for err in (enriched_change.get('probe_errors') or []):
            # Extract keywords from error text
            query_parts += re.findall(r'\b\w{4,}\b', str(err).lower())[:3]
        query = ' '.join(query_parts)
        results = self.search(query, max_results=3)
        # Boost via affinity map
        affinities = [v for k, v in self._VERB_AFFINITY.items() if k in query]
        for aff in affinities:
            for item in self._tools:
                if aff in item.get('category', '').lower():
                    # Check if not already in results
                    ids = {r[2].get('tool_id') for r in results if r[1] == 'menu'}
                    if item.get('tool_id') not in ids:
                        results.append((1, 'menu', item))
        return results[:5]


# =============================================================================
# MorphManifestBridge — Step D: py_manifest_augmented engine access
# =============================================================================

class MorphManifestBridge:
    """
    Wraps py_manifest_augmented engines (QueryEngine, GraphEngine,
    PatternLearningEngine, HealingEngine) for use in morph-chat commands.
    Falls back gracefully if manifest is stale or unavailable.
    """

    MANIFEST_SEARCH_PATHS = [
        'Data/pymanifest/py_manifest_augmented.json',
        'Data/tabs/map_tab/py_manifest_augmented.json',
    ]
    PY_MANIFEST_PY = 'Data/tabs/map_tab/py_manifest_augmented.py'

    _MIN_FILE_COUNT = 3  # below this, manifest is considered stale

    def __init__(self, babel_root: Path):
        babel_root = Path(babel_root).resolve()
        if babel_root.name == 'babel_data':
            self._apt = babel_root.parent
        else:
            self._apt = babel_root
        self._trainer_root = self._apt.parent.parent.parent
        self._manifest = None   # loaded lazily
        self._engines = {}      # lazy engine cache
        self._available = None  # None = unknown, False = not available

    def _find_manifest_path(self) -> Optional[Path]:
        for rel in self.MANIFEST_SEARCH_PATHS:
            p = self._trainer_root / rel
            if p.exists() and p.stat().st_size > 1024:
                return p
        return None

    def _load(self) -> bool:
        """Load manifest + engines. Returns True if usable."""
        if self._available is not None:
            return self._available
        mp = self._find_manifest_path()
        if mp is None:
            self._available = False
            return False
        # Add py_manifest_augmented.py to path
        py_path = self._trainer_root / self.PY_MANIFEST_PY
        if py_path.parent not in [Path(p) for p in sys.path]:
            sys.path.insert(0, str(py_path.parent))
        try:
            import py_manifest_augmented as _pma
            # Load static manifest
            data = json.loads(mp.read_text(encoding='utf-8'))
            files_count = len(data.get('files', {}))
            if files_count < self._MIN_FILE_COUNT:
                self._available = False
                return False
            # Build Manifest dataclass
            manifest = _pma.Manifest(
                project_root=data.get('project_root', str(self._trainer_root)),
                generated_at=data.get('generated_at', ''),
                files={fp: _pma.FileMetadata(**fm) if isinstance(fm, dict) else fm
                       for fp, fm in data.get('files', {}).items()},
            )
            self._engines['query'] = _pma.QueryEngine(manifest)
            self._engines['graph'] = _pma.GraphEngine(manifest)
            self._available = True
            return True
        except Exception as e:
            self._available = False
            return False

    def query_6w1h(self, dimension: str, value: str) -> list:
        """Wraps QueryEngine.query_6w1h() → list of matching function/file dicts."""
        if not self._load():
            return [{'error': 'manifest not available or stale'}]
        try:
            return self._engines['query'].query_6w1h(dimension, value) or []
        except Exception as e:
            return [{'error': str(e)}]

    def chain_delta(self, target: str) -> dict:
        """Wraps GraphEngine.chain_delta() → call chain with delta scores."""
        if not self._load():
            return {'error': 'manifest not available or stale'}
        try:
            result = self._engines['graph'].chain_delta(target, include_delta=True)
            return result or {'error': f'no chain found for {target}'}
        except Exception as e:
            return {'error': str(e)}

    def format_chain(self, chain_result: dict) -> str:
        """Format chain_delta result into readable output."""
        if 'error' in chain_result:
            return f"  [ERROR] {chain_result['error']}"
        lines = []
        target = chain_result.get('target', '?')
        callers = chain_result.get('callers', [])
        callees = chain_result.get('callees', [])
        delta = chain_result.get('delta_score', 0)
        lines.append(f"[CALL GRAPH: {target}]")
        lines.append(f"  Delta score : {delta:.2f} (coupling indicator)")
        if callers:
            lines.append(f"  Called by   : {', '.join(str(c) for c in callers[:5])}")
        if callees:
            lines.append(f"  Calls       : {', '.join(str(c) for c in callees[:5])}")
        if delta > 0.7:
            lines.append(f"  [WARN] High coupling — consider refactoring")
        return '\n'.join(lines)

    def is_available(self) -> bool:
        """Check if manifest is loaded and has sufficient data."""
        return self._load()


# =============================================================================
# MorphConformer — Step E: </Diffs>-compatible plan template generator
# =============================================================================

class MorphConformer:
    """
    Generates </Diffs>-compatible plan markdown from task_context + enriched_changes.
    Output parseable by planner_tab._parse_expected_diffs() and Os_Toolkit plan consolidate.
    """

    def __init__(self, babel_root: Path):
        babel_root = Path(babel_root).resolve()
        if babel_root.name == 'babel_data':
            self._apt = babel_root.parent
        else:
            self._apt = babel_root
        self._trainer_root = self._apt.parent.parent.parent

    def generate_plan(self, task_id: str, task_context: dict,
                      grounded: dict, output_dir: Optional[Path] = None) -> Path:
        """
        Build morph_plan_{task_id}.md in output_dir (default: plans/Morph/).

        Template sections:
        </High_Level>   — title, goal, risk summary
        </Mid_Level>    — functions touched, imports, probe history
        </Diffs>        — enriched_change → Os_Toolkit Diffs format
        </Tests>        — probe assertions
        </Tasks>        — task_ids with status
        """
        if output_dir is None:
            output_dir = self._trainer_root / 'Data' / 'plans' / 'Morph'
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filter grounded changes to those linked to this task
        all_changes = grounded.get('recent_changes', [])
        task_changes = [
            c for c in all_changes
            if task_id in (c.get('task_ids') or [])
            or task_id in str(c.get('feature', ''))
        ]
        if not task_changes:
            # Fallback: use wherein from task_context
            wherein = task_context.get('wherein', '')
            if wherein:
                basename = Path(wherein).name
                task_changes = [
                    c for c in all_changes
                    if basename in str(c.get('file', ''))
                ]

        title = task_context.get('title', f'Task {task_id}')
        wherein = task_context.get('wherein', 'unknown')
        status = task_context.get('status', 'pending')

        # Aggregate risk/probe from changes
        risks = [c.get('risk_level', c.get('risk', 'LOW')) for c in task_changes]
        probes = [c.get('probe_status', 'NONE') for c in task_changes]
        top_risk = ('CRITICAL' if 'CRITICAL' in risks else
                    'HIGH' if 'HIGH' in risks else
                    'MEDIUM' if 'MEDIUM' in risks else 'LOW')
        probe_summary = (f"FAIL({probes.count('FAIL')})" if 'FAIL' in probes
                         else 'PASS' if 'PASS' in probes else 'NONE')

        lines = [
            f"</MORPH_PLAN>: {task_id} — {title}",
            "",
            "</High_Level>",
            f"Task    : {task_id}",
            f"Title   : {title}",
            f"Wherein : {wherein}",
            f"Status  : {status}",
            f"Risk    : {top_risk} | Probe: {probe_summary}",
            f"Changes : {len(task_changes)} linked enriched_changes",
            "<High_Level/>",
            "",
        ]

        # Mid-level: functions and imports
        all_methods = []
        all_imports = []
        for c in task_changes:
            all_methods.extend(c.get('methods', []) or [])
            all_imports.extend(c.get('imports_added', []) or [])
        lines += [
            "</Mid_Level>",
            f"Functions touched : {', '.join(sorted(set(all_methods))[:10]) or 'unknown'}",
            f"Imports added     : {', '.join(sorted(set(all_imports))[:8]) or 'none'}",
            f"Probe history     : {probe_summary}",
            "<Mid_Level/>",
            "",
        ]

        # Diffs block (Os_Toolkit compatible format)
        lines += self._build_diffs_block(task_id, wherein, task_changes)
        lines.append("")

        # Tests block
        lines += self._build_tests_block(task_changes, task_context)
        lines.append("")

        # Tasks block
        lines += self._build_tasks_block(task_id, task_context)
        lines.append("")
        lines.append("<MORPH_PLAN/>")

        content = '\n'.join(lines)
        from datetime import datetime as _dt
        _ts = _dt.now().strftime('%Y%m%d_%H%M%S')
        out_path = output_dir / f'morph_plan_{task_id}_{_ts}.md'
        out_path.write_text(content, encoding='utf-8')
        return out_path

    def _build_diffs_block(self, task_id: str, wherein: str,
                            changes: list) -> list:
        """Build </Diffs> ... <Diffs/> block compatible with _parse_expected_diffs()."""
        lines = [
            f"</Diffs>: (Modify) {{WHERE:[{wherein}]}}",
        ]
        # Group by file
        by_file: dict = {}
        for c in changes:
            fp = c.get('file', wherein)
            by_file.setdefault(fp, []).append(c)

        for fp, file_changes in by_file.items():
            fname = Path(fp).name
            total_add = sum(c.get('additions', 0) or 0 for c in file_changes)
            total_del = sum(c.get('deletions', 0) or 0 for c in file_changes)
            lines.append(f"[File/Doc] - [{fname}]")
            lines.append(f" -path: {fp}")
            lines.append(f" -Lines")
            lines.append(f"  -{total_del}")
            lines.append(f"  +{total_add}")
            for c in file_changes:
                eid = c.get('event_id', '?')
                verb = c.get('verb', 'modify')
                risk = c.get('risk_level', c.get('risk', 'LOW'))
                tids = ','.join(c.get('task_ids') or [task_id])
                methods = ','.join((c.get('methods') or [])[:4])
                lines.append(f"-#[Event:{eid}] ({verb}, risk:{risk}, tasks:{tids})")
                if methods:
                    lines.append(f" -{methods}")
        lines.append("<Diffs/>")
        return lines

    def _build_tests_block(self, changes: list, task_context: dict) -> list:
        probes = [c.get('probe_status', 'NONE') for c in changes]
        all_imports = []
        all_methods = []
        for c in changes:
            all_imports.extend(c.get('imports_added') or [])
            all_methods.extend(c.get('methods') or [])

        lines = ["</Tests>"]
        lines.append(f"- probe_status: {set(probes)}")
        if all_imports:
            lines.append(f"- imports_added should include: {', '.join(sorted(set(all_imports)))}")
        if all_methods:
            lines.append(f"- methods must exist in AST: {', '.join(sorted(set(all_methods))[:6])}")
        sigs = task_context.get('completion_signals', {})
        if sigs:
            lines.append(f"- completion_signal: {sigs.get('status', 'unknown')}")
        lines.append("<Tests/>")
        return lines

    def _build_tasks_block(self, task_id: str, task_context: dict) -> list:
        lines = ["</Tasks>"]
        title = task_context.get('title', '?')
        status = task_context.get('status', 'pending')
        wherein = task_context.get('wherein', '?')
        lines.append(f"-TYPE:FILE")
        lines.append(f" - {task_id}: {title} [{status.upper()}]")
        lines.append(f" - wherein: {wherein}")
        exp = task_context.get('expected_diffs', [])
        for ed in exp[:5]:
            check = '✓' if ed.get('matched') else '○'
            lines.append(f" - {check} {ed.get('description', str(ed))}")
        lines.append("<Tasks/>")
        return lines

    def get_plan_summary(self, out_path: Path, task_changes: list,
                         task_context: dict) -> str:
        """Return a human-readable summary of the generated plan."""
        exp_diffs = task_context.get('expected_diffs', [])
        sigs = task_context.get('completion_signals', {})
        return (
            f"  Written    : {out_path}\n"
            f"  Changes    : {len(task_changes)} linked events\n"
            f"  Exp. diffs : {len(exp_diffs)}\n"
            f"  Plan status: {sigs.get('status', 'unknown')}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# MorphDatasetExporter — Phase I
# ──────────────────────────────────────────────────────────────────────────────

class MorphDatasetExporter:
    """
    Generates JSONL training data from enriched_changes + task_contexts +
    morph plan output.  Each record is a {system, user, assistant} triple
    compatible with Ollama fine-tuning and llama.cpp alpaca format.

    Record types:
      CHANGE_ANALYSIS  – per enriched_change: risk/blame/probe/suggested action
      TASK_PLAN        – per task_context: plan conformer output
      HOTSPOT          – top temporal hotspots: activity summary
      SELF_DEBUG       – morph-chat `debug` sessions: error → control_signal → fix plan
                         (appended by orchestrator.py export command from grounded_ctx)
    """

    SYSTEM_PROMPT = (
        "You are Morph, a code intelligence assistant deeply familiar with the Trainer "
        "project codebase. You understand enriched code change events, task attribution, "
        "probe results, call graphs, and AoE vectors. Given a change event and its context "
        "you assess risk, explain what changed, identify related tasks, and suggest next steps."
    )

    MODELFILE_TEMPLATE = """\
FROM {base_model}

SYSTEM \"\"\"{system_prompt}

Project context:
- Core systems: interactive_trainer_gui_NEW.py, planner_tab.py, Os_Toolkit.py,
  orchestrator.py, activity_integration_bridge.py
- Change tracking: enriched_changes in version_manifest.json
- Attribution: AoE vectors (89 vectors, 11 layers) in aoe_vector_config.json
- Task system: todos.json phases, task_context_{{tid}}.json per task
- Probe system: exec-probe (PASS/WARN/FAIL) linked to each change event
- Plans: morph_plan_{{tid}}.md in Data/plans/Morph/

When analyzing a change event, structure responses as:
1. Risk level + reasons
2. Probe status + resolution chain (if FAIL)
3. Tasks affected
4. Suggested next step (action verb + target)
5. AoE vectors affected (what/where/who/why/how)

Codebase conventions:
- Mark refs: #[Mark:XXXX], Event refs: #[Event:XXXX], Task refs: task_NN_N
- Risk levels: CRITICAL > HIGH > MEDIUM > LOW
- Verb categories: add/modify/delete/import/refactor/fix/test
- AoE layers: attribution, version_health, ux_baseline, code_profile,
  query_weights, temporal, morph_opinion
\"\"\"

PARAMETER temperature 0.25
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1
PARAMETER num_ctx 8192
"""

    def __init__(self, trainer_root: Path | None = None):
        self._scripts_dir   = Path(__file__).resolve().parent
        self._action_dir    = self._scripts_dir.parents[3]
        self._trainer_root  = Path(trainer_root) if trainer_root else self._action_dir.parents[2]
        self._manifest_path = self._trainer_root / "Data" / "backup" / "version_manifest.json"
        self._task_ctx_dir  = self._trainer_root / "Data" / "plans" / "Tasks"
        self._output_dir    = self._trainer_root / "Data" / "training_data"

    # ------------------------------------------------------------------ export
    def export(
        self,
        task_id: str | None = None,
        include_all: bool = True,
        output_path: Path | None = None,
    ) -> tuple[Path, int, int]:
        """
        Build and write JSONL dataset.  Returns (output_path, record_count, token_estimate).
        """
        from datetime import datetime as _dt
        records: list[dict] = []

        # Load version manifest
        vm: dict = {}
        if self._manifest_path.exists():
            try:
                vm = json.loads(self._manifest_path.read_text(encoding='utf-8'))
            except Exception:
                pass

        ec_all: dict = vm.get('enriched_changes', {})
        cs_all: dict = vm.get('change_states', {})

        # -- CHANGE_ANALYSIS records --
        teaching_bridge: MorphTeachingBridge | None = None
        try:
            teaching_bridge = MorphTeachingBridge(self._trainer_root)
        except Exception:
            pass

        for eid, ec in ec_all.items():
            # Filter by task_id if specified
            if task_id:
                if task_id not in (ec.get('task_ids') or []):
                    continue
            rec = self._make_change_record(eid, ec, cs_all.get(eid, {}), teaching_bridge)
            if rec:
                records.append(rec)

        # -- TASK_PLAN records (from task_context files) --
        if self._task_ctx_dir.exists():
            for tc_path in sorted(self._task_ctx_dir.glob('task_context_*.json')):
                tid = tc_path.stem.replace('task_context_', '', 1)
                if task_id and task_id != tid:
                    continue
                try:
                    tc = json.loads(tc_path.read_text(encoding='utf-8'))
                    # Only include if has real data (changes or expected_diffs)
                    if tc.get('changes') or tc.get('expected_diffs') or tc.get('metastate'):
                        rec = self._make_task_plan_record(tid, tc)
                        if rec:
                            records.append(rec)
                except Exception:
                    pass

        # -- HOTSPOT records (top 5 from temporal manifest) --
        if include_all:
            hotspot_records = self._make_hotspot_records(vm)
            records.extend(hotspot_records)

        if not records:
            print("[MorphDatasetExporter] No records generated — check data sources")
            return (self._output_dir / "morph_dataset_empty.jsonl", 0, 0)

        # Write output
        self._output_dir.mkdir(parents=True, exist_ok=True)
        ts = _dt.now().strftime('%Y%m%d_%H%M%S')
        out_path = output_path or (self._output_dir / f"morph_dataset_{ts}.jsonl")
        out_path = self.write_jsonl(records, out_path)

        total_tokens = sum(
            self.token_count_estimate(json.dumps(r, default=str))
            for r in records
        )
        return out_path, len(records), total_tokens

    def _make_change_record(
        self,
        event_id: str,
        ec: dict,
        cs: dict,
        teaching_bridge: 'MorphTeachingBridge | None',
    ) -> dict | None:
        """One ChatML record for a change event."""
        rel_file    = ec.get('file', '?')
        verb        = ec.get('verb', '?')
        feature     = ec.get('feature', '?')
        risk_level  = ec.get('risk_level', '?')
        risk_conf   = ec.get('risk_confidence', '?')
        probe_st    = ec.get('probe_status') or 'n/a'
        probe_errs  = ec.get('probe_errors') or []
        task_ids    = ec.get('task_ids') or []
        methods     = ec.get('methods') or []
        risk_rsns   = ec.get('risk_reasons') or []
        blame       = ec.get('blame_event', '')
        additions   = ec.get('additions', 0)
        deletions   = ec.get('deletions', 0)
        bav         = ec.get('before_after_values') or []

        # Blueprint snippet (top LOC info if bridge available)
        blueprint_snippet = ''
        if teaching_bridge:
            try:
                bp = teaching_bridge.get_file_blueprint(rel_file)
                loc     = bp.get('loc', '?')
                fn_count = len(bp.get('functions', []))
                blueprint_snippet = f"File: {rel_file} ({loc} lines, {fn_count} functions)"
            except Exception:
                blueprint_snippet = f"File: {rel_file}"
        else:
            blueprint_snippet = f"File: {rel_file}"

        # User message
        bav_str = '\n'.join(
            f"  line {b.get('line','?')}: {b.get('before','')[:60]} → {b.get('after','')[:60]}"
            for b in bav[:3]
        )
        user_msg = (
            f"[CODE CHANGE EVENT: {event_id}]\n"
            f"{blueprint_snippet}\n"
            f"Change: {verb} — {feature}\n"
            f"Risk: {risk_level} (confidence: {risk_conf})\n"
            f"Functions touched: {', '.join(methods[:6]) or 'none'}\n"
            f"AoE context:\n"
            f"  tasks: {', '.join(task_ids) or 'none'}\n"
            f"  probe: {probe_st}  errors: {'; '.join(probe_errs[:2]) or 'none'}\n"
            f"Code changes (+{additions}/-{deletions}):\n{bav_str}"
        )

        # Assistant message (structured assessment)
        risk_reasons_str = ('\n'.join(f"  - {r}" for r in risk_rsns[:4])
                            or '  - No specific risk reasons captured')
        resolution_note = ''
        if probe_st == 'FAIL' and blame:
            resolution_note = f"\nResolution path: blame={blame} (check if resolved_by event exists)"
        elif probe_st == 'FAIL':
            resolution_note = "\nResolution path: no blame event — investigate manually"

        tasks_fmt = ', '.join(task_ids) if task_ids else 'none assigned'

        assistant_msg = (
            f"Risk Assessment: {risk_level}\n"
            f"Reasons:\n{risk_reasons_str}\n"
            f"\nProbe Status: {probe_st}{resolution_note}\n"
            f"\nTasks affected: {tasks_fmt}\n"
            f"\nSuggested next step: "
            + (f"Investigate probe failure in {rel_file} via diagnose command" if probe_st == 'FAIL'
               else f"Review {verb} change to {feature} — verify all {len(methods)} touched functions")
            + f"\n\nAoE attribution: {verb} into '{feature}' "
            + f"with +{additions}/-{deletions} net lines"
        )

        return {
            'messages': [
                {'role': 'system',    'content': self.SYSTEM_PROMPT},
                {'role': 'user',      'content': user_msg},
                {'role': 'assistant', 'content': assistant_msg},
            ],
            'metadata': {
                'record_type': 'CHANGE_ANALYSIS',
                'event_id':    event_id,
                'file':        rel_file,
                'risk_level':  risk_level,
                'probe_status': probe_st,
                'timestamp':   ec.get('timestamp', ''),
            },
        }

    def _make_task_plan_record(self, tid: str, tc: dict) -> dict | None:
        """One ChatML record for a task plan / task context."""
        meta        = tc.get('_meta', {})
        title       = meta.get('title', tid)
        wherein     = meta.get('wherein', tc.get('wherein', '?'))
        project_id  = meta.get('project_id', '?')
        changes     = tc.get('changes', [])
        exp_diffs   = tc.get('expected_diffs', [])
        metastate   = tc.get('metastate', {})
        comp_sigs   = tc.get('completion_signals', {})
        qw          = tc.get('query_weights_data', {})

        if not (changes or exp_diffs or metastate):
            return None

        user_msg = (
            f"[TASK CONTEXT: {tid}]\n"
            f"Title: {title}\n"
            f"Wherein: {wherein}\n"
            f"Project: {project_id}\n"
            f"Changes linked: {len(changes)}\n"
            f"Expected diffs: {len(exp_diffs)}\n"
            f"Gap severity: {metastate.get('gap_severity', '?')}\n"
            f"5W1H:\n"
            f"  what: {qw.get('what','?')[:60]}\n"
            f"  why:  {qw.get('why','?')[:60]}\n"
            f"  how:  {qw.get('how','?')}\n"
            f"  state: {qw.get('state','?')}\n"
        )

        status     = comp_sigs.get('inferred_status', 'NO_EVIDENCE')
        probes_ok  = comp_sigs.get('probes_passing', 0)
        probes_fail = comp_sigs.get('probes_failing', 0)

        assistant_msg = (
            f"Task Status: {status}\n"
            f"Probes: {probes_ok} passing, {probes_fail} failing\n"
            f"Recommended action: {metastate.get('recommended_action', 'STANDARD_RESPONSE')}\n"
            f"Priority: {int(metastate.get('priority_pct', 0) * 100)}%\n"
            f"\n"
            + (f"Expected changes to {wherein}:\n"
               + '\n'.join(
                   f"  [{d.get('type','?')}] {d.get('file','?')} — "
                   f"{', '.join(d.get('methods',[])[:3])}"
                   for d in exp_diffs[:5]
               )
               if exp_diffs else "No expected diffs captured yet.")
        )

        return {
            'messages': [
                {'role': 'system',    'content': self.SYSTEM_PROMPT},
                {'role': 'user',      'content': user_msg},
                {'role': 'assistant', 'content': assistant_msg},
            ],
            'metadata': {
                'record_type': 'TASK_PLAN',
                'task_id':     tid,
                'wherein':     wherein,
                'status':      status,
            },
        }

    def _make_hotspot_records(self, vm: dict) -> list[dict]:
        """Records for top temporal hotspots."""
        records = []
        # Get hotspots from enriched_changes grouped by file
        file_counts: dict[str, int] = {}
        for ec in vm.get('enriched_changes', {}).values():
            f = ec.get('file', '')
            if f:
                file_counts[f] = file_counts.get(f, 0) + 1
        top_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        for rel_file, change_count in top_files:
            user_msg = (
                f"[HOTSPOT QUERY]\n"
                f"Which file has the most changes and why is it a hotspot?\n"
                f"File: {rel_file}\n"
                f"Change count: {change_count}"
            )
            assistant_msg = (
                f"{rel_file} is a hotspot with {change_count} recorded changes.\n"
                f"It is likely central to ongoing feature development or frequently "
                f"modified during bug-fix cycles. Review its probe history and task "
                f"attributions before making further changes to avoid regression."
            )
            records.append({
                'messages': [
                    {'role': 'system',    'content': self.SYSTEM_PROMPT},
                    {'role': 'user',      'content': user_msg},
                    {'role': 'assistant', 'content': assistant_msg},
                ],
                'metadata': {'record_type': 'HOTSPOT', 'file': rel_file, 'change_count': change_count},
            })
        return records

    def token_count_estimate(self, text: str) -> int:
        """Rough GPT-style token estimate: word count × 1.33."""
        return int(len(text.split()) * 1.33)

    def write_jsonl(self, records: list[dict], output_path: Path) -> Path:
        """Write records as JSONL (one JSON object per line)."""
        with open(output_path, 'w', encoding='utf-8') as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
        size_kb = output_path.stat().st_size // 1024
        print(f"[MorphDatasetExporter] Written: {output_path} ({size_kb} KB, {len(records)} records)")
        return output_path

    def write_modelfile(
        self,
        output_path: Path | None = None,
        base_model: str | None = None,
        morph_root: Path | None = None,
    ) -> Path:
        """Write an Ollama Modelfile for Morph-001.

        base_model resolution order:
          1. Explicit base_model argument
          2. Latest *.gguf in morph_root/exports/gguf/ (auto-detected)
          3. Placeholder: llama3.2:latest (with instructions to export GGUF)
        """
        if base_model is None:
            if morph_root is None:
                morph_root = self._trainer_root / "Models" / "Morph0.1-10m-Babble"
            gguf_dir = morph_root / "exports" / "gguf"
            gguf_candidates = sorted(gguf_dir.glob("*.gguf")) if gguf_dir.exists() else []
            if gguf_candidates:
                base_model = str(gguf_candidates[-1])
                print(f"[MorphDatasetExporter] Auto-detected GGUF: {Path(base_model).name}")
            else:
                base_model = 'llama3.2:latest'
                print("[WARN] No Morph GGUF found. Using llama3.2:latest as placeholder.")
                print("[WARN] Export Morph0.1 via models_tab.py → History → Levels → Export to GGUF")
                print(f"[WARN] Expected path: {gguf_dir / 'morph_q8_0.gguf'}")

        out = output_path or (self._output_dir / 'Morph.modelfile')
        out.parent.mkdir(parents=True, exist_ok=True)
        content = self.MODELFILE_TEMPLATE.format(
            base_model=base_model,
            system_prompt=self.SYSTEM_PROMPT,
        )
        out.write_text(content, encoding='utf-8')
        print(f"[MorphDatasetExporter] Modelfile written: {out}")
        return out


class MorphExportManager:
    """
    Orchestrate Morph variant export lifecycle:
      - bundle_variant: write versioned JSONL bundle to Models/<base>/exports/variants/
      - prep_lora_config: generate LoRA training config from accepted interactions
      - register_level: write Models/archive/levels/{base}/{name}/manifest.json

    Connects lineage_tracker morph_interactions → LoRA training config → level manifest.
    """

    def __init__(self, trainer_root: Path = None):
        if trainer_root is None:
            trainer_root = Path(__file__).resolve().parents[6]  # up to Trainer/
        self._trainer_root = trainer_root
        self._models_dir = trainer_root / "Models"

    def bundle_variant(self, variant_sha: str, export_name: str = None) -> Path:
        """
        Find the variant JSON matching variant_sha and copy it to
        Models/Morph0.1-10m-Babble/exports/variants/ as a versioned JSONL bundle.
        Returns the bundle path on success, or raises FileNotFoundError.
        """
        variants_src = self._models_dir / "Morph0.1-10m-Babble" / "Morph_regex" / "variants"
        if not variants_src.exists():
            raise FileNotFoundError(f"Variants directory not found: {variants_src}")

        # Find variant file matching sha
        import shutil
        matched = None
        for vf in variants_src.glob("morph_variant_*.json"):
            if variant_sha in vf.stem:
                matched = vf
                break
        if matched is None:
            raise FileNotFoundError(f"No variant JSON found for sha '{variant_sha}' in {variants_src}")

        out_name = export_name or matched.stem
        out_dir = self._models_dir / "Morph0.1-10m-Babble" / "exports" / "variants"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{out_name}.jsonl"

        # Write as single-line JSONL bundle (one JSON object per line)
        import json as _json
        record = _json.loads(matched.read_text(encoding='utf-8'))
        from datetime import datetime as _dt
        bundle = {
            "bundle_type":  "morph_variant",
            "variant_sha":  variant_sha,
            "export_name":  out_name,
            "created":      _dt.now().isoformat(),
            "variant_data": record,
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(_json.dumps(bundle, ensure_ascii=False) + '\n')

        print(f"[MorphExportManager] Bundle written: {out_path}")
        return out_path

    def prep_lora_config(self, base_model: str, interactions_jsonl: Path) -> dict:
        """
        Generate a LoRA training config dict from accepted morph interaction records.

        Args:
            base_model: HuggingFace model name or local path for base model
            interactions_jsonl: Path to morph_evals/accepted_*.jsonl

        Returns:
            dict with keys: model_name_or_path, output_dir, training_data, lora_r, lora_alpha,
                            num_train_epochs, learning_rate
        """
        import json as _json
        records = []
        if interactions_jsonl.exists():
            with open(interactions_jsonl, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(_json.loads(line))
                        except Exception:
                            pass

        config = {
            "model_name_or_path": base_model,
            "output_dir": str(self._models_dir / "Morph0.1-10m-Babble" /
                              f"training_lora_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            "training_data": str(interactions_jsonl),
            "num_training_samples": len(records),
            "lora_r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "num_train_epochs": max(1, min(3, len(records) // 20)),
            "per_device_train_batch_size": 1,
            "learning_rate": 2e-4,
            "fp16": True,
            "save_steps": 50,
            "logging_steps": 10,
        }
        print(f"[MorphExportManager] LoRA config prepared: {len(records)} samples, "
              f"{config['num_train_epochs']} epochs")
        return config

    def register_level(
        self,
        base_model: str,
        adapters: list,
        notes: str = "",
        level_name: str = None,
    ) -> Path:
        """
        Write a level manifest to Models/archive/levels/{clean_base}/{level_name}/manifest.json.

        Args:
            base_model: Name of the base model
            adapters: List of adapter paths (strings)
            notes: Optional description
            level_name: If None, auto-generates from timestamp

        Returns:
            Path to the written manifest.json
        """
        import json as _json
        from datetime import datetime as _dt

        clean_base = base_model.replace('/', '_').replace(':', '_')
        if level_name is None:
            level_name = f"level_{_dt.now().strftime('%Y%m%d_%H%M%S')}"

        level_dir = self._models_dir / "archive" / "levels" / clean_base / level_name
        level_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "name":       level_name,
            "base_model": base_model,
            "created":    _dt.now().isoformat(),
            "adapters":   [{"name": str(a)} for a in adapters],
            "notes":      notes,
            "exports":    [],
        }
        manifest_path = level_dir / "manifest.json"
        manifest_path.write_text(_json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"[MorphExportManager] Level registered: {manifest_path}")
        return manifest_path


if __name__ == "__main__":
    # Test 5W1H Classifier
    print("=== Testing 5W1H Classifier ===\n")

    classifier = FiveWOneHClassifier()

    test_tools = [
        "code_analyzer.py",
        "path-fixer.py",
        "import_organizer.py",
        "workflow_manager.py"
    ]

    for tool in test_tools:
        print(f"Classifying: {tool}")
        classification = classifier.classify(tool, "")
        print(f"  Confidence: {classification.get('confidence', 0):.0%}")
        for dim in ['what', 'how', 'where']:
            print(f"  {dim}: {classification.get(dim, 'N/A')}")
        print()
