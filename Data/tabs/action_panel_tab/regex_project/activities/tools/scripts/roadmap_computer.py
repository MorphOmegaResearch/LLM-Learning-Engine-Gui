"""
Deterministic Roadmap Computer — Compute Roadmap to Goal Completion.

Reads from grounded data sources (todos, task_context, runtime_bugs, debug logs,
py_manifest, version_manifest) and produces a prioritized roadmap with dependency
ordering, blocker identification, and completion metrics. No LLM calls.

Usage:
    from roadmap_computer import RoadmapComputer
    rc = RoadmapComputer(trainer_root)
    result = rc.compute("Project_Morph_Alpha")
    rc.print_report(result)

CLI:
    Os_Toolkit.py roadmap [project_id] [--format text|json|both] [--save] [--top N]
    orchestrator.py --morph-chat → roadmap [project_id]
"""

import json
import re
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Status normalization sets ───────────────────────────────────────────

STATUS_DONE = {
    'DONE', 'COMPLETE', 'complete', 'VERIFIED', 'SHIPPED',
    'IMPLEMENTED', 'RESOLVED',
}
STATUS_BLOCKED = {
    'BLOCKED', 'BLOCKED_BY_PHASE_1', 'BLOCKED_BY_PHASE_2',
    'BLOCKED_BY_PHASE_3', 'BLOCKED_ON_7_AND_37', 'BLOCKED_ON_DISCOVERY',
    'PENDING_BLOCKING', 'WAITING',
}
STATUS_ACTIVE = {
    'IN_PROGRESS', 'READY', 'READY_FOR_TESTING', 'READY_TO_IMPLEMENT',
    'READY_TO_DESIGN', 'READY_TO_EXECUTE', 'DESIGN_READY',
    'IN_REVIEW', 'TESTING',
}
STATUS_PENDING = {
    'PENDING', 'DESIGN', 'NOT_STARTED', 'TODO', 'PLANNED',
}

# Keys in phase dicts that are metadata, not tasks
PHASE_META_KEYS = {
    'phase', 'status', 'description', 'blocker', 'key_insight',
    'effort', 'note', 'notes', 'summary', 'depends_on',
}


