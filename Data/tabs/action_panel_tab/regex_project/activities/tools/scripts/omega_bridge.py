"""
OmegaBridge — Phase J
=====================
Translates grounded Os_Toolkit context (UnifiedContextIndex, enriched_changes,
task_contexts) into Morph_regex state dicts, derives control packets, and
optionally calls the Morph_regex MetacognitiveOrchestrator for real responses.

Architecture:
    UnifiedContextIndex entity  ──→  epistemic_state + metacognitive_state
    epistemic + metacognitive   ──→  control_signal (ControlSignalClassifier logic)
    control_signal + entity     ──→  fix_suggestion (via GapAnalyzer recommended_action)
    process_interaction(text)   ──→  response (Morph_regex, subprocess, graceful fallback)
    full state snapshot         ──→  MorphVariantSpawner variant JSON
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Entity → Morph state mappings (per plan architecture)
# ---------------------------------------------------------------------------

_GAP_MAP = {
    "high":     "critical",   # escalate high → critical
    "critical": "critical",
    "medium":   "medium",
    "low":      "low",
    "":         "low",
}

_PROBE_UNDERSTANDING = {
    "PASS": 0.9,
    "WARN": 0.5,
    "FAIL": 0.1,
}

_TAB_DOMAIN = {
    "planner_tab":        "technical",
    "action_panel_tab":   "technical",
    "models_tab":         "technical",
    "ag_forge_tab":       "creative",
    "custom_code_tab":    "technical",
    "gui":                "operational",
    "Os_Toolkit":         "technical",
    "orchestrator":       "linguistic",
}

_PERSONA_BY_GAP = {
    "critical": "Scholar",
    "medium":   "Engineer",
    "low":      "Mate",
}


def _infer_domain(owning_tab: str) -> str:
    for k, v in _TAB_DOMAIN.items():
        if k in owning_tab:
            return v
    return "general"


# ---------------------------------------------------------------------------
# Control signal derivation (mirrors ControlSignalClassifier in token_generator_v2.py)
# Pure logic — no Morph_regex import needed
# ---------------------------------------------------------------------------

def _derive_control_signal(epistemic: dict, metacog: dict) -> str:
    """Derive control_signal from epistemic + metacognitive state dicts."""
    gap          = epistemic.get("gap_severity", "low")
    recommended  = epistemic.get("recommended_action", "")
    thought      = metacog.get("thought_event", "")
    persona      = metacog.get("active_persona", "")
    probe        = epistemic.get("probe_status", "")

    if recommended in ("TRIGGER_AUDIT_DIFF", "PROACTIVE_INQUIRY"):
        return "STRATEGIC_INQUIRY_OR_AUDIT"
    if probe == "FAIL" or gap == "critical":
        return "CLARIFYING_INQUIRY"
    if thought == "KNOWLEDGE_ACQUISITION":
        return "ASSERTIVE_KNOWLEDGE"
    if thought == "ACTIVITY_TRIGGER":
        return "PROACTIVE_ENGAGEMENT"
    if gap == "medium":
        return "EXPLANATORY_NARRATIVE"

    # Persona fallbacks
    if persona == "Scholar":
        return "FORMAL_EXPLANATION"
    if persona == "Engineer":
        return "TECHNICAL_REPORT"
    if persona == "Mate":
        return "INFORMAL_DIALOGUE"
    return "GENERAL_RESPONSE"


def _derive_sampling_params(epistemic: dict, metacog: dict) -> dict:
    """Derive sampling parameters from state (mirrors SamplingParametersGenerator)."""
    gap         = epistemic.get("gap_severity", "low")
    confidence  = metacog.get("system_confidence", 0.5)
    priority    = metacog.get("volition_score", 0.5)

    temp_map   = {"critical": 0.15, "medium": 0.35, "low": 0.55}
    top_p_map  = {"critical": 0.80, "medium": 0.88, "low": 0.95}

    temperature = temp_map.get(gap, 0.45)
    top_p       = top_p_map.get(gap, 0.90)
    # Lower temperature when confidence is low (be more conservative)
    if confidence < 0.4:
        temperature = max(temperature - 0.1, 0.05)

    return {
        "temperature":    round(temperature, 2),
        "top_p":          round(top_p, 2),
        "repetition_penalty": 1.1,
        "max_new_tokens": 256 if gap in ("critical", "medium") else 128,
        "confidence_bias": round(confidence, 3),
        "priority_bias":   round(priority, 3),
    }


def _derive_dimensional_weights(epistemic: dict, metacog: dict) -> dict:
    """Derive dimensional weight map from state (simplified proxy)."""
    gap         = epistemic.get("gap_severity", "low")
    probe_pass  = epistemic.get("understanding_pct", 0.5)
    activity    = 1.0 - metacog.get("boredom_score", 0.5)
    priority    = metacog.get("volition_score", 0.5)

    gap_weight  = {"critical": 0.9, "medium": 0.6, "low": 0.3}.get(gap, 0.5)

    return {
        "diagnostic":     round(gap_weight, 3),
        "analytic":       round(probe_pass, 3),
        "creative":       round(1.0 - priority, 3),
        "activity":       round(activity, 3),
        "volition":       round(priority, 3),
        "understanding":  round(probe_pass, 3),
        "gap_awareness":  round(gap_weight, 3),
    }


# ---------------------------------------------------------------------------
# OmegaBridge
# ---------------------------------------------------------------------------

class OmegaBridge:
    """
    Translates grounded Os_Toolkit context into Morph_regex state dicts.
    Enables Morph_regex conversation engine to reason about real task/entity data.

    Read-only: Morph_regex files are imported but never modified.
    """

    def __init__(
        self,
        trainer_root: Path,
        morph_regex_path: Path | None = None,
    ):
        self.trainer_root     = Path(trainer_root)
        self.morph_regex_path = Path(morph_regex_path) if morph_regex_path else (
            self.trainer_root / "Models" / "Morph0.1-10m-Babble" / "Morph_regex"
        )
        self._index       = None   # UnifiedContextIndex (lazy)
        self._morph_orc   = None   # MetacognitiveOrchestrator (lazy)
        self._debug_records: list[dict] = []   # SELF_DEBUG records for export

    # ── Index access ─────────────────────────────────────────────────────────

    def _load_index(self):
        if self._index is not None:
            return self._index
        try:
            _scripts = Path(__file__).resolve().parent
            if str(_scripts) not in sys.path:
                sys.path.insert(0, str(_scripts))
            from unified_context_index import get_index
            self._index = get_index(self.trainer_root)
        except Exception as e:
            print(f"[OmegaBridge] Index unavailable: {e}")
            self._index = None
        return self._index

    def _get_entity(self, file_hint: str | None) -> dict:
        """Return entity for file_hint, or {} if not found."""
        if not file_hint:
            return {}
        idx = self._load_index()
        if idx is None:
            return {}
        entity = idx.get(file_hint)
        return entity or {}

    # ── State builders ────────────────────────────────────────────────────────

    def build_epistemic_state(
        self,
        entity: dict,
        event: dict | None = None,
    ) -> dict:
        """
        Maps entity record + optional enriched_change → Morph_regex epistemic_state.

        entity.gap_severity ("high")   → gap_severity = "critical"
        entity.latest_probe ("FAIL")   → understanding_pct = 0.1
        entity.metastate.priority_pct  → priority_pct
        """
        raw_gap      = (entity.get("gap_severity") or "").lower()
        gap_severity = _GAP_MAP.get(raw_gap, "low")

        probe = entity.get("latest_probe")
        if event:
            probe = event.get("probe_status") or probe
        understanding_pct = _PROBE_UNDERSTANDING.get(probe or "", 0.5)

        metastate       = entity.get("metastate") or {}
        priority_pct    = metastate.get("priority_pct") or metastate.get("priority_weight") or 0.5
        rec_action      = metastate.get("recommended_action") or ""

        return {
            "gap_severity":       gap_severity,
            "understanding_pct":  understanding_pct,
            "priority_pct":       float(priority_pct),
            "recommended_action": rec_action,
            "probe_status":       probe or "",
            "entity_file":        entity.get("file", ""),
            "event_id":           (event.get("event_id") if event else
                                   entity.get("event_summary", {}).get("latest_event_id", "")),
        }

    def build_metacognitive_state(self, entity: dict) -> dict:
        """
        Maps entity record → Morph_regex metacognitive_state.

        entity.activity_score       → boredom_score = 1 - activity_score
        entity.owning_tab           → active_domain
        entity.event_summary.top_verb → thought_event
        entity.gap_severity         → active_persona
        entity.metastate.priority   → volition_score
        """
        activity_score  = entity.get("activity_score") or 0.5
        boredom_score   = max(0.0, min(1.0, 1.0 - float(activity_score)))
        owning_tab      = entity.get("owning_tab") or "unknown"
        active_domain   = _infer_domain(owning_tab)

        raw_gap         = (entity.get("gap_severity") or "").lower()
        gap_severity    = _GAP_MAP.get(raw_gap, "low")
        active_persona  = _PERSONA_BY_GAP.get(gap_severity, "Assistant")

        ev_summary      = entity.get("event_summary") or {}
        top_verb        = ev_summary.get("top_verb") or ev_summary.get("verbs", [None])[0] or "modify"
        thought_event   = f"VERB_{top_verb.upper()}_ACTIVITY" if top_verb else "STABILITY_CHECK"

        metastate       = entity.get("metastate") or {}
        volition_score  = float(
            metastate.get("priority_pct")
            or metastate.get("priority_weight")
            or 0.5
        )
        probe           = entity.get("latest_probe")
        system_confidence = {
            "PASS": 0.85,
            "WARN": 0.55,
            "FAIL": 0.30,
        }.get(probe or "", 0.5)

        return {
            "active_domain":      active_domain,
            "active_persona":     active_persona,
            "boredom_score":      round(boredom_score, 3),
            "volition_score":     round(volition_score, 3),
            "thought_event":      thought_event,
            "system_confidence":  round(system_confidence, 3),
            "owning_tab":         owning_tab,
            "priority_weight":    round(volition_score, 3),
        }

    # ── Morph_regex orchestrator (lazy, graceful) ─────────────────────────────

    def _load_morph_orchestrator(self):
        """
        Lazy-load Morph_regex MetacognitiveOrchestrator.
        Returns None gracefully if Morph_regex files are missing/broken.

        Morph_regex requires morph_conceptual_vocab.json to initialise
        TokenGeneratorV2. If that file is absent the orchestrator cannot init.
        """
        if self._morph_orc is not None:
            return self._morph_orc
        try:
            import argparse
            # Build a minimal args namespace (only use_variant is tested by Morph_regex)
            fake_args = argparse.Namespace(use_variant=None)

            # Save sys.path to restore afterwards
            _orig_path = sys.path[:]
            sys.path.insert(0, str(self.morph_regex_path))

            # Import MetacognitiveOrchestrator (module name prefixed to avoid cache clash)
            spec = importlib.util.spec_from_file_location(
                "morph_rx_orchestrator",
                self.morph_regex_path / "orchestrator.py",
            )
            mod = importlib.util.module_from_spec(spec)

            # Temporarily evict shared module names that differ between the two orchestrators
            # so Morph_regex loads its own versions (gap_analyzer, realization_engine, etc.)
            _SHADOW_MODS = ["gap_analyzer", "realization_engine", "interaction_resolver",
                            "CDALS_v3", "token_generator_v2", "morph_vocab_builder",
                            "activity_integration_bridge"]
            _saved_mods = {k: sys.modules.pop(k) for k in _SHADOW_MODS if k in sys.modules}
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.modules.update(_saved_mods)  # Restore outer versions

            self._morph_orc = mod.MetacognitiveOrchestrator(fake_args)
            sys.path[:] = _orig_path
            print(f"[OmegaBridge] Morph_regex orchestrator loaded from {self.morph_regex_path}")
        except Exception as e:
            sys.path[:] = sys.path  # ensure not left polluted
            print(f"[OmegaBridge] Morph_regex unavailable (will use fallback): {e}")
            self._morph_orc = None
        return self._morph_orc

    # ── Self-debug pipeline ───────────────────────────────────────────────────

    def run_debug_query(
        self,
        error_text: str,
        file_hint: str | None = None,
    ) -> dict:
        """
        Full self-debug pipeline:
        1. Load entity for file_hint (if provided)
        2. Build epistemic + metacognitive state from entity
        3. Try Morph_regex process_interaction(error_text); fallback to GapAnalyzer
        4. Derive fix_suggestion from entity metastate + response
        5. Append SELF_DEBUG record for later export
        6. Return {response, control_signal, gap_severity, pattern_matched, fix_suggestion}
        """
        entity   = self._get_entity(file_hint)
        epistemic = self.build_epistemic_state(entity)
        metacog   = self.build_metacognitive_state(entity)

        control_signal  = _derive_control_signal(epistemic, metacog)
        gap_severity    = epistemic["gap_severity"]
        pattern_matched = None
        response        = ""

        # ── Try Morph_regex orchestrator ─────────────────────────────────────
        orc = self._load_morph_orchestrator()
        if orc is not None:
            try:
                # Inject grounded gap severity before calling process_interaction
                if hasattr(orc, "epistemic_loop") and hasattr(orc.epistemic_loop, "last_gap_severity"):
                    orc.epistemic_loop.last_gap_severity = gap_severity
                result = orc.process_interaction(error_text)
                response = result.get("response", "")
                ms       = result.get("metacognitive_state", {})
                pattern_matched = ms.get("thought_event") or ms.get("pattern_matched")
                # Prefer Morph's control signal if richer
                morph_meta = result.get("metacognitive_state", {})
                if morph_meta.get("priority_weight", 0) > 0:
                    control_signal = _derive_control_signal(
                        {**epistemic, **result.get("epistemic_state", {})},
                        {**metacog, **morph_meta},
                    )
            except Exception as _e:
                print(f"[OmegaBridge] Morph_regex process_interaction error: {_e}")

        # ── Fallback: subprocess ──────────────────────────────────────────────
        if not response and self.morph_regex_path.exists():
            try:
                proc = subprocess.run(
                    [sys.executable, "orchestrator.py", error_text],
                    cwd=str(self.morph_regex_path),
                    capture_output=True, text=True, timeout=30,
                )
                out = proc.stdout.strip()
                # Parse RESPONSE: line from output
                for line in out.splitlines():
                    if line.startswith("RESPONSE:"):
                        response = line[9:].strip()
                    elif line.startswith("METASTATE:") and not pattern_matched:
                        try:
                            ms = json.loads(line[10:].strip())
                            pattern_matched = ms.get("thought_event")
                        except Exception:
                            pass
            except Exception as _se:
                print(f"[OmegaBridge] Subprocess fallback failed: {_se}")

        # ── Fallback: llama_cpp (Morph Alpha GGUF) ────────────────────────────
        if not response:
            llm_response = self._run_llama_inference(
                error_text, entity, epistemic, metacog, control_signal
            )
            if llm_response:
                response = llm_response
                if not pattern_matched:
                    pattern_matched = "LLAMA_CPP_ALPHA"

        # ── GapAnalyzer fallback ──────────────────────────────────────────────
        if not response:
            response = self._fallback_response(error_text, entity, epistemic, metacog)
            if not pattern_matched:
                pattern_matched = "GAP_ANALYSIS_FALLBACK"

        # ── Fix suggestion ────────────────────────────────────────────────────
        fix_suggestion = self._build_fix_suggestion(entity, epistemic, error_text)

        # ── SELF_DEBUG record for training export ─────────────────────────────
        system_prompt = (
            "You are Morph, a code intelligence assistant. Given a debug error and "
            "file context, identify the problem pattern and suggest a concrete fix."
        )
        self._debug_records.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content":
                    f"DEBUG: {error_text}"
                    + (f" [file: {file_hint}]" if file_hint else "")},
                {"role": "assistant", "content":
                    f"Pattern: {pattern_matched or 'UNKNOWN'}\n"
                    f"Signal: {control_signal}\n"
                    f"Fix: {fix_suggestion}"},
            ],
            "metadata": {
                "record_type":    "SELF_DEBUG",
                "file":           file_hint or "",
                "control_signal": control_signal,
                "pattern_matched": pattern_matched or "",
                "gap_severity":   gap_severity,
                "timestamp":      datetime.now().isoformat(),
            },
        })

        return {
            "response":        response,
            "control_signal":  control_signal,
            "gap_severity":    gap_severity,
            "pattern_matched": pattern_matched,
            "fix_suggestion":  fix_suggestion,
        }

    def _run_llama_inference(
        self,
        error_text: str,
        entity: dict,
        epistemic: dict,
        metacog: dict,
        control_signal: str,
    ) -> str:
        """
        Run inference against Morph Alpha GGUF via llama_cpp_python.
        Returns the generated response string, or "" on failure.

        Builds a grounded prompt from entity state + error_text so the
        base model has maximal context even before fine-tuning.
        """
        gguf_dir = self.trainer_root / "Models" / "Morph0.1-10m-Babble" / "exports" / "gguf"
        candidates = sorted(gguf_dir.glob("*.gguf")) if gguf_dir.exists() else []
        if not candidates:
            return ""
        gguf_path = candidates[-1]

        try:
            from llama_cpp import Llama  # type: ignore
        except ImportError:
            return ""

        # Build grounded prompt
        file_name  = entity.get("file") or "unknown file"
        gap        = epistemic.get("gap_severity", "low")
        probe      = epistemic.get("probe_status", "n/a")
        rec_action = epistemic.get("recommended_action") or "review"
        persona    = metacog.get("active_persona", "Engineer")
        domain     = metacog.get("active_domain", "technical")

        system = (
            f"You are Morph, a {domain} code intelligence assistant ({persona} mode). "
            f"Analyze the following error in the context of '{Path(file_name).name}'. "
            f"Gap severity: {gap}. Probe: {probe}. Recommended: {rec_action}. "
            f"Control signal: {control_signal}. "
            "Give a concise diagnosis and a concrete fix suggestion."
        )
        user_msg = f"Error: {error_text}"
        prompt   = f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user_msg}<|im_end|>\n<|im_start|>assistant\n"

        try:
            llm = Llama(model_path=str(gguf_path), n_ctx=512, n_threads=4, verbose=False)
            out = llm(prompt, max_tokens=128, echo=False, stop=["<|im_end|>"])
            text = out["choices"][0]["text"].strip()
            if text:
                print(f"[OmegaBridge] llama_cpp response ({Path(gguf_path).name})")
            return text
        except Exception as _le:
            print(f"[OmegaBridge] llama_cpp inference failed: {_le}")
            return ""

    def _fallback_response(
        self,
        error_text: str,
        entity: dict,
        epistemic: dict,
        metacog: dict,
    ) -> str:
        """Generate a structured fallback response using grounded entity data."""
        gap   = epistemic["gap_severity"]
        probe = epistemic.get("probe_status") or "n/a"
        rec   = epistemic.get("recommended_action") or "review code"
        file  = entity.get("file") or entity.get("entity_file", "unknown file")

        lines = [
            f"[{metacog['active_persona']} Mode] <{metacog['active_domain']}>",
            f"Analyzing: {error_text!r}",
            f"File: {file} | Gap: {gap} | Probe: {probe}",
        ]
        if gap in ("critical", "medium"):
            lines.append(f"Recommended action: {rec}")
        ev_summary = entity.get("event_summary") or {}
        top_verb   = ev_summary.get("top_verb")
        if top_verb:
            lines.append(f"Recent activity pattern: {top_verb}")
        return " | ".join(lines)

    def _build_fix_suggestion(
        self,
        entity: dict,
        epistemic: dict,
        error_text: str,
    ) -> str:
        """Generate a fix suggestion from entity metastate + probe data."""
        metastate  = entity.get("metastate") or {}
        rec_action = (
            metastate.get("recommended_action")
            or epistemic.get("recommended_action")
            or ""
        )
        probe = epistemic.get("probe_status") or "n/a"
        gap   = epistemic["gap_severity"]
        file  = entity.get("file") or ""

        # Error type detection
        error_lower = error_text.lower()
        if "none" in error_lower and "attribute" in error_lower:
            suggestion = f"Guard against NoneType: add `or []`/`or {{}}` before attribute access"
        elif "import" in error_lower:
            suggestion = "Verify import paths; check sys.path ordering for circular imports"
        elif "key" in error_lower and "error" in error_lower:
            suggestion = "Use .get() instead of direct dict access; verify key existence"
        elif probe == "FAIL":
            suggestion = f"Fix probe failures in {Path(file).name or 'file'}: run exec-probe and check errors"
        elif gap == "critical":
            suggestion = f"Critical gap: {rec_action or 'prioritise immediate review'}"
        elif rec_action:
            suggestion = rec_action
        else:
            suggestion = f"Review recent changes in {Path(file).name or 'file'}"

        return suggestion

    # ── Token endpoint ────────────────────────────────────────────────────────

    def get_token_endpoint(self, file_hint: str) -> dict:
        """
        Generate TokenGeneratorV2-compatible control packet for file_hint's grounded state.

        Returns: {
            control_signal, sampling_params, dimensional_weights,
            top_biased_tokens (list[str][:10]),
            morph_state_sha, entity_summary
        }

        When morph_conceptual_vocab.json exists, also includes full bias_vector.
        Falls back to pure-logic derivation if Morph_regex files are incomplete.
        """
        entity   = self._get_entity(file_hint)
        epistemic = self.build_epistemic_state(entity)
        metacog   = self.build_metacognitive_state(entity)

        control_signal      = _derive_control_signal(epistemic, metacog)
        sampling_params     = _derive_sampling_params(epistemic, metacog)
        dimensional_weights = _derive_dimensional_weights(epistemic, metacog)

        # Derive top biased tokens from entity (verb/domain/persona heuristic)
        ev_summary  = entity.get("event_summary") or {}
        top_verb    = ev_summary.get("top_verb") or "modify"
        domain      = metacog["active_domain"]
        persona     = metacog["active_persona"]
        gap         = epistemic["gap_severity"]
        top_biased  = self._derive_top_tokens(top_verb, domain, persona, gap)

        # Morph_state SHA (deterministic from key state fields)
        sha_data = json.dumps({
            "control_signal":  control_signal,
            "gap_severity":    gap,
            "understanding":   epistemic["understanding_pct"],
            "active_domain":   domain,
            "active_persona":  persona,
        }, sort_keys=True)
        morph_state_sha = hashlib.sha256(sha_data.encode()).hexdigest()[:16]

        packet: dict = {
            "control_signal":      control_signal,
            "sampling_params":     sampling_params,
            "dimensional_weights": dimensional_weights,
            "top_biased_tokens":   top_biased,
            "morph_state_sha":     morph_state_sha,
            "entity_summary": {
                "file":             entity.get("file", ""),
                "gap_severity":     gap,
                "probe_status":     epistemic.get("probe_status", ""),
                "activity_score":   entity.get("activity_score", 0),
                "owning_tab":       entity.get("owning_tab", ""),
                "top_verb":         top_verb,
            },
        }

        # Attempt full bias_vector via Morph_regex TokenGeneratorV2 (needs vocab)
        vocab_path = self.morph_regex_path / "morph_conceptual_vocab.json"
        if vocab_path.exists():
            try:
                _orig = sys.path[:]
                sys.path.insert(0, str(self.morph_regex_path))
                from token_generator_v2 import TokenGeneratorV2 as _TGV2
                tgv2 = _TGV2(
                    vocab_path=vocab_path,
                    speech_pattern_store_path=self.morph_regex_path / "speech_pattern_store.json",
                    response_weights_path=self.morph_regex_path / "response_weights.json",
                    knowledge_base_path=self.morph_regex_path / "regex" / "knowledge_base.json",
                    activity_tools_path=self.morph_regex_path / "activity_tools.json",
                )
                sys.path[:] = _orig

                cp = tgv2.generate_control_packet(
                    resp_event={"preset": "MEDIUM_STMT", "length_weight": 0.5},
                    epistemic_state=epistemic,
                    slots={
                        "subject": Path(entity.get("file", "")).name,
                        "domain":  domain,
                    },
                    metacognitive_state=metacog,
                    regex_debug={},
                    activity_tools={},
                )
                packet["bias_vector"]    = cp.get("bias_vector", [])
                packet["morph_state_sha"] = cp.get("morph_state_sha", morph_state_sha)
                packet["control_signal"]  = cp.get("control_signal", control_signal)
            except Exception as _e:
                sys.path[:] = sys.path
                packet["bias_vector_note"] = f"Full bias_vector unavailable: {_e}"

        return packet

    def _derive_top_tokens(
        self,
        top_verb: str,
        domain: str,
        persona: str,
        gap: str,
    ) -> list[str]:
        """Derive 10 heuristic top-biased tokens from entity state."""
        tokens = []
        # Domain tokens
        domain_tokens = {
            "technical":    ["debug", "analyze", "trace", "probe", "fix"],
            "creative":     ["explore", "generate", "expand", "innovate"],
            "operational":  ["monitor", "status", "check", "verify"],
            "linguistic":   ["parse", "classify", "match", "map"],
            "general":      ["examine", "review", "assess"],
        }
        tokens.extend(domain_tokens.get(domain, ["review"])[:3])

        # Verb token
        if top_verb and top_verb not in tokens:
            tokens.append(top_verb)

        # Gap tokens
        gap_tokens = {
            "critical": ["urgent", "critical", "error", "fail", "repair"],
            "medium":   ["warning", "review", "check", "inspect"],
            "low":      ["stable", "confirm", "verify"],
        }
        tokens.extend(gap_tokens.get(gap, ["review"])[:3])

        # Persona tone tokens
        persona_tokens = {
            "Scholar":  ["analyze", "systematic", "rigorous"],
            "Engineer": ["implement", "efficient", "robust"],
            "Mate":     ["quick", "simple", "check"],
        }
        tokens.extend(persona_tokens.get(persona, [])[:2])

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                unique.append(t)

        return unique[:10]

    # ── Variant spawner ───────────────────────────────────────────────────────

    def spawn_grounded_variant(self, file_hint: str) -> Path:
        """
        Spawn a MorphVariantSpawner variant from file_hint's grounded state.
        Saves variant to Morph_regex/variants/morph_variant_{SHA}.json.

        Falls back to pure-logic variant JSON if MorphVariantSpawner is unavailable
        (e.g. morph_conceptual_vocab.json missing).
        """
        entity   = self._get_entity(file_hint)
        epistemic = self.build_epistemic_state(entity)
        metacog   = self.build_metacognitive_state(entity)
        packet   = self.get_token_endpoint(file_hint)

        variants_dir = self.morph_regex_path / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        sha = packet.get("morph_state_sha", hashlib.sha256(file_hint.encode()).hexdigest()[:16])

        # Try MorphVariantSpawner first (needs vocab)
        vocab_path = self.morph_regex_path / "morph_conceptual_vocab.json"
        if vocab_path.exists():
            try:
                _orig = sys.path[:]
                sys.path.insert(0, str(self.morph_regex_path))
                from morph_variant_spawner import MorphVariantSpawner as _MVS

                spawner = _MVS(
                    vocab_path=vocab_path,
                    speech_pattern_store_path=self.morph_regex_path / "speech_pattern_store.json",
                    response_weights_path=self.morph_regex_path / "response_weights.json",
                    knowledge_base_path=self.morph_regex_path / "regex" / "knowledge_base.json",
                    activity_tools_path=self.morph_regex_path / "activity_tools.json",
                    variant_output_dir=variants_dir,
                    variant_registry_path=self.morph_regex_path / "variant_registry.json",
                )
                sys.path[:] = _orig

                # Build orchestrator output snapshot from grounded state
                orc_output = {
                    "resp_event":       {"preset": "MEDIUM_STMT", "length_weight": 0.5},
                    "epistemic_state":  epistemic,
                    "5w1h_resolution":  {
                        "subject": Path(entity.get("file", "")).name,
                        "domain":  metacog["active_domain"],
                        "gap":     epistemic["gap_severity"],
                    },
                    "metacognitive_state": {
                        **metacog,
                        "thought_event": metacog["thought_event"],
                    },
                    "regex_debug": {},
                }
                result = spawner.spawn_variant_from_orchestrator_output(orc_output)
                vpath  = Path(result.get("path", variants_dir / f"morph_variant_{sha}.json"))
                print(f"[OmegaBridge] Variant spawned (MorphVariantSpawner): {vpath}")
                return vpath
            except Exception as _e:
                sys.path[:] = sys.path
                print(f"[OmegaBridge] MorphVariantSpawner unavailable, writing pure-logic variant: {_e}")

        # Pure-logic fallback variant JSON
        variant_data = {
            "morph_state_sha":        sha,
            "control_signal":         packet["control_signal"],
            "sampling_params":        packet["sampling_params"],
            "dimensional_weights_map": packet["dimensional_weights"],
            "top_biased_tokens":      packet.get("top_biased_tokens", []),
            "originating_state_summary": {
                "active_domain":     metacog["active_domain"],
                "active_persona":    metacog["active_persona"],
                "gap_severity":      epistemic["gap_severity"],
                "system_confidence": metacog["system_confidence"],
                "understanding_pct": epistemic["understanding_pct"],
                "entity_file":       entity.get("file", ""),
            },
            "timestamp": datetime.now().isoformat(),
            "source":    "omega_bridge_pure_logic",
        }
        out_path = variants_dir / f"morph_variant_{sha}.json"
        out_path.write_text(json.dumps(variant_data, indent=2), encoding="utf-8")
        print(f"[OmegaBridge] Variant written (pure-logic): {out_path}")
        return out_path

    # ── Debug record access (for MorphDatasetExporter) ────────────────────────

    # ------------------------------------------------------------------
    # explain_period — feed temporal narrative into Morph (L4)
    # ------------------------------------------------------------------

    def explain_period(self, narrative: dict) -> dict:
        """
        Feed a temporal narrative dict (from TemporalNarrativeEngine.explain())
        into Morph_regex for an AI-driven session summary response.

        Steps:
          1. Build epistemic_state from narrative metadata
          2. Build metacognitive_state from dominant files/tasks
          3. Format narrative_text as process_interaction() input
          4. Call process_interaction() → CDALS pattern match + response
          5. Append SELF_EXPLAIN record to _debug_records for export

        Parameters
        ----------
        narrative : dict
            Result from TemporalNarrativeEngine.explain()

        Returns
        -------
        dict:
            {response, control_signal, pattern_matched, gap_severity}
        """
        period = narrative.get('period', {})
        files_touched = narrative.get('files_touched', [])
        tasks_active = narrative.get('tasks_active', [])
        risk_events = narrative.get('risk_events', [])
        probe_chain = narrative.get('probe_chain', [])
        narrative_text = narrative.get('narrative', '')
        phase_label = narrative.get('phase_summary', 'Session recap')

        # 1. Build epistemic_state from narrative
        probe_statuses = [f.get('probe_status') for f in files_touched if f.get('probe_status')]
        fail_count = sum(1 for s in probe_statuses if s == 'FAIL')
        pass_count = sum(1 for s in probe_statuses if s == 'PASS')
        total_probes = max(fail_count + pass_count, 1)

        has_critical = any(r['risk_level'] == 'CRITICAL' for r in risk_events)
        has_high = any(r['risk_level'] == 'HIGH' for r in risk_events)
        p1_tasks = [t for t in tasks_active if 'P1' in str(t.get('phase', ''))]

        epistemic_state = {
            'gap_severity': 'critical' if has_critical else ('high' if has_high else 'low'),
            'understanding_pct': pass_count / total_probes,
            'priority_pct': len(p1_tasks) / max(len(tasks_active), 1),
            'recommended_action': 'review_changes' if (has_critical or fail_count > 0) else 'continue',
        }

        # 2. Build metacognitive_state from dominant context
        dominant_file = files_touched[0]['file'] if files_touched else ''
        # Infer domain from dominant file path
        domain_map = {
            'planner_tab': 'technical',
            'models_tab': 'model_management',
            'custom_code_tab': 'code_generation',
            'ag_forge_tab': 'knowledge_engineering',
            'omega_bridge': 'meta_learning',
            'CDALS': 'pattern_recognition',
            'Morph': 'language_model',
        }
        active_domain = 'technical'
        for key, domain in domain_map.items():
            if key.lower() in dominant_file.lower():
                active_domain = domain
                break

        metacognitive_state = {
            'active_domain': active_domain,
            'active_persona': 'Scholar' if has_critical else 'Explorer',
            'system_confidence': pass_count / total_probes,
            'boredom_score': max(0.0, 1.0 - len(files_touched) / 10.0),
            'volition_score': epistemic_state['priority_pct'],
            'thought_event': phase_label,
        }

        # 3. Format narrative as process_interaction() input
        period_str = f"{period.get('since', '?')[:10]} to {period.get('until', '?')[:10]}"
        interaction_text = (
            f"SESSION RECAP [{phase_label}] ({period_str})\n"
            f"{narrative_text}\n"
            f"Probe chain resolutions: {len(probe_chain)}\n"
            f"What can you infer from this session's activity?"
        )

        # 4. Call Morph_regex if available
        result = {
            'response': '',
            'control_signal': 'unknown',
            'pattern_matched': 'unknown',
            'gap_severity': epistemic_state['gap_severity'],
        }

        try:
            self._load_morph_orchestrator()
            if self._morph_orc:
                # Inject grounded states
                if hasattr(self._morph_orc, 'epistemic_state'):
                    self._morph_orc.epistemic_state.update(epistemic_state)
                if hasattr(self._morph_orc, 'metacognitive_state'):
                    self._morph_orc.metacognitive_state.update(metacognitive_state)

                raw = self._morph_orc.process_interaction(interaction_text)
                if isinstance(raw, dict):
                    # Match the same key extraction as run_debug_query
                    result['response'] = (
                        raw.get('response') or
                        raw.get('ideal_response') or
                        raw.get('output') or
                        str(raw)
                    )
                    ms = raw.get('metacognitive_state', {})
                    result['control_signal'] = (
                        raw.get('control_signal') or
                        ms.get('thought_event') or
                        'GENERAL_RESPONSE'
                    )
                    result['pattern_matched'] = (
                        raw.get('pattern_matched') or
                        ms.get('pattern_matched') or
                        'unknown'
                    )
                else:
                    result['response'] = str(raw)
        except Exception as _e:
            import traceback as _tb
            _tb.print_exc()
            result['response'] = f"[Morph unavailable: {_e}] Narrative: {narrative_text[:200]}"

        # 5. Append SELF_EXPLAIN record for JSONL export
        system_prompt = (
            "You are Morph, a self-aware code intelligence assistant. "
            "Summarise what was worked on and what it means for the system."
        )
        self._debug_records.append({
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': interaction_text},
                {'role': 'assistant', 'content': result['response'] or narrative_text},
            ],
            'metadata': {
                'record_type': 'SELF_EXPLAIN',
                'period_since': period.get('since', ''),
                'period_until': period.get('until', ''),
                'phase_label': phase_label,
                'files_touched': len(files_touched),
                'tasks_active': len(tasks_active),
                'control_signal': result['control_signal'],
                'gap_severity': epistemic_state['gap_severity'],
            },
        })

        return result

    def get_debug_records(self) -> list[dict]:
        """Return accumulated SELF_DEBUG + SELF_EXPLAIN records for JSONL export."""
        return list(self._debug_records)

    def clear_debug_records(self):
        """Clear accumulated debug records."""
        self._debug_records.clear()


# ---------------------------------------------------------------------------
# Module-level helper (mirrors orchestrator pattern)
# ---------------------------------------------------------------------------

_DEFAULT_BRIDGE: OmegaBridge | None = None


def get_bridge(
    trainer_root: Path | None = None,
    morph_regex_path: Path | None = None,
) -> OmegaBridge:
    """Return (or create) the default singleton OmegaBridge."""
    global _DEFAULT_BRIDGE
    if _DEFAULT_BRIDGE is None:
        _root = trainer_root or Path(__file__).parents[7]
        _DEFAULT_BRIDGE = OmegaBridge(_root, morph_regex_path)
    return _DEFAULT_BRIDGE


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser(description="OmegaBridge standalone test")
    _parser.add_argument("--entity",   metavar="FILE", help="Test entity lookup")
    _parser.add_argument("--debug",    metavar="ERROR", help="Test run_debug_query")
    _parser.add_argument("--endpoint", metavar="FILE", help="Test get_token_endpoint")
    _args = _parser.parse_args()

    _trainer = Path(__file__).parents[7]
    _bridge  = OmegaBridge(_trainer)

    if _args.entity:
        _ent = _bridge._get_entity(_args.entity)
        if _ent:
            _ep = _bridge.build_epistemic_state(_ent)
            _mc = _bridge.build_metacognitive_state(_ent)
            print(f"Epistemic  : {json.dumps(_ep, indent=2)}")
            print(f"Metacognitive: {json.dumps(_mc, indent=2)}")
        else:
            print(f"No entity found for: {_args.entity!r}")

    if _args.debug:
        _res = _bridge.run_debug_query(_args.debug, _args.entity)
        print(f"Control Signal : {_res['control_signal']}")
        print(f"Pattern Matched: {_res['pattern_matched']}")
        print(f"Gap Severity   : {_res['gap_severity']}")
        print(f"Response       : {_res['response']}")
        print(f"Fix Suggestion : {_res['fix_suggestion']}")

    if _args.endpoint:
        _pkt = _bridge.get_token_endpoint(_args.endpoint)
        print(json.dumps(_pkt, indent=2))
