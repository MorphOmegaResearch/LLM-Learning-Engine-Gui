"""
TemporalNarrativeEngine — explain what was worked on in any time window.

Data sources (all read-only):
  - Data/backup/version_manifest.json          → enriched_changes (timestamped file events)
  - babel_data/timeline/manifests/*.json        → file activity profiles (first_seen, activity_score)
  - forekit_data/sessions/*/journal.jsonl       → session-level event timeline
  - regex_project/interaction_logs.json         → orchestrator interaction history
  - Data/plans/todos.json                       → task phase/status data
  - Data/plans/Tasks/task_context_{tid}.json    → per-task context snapshots

Usage:
  from temporal_narrative_engine import TemporalNarrativeEngine
  from pathlib import Path
  engine = TemporalNarrativeEngine(Path('/home/commander/Trainer'))
  result = engine.explain(since='yesterday')
  print(result['narrative'])

CLI (via Os_Toolkit.py explain):
  python3 Os_Toolkit.py explain --since "2026-02-21"
  python3 Os_Toolkit.py explain --last 48h --format json
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now()


def _parse_iso(s: str) -> datetime | None:
    """Parse ISO 8601 string → datetime (naive, local time)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00').split('+')[0])
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# TemporalNarrativeEngine
# ---------------------------------------------------------------------------

