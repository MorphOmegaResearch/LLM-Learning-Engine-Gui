"""
unified_context_index.py — UnifiedContextIndex
Aggregates per-file facts from all catalog systems into one queryable entity model.

Sources aggregated per file:
  1. version_manifest.json   → enriched_changes, versions, change_states, probe history
  2. consolidated_menu.json  → onboarder tool entries that own / reference the file
  3. py_manifest_augmented.json → AST: classes, functions, imports, call graph
  4. history_temporal_manifest.json → activity_score, backup_count, cluster info
  5. provisions_catalog.json → packages (matched via py_manifest imports)
  6. plans/Tasks/task_context_*.json → task_ids[], wherein matches, metastate

CLI:
  python3 unified_context_index.py --build
  python3 unified_context_index.py --show <file>
  python3 unified_context_index.py --search <term>
  python3 unified_context_index.py --graph <file>
  python3 unified_context_index.py --chain <file> <function>
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path constants (resolved from this file's location)
# ---------------------------------------------------------------------------
_SCRIPTS_DIR  = Path(__file__).resolve().parent          # .../scripts/
_ACTION_DIR   = _SCRIPTS_DIR.parents[3]                  # .../action_panel_tab/
_TRAINER_ROOT = _ACTION_DIR.parents[2]                   # .../Trainer/

_MANIFEST_PATH       = _TRAINER_ROOT / "Data" / "backup" / "version_manifest.json"
_TEMPORAL_PATH       = _ACTION_DIR / "babel_data" / "timeline" / "manifests" / "history_temporal_manifest.json"
_PY_MANIFEST_PATH    = _TRAINER_ROOT / "Data" / "pymanifest" / "py_manifest_augmented.json"
_MENU_PATH           = _ACTION_DIR / "babel_data" / "inventory" / "consolidated_menu.json"
_PROVISIONS_PATH     = _ACTION_DIR / "babel_data" / "inventory" / "provisions_catalog.json"
_TASK_CTX_DIR        = _TRAINER_ROOT / "Data" / "plans" / "Tasks"
_INDEX_CACHE_PATH    = _ACTION_DIR / "babel_data" / "index" / "unified_entity_index.json"


# ---------------------------------------------------------------------------
# Helper: backup-key → relative path (e.g. "Data_tabs_..._planner_tab.py")
# ---------------------------------------------------------------------------
def _backup_key_to_rel_path(key: str, trainer_root: Path) -> str | None:
    """
    Convert a temporal-manifest backup key (underscore-as-separator) to a
    relative path from trainer_root.  Strategy: try every underscore as a
    possible path separator and return the first candidate that exists on disk.
    Searches in order from rightmost (shortest filename) to leftmost.
    """
    positions = [i for i, c in enumerate(key) if c == '_']
    for pos in reversed(positions):
        dir_raw  = key[:pos]
        file_raw = key[pos + 1:]
        # Replace only leading path separators (treat _-separated prefix as path)
        # dir_raw still has _ where directory names have _, so we must try all splits
        # of dir_raw too.  For simplicity: replace ALL _ in dir_raw with /
        dir_part = dir_raw.replace('_', '/')
        candidate = dir_part + '/' + file_raw
        if (trainer_root / candidate).is_file():
            return candidate
    # Fallback: maybe key has no prefix (just a filename)
    if (trainer_root / key).is_file():
        return key
    return None


def _basename_match(backup_key: str, basename: str) -> bool:
    """True if backup_key ends with basename or '_' + basename."""
    return backup_key == basename or backup_key.endswith('_' + basename)


def _normalize_wherein(wherein: str, trainer_root: Path) -> str:
    """
    Normalize a task_context wherein path to a canonical relative path
    (relative to trainer_root, starting with Data/ where applicable).

    Handles:
      'planner_tab.py'                                          → resolved by filesystem search
      'tabs/ag_forge_tab/.../planner_tab.py'                   → 'Data/tabs/...'
      'Data/tabs/ag_forge_tab/.../planner_tab.py'              → unchanged
      'Data/tabs/action_panel_tab/Os_Toolkit.py'               → unchanged
    """
    w = wherein.lstrip('/')
    # Already canonical
    if (trainer_root / w).exists():
        return w
    # Try prepending 'Data/'
    candidate = 'Data/' + w
    if (trainer_root / candidate).exists():
        return candidate
    # Just a basename: search under trainer_root/Data
    basename = Path(w).name
    if '/' not in w and basename:
        data_dir = trainer_root / 'Data'
        matches = list(data_dir.rglob(basename)) if data_dir.exists() else []
        if len(matches) == 1:
            try:
                return str(matches[0].relative_to(trainer_root))
            except ValueError:
                pass
        if len(matches) > 1:
            # Prefer match with most path components (deepest, most specific)
            best = max(matches, key=lambda p: len(p.parts))
            try:
                return str(best.relative_to(trainer_root))
            except ValueError:
                pass
    return w  # fallback: return as-is


# ---------------------------------------------------------------------------
# Helper: simple AST call extraction
# ---------------------------------------------------------------------------
def _extract_calls_from_source(source: str) -> dict[str, list[str]]:
    """
    Parse Python source and return {function_name: [called_names]}.
    Safe: returns {} on any parse error.
    """
    result: dict[str, list[str]] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        if calls:
            result[node.name] = calls
    return result


# ---------------------------------------------------------------------------
# UnifiedContextIndex
# ---------------------------------------------------------------------------
class UnifiedContextIndex:
    """
    Aggregates all per-file catalog data into entity records.
    Cache written to babel_data/index/unified_entity_index.json.
    """

    def __init__(self, trainer_root: Path | None = None):
        self.trainer_root = Path(trainer_root) if trainer_root else _TRAINER_ROOT
        self._index: dict[str, dict] = {}   # rel_path → EntityRecord
        self._built = False
        self._cache_path = _INDEX_CACHE_PATH

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def build(self, force: bool = False) -> None:
        """Build the unified index from all sources and cache to disk."""
        if self._built and not force:
            return

        print("[UnifiedContextIndex] Building entity index…")

        # ---- 1. version_manifest ----
        ec_by_file: dict[str, list[dict]] = defaultdict(list)
        cs_by_event: dict[str, dict] = {}
        event_pools: dict[str, list[str]] = {}
        versions_by_file: dict[str, list[str]] = defaultdict(list)

        if _MANIFEST_PATH.exists():
            try:
                vm = json.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))
                ec_all = vm.get('enriched_changes', {})
                for eid, ec in ec_all.items():
                    rel = ec.get('file', '')
                    if rel:
                        ec_by_file[rel].append({**ec, 'event_id': eid})
                cs_by_event = vm.get('change_states', {})
                event_pools = vm.get('event_pools', {})
                # versions: which files changed in each version
                for vts, vdata in vm.get('versions', {}).items():
                    for fpath in vdata.get('files_changed', []):
                        versions_by_file[fpath].append(vts)
                print(f"  version_manifest: {len(ec_all)} events, {len(ec_by_file)} unique files")
            except Exception as exc:
                print(f"  [WARN] version_manifest load failed: {exc}")

        # ---- 2. temporal manifest ----
        temporal_profiles: dict[str, dict] = {}
        if _TEMPORAL_PATH.exists():
            try:
                tm = json.loads(_TEMPORAL_PATH.read_text(encoding='utf-8'))
                temporal_profiles = tm.get('profiles', {})
                print(f"  temporal_manifest: {len(temporal_profiles)} profiles")
            except Exception as exc:
                print(f"  [WARN] temporal_manifest load failed: {exc}")

        # Build basename → temporal_key lookup
        temporal_by_basename: dict[str, dict] = {}
        for tkey, tdata in temporal_profiles.items():
            # Extract likely basename: part after last underscore that has .py
            # Use longest suffix that looks like a filename
            if '.' in tkey:
                for i, c in enumerate(tkey):
                    if c == '_' or i == 0:
                        suffix = tkey[i + 1:] if c == '_' else tkey
                        if suffix.endswith('.py') and '_' not in suffix.split('.')[0]:
                            # Could be a basename (no more underscores in stem)
                            pass
                # Simpler: take everything after last _ that contains .py
                basename = tkey.rsplit('_', 1)[-1] if '_' in tkey else tkey
                if basename not in temporal_by_basename:
                    temporal_by_basename[basename] = tdata
                # Also store by full key for later lookup
                temporal_by_basename[tkey] = tdata

        # ---- 3. py_manifest_augmented ----
        ast_by_file: dict[str, dict] = {}   # abs_path → {classes, functions, imports}
        if _PY_MANIFEST_PATH.exists():
            try:
                pm = json.loads(_PY_MANIFEST_PATH.read_text(encoding='utf-8'))
                files_pm = pm.get('files', {})
                for abs_path, fdata in files_pm.items():
                    # Normalize to relative from trainer_root
                    try:
                        rel = str(Path(abs_path).relative_to(self.trainer_root))
                    except ValueError:
                        rel = abs_path
                    classes = [c.get('name', '') for c in fdata.get('classes', [])
                               if isinstance(c, dict)]
                    functions = [f.get('name', '') for f in fdata.get('functions', [])
                                 if isinstance(f, dict)]
                    imports = list({imp.get('module', imp.get('name', ''))
                                    for imp in fdata.get('imports', [])
                                    if isinstance(imp, dict)})
                    ast_by_file[rel] = {
                        'classes':   classes,
                        'functions': functions,
                        'imports':   imports,
                        'abs_path':  abs_path,
                    }
                print(f"  py_manifest_augmented: {len(ast_by_file)} files indexed")
            except Exception as exc:
                print(f"  [WARN] py_manifest_augmented load failed: {exc}")

        # ---- 4. consolidated_menu ----
        tool_by_command: dict[str, list[str]] = defaultdict(list)
        if _MENU_PATH.exists():
            try:
                menu = json.loads(_MENU_PATH.read_text(encoding='utf-8'))
                for tool in menu.get('tools', []):
                    cmd = tool.get('command', '')
                    name = tool.get('display_name', tool.get('tool_id', ''))
                    if cmd:
                        # Index by .py filename in command
                        for part in cmd.split():
                            if part.endswith('.py'):
                                basename = Path(part).name
                                tool_by_command[basename].append(name)
                print(f"  consolidated_menu: {len(menu.get('tools', []))} tools")
            except Exception as exc:
                print(f"  [WARN] consolidated_menu load failed: {exc}")

        # ---- 5. provisions_catalog ----
        packages_lookup: dict[str, dict] = {}
        if _PROVISIONS_PATH.exists():
            try:
                prov = json.loads(_PROVISIONS_PATH.read_text(encoding='utf-8'))
                packages = prov.get('packages', [])
                for pkg in packages:
                    packages_lookup[pkg.get('name', '')] = pkg
                print(f"  provisions_catalog: {len(packages_lookup)} packages")
            except Exception as exc:
                print(f"  [WARN] provisions_catalog load failed: {exc}")

        # ---- 6. task_contexts ----
        tasks_by_wherein: dict[str, list[str]] = defaultdict(list)
        task_meta_by_tid: dict[str, dict] = {}
        if _TASK_CTX_DIR.exists():
            tc_files = list(_TASK_CTX_DIR.glob('task_context_*.json'))
            for tc_path in tc_files:
                try:
                    tc = json.loads(tc_path.read_text(encoding='utf-8'))
                    # Extract task_id from filename
                    tid = tc_path.stem.replace('task_context_', '', 1)
                    # Get wherein from top-level or _meta
                    wherein = tc.get('wherein', '?')
                    if not wherein or wherein == '?':
                        wherein = tc.get('_meta', {}).get('wherein', '')
                    if wherein and wherein != '?':
                        rel_wherein = _normalize_wherein(wherein, self.trainer_root)
                        tasks_by_wherein[rel_wherein].append(tid)
                    # Store useful meta
                    task_meta_by_tid[tid] = {
                        'wherein':       wherein,
                        'title':         tc.get('_meta', {}).get('title', ''),
                        'project_id':    tc.get('_meta', {}).get('project_id', ''),
                        'metastate':     tc.get('metastate', {}),
                        'query_weights': tc.get('query_weights_data', {}),
                        'morph_opinion': tc.get('morph_opinion_data', {}),
                        'gap_severity':  tc.get('morph_opinion_data', {}).get('gap_severity', ''),
                    }
                except Exception:
                    pass
            print(f"  task_contexts: {len(tc_files)} files, {len(tasks_by_wherein)} unique wherein paths")

        # ---- Merge into entity records ----
        all_files: set[str] = set(ec_by_file.keys())
        # Also add files from task_context wherein paths
        for w in tasks_by_wherein:
            all_files.add(w)

        self._index = {}
        for rel_file in sorted(all_files):
            if not rel_file:
                continue
            self._index[rel_file] = self._build_entity(
                rel_file,
                ec_by_file=ec_by_file,
                cs_by_event=cs_by_event,
                event_pools=event_pools,
                versions_by_file=versions_by_file,
                temporal_by_basename=temporal_by_basename,
                temporal_profiles=temporal_profiles,
                ast_by_file=ast_by_file,
                tool_by_command=tool_by_command,
                packages_lookup=packages_lookup,
                tasks_by_wherein=tasks_by_wherein,
                task_meta_by_tid=task_meta_by_tid,
            )

        self._built = True
        print(f"[UnifiedContextIndex] Built {len(self._index)} entity records")
        self._save_cache()

    def _build_entity(
        self,
        rel_file: str,
        *,
        ec_by_file: dict,
        cs_by_event: dict,
        event_pools: dict,
        versions_by_file: dict,
        temporal_by_basename: dict,
        temporal_profiles: dict,
        ast_by_file: dict,
        tool_by_command: dict,
        packages_lookup: dict,
        tasks_by_wherein: dict,
        task_meta_by_tid: dict,
    ) -> dict:
        """Build one EntityRecord for a relative file path."""
        basename = Path(rel_file).name
        stem     = Path(rel_file).stem

        # --- Events ---
        events = ec_by_file.get(rel_file, [])
        event_ids   = [e['event_id'] for e in events]
        risk_high   = sum(1 for e in events if e.get('risk_level') in ('HIGH', 'CRITICAL'))
        probe_fails = sum(1 for e in events if e.get('probe_status') == 'FAIL')
        latest_probe = None
        if events:
            sorted_ev = sorted(events, key=lambda e: e.get('timestamp', ''), reverse=True)
            latest_probe = sorted_ev[0].get('probe_status')

        # Blame chain (events with probe FAIL + resolution links)
        blame_chain = []
        for e in events:
            if e.get('probe_status') == 'FAIL' or e.get('blame_event'):
                blame_chain.append({
                    'event_id':    e.get('event_id', ''),
                    'blame_event': e.get('blame_event', ''),
                    'probe_errors': e.get('probe_errors', []),
                })

        # Change states for this file's events
        change_states = {
            eid: cs_by_event[eid]
            for eid in event_ids
            if eid in cs_by_event
        }

        # Feature pool membership
        feature_pool = None
        for pool_name, pool_eids in event_pools.items():
            if any(eid in pool_eids for eid in event_ids):
                feature_pool = pool_name
                break

        # Top verb across events
        verb_counts: dict[str, int] = defaultdict(int)
        for e in events:
            verb_counts[e.get('verb', '')] += 1
        top_verb = max(verb_counts, key=verb_counts.get) if verb_counts else ''

        event_summary = {
            'total':      len(events),
            'risk_high':  risk_high,
            'probe_fail': probe_fails,
            'top_verb':   top_verb,
        }

        # --- Versions ---
        versions = versions_by_file.get(rel_file, [])

        # --- Temporal ---
        temporal_data = {}
        # Match by basename first, then try backup key lookup
        if basename in temporal_by_basename:
            temporal_data = temporal_by_basename[basename]
        else:
            # Try progressive matching: look for tkey that ends with basename or stem
            for tkey, tdata in temporal_profiles.items():
                if _basename_match(tkey, basename) or _basename_match(tkey, stem + '.py'):
                    temporal_data = tdata
                    break

        # --- AST (py_manifest) ---
        ast_data = {}
        # Match by rel_file directly, then by basename
        for ast_key in ast_by_file:
            if ast_key == rel_file or ast_key.endswith('/' + basename):
                ast_data = ast_by_file[ast_key]
                break

        classes   = ast_data.get('classes', [])
        functions = ast_data.get('functions', [])
        imports   = ast_data.get('imports', [])

        # If no AST data, try live parse
        abs_file = self.trainer_root / rel_file
        if not classes and not functions and abs_file.is_file() and abs_file.suffix == '.py':
            try:
                source = abs_file.read_text(encoding='utf-8', errors='ignore')
                tree   = ast.parse(source)
                classes   = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                functions = [n.name for n in ast.walk(tree)
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                # LOC
                loc = source.count('\n') + 1
            except Exception:
                loc = 0
        else:
            loc = 0
            if abs_file.is_file():
                try:
                    loc = abs_file.read_text(encoding='utf-8', errors='ignore').count('\n') + 1
                except Exception:
                    pass

        # call_graph_summary from live parse
        call_graph_summary: dict = {}
        if abs_file.is_file() and abs_file.suffix == '.py':
            try:
                src = abs_file.read_text(encoding='utf-8', errors='ignore')
                calls_by_fn = _extract_calls_from_source(src)
                all_called = {c for cs in calls_by_fn.values() for c in cs}
                call_graph_summary = {
                    'forward_count': sum(len(v) for v in calls_by_fn.values()),
                    'backward_count': 0,   # needs full project graph
                    'function_count': len(calls_by_fn),
                    'unique_callees': len(all_called),
                }
            except Exception:
                pass

        # --- Tools ---
        owned_by_tools = tool_by_command.get(basename, [])

        # --- Packages ---
        dependent_packages = list(set(imports))

        # --- Tasks ---
        task_ids: list[str] = []
        for w_path, tids in tasks_by_wherein.items():
            # Match if rel_file ends with w_path or w_path ends with basename
            if rel_file.endswith(w_path) or w_path.endswith(rel_file) or rel_file == w_path:
                task_ids.extend(tids)
            elif Path(w_path).name == basename:
                task_ids.extend(tids)
        # Also from enriched_changes task_ids
        for e in events:
            for tid in (e.get('task_ids') or []):
                if tid not in task_ids:
                    task_ids.append(tid)
        task_ids = list(dict.fromkeys(task_ids))  # deduplicate preserving order

        # Metastate from most recent task_context for this file
        gap_severity   = ''
        metastate      = {}
        query_weights  = {}
        morph_opinion  = {}
        for tid in task_ids:
            if tid in task_meta_by_tid:
                m = task_meta_by_tid[tid]
                if not gap_severity and m.get('gap_severity'):
                    gap_severity  = m['gap_severity']
                if not metastate and m.get('metastate'):
                    metastate     = m['metastate']
                if not query_weights and m.get('query_weights'):
                    query_weights = m['query_weights']
                if not morph_opinion and m.get('morph_opinion'):
                    morph_opinion = m['morph_opinion']

        # File type classification
        file_type = _classify_file_type(rel_file)

        # Owning tab (heuristic: parent directory name if it looks like a tab)
        owning_tab = _infer_owning_tab(rel_file)

        return {
            'file_path':          rel_file,
            'file_type':          file_type,
            'owning_tab':         owning_tab,
            'loc':                loc,

            'events':             event_ids,
            'event_summary':      event_summary,
            'latest_probe':       latest_probe,
            'blame_chain':        blame_chain,
            'feature_pool':       feature_pool,

            'versions':           versions,
            'change_states':      change_states,

            'classes':            classes,
            'functions':          functions[:50],   # cap for JSON size
            'imports':            imports,
            'call_graph_summary': call_graph_summary,

            'activity_score':     temporal_data.get('activity_score', 0.0),
            'backup_count':       temporal_data.get('backup_count', 0),
            'cluster_id':         temporal_data.get('cluster_id', ''),
            'span_days':          temporal_data.get('span_days', 0),
            'first_seen':         temporal_data.get('first_seen', ''),
            'last_seen':          temporal_data.get('last_seen', ''),

            'task_ids':           task_ids,
            'gap_severity':       gap_severity,
            'metastate':          metastate,
            'query_weights_data': query_weights,
            'morph_opinion_data': morph_opinion,

            'dependent_packages': dependent_packages,
            'owned_by_tools':     owned_by_tools,

            'temporal_ts':        datetime.now().isoformat(timespec='seconds'),
            'index_built_at':     datetime.now().isoformat(timespec='seconds'),
        }

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    def _save_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(
            json.dumps(self._index, indent=2, default=str),
            encoding='utf-8',
        )
        size_kb = self._cache_path.stat().st_size // 1024
        print(f"[UnifiedContextIndex] Cache saved → {self._cache_path} ({size_kb} KB)")

    def _load_cache(self) -> bool:
        if self._cache_path.exists():
            try:
                self._index = json.loads(self._cache_path.read_text(encoding='utf-8'))
                self._built = True
                return True
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, file_path_hint: str) -> dict:
        """
        Return entity record for a file.  Accepts:
        - exact relative path (e.g. 'Data/tabs/.../planner_tab.py')
        - basename only (e.g. 'planner_tab.py')
        - absolute path
        Builds index from cache if not yet loaded.
        """
        if not self._built:
            if not self._load_cache():
                self.build()

        key = self._find_key(file_path_hint)
        return self._index.get(key, {})

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """
        Multi-field search across entity records.
        Rank: exact path > basename > class/function name > task_id > event_id
        Returns list of {file_path, score, entity}
        """
        if not self._built:
            if not self._load_cache():
                self.build()

        q = query.lower()
        scored: list[tuple[float, str, dict]] = []

        for rel_path, entity in self._index.items():
            score = 0.0
            if q in rel_path.lower():
                score += 10.0 if rel_path.lower() == q else 5.0
            if q in Path(rel_path).name.lower():
                score += 4.0
            if any(q in fn.lower() for fn in entity.get('functions', [])):
                score += 3.0
            if any(q in cl.lower() for cl in entity.get('classes', [])):
                score += 3.0
            if any(q in tid.lower() for tid in entity.get('task_ids', [])):
                score += 2.0
            if any(q in eid.lower() for eid in entity.get('events', [])):
                score += 1.5
            if q in entity.get('owning_tab', '').lower():
                score += 1.0
            if score > 0:
                scored.append((score, rel_path, entity))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {'file_path': rp, 'score': sc, 'entity': ent}
            for sc, rp, ent in scored[:max_results]
        ]

    def get_call_graph(self, file_path_hint: str) -> dict:
        """
        Return call graph for a file via live AST parsing.
        Returns {function_name: {forward: [called_names], loc: int}}
        """
        entity = self.get(file_path_hint)
        rel_file = entity.get('file_path') or self._find_key(file_path_hint)
        if not rel_file:
            return {'error': f'File not found in index: {file_path_hint}'}

        abs_file = self.trainer_root / rel_file
        if not abs_file.is_file():
            return {'error': f'File not on disk: {abs_file}'}

        try:
            source = abs_file.read_text(encoding='utf-8', errors='ignore')
            calls_by_fn = _extract_calls_from_source(source)
        except Exception as exc:
            return {'error': str(exc)}

        # Build reverse map (backward edges)
        backward: dict[str, list[str]] = defaultdict(list)
        all_fn_names = set(calls_by_fn.keys())
        for fn, callees in calls_by_fn.items():
            for callee in callees:
                if callee in all_fn_names:
                    backward[callee].append(fn)

        result: dict[str, Any] = {'file_path': rel_file, 'functions': {}}
        for fn, callees in calls_by_fn.items():
            result['functions'][fn] = {
                'forward':  callees,
                'backward': backward.get(fn, []),
            }

        result['summary'] = {
            'total_functions': len(calls_by_fn),
            'forward_edges':   sum(len(v) for v in calls_by_fn.values()),
            'backward_edges':  sum(len(v) for v in backward.values()),
        }
        return result

    def get_attribution_chain(self, file_path_hint: str) -> list[dict]:
        """
        Return chronological enriched_changes for a file with blame/resolution info.
        """
        entity = self.get(file_path_hint)
        if not entity:
            return []

        if not _MANIFEST_PATH.exists():
            return []

        try:
            vm = json.loads(_MANIFEST_PATH.read_text(encoding='utf-8'))
            ec_all = vm.get('enriched_changes', {})
        except Exception:
            return []

        rel_file = entity.get('file_path', '')
        events = [
            {
                'event_id':    eid,
                'verb':        ec.get('verb', ''),
                'feature':     ec.get('feature', ''),
                'risk_level':  ec.get('risk_level', ''),
                'probe_status': ec.get('probe_status'),
                'task_ids':    ec.get('task_ids') or [],
                'timestamp':   ec.get('timestamp', ''),
                'blame_event': ec.get('blame_event', ''),
                'methods':     ec.get('methods', []),
            }
            for eid, ec in ec_all.items()
            if ec.get('file', '') == rel_file
        ]
        events.sort(key=lambda e: e.get('timestamp', ''))
        return events

    def _find_key(self, hint: str) -> str:
        """Find the best matching key in self._index for a file hint."""
        if hint in self._index:
            return hint
        # Try as absolute path → relative
        try:
            rel = str(Path(hint).relative_to(self.trainer_root))
            if rel in self._index:
                return rel
        except ValueError:
            pass
        # Try basename match
        basename = Path(hint).name
        matches = [k for k in self._index if Path(k).name == basename]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Prefer match with most events (most active file)
            return max(matches, key=lambda k: len(self._index[k].get('events', [])))
        # Fuzzy: hint contained in key
        hint_lower = hint.lower()
        for k in self._index:
            if hint_lower in k.lower():
                return k
        return ''


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _classify_file_type(rel_path: str) -> str:
    p = rel_path.lower()
    if p.endswith('.md'):
        return 'doc'
    if p.endswith('.json'):
        return 'config'
    if 'test' in p:
        return 'test'
    if p.endswith('.py'):
        return 'code'
    return 'unknown'


def _infer_owning_tab(rel_path: str) -> str:
    """Guess the owning tab from path components."""
    parts = Path(rel_path).parts
    for part in reversed(parts[:-1]):
        if part.endswith('_tab') or 'tab' in part.lower():
            return part
    # Fall back to parent directory name
    return parts[-2] if len(parts) >= 2 else ''


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_singleton: UnifiedContextIndex | None = None


def get_index(trainer_root: Path | None = None, force_build: bool = False) -> UnifiedContextIndex:
    """Return a cached singleton UnifiedContextIndex."""
    global _singleton
    if _singleton is None:
        _singleton = UnifiedContextIndex(trainer_root)
    if force_build or not _singleton._built:
        if not _singleton._load_cache():
            _singleton.build()
    return _singleton


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------
def _print_entity(entity: dict, verbose: bool = False) -> None:
    fp = entity.get('file_path', '?')
    print(f"\n[ENTITY] {fp}")
    print(f"  type: {entity.get('file_type','?')}  "
          f"| tab: {entity.get('owning_tab','?')}  "
          f"| loc: {entity.get('loc', 0)}")

    es = entity.get('event_summary', {})
    print(f"  events: {es.get('total',0)}  "
          f"(HIGH:{es.get('risk_high',0)}, PROBE_FAIL:{es.get('probe_fail',0)})  "
          f"| latest_probe: {entity.get('latest_probe') or 'n/a'}")

    print(f"  activity: {entity.get('activity_score',0):.2f}  "
          f"| backups: {entity.get('backup_count',0)}  "
          f"| span_days: {entity.get('span_days',0)}")

    tids = entity.get('task_ids', [])
    if tids:
        print(f"  tasks: {', '.join(tids[:6])}" + (" …" if len(tids) > 6 else ""))

    gs = entity.get('gap_severity', '')
    if gs:
        ms = entity.get('metastate', {})
        print(f"  gap_severity: {gs}  | recommended: {ms.get('recommended_action','?')}")

    cg = entity.get('call_graph_summary', {})
    if cg:
        print(f"  call_graph: {cg.get('forward_count',0)} forward edges  "
              f"| {cg.get('unique_callees',0)} unique callees")

    pkgs = entity.get('dependent_packages', [])
    if pkgs:
        shown = pkgs[:6]
        tail = f" (+{len(pkgs)-6} more)" if len(pkgs) > 6 else ""
        print(f"  packages: {', '.join(shown)}{tail}")

    if verbose:
        fns = entity.get('functions', [])
        if fns:
            print(f"  functions ({len(fns)}): {', '.join(fns[:8])}" +
                  (" …" if len(fns) > 8 else ""))
        cls = entity.get('classes', [])
        if cls:
            print(f"  classes: {', '.join(cls)}")
        evts = entity.get('events', [])
        if evts:
            print(f"  events: {', '.join(evts)}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def _main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description='UnifiedContextIndex — aggregate all catalog systems per file',
    )
    sub = parser.add_subparsers(dest='cmd')

    sub.add_parser('build', help='Build index from all sources')

    p_show = sub.add_parser('show', help='Show entity record for a file')
    p_show.add_argument('file', help='filename or relative path')
    p_show.add_argument('-v', '--verbose', action='store_true')

    p_search = sub.add_parser('search', help='Search across all entities')
    p_search.add_argument('query', help='search term')
    p_search.add_argument('-n', '--max', type=int, default=10)

    p_graph = sub.add_parser('graph', help='Show call graph for a file')
    p_graph.add_argument('file', help='filename or relative path')

    p_chain = sub.add_parser('chain', help='Show call chain for one function')
    p_chain.add_argument('file', help='filename or relative path')
    p_chain.add_argument('function', help='function name')

    p_attr = sub.add_parser('attribution', help='Show attribution chain for a file')
    p_attr.add_argument('file', help='filename or relative path')

    # Also support legacy --build / --show / --search flags
    parser.add_argument('--build',  action='store_true', help='Build index')
    parser.add_argument('--show',   metavar='FILE')
    parser.add_argument('--search', metavar='QUERY')

    args = parser.parse_args()

    idx = UnifiedContextIndex(_TRAINER_ROOT)

    # Legacy flags
    if args.build or getattr(args, 'cmd', None) == 'build':
        idx.build(force=True)
        print(f"Done. {len(idx._index)} entities indexed.")
        return

    if not idx._load_cache():
        idx.build()

    if args.show or getattr(args, 'cmd', None) == 'show':
        target = args.show or getattr(args, 'file', '')
        entity = idx.get(target)
        if not entity:
            print(f"No entity found for: {target}")
            sys.exit(1)
        _print_entity(entity, verbose=getattr(args, 'verbose', False))
        return

    if args.search or getattr(args, 'cmd', None) == 'search':
        query = args.search or getattr(args, 'query', '')
        results = idx.search(query, max_results=getattr(args, 'max', 10))
        if not results:
            print(f"No results for: {query!r}")
        for r in results:
            print(f"  [{r['score']:.1f}] {r['file_path']}")
        return

    if getattr(args, 'cmd', None) == 'graph':
        cg = idx.get_call_graph(args.file)
        if 'error' in cg:
            print(f"[ERR] {cg['error']}")
            sys.exit(1)
        print(f"\n[CALL GRAPH] {cg.get('file_path','')}")
        s = cg.get('summary', {})
        print(f"  functions: {s.get('total_functions',0)}  "
              f"| forward_edges: {s.get('forward_edges',0)}")
        for fn, data in list(cg.get('functions', {}).items())[:20]:
            fwd = ', '.join(data['forward'][:5])
            bwd = ', '.join(data['backward'][:3])
            parts = []
            if fwd:
                parts.append(f"→ {fwd}")
            if bwd:
                parts.append(f"← {bwd}")
            print(f"  {fn}: {' | '.join(parts) if parts else '(no calls)'}")
        return

    if getattr(args, 'cmd', None) == 'chain':
        cg = idx.get_call_graph(args.file)
        fn_data = cg.get('functions', {}).get(args.function)
        if fn_data is None:
            print(f"Function {args.function!r} not found in {args.file}")
            sys.exit(1)
        print(f"\n[CHAIN] {args.function} ({args.file})")
        print(f"  → forward  ({len(fn_data['forward'])}):  {', '.join(fn_data['forward'])}")
        print(f"  ← backward ({len(fn_data['backward'])}): {', '.join(fn_data['backward'])}")
        return

    if getattr(args, 'cmd', None) == 'attribution':
        chain = idx.get_attribution_chain(args.file)
        if not chain:
            print(f"No attribution chain for: {args.file}")
        else:
            print(f"\n[ATTRIBUTION CHAIN] {args.file} ({len(chain)} events)")
            for e in chain:
                probe = e.get('probe_status') or 'n/a'
                print(f"  {e['event_id']}  {e['timestamp'][:19]}  "
                      f"{e['verb']:8}  risk:{e.get('risk_level','?'):8}  "
                      f"probe:{probe:4}  tasks:{e['task_ids']}")
        return

    parser.print_help()


if __name__ == '__main__':
    _main()
