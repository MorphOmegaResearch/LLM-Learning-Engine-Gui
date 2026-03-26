"""
MoE Plan Engine — Sequential multi-model plan generation + comparison.

Loads GGUFs one at a time via llama_cpp, builds rich context from existing
infrastructure (MorphToolkit, OmegaBridge, TNE, recovery_util), generates
plans per model, and cross-validates outputs.

Usage:
    from moe_plan_engine import MoEPlanEngine
    engine = MoEPlanEngine(trainer_root)
    results, comparison = engine.run("task_25_2", compare=True)

CLI:
    Os_Toolkit.py plan generate <task_id> [--models M1,M2] [--compare]
    orchestrator.py --morph-chat → moe <task_id> [model1,model2]
"""

import gc
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class MoEModelSpec:
    """Describes a single expert model."""
    name: str
    gguf_path: str
    n_ctx: int = 2048
    n_threads: int = 4


@dataclass
class MoEContextPacket:
    """Rich context assembled from all available sources."""
    task_id: str
    task_context: dict = field(default_factory=dict)
    grounded_context: dict = field(default_factory=dict)
    omega_state: dict = field(default_factory=dict)
    aoe_vectors: dict = field(default_factory=dict)
    explain_narrative: dict = field(default_factory=dict)
    version_info: dict = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class MoEPlanResult:
    """Output from a single model's plan generation run."""
    model_name: str
    gguf_path: str
    plan_text: str = ""
    plan_sections: dict = field(default_factory=dict)
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    tokens_generated: int = 0
    output_path: Path = field(default_factory=Path)


