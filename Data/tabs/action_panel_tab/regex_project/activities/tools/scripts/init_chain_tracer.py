"""
InitChainTracer — headless reverse-init-chain analysis.

Given a set of recently changed files, traces forward through the GUI init
sequence to detect which Tabs / widgets will fail to initialize and why.

Works without running the GUI. Uses:
  - py_manifest.json (AST: imports, dependencies, classes, functions per file)
  - enriched_changes  (before_after_values, verbs, methods, imports_removed)
  - INIT_CHAIN constant (known tab load order from interactive_trainer_gui_NEW.py)

Usage:
  from init_chain_tracer import InitChainTracer
  from pathlib import Path
  tracer = InitChainTracer(Path('/home/commander/Trainer'))
  report = tracer.trace(['omega_bridge.py', 'planner_tab.py'])
  print(report['summary'])
  print(report['text'])
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# GUI Init Chain (from interactive_trainer_gui_NEW.py analysis)
# Step name, module hint, critical (True = init breaks all subsequent tabs)
# ---------------------------------------------------------------------------

INIT_CHAIN = [
    {
        'step': 1,
        'name': 'logger_util',
        'module_hint': 'logger_util',
        'critical': True,
        'description': 'logger_util.init_logger() — must succeed or logging breaks',
    },
    {
        'step': 2,
        'name': 'py_manifest',
        'module_hint': '_lookup_py_manifest',
        'critical': False,
        'description': '_lookup_py_manifest() — AST cache; non-fatal if missing',
    },
    {
        'step': 3,
        'name': 'TrainingTab',
        'module_hint': 'tabs.training_tab',
        'critical': True,
        'description': 'tabs.training_tab.TrainingTab — first tab',
    },
    {
        'step': 4,
        'name': 'ModelsTab',
        'module_hint': 'tabs.models_tab',
        'critical': True,
        'description': 'tabs.models_tab.ModelsTab',
    },
    {
        'step': 5,
        'name': 'SettingsTab',
        'module_hint': 'tabs.settings_tab',
        'critical': True,
        'description': 'tabs.settings_tab.SettingsTab',
    },
    {
        'step': 6,
        'name': 'CustomCodeTab',
        'module_hint': 'tabs.custom_code_tab',
        'critical': True,
        'description': 'tabs.custom_code_tab.CustomCodeTab',
    },
    {
        'step': 7,
        'name': 'MapTab',
        'module_hint': 'tabs.map_tab',
        'critical': False,
        'description': 'tabs.map_tab.digital_biosphere_visualizer.MapTab [optional]',
    },
    {
        'step': 8,
        'name': 'AgForgeTab',
        'module_hint': 'tabs.ag_forge_tab',
        'critical': False,
        'description': 'tabs.ag_forge_tab.ag_forge_tab.AgForgeTab [optional]',
    },
]


# ---------------------------------------------------------------------------
# InitChainTracer
# ---------------------------------------------------------------------------

class InitChainTracer:
    """Trace file changes through the GUI init chain to detect init failures."""

    def __init__(self, trainer_root: Path):
        self.trainer_root = trainer_root
        self._action_panel = trainer_root / 'Data' / 'tabs' / 'action_panel_tab'
        self._py_manifest: dict | None = None
        self._reverse_deps: dict[str, list[str]] | None = None  # file → [files that import it]
        self._enriched_changes: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def trace(
        self,
        changed_files: list[str],
        since=None,
    ) -> dict:
        """
        Analyse a list of changed files against the init chain.

        Parameters
        ----------
        changed_files : list of str
            File paths (relative or absolute) to analyse.
        since : datetime, optional
            If provided, also filter enriched_changes to this window.

        Returns
        -------
        dict:
            {
                'impacts': [InitImpact, ...],   # per-file findings
                'fatal_count': int,
                'warning_count': int,
                'info_count': int,
                'summary': str,
                'text': str,                    # formatted report
            }
        """
        impacts = []
        for f in changed_files:
            impact = self._trace_file(f)
            if impact:
                impacts.extend(impact)

        # Deduplicate by (file, tab) key
        seen = set()
        unique_impacts = []
        for imp in impacts:
            key = (imp['changed_file'], imp['affected_tab'])
            if key not in seen:
                seen.add(key)
                unique_impacts.append(imp)

        fatal = [i for i in unique_impacts if i['severity'] == 'FATAL']
        warnings = [i for i in unique_impacts if i['severity'] == 'WARNING']
        infos = [i for i in unique_impacts if i['severity'] == 'INFO']

        summary = f"{len(fatal)} FATAL | {len(warnings)} WARNING | {len(infos)} INFO"
        if not unique_impacts:
            summary = "No init chain impact detected from changed files"

        return {
            'impacts': unique_impacts,
            'fatal_count': len(fatal),
            'warning_count': len(warnings),
            'info_count': len(infos),
            'summary': summary,
            'text': self._format_report(changed_files, unique_impacts),
        }

    # ------------------------------------------------------------------
    # Per-file tracing
    # ------------------------------------------------------------------

    def _trace_file(self, file_path: str) -> list[dict]:
        """Trace a single file through the init chain. Returns list of impact dicts."""
        impacts = []

        # Normalize to Path
        p = Path(file_path)
        if not p.is_absolute():
            # Try to resolve relative to common roots
            candidates = [
                self.trainer_root / file_path,
                self.trainer_root / 'Data' / file_path,
                self._action_panel / file_path,
                self._action_panel / 'regex_project' / file_path,
            ]
            resolved = next((c for c in candidates if c.exists()), None)
            p = resolved if resolved else self.trainer_root / file_path

        abs_path = str(p)
        file_name = p.name

        # 1. Get change metadata from enriched_changes
        change_data = self._get_change_data(abs_path, file_name)

        # 2. Detect what was broken by the change
        broken_exports = self._detect_broken_exports(change_data)

        # 3. If nothing obviously broken, still check for any additive changes
        if not broken_exports and not self._is_risky_change(change_data):
            impacts.append({
                'changed_file': file_name,
                'changed_file_path': abs_path,
                'affected_tab': 'None',
                'severity': 'INFO',
                'reason': f"No broken exports detected ({change_data.get('verb', 'unknown')} verb)",
                'chain_step': 0,
            })
            return impacts

        # 4. Find which Tab files import this file
        importers = self._find_reverse_importers(abs_path, file_name)

        if not importers:
            # File has broken exports but nothing in the init chain imports it
            impacts.append({
                'changed_file': file_name,
                'changed_file_path': abs_path,
                'affected_tab': 'None',
                'severity': 'INFO',
                'reason': (
                    f"Broken: {broken_exports or 'risky change'} — "
                    f"but no Tab in init chain imports this file"
                ),
                'chain_step': 0,
            })
            return impacts

        # 5. For each importer, check init chain step and severity
        for importer_path, importer_name in importers:
            chain_step = self._get_init_chain_step(importer_path, importer_name)
            chain_entry = INIT_CHAIN[chain_step - 1] if 1 <= chain_step <= len(INIT_CHAIN) else None

            severity = 'WARNING'
            if chain_entry and chain_entry['critical'] and broken_exports:
                severity = 'FATAL'
            elif broken_exports:
                severity = 'WARNING'
            else:
                severity = 'INFO'

            reason_parts = []
            if broken_exports:
                reason_parts.append(f"Broken exports: {', '.join(broken_exports[:3])}")
            if change_data.get('verb'):
                reason_parts.append(f"verb={change_data['verb']}")
            if change_data.get('risk_level') in ('HIGH', 'CRITICAL'):
                reason_parts.append(f"risk={change_data['risk_level']}")

            impacts.append({
                'changed_file': file_name,
                'changed_file_path': abs_path,
                'affected_tab': importer_name,
                'affected_tab_path': importer_path,
                'severity': severity,
                'reason': ' | '.join(reason_parts) or 'Risky change in dependency',
                'chain_step': chain_step,
                'chain_description': chain_entry['description'] if chain_entry else 'unknown',
                'broken_exports': broken_exports,
                'change_verb': change_data.get('verb', ''),
                'event_id': change_data.get('event_id', ''),
            })

        return impacts

    # ------------------------------------------------------------------
    # Change metadata
    # ------------------------------------------------------------------

    def _get_change_data(self, abs_path: str, file_name: str) -> dict:
        """
        Fetch the most recent enriched_change entry for this file.
        Falls back to empty dict if not found.
        """
        changes = self._load_enriched_changes()
        # Match by full path or file name tail
        candidates = [
            ev for ev in changes.values()
            if (ev.get('file', '') == abs_path or
                ev.get('file', '').endswith('/' + file_name) or
                ev.get('file', '') == file_name)
        ]
        if not candidates:
            return {}
        # Return the most recent
        candidates.sort(key=lambda e: e.get('timestamp', ''), reverse=True)
        return candidates[0]

    def _detect_broken_exports(self, change_data: dict) -> list[str]:
        """
        Identify symbols that were removed/renamed based on enriched_change metadata.
        """
        broken = []

        if not change_data:
            return broken

        verb = change_data.get('verb', '')

        # imports_removed = something that was previously exported is gone
        for imp in (change_data.get('imports_removed') or []):
            broken.append(f"import removed: {imp}")

        # before_after_values: class attribute removed
        for bav in (change_data.get('before_after_values') or []):
            if isinstance(bav, dict):
                before = bav.get('before_value', '')
                after = bav.get('after_value', '')
                # If before had something and after is empty/None → removal
                if before and not after:
                    broken.append(f"removed: {str(before)[:60]}")
                # Rename pattern: before != after and both non-empty
                elif before and after and before != after:
                    broken.append(f"renamed: {str(before)[:40]} → {str(after)[:40]}")

        # Whole class/function deleted
        if verb in ('delete', 'remove'):
            for cls in (change_data.get('classes') or []):
                broken.append(f"class deleted: {cls}")
            for method in (change_data.get('methods') or []):
                broken.append(f"method deleted: {method}")

        return broken

    def _is_risky_change(self, change_data: dict) -> bool:
        """Return True if the change warrants further tracing (HIGH/CRITICAL risk)."""
        return change_data.get('risk_level') in ('HIGH', 'CRITICAL')

    # ------------------------------------------------------------------
    # Reverse import lookup
    # ------------------------------------------------------------------

    def _find_reverse_importers(self, abs_path: str, file_name: str) -> list[tuple[str, str]]:
        """
        Find all files in the py_manifest that have this file as a dependency.
        Returns list of (importer_path, importer_name) tuples.
        """
        reverse_deps = self._get_reverse_deps()
        matches = []

        # Try exact path match first
        if abs_path in reverse_deps:
            for dep_path in reverse_deps[abs_path]:
                matches.append((dep_path, Path(dep_path).name))

        # Also try name-only match (for files not in py_manifest by full path)
        stem = Path(file_name).stem
        for dep_key, importers in reverse_deps.items():
            if dep_key.endswith('/' + file_name) or dep_key.endswith('/' + stem + '.py'):
                for imp_path in importers:
                    entry = (imp_path, Path(imp_path).name)
                    if entry not in matches:
                        matches.append(entry)

        # Also do text-based scan of known Tab files if py_manifest is sparse
        if not matches:
            matches = self._scan_tab_files_for_import(file_name, stem)

        return matches

    def _scan_tab_files_for_import(self, file_name: str, stem: str) -> list[tuple[str, str]]:
        """
        Fallback: text-grep key Tab files for import of this module.
        Only scans files in the INIT_CHAIN.
        """
        results = []
        tab_paths = self._get_tab_file_paths()
        patterns = [
            re.compile(rf'\bimport\s+{re.escape(stem)}\b'),
            re.compile(rf'from\s+[\w.]*{re.escape(stem)}\s+import'),
            re.compile(rf'from\s+.*\s+import\s+.*{re.escape(stem)}'),
        ]
        for tab_path in tab_paths:
            p = Path(tab_path)
            if not p.exists():
                continue
            try:
                text = p.read_text(errors='replace')
                if any(pat.search(text) for pat in patterns):
                    results.append((tab_path, p.name))
            except Exception:
                continue
        return results

    def _get_tab_file_paths(self) -> list[str]:
        """Return known Tab file paths for text scanning."""
        root = self.trainer_root
        data = root / 'Data'
        return [
            str(root / 'Data' / 'interactive_trainer_gui_NEW.py'),
            str(root / 'interactive_trainer_gui_NEW.py'),
            str(data / 'tabs' / 'training_tab' / 'training_tab.py'),
            str(data / 'tabs' / 'models_tab' / 'models_tab.py'),
            str(data / 'tabs' / 'settings_tab' / 'settings_tab.py'),
            str(data / 'tabs' / 'custom_code_tab' / 'custom_code_tab.py'),
            str(data / 'tabs' / 'map_tab' / 'digital_biosphere_visualizer.py'),
            str(data / 'tabs' / 'ag_forge_tab' / 'ag_forge_tab.py'),
            str(data / 'logger_util.py'),
            str(root / 'logger_util.py'),
            str(root / 'recovery_util.py'),
        ]

    def _get_init_chain_step(self, importer_path: str, importer_name: str) -> int:
        """Return the INIT_CHAIN step number for an importer file (1-based, 0 = unknown)."""
        p_lower = importer_path.lower()
        n_lower = importer_name.lower()
        for entry in INIT_CHAIN:
            hint = entry['module_hint'].lower().replace('.', '/')
            if (hint in p_lower or
                    hint.split('/')[-1] in n_lower or
                    entry['name'].lower() in n_lower):
                return entry['step']
        # Special: gui main file is step 0 (pre-tab)
        if 'interactive_trainer_gui' in p_lower:
            return 0
        return 0

    # ------------------------------------------------------------------
    # Data loading
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

    def _load_py_manifest(self) -> dict:
        if self._py_manifest is None:
            pm_paths = [
                self.trainer_root / 'Data' / 'pymanifest' / 'py_manifest.json',
                self.trainer_root / 'Data' / 'plans' / 'py_manifest.json',
                self.trainer_root / 'py_manifest.json',
            ]
            for pm_path in pm_paths:
                if pm_path.exists():
                    try:
                        self._py_manifest = json.loads(pm_path.read_text())
                        break
                    except Exception:
                        continue
            if self._py_manifest is None:
                self._py_manifest = {}
        return self._py_manifest

    def _get_reverse_deps(self) -> dict[str, list[str]]:
        """
        Build reverse dependency index: file → [files that depend on it].
        Uses py_manifest 'dependencies' field (list of resolved local paths).
        """
        if self._reverse_deps is not None:
            return self._reverse_deps

        pm = self._load_py_manifest()
        files = pm.get('files', {})
        reverse: dict[str, list[str]] = {}

        for file_path, entry in files.items():
            if not isinstance(entry, dict):
                continue
            for dep in (entry.get('dependencies') or []):
                if dep not in reverse:
                    reverse[dep] = []
                if file_path not in reverse[dep]:
                    reverse[dep].append(file_path)

        self._reverse_deps = reverse
        return reverse

    # ------------------------------------------------------------------
    # Report formatting
    # ------------------------------------------------------------------

    def _format_report(self, changed_files: list[str], impacts: list[dict]) -> str:
        lines = [
            'INIT CHAIN IMPACT REPORT (headless)',
            '=' * 45,
            f'Analysis based on: {len(changed_files)} changed file(s)',
            '',
        ]

        # Group impacts by changed file
        by_file: dict[str, list[dict]] = {}
        for imp in impacts:
            key = imp['changed_file']
            by_file.setdefault(key, []).append(imp)

        for file_name, file_impacts in by_file.items():
            # Check if all impacts are INFO (no risk)
            severities = {i['severity'] for i in file_impacts}
            if severities == {'INFO'}:
                lines.append(f'✅  No risk: {file_name}')
                for imp in file_impacts:
                    lines.append(f'     {imp["reason"]}')
            else:
                for imp in file_impacts:
                    if imp['severity'] == 'FATAL':
                        icon = '❌ FATAL  '
                    elif imp['severity'] == 'WARNING':
                        icon = '⚠️  WARNING'
                    else:
                        icon = 'ℹ️  INFO   '

                    lines.append(f'{icon} {file_name}')
                    lines.append(f'         Reason : {imp["reason"]}')
                    if imp.get('affected_tab') and imp['affected_tab'] != 'None':
                        lines.append(f'         Tab    : {imp["affected_tab"]} (step {imp.get("chain_step", "?")})')
                    if imp.get('chain_description'):
                        lines.append(f'         Chain  : {imp["chain_description"]}')
                    if imp.get('event_id'):
                        lines.append(f'         Event  : {imp["event_id"]}')
            lines.append('')

        # Summary line
        fatal = len([i for i in impacts if i['severity'] == 'FATAL'])
        warnings = len([i for i in impacts if i['severity'] == 'WARNING'])
        infos = len([i for i in impacts if i['severity'] == 'INFO'])
        lines.append(f'SUMMARY: {fatal} FATAL | {warnings} WARNING | {infos} INFO')

        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys
    trainer_root = Path('/home/commander/Trainer')
    tracer = InitChainTracer(trainer_root)

    files = sys.argv[1:] if len(sys.argv) > 1 else [
        'omega_bridge.py',
        'activity_integration_bridge.py',
    ]

    print(f'[InitChainTracer] Tracing {len(files)} file(s): {files}')
    report = tracer.trace(files)
    print(report['text'])
