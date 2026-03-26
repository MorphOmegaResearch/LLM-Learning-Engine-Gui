"""
CLIChangeTracker — inject enriched_change events from CLI/non-GUI sessions
into version_manifest.json so that Os_Toolkit explain can see them.

The GUI registers file changes via interactive_trainer_gui_NEW.py → register_event().
CLI edits (Claude Code, terminal editors, scripts) bypass this path entirely,
making them invisible to the explain system. This class closes that gap.

Usage (programmatic):
  from cli_change_tracker import CLIChangeTracker
  from pathlib import Path
  tracker = CLIChangeTracker(Path('/home/commander/Trainer'))
  event_id = tracker.record_change(
      file_path='regex_project/activities/tools/scripts/omega_bridge.py',
      verb='modify',
      methods=['explain_period', 'get_debug_records'],
      task_ids=['task_morph_l4'],
      risk_level='LOW',
      description='Added explain_period() + SELF_EXPLAIN record type',
  )
  print('Recorded:', event_id)

Usage (CLI via Os_Toolkit.py):
  python3 Os_Toolkit.py track --file omega_bridge.py \\
      --verb modify --methods "explain_period,get_debug_records" \\
      --task task_morph_l4 --risk LOW --desc "Added explain_period"

Event ID format: CLI_{YYYYMMDD_HHMMSS}_{4hex}
Source field: "cli" (distinguishable from GUI-generated events)
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class CLIChangeTracker:
    """
    Append enriched_change events to version_manifest.json.
    Uses the same 28-field schema as GUI-generated events so
    TemporalNarrativeEngine and Os_Toolkit explain can process them.
    """

    def __init__(self, trainer_root: Path):
        self._trainer_root = Path(trainer_root)
        self._vm_path = self._trainer_root / 'Data' / 'backup' / 'version_manifest.json'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_change(
        self,
        file_path: str,
        verb: str = 'modify',
        methods: Optional[list[str]] = None,
        task_ids: Optional[list[str]] = None,
        risk_level: str = 'LOW',
        description: str = '',
        probe_status: str = 'PASS',
        additions: int = 0,
        deletions: int = 0,
        classes: Optional[list[str]] = None,
        imports_added: Optional[list[str]] = None,
    ) -> str:
        """
        Append a new enriched_change to version_manifest.json.

        Parameters
        ----------
        file_path : str
            Relative or absolute path to the changed file.
        verb : str
            add | modify | delete | fix | refactor | import
        methods : list[str], optional
            Method/function names affected.
        task_ids : list[str], optional
            Task IDs this change belongs to (e.g. ['task_morph_l4']).
        risk_level : str
            LOW | MEDIUM | HIGH | CRITICAL
        description : str
            Short human description of what changed.
        probe_status : str
            PASS | FAIL | WARN | NONE
        additions : int
            Lines added (approximate).
        deletions : int
            Lines deleted (approximate).
        classes : list[str], optional
            Class names affected.
        imports_added : list[str], optional
            New imports introduced.

        Returns
        -------
        str
            The generated event_id (e.g. "CLI_20260223_054501_a3f2").
        """
        now = datetime.now()
        event_id = f"CLI_{now.strftime('%Y%m%d_%H%M%S')}_{random.randint(0, 0xFFFF):04x}"

        # Resolve relative path to a canonical relative form
        abs_path = Path(file_path)
        if not abs_path.is_absolute():
            abs_path = (self._trainer_root / file_path).resolve()
        try:
            rel_path = str(abs_path.relative_to(self._trainer_root))
        except ValueError:
            rel_path = str(abs_path)

        # Infer feature from file stem (matches GUI convention)
        feature = abs_path.stem.replace('_', ' ').title()

        # Build the enriched_change record (same schema as GUI)
        record = {
            'event_id': event_id,
            'file': rel_path,
            'feature': feature,
            'verb': verb.lower(),
            'risk_level': risk_level.upper(),
            'risk_confidence': 0.7,
            'risk_reasons': [description] if description else [f'CLI {verb}'],
            'context_function': (methods[0] if methods else ''),
            'context_class': (classes[0] if classes else ''),
            'classes': classes or [],
            'methods': methods or [],
            'imports_added': imports_added or [],
            'additions': additions,
            'deletions': deletions,
            'before_after_values': [],
            'task_ids': task_ids or [],
            'probe_status': probe_status.upper(),
            'probe_errors': [],
            'blame_event': None,
            'test_status': None,
            'test_errors': [],
            'timestamp': now.isoformat(),
            'source': 'cli',            # distinguishes CLI from GUI events
            'description': description,
        }

        self._append_to_manifest(event_id, record)
        return event_id

    def record_session(self, phase: str, files: list[dict]) -> list[str]:
        """
        Record multiple file changes at once for a whole session.

        Parameters
        ----------
        phase : str
            Phase label, e.g. 'Phase L'
        files : list[dict]
            Each dict: {file, verb, methods, task_ids, risk_level, description}

        Returns
        -------
        list[str]
            Generated event IDs.
        """
        event_ids = []
        for f in files:
            eid = self.record_change(
                file_path=f.get('file', ''),
                verb=f.get('verb', 'modify'),
                methods=f.get('methods', []),
                task_ids=f.get('task_ids', []),
                risk_level=f.get('risk_level', 'LOW'),
                description=f.get('description', phase),
            )
            event_ids.append(eid)
        return event_ids

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append_to_manifest(self, event_id: str, record: dict) -> None:
        """Load version_manifest.json, append the record, save back."""
        vm: dict = {}
        if self._vm_path.exists():
            try:
                vm = json.loads(self._vm_path.read_text(encoding='utf-8'))
            except Exception:
                vm = {}

        if 'enriched_changes' not in vm or not isinstance(vm['enriched_changes'], dict):
            vm['enriched_changes'] = {}

        vm['enriched_changes'][event_id] = record

        # Write back — preserve original formatting style (4-space indent)
        self._vm_path.write_text(
            json.dumps(vm, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