class MoEPlanEngine:
    """
    Sequential multi-model plan generation engine.

    Assembles rich context from existing infrastructure, runs each GGUF model
    one at a time, parses plan sections, and optionally cross-validates outputs.
    """

    def __init__(self, trainer_root: Path):
        self._root = Path(trainer_root).resolve()
        self._apt = self._root / "Data" / "tabs" / "action_panel_tab"
        self._scripts = self._apt / "regex_project" / "activities" / "tools" / "scripts"
        self._output_dir = self._root / "Data" / "plans" / "Morph"
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Ensure scripts dir is on path for imports
        _sd = str(self._scripts)
        if _sd not in sys.path:
            sys.path.insert(0, _sd)

    # ── Model Discovery ──────────────────────────────────────────────────

    def discover_models(self) -> list:
        """Scan Models/*/exports/gguf/*.gguf + Models/*/*.gguf for available GGUFs."""
        models = []
        models_dir = self._root / "Models"
        if not models_dir.exists():
            return models

        seen_paths = set()
        for model_dir in sorted(models_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            # Check exports/gguf/
            gguf_dir = model_dir / "exports" / "gguf"
            if gguf_dir.exists():
                for g in sorted(gguf_dir.glob("*.gguf")):
                    if str(g) not in seen_paths:
                        models.append(MoEModelSpec(
                            name=g.stem, gguf_path=str(g)))
                        seen_paths.add(str(g))
            # Also check root of model dir
            for g in sorted(model_dir.glob("*.gguf")):
                if str(g) not in seen_paths:
                    models.append(MoEModelSpec(
                        name=g.stem, gguf_path=str(g)))
                    seen_paths.add(str(g))

        return models

    # ── Context Building ─────────────────────────────────────────────────

    def build_context_packet(self, task_id: str) -> MoEContextPacket:
        """Assemble rich context from all available infrastructure."""
        packet = MoEContextPacket(
            task_id=task_id,
            timestamp=datetime.now().isoformat(),
        )

        # 1. Task context from MorphToolkit
        try:
            from activity_integration_bridge import MorphToolkit
            toolkit = MorphToolkit(self._apt)
            packet.task_context = toolkit.task_context(task_id)
        except Exception as e:
            packet.task_context = {"error": f"MorphToolkit: {e}"}

        # 2. Grounded context from OsToolkitGroundingBridge
        try:
            from activity_integration_bridge import OsToolkitGroundingBridge
            grounder = OsToolkitGroundingBridge(self._apt)
            packet.grounded_context = grounder.load()
        except Exception as e:
            packet.grounded_context = {"error": f"GroundingBridge: {e}"}

        # 3. Omega state (epistemic + metacog + control_signal + sampling)
        try:
            from omega_bridge import OmegaBridge
            omega = OmegaBridge(self._root)
            wherein = ""
            if isinstance(packet.task_context, dict):
                _meta = packet.task_context.get("_meta", {})
                wherein = _meta.get("wherein", "") or packet.task_context.get("wherein", "")
            if wherein:
                packet.omega_state = omega.get_token_endpoint(wherein)
            else:
                packet.omega_state = {"note": "no wherein file for omega state"}
        except Exception as e:
            packet.omega_state = {"error": f"OmegaBridge: {e}"}

        # 4. AoE vectors from task_context (already written by planner_tab)
        if isinstance(packet.task_context, dict):
            packet.aoe_vectors = {
                "query_weights": packet.task_context.get("query_weights_data", {}),
                "morph_opinion": packet.task_context.get("morph_opinion_data", {}),
                "metastate": packet.task_context.get("metastate", {}),
            }

        # 5. Temporal narrative
        try:
            from temporal_narrative_engine import TemporalNarrativeEngine
            tne = TemporalNarrativeEngine(self._root)
            packet.explain_narrative = tne.explain("last 24h")
        except Exception as e:
            packet.explain_narrative = {"error": f"TNE: {e}"}

        # 6. Version info from recovery_util
        try:
            _data_dir = str(self._root / "Data")
            if _data_dir not in sys.path:
                sys.path.insert(0, _data_dir)
            from recovery_util import load_version_manifest
            vm = load_version_manifest()
            packet.version_info = {
                "active_version": vm.get("active_version", ""),
                "default_version": vm.get("default_version", ""),
                "enriched_changes_count": len(vm.get("enriched_changes", {})),
                "versions_count": len(vm.get("versions", {})),
            }
        except Exception as e:
            packet.version_info = {"error": f"recovery_util: {e}"}

        return packet

    # ── Prompt Formatting ────────────────────────────────────────────────

    def _format_chatml_prompt(self, ctx: MoEContextPacket, max_tokens: int = 1024) -> list:
        """Build ChatML messages for llama_cpp create_chat_completion."""
        system_msg = (
            "You are a software planning assistant. Given the context below about a task, "
            "codebase state, and recent changes, generate a structured plan.\n\n"
            "Output format — use these section markers:\n"
            "</High_Level>:\n  - Task title, goal, risk summary, probe status\n\n"
            "</Mid_Level>:\n  - Functions touched, imports, probe history, file context\n\n"
            "</Diffs>:\n  - File-level change specifications with methods and risk\n\n"
            "</Tests>:\n  - Probe assertions, import checks, method verification\n\n"
            "</Current_Tasks>:\n  - Task IDs with status, expected diffs checklist\n\n"
            "Be specific: name files, functions, line ranges. Reference enriched_change event IDs."
        )

        # Build compact context (stay within token budget)
        _tc = ctx.task_context if isinstance(ctx.task_context, dict) else {}
        _meta = _tc.get("_meta", {})
        _changes = _tc.get("changes", [])[:15]  # cap at 15
        _grounded = ctx.grounded_context if isinstance(ctx.grounded_context, dict) else {}

        user_content = {
            "task_id": ctx.task_id,
            "title": _meta.get("title", ""),
            "wherein": _meta.get("wherein", ""),
            "status": _meta.get("status", ""),
            "gap_severity": _grounded.get("gap_severity", ""),
            "probe_failures": _grounded.get("probe_failures", []),
            "high_risk_files": _grounded.get("high_risk_files", []),
            "recent_changes": [
                {
                    "event_id": c.get("event_id", ""),
                    "file": c.get("file", ""),
                    "verb": c.get("verb", ""),
                    "risk": c.get("risk_level", ""),
                    "methods": c.get("methods", [])[:5],
                }
                for c in _changes
            ],
            "omega_control_signal": (ctx.omega_state.get("control_signal", "")
                                     if isinstance(ctx.omega_state, dict) else ""),
            "explain_phase": (ctx.explain_narrative.get("phase_summary", "")
                              if isinstance(ctx.explain_narrative, dict) else ""),
            "version": ctx.version_info,
        }

        user_msg = (
            f"Generate a plan for task {ctx.task_id}:\n\n"
            + json.dumps(user_content, indent=2, default=str)
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    # ── Single Model Run ─────────────────────────────────────────────────

    def _run_single_model(self, spec: MoEModelSpec, prompt: list,
                          task_id: str, ts: str, max_tokens: int = 1024) -> MoEPlanResult:
        """Load GGUF, generate plan, parse sections, save, unload."""
        from llama_cpp import Llama

        result = MoEPlanResult(
            model_name=spec.name,
            gguf_path=spec.gguf_path,
            start_time=datetime.now().isoformat(),
        )

        try:
            print(f"  Loading {spec.name}...")
            llm = Llama(
                model_path=spec.gguf_path,
                n_ctx=spec.n_ctx,
                n_threads=spec.n_threads,
                verbose=False,
            )

            start = time.time()
            response = llm.create_chat_completion(
                messages=prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                top_p=0.9,
            )
            end = time.time()

            raw_text = response["choices"][0]["message"]["content"]
            tokens = response.get("usage", {}).get("completion_tokens", 0)

            result.plan_text = raw_text
            result.tokens_generated = tokens
            result.duration_seconds = round(end - start, 2)

            # Unload model
            del llm
            gc.collect()

        except Exception as e:
            result.plan_text = f"[ERROR] {e}"
            result.duration_seconds = 0.0

        result.end_time = datetime.now().isoformat()

        # Parse sections
        result.plan_sections = self._parse_plan_sections(result.plan_text)

        # Save plan file
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', spec.name)
        out_path = self._output_dir / f"moe_plan_{task_id}_{safe_name}_{ts}.md"
        try:
            out_path.write_text(
                f"# MoE Plan: {task_id} | Model: {spec.name}\n"
                f"# Generated: {result.start_time}\n"
                f"# Duration: {result.duration_seconds}s | Tokens: {result.tokens_generated}\n"
                f"# GGUF: {spec.gguf_path}\n\n"
                + result.plan_text,
                encoding="utf-8",
            )
            result.output_path = out_path
        except Exception:
            pass

        return result

    # ── Section Parsing ──────────────────────────────────────────────────

    def _parse_plan_sections(self, raw: str) -> dict:
        """Extract </High_Level>, </Mid_Level>, </Diffs>, </Tests>, </Current_Tasks> sections."""
        sections = {}
        section_names = ["High_Level", "Mid_Level", "Diffs", "Tests", "Current_Tasks"]

        for name in section_names:
            # Match: </Name>: ... up to next </Name> or end
            pattern = rf'</{name}>:?\s*(.*?)(?=</{"|</".join(n for n in section_names if n != name)}>|$)'
            match = re.search(pattern, raw, re.DOTALL)
            if match:
                sections[name.lower()] = match.group(1).strip()

        # If no template markers found, treat whole text as high_level
        if not sections:
            sections["high_level"] = raw.strip()

        return sections

    # ── Comparison ───────────────────────────────────────────────────────

    def _extract_key_points(self, text: str) -> list:
        """Extract key identifiers from plan text: file paths, function names, task IDs."""
        points = set()
        # File paths (*.py)
        for m in re.finditer(r'[\w/]+\.py', text):
            points.add(m.group())
        # Function/method names
        for m in re.finditer(r'\b(\w+)\(\)', text):
            points.add(m.group(1))
        # Event IDs
        for m in re.finditer(r'#\[Event:\w+\]', text):
            points.add(m.group())
        # Task IDs
        for m in re.finditer(r'task_\w+', text):
            points.add(m.group())
        return sorted(points)

    def _compare_results(self, results: list, task_id: str, ts: str) -> dict:
        """Cross-validate plan outputs from multiple models."""
        SECTIONS = ["high_level", "mid_level", "diffs", "tests", "current_tasks"]
        section_alignment = {}

        for section in SECTIONS:
            entries = []
            for r in results:
                content = r.plan_sections.get(section, "")
                entries.append({
                    "model": r.model_name,
                    "content_hash": hashlib.md5(content.encode()).hexdigest()[:8],
                    "key_points": self._extract_key_points(content),
                    "length": len(content),
                    "present": bool(content),
                })
            section_alignment[section] = entries

        # Agreement: fraction of sections where all models have content
        _present_counts = []
        for section in SECTIONS:
            _pct = sum(1 for e in section_alignment[section] if e["present"]) / max(len(results), 1)
            _present_counts.append(_pct)
        agreement = sum(_present_counts) / len(SECTIONS) if SECTIONS else 0.0

        # Key point overlap between models
        divergences = []
        for section in SECTIONS:
            _all_points = [set(e["key_points"]) for e in section_alignment[section] if e["present"]]
            if len(_all_points) >= 2:
                _common = set.intersection(*_all_points)
                _union = set.union(*_all_points)
                if _union and len(_common) / len(_union) < 0.3:
                    divergences.append({
                        "section": section,
                        "overlap_pct": round(len(_common) / len(_union), 2),
                        "unique_per_model": {
                            section_alignment[section][i]["model"]: sorted(_all_points[i] - _common)[:5]
                            for i in range(len(_all_points))
                        },
                    })

        # Quality scoring per model
        quality = {}
        for r in results:
            completeness = sum(1 for s in SECTIONS if r.plan_sections.get(s)) / len(SECTIONS)
            # Specificity: count of named entities
            _all_text = " ".join(r.plan_sections.values())
            specificity = min(len(self._extract_key_points(_all_text)) / 20.0, 1.0)
            quality[r.model_name] = {
                "completeness": round(completeness, 2),
                "specificity": round(specificity, 2),
                "tokens": r.tokens_generated,
                "duration_s": r.duration_seconds,
            }

        # Save comparison metadata
        meta_path = self._output_dir / f"moe_comparison_{task_id}_{ts}.json"
        report = {
            "task_id": task_id,
            "timestamp": ts,
            "models_compared": [r.model_name for r in results],
            "section_alignment": section_alignment,
            "agreement_score": round(agreement, 3),
            "divergences": divergences,
            "quality_scores": quality,
            "plan_paths": [str(r.output_path) for r in results],
            "metadata_path": str(meta_path),
        }
        try:
            meta_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

        return report

    # ── Main Entry Point ─────────────────────────────────────────────────

    def run(self, task_id: str, model_names: Optional[list] = None,
            compare: bool = True, max_tokens: int = 1024,
            n_ctx: int = 2048) -> tuple:
        """
        Main entry: sequential model execution → optional comparison.

        Args:
            task_id: Task ID to generate plans for
            model_names: Filter to specific models (by name substring). None = all.
            compare: Whether to cross-validate outputs
            max_tokens: Max generation tokens per model
            n_ctx: Context window per model

        Returns:
            (list[MoEPlanResult], comparison_dict | None)
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. Discover models
        all_models = self.discover_models()
        if not all_models:
            print("  [MoE] No GGUF models found in Models/*/exports/gguf/")
            return [], None

        # Filter if specific models requested
        if model_names:
            filtered = []
            for spec in all_models:
                for name in model_names:
                    if name.lower() in spec.name.lower():
                        filtered.append(spec)
                        break
            if not filtered:
                print(f"  [MoE] No models matched: {model_names}")
                print(f"  Available: {[m.name for m in all_models]}")
                return [], None
            all_models = filtered

        # Apply n_ctx override
        for m in all_models:
            m.n_ctx = n_ctx

        print(f"  [MoE] Task: {task_id} | Models: {len(all_models)} | Compare: {compare}")
        for m in all_models:
            print(f"    → {m.name}: {m.gguf_path}")

        # 2. Build context packet (once, shared across all models)
        print(f"  [MoE] Building context packet...")
        ctx = self.build_context_packet(task_id)
        prompt = self._format_chatml_prompt(ctx, max_tokens=max_tokens)

        # Log context summary
        _tc = ctx.task_context if isinstance(ctx.task_context, dict) else {}
        print(f"    task: {_tc.get('_meta', {}).get('title', '?')}")
        print(f"    gap: {ctx.grounded_context.get('gap_severity', '?')}")
        print(f"    version: {ctx.version_info.get('active_version', '?')}")
        print(f"    changes: {ctx.version_info.get('enriched_changes_count', '?')}")

        # 3. Run each model sequentially
        results = []
        for i, spec in enumerate(all_models, 1):
            print(f"\n  [MoE {i}/{len(all_models)}] Generating with {spec.name}...")
            result = self._run_single_model(spec, prompt, task_id, ts, max_tokens)
            results.append(result)
            print(f"    Done: {result.duration_seconds}s, {result.tokens_generated} tokens")
            if result.output_path and result.output_path.exists():
                print(f"    Saved: {result.output_path.name}")

        # 4. Compare if requested and multiple results
        comparison = None
        if compare and len(results) >= 1:
            print(f"\n  [MoE] Cross-validating {len(results)} plan(s)...")
            comparison = self._compare_results(results, task_id, ts)
            if comparison:
                print(f"    Agreement: {comparison.get('agreement_score', 0):.0%}")
                _divs = comparison.get("divergences", [])
                if _divs:
                    print(f"    Divergences: {len(_divs)} section(s)")
                    for d in _divs:
                        print(f"      {d['section']}: {d['overlap_pct']:.0%} overlap")

        return results, comparison
