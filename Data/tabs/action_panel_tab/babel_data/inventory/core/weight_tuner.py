#!/usr/bin/env python3
"""
Weight Tuner - Iterative confidence weight correction system
Part of Babel v01a Intelligence Layer

#[Mark:P0-PropertyAttributionGap] FOUNDATIONAL: Schema alignment across core 3 scripts
#[Mark:P1-WeightTuner] Data-driven weight correction using manifest properties + Morph validation

#TODO: [P0-FOUNDATION] Map property attribution across Os_Toolkit/Filesync/onboarder
#TODO: [P0-FOUNDATION] Document data field schemas for each measurement system
#TODO: [P0-FOUNDATION] Create unified property alignment schema (6W1H base)
#TODO: [P0-FOUNDATION] Catalog measurement systems: what fields exist where
#TODO: [P0-FOUNDATION] Add call graph mapping per file profile (class/type/data fields)

#TODO: [P0-SCHEMA-GAPS] Filesync.py - Add 6W1H classification to manifest files
#TODO: [P0-SCHEMA-GAPS] Filesync.py - Add security context (owner_uid, owner_gid, permissions)
#TODO: [P0-SCHEMA-GAPS] Filesync.py - Add content_analysis (is_text, imports, line_count)
#TODO: [P0-SCHEMA-GAPS] onboarder.py - Add package dependency catalog (1600+ packages)
#TODO: [P0-SCHEMA-GAPS] onboarder.py - Link tool profiles to file_id for cross-reference
#TODO: [P0-SCHEMA-GAPS] onboarder.py - Add 6W1H capability classification per tool
#TODO: [P0-SCHEMA-GAPS] orchestrator.py - Add "which" dimension to 5W1H → make it 6W1H
#TODO: [P0-SCHEMA-GAPS] regex_project - Add "which" to master_regex.json patterns

#TODO: [P1-INTEGRATION] Use latest command to gain update_profiles() function
#TODO: [P1-INTEGRATION] Update existing /babel_data profiles with aligned schema
#TODO: [P1-INTEGRATION] Create --diff validator that detects schema misalignments
#TODO: [P1-INTEGRATION] Suggest actions for property alignment corrections
#TODO: [P1-INTEGRATION] Back-propagate coherence corrections across all 3 systems

#TODO: Integrate with regex_project/orchestrator.py for interactive UX
#TODO: Add live weight tuning mode with real-time suggestion updates
#TODO: Wrap session logs + live context for Morph chat about "Current-situation/Latest-state"
#TODO: Add --session flag support to load specific Os_Toolkit sessions
#TODO: Create dual-mode system: 1# Weight testing, 2# Morph state chat

#[Event:WEIGHT_TUNER_INIT] Module initialization with manifest loading
#[Event:PROPERTY_ATTRIBUTION_GAP] Schema alignment needed before coherent backpropagation

Purpose:
  - Avoid heavy system scans by loading existing manifest data
  - Iteratively tune action confidence weights
  - Validate with Morph regex patterns from regex_project
  - Preview suggestions with --diff mode (no execution)
  - Export corrected weights for Os_Toolkit consumption

Author: Babel Team
Created: 2026-02-10
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict


class ActionWeightTuner:
    """
    Iterative weight correction system for suggested actions

    Uses manifest data to tune confidence weights without triggering heavy scans.
    Integrates with Morph patterns for validation.
    """

    def __init__(self, babel_root: Path, manifest_path: Optional[Path] = None):
        """
        Initialize weight tuner

        Args:
            babel_root: Root Babel directory
            manifest_path: Optional specific manifest (defaults to latest)
        """
        self.babel_root = Path(babel_root)
        self.weights_file = self.babel_root / "babel_data/profile/action_weights.json"
        self.morph_weights_file = self.babel_root / "regex_project/format_weights.json"

        # Load manifest (use latest if not specified)
        if manifest_path is None:
            manifest_path = self._find_latest_manifest()

        self.manifest_path = manifest_path
        self.manifest = self._load_manifest()

        # Load weights
        self.weights = self._load_weights()
        self.morph_patterns = self._load_morph_patterns()

        # Track adjustments
        self.adjustment_history = []

    def _find_latest_manifest(self) -> Path:
        """Find most recent Filesync manifest"""
        manifest_dir = self.babel_root / "babel_data/timeline/manifests"
        manifests = sorted(manifest_dir.glob("manifest_*.json"),
                          key=lambda p: p.stat().st_mtime,
                          reverse=True)

        if not manifests:
            raise FileNotFoundError("No Filesync manifests found")

        return manifests[0]

    def _load_manifest(self) -> Dict:
        """Load Filesync manifest data"""
        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)

            print(f"[WEIGHT_TUNER] Loaded manifest: {self.manifest_path.name}")
            print(f"  Files: {manifest.get('metadata', {}).get('file_count', 0)}")
            print(f"  Generated: {manifest.get('metadata', {}).get('generated', 'unknown')}")

            return manifest
        except Exception as e:
            raise RuntimeError(f"Failed to load manifest: {e}")

    def _load_weights(self) -> Dict[str, float]:
        """Load action weights from profile or use defaults"""
        if self.weights_file.exists():
            try:
                with open(self.weights_file) as f:
                    data = json.load(f)

                # Handle both formats: direct dict or wrapped with metadata
                if 'weights' in data:
                    weights = data['weights']
                else:
                    weights = data

                print(f"[WEIGHT_TUNER] Loaded {len(weights)} weights from {self.weights_file}")
                return weights
            except Exception as e:
                print(f"[WEIGHT_TUNER] Error loading weights: {e}, using defaults")

        # Default weights (starting point)
        return {
            'backup_now': 0.85,
            'run_security': 0.80,
            'check_security': 0.80,
            'audit_workflow': 0.75,
            'sync_todos': 0.75,
            'view_conflicts': 0.70,
            'consolidate_plans': 0.50,
            'debug_file': 0.60,
            'fix_syntax': 0.70,
            'add_mark': 0.50,
            'update_memory': 0.60,
            'view_todos': 0.50,
            'classify_events': 0.50
        }

    def _load_morph_patterns(self) -> Dict:
        """Load Morph regex patterns for validation

        #TODO: Expand Morph pattern loading from regex_project/
        #TODO: Load level_2_morphology patterns for linguistic analysis
        #TODO: Load domain-specific patterns (academic, technical, informal)
        #TODO: Integrate with orchestrator.py pattern registry
        #[Event:MORPH_PATTERNS_LOAD] Loading Morph validation patterns
        """
        patterns = {}

        # Load format weights (Morph domain patterns)
        if self.morph_weights_file.exists():
            try:
                with open(self.morph_weights_file) as f:
                    morph_weights = json.load(f)
                patterns['format_weights'] = morph_weights
                print(f"[WEIGHT_TUNER] Loaded {len(morph_weights)} Morph format weights")
            except Exception as e:
                print(f"[WEIGHT_TUNER] Error loading Morph weights: {e}")

        #TODO: Load additional Morph pattern files from regex_project/
        # patterns['level_2_morphology'] = load_morphology_patterns()
        # patterns['domain_patterns'] = load_domain_patterns()
        # patterns['orchestrator_registry'] = load_orchestrator_patterns()

        return patterns

    def extract_context_from_manifest(self) -> Dict[str, Any]:
        """
        Extract actionable context from manifest without full scan

        Returns:
            Context dict with: scattered_plans, security_state, file_changes, etc.
        """
        context = {
            'scattered_plan_count': 0,
            'unassociated_md_files': 0,
            'top_level_md_files': 0,
            'nested_md_files': 0,
            'recent_file_changes': 0,
            'project_associations': {},
            'file_categories': defaultdict(int),
            'security_anomalies': False,
            'todo_conflicts': 0
        }

        files = self.manifest.get('files', {})

        for file_id, props in files.items():
            # Track .md files (plans)
            if props.get('extension') == '.md':
                context['scattered_plan_count'] += 1

                # Check project association
                if not props.get('project_association'):
                    context['unassociated_md_files'] += 1

                # Check depth
                depth = props.get('depth_from_root', 99)
                if depth == 1:
                    context['top_level_md_files'] += 1
                else:
                    context['nested_md_files'] += 1

            # Track file categories
            category = props.get('category', 'unknown')
            context['file_categories'][category] += 1

            # Check recent modifications (last 24h)
            mtime = props.get('modified_time', '')
            if mtime:
                try:
                    mod_dt = datetime.fromisoformat(mtime.replace('Z', '+00:00'))
                    if (datetime.now().astimezone() - mod_dt).total_seconds() < 86400:
                        context['recent_file_changes'] += 1
                except:
                    pass

        # Extract project associations
        projects = self.manifest.get('projects', {})
        for proj_id, proj_data in projects.items():
            context['project_associations'][proj_id] = proj_data.get('file_count', 0)

        return context

    def calculate_confidence(self, action_id: str, context: Dict[str, Any]) -> Tuple[float, str]:
        """
        Calculate confidence score for an action using current weights + context

        Args:
            action_id: Action identifier
            context: Manifest-derived context

        Returns:
            (confidence_score, reasoning)
        """
        base_weight = self.weights.get(action_id, 0.5)
        confidence = base_weight
        reasoning_parts = [f"Base: {base_weight:.2f}"]

        # PLAN CONSOLIDATION SCORING
        if 'consolidate' in action_id:
            scattered = context.get('scattered_plan_count', 0)
            unassociated = context.get('unassociated_md_files', 0)
            top_level = context.get('top_level_md_files', 0)

            if scattered > 50:
                confidence += 0.20
                reasoning_parts.append(f"+0.20 (50+ scattered plans)")
            elif scattered > 20:
                confidence += 0.15
                reasoning_parts.append(f"+0.15 (20+ scattered plans)")
            elif scattered > 10:
                confidence += 0.10
                reasoning_parts.append(f"+0.10 (10+ scattered plans)")

            if unassociated > 30:
                confidence += 0.10
                reasoning_parts.append(f"+0.10 (30+ unassociated)")

            if top_level > 15:
                confidence += 0.08
                reasoning_parts.append(f"+0.08 (15+ top-level .md)")

        # SECURITY ACTION SCORING
        elif 'security' in action_id:
            if context.get('security_anomalies', False):
                confidence += 0.10
                reasoning_parts.append(f"+0.10 (security anomalies)")

        # TODO SYNC SCORING
        elif 'sync' in action_id or 'conflict' in action_id:
            conflicts = context.get('todo_conflicts', 0)
            if conflicts > 10:
                confidence += 0.15
                reasoning_parts.append(f"+0.15 ({conflicts} conflicts)")
            elif conflicts > 5:
                confidence += 0.10
                reasoning_parts.append(f"+0.10 ({conflicts} conflicts)")
            elif conflicts > 0:
                confidence += 0.05
                reasoning_parts.append(f"+0.05 ({conflicts} conflicts)")

        # Clamp to valid range
        confidence = min(max(confidence, 0.4), 0.85)

        reasoning = " | ".join(reasoning_parts) + f" → {confidence:.2f}"
        return confidence, reasoning

    def preview_suggestions(self, context: Optional[Dict] = None) -> List[Dict]:
        """
        Generate action suggestions with current weights (--diff mode)

        Args:
            context: Optional context (extracts from manifest if None)

        Returns:
            List of suggestion dicts with confidence scores
        """
        if context is None:
            context = self.extract_context_from_manifest()

        suggestions = []

        # Generate suggestions for all tracked actions
        for action_id in self.weights.keys():
            confidence, reasoning = self.calculate_confidence(action_id, context)

            suggestions.append({
                'action_id': action_id,
                'confidence': confidence,
                'reasoning': reasoning,
                'priority': confidence + (0.2 if confidence >= 0.7 else 0)
            })

        # Sort by priority
        suggestions.sort(key=lambda x: x['priority'], reverse=True)

        return suggestions

    def adjust_weight(self, action_id: str, delta: float, reason: str = ""):
        """
        Adjust weight for specific action

        Args:
            action_id: Action to adjust
            delta: Change amount (e.g., +0.15, -0.05)
            reason: Optional reason for adjustment
        """
        old_weight = self.weights.get(action_id, 0.5)
        new_weight = min(max(old_weight + delta, 0.0), 1.0)

        self.weights[action_id] = new_weight

        # Track adjustment
        adjustment = {
            'action_id': action_id,
            'old_weight': old_weight,
            'new_weight': new_weight,
            'delta': delta,
            'reason': reason,
            'timestamp': datetime.now().isoformat()
        }
        self.adjustment_history.append(adjustment)

        print(f"[WEIGHT_TUNER] Adjusted {action_id}: {old_weight:.2f} → {new_weight:.2f} ({delta:+.2f})")
        if reason:
            print(f"  Reason: {reason}")

    def validate_with_morph(self, action_id: str, file_path: Optional[str] = None) -> Dict:
        """
        Validate action using Morph regex patterns

        #TODO: Deep Morph integration with orchestrator.py pattern engine
        #TODO: Cross-reference action context with linguistic patterns
        #TODO: Apply domain-specific weight corrections (academic vs technical vs informal)
        #TODO: Validate suggested actions against Morph confidence scoring
        #[Event:MORPH_VALIDATION] Validating action with Morph patterns

        Args:
            action_id: Action to validate
            file_path: Optional file to check patterns against

        Returns:
            Validation result with pattern matches
        """
        result = {
            'action_id': action_id,
            'valid': True,
            'patterns_matched': [],
            'confidence_adjustment': 0.0
        }

        # Check format weights from Morph
        format_weights = self.morph_patterns.get('format_weights', {})

        # Apply Morph-based corrections
        if 'user_correction' in format_weights:
            # User corrections have high weight (4.0 in Morph)
            result['confidence_adjustment'] = 0.15
            result['patterns_matched'].append('user_correction')

        #TODO: Add comprehensive Morph pattern matching logic
        #TODO: Match against level_2_morphology for linguistic structure
        #TODO: Apply domain pattern weights for context-aware scoring
        #TODO: Integrate orchestrator.py real-time pattern updates

        return result

    def validate_coherence(self, suggestions: List[Dict], session_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate suggested actions against ground truth (frozen state validation)

        #[Mark:P0-CoherenceValidator] Training mode - compare predictions to reality, NO execution
        #TODO: Integrate with Os_Toolkit session artifacts for ground truth
        #TODO: Add 6W1H attribute mapping to regex prefix weights
        #TODO: Implement parent weight confirmation for 100% correct predictions
        #TODO: Add back-propagation from coherence scores to layer weights
        #TODO: Validate against code-state file properties (syntax errors, security issues)
        #TODO: Cross-reference with Morph domain profiles for response tuning
        #[Event:COHERENCE_VALIDATION_START] Beginning frozen state validation

        Purpose:
          - Compare action suggestions to actual system state
          - Measure prediction accuracy without executing actions
          - Generate weight adjustment recommendations
          - Validate coherence between suggestions and plans/todos/code-state

        Args:
            suggestions: List of action suggestions with confidence scores
            session_data: Optional Os_Toolkit session for ground truth validation

        Returns:
            Validation report with accuracy scores and discrepancies
        """
        #[Event:COHERENCE_LOAD_GROUND_TRUTH] Loading ground truth from manifest + session

        # Extract ground truth context
        context = self.extract_context_from_manifest()

        # Load session ground truth if available
        ground_truth = {
            'scattered_plans': context['scattered_plan_count'],
            'unassociated_md': context['unassociated_md_files'],
            'top_level_md': context['top_level_md_files'],
            'recent_changes': context['recent_file_changes'],
            'file_categories': dict(context['file_categories']),
            'todo_conflicts': 0,  # Will be populated from session
            'syntax_errors': 0,   # Will be populated from session
            'security_issues': 0  # Will be populated from session
        }

        # Populate from session data if available
        if session_data:
            # Extract todos and conflicts
            todos = session_data.get('todos', [])
            ground_truth['active_todos'] = len(todos)

            # Count conflicts (todos marked with CONFLICT or multiple sources)
            #TODO: Implement actual conflict detection from todo metadata
            ground_truth['todo_conflicts'] = sum(1 for t in todos if 'conflict' in t.get('text', '').lower())

            # Extract plans
            plans = session_data.get('plans', [])
            ground_truth['active_plans'] = len(plans)

            # Extract file index for code-state validation
            file_index = session_data.get('file_index', {})

            # Count syntax errors from file properties
            #TODO: Integrate with Os_Toolkit file classification for actual syntax error detection
            for file_path, file_props in file_index.items():
                if file_props.get('category') == 'syntax_error':
                    ground_truth['syntax_errors'] += 1
                if file_props.get('security_risk', False):
                    ground_truth['security_issues'] += 1

        # Validation report
        validation_report = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'manifest_source': str(self.manifest_path),
                'session_source': session_data.get('metadata', {}).get('session_id', 'none') if session_data else 'none',
                'total_suggestions': len(suggestions),
                'schema_version': '1.0'
            },
            'ground_truth': ground_truth,
            'action_validations': [],
            'coherence_scores': {},
            'discrepancies': [],
            'weight_recommendations': []
        }

        #[Event:COHERENCE_VALIDATE_ACTIONS] Validating each suggested action

        # Validate each suggestion
        for suggestion in suggestions:
            action_id = suggestion['action_id']
            predicted_confidence = suggestion['confidence']

            validation = {
                'action_id': action_id,
                'predicted_confidence': predicted_confidence,
                'ground_truth_score': 0.0,
                'coherence_score': 0.0,
                'is_valid': False,
                'evidence': [],
                'discrepancies': []
            }

            # ACTION-SPECIFIC VALIDATION

            # CONSOLIDATE PLANS
            if 'consolidate' in action_id and 'plan' in action_id:
                scattered = ground_truth['scattered_plans']
                unassociated = ground_truth['unassociated_md']

                # Ground truth: Should suggest if scattered > 50 or unassociated > 30
                should_suggest = scattered > 50 or unassociated > 30

                if should_suggest:
                    validation['ground_truth_score'] = min(0.85, 0.5 + (scattered / 100) * 0.2)
                    validation['is_valid'] = True
                    validation['evidence'].append(f"{scattered} scattered plans detected")
                    validation['evidence'].append(f"{unassociated} unassociated .md files")
                else:
                    validation['ground_truth_score'] = 0.4
                    validation['evidence'].append(f"Only {scattered} scattered plans (threshold: 50)")

                # Calculate coherence (how close prediction matches ground truth)
                coherence = 1.0 - abs(predicted_confidence - validation['ground_truth_score'])
                validation['coherence_score'] = coherence

                # Flag discrepancies
                if abs(predicted_confidence - validation['ground_truth_score']) > 0.15:
                    discrepancy = {
                        'action_id': action_id,
                        'predicted': predicted_confidence,
                        'actual': validation['ground_truth_score'],
                        'delta': predicted_confidence - validation['ground_truth_score'],
                        'reason': f"Confidence mismatch: predicted {predicted_confidence:.2f} vs ground truth {validation['ground_truth_score']:.2f}"
                    }
                    validation['discrepancies'].append(discrepancy)
                    validation_report['discrepancies'].append(discrepancy)

            # SYNC TODOS
            elif 'sync' in action_id and 'todo' in action_id:
                conflicts = ground_truth.get('todo_conflicts', 0)

                # Ground truth: Should suggest if conflicts > 5
                should_suggest = conflicts > 5

                if should_suggest:
                    validation['ground_truth_score'] = min(0.85, 0.6 + (conflicts / 20) * 0.25)
                    validation['is_valid'] = True
                    validation['evidence'].append(f"{conflicts} todo conflicts detected")
                else:
                    validation['ground_truth_score'] = 0.5
                    validation['evidence'].append(f"Only {conflicts} conflicts (threshold: 5)")

                coherence = 1.0 - abs(predicted_confidence - validation['ground_truth_score'])
                validation['coherence_score'] = coherence

                if abs(predicted_confidence - validation['ground_truth_score']) > 0.15:
                    validation['discrepancies'].append({
                        'action_id': action_id,
                        'predicted': predicted_confidence,
                        'actual': validation['ground_truth_score'],
                        'delta': predicted_confidence - validation['ground_truth_score']
                    })

            # FIX SYNTAX
            elif 'syntax' in action_id:
                syntax_errors = ground_truth.get('syntax_errors', 0)

                should_suggest = syntax_errors > 0

                if should_suggest:
                    validation['ground_truth_score'] = min(0.85, 0.6 + (syntax_errors / 10) * 0.25)
                    validation['is_valid'] = True
                    validation['evidence'].append(f"{syntax_errors} syntax errors detected")
                else:
                    validation['ground_truth_score'] = 0.4
                    validation['evidence'].append("No syntax errors detected")

                coherence = 1.0 - abs(predicted_confidence - validation['ground_truth_score'])
                validation['coherence_score'] = coherence

                # Flag discrepancies for syntax actions
                if abs(predicted_confidence - validation['ground_truth_score']) > 0.15:
                    discrepancy = {
                        'action_id': action_id,
                        'predicted': predicted_confidence,
                        'actual': validation['ground_truth_score'],
                        'delta': predicted_confidence - validation['ground_truth_score'],
                        'reason': f"Syntax confidence mismatch: predicted {predicted_confidence:.2f} vs ground truth {validation['ground_truth_score']:.2f}"
                    }
                    validation['discrepancies'].append(discrepancy)
                    validation_report['discrepancies'].append(discrepancy)

            # SECURITY ACTIONS
            elif 'security' in action_id:
                security_issues = ground_truth.get('security_issues', 0)
                recent_changes = ground_truth.get('recent_changes', 0)

                # Should suggest if security issues OR recent changes in last 24h
                should_suggest = security_issues > 0 or recent_changes > 10

                if should_suggest:
                    validation['ground_truth_score'] = 0.8
                    validation['is_valid'] = True
                    if security_issues > 0:
                        validation['evidence'].append(f"{security_issues} security issues detected")
                    if recent_changes > 10:
                        validation['evidence'].append(f"{recent_changes} recent file changes")
                else:
                    validation['ground_truth_score'] = 0.6
                    validation['evidence'].append("No security issues or recent changes")

                coherence = 1.0 - abs(predicted_confidence - validation['ground_truth_score'])
                validation['coherence_score'] = coherence

                # Flag discrepancies for security actions
                if abs(predicted_confidence - validation['ground_truth_score']) > 0.15:
                    discrepancy = {
                        'action_id': action_id,
                        'predicted': predicted_confidence,
                        'actual': validation['ground_truth_score'],
                        'delta': predicted_confidence - validation['ground_truth_score'],
                        'reason': f"Security confidence mismatch: predicted {predicted_confidence:.2f} vs ground truth {validation['ground_truth_score']:.2f}"
                    }
                    validation['discrepancies'].append(discrepancy)
                    validation_report['discrepancies'].append(discrepancy)

            # DEFAULT: Assume suggestion is contextually appropriate
            else:
                validation['ground_truth_score'] = predicted_confidence
                validation['coherence_score'] = 1.0
                validation['is_valid'] = True
                validation['evidence'].append("No specific ground truth validation available")

            validation_report['action_validations'].append(validation)

        #[Event:COHERENCE_CALCULATE_SCORES] Calculating overall coherence scores

        # Calculate overall coherence scores
        total_coherence = sum(v['coherence_score'] for v in validation_report['action_validations'])
        avg_coherence = total_coherence / len(suggestions) if suggestions else 0.0

        validation_report['coherence_scores'] = {
            'average_coherence': avg_coherence,
            'total_validations': len(suggestions),
            'valid_suggestions': sum(1 for v in validation_report['action_validations'] if v['is_valid']),
            'discrepancy_count': len(validation_report['discrepancies']),
            'accuracy_pct': (sum(1 for v in validation_report['action_validations'] if v['coherence_score'] > 0.85) / len(suggestions) * 100) if suggestions else 0.0
        }

        #[Event:COHERENCE_GENERATE_RECOMMENDATIONS] Generating weight adjustment recommendations

        # Generate weight adjustment recommendations
        #TODO: Implement parent weight confirmation - if 100% correct, strengthen core algorithm
        for discrepancy in validation_report['discrepancies']:
            action_id = discrepancy['action_id']
            delta = discrepancy['delta']

            # Recommend weight adjustment
            recommended_adjustment = -delta * 0.5  # Adjust by half the discrepancy

            recommendation = {
                'action_id': action_id,
                'current_weight': self.weights.get(action_id, 0.5),
                'recommended_delta': recommended_adjustment,
                'new_weight': min(max(self.weights.get(action_id, 0.5) + recommended_adjustment, 0.0), 1.0),
                'reason': f"Coherence gap: {abs(delta):.2f} (predicted too {'high' if delta > 0 else 'low'})"
            }

            validation_report['weight_recommendations'].append(recommendation)

        #[Event:COHERENCE_VALIDATION_COMPLETE] Coherence validation complete

        return validation_report

    def apply_coherence_recommendations(self, validation_report: Dict[str, Any], auto_apply: bool = False):
        """
        Apply weight recommendations from coherence validation

        #[Mark:P0-WeightBackPropagation] Back-propagate coherence corrections to weights
        #TODO: Add confirmation threshold for auto-apply (e.g., only if coherence > 90%)
        #TODO: Track recommendation history for learning velocity
        #TODO: Implement parent weight confirmation for high-accuracy predictions
        #[Event:WEIGHT_BACKPROP_START] Applying coherence-based weight corrections

        Args:
            validation_report: Coherence validation report
            auto_apply: If True, apply recommendations without confirmation
        """
        recommendations = validation_report.get('weight_recommendations', [])

        if not recommendations:
            print("[COHERENCE] No weight adjustments recommended")
            return

        print(f"\n[COHERENCE] {len(recommendations)} weight adjustment recommendations")
        print("=" * 80)

        for rec in recommendations:
            action_id = rec['action_id']
            current = rec['current_weight']
            delta = rec['recommended_delta']
            new_weight = rec['new_weight']
            reason = rec['reason']

            print(f"\nAction: {action_id}")
            print(f"  Current: {current:.2f} → Recommended: {new_weight:.2f} (Δ {delta:+.2f})")
            print(f"  Reason: {reason}")

            if auto_apply:
                self.adjust_weight(action_id, delta, reason=f"Coherence validation: {reason}")
                print(f"  ✓ Applied")
            else:
                print(f"  (Use --apply-recommendations to apply)")

        print("=" * 80)
        print()

        #[Event:WEIGHT_BACKPROP_COMPLETE] Weight back-propagation complete

    def export_weights(self, output_path: Optional[Path] = None):
        """
        Export corrected weights to JSON

        Args:
            output_path: Optional custom path (defaults to profile/action_weights.json)
        """
        if output_path is None:
            output_path = self.weights_file

        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            'metadata': {
                'generated': datetime.now().isoformat(),
                'manifest_source': str(self.manifest_path),
                'adjustment_count': len(self.adjustment_history),
                'schema_version': '1.0'
            },
            'weights': self.weights,
            'adjustment_history': self.adjustment_history
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        print(f"[WEIGHT_TUNER] Exported weights to: {output_path}")
        print(f"  Total weights: {len(self.weights)}")
        print(f"  Adjustments: {len(self.adjustment_history)}")

    def display_comparison(self, old_suggestions: List[Dict], new_suggestions: List[Dict]):
        """Display side-by-side comparison of suggestion changes"""
        print("\n" + "="*80)
        print("WEIGHT ADJUSTMENT COMPARISON")
        print("="*80)

        # Create lookup for old suggestions
        old_lookup = {s['action_id']: s for s in old_suggestions}

        for new_sugg in new_suggestions[:10]:  # Top 10
            action_id = new_sugg['action_id']
            old_sugg = old_lookup.get(action_id, {})

            old_conf = old_sugg.get('confidence', 0.0)
            new_conf = new_sugg['confidence']
            delta = new_conf - old_conf

            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "="

            print(f"\n{action_id}")
            print(f"  Old: {old_conf:.2f} → New: {new_conf:.2f} ({arrow} {delta:+.2f})")
            print(f"  Reasoning: {new_sugg['reasoning']}")


