"""
GroundedSuggestEngine — unified suggestion engine with temporal + grounded context.

Wraps Os_Toolkit's SuggestiveGrepEngine and enriches its suggestions with:
  - OsToolkitGroundingBridge: recent_changes, probe_failures, gap_severity
  - TemporalNarrativeEngine: current phase, dominant_domain, active tasks
  - INIT_CHAIN awareness: surface init-chain trace action when relevant
  - Domain-biased extras: different actions for meta_learning vs knowledge_engineering

Used by:
  - Os_Toolkit.py `suggest` subcommand (replaces bare SuggestiveGrepEngine)
  - orchestrator.py morph-chat `suggest` command
  - (future) ag_knowledge search bar direct call

Usage:
  from grounded_suggest_engine import GroundedSuggestEngine
  from pathlib import Path
  engine = GroundedSuggestEngine(Path('/home/commander/Trainer'))
  suggestions = engine.suggest("omega_bridge.py")
  print(json.dumps(suggestions, indent=2))
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# INIT_CHAIN — tab files that have a known init order
# ---------------------------------------------------------------------------

_INIT_CHAIN_FILES = {
    'logger_util.py', 'logger_util',
    'interactive_trainer_gui_NEW.py',
    'training_tab.py', 'models_tab.py', 'settings_tab.py',
    'custom_code_tab.py', 'digital_biosphere_visualizer.py',
    'ag_forge_tab.py', 'planner_tab.py',
}

# Domain → extra suggestion labels
_DOMAIN_EXTRAS: dict[str, list[dict]] = {
    'meta_learning': [
        {
            'id': 'spawn_variant',
            'label': '🤖 Spawn Morph variant',
            'command': "python3 regex_project/orchestrator.py --spawn-variant",
            'selected': False,
        },
        {
            'id': 'export_debug',
            'label': '📦 Export SELF_DEBUG records',
            'command': "python3 regex_project/orchestrator.py --morph-chat",
            'selected': False,
        },
    ],
    'pattern_recognition': [
        {
            'id': 'export_cdals',
            'label': '📊 Export CDALS state',
            'command': "python3 regex_project/orchestrator.py --morph-chat",
            'selected': False,
        },
    ],
    'knowledge_engineering': [
        {
            'id': 'search_kf',
            'label': '🔍 Search Knowledge Forge',
            'command': "echo 'Open ag_knowledge tab → Knowledge Forge'",
            'selected': False,
        },
    ],
    'technical': [
        {
            'id': 'profile_classes',
            'label': '📊 Profile classes',
            'command': "python3 Os_Toolkit.py suggest --context file",
            'selected': False,
        },
        {
            'id': 'run_linter',
            'label': '🧪 Run linter (ruff)',
            'command': "python3 -m ruff check .",
            'selected': False,
        },
    ],
    'model_management': [
        {
            'id': 'check_gguf',
            'label': '🗂️ Check GGUF exports',
            'command': "ls -lh Models/Morph0.1-10m-Babble/exports/gguf/",
            'selected': False,
        },
    ],
}


class GroundedSuggestEngine:
    """
    Single grounded suggestion engine. Combines:
      1. Grounded context from OsToolkitGroundingBridge (probe failures, gap_severity)
      2. Temporal narrative from TemporalNarrativeEngine (phase, domain, active tasks)
      3. File-heuristic base suggestions from Os_Toolkit's SuggestiveGrepEngine (when available)
      4. INIT_CHAIN detection (surface trace action for init-critical files)
      5. Domain-biased extra suggestions
    """

    _NARRATIVE_CACHE_MINUTES = 10

    def __init__(self, trainer_root: Path):
        self._trainer_root = trainer_root
        self._grounded: dict | None = None
        self._narrative: dict | None = None
        self._narrative_loaded_at: datetime | None = None

    # ------------------------------------------------------------------
    # Context loading (lazy, cached)
    # ------------------------------------------------------------------

    def load_context(self, force: bool = False) -> None:
        """Load grounded_ctx + narrative snapshot. Narrative cached 10 min."""
        self._load_grounded()
        self._load_narrative(force=force)

    def _load_grounded(self) -> None:
        try:
            _scripts = Path(__file__).parent
            if str(_scripts) not in sys.path:
                sys.path.insert(0, str(_scripts))
            from activity_integration_bridge import OsToolkitGroundingBridge
            self._grounded = OsToolkitGroundingBridge(self._trainer_root).load()
        except Exception as e:
            self._grounded = {'gap_severity': 'unknown', 'probe_failures': [], 'recent_changes': []}

    def _load_narrative(self, force: bool = False) -> None:
        now = datetime.now()
        if (not force and self._narrative is not None and self._narrative_loaded_at is not None
                and (now - self._narrative_loaded_at).total_seconds() < self._NARRATIVE_CACHE_MINUTES * 60):
            return
        try:
            from temporal_narrative_engine import TemporalNarrativeEngine
            self._narrative = TemporalNarrativeEngine(self._trainer_root).explain('last 24h')
            self._narrative_loaded_at = now
        except Exception:
            self._narrative = {
                'phase_summary': 'unknown', 'dominant_domain': 'unknown',
                'domain_confidence': 0.0, 'tasks_active': [], 'files_touched': [],
            }
            self._narrative_loaded_at = now

    # ------------------------------------------------------------------
    # Main suggest method
    # ------------------------------------------------------------------

    def suggest(
        self,
        query: str = '',
        artifact: dict | None = None,
        filepath: str | None = None,
    ) -> list[dict]:
        """
        Return enriched action list.

        Order:
          1. Base SuggestiveGrepEngine suggestions (file-heuristic)
          2. Probe failure actions (from grounded_ctx)
          3. INIT_CHAIN action (if file is init-critical)
          4. Explain action (if no recent narrative)
          5. Domain extras (meta_learning / knowledge_engineering / technical / …)
          6. Active task link (if active task wherein matches query)
        """
        if self._grounded is None:
            self.load_context()

        suggestions: list[dict] = []

        # 1. Base file-heuristic suggestions from SuggestiveGrepEngine
        suggestions.extend(self._base_suggestions(query, artifact, filepath))

        # 2. Probe failures → diagnose action
        suggestions.extend(self._probe_failure_actions())

        # 3. INIT_CHAIN file → trace action
        if filepath:
            stem = Path(filepath).name
            if stem in _INIT_CHAIN_FILES or Path(filepath).stem in _INIT_CHAIN_FILES:
                suggestions.append({
                    'id': 'init_chain_trace',
                    'label': f'🔗 Trace init chain impact for {Path(filepath).name}',
                    'command': f"python3 Os_Toolkit.py explain --init-chain {filepath}",
                    'selected': False,
                })

        # 4. Explain action if narrative is stale / empty
        suggestions.extend(self._explain_action())

        # 5. Domain-biased extras
        suggestions.extend(self._domain_extras())

        # 6. Active task link
        suggestions.extend(self._active_task_action(query, filepath))

        return suggestions

    # ------------------------------------------------------------------
    # Sub-builders
    # ------------------------------------------------------------------

    def _base_suggestions(self, query: str, artifact: dict | None, filepath: str | None) -> list[dict]:
        """Try to get SuggestiveGrepEngine suggestions; fall back gracefully."""
        try:
            # Os_Toolkit.py is one level up from regex_project/
            ostk_dir = self._trainer_root / 'Data' / 'tabs' / 'action_panel_tab'
            if str(ostk_dir) not in sys.path:
                sys.path.insert(0, str(ostk_dir))
            from Os_Toolkit import SuggestiveGrepEngine  # type: ignore
            if artifact and filepath:
                return SuggestiveGrepEngine.suggest_for_file_query(artifact, filepath)
        except Exception:
            pass
        return []

    def _probe_failure_actions(self) -> list[dict]:
        actions: list[dict] = []
        if not self._grounded:
            return actions
        failures = self._grounded.get('probe_failures', [])
        for f in failures[:3]:
            fname = Path(f.get('file', '?')).name
            actions.append({
                'id': f'diagnose_{fname}',
                'label': f'🔍 Diagnose probe failure: {fname}',
                'command': f"python3 regex_project/orchestrator.py --morph-chat",
                'selected': False,
            })
        return actions

    def _explain_action(self) -> list[dict]:
        """Prepend 'Explain last 24h' if no recent narrative or narrative shows no files."""
        nar = self._narrative or {}
        has_files = bool(nar.get('files_touched'))
        if not has_files:
            return [{
                'id': 'explain_now',
                'label': '📖 Explain last 24h',
                'command': "python3 Os_Toolkit.py explain --since 'last 24h'",
                'selected': not has_files,
            }]
        return []

    def _domain_extras(self) -> list[dict]:
        nar = self._narrative or {}
        domain = nar.get('dominant_domain', 'unknown')
        return _DOMAIN_EXTRAS.get(domain, [])

    def _active_task_action(self, query: str, filepath: str | None) -> list[dict]:
        """If narrative active tasks have a matching wherein, suggest linking."""
        nar = self._narrative or {}
        tasks = nar.get('tasks_active', [])
        target = filepath or query
        for t in tasks[:3]:
            tid = t.get('id', '')
            if tid and target:
                return [{
                    'id': 'link_task',
                    'label': f'📋 Link to active task {tid}',
                    'command': f"python3 Os_Toolkit.py track --file \"{target}\" --task {tid}",
                    'selected': False,
                }]
        return []

    # ------------------------------------------------------------------
    # Phase / domain summary (for morph-chat display)
    # ------------------------------------------------------------------

    def phase_summary(self) -> str:
        if self._narrative is None:
            self._load_narrative()
        return (self._narrative or {}).get('phase_summary', 'unknown')

    def dominant_domain(self) -> str:
        if self._narrative is None:
            self._load_narrative()
        return (self._narrative or {}).get('dominant_domain', 'unknown')

    def gap_severity(self) -> str:
        if self._grounded is None:
            self._load_grounded()
        return (self._grounded or {}).get('gap_severity', 'unknown')