class RoadmapComputer:
    """Deterministic roadmap computation from grounded data sources."""

    def __init__(self, trainer_root: Path):
        self._root = Path(trainer_root).resolve()
        self._plans = self._root / 'Data' / 'plans'
        self._tasks_dir = self._plans / 'Tasks'
        self._debug_dir = self._root / 'Data' / 'DeBug'
        self._manifest_path = self._root / 'Data' / 'backup' / 'version_manifest.json'
        self._pymanifest_path = self._root / 'Data' / 'pymanifest' / 'py_manifest.json'
        self._bugs_path = self._plans / 'runtime_bugs.json'
        self._todos_path = self._plans / 'todos.json'
        self._projects_path = self._plans / 'projects.json'
        self._config_path = self._plans / 'config.json'
        self._output_dir = self._plans / 'Morph'
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self._aoe_config_path = self._plans / 'aoe_vector_config.json'

        # Load aoe_vector_config at init — dynamic thresholds (Tasks #17 + #18)
        self._aoe_weights = {}
        self._blast_high_threshold = 5    # default: HIGH_BLAST when >=5 importers
        self._blast_moderate_threshold = 2  # default: MODERATE when >=2 importers
        self._dynamic_critical_files = self.CRITICAL_FILES.copy()
        try:
            if self._aoe_config_path.exists():
                _avc = json.loads(self._aoe_config_path.read_text(encoding='utf-8'))
                self._aoe_weights = _avc.get('aoe_weights', {})
                # #18: Derive blast_radius thresholds from context_windows
                _cw = _avc.get('context_windows', {})
                self._blast_high_threshold = _cw.get('version_manifest_high_risk_max', 5)
                self._blast_moderate_threshold = max(1, self._blast_high_threshold // 2)
                # #20: context_windows limits for task_context reads
                self._task_context_top_n = _cw.get('task_context_top_n', 10)
                self._enriched_changes_top_n = _cw.get('enriched_changes_top_n', 5)
                self._agent_context_top_max = _cw.get('agent_context_top_priority_max', 10)
                # #17: Override critical_files from aoe_vector_config if defined
                _extra_critical = _avc.get('critical_files', [])
                if _extra_critical:
                    self._dynamic_critical_files = self.CRITICAL_FILES | set(_extra_critical)
        except Exception:
            pass

        # Caches
        self._pymanifest_cache = None
        self._version_manifest_cache = None
        self._assess_cache = {}  # filename → assess dict

    # ── Main entry ──────────────────────────────────────────────────────

    def compute(self, project_id: Optional[str] = None) -> dict:
        """Main pipeline: collect → enrich → bugs → debug → deps → sort → prioritize → metrics."""
        # Resolve project
        if not project_id:
            project_id = self._get_active_project()

        # Step 1-2: Collect and enrich tasks
        tasks = self._collect_tasks(project_id)
        # Fall back to all tasks if project filter yields nothing
        if not tasks and project_id:
            tasks = self._collect_tasks(None)
            project_id = f"{project_id} (expanded to all — no tasks matched filter)"
        tasks = self._enrich_with_context(tasks)

        # Step 3-4: External issues
        bugs = self._collect_relevant_bugs(project_id, tasks)
        debug_issues = self._scan_latest_debug_log()

        # Step 5-6: Dependency graph + ordering
        dep_graph = self._build_dependency_graph(tasks)
        ordered = self._topological_sort(dep_graph, tasks)

        # Step 7: Priority classification
        task_by_id = {t['id']: t for t in tasks}
        items = self._prioritize(ordered, task_by_id, bugs, debug_issues)

        # Step 7.5: Resolve function skeletons + AoE + spawn specs
        self._resolve_skeletons(items, task_by_id)

        # Step 8: Metrics
        metrics = self._compute_metrics(tasks, bugs, debug_issues)

        return {
            'project_id': project_id or '__all__',
            'generated_at': datetime.now().isoformat(),
            'metrics': metrics,
            'items': items,
            'bugs': bugs,
            'debug_issues': debug_issues,
            'task_count': len(tasks),
            'dependency_edges': sum(len(v) for v in dep_graph.values()),
        }

    # ── Step 1: Collect tasks ───────────────────────────────────────────

    def _get_active_project(self) -> Optional[str]:
        if self._config_path.exists():
            try:
                cfg = json.loads(self._config_path.read_text(encoding='utf-8'))
                return cfg.get('active_project_id')
            except Exception:
                pass
        return None

    def _load_project_info(self, project_id: str) -> dict:
        if not self._projects_path.exists():
            return {}
        try:
            data = json.loads(self._projects_path.read_text(encoding='utf-8'))
            projects = data.get('projects', [])
            if isinstance(projects, list):
                for p in projects:
                    if p.get('project_id') == project_id:
                        return p
            elif isinstance(projects, dict):
                return projects.get(project_id, {})
        except Exception:
            pass
        return {}

    def _collect_tasks(self, project_id: Optional[str]) -> list:
        """Flatten todos.json phase structure into task list."""
        if not self._todos_path.exists():
            return []
        try:
            raw = json.loads(self._todos_path.read_text(encoding='utf-8'))
        except Exception:
            return []

        tasks = []
        if isinstance(raw, dict):
            self._flatten_phase_dict(raw, tasks, depth=0)
        elif isinstance(raw, list):
            tasks = [t for t in raw if isinstance(t, dict) and t.get('id')]

        # Filter by project
        if project_id:
            proj_info = self._load_project_info(project_id)
            key_files = set(proj_info.get('key_files', []))
            tasks = [t for t in tasks
                     if self._task_matches_project(t, project_id, key_files)]

        return tasks

    def _flatten_phase_dict(self, d: dict, out: list, depth: int,
                            phase_key: str = '', phase_name: str = ''):
        """Recursively flatten nested phase dicts into task list."""
        if depth > 4:
            return
        for key, val in d.items():
            if not isinstance(val, dict):
                continue
            if key in PHASE_META_KEYS:
                continue
            # Is this a task? (has 'title' or 'status' and key starts with 'task_')
            if key.startswith('task_') and ('title' in val or 'status' in val):
                val.setdefault('id', key)
                val['_phase'] = phase_key
                val['_phase_name'] = phase_name or phase_key
                out.append(val)
            # Is this a phase? (key starts with 'phase_' or contains nested task_ keys)
            elif key.startswith('phase_') or any(
                    k.startswith('task_') for k in val if isinstance(val.get(k), dict)):
                _pname = val.get('phase', key)
                self._flatten_phase_dict(val, out, depth + 1,
                                         phase_key=key, phase_name=_pname)
            # Could be a task with non-standard key (has title + status)
            elif 'title' in val and 'status' in val:
                val.setdefault('id', key)
                val['_phase'] = phase_key
                val['_phase_name'] = phase_name or phase_key
                out.append(val)

    def _task_matches_project(self, task: dict, project_id: str,
                               key_files: set) -> bool:
        # Direct project field
        if task.get('project', '') == project_id:
            return True
        # Phase name contains project ref
        phase = task.get('_phase', '') + task.get('_phase_name', '')
        pid_norm = project_id.lower().replace('_', '').replace('-', '')
        if pid_norm and pid_norm in phase.lower().replace('_', '').replace('-', ''):
            return True
        # Task files overlap with project key_files
        task_files = set(task.get('files', []))
        if task_files and key_files and (task_files & key_files):
            return True
        # Wherein matches key_files
        wherein = task.get('wherein', '')
        if wherein and key_files:
            for kf in key_files:
                if wherein.endswith(kf) or kf.endswith(wherein):
                    return True
        return False

    # ── Step 2: Enrich with task_context ────────────────────────────────

    def _enrich_with_context(self, tasks: list) -> list:
        for t in tasks:
            tid = t.get('id', '')
            ctx_path = self._tasks_dir / f'task_context_{tid}.json'
            if ctx_path.exists():
                try:
                    ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
                    t['_context'] = {
                        'changes_count': len(ctx.get('changes', [])),
                        'expected_diffs': ctx.get('expected_diffs', []),
                        'completion_signals': ctx.get('completion_signals', {}),
                        'metastate': ctx.get('metastate', {}),
                        'inferred_status': ctx.get('completion_signals', {}).get(
                            'inferred_status', ''),
                    }
                except Exception:
                    t['_context'] = {}
            else:
                t['_context'] = {}
        return tasks

    # ── Step 3: Collect bugs ────────────────────────────────────────────

    def _collect_relevant_bugs(self, project_id: Optional[str],
                                tasks: list) -> list:
        if not self._bugs_path.exists():
            return []
        try:
            bugs = json.loads(self._bugs_path.read_text(encoding='utf-8'))
        except Exception:
            return []

        open_bugs = [b for b in bugs
                     if b.get('status') == 'OPEN'
                     and len(b.get('message', '')) >= 20]

        # Build filename set from tasks
        task_files = set()
        for t in tasks:
            for f in t.get('files', []):
                task_files.add(Path(f).name)
                task_files.add(f)
            w = t.get('wherein', '')
            if w:
                task_files.add(Path(w).name)

        # Filter + deduplicate
        seen = set()
        relevant = []
        for b in open_bugs:
            msg = b.get('message', '')
            # Dedupe by first 80 chars
            key = msg[:80].strip()
            if key in seen:
                continue
            seen.add(key)

            if not task_files:
                relevant.append(b)
            elif any(tf in msg for tf in task_files if len(tf) > 3):
                relevant.append(b)

        return relevant[:30]  # cap at 30

    # ── Step 4: Scan debug log ──────────────────────────────────────────

    def _scan_latest_debug_log(self) -> dict:
        result = {
            'probe_failures': [], 'high_risks': [],
            'attribution_gaps': [], 'log_file': '',
        }
        if not self._debug_dir.exists():
            return result

        logs = sorted(self._debug_dir.glob('debug_log_*.txt'))
        if not logs:
            return result

        latest = logs[-1]
        result['log_file'] = latest.name
        try:
            text = latest.read_text(encoding='utf-8', errors='replace')
        except Exception:
            return result

        # Probe failures
        for m in re.finditer(
                r'(?:PROBE|probe_status)[:\s]*(?:FAIL|ERROR)'
                r'.*?(?:file|File|tab)[:\s]*(\S+)', text):
            f = m.group(1).strip('",\'')
            if f and f not in [p['file'] for p in result['probe_failures']]:
                result['probe_failures'].append({'file': f, 'severity': 'FAIL'})

        # Probe issues from "Tabs with probe issues:" line
        for m in re.finditer(r'Tabs with probe issues:\s*(.+)', text):
            for tab in m.group(1).split(','):
                tab = tab.strip()
                if tab and tab not in [p['file'] for p in result['probe_failures']]:
                    result['probe_failures'].append({
                        'file': tab, 'severity': 'WARN'})

        # HIGH/CRITICAL risks
        for m in re.finditer(r"risk[_:].*?(HIGH|CRITICAL).*?['\"]([\w_]+\.py)", text):
            f = m.group(2)
            if f not in result['high_risks']:
                result['high_risks'].append(f)

        # Attribution gaps
        gap_m = re.search(r'Attribution gaps:\s*(\d+)', text)
        if gap_m:
            n = int(gap_m.group(1))
            if n > 0:
                # Try to extract the gap files
                gap_files = re.findall(
                    r'GAP\s+#\[Event:\d+\]:\s*(\S+)', text)
                result['attribution_gaps'] = {
                    'count': n, 'files': gap_files[:10]}

        # AUTO_TEST failures
        for m in re.finditer(r'AUTO_TEST.*?FAIL.*?(\S+\.py)', text):
            f = m.group(1)
            if f not in [p['file'] for p in result['probe_failures']]:
                result['probe_failures'].append({
                    'file': f, 'severity': 'TEST_FAIL'})

        return result

    # ── Step 5: Dependency graph ────────────────────────────────────────

    def _load_pymanifest_cached(self) -> dict:
        if self._pymanifest_cache is None:
            if self._pymanifest_path.exists():
                try:
                    self._pymanifest_cache = json.loads(
                        self._pymanifest_path.read_text(encoding='utf-8'))
                except Exception:
                    self._pymanifest_cache = {}
            else:
                self._pymanifest_cache = {}
        return self._pymanifest_cache

    @staticmethod
    def _normalize_task_ref(ref) -> str:
        """Normalize '8.1' -> 'task_8_1', 'task_10' -> 'task_10'."""
        ref = str(ref).strip()
        if ref.startswith('task_'):
            return ref
        if re.match(r'^\d+\.?\d*$', ref):
            return 'task_' + ref.replace('.', '_')
        return ref

    def _build_dependency_graph(self, tasks: list) -> dict:
        """Build adjacency: {tid: set(tids this depends on)}."""
        task_by_id = {t['id']: t for t in tasks}
        all_ids = set(task_by_id.keys())
        graph = {tid: set() for tid in all_ids}

        # Index tasks by file (for import-graph edges)
        tasks_by_file = defaultdict(set)
        for t in tasks:
            for f in t.get('files', []):
                tasks_by_file[Path(f).name].add(t['id'])
            w = t.get('wherein', '')
            if w:
                tasks_by_file[Path(w).name].add(t['id'])

        for t in tasks:
            tid = t['id']

            # 1. Explicit depends_on
            for d in t.get('depends_on', []):
                d_norm = self._normalize_task_ref(d)
                if d_norm in all_ids and d_norm != tid:
                    graph[tid].add(d_norm)

            # 2. Import-graph: if this task's files import other tasks' files
            pm = self._load_pymanifest_cached()
            pm_files = pm.get('files', {})
            for f in t.get('files', []):
                fname = Path(f).name
                # Find this file in py_manifest
                for pm_path, pm_entry in pm_files.items():
                    if pm_path.endswith(fname):
                        for imp in pm_entry.get('imports', []):
                            resolved = imp.get('resolved_local', '')
                            if resolved:
                                imp_name = Path(resolved).name
                                for dep_tid in tasks_by_file.get(imp_name, set()):
                                    if dep_tid != tid:
                                        graph[tid].add(dep_tid)
                        break  # found the file, stop searching

        return graph

    # ── Step 6: Topological sort ────────────────────────────────────────

    def _topological_sort(self, graph: dict, tasks: list) -> list:
        """Kahn's algorithm with cycle detection."""
        all_ids = set(t['id'] for t in tasks)
        in_degree = defaultdict(int)

        for tid in all_ids:
            if tid not in in_degree:
                in_degree[tid] = 0

        for tid, deps in graph.items():
            for d in deps:
                if d in all_ids:
                    in_degree[tid] = in_degree.get(tid, 0) + 1

        queue = deque(sorted(
            [tid for tid in all_ids if in_degree[tid] == 0]))
        ordered = []

        while queue:
            tid = queue.popleft()
            ordered.append(tid)
            # Find tasks that depend on tid → decrease their in_degree
            for other, deps in graph.items():
                if tid in deps:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        # Remaining = cyclic
        remaining = all_ids - set(ordered)
        for tid in sorted(remaining):
            ordered.append(tid)

        return ordered

    def _compute_trust_score(self, task: dict, aoe_weights: dict) -> float:
        """Compute AoE-weighted trust score for a task item.

        Uses only TRUSTED fields from aoe_vector_config: task priority, status tier.
        changes[].risk_level is PROVISIONAL — capped contribution only.
        Returns float in [0.0, 1.0].
        """
        priority = task.get('priority', 'P3')
        status   = task.get('status', 'PENDING').upper()
        ctx      = task.get('_context', {})

        pri_key = f'task_P{priority[-1:]}' if priority else 'task_P3'
        base = aoe_weights.get(pri_key, 0.30)

        status_weight = aoe_weights.get(f'task_status_{status}', 0.60)

        # PROVISIONAL: changes[].risk_level — capped at 30% contribution
        risk_bonus = 0.0
        history = ctx.get('history', {})
        latest_risk = history.get('latest_risk', 'LOW')
        if latest_risk in ('HIGH', 'CRITICAL'):
            risk_bonus = aoe_weights.get('event_risk_HIGH', 1.0) * 0.3

        return round(min(1.0, base * status_weight + risk_bonus), 3)

    # ── Step 7: Prioritize ──────────────────────────────────────────────

    def _prioritize(self, ordered: list, task_by_id: dict,
                     bugs: list, debug_issues: dict) -> list:
        items = []
        position = {tid: i for i, tid in enumerate(ordered)}

        # Load aoe_weights for trust_score computation
        aoe_weights = {}
        try:
            if self._aoe_config_path.exists():
                avc = json.loads(self._aoe_config_path.read_text(encoding='utf-8'))
                aoe_weights = avc.get('aoe_weights', {})
        except Exception:
            pass

        # P0: Probe failures
        for pf in debug_issues.get('probe_failures', []):
            items.append({
                'priority': 'P0',
                'type': 'probe_failure',
                'file': pf['file'],
                'severity': pf.get('severity', 'FAIL'),
                'reason': f"Probe {pf.get('severity', 'FAIL')} on {pf['file']}"
                          f" — system may crash or degrade on load",
            })

        # P1: Open bugs
        for b in bugs[:10]:
            items.append({
                'priority': 'P1',
                'type': 'bug',
                'message': b.get('message', '')[:120],
                'timestamp': b.get('timestamp', ''),
                'bug_type': b.get('type', 'BUG'),
                'reason': f"OPEN {b.get('type', 'BUG')}: {b.get('message', '')[:100]}",
            })

        # Tasks by tier
        for tid in ordered:
            t = task_by_id.get(tid)
            if not t:
                continue
            status = t.get('status', 'PENDING').upper()
            ctx = t.get('_context', {})
            signals = ctx.get('completion_signals', {})
            inferred = ctx.get('inferred_status', '')

            if status in STATUS_DONE:
                # Don't add to action items, just counted in metrics
                continue

            elif status in STATUS_BLOCKED:
                # P2: Blocked (inferred_status=='BLOCKED' is UNTRUSTED per aoe_vector_config;
                # only the TRUSTED checklist.json 'status' field gates blocking decisions)
                deps = t.get('depends_on', [])
                dep_statuses = []
                for d in deps:
                    d_norm = self._normalize_task_ref(d)
                    dt = task_by_id.get(d_norm, {})
                    ds = dt.get('status', '?')
                    if ds.upper() not in STATUS_DONE:
                        dep_statuses.append(f"{d_norm} ({ds})")
                reason = f"BLOCKED"
                if dep_statuses:
                    reason += f" by: {', '.join(dep_statuses[:3])}"
                items.append({
                    'priority': 'P2',
                    'type': 'blocked_task',
                    'task_id': tid,
                    'title': t.get('title', ''),
                    'status': status,
                    'phase': t.get('_phase_name', t.get('_phase', '')),
                    'depends_on': deps,
                    'reason': reason,
                })

            elif status in STATUS_ACTIVE or (
                    signals.get('changes_count', 0) > 0
                    and inferred != 'COMPLETABLE'):
                # P3: In progress / partial
                changes = signals.get('changes_count', 0)
                exp_diffs = ctx.get('expected_diffs', [])
                n_exp = len(exp_diffs)
                n_matched = sum(1 for e in exp_diffs
                                if e.get('matched') or e.get('inferred'))
                reason = f"IN PROGRESS: {changes} changes"
                if n_exp > 0:
                    reason += f", {n_matched}/{n_exp} diffs matched"
                items.append({
                    'priority': 'P3',
                    'type': 'partial_task',
                    'task_id': tid,
                    'title': t.get('title', ''),
                    'status': status,
                    'phase': t.get('_phase_name', t.get('_phase', '')),
                    'changes_count': changes,
                    'expected_total': n_exp,
                    'expected_matched': n_matched,
                    'reason': reason,
                    'trust_score': self._compute_trust_score(t, aoe_weights),
                })

            else:
                # P4: Ready / pending
                dep_order = position.get(tid, 999)
                total = len(ordered)
                reason = f"READY: dep order {dep_order + 1}/{total}"
                pri = t.get('priority', '')
                if pri:
                    reason += f", priority {pri}"
                items.append({
                    'priority': 'P4',
                    'type': 'ready_task',
                    'task_id': tid,
                    'title': t.get('title', ''),
                    'status': status,
                    'phase': t.get('_phase_name', t.get('_phase', '')),
                    'dep_order': dep_order,
                    'reason': reason,
                    'trust_score': self._compute_trust_score(t, aoe_weights),
                })

        return items

    # ── Step 7.5: Skeleton Resolution + Spawn Specs ────────────────

    def _resolve_skeletons(self, items: list, task_by_id: dict):
        """For each P3/P4 item, look up py_manifest to find function skeletons,
        imports, class context, blast radius. Attach spawn-ready metadata."""
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})
        if not pm_files:
            return

        # Pre-build reverse import index: filename → list of importer filenames
        reverse_imports = self._build_reverse_import_index(pm_files)

        # Pre-build function index: func_name → [FunctionInfo dicts]
        func_index = {}
        class_index = {}
        for fpath, meta in pm_files.items():
            for fn in meta.get('functions', []):
                fname = fn.get('name', '')
                if fname:
                    func_index.setdefault(fname, []).append({
                        'file': fpath.split('/')[-1],
                        'qualname': fn.get('qualname', fname),
                        'args': fn.get('args', []),
                        'returns': fn.get('returns'),
                        'calls': fn.get('calls', []),
                        'decorators': fn.get('decorators', []),
                        'complexity': fn.get('complexity', 0),
                        'line': fn.get('line', 0),
                    })
            for cls in meta.get('classes', []):
                cname = cls.get('name', '')
                if cname:
                    class_index.setdefault(cname, []).append({
                        'file': fpath.split('/')[-1],
                        'qualname': cls.get('qualname', cname),
                        'bases': cls.get('bases', []),
                        'methods': [m.get('name') for m in cls.get('methods', [])],
                        'line': cls.get('line', 0),
                    })
                for mth in cls.get('methods', []):
                    mname = mth.get('name', '')
                    if mname:
                        func_index.setdefault(mname, []).append({
                            'file': fpath.split('/')[-1],
                            'qualname': mth.get('qualname', f'{cname}.{mname}'),
                            'args': mth.get('args', []),
                            'returns': mth.get('returns'),
                            'calls': mth.get('calls', []),
                            'decorators': mth.get('decorators', []),
                            'complexity': mth.get('complexity', 0),
                            'line': mth.get('line', 0),
                            'class': cname,
                        })

        for item in items:
            if item.get('type') not in ('partial_task', 'ready_task', 'blocked_task'):
                continue

            tid = item.get('task_id', '')
            task = task_by_id.get(tid, {})
            ctx = task.get('_context', {})

            # Collect target files for this task
            target_files = set()
            wherein = task.get('wherein', '')
            if wherein:
                target_files.add(Path(wherein).name)
            for f in task.get('files', []):
                target_files.add(Path(f).name)

            # Extract methods from expected_diffs, changes, and task title/description
            expected_methods = set()
            for ed in ctx.get('expected_diffs', []):
                for m in ed.get('methods', []):
                    expected_methods.add(m)
                for m in ed.get('functions', []):
                    expected_methods.add(m)

            # Pull methods from task_context changes[]
            changes = task.get('_context_raw', {}).get('changes', [])
            if not changes:
                # Re-read task_context for full changes array
                ctx_path = self._tasks_dir / f'task_context_{tid}.json'
                if ctx_path.exists():
                    try:
                        _full_ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
                        changes = _full_ctx.get('changes', [])
                    except Exception:
                        changes = []
            for ch in changes:
                for m in ch.get('methods', []):
                    expected_methods.add(m)
                # Also capture file from change events
                ch_file = ch.get('file', '')
                if ch_file:
                    target_files.add(Path(ch_file).name)

            # Also check completion_signals for methods mentioned
            signals = ctx.get('completion_signals', {})
            probes_failing_val = signals.get('probes_failing', [])
            probes_failing_list = probes_failing_val if isinstance(probes_failing_val, list) else []
            for m in probes_failing_list:
                if isinstance(m, str) and '.' not in m and not m.startswith('#'):
                    expected_methods.add(m)

            if not target_files and not expected_methods:
                continue

            # ── Build spawn spec ──────────────────────────────────────
            spawn = {
                'target_files': sorted(target_files),
                'skeletons': [],
                'missing_imports': [],
                'aoe': {},
            }

            # Resolve skeletons for expected methods
            for method_name in sorted(expected_methods):
                matches = func_index.get(method_name, [])
                if matches:
                    # Prefer match in target file, else take first
                    best = None
                    for m in matches:
                        if m['file'] in target_files:
                            best = m
                            break
                    if not best:
                        best = matches[0]
                    skeleton = {
                        'name': method_name,
                        'status': 'EXISTS',
                        'qualname': best['qualname'],
                        'args': best['args'],
                        'returns': best.get('returns'),
                        'calls': [c[0] if isinstance(c, (list, tuple)) else c
                                  for c in best.get('calls', [])[:10]],
                        'complexity': best.get('complexity', 0),
                        'file': best['file'],
                        'line': best.get('line', 0),
                    }
                    if best.get('class'):
                        skeleton['class'] = best['class']
                    spawn['skeletons'].append(skeleton)
                else:
                    # Method not found — truly missing, spawnable
                    spawn['skeletons'].append({
                        'name': method_name,
                        'status': 'MISSING',
                        'pattern_hint': self._find_pattern_hint(
                            method_name, func_index),
                    })

            # Resolve imports needed for target files
            for tf in target_files:
                for fpath, meta in pm_files.items():
                    if fpath.endswith(tf):
                        for imp in meta.get('imports', []):
                            if imp.get('runtime_success') is False or imp.get('runtime_error'):
                                spawn['missing_imports'].append({
                                    'module': imp.get('module', ''),
                                    'error': imp.get('runtime_error', ''),
                                    'file': tf,
                                    'line': imp.get('line', 0),
                                })
                        break

            # AoE-like blast radius from reverse imports
            total_importers = 0
            aoe_files = {}
            for tf in target_files:
                importers = reverse_imports.get(tf, [])
                total_importers += len(importers)
                if importers:
                    aoe_files[tf] = {
                        'imported_by': importers[:10],
                        'importer_count': len(importers),
                    }

            if aoe_files:
                spawn['aoe'] = {
                    'blast_radius': total_importers,
                    'files': aoe_files,
                }
                if total_importers >= self._blast_high_threshold:
                    spawn['aoe']['risk'] = 'HIGH_BLAST'
                elif total_importers >= self._blast_moderate_threshold:
                    spawn['aoe']['risk'] = 'MODERATE'
                else:
                    spawn['aoe']['risk'] = 'LOW'

            # Attach per-file assess for target files
            file_assessments = {}
            for tf in target_files:
                fa = self.assess_file(tf)
                if fa.get('warnings') or fa.get('is_critical'):
                    file_assessments[tf] = fa
            if file_assessments:
                spawn['file_assess'] = file_assessments

            # Domain classification from imports (T6-4)
            file_domains = {}
            for tf in target_files:
                for fpath, meta in pm_files.items():
                    if fpath.endswith(tf):
                        imports = meta.get('imports', [])
                        dv = {}
                        for imp in imports:
                            if isinstance(imp, dict):
                                dom = self._infer_module_domain_simple(
                                    imp.get('module', ''))
                                if dom != 'unknown':
                                    dv[dom] = dv.get(dom, 0) + 1
                        if dv:
                            file_domains[tf] = max(dv, key=dv.get)
                        break
            if file_domains:
                spawn['domains'] = file_domains

            # Only attach if we found something useful
            has_data = (spawn['skeletons'] or spawn['missing_imports']
                        or spawn['aoe'] or file_assessments)
            if has_data:
                item['spawn_spec'] = spawn

    def _build_reverse_import_index(self, pm_files: dict) -> dict:
        """Build filename → [importer filenames] from py_manifest dependencies."""
        rev = defaultdict(list)
        for fpath, meta in pm_files.items():
            if '/backup/' in fpath or '/history/' in fpath:
                continue
            fname = fpath.split('/')[-1]
            if '.backup_' in fname or fname.startswith('LEGACY'):
                continue
            for dep in meta.get('dependencies', []):
                dep_name = dep.split('/')[-1] if isinstance(dep, str) else ''
                if dep_name:
                    rev[dep_name].append(fname)
        return dict(rev)

    @staticmethod
    def _find_pattern_hint(method_name: str, func_index: dict) -> dict:
        """Find similar functions by prefix/suffix to suggest a pattern for missing methods."""
        # Strip common prefixes to find related functions
        hints = {}
        bare = method_name.lstrip('_')
        # Look for functions with same verb prefix (e.g. _build_ → _build_*)
        parts = bare.split('_', 1)
        if len(parts) > 1:
            verb = parts[0]
            similar = []
            for fname, entries in func_index.items():
                if fname.lstrip('_').startswith(verb + '_') and fname != method_name:
                    similar.append({
                        'name': fname,
                        'args': entries[0].get('args', []),
                        'file': entries[0].get('file', ''),
                    })
                    if len(similar) >= 3:
                        break
            if similar:
                hints['similar_by_verb'] = similar
                hints['verb'] = verb

        return hints

    # ── Step 8: Metrics ─────────────────────────────────────────────────

    def _compute_metrics(self, tasks: list, bugs: list,
                          debug_issues: dict) -> dict:
        total = len(tasks)
        done = sum(1 for t in tasks
                   if t.get('status', '').upper() in STATUS_DONE)
        blocked = sum(1 for t in tasks
                      if t.get('status', '').upper() in STATUS_BLOCKED)
        active = sum(1 for t in tasks
                     if t.get('status', '').upper() in STATUS_ACTIVE)
        pending = total - done - blocked - active

        # Expected diffs totals
        exp_total = 0
        exp_matched = 0
        for t in tasks:
            eds = t.get('_context', {}).get('expected_diffs', [])
            exp_total += len(eds)
            exp_matched += sum(1 for e in eds
                               if e.get('matched') or e.get('inferred'))

        return {
            'total_tasks': total,
            'done': done,
            'blocked': blocked,
            'active': active,
            'pending': pending,
            'completion_pct': round(done / total * 100, 1) if total else 0.0,
            'open_bugs': len(bugs),
            'probe_failures': len(debug_issues.get('probe_failures', [])),
            'high_risk_files': len(debug_issues.get('high_risks', [])),
            'attribution_gaps': (debug_issues.get('attribution_gaps', {})
                                 .get('count', 0)
                                 if isinstance(debug_issues.get('attribution_gaps'), dict)
                                 else 0),
            'phases_represented': len(set(
                t.get('_phase', '') for t in tasks if t.get('_phase'))),
            'expected_diffs_total': exp_total,
            'expected_diffs_matched': exp_matched,
        }

    # ── Output: Text Report ─────────────────────────────────────────────

    def print_report(self, result: dict, top_n: int = 0):
        m = result['metrics']
        pid = result['project_id']
        ts = result['generated_at']

        D = '═' * 62
        d = '─' * 58
        print(f"\n{D}")
        print(f"  ROADMAP: {pid}")
        print(f"  Generated: {ts}")
        print(D)

        # Metrics
        print(f"\n  METRICS")
        print(f"  {d}")
        print(f"  Tasks: {m['total_tasks']} total | "
              f"{m['done']} done ({m['completion_pct']}%) | "
              f"{m['active']} active | "
              f"{m['blocked']} blocked | "
              f"{m['pending']} pending")
        print(f"  Bugs: {m['open_bugs']} open | "
              f"Probes: {m['probe_failures']} failing | "
              f"High-risk: {m['high_risk_files']} files")
        if m['expected_diffs_total'] > 0:
            ed_pct = round(m['expected_diffs_matched'] / m['expected_diffs_total'] * 100, 1)
            print(f"  Diffs: {m['expected_diffs_matched']}/{m['expected_diffs_total']}"
                  f" matched ({ed_pct}%)")
        if m['attribution_gaps'] > 0:
            print(f"  Attribution gaps: {m['attribution_gaps']}")
        print(f"  Phases: {m['phases_represented']}")

        # Items by priority
        items = result['items']
        if top_n > 0:
            items = items[:top_n]

        current_priority = None
        counter = 0
        tier_labels = {
            'P0': 'P0: CRITICAL (fix now)',
            'P1': 'P1: BUGS (open issues)',
            'P2': 'P2: BLOCKED (need dependency resolution)',
            'P3': 'P3: IN PROGRESS (partial)',
            'P4': 'P4: READY (next up, in dependency order)',
        }

        for item in items:
            p = item['priority']
            if p != current_priority:
                current_priority = p
                label = tier_labels.get(p, p)
                print(f"\n  ─── {label} {'─' * max(1, 50 - len(label))}")

            counter += 1
            tid = item.get('task_id', '')
            title = item.get('title', '')

            if item['type'] == 'probe_failure':
                print(f"  [{counter}] Probe {item['severity']}: {item['file']}")
                print(f"      {item['reason']}")
            elif item['type'] == 'bug':
                print(f"  [{counter}] {item['bug_type']}: "
                      f"{item['message'][:80]}")
                if item.get('timestamp'):
                    print(f"      Since: {item['timestamp']}")
            else:
                print(f"  [{counter}] {tid}: {title}")
                print(f"      {item['reason']}")

                # Show spawn spec if available
                spawn = item.get('spawn_spec')
                if spawn:
                    skels = spawn.get('skeletons', [])
                    missing = [s for s in skels if s.get('status') == 'MISSING']
                    exists = [s for s in skels if s.get('status') == 'EXISTS']

                    if exists:
                        fn_summary = ', '.join(
                            f"{s['name']}({', '.join(s.get('args', [])[:3])})"
                            for s in exists[:3])
                        print(f"      Functions: {fn_summary}")
                    if missing:
                        print(f"      Missing: {', '.join(s['name'] for s in missing)}")
                        for s in missing:
                            hint = s.get('pattern_hint', {})
                            sim = hint.get('similar_by_verb', [])
                            if sim:
                                print(f"        Pattern hint [{hint.get('verb', '?')}_*]: "
                                      f"{sim[0]['name']}({', '.join(sim[0].get('args', [])[:3])})"
                                      f" in {sim[0].get('file', '?')}")
                    imps = spawn.get('missing_imports', [])
                    if imps:
                        print(f"      Import issues: {', '.join(i['module'] for i in imps[:3])}")

                    aoe = spawn.get('aoe', {})
                    blast = aoe.get('blast_radius', 0)
                    if blast > 0:
                        risk = aoe.get('risk', 'LOW')
                        print(f"      Blast radius: {blast} importers [{risk}]")

                    # Spawnable verdict
                    if exists or missing:
                        n_spawn = len(missing)
                        n_known = len(exists)
                        if n_spawn > 0:
                            print(f"      Spawn: {n_spawn} function(s) to create, "
                                  f"{n_known} resolved")
                        elif n_known > 0:
                            print(f"      Spawn: {n_known} function(s) resolved — "
                                  f"verify calls + tests")

                    # File assess risk badges
                    fa = spawn.get('file_assess', {})
                    for fa_file, fa_data in fa.items():
                        rs = fa_data.get('risk_summary', 'INFO')
                        if rs == 'INFO':
                            continue
                        ws = fa_data.get('warnings', [])
                        w_parts = []
                        for w in ws[:3]:
                            w_parts.append(f"{w['level']}: {w['message'][:60]}")
                        badge = f"AoE [{rs}]"
                        if fa_data.get('is_critical'):
                            badge = f"AoE [CRITICAL — CORE]"
                        print(f"      {badge} {fa_file}")
                        for wp in w_parts:
                            print(f"        {wp}")

        # Next action
        if items:
            first = items[0]
            if first['type'] == 'probe_failure':
                action = f"Fix probe failure in {first['file']}"
            elif first['type'] == 'bug':
                action = f"Resolve: {first.get('message', '')[:60]}"
            else:
                action = f"Work on {first.get('task_id', '')}: {first.get('title', '')[:50]}"
            print(f"\n{D}")
            print(f"  NEXT ACTION: {action}")
            print(f"{D}\n")
        else:
            print(f"\n{D}")
            print(f"  ALL CLEAR — no action items found")
            print(f"{D}\n")

    # ── Output: JSON ────────────────────────────────────────────────────

    def save_json(self, result: dict, project_id: Optional[str] = None):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        proj = (project_id or 'all').replace(' ', '_')
        out_path = self._output_dir / f'roadmap_{proj}_{ts}.json'
        out_path.write_text(
            json.dumps(result, indent=2, default=str, ensure_ascii=False),
            encoding='utf-8')
        print(f"  [+] Roadmap saved: {out_path.name}")
        return out_path

    # ── Assess: Per-File AoE Impact ────────────────────────────────

    CRITICAL_FILES = {
        'logger_util.py', 'recovery_util.py', 'interactive_trainer_gui_NEW.py',
    }

    def _load_version_manifest_cached(self) -> dict:
        if self._version_manifest_cache is None:
            if self._manifest_path.exists():
                try:
                    self._version_manifest_cache = json.loads(
                        self._manifest_path.read_text(encoding='utf-8'))
                except Exception:
                    self._version_manifest_cache = {}
            else:
                self._version_manifest_cache = {}
        return self._version_manifest_cache

    def assess_file(self, filename: str) -> dict:
        """Lightweight per-file AoE assessment — same data as Os_Toolkit assess
        but returned as a dict instead of text. Cached per filename."""
        if filename in self._assess_cache:
            return self._assess_cache[filename]

        result = {
            'file': filename,
            'warnings': [],  # list of {level, message}
            'risk_summary': 'INFO',
            'history': {},
            'blast_radius': {},
            'aoe_vectors': [],
            'is_critical': False,
        }

        file_base = filename.split('/')[-1]

        # 1. Core file check (#17: uses _dynamic_critical_files — reads from aoe_vector_config + hardcoded fallback)
        if file_base in self._dynamic_critical_files:
            result['is_critical'] = True
            result['warnings'].append({
                'level': 'CRITICAL',
                'message': f"'{file_base}' is a CORE system file — "
                           f"changes affect the recovery pipeline",
            })

        # 2. Historical risk from enriched_changes in version_manifest
        vm = self._load_version_manifest_cached()
        ec_all = vm.get('enriched_changes', {})
        pat_base = file_base.lower()

        total_changes = 0
        risk_high_count = 0
        unresolved_probes = 0
        latest_risk = 'LOW'
        latest_probe = ''
        latest_test = ''
        risk_reasons = []

        for eid, ch in ec_all.items():
            ch_base = ch.get('file', '').lower().split('/')[-1]
            if pat_base not in ch_base:
                continue
            total_changes += 1
            rl = ch.get('risk_level', 'LOW')
            if rl in ('HIGH', 'CRITICAL'):
                risk_high_count += 1
            latest_risk = rl
            ps = ch.get('probe_status', '')
            if ps == 'FAIL':
                # Check if resolved
                if not ch.get('resolved_by'):
                    unresolved_probes += 1
            latest_probe = ps or latest_probe
            latest_test = ch.get('test_status', '') or latest_test
            rr = ch.get('risk_reasons', [])
            if isinstance(rr, list):
                risk_reasons.extend(rr)
            elif isinstance(rr, str) and rr:
                risk_reasons.append(rr)

        unique_reasons = list(dict.fromkeys(risk_reasons))[:5]

        result['history'] = {
            'total_changes': total_changes,
            'latest_risk': latest_risk,
            'risk_high_count': risk_high_count,
            'unresolved_probes': unresolved_probes,
            'latest_probe': latest_probe,
            'latest_test': latest_test,
            'risk_reasons': unique_reasons,
        }

        if risk_high_count:
            result['warnings'].append({
                'level': 'RISK',
                'message': f"{risk_high_count} HIGH/CRITICAL risk events in history",
            })
        if unresolved_probes:
            result['warnings'].append({
                'level': 'CRITICAL',
                'message': f"{unresolved_probes} probe FAIL(s) unresolved "
                           f"— fix before modifying",
            })
        elif latest_probe == 'FAIL':
            result['warnings'].append({
                'level': 'WARN',
                'message': "Latest probe status is FAIL",
            })
        if latest_test and latest_test.upper() not in ('OK', 'PASS', ''):
            result['warnings'].append({
                'level': 'WARN',
                'message': f"Test status is '{latest_test}'",
            })

        # 3. Blast radius from py_manifest reverse imports (with names)
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})
        importers = []
        imports = []
        for fpath, meta in pm_files.items():
            if fpath.endswith(file_base):
                # This file's own imports
                imports = [d.split('/')[-1]
                           for d in meta.get('dependencies', [])
                           if isinstance(d, str)]
                break

        # Reverse: who imports this file?
        for fpath, meta in pm_files.items():
            if '/backup/' in fpath or '/history/' in fpath:
                continue
            fname = fpath.split('/')[-1]
            if '.backup_' in fname or fname.startswith('LEGACY'):
                continue
            if fpath.endswith(file_base):
                continue
            for dep in meta.get('dependencies', []):
                if isinstance(dep, str) and dep.endswith(file_base):
                    importers.append(fname)
                    break

        result['blast_radius'] = {
            'importer_count': len(importers),
            'importers': importers[:20],
            'imports': imports[:20],
        }
        # #18: blast_radius warning thresholds from self._blast_high_threshold (aoe_vector_config driven)
        if len(importers) >= self._blast_high_threshold * 2:
            result['warnings'].append({
                'level': 'WARN',
                'message': f"{len(importers)} downstream dependents "
                           f"— test all importers after changes",
            })
        elif len(importers) >= self._blast_high_threshold:
            result['warnings'].append({
                'level': 'WARN',
                'message': f"{len(importers)} downstream dependents",
            })

        # 4. AoE vector config risk scan
        try:
            if self._aoe_config_path.exists():
                avc = json.loads(
                    self._aoe_config_path.read_text(encoding='utf-8'))
                # Build check map from enriched_change fields
                hist = result['history']
                check_map = {
                    'ec_risk_level': (hist.get('latest_risk', ''),
                                     lambda v: v in ('HIGH', 'CRITICAL'), 'RISK'),
                    'ec_risk_reasons': (hist.get('risk_reasons', []),
                                       lambda v: bool(v), 'WARN'),
                    'ec_test_status': (hist.get('latest_test', ''),
                                      lambda v: v and v.upper() not in
                                      ('OK', 'PASS', ''), 'WARN'),
                    'ec_probe_status': (hist.get('latest_probe', ''),
                                       lambda v: v == 'FAIL', 'WARN'),
                }
                # FIX: aoe_vector_config has no 'layers' key — apply check_map directly.
                # aoe_weights provides per-level risk weights for trust_score integration.
                aoe_weight_map = {
                    'RISK': avc.get('aoe_weights', {}).get('event_risk_HIGH', 1.0),
                    'WARN': avc.get('aoe_weights', {}).get('event_risk_MEDIUM', 0.6),
                    'INFO': avc.get('aoe_weights', {}).get('event_risk_LOW', 0.2),
                }
                _display_map = {
                    'ec_risk_level':  'AoE risk level',
                    'ec_risk_reasons': 'AoE risk reasons',
                    'ec_test_status': 'AoE test status',
                    'ec_probe_status': 'AoE probe status',
                }
                for vid, (val, check_fn, level) in check_map.items():
                    try:
                        if check_fn(val):
                            result['aoe_vectors'].append({
                                'id': vid,
                                'display': _display_map.get(vid, vid),
                                'value': str(val)[:80],
                                'level': level,
                                'weight': aoe_weight_map.get(level, 0.2),
                            })
                    except Exception:
                        pass
        except Exception:
            pass

        # 5. Compute summary risk level
        levels = [w['level'] for w in result['warnings']]
        if 'CRITICAL' in levels:
            result['risk_summary'] = 'CRITICAL'
        elif 'RISK' in levels:
            result['risk_summary'] = 'RISK'
        elif 'WARN' in levels:
            result['risk_summary'] = 'WARN'
        else:
            result['risk_summary'] = 'INFO'

        self._assess_cache[filename] = result
        return result

    # ── Spawn: Diff Template Generation ─────────────────────────────

    def generate_spawn_diffs(self, result: dict) -> list:
        """For each roadmap item with MISSING skeletons, generate a deterministic
        diff template showing: target file, class context, insertion point,
        function signature, inferred calls, and required imports.

        Returns list of spawn_diff dicts, each representing one function to create."""
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})
        if not pm_files:
            return []

        diffs = []
        # Deduplicate: same function + same target file = one diff, multiple tasks
        seen = {}  # (func_name, target_file) → diff index

        for item in result.get('items', []):
            spawn = item.get('spawn_spec')
            if not spawn:
                continue
            skeletons = spawn.get('skeletons', [])
            missing = [s for s in skeletons if s.get('status') == 'MISSING']
            if not missing:
                continue

            tid = item.get('task_id', '')
            title = item.get('title', '')
            target_files = spawn.get('target_files', [])

            for skel in missing:
                func_name = skel.get('name', '')
                if not func_name:
                    continue

                # Check for dedup
                tf_key = target_files[0] if target_files else '?'
                dedup_key = (func_name, tf_key)
                if dedup_key in seen:
                    # Merge task into existing diff
                    existing = diffs[seen[dedup_key]]
                    existing.setdefault('also_needed_by', []).append(
                        {'task_id': tid, 'title': title})
                    continue

                # Find the best target file and class context from py_manifest
                file_ctx = self._find_file_context(func_name, target_files, pm_files)
                if not file_ctx:
                    # No py_manifest entry — emit a bare diff
                    diff = {
                        'task_id': tid,
                        'task_title': title,
                        'function': func_name,
                        'status': 'SPAWN_BARE',
                        'target_file': tf_key,
                        'class': None,
                        'insert_after_line': None,
                        'signature': f"def {func_name}(self):",
                        'docstring': f'"""TODO: Implement for {tid}."""',
                        'inferred_calls': [],
                        'required_imports': [],
                        'pattern_hint': skel.get('pattern_hint', {}),
                        'blast_radius': spawn.get('aoe', {}).get('blast_radius', 0),
                    }
                    # Attach assess data
                    diff['assess'] = self.assess_file(tf_key)
                    seen[dedup_key] = len(diffs)
                    diffs.append(diff)
                    continue

                # Build the diff template from file context
                diff = self._build_spawn_diff(
                    func_name, skel, file_ctx, tid, title, spawn)
                # Attach assess data for the target file
                diff['assess'] = self.assess_file(
                    diff.get('target_file', tf_key))
                seen[dedup_key] = len(diffs)
                diffs.append(diff)

        return diffs

    def _find_file_context(self, func_name: str, target_files: list,
                           pm_files: dict) -> dict:
        """Find the py_manifest file entry and class where this function should live."""
        # Strategy: look for sibling methods in the same class
        # If the task's changes include methods from a class, the missing function
        # likely belongs to the same class

        for tf in target_files:
            for fpath, meta in pm_files.items():
                if not fpath.endswith(tf):
                    continue

                # Check classes — does any class have methods with similar prefix?
                best_class = None
                best_score = 0
                bare = func_name.lstrip('_')
                prefix = bare.split('_')[0] if '_' in bare else bare

                for cls in meta.get('classes', []):
                    score = 0
                    for mth in cls.get('methods', []):
                        mname = mth.get('name', '').lstrip('_')
                        # Same verb prefix
                        if mname.startswith(prefix + '_'):
                            score += 2
                        # Same class = likely home
                        if mname:
                            score += 0.1
                    if score > best_score:
                        best_score = score
                        best_class = cls

                # If no class matched by prefix, pick the largest class
                if not best_class and meta.get('classes'):
                    best_class = max(meta['classes'],
                                     key=lambda c: len(c.get('methods', [])))

                return {
                    'file_path': fpath,
                    'file_name': tf,
                    'classes': meta.get('classes', []),
                    'functions': meta.get('functions', []),
                    'imports': meta.get('imports', []),
                    'target_class': best_class,
                }
        return {}

    def _build_spawn_diff(self, func_name: str, skel: dict, file_ctx: dict,
                          tid: str, title: str, spawn: dict) -> dict:
        """Build a structured diff template for a missing function."""
        target_class = file_ctx.get('target_class')

        # Determine insertion point: after the last method in the target class
        insert_after_line = None
        insert_after_method = None
        class_name = None
        class_indent = '    '  # default 4-space class method indent

        if target_class:
            class_name = target_class.get('name')
            methods = target_class.get('methods', [])
            if methods:
                # Insert after the last method
                last = max(methods, key=lambda m: m.get('end_line', 0))
                insert_after_line = last.get('end_line', 0)
                insert_after_method = last.get('name', '')

        # Infer signature from pattern hints and sibling methods
        args = self._infer_args(func_name, skel, target_class)
        returns = self._infer_return_type(func_name, skel)

        # Infer what this function should call based on name patterns
        inferred_calls = self._infer_calls(func_name, file_ctx)

        # Infer imports needed
        required_imports = self._infer_imports(func_name, file_ctx)

        # Build the signature
        arg_str = ', '.join(args)
        ret_annotation = f" -> {returns}" if returns else ''
        signature = f"def {func_name}({arg_str}){ret_annotation}:"

        # Build docstring from task title
        docstring = f'"""TODO [{tid}]: {title[:80]}."""'

        # Build the body hint from inferred calls
        body_lines = []
        for call in inferred_calls[:5]:
            body_lines.append(f"# → {call}")
        if not body_lines:
            body_lines.append("pass  # TODO: implement")

        # Build the full diff block
        diff_lines = []
        diff_lines.append('')
        diff_lines.append(f"{class_indent}{signature}")
        diff_lines.append(f"{class_indent}    {docstring}")
        for bl in body_lines:
            diff_lines.append(f"{class_indent}    {bl}")
        diff_lines.append('')

        return {
            'task_id': tid,
            'task_title': title,
            'function': func_name,
            'status': 'SPAWN_READY',
            'target_file': file_ctx.get('file_name', '?'),
            'target_file_full': file_ctx.get('file_path', ''),
            'class': class_name,
            'insert_after_line': insert_after_line,
            'insert_after_method': insert_after_method,
            'signature': signature,
            'args': args,
            'returns': returns,
            'docstring': docstring,
            'inferred_calls': inferred_calls,
            'required_imports': required_imports,
            'body_lines': body_lines,
            'diff_block': '\n'.join(diff_lines),
            'pattern_hint': skel.get('pattern_hint', {}),
            'blast_radius': spawn.get('aoe', {}).get('blast_radius', 0),
        }

    @staticmethod
    def _infer_args(func_name: str, skel: dict, target_class: dict) -> list:
        """Infer function arguments from pattern hints and naming conventions."""
        args = ['self']  # assume instance method if inside a class

        # Check pattern hints for similar functions
        hint = skel.get('pattern_hint', {})
        similar = hint.get('similar_by_verb', [])
        if similar:
            # Use args from the most similar function
            hint_args = similar[0].get('args', [])
            if hint_args and hint_args != ['self']:
                return hint_args

        # Naming convention heuristics
        bare = func_name.lstrip('_')
        if bare.startswith('lookup_') or bare.startswith('get_'):
            # Lookup/getter: typically takes a key/name/pattern
            args.append('key')
        elif bare.startswith('build_') or bare.startswith('create_'):
            # Builder: takes config or context
            args.append('config=None')
        elif bare.startswith('process_') or bare.startswith('handle_'):
            args.append('event')
        elif bare.startswith('validate_') or bare.startswith('check_'):
            args.append('value')
        elif bare.startswith('parse_'):
            args.append('text')
        elif bare.startswith('load_') or bare.startswith('read_'):
            args.append('path')
        elif bare.startswith('save_') or bare.startswith('write_'):
            args.extend(['data', 'path=None'])
        elif bare.startswith('format_') or bare.startswith('render_'):
            args.append('data')
        elif bare.startswith('on_') or bare.startswith('_on_'):
            args.append('event=None')
        elif bare.startswith('sync_') or bare.startswith('refresh_'):
            pass  # typically just self
        elif bare.startswith('compute_') or bare.startswith('calculate_'):
            args.append('inputs')

        return args

    @staticmethod
    def _infer_return_type(func_name: str, skel: dict) -> str:
        """Infer return type from naming conventions."""
        bare = func_name.lstrip('_')
        if bare.startswith(('get_', 'lookup_', 'find_', 'load_', 'read_')):
            return 'Optional[Any]'
        if bare.startswith(('is_', 'has_', 'can_', 'should_', 'check_', 'validate_')):
            return 'bool'
        if bare.startswith(('count_', 'calculate_', 'compute_')):
            return 'int'
        if bare.startswith(('build_', 'create_', 'format_', 'render_')):
            return 'str'
        if bare.startswith(('list_', 'collect_', 'gather_')):
            return 'list'
        if bare.startswith('parse_'):
            return 'dict'
        return ''

    def _infer_calls(self, func_name: str, file_ctx: dict) -> list:
        """Infer what methods this function likely calls based on
        sibling methods and naming patterns."""
        calls = []
        bare = func_name.lstrip('_')

        target_class = file_ctx.get('target_class')
        if target_class:
            methods = target_class.get('methods', [])
            method_names = [m.get('name', '') for m in methods]

            # If func is _lookup_X, it probably calls self._X or reads data
            parts = bare.split('_', 1)
            if len(parts) > 1:
                verb, noun = parts[0], parts[1]
                # Look for related methods
                for mname in method_names:
                    mbare = mname.lstrip('_')
                    # Same noun — likely a helper/accessor for the same data
                    if noun in mbare and mname != func_name:
                        calls.append(f"self.{mname}()")
                        if len(calls) >= 3:
                            break

        # Name-based call patterns
        if bare.startswith('lookup_') or bare.startswith('load_'):
            calls.append("Path(...).read_text()")
            calls.append("json.loads(...)")
        elif bare.startswith('build_') or bare.startswith('format_'):
            calls.append("# assemble output dict/str")
        elif bare.startswith('save_') or bare.startswith('write_'):
            calls.append("json.dumps(...)")
            calls.append("Path(...).write_text(...)")

        return calls[:5]

    def _infer_imports(self, func_name: str, file_ctx: dict) -> list:
        """Infer import statements needed based on naming and existing imports."""
        needed = []
        bare = func_name.lstrip('_')

        # Check if file already has common imports
        existing_modules = {imp.get('module', '') for imp in file_ctx.get('imports', [])}

        if bare.startswith(('load_', 'save_', 'read_', 'write_', 'lookup_')):
            if 'json' not in existing_modules:
                needed.append('import json')
            if 'pathlib' not in existing_modules and 'pathlib.Path' not in existing_modules:
                needed.append('from pathlib import Path')

        return needed

    # ── Spawn: Output ───────────────────────────────────────────────

    def print_spawn_report(self, diffs: list):
        """Print human-readable spawn diff report."""
        if not diffs:
            print("\n  [spawn] No MISSING functions to spawn.")
            return

        D = '═' * 62
        d = '─' * 58

        print(f"\n{D}")
        print(f"  SPAWN DIFFS: {len(diffs)} function(s) to create")
        print(D)

        for i, diff in enumerate(diffs, 1):
            status = diff.get('status', '?')
            func = diff.get('function', '?')
            target = diff.get('target_file', '?')
            cls = diff.get('class')
            line = diff.get('insert_after_line')
            blast = diff.get('blast_radius', 0)

            print(f"\n  ─── [{i}] {func} {'─' * max(1, 45 - len(func))}")
            print(f"  Task    : {diff.get('task_id', '?')}: {diff.get('task_title', '')[:50]}")
            also = diff.get('also_needed_by', [])
            if also:
                print(f"  Also for: {', '.join(a['task_id'] for a in also)} "
                      f"({len(also) + 1} tasks total)")
            print(f"  File    : {target}")
            if cls:
                print(f"  Class   : {cls}")
            if line:
                after = diff.get('insert_after_method', '')
                print(f"  Insert  : after line {line}"
                      f"{f' ({after})' if after else ''}")
            print(f"  Status  : {status}")

            # AoE Assessment Panel
            assess = diff.get('assess', {})
            if assess:
                risk_sum = assess.get('risk_summary', 'INFO')
                is_crit = assess.get('is_critical', False)
                hist = assess.get('history', {})
                br = assess.get('blast_radius', {})
                warnings = assess.get('warnings', [])
                vectors = assess.get('aoe_vectors', [])

                # Risk badge
                risk_badge = f"[{risk_sum}]"
                if is_crit:
                    risk_badge = f"[CRITICAL — CORE FILE]"

                print(f"\n  [AoE ASSESS] {risk_badge}")

                # History line
                tc = hist.get('total_changes', 0)
                lr = hist.get('latest_risk', 'LOW')
                lp = hist.get('latest_probe', '')
                if tc > 0:
                    probe_str = f" | probe: {lp}" if lp else ''
                    print(f"    History: {tc} changes | risk: {lr}{probe_str}")
                else:
                    print(f"    History: no enriched_changes data")

                # Risk reasons
                reasons = hist.get('risk_reasons', [])
                if reasons:
                    print(f"    Risk reasons:")
                    for r in reasons[:3]:
                        print(f"      - {r}")

                # Blast radius with names
                imp_count = br.get('importer_count', 0)
                if imp_count > 0:
                    importer_names = br.get('importers', [])
                    shown = ', '.join(importer_names[:8])
                    extra = f" +{imp_count - 8} more" if imp_count > 8 else ''
                    print(f"    Blast radius: {imp_count} importers")
                    print(f"      {shown}{extra}")

                own_imports = br.get('imports', [])
                if own_imports:
                    print(f"    Depends on: {', '.join(own_imports[:8])}")

                # AoE vector fires
                if vectors:
                    for v in vectors:
                        print(f"    AoE {{{v['level']}}} [{v['id']}]: "
                              f"'{v['display']}' = {v['value']}")

                # Warnings summary
                if warnings:
                    crits = sum(1 for w in warnings if w['level'] == 'CRITICAL')
                    risks = sum(1 for w in warnings if w['level'] == 'RISK')
                    warns = sum(1 for w in warnings if w['level'] == 'WARN')
                    parts = []
                    if crits:
                        parts.append(f"{crits} CRITICAL")
                    if risks:
                        parts.append(f"{risks} RISK")
                    if warns:
                        parts.append(f"{warns} WARN")
                    print(f"    Summary: {' | '.join(parts)}")

            # Show the diff block
            print(f"\n  {d}")
            block = diff.get('diff_block', '')
            for bl in block.split('\n'):
                print(f"  + {bl}" if bl.strip() else f"  {bl}")
            print(f"  {d}")

            # Show inferred calls
            calls = diff.get('inferred_calls', [])
            if calls:
                print(f"  Inferred calls:")
                for c in calls:
                    print(f"    {c}")

            # Show required imports
            imps = diff.get('required_imports', [])
            if imps:
                print(f"  Imports needed:")
                for imp in imps:
                    print(f"    + {imp}")

        print(f"\n{D}")
        print(f"  Total: {len(diffs)} spawn diffs | "
              f"Ready: {sum(1 for d in diffs if d['status'] == 'SPAWN_READY')} | "
              f"Bare: {sum(1 for d in diffs if d['status'] == 'SPAWN_BARE')}")
        print(D)

    def save_spawn_json(self, diffs: list, project_id: Optional[str] = None):
        """Save spawn diffs to timestamped JSON."""
        if not diffs:
            return None
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        proj = (project_id or 'all').replace(' ', '_')
        out_path = self._output_dir / f'spawn_{proj}_{ts}.json'
        out_path.write_text(
            json.dumps(diffs, indent=2, default=str, ensure_ascii=False),
            encoding='utf-8')
        print(f"  [+] Spawn diffs saved: {out_path.name}")
        return out_path

    # ══════════════════════════════════════════════════════════════════════
    #   T6-2: PROPOSE — Targeted Change Proposal for a File or Package
    # ══════════════════════════════════════════════════════════════════════

    def propose(self, target: str) -> dict:
        """Generate a targeted change proposal for a specific file or package.

        Pipeline:
          1. Resolve target → file path(s) via py_manifest
          2. Resolve project context from file overlap
          3. Collect tasks touching these files
          4. Classify proposal type (NEW/MODIFY/BUG/etc.)
          5. Detect tab profile (tkinter)
          6. Assess each file (AoE risk)
          7. Resolve skeletons + missing functions
          8. Generate spawn diffs
        """
        # Step 1: Resolve target to file list
        resolved = self._resolve_target(target)
        if not resolved:
            return {
                'target': target, 'error': f'Target "{target}" not found in py_manifest or filesystem',
                'resolved_files': [], 'items': [], 'diffs': [],
            }

        # Step 2: Resolve project
        project_id = self._resolve_project_from_files(resolved)

        # Step 3: Collect tasks touching these files
        all_tasks = self._collect_tasks(None)  # all tasks
        if not all_tasks:
            all_tasks = self._collect_tasks(project_id)
        relevant_tasks = self._filter_tasks_by_files(all_tasks, resolved)
        relevant_tasks = self._enrich_with_context(relevant_tasks)

        # Step 4: Classify proposal type
        proposal_type = self._classify_proposal_type(resolved, relevant_tasks)

        # Step 5: Tab profile per file
        tab_profiles = {}
        for f in resolved:
            tp = self._detect_tab_profile(f)
            if tp:
                tab_profiles[f] = tp

        # Step 6: Assess each file
        assessments = {}
        for f in resolved:
            assessments[f] = self.assess_file(f)

        # Step 7: Build items + resolve skeletons
        items = self._build_proposal_items(resolved, relevant_tasks)
        task_by_id = {t['id']: t for t in relevant_tasks}
        self._resolve_skeletons(items, task_by_id)

        # Step 8: Spawn diffs for MISSING functions
        diffs = self.generate_spawn_diffs({'items': items})

        # Find relevant tools
        tool_matches = self._find_relevant_tools(resolved)

        # File-level domain resolution (best-effort from imports)
        file_domains = {}
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})
        for fname in resolved:
            for fpath, meta in pm_files.items():
                if fpath.endswith('/' + fname) or fpath.endswith(fname):
                    imports = meta.get('imports', [])
                    modules = [imp.get('module', '') for imp in imports if isinstance(imp, dict)]
                    # Simple domain vote
                    domain_votes = {}
                    for mod in modules:
                        dom = self._infer_module_domain_simple(mod)
                        if dom != 'unknown':
                            domain_votes[dom] = domain_votes.get(dom, 0) + 1
                    if domain_votes:
                        file_domains[fname] = max(domain_votes, key=domain_votes.get)
                    else:
                        file_domains[fname] = 'unknown'
                    break

        # ── Gateway enrichment (T7) ───────────────────────────────
        # Step 9: Enrich task contexts (#20: capped by context_windows.task_context_top_n)
        task_contexts = {}
        _ctx_limit = getattr(self, '_task_context_top_n', 10)
        for t in relevant_tasks[:_ctx_limit]:
            tid = t.get('id', '')
            if tid:
                task_contexts[tid] = self._enrich_task_context(t)

        # Step 10: Load linked plan docs
        task_ids = [t.get('id', '') for t in relevant_tasks if t.get('id')]
        plan_docs = self._load_plan_docs(task_ids, project_id)

        # Step 11: Deterministic proposal scoring
        partial = {
            'proposal_type': proposal_type,
            'file_domains': file_domains,
            'relevant_tasks': relevant_tasks,
            'diffs': diffs,
            'assessments': assessments,
            'items': items,
        }
        proposal_score = self._compute_proposal_score(partial)

        # Step 12: Domain summary
        domain_summary = {}
        for dom in file_domains.values():
            domain_summary[dom] = domain_summary.get(dom, 0) + 1

        # Step 12.5: Semantic domain scoring (if py_manifest_augmented available)
        semantic_score = None
        try:
            import sys as _sys
            augmented_path = self._root / "Data" / "pymanifest"
            if str(augmented_path) not in _sys.path:
                _sys.path.insert(0, str(augmented_path))
            from py_manifest_augmented import PyManifestController
            pmc = PyManifestController(self._root)
            # Build a text summary of the proposal for domain classification
            summary_text = f"{target} {proposal_type} "
            summary_text += " ".join(t.get('title', '') for t in relevant_tasks[:5])
            summary_text += " " + " ".join(file_domains.values())
            classify_result = pmc.classify_and_train(summary_text, outcome='success')
            if 'error' not in classify_result:
                semantic_score = {
                    'dominant_domain': classify_result.get('dominant_domain', 'unknown'),
                    'associations': classify_result.get('associations', {}),
                    'gap_severity': classify_result.get('gap_severity', 'unknown'),
                    'understanding_pct': classify_result.get('understanding_pct', 0),
                    'recognized_ratio': classify_result.get('recognized_ratio', 0),
                }
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Semantic scoring skipped: {e}")

        # Step 13: Gateway status
        gateway = self._compute_gateway_status(partial, proposal_score)
        gateway['linked_plans'] = len(plan_docs.get('task_plans', []))

        return {
            'target': target,
            'resolved_files': resolved,
            'project_id': project_id,
            'proposal_type': proposal_type,
            'generated_at': datetime.now().isoformat(),
            'tab_profiles': tab_profiles,
            'file_domains': file_domains,
            'domain_summary': domain_summary,
            'assessments': assessments,
            'relevant_tasks': relevant_tasks,
            'task_contexts': task_contexts,
            'plan_docs': plan_docs,
            'proposal_score': proposal_score,
            'semantic_score': semantic_score,
            'gateway_status': gateway,
            'items': items,
            'diffs': diffs,
            'tool_matches': tool_matches,
        }

    # ── Propose helper methods ───────────────────────────────────────────

    def _resolve_target(self, target: str) -> list:
        """Resolve a filename, partial path, or package dir to file basenames.
        Skips backup directory files to avoid noise."""
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})
        target_norm = target.replace('\\', '/').rstrip('/')
        matches = set()

        for fpath in pm_files:
            # Skip backup directory entries
            if '/backup/' in fpath or '/backups/' in fpath:
                continue
            basename = fpath.rsplit('/', 1)[-1] if '/' in fpath else fpath
            # Exact basename match
            if basename == target_norm or fpath.endswith('/' + target_norm):
                matches.add(basename)
            # Directory/package match
            elif f'/{target_norm}/' in fpath:
                matches.add(basename)

        # If no matches, try fuzzy stem matching (still skip backups)
        if not matches:
            target_stem = target_norm.replace('.py', '').lower()
            for fpath in pm_files:
                if '/backup/' in fpath or '/backups/' in fpath:
                    continue
                basename = fpath.rsplit('/', 1)[-1] if '/' in fpath else fpath
                stem = basename.replace('.py', '').lower()
                if target_stem in stem or stem in target_stem:
                    matches.add(basename)
                    if len(matches) >= 20:
                        break

        return sorted(matches)

    def _resolve_project_from_files(self, target_files: list) -> Optional[str]:
        """Find project whose key_files best overlap with target files."""
        if not self._projects_path.exists():
            return self._get_active_project()
        try:
            data = json.loads(self._projects_path.read_text(encoding='utf-8'))
            projects = data.get('projects', [])
        except Exception:
            return self._get_active_project()

        best_project = None
        best_score = 0

        for proj in projects:
            key_files = proj.get('key_files', [])
            if not key_files:
                continue
            key_basenames = {Path(kf).name for kf in key_files}
            score = len(key_basenames & set(target_files))
            # Partial path containment bonus
            for tf in target_files:
                for kf in key_files:
                    if tf in kf or kf.endswith(tf):
                        score += 0.5
            if score > best_score:
                best_score = score
                best_project = proj.get('project_id')

        return best_project or self._get_active_project()

    def _filter_tasks_by_files(self, tasks: list, target_files: list) -> list:
        """Find tasks whose wherein, changes, expected_diffs, or title touch target files."""
        target_set = {f.lower() for f in target_files}
        # Also build stem set for title matching (e.g. "planner_tab" matches planner_tab.py)
        target_stems = {f.replace('.py', '').lower() for f in target_files}
        seen_ids = set()
        matched = []

        def _add(task):
            tid = task.get('id', '')
            if tid not in seen_ids:
                seen_ids.add(tid)
                matched.append(task)

        for t in tasks:
            tid = t.get('id', '')
            # Check wherein
            wherein = t.get('wherein', '')
            if isinstance(wherein, str) and wherein.lower() in target_set:
                _add(t)
                continue

            # Check title for file stem references
            title = t.get('title', '').lower()
            if any(stem in title for stem in target_stems if len(stem) >= 4):
                _add(t)
                continue

            # Check task_context: changes, expected_diffs, files
            ctx_path = self._tasks_dir / f'task_context_{tid}.json'
            if ctx_path.exists():
                try:
                    ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
                    # changes[].file
                    for ch in ctx.get('changes', []):
                        ch_file = Path(ch.get('file', '')).name.lower()
                        if ch_file and ch_file in target_set:
                            _add(t)
                            break
                    if tid in seen_ids:
                        continue
                    # expected_diffs[].file
                    for ed in ctx.get('expected_diffs', []):
                        ed_file = Path(ed.get('file', '')).name.lower()
                        if ed_file and ed_file in target_set:
                            _add(t)
                            break
                except Exception:
                    pass
        return matched

    def _classify_proposal_type(self, files: list, tasks: list) -> str:
        """Classify proposal type using checklist task_types taxonomy."""
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})

        # Check if files exist in manifest
        files_in_manifest = 0
        for tf in files:
            for fpath in pm_files:
                if fpath.endswith(tf):
                    files_in_manifest += 1
                    break

        if files_in_manifest == 0:
            return 'NEW'

        # Check for BUG tasks
        bug_count = sum(1 for t in tasks
                        if 'bug' in t.get('title', '').lower()
                        or t.get('status', '').upper() in ('BUG',))
        if bug_count > 0 and bug_count >= len(tasks) / 2:
            return 'BUG'

        # Check task statuses
        active = sum(1 for t in tasks
                     if t.get('status', '').upper() in STATUS_ACTIVE)
        if active > 0:
            return 'MODIFY'

        return 'MODIFY'

    def _detect_tab_profile(self, filename: str) -> Optional[dict]:
        """Detect if file is a tkinter tab and return profile info."""
        pm = self._load_pymanifest_cached()
        pm_files = pm.get('files', {})

        for fpath, meta in pm_files.items():
            if not fpath.endswith(filename):
                continue
            if not isinstance(meta, dict):
                continue

            is_tab = False
            packages = set()
            for imp in meta.get('imports', []):
                if not isinstance(imp, dict):
                    continue
                mod = imp.get('module', '')
                ext_pkg = imp.get('external_package', '') or ''
                if 'tkinter' in mod or 'tkinter' in ext_pkg or 'ttk' in mod:
                    is_tab = True
                    packages.add('tkinter')
                if ext_pkg:
                    packages.add(ext_pkg)

            # Check class bases
            classes_info = []
            for cls in meta.get('classes', []):
                if not isinstance(cls, dict):
                    continue
                cname = cls.get('name', '')
                bases = cls.get('bases', [])
                methods = cls.get('methods', [])
                for base in bases:
                    if base in ('BaseTab', 'ttk.Frame', 'tk.Frame', 'tk.Toplevel', 'Frame'):
                        is_tab = True
                classes_info.append({
                    'name': cname,
                    'bases': bases,
                    'method_count': len(methods),
                })

            if is_tab:
                return {
                    'is_tab': True,
                    'classes': classes_info,
                    'packages': sorted(packages),
                    'method_count': sum(c['method_count'] for c in classes_info),
                }
            return None
        return None

    def _find_relevant_tools(self, target_files: list) -> list:
        """Find tools from consolidated_menu that relate to target files."""
        menu_path = (self._root / 'Data' / 'tabs' / 'action_panel_tab' /
                     'babel_data' / 'inventory' / 'consolidated_menu.json')
        if not menu_path.exists():
            return []
        try:
            menu = json.loads(menu_path.read_text(encoding='utf-8'))
            tools = menu.get('tools', [])
        except Exception:
            return []

        matches = []
        seen_names = set()
        file_stems = {f.replace('.py', '').lower() for f in target_files}

        for tool in tools:
            if not isinstance(tool, dict):
                continue
            tool_name = tool.get('display_name', '').lower()
            tool_cmd = tool.get('command', '').lower()
            display = tool.get('display_name', '')
            if display in seen_names:
                continue
            for stem in file_stems:
                if stem in tool_name or stem in tool_cmd or tool_name in stem:
                    seen_names.add(display)
                    matches.append({
                        'tool_id': tool.get('tool_id', tool.get('id', '')),
                        'display_name': display,
                        'category': tool.get('category', ''),
                    })
                    break
        return matches[:10]

    def _build_proposal_items(self, files: list, tasks: list) -> list:
        """Build roadmap-style items for the proposal from relevant tasks."""
        items = []
        for t in tasks:
            status_str = t.get('status', 'PENDING').upper()
            if status_str in STATUS_DONE:
                continue  # skip done tasks in proposals

            item = {
                'priority': 'P3' if status_str in STATUS_ACTIVE else 'P4',
                'type': 'partial_task' if status_str in STATUS_ACTIVE else 'ready_task',
                'task_id': t.get('id', ''),
                'title': t.get('title', ''),
                'status': status_str,
                'phase': t.get('phase', ''),
                'reason': f'Touches {", ".join(files[:3])}',
            }

            # Attach context if available
            ctx = t.get('_context', {})
            if ctx:
                cs = ctx.get('completion_signals', {})
                item['changes_count'] = cs.get('changes_count', 0)
                item['expected_total'] = len(ctx.get('expected_diffs', []))
                item['expected_matched'] = cs.get('diffs_matched', 0)

            items.append(item)
        return items

    @staticmethod
    def _infer_module_domain_simple(module_name: str) -> str:
        """Quick module→domain using inline map (no external import needed)."""
        _map = {
            'tkinter': 'gui', 'ttk': 'gui', 'matplotlib': 'gui', 'PIL': 'gui',
            'json': 'serialization', 'pickle': 'serialization', 'yaml': 'serialization',
            'os': 'system', 'sys': 'system', 'subprocess': 'system', 'pathlib': 'file_io',
            'shutil': 'file_io', 'io': 'file_io', 'socket': 'network', 'http': 'network',
            'requests': 'network', 'math': 'math', 'numpy': 'math', 're': 'nlp',
            'string': 'nlp', 'unittest': 'testing', 'pytest': 'testing',
            'argparse': 'config', 'logging': 'logging', 'hashlib': 'data',
            'collections': 'data', 'itertools': 'data', 'threading': 'system',
            'ast': 'system', 'importlib': 'system', 'typing': 'system',
            'datetime': 'system', 'time': 'system',
        }
        if module_name in _map:
            return _map[module_name]
        prefix = module_name.split('.')[0]
        return _map.get(prefix, 'unknown')

    # ── Gateway enrichment methods ────────────────────────────────────────

    def _enrich_task_context(self, task: dict) -> dict:
        """Load full task_context for a task and extract key fields."""
        tid = task.get('id', '')
        ctx_path = self._tasks_dir / f'task_context_{tid}.json'
        result = {'task_id': tid}
        if not ctx_path.exists():
            return result
        try:
            ctx = json.loads(ctx_path.read_text(encoding='utf-8'))
        except Exception:
            return result

        # _temporal fields — structure varies: may have dominant_domain OR backup_count
        temporal = ctx.get('_temporal', {})
        if temporal:
            result['dominant_domain'] = temporal.get('dominant_domain', '')
            result['domain_confidence'] = temporal.get('domain_confidence', 0)
            result['phase_name'] = temporal.get('phase_name', '')
            result['files_touched'] = temporal.get('files_touched_count', 0)
            # Alternate temporal format (backup_count, activity_score, first/last_seen)
            result['backup_count'] = temporal.get('backup_count', 0)
            result['activity_score'] = temporal.get('activity_score', 0)
            result['first_seen'] = temporal.get('first_seen', '')
            result['last_seen'] = temporal.get('last_seen', '')

        # metastate
        ms = ctx.get('metastate', {})
        if ms:
            result['gap_severity'] = ms.get('gap_severity', '')
            result['recommended_action'] = ms.get('recommended_action', '')

        # completion signals
        cs = ctx.get('completion_signals', {})
        if cs:
            result['signals_met'] = cs.get('diffs_matched', 0)
            result['signals_total'] = cs.get('total_expected', 0)

        # expected diffs
        ed = ctx.get('expected_diffs', [])
        if ed:
            result['expected_diffs'] = [
                {'file': d.get('file', ''), 'functions': d.get('functions', [])}
                for d in ed[:10]
            ]

        # recent changes (last 5)
        changes = ctx.get('changes', [])
        if changes:
            result['recent_changes'] = len(changes)
            last = changes[-1] if changes else {}
            result['last_change_ts'] = last.get('timestamp', last.get('event_id', ''))

        # blame
        blame = ctx.get('blame', {})
        if blame:
            result['blame'] = blame

        return result

    def _load_plan_docs(self, task_ids: list, project_id: str) -> dict:
        """Discover morph plan docs, epic docs, and project info for matched tasks."""
        result = {'task_plans': [], 'epic': None, 'project': None}

        # 1. Morph plans per task
        morph_dir = self._plans / 'Morph'
        if morph_dir.exists():
            for tid in task_ids:
                pattern = f'morph_plan_{tid}*'
                matches = sorted(morph_dir.glob(pattern))
                if matches:
                    plan_path = matches[-1]  # latest
                    try:
                        lines = plan_path.read_text(encoding='utf-8').splitlines()[:50]
                        summary = '\n'.join(lines)
                    except Exception:
                        summary = '(could not read)'
                    result['task_plans'].append({
                        'task_id': tid,
                        'path': plan_path.name,
                        'summary': summary,
                    })

        # 2. Epic doc
        if project_id:
            epics_dir = self._plans / 'Epics'
            if epics_dir.exists():
                epic_path = epics_dir / f'{project_id}.md'
                if epic_path.exists():
                    try:
                        lines = epic_path.read_text(encoding='utf-8').splitlines()[:30]
                        result['epic'] = {
                            'path': epic_path.name,
                            'summary': '\n'.join(lines),
                        }
                    except Exception:
                        pass

        # 3. Project info from projects.json
        if project_id and self._projects_path.exists():
            try:
                data = json.loads(self._projects_path.read_text(encoding='utf-8'))
                for proj in data.get('projects', []):
                    if proj.get('project_id') == project_id:
                        result['project'] = {
                            'id': project_id,
                            'description': proj.get('description', ''),
                            'key_files': proj.get('key_files', []),
                            'plan_ref': proj.get('plan_ref', ''),
                        }
                        break
            except Exception:
                pass

        return result

    def _compute_proposal_score(self, proposal: dict) -> dict:
        """Deterministic proposal quality score from grounded data."""
        assessments = proposal.get('assessments', {})
        tasks = proposal.get('relevant_tasks', [])
        diffs = proposal.get('diffs', [])
        items = proposal.get('items', [])

        # 1. AoE risk score (0-1, higher = riskier)
        risk_map = {'CRITICAL': 1.0, 'RISK': 0.7, 'WARN': 0.4, 'INFO': 0.1}
        aoe_risk = max((risk_map.get(a.get('risk_summary', 'INFO'), 0)
                        for a in assessments.values()), default=0)

        # 2. Blast radius score (normalized)
        total_deps = sum(a.get('blast_radius', {}).get('importer_count', 0)
                         for a in assessments.values())
        blast_norm = min(total_deps / 20.0, 1.0)

        # 3. Completion coverage
        done_tasks = sum(1 for t in tasks if t.get('status', '').upper() in STATUS_DONE)
        coverage = done_tasks / len(tasks) if tasks else 0

        # 4. Missing function ratio
        missing = len(diffs)
        total_funcs = sum(len(it.get('spawn_spec', {}).get('skeletons', []))
                          for it in items)
        missing_ratio = missing / max(total_funcs, 1)

        # 5. Bug pressure
        bug_count = sum(1 for t in tasks if 'bug' in t.get('title', '').lower())

        # Composite risk weight
        risk_weight = (aoe_risk * 0.30 + blast_norm * 0.20 +
                       missing_ratio * 0.25 + (1 - coverage) * 0.15 +
                       min(bug_count / 3.0, 1.0) * 0.10)

        return {
            'risk_weight': round(risk_weight, 3),
            'aoe_risk': round(aoe_risk, 2),
            'blast_radius_norm': round(blast_norm, 3),
            'completion_coverage': round(coverage, 3),
            'missing_ratio': round(missing_ratio, 3),
            'bug_pressure': bug_count,
            'total_dependents': total_deps,
        }

    def _compute_gateway_status(self, proposal: dict, score: dict) -> dict:
        """Compute gateway status from deterministic proposal score."""
        rw = score.get('risk_weight', 0)
        aoe = score.get('aoe_risk', 0)
        missing = len(proposal.get('diffs', []))
        bug_count = score.get('bug_pressure', 0)
        total_deps = score.get('total_dependents', 0)

        # Determine AoE label
        if aoe >= 1.0:
            aoe_label = 'CRITICAL'
        elif aoe >= 0.7:
            aoe_label = 'RISK'
        elif aoe >= 0.4:
            aoe_label = 'WARN'
        else:
            aoe_label = 'INFO'

        # Gateway thresholds on risk_weight
        if rw >= 0.75 or (aoe >= 1.0 and missing > 3):
            status = 'BLOCKED'
            action = 'Resolve critical AoE risks and missing functions before changes'
        elif rw >= 0.50 or aoe >= 1.0 or missing > 5:
            status = 'CAUTION'
            action = 'Review AoE dependencies and spawn diffs carefully before proceeding'
        elif rw >= 0.25 or aoe >= 0.7 or missing > 2:
            status = 'REVIEW'
            action = 'Review spawn diffs and check AoE dependents before changes'
        else:
            status = 'CLEAR'
            action = 'Safe to proceed with proposed changes'

        return {
            'status': status,
            'action': action,
            'risk_weight': rw,
            'aoe_risk': aoe_label,
            'total_dependents': total_deps,
            'missing_functions': missing,
            'spawn_diffs_available': missing,
            'linked_plans': 0,  # filled by caller
            'open_bugs': bug_count,
        }

    # ── Proposal output ──────────────────────────────────────────────────

    def print_proposal_report(self, proposal: dict):
        """Print formatted change proposal report."""
        if proposal.get('error'):
            print(f"\n  [ERROR] {proposal['error']}\n")
            return

        target = proposal.get('target', '?')
        ptype = proposal.get('proposal_type', '?')
        project = proposal.get('project_id', '?')
        ts = proposal.get('generated_at', '')
        files = proposal.get('resolved_files', [])
        tasks = proposal.get('relevant_tasks', [])
        diffs = proposal.get('diffs', [])
        assessments = proposal.get('assessments', {})
        tab_profiles = proposal.get('tab_profiles', {})
        file_domains = proposal.get('file_domains', {})
        tools = proposal.get('tool_matches', [])

        W = 62
        print()
        print('═' * W)
        print(f"  CHANGE PROPOSAL: {target}")
        print(f"  Type: {ptype} | Project: {project}")
        print(f"  Generated: {ts}")
        print('═' * W)

        # ── File profiles ────────────────────────────────────────────
        print(f"\n  ─── FILE PROFILE ({len(files)} file{'s' if len(files) != 1 else ''}) {'─' * max(0, W - 28)}")
        for fname in files[:10]:
            parts = []
            tp = tab_profiles.get(fname)
            if tp:
                classes = ', '.join(c['name'] for c in tp.get('classes', []))
                parts.append(f"Tab: Yes (tkinter) | Classes: {classes} | Methods: {tp.get('method_count', 0)}")
            dom = file_domains.get(fname, '')
            if dom and dom != 'unknown':
                parts.append(f"Domain: {dom}")
            pkgs = tp.get('packages', []) if tp else []
            if pkgs:
                parts.append(f"Packages: {', '.join(pkgs[:5])}")

            assess = assessments.get(fname, {})
            risk = assess.get('risk_summary', '')
            warnings = assess.get('warnings', [])

            print(f"  [{fname}]")
            for p in parts:
                print(f"    {p}")

            if risk and risk != 'INFO':
                warn_msgs = [w.get('message', '') for w in warnings[:3]]
                print(f"    AoE: [{risk}] {'; '.join(warn_msgs)}")
            elif not parts:
                print(f"    (no profile data)")

        # ── Relevant tasks ───────────────────────────────────────────
        if tasks:
            print(f"\n  ─── RELEVANT TASKS ({len(tasks)}) {'─' * max(0, W - 28)}")
            for i, t in enumerate(tasks[:10], 1):
                status = t.get('status', '?')
                print(f"  [{i}] {t.get('id', '?')}: {t.get('title', '?')} [{status}]")

        # ── Items with skeletons ─────────────────────────────────────
        items = proposal.get('items', [])
        items_with_spawn = [it for it in items if it.get('spawn_spec', {}).get('skeletons')]
        if items_with_spawn:
            total_missing = sum(1 for it in items_with_spawn
                                for s in it.get('spawn_spec', {}).get('skeletons', [])
                                if s.get('status') == 'MISSING')
            total_exists = sum(1 for it in items_with_spawn
                               for s in it.get('spawn_spec', {}).get('skeletons', [])
                               if s.get('status') == 'EXISTS')
            print(f"\n  ─── FUNCTION ANALYSIS {'─' * max(0, W - 26)}")
            print(f"  EXISTS: {total_exists} | MISSING: {total_missing}")
            for it in items_with_spawn[:5]:
                sp = it.get('spawn_spec', {})
                skels = sp.get('skeletons', [])
                tfiles = sp.get('target_files', [])
                tf_display = tfiles[0] if tfiles else '?'
                missing = [s for s in skels if s.get('status') == 'MISSING']
                if missing:
                    for s in missing[:3]:
                        print(f"    MISSING: {s.get('name', '?')} in {s.get('target_file', tf_display)}")

        # ── Spawn diffs ──────────────────────────────────────────────
        if diffs:
            print(f"\n  ─── SPAWN DIFFS ({len(diffs)}) {'─' * max(0, W - 24)}")
            for d in diffs[:5]:
                func = d.get('function', '?')
                tfile = d.get('target_file', '?')
                sig = d.get('signature', '')
                also = d.get('also_needed_by', [])
                print(f"  [{func}] in {tfile}")
                if sig:
                    print(f"    {sig}")
                if also:
                    names = [a.get('task_id', '') for a in also]
                    print(f"    Also needed by: {', '.join(names)} ({len(also) + 1} tasks total)")

                assess = d.get('assess', {})
                risk = assess.get('risk_summary', '')
                if risk and risk not in ('INFO', ''):
                    print(f"    AoE: [{risk}]")

        # ── Related tools ────────────────────────────────────────────
        if tools:
            print(f"\n  ─── RELATED TOOLS {'─' * max(0, W - 22)}")
            tool_strs = [f"{t['display_name']} ({t['category']})" for t in tools[:5]]
            print(f"  {' | '.join(tool_strs)}")

        # ── Linked plans (T7) ──────────────────────────────────────
        plan_docs = proposal.get('plan_docs', {})
        task_plans = plan_docs.get('task_plans', [])
        epic = plan_docs.get('epic')
        proj_info = plan_docs.get('project')

        if task_plans or epic:
            print(f"\n  ─── LINKED PLANS {'─' * max(0, W - 21)}")
            if epic:
                # Skip XML/template tags to find first meaningful line
                summary_line = ''
                for line in epic.get('summary', '').split('\n'):
                    stripped = line.strip()
                    if stripped and not stripped.startswith('<') and not stripped.startswith('#'):
                        summary_line = stripped[:60]
                        break
                if not summary_line:
                    summary_line = epic.get('path', '?')
                print(f"  [Epic] {epic.get('path', '?')} — {summary_line}")
            for tp in task_plans[:5]:
                print(f"  [Plan] {tp['task_id']} — {tp['path']}")

        # ── Project context (T7) ──────────────────────────────────
        if proj_info:
            print(f"\n  ─── PROJECT CONTEXT {'─' * max(0, W - 24)}")
            desc = proj_info.get('description', '')[:60]
            kf_count = len(proj_info.get('key_files', []))
            print(f"  Project: {proj_info.get('id', '?')} | Key files: {kf_count}")
            if desc:
                print(f"  Description: \"{desc}\"")
            plan_ref = proj_info.get('plan_ref', '')
            if plan_ref:
                print(f"  Plan ref: {plan_ref}")

        # ── Proposal score (T8) ───────────────────────────────────
        ps = proposal.get('proposal_score', {})
        if ps:
            print(f"\n  ─── PROPOSAL SCORE {'─' * max(0, W - 23)}")
            rw = ps.get('risk_weight', 0)
            aoe_s = ps.get('aoe_risk', 0)
            blast = ps.get('blast_radius_norm', 0)
            cov = ps.get('completion_coverage', 0)
            miss_r = ps.get('missing_ratio', 0)
            bugs_p = ps.get('bug_pressure', 0)
            print(f"  Risk: {rw:.2f} | AoE: {aoe_s:.1f} | Blast: {blast:.2f} | "
                  f"Coverage: {cov:.0%} | Missing: {miss_r:.0%}")
            if bugs_p:
                print(f"  Bug pressure: {bugs_p} open")

        # ── Task context (T7/T8) ─────────────────────────────────
        task_contexts = proposal.get('task_contexts', {})
        # Show any task with useful data (temporal OR changes)
        enriched = {tid: ctx for tid, ctx in task_contexts.items()
                    if ctx.get('dominant_domain') or ctx.get('signals_total')
                    or ctx.get('recent_changes') or ctx.get('activity_score')}
        if enriched:
            print(f"\n  ─── TASK CONTEXT ({len(enriched)}) {'─' * max(0, W - 25)}")
            for tid, ctx in list(enriched.items())[:5]:
                parts = []
                # Temporal: use actual fields (backup_count, activity_score, first/last_seen)
                dom = ctx.get('dominant_domain', '')
                if dom:
                    conf = ctx.get('domain_confidence', 0)
                    parts.append(f"Domain: {dom} ({conf:.2f})" if conf else f"Domain: {dom}")
                phase = ctx.get('phase_name', '')
                if phase:
                    parts.append(f"Phase: {phase}")
                act = ctx.get('activity_score', 0)
                backups = ctx.get('backup_count', 0)
                if act or backups:
                    parts.append(f"Activity: {act:.1f}" if act else f"Backups: {backups}")
                print(f"  [{tid}] {' | '.join(parts) if parts else '(minimal data)'}")

                sig_met = ctx.get('signals_met', 0)
                sig_total = ctx.get('signals_total', 0)
                ed = ctx.get('expected_diffs', [])
                if sig_total:
                    print(f"    Completion: {sig_met}/{sig_total} signals met | "
                          f"Expected diffs: {len(ed)} files")
                changes = ctx.get('recent_changes', 0)
                last_ts = ctx.get('last_change_ts', '')
                if changes:
                    print(f"    Recent: {changes} changes (last: {last_ts[:10] if last_ts else '?'})")

        # ── Gateway status (T8) ───────────────────────────────────
        gw = proposal.get('gateway_status', {})
        gw_status = gw.get('status', '?')
        print()
        print('═' * W)
        print(f"  GATEWAY STATUS: {gw_status}")
        print('─' * W)
        aoe = gw.get('aoe_risk', 'INFO')
        deps = gw.get('total_dependents', 0)
        rw = gw.get('risk_weight', 0)
        miss = gw.get('missing_functions', 0)
        spawns = gw.get('spawn_diffs_available', 0)
        plans = gw.get('linked_plans', 0)
        bugs = gw.get('open_bugs', 0)
        print(f"  AoE: {aoe}"
              + (f" ({deps} dependents)" if deps else "")
              + f" | Risk: {rw:.2f}"
              + f" | Missing: {miss} functions")
        print(f"  Spawn diffs: {spawns} | Linked plans: {plans} | Open bugs: {bugs}")
        print(f"  Action: {gw.get('action', 'N/A')}")

        # Semantic domain score (T9)
        sem = proposal.get('semantic_score')
        if sem:
            print('─' * W)
            print(f"  SEMANTIC: domain={sem.get('dominant_domain', '?')} "
                  f"| gap={sem.get('gap_severity', '?')} "
                  f"| recognized={sem.get('recognized_ratio', 0):.1%} "
                  f"| understanding={sem.get('understanding_pct', 0):.1f}%")

        print('═' * W)
        print()

    def save_proposal_json(self, proposal: dict, target: str = None):
        """Save proposal to timestamped JSON (includes gateway enrichment)."""
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        tgt = (target or proposal.get('target', 'unknown')).replace('/', '_').replace('.', '_')
        out_path = self._output_dir / f'proposal_{tgt}_{ts}.json'
        # Make JSON-serializable
        save_data = dict(proposal)
        if 'relevant_tasks' in save_data and save_data['relevant_tasks']:
            save_data['relevant_tasks'] = [
                {'id': t.get('id', ''), 'title': t.get('title', ''), 'status': t.get('status', '')}
                for t in save_data['relevant_tasks']
            ]
        # Truncate plan doc summaries for JSON size
        pd = save_data.get('plan_docs', {})
        if pd:
            for tp in pd.get('task_plans', []):
                s = tp.get('summary', '')
                if len(s) > 500:
                    tp['summary'] = s[:500] + '...'
            epic = pd.get('epic')
            if epic and len(epic.get('summary', '')) > 300:
                epic['summary'] = epic['summary'][:300] + '...'
        out_path.write_text(
            json.dumps(save_data, indent=2, default=str, ensure_ascii=False),
            encoding='utf-8')
        print(f"  [+] Proposal saved: {out_path.name}")
        return out_path