def main():
    """CLI interface for weight tuner"""
    import argparse

    parser = argparse.ArgumentParser(description="Babel Weight Tuner")
    parser.add_argument('--babel-root', default='.',
                       help='Babel root directory')
    parser.add_argument('--manifest',
                       help='Specific manifest path (defaults to latest)')
    parser.add_argument('--diff', action='store_true',
                       help='Preview suggestions with current weights')
    parser.add_argument('--adjust', nargs=2, metavar=('ACTION', 'DELTA'),
                       help='Adjust weight: --adjust consolidate_plans +0.15')
    parser.add_argument('--export', action='store_true',
                       help='Export corrected weights')

    # Coherence Validation (Training Mode)
    parser.add_argument('--validate', action='store_true',
                       help='Validate action coherence against ground truth (frozen state)')
    parser.add_argument('--session', metavar='SESSION_ID',
                       help='Os_Toolkit session for ground truth validation')
    parser.add_argument('--apply-recommendations', action='store_true',
                       help='Auto-apply weight recommendations from coherence validation')

    args = parser.parse_args()

    # Initialize tuner
    babel_root = Path(args.babel_root)
    manifest_path = Path(args.manifest) if args.manifest else None

    tuner = ActionWeightTuner(babel_root, manifest_path)

    # Extract context
    context = tuner.extract_context_from_manifest()

    print(f"\n[CONTEXT]")
    print(f"  Scattered plans: {context['scattered_plan_count']}")
    print(f"  Unassociated .md: {context['unassociated_md_files']}")
    print(f"  Recent changes: {context['recent_file_changes']}")
    print(f"  Projects: {len(context['project_associations'])}")

    # Handle commands
    if args.diff:
        suggestions = tuner.preview_suggestions(context)

        print(f"\n[SUGGESTED ACTIONS] (Current weights)")
        print("="*80)
        for i, sugg in enumerate(suggestions[:15], 1):
            conf_level = "HIGH" if sugg['confidence'] >= 0.7 else "MED" if sugg['confidence'] >= 0.5 else "LOW"
            print(f"{i}. [{sugg['confidence']:.2f}] {conf_level:4s} - {sugg['action_id']}")
            print(f"   {sugg['reasoning']}")

    if args.adjust:
        action_id, delta_str = args.adjust
        delta = float(delta_str)
        tuner.adjust_weight(action_id, delta)

        # Show updated suggestions
        suggestions = tuner.preview_suggestions(context)
        print(f"\n[UPDATED SUGGESTIONS]")
        for sugg in suggestions[:5]:
            if sugg['action_id'] == action_id:
                print(f"  {action_id}: {sugg['confidence']:.2f}")
                print(f"  {sugg['reasoning']}")

    if args.export:
        tuner.export_weights()

    # Coherence Validation (Training Mode)
    #[Event:CLI_COHERENCE_VALIDATION] Executing coherence validation from CLI
    if args.validate:
        # Load Os_Toolkit session for ground truth
        session_data = None
        if args.session:
            session_dir = babel_root / f"babel_data/profile/sessions/{args.session}"
            if session_dir.exists():
                try:
                    # Load session metadata
                    metadata_file = session_dir / "metadata.json"
                    artifacts_file = session_dir / "artifacts.json"

                    with open(metadata_file) as f:
                        metadata = json.load(f)

                    artifacts = {}
                    if artifacts_file.exists():
                        with open(artifacts_file) as f:
                            artifacts = json.load(f)

                    session_data = {
                        'metadata': metadata,
                        'file_index': artifacts.get('file_profiles', {}),
                        'todos': list(artifacts.get('todo_index', {}).values()),
                        'plans': list(artifacts.get('plan_index', {}).values())
                    }

                    print(f"[SESSION] Loaded: {args.session}")
                    print(f"  Files: {len(session_data['file_index'])}")
                    print(f"  Todos: {len(session_data['todos'])}")
                    print(f"  Plans: {len(session_data['plans'])}")
                    print()
                except Exception as e:
                    print(f"[ERROR] Failed to load session {args.session}: {e}")
                    session_data = None
            else:
                print(f"[ERROR] Session not found: {session_dir}")
        else:
            # Try to find latest session
            sessions_dir = babel_root / "babel_data/profile/sessions"
            if sessions_dir.exists():
                session_dirs = sorted(sessions_dir.glob("babel_catalog_*"),
                                    key=lambda p: p.stat().st_mtime,
                                    reverse=True)
                if session_dirs:
                    latest_session = session_dirs[0]
                    print(f"[INFO] Using latest session: {latest_session.name}")
                    # Load it (same code as above)
                    try:
                        metadata_file = latest_session / "metadata.json"
                        artifacts_file = latest_session / "artifacts.json"

                        with open(metadata_file) as f:
                            metadata = json.load(f)

                        artifacts = {}
                        if artifacts_file.exists():
                            with open(artifacts_file) as f:
                                artifacts = json.load(f)

                        session_data = {
                            'metadata': metadata,
                            'file_index': artifacts.get('file_profiles', {}),
                            'todos': list(artifacts.get('todo_index', {}).values()),
                            'plans': list(artifacts.get('plan_index', {}).values())
                        }
                        print(f"  Files: {len(session_data['file_index'])}")
                        print(f"  Todos: {len(session_data['todos'])}")
                        print(f"  Plans: {len(session_data['plans'])}")
                        print()
                    except Exception as e:
                        print(f"[WARNING] Could not load latest session: {e}")

        # Generate suggestions
        suggestions = tuner.preview_suggestions(context)

        # Validate coherence
        print("\n[COHERENCE VALIDATION] Training mode - frozen state comparison")
        print("=" * 80)
        validation_report = tuner.validate_coherence(suggestions, session_data)

        # Display validation results
        scores = validation_report['coherence_scores']
        print(f"\nCoherence Scores:")
        print(f"  Average coherence: {scores['average_coherence']:.2%}")
        print(f"  Accuracy (>85%):   {scores['accuracy_pct']:.1f}%")
        print(f"  Valid suggestions: {scores['valid_suggestions']}/{scores['total_validations']}")
        print(f"  Discrepancies:     {scores['discrepancy_count']}")

        # Show sample validations
        print("\n[VALIDATION DETAILS] (Top 5)")
        print("=" * 80)
        for i, val in enumerate(validation_report['action_validations'][:5], 1):
            status = "✓" if val['is_valid'] else "✗"
            print(f"{i}. [{status}] {val['action_id']}")
            print(f"   Predicted: {val['predicted_confidence']:.2f} | Ground truth: {val['ground_truth_score']:.2f} | Coherence: {val['coherence_score']:.2%}")
            for evidence in val['evidence'][:2]:
                print(f"   - {evidence}")

        # Show discrepancies
        if validation_report['discrepancies']:
            print("\n[DISCREPANCIES] Actions with coherence gaps")
            print("=" * 80)
            for disc in validation_report['discrepancies']:
                print(f"  {disc['action_id']}: {disc['predicted']:.2f} vs {disc['actual']:.2f} (Δ {disc['delta']:+.2f})")
                print(f"    {disc['reason']}")

        # Apply recommendations if requested
        tuner.apply_coherence_recommendations(validation_report, auto_apply=args.apply_recommendations)

        print("\n[COHERENCE] Validation complete")
        print("=" * 80)
        print()


if __name__ == '__main__':
    main()