class TemporalNarrativeEngine:
    """Synthesise a human-readable narrative of recent work from stored data."""

    # Where to persist the last-explain timestamp for --incremental queries
    LAST_EXPLAIN_FILE = '.last_explain_ts'

    def __init__(self, trainer_root: Path):
        self.trainer_root = trainer_root
        self._action_panel = trainer_root / 'Data' / 'tabs' / 'action_panel_tab'
        self._forekit = trainer_root / 'forekit_data'

        # Lazy-loaded caches
        self._enriched_changes: dict | None = None
        self._temporal_profiles: dict | None = None
        self._todos: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain(
        self,
        since: 'datetime | str | None' = None,
        until: 'datetime | str | None' = None,
        incremental: bool = False,
        format: str = 'text',
    ) -> dict:
        """
        Build a narrative dict for the given time window.

        Parameters
        ----------
        since : str | datetime | None
            Natural language ("yesterday", "last 24h", "phase-j") or ISO date.
            Defaults to last 24 hours.
        until : str | datetime | None
            End of window. Defaults to now.
        incremental : bool
            If True, use the last-explain timestamp as `since`.
        format : str
            Output hint ('text', 'json', 'morph-jsonl') — affects narrative_text style.

        Returns
        -------
        dict with keys:
            period, files_touched, tasks_active, phase_summary,
            risk_events, probe_chain, session_highlights, narrative
        """
        now = _utcnow()

        if incremental:
            since = self._load_last_explain_ts() or (now - timedelta(hours=24))

        since_dt = self._parse_date(since, now) if since else now - timedelta(hours=24)
        until_dt = self._parse_date(until, now) if until else now

        events = self._filter_events_by_range(since_dt, until_dt)
        files_touched = self._build_files_touched(events)
        tasks_active = self._build_tasks_active(events)
        phase_summary = self._infer_phase_label(events, tasks_active)
        risk_events = self._extract_risk_events(events)
        probe_chain = self._build_probe_chain(events)
        session_highlights = self._load_session_highlights(since_dt, until_dt)

        dominant_domain, domain_confidence = self._infer_dominant_domain(files_touched)

        result = {
            'period': {
                'since': since_dt.isoformat(),
                'until': until_dt.isoformat(),
                'label': phase_summary,
            },
            'files_touched': files_touched,
            'tasks_active': tasks_active,
            'phase_summary': phase_summary,
            'risk_events': risk_events,
            'probe_chain': probe_chain,
            'session_highlights': session_highlights,
            'dominant_domain': dominant_domain,
            'domain_confidence': domain_confidence,
            'narrative': '',
        }
        result['narrative'] = self._build_narrative_text(result)

        # Persist timestamp for next --incremental call
        self._save_last_explain_ts(until_dt)

        return result

    # ------------------------------------------------------------------
    # Date parsing
    # ------------------------------------------------------------------

    def _parse_date(self, s: 'str | datetime', now: datetime) -> datetime:
        """Parse natural language / ISO date string → datetime."""
        if isinstance(s, datetime):
            return s

        if not s:
            return now - timedelta(hours=24)

        s = s.strip().lower()

        # Natural language
        if s == 'yesterday':
            return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if s == 'today':
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if s in ('now', 'just now'):
            return now

        # "last Nh" or "last N days"
        m = re.match(r'^last\s+(\d+)\s*(h|hour|hours|d|day|days)$', s)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            return now - timedelta(hours=n if unit.startswith('h') else n * 24)

        # "Nh ago" or "Nd ago"
        m = re.match(r'^(\d+)\s*(h|hour|hours|d|day|days)\s+ago$', s)
        if m:
            n, unit = int(m.group(1)), m.group(2)
            return now - timedelta(hours=n if unit.startswith('h') else n * 24)

        # "phase-j", "phase-k" etc → lookup via task IDs in todos
        m = re.match(r'^phase[-_]?([a-z0-9]+)$', s)
        if m:
            phase_key = m.group(1).lower()
            phase_dt = self._infer_phase_start(phase_key)
            if phase_dt:
                return phase_dt

        # ISO date "2026-02-21" or "2026-02-21T10:00"
        try:
            if 'T' not in s.upper() and len(s) == 10:
                return datetime.fromisoformat(s)
            return datetime.fromisoformat(s)
        except ValueError:
            pass

        # Fallback: 24h ago
        return now - timedelta(hours=24)

    def _infer_phase_start(self, phase_key: str) -> datetime | None:
        """
        Look up todos for tasks matching phase_morph_{key}* and return
        the earliest timestamp found in enriched_changes for those tasks.
        """
        todos = self._load_todos()
        phase_block_key = f'phase_morph_{phase_key}'
        phase_block = todos.get(phase_block_key, {})
        if not phase_block:
            return None

        task_ids = list(phase_block.keys())
        changes = self._load_enriched_changes()
        timestamps = []
        for ev in changes.values():
            tids = ev.get('task_ids') or []
            if any(t in task_ids for t in tids):
                ts = _parse_iso(ev.get('timestamp', ''))
                if ts:
                    timestamps.append(ts)
        if timestamps:
            return min(timestamps)
        return None

    # ------------------------------------------------------------------
    # Data loading (lazy)
    # ------------------------------------------------------------------

    def _load_enriched_changes(self) -> dict:
        if self._enriched_changes is None:
            vm_path = self.trainer_root / 'Data' / 'backup' / 'version_manifest.json'
            if vm_path.exists():
                try:
                    vm = json.loads(vm_path.read_text())
                    self._enriched_changes = vm.get('enriched_changes', {})
                except Exception:
                    self._enriched_changes = {}
            else:
                self._enriched_changes = {}
        return self._enriched_changes

    def _load_temporal_profiles(self) -> dict:
        if self._temporal_profiles is None:
            manifest_path = (
                self._action_panel
                / 'babel_data' / 'timeline' / 'manifests'
                / 'history_temporal_manifest.json'
            )
            if manifest_path.exists():
                try:
                    d = json.loads(manifest_path.read_text())
                    self._temporal_profiles = d.get('profiles', {})
                except Exception:
                    self._temporal_profiles = {}
            else:
                self._temporal_profiles = {}
        return self._temporal_profiles

    def _load_todos(self) -> dict:
        if self._todos is None:
            todos_path = self.trainer_root / 'Data' / 'plans' / 'todos.json'
            if todos_path.exists():
                try:
                    self._todos = json.loads(todos_path.read_text())
                except Exception:
                    self._todos = {}
            else:
                self._todos = {}
        return self._todos

    def _load_interaction_logs(self) -> list:
        log_path = self._action_panel / 'regex_project' / 'interaction_logs.json'
        if log_path.exists():
            try:
                data = json.loads(log_path.read_text())
                return data if isinstance(data, list) else []
            except Exception:
                return []
        return []

    # ------------------------------------------------------------------
    # Filtering + grouping
    # ------------------------------------------------------------------

    def _filter_events_by_range(self, since: datetime, until: datetime) -> list[dict]:
        """Return enriched_change entries whose timestamp falls in [since, until]."""
        changes = self._load_enriched_changes()
        result = []
        for ev in changes.values():
            ts = _parse_iso(ev.get('timestamp', ''))
            if ts and since <= ts <= until:
                result.append(ev)
        # Sort by timestamp ascending
        result.sort(key=lambda e: e.get('timestamp', ''))
        return result

    def _build_files_touched(self, events: list[dict]) -> list[dict]:
        """Aggregate events by file into a per-file summary."""
        by_file: dict[str, dict] = {}
        for ev in events:
            file = ev.get('file', 'unknown')
            if file not in by_file:
                by_file[file] = {
                    'file': file,
                    'verbs': [],
                    'risk': 'LOW',
                    'tasks': [],
                    'methods': [],
                    'probe_status': ev.get('probe_status'),
                    'changes': 0,
                    'events': [],
                }
            entry = by_file[file]
            verb = ev.get('verb', '')
            if verb and verb not in entry['verbs']:
                entry['verbs'].append(verb)

            # Escalate risk
            risk = ev.get('risk_level', 'LOW')
            risk_rank = {'LOW': 0, 'MEDIUM': 1, 'HIGH': 2, 'CRITICAL': 3}
            if risk_rank.get(risk, 0) > risk_rank.get(entry['risk'], 0):
                entry['risk'] = risk

            for t in (ev.get('task_ids') or []):
                if t not in entry['tasks']:
                    entry['tasks'].append(t)

            for m in (ev.get('methods') or []):
                if m not in entry['methods']:
                    entry['methods'].append(m)

            entry['changes'] += 1
            entry['events'].append(ev.get('event_id', ''))

            # Latest probe status wins
            if ev.get('probe_status'):
                entry['probe_status'] = ev['probe_status']

        return sorted(by_file.values(), key=lambda x: x['changes'], reverse=True)

    def _build_tasks_active(self, events: list[dict]) -> list[dict]:
        """Aggregate events by task_id into a per-task summary."""
        todos = self._load_todos()
        by_task: dict[str, dict] = {}
        for ev in events:
            for tid in (ev.get('task_ids') or []):
                if tid not in by_task:
                    # Look up title + phase from todos
                    title, status, phase = self._lookup_task(tid, todos)
                    by_task[tid] = {
                        'id': tid,
                        'title': title,
                        'phase': phase,
                        'status': status,
                        'files_changed': 0,
                        'events': [],
                    }
                by_task[tid]['files_changed'] += 1
                eid = ev.get('event_id', '')
                if eid not in by_task[tid]['events']:
                    by_task[tid]['events'].append(eid)

        return sorted(by_task.values(), key=lambda x: x['files_changed'], reverse=True)

    def _lookup_task(self, tid: str, todos: dict) -> tuple[str, str, str]:
        """Return (title, status, phase) for a task ID across all phase blocks.
        Handles both dict-format ({tid: task}) and list-format ([{id, title...}]) phases.
        """
        for phase_key, phase_block in todos.items():
            if isinstance(phase_block, dict):
                if tid in phase_block:
                    task = phase_block[tid]
                    if isinstance(task, dict):
                        return (
                            task.get('title', tid),
                            task.get('status', 'UNKNOWN'),
                            phase_key,
                        )
            elif isinstance(phase_block, list):
                for task in phase_block:
                    if isinstance(task, dict) and task.get('id') == tid:
                        return (
                            task.get('title', tid),
                            task.get('status', 'UNKNOWN'),
                            phase_key,
                        )
        return (tid, 'UNKNOWN', 'unknown')

    def _extract_risk_events(self, events: list[dict]) -> list[dict]:
        """Return events with risk HIGH or CRITICAL."""
        out = []
        for ev in events:
            risk = ev.get('risk_level', 'LOW')
            if risk in ('HIGH', 'CRITICAL'):
                out.append({
                    'event_id': ev.get('event_id', ''),
                    'file': ev.get('file', ''),
                    'risk_level': risk,
                    'reasons': ev.get('risk_reasons', []),
                    'probe_status': ev.get('probe_status'),
                })
        return out

    def _build_probe_chain(self, events: list[dict]) -> list[dict]:
        """
        Detect FAIL → PASS resolution chains.
        A probe chain exists when the same file appears first with probe FAIL,
        then later with probe PASS.
        """
        by_file_status: dict[str, list[dict]] = defaultdict(list)
        for ev in events:
            ps = ev.get('probe_status')
            if ps in ('PASS', 'FAIL'):
                by_file_status[ev.get('file', '')].append(ev)

        chains = []
        for file, evs in by_file_status.items():
            fail_ev = next((e for e in evs if e.get('probe_status') == 'FAIL'), None)
            pass_ev = next((e for e in evs if e.get('probe_status') == 'PASS'), None)
            if fail_ev and pass_ev:
                fail_ts = _parse_iso(fail_ev.get('timestamp', ''))
                pass_ts = _parse_iso(pass_ev.get('timestamp', ''))
                if fail_ts and pass_ts and fail_ts < pass_ts:
                    chains.append({
                        'file': file,
                        'fail_event': fail_ev.get('event_id', ''),
                        'pass_event': pass_ev.get('event_id', ''),
                        'resolved_by': pass_ev.get('user', 'unknown'),
                    })
        return chains

    # ------------------------------------------------------------------
    # Session journals
    # ------------------------------------------------------------------

    def _load_session_highlights(self, since: datetime, until: datetime) -> list[dict]:
        """Scan session journals for entries in the time window."""
        highlights = []
        sessions_dir = self._forekit / 'sessions'
        if not sessions_dir.exists():
            return highlights

        interesting_types = {'command_exec', 'action_start', 'action_complete',
                             'file_analyzed', 'session_start', 'session_end'}

        for session_dir in sorted(sessions_dir.iterdir()):
            journal_path = session_dir / 'journal.jsonl'
            if not journal_path.exists():
                continue
            try:
                for line in journal_path.read_text().strip().split('\n'):
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    ts = _parse_iso(entry.get('timestamp', ''))
                    if ts and since <= ts <= until:
                        etype = entry.get('entry_type', '')
                        if etype in interesting_types:
                            highlights.append({
                                'session_id': session_dir.name,
                                'entry_type': etype,
                                'content': entry.get('content', '')[:200],
                                'ts': entry.get('timestamp', ''),
                            })
            except Exception:
                continue

        return highlights[:20]  # Cap at 20 highlights

    # ------------------------------------------------------------------
    # Phase label inference
    # ------------------------------------------------------------------

    def _infer_phase_label(self, events: list[dict], tasks_active: list[dict]) -> str:
        """
        Infer phase name from task IDs and dominant feature.
        task_morph_j* → 'Phase J (Morph)' etc.
        """
        if not events and not tasks_active:
            return 'No activity in period'

        # Collect all task IDs
        all_task_ids: list[str] = []
        for t in tasks_active:
            all_task_ids.append(t['id'])
        for ev in events:
            all_task_ids.extend(ev.get('task_ids') or [])

        # Match phase patterns
        phase_patterns = [
            (r'task_morph_k', 'Phase K (Auditable Superposition)'),
            (r'task_morph_j', 'Phase J (Omega Morph Line)'),
            (r'task_30_', 'Phase 30 (Universal Catalog)'),
            (r'task_29_', 'Phase 29 (Consolidation Pipeline)'),
            (r'task_28_', 'Phase 28 (Version Lifecycle)'),
            (r'task_27_', 'Phase 27 (Query Catalog)'),
            (r'task_26_', 'Phase 26 (Conformers)'),
            (r'task_25_', 'Phase 25 (Os_Toolkit Latest)'),
        ]
        for pattern, label in phase_patterns:
            if any(re.match(pattern, tid) for tid in all_task_ids):
                return label

        # Fall back to dominant feature from events
        features = [ev.get('feature', '') for ev in events if ev.get('feature')]
        if features:
            from collections import Counter
            top_feature = Counter(features).most_common(1)[0][0]
            return f'Work on {top_feature}'

        return 'Mixed activity'

    # ------------------------------------------------------------------
    # Domain inference
    # ------------------------------------------------------------------

    _DOMAIN_MAP = {
        'omega_bridge': 'meta_learning',
        'CDALS': 'pattern_recognition',
        'morph': 'meta_learning',
        'Morph': 'meta_learning',
        'temporal_narrative': 'meta_learning',
        'init_chain': 'meta_learning',
        'orchestrator': 'meta_learning',
        'conversational_trainer': 'meta_learning',
        'activity_integration_bridge': 'meta_learning',
        'grounded_suggest': 'meta_learning',
        'cli_change_tracker': 'meta_learning',
        'planner_tab': 'technical',
        'Os_Toolkit': 'technical',
        'interactive_trainer_gui': 'technical',
        'recovery_util': 'technical',
        'logger_util': 'technical',
        'models_tab': 'model_management',
        'export_base_to_gguf': 'model_management',
        'custom_code_tab': 'code_generation',
        'guillm': 'code_generation',
        'ag_forge_tab': 'knowledge_engineering',
        'ag_onboarding': 'knowledge_engineering',
        'KnowledgeForge': 'knowledge_engineering',
    }

    def _infer_dominant_domain(self, files_touched: list[dict]) -> tuple[str, float]:
        """
        Vote per file → domain using _DOMAIN_MAP stem matches.
        Returns (dominant_domain, confidence) where confidence = top_votes / total_files.
        """
        if not files_touched:
            return 'unknown', 0.0

        from collections import Counter
        votes: Counter = Counter()
        for f in files_touched:
            path = f.get('file', '')
            stem = Path(path).stem
            full = path
            domain = 'other'
            for key, dom in self._DOMAIN_MAP.items():
                if key.lower() in full.lower() or key.lower() in stem.lower():
                    domain = dom
                    break
            votes[domain] += 1

        total = sum(votes.values())
        top_domain, top_votes = votes.most_common(1)[0]
        confidence = top_votes / total if total else 0.0
        return top_domain, round(confidence, 2)

    # ------------------------------------------------------------------
    # Narrative text generation
    # ------------------------------------------------------------------

    def _build_narrative_text(self, result: dict) -> str:
        """Build a human-readable paragraph from the structured result."""
        period = result['period']
        files = result['files_touched']
        tasks = result['tasks_active']
        risks = result['risk_events']
        probes = result['probe_chain']
        phase = result['phase_summary']

        since_dt = _parse_iso(period['since'])
        until_dt = _parse_iso(period['until'])

        if since_dt and until_dt:
            span = until_dt - since_dt
            if span.days >= 1:
                period_str = f"{since_dt.strftime('%b %d')}–{until_dt.strftime('%b %d, %Y')}"
            else:
                hours = int(span.total_seconds() / 3600)
                period_str = f"the last {hours}h"
        else:
            period_str = 'the period'

        lines = [f"[{phase}]"]
        lines.append(f"Period: {period_str}")

        if not files:
            lines.append("No enriched file changes recorded in this window.")
            return '\n'.join(lines)

        # Files summary
        lines.append(f"\n{len(files)} file(s) touched:")
        for f in files[:8]:  # Top 8 by change count
            verbs_str = '/'.join(f['verbs']) if f['verbs'] else 'modified'
            methods_str = (
                f" (methods: {', '.join(f['methods'][:3])}{'...' if len(f['methods']) > 3 else ''})"
                if f['methods'] else ''
            )
            probe_str = f" [probe:{f['probe_status']}]" if f['probe_status'] else ''
            risk_str = f" ⚠{f['risk']}" if f['risk'] in ('HIGH', 'CRITICAL') else ''
            lines.append(
                f"  {verbs_str.upper():8} {f['file']}{methods_str}{probe_str}{risk_str}"
            )
        if len(files) > 8:
            lines.append(f"  ... and {len(files) - 8} more files")

        # Tasks summary
        if tasks:
            done = [t for t in tasks if t['status'] in ('DONE', 'COMPLETE')]
            todo = [t for t in tasks if t['status'] in ('TODO', 'READY')]
            lines.append(f"\n{len(tasks)} task(s) active:")
            for t in tasks[:6]:
                status_icon = '✓' if t['status'] in ('DONE', 'COMPLETE') else '○'
                lines.append(f"  {status_icon} [{t['id']}] {t['title']} ({t['status']})")
            if done:
                lines.append(f"  → {len(done)} completed this period")

        # Risk events
        if risks:
            crit = [r for r in risks if r['risk_level'] == 'CRITICAL']
            high = [r for r in risks if r['risk_level'] == 'HIGH']
            lines.append(f"\nRisk events: {len(crit)} CRITICAL, {len(high)} HIGH")
            for r in risks[:3]:
                reason_str = r['reasons'][0] if r['reasons'] else ''
                lines.append(f"  ⚠ {r['file']}: {reason_str[:80]}")

        # Probe chain (FAIL → PASS resolutions)
        if probes:
            lines.append(f"\nProbe resolutions ({len(probes)} FAIL→PASS):")
            for p in probes[:3]:
                lines.append(f"  ✓ {p['file']}: {p['fail_event']} → {p['pass_event']}")

        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # Persistence helpers (for --incremental)
    # ------------------------------------------------------------------

    def _last_explain_path(self) -> Path:
        return self._action_panel / self.LAST_EXPLAIN_FILE

    def _load_last_explain_ts(self) -> datetime | None:
        p = self._last_explain_path()
        if p.exists():
            return _parse_iso(p.read_text().strip())
        return None

    def _save_last_explain_ts(self, ts: datetime) -> None:
        try:
            self._last_explain_path().write_text(ts.isoformat())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Convenience: print formatted output
    # ------------------------------------------------------------------

    def print_narrative(self, result: dict, fmt: str = 'text') -> None:
        """Print the narrative to stdout in the requested format."""
        if fmt == 'json':
            print(json.dumps(result, indent=2, default=str))
        elif fmt == 'morph-jsonl':
            # Emit a SELF_EXPLAIN JSONL record
            record = {
                'messages': [
                    {'role': 'system', 'content': 'You are Morph, a code intelligence assistant. Summarise what was worked on.'},
                    {'role': 'user', 'content': f"SESSION RECAP [{result['period']['label']}]:\n{result['narrative']}"},
                    {'role': 'assistant', 'content': result['narrative']},
                ],
                'metadata': {
                    'record_type': 'SELF_EXPLAIN',
                    'period_since': result['period']['since'],
                    'period_until': result['period']['until'],
                    'phase_label': result['phase_summary'],
                    'files_touched': len(result['files_touched']),
                    'tasks_active': len(result['tasks_active']),
                },
            }
            print(json.dumps(record))
        else:
            print(result['narrative'])
            if result['session_highlights']:
                print(f"\nSession highlights ({len(result['session_highlights'])}):")
                for h in result['session_highlights'][:5]:
                    print(f"  [{h['ts'][:16]}] {h['entry_type']}: {h['content'][:80]}")


# ---------------------------------------------------------------------------
# CLI entry point (standalone test)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    trainer_root = Path('/home/commander/Trainer')
    engine = TemporalNarrativeEngine(trainer_root)

    since_arg = sys.argv[1] if len(sys.argv) > 1 else 'last 48h'
    fmt_arg = sys.argv[2] if len(sys.argv) > 2 else 'text'

    print(f"[TemporalNarrativeEngine] Explaining: {since_arg!r}")
    result = engine.explain(since=since_arg)
    engine.print_narrative(result, fmt=fmt_arg)
