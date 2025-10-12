# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Evaluation Engine
This component is responsible for running benchmark tests against models,
scoring their performance, and generating reports.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import requests
from config import load_system_prompt, load_tool_schema

class EvaluationEngine:
    """
    Manages the evaluation pipeline, including running benchmarks,
    comparing models, and verifying skills.
    """

    def __init__(self, tests_dir: Path):
        """
        Initializes the evaluation engine.

        Args:
            tests_dir: The root directory where test suites are stored.
        """
        self.tests_dir = tests_dir
        # Debug log file under Data/DeBug
        try:
            self._debug_dir = Path(__file__).parent / 'DeBug'
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            self._debug_file = self._debug_dir / 'eval_debug.log'
        except Exception:
            self._debug_dir = None
            self._debug_file = None

    def _log(self, msg: str):
        try:
            if not self._debug_file:
                return
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self._debug_file.open('a', encoding='utf-8') as f:
                f.write(f"[{ts}] {msg}\n")
        except Exception:
            pass

    def run_benchmark(self, model_name: str, test_suite_name: str,
                      system_prompt_name: str = None,
                      tool_schema_name: str = None,
                      *, sample_fraction: float = None,
                      inference_override: str = None) -> Dict[str, Any]:
        """
        Runs a full test suite against a specified model.

        Args:
            model_name: The name of the model to test.
            test_suite_name: The name of the test suite to run (e.g., "Tools").
            system_prompt_name: Optional name of the system prompt to use.
            tool_schema_name: Optional name of the tool schema to use.

        Returns:
            A dictionary containing aggregated scores and results.
        """
        print(f"Running benchmark for model '{model_name}' on test suite '{test_suite_name}'...")

        # Support special 'All' suite to aggregate across all available suites
        test_files: List[Path] = []
        if test_suite_name == "All":
            if not self.tests_dir.exists():
                return {"error": f"Tests root not found: {self.tests_dir}"}
            for suite in sorted([d for d in self.tests_dir.iterdir() if d.is_dir()]):
                test_files.extend(sorted(suite.glob("*.jsonl")))
            if not test_files:
                return {"error": f"No tests found under {self.tests_dir}"}
        else:
            suite_dir = self.tests_dir / test_suite_name
            if not suite_dir.is_dir():
                print(f"Error: Test suite directory not found at {suite_dir}")
                return {"error": f"Test suite '{test_suite_name}' not found."}
            test_files = list(suite_dir.glob("*.jsonl"))
            if not test_files:
                print(f"Error: No .jsonl test files found in {suite_dir}")
                return {"error": f"No tests found for suite '{test_suite_name}'."}

        all_test_cases = []
        for test_file in test_files:
            try:
                with open(test_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            all_test_cases.append(json.loads(line))
            except Exception as e:
                print(f"Error reading or parsing {test_file}: {e}")
                continue
        
        print(f"Loaded {len(all_test_cases)} test cases from {len(test_files)} files.")

        # Optional sampling for quick regression runs
        if sample_fraction is not None:
            try:
                import random
                if 0.0 < float(sample_fraction) < 1.0 and len(all_test_cases) > 1:
                    k = max(1, int(len(all_test_cases) * float(sample_fraction)))
                    all_test_cases = random.sample(all_test_cases, k)
            except Exception:
                pass

        # Prepare schema index if a tool schema is provided
        schema_index = None
        if tool_schema_name:
            try:
                from config import load_tool_schema
                schema_dict = load_tool_schema(tool_schema_name)
                schema_index = self._build_schema_index(schema_dict)
            except Exception:
                schema_index = None

        results = []
        scoring_counts: Dict[str, int] = {}
        # Behavior aggregates
        per_tool: Dict[str, Dict[str, Any]] = {}
        per_difficulty: Dict[str, Dict[str, Any]] = {}
        per_policy_stats: Dict[str, Dict[str, Any]] = {}
        per_tag: Dict[str, Dict[str, Any]] = {}
        confusion_matrix: Dict[str, Dict[str, int]] = {}
        arg_errors = {"missing": 0, "mismatch": 0, "extra": 0, "schema_fail": 0, "non_json": 0, "path_format": 0, "policy_violation": 0}
        json_valid_count = 0
        schema_valid_count = 0
        elapsed_sum_ms = 0
        total_steps = 0
        predicted_tools = set()
        for test_case in all_test_cases:
            # Track scoring policy used (treat sequences specially)
            policy = test_case.get("scoring", "exact_match")
            if isinstance(test_case, dict) and "sequence" in test_case:
                policy = "sequence"
                scoring_counts[policy] = scoring_counts.get(policy, 0) + 1
                result = self._execute_sequence_test_case(
                    model_name, test_case, system_prompt_name, tool_schema_name, schema_index, inference_override
                )
                # Aggregate sequence per-step confusion and errors if available
                steps = result.get("sequence_details") or []
                total_steps += max(1, len(steps))
                for s in steps:
                    exp_tool = None
                    pred_tool = None
                    # We carried details in step entries
                    exp_tool = (s.get("expected", {}) or {}).get("tool") if isinstance(s.get("expected"), dict) else None
                    pred_tool = (s.get("predicted", {}) or {}).get("tool") if isinstance(s.get("predicted"), dict) else None
                    if exp_tool or pred_tool:
                        cm = confusion_matrix.setdefault(exp_tool or "<none>", {})
                        cm[pred_tool or "<none>"] = cm.get(pred_tool or "<none>", 0) + 1
                    # Tags / difficulty roll up from parent test
                # Tagging by category (fallback)
                cat = (test_case.get("category") or "").lower()
                inferred_tag = None
                if cat == "adversarial": inferred_tag = "adversarial"
                elif cat == "paraphrasing": inferred_tag = "paraphrasing"
                elif cat == "thinktime" or cat == "think_time": inferred_tag = "think_time"
                elif cat == "workflows": inferred_tag = "workflows"
                # Update per_tag totals
                tag = inferred_tag or (test_case.get("tags") or [None])[0]
                if tag:
                    b = per_tag.setdefault(tag, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                    b["total"] += 1
                    if result.get("passed"): b["passed"] += 1
            else:
                result = self._execute_test_case(model_name, test_case, system_prompt_name, tool_schema_name, schema_index, inference_override)
                scoring_counts[policy] = scoring_counts.get(policy, 0) + 1
                total_steps += 1
                # Aggregations for single-step tests
                diff = (test_case.get("difficulty") or "Unknown").title()
                b = per_difficulty.setdefault(diff, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                b["total"] += 1
                if result.get("passed"): b["passed"] += 1

                exp_tool = (result.get("expected") or {}).get("tool")
                pred_tool = (result.get("predicted") or {}).get("tool")
                if exp_tool:
                    t = per_tool.setdefault(exp_tool, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                    t["total"] += 1
                    if result.get("passed"): t["passed"] += 1
                # Policy stats
                pstat = per_policy_stats.setdefault(policy, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                pstat["total"] += 1
                if result.get("passed"): pstat["passed"] += 1
                # Confusions
                cm = confusion_matrix.setdefault(exp_tool or "<none>", {})
                cm[pred_tool or "<none>"] = cm.get(pred_tool or "<none>", 0) + 1
                # Arg error types
                et = result.get("error_type")
                if et == "args_missing": arg_errors["missing"] += 1
                elif et == "args_mismatch": arg_errors["mismatch"] += 1
                elif et == "extra_args": arg_errors["extra"] += 1
                elif et == "schema_validation_failed": arg_errors["schema_fail"] += 1
                elif et == "non_json": arg_errors["non_json"] += 1
                elif et == "path_format_issue": arg_errors["path_format"] += 1
                elif et == "policy_violation": arg_errors["policy_violation"] += 1
                # Preference violations (simple rules)
                if exp_tool == "file_search" and pred_tool == "directory_list":
                    arg_errors["policy_violation"] += 1
                if exp_tool == "file_write" and pred_tool == "file_create":
                    arg_errors["policy_violation"] += 1
                # JSON/schema validity
                if result.get("json_valid") is True: json_valid_count += 1
                if result.get("schema_valid") is True: schema_valid_count += 1
                # Elapsed
                try:
                    elapsed_sum_ms += int(result.get("elapsed_ms") or 0)
                except Exception:
                    pass
                # Predicted tools diversity
                if pred_tool:
                    predicted_tools.add(pred_tool)
            results.append(result)

        # Aggregate results
        passed_count = sum(1 for r in results if r["passed"])
        total_count = len(results)
        pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

        # Per-skill aggregation to support comparisons and skills tab
        per_skill: Dict[str, Dict[str, Any]] = {}
        for r in results:
            skill = r.get("skill") or "Unknown"
            bucket = per_skill.setdefault(skill, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
            bucket["total"] += 1
            if r.get("passed"):
                bucket["passed"] += 1
        for s, v in per_skill.items():
            rate = (v["passed"] / v["total"] * 100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"

        # Per-category aggregation
        per_category: Dict[str, Dict[str, Any]] = {}
        for r in results:
            cat = r.get("category") or (r.get("test_case_obj", {}).get("category") if isinstance(r.get("test_case_obj"), dict) else None) or "Unknown"
            bucket = per_category.setdefault(cat, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
            bucket["total"] += 1
            if r.get("passed"):
                bucket["passed"] += 1
        for c, v in per_category.items():
            rate = (v["passed"] / v["total"] * 100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"

        # Finalize aggregates
        for k, v in per_tool.items():
            rate = (v["passed"]/v["total"]*100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"
        for k, v in per_difficulty.items():
            rate = (v["passed"]/v["total"]*100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"
        for k, v in per_policy_stats.items():
            rate = (v["passed"]/v["total"]*100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"
        for k, v in per_tag.items():
            rate = (v["passed"]/v["total"]*100) if v["total"] else 0.0
            v["pass_rate_percent"] = f"{rate:.2f}%"

        # Ensure defaults exist with 0% so UI can render a full inventory
        # Per-policy defaults
        for pol in ["exact_match", "args_subset", "partial_match", "function_call_match", "sequence"]:
            if pol not in per_policy_stats:
                per_policy_stats[pol] = {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"}
        # Per-difficulty defaults
        for diff in ["Basic", "Intermediate", "Hard"]:
            if diff not in per_difficulty:
                per_difficulty[diff] = {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"}
        # Per-tag defaults
        for tag in ["think_time", "adversarial", "paraphrasing", "workflows"]:
            if tag not in per_tag:
                per_tag[tag] = {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"}
        # Per-category defaults (common suites)
        for cat in ["Tools", "Workflows", "Adversarial", "Paraphrasing", "ThinkTime", "Orchestration"]:
            if cat not in per_category:
                per_category[cat] = {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"}
        # Per-tool defaults: if schema provided, include all tool names at 0%
        try:
            if schema_index:
                for tool_name in schema_index.keys():
                    if tool_name not in per_tool:
                        per_tool[tool_name] = {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"}
        except Exception:
            pass

        sequence_tests = sum(1 for r in results if r.get("policy") == "sequence")
        total_results = len(results)
        json_valid_rate = (json_valid_count/total_results*100) if total_results else 0.0
        schema_valid_rate = (schema_valid_count/total_results*100) if total_results else 0.0
        avg_elapsed_ms = int(elapsed_sum_ms/max(1, len(results)))
        avg_steps = float(total_steps)/max(1, len(results))

        # Behavior scores (heuristic, judge-free)
        # Compliance: emphasize JSON+schema validity and low violations
        vio = arg_errors.get('policy_violation', 0)
        arg_err = arg_errors.get('missing',0) + arg_errors.get('mismatch',0) + arg_errors.get('extra',0) + arg_errors.get('path_format',0) + arg_errors.get('schema_fail',0)
        vio_rate = (vio/max(1, total_results))*100.0
        arg_err_rate = (arg_err/max(1, total_results))*100.0
        compliance_raw = max(0.0, min(100.0, 0.5*(json_valid_rate + schema_valid_rate) - 0.5*(vio_rate + arg_err_rate)))

        # Creativity: diversity of tool selection + tendency to free-form (non_json) when tools are expected
        unique_pred_rate = (len(predicted_tools)/max(1, len(per_tool))) if per_tool else (1.0 if predicted_tools else 0.0)
        non_json_rate = (arg_errors.get('non_json',0)/max(1, total_results))
        creativity_raw = max(0.0, min(100.0, 50.0*unique_pred_rate + 50.0*non_json_rate))

        # Coherence: sequence reliability; fallback to low arg error rate when no sequences
        if sequence_tests > 0:
            # Approximate with avg_steps quality: fewer step failures reflected in overall pass and arg_err_rate
            # Use overall pass rate as proxy for coherence across sequences
            seq_pass_rate = (passed_count/max(1, total_count))*100.0
            coherence_raw = max(0.0, min(100.0, seq_pass_rate - arg_err_rate))
        else:
            coherence_raw = max(0.0, min(100.0, 100.0 - arg_err_rate - vio_rate))

        summary = {
            "version": "eval_report_v2",
            "total_tests": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "pass_rate_percent": f"{pass_rate:.2f}%",
            "results": results,
            "per_skill": per_skill,
            "per_category": per_category,
            "metrics": {
                "per_tool": per_tool,
                "per_difficulty": per_difficulty,
                "per_policy": per_policy_stats,
                "per_tag": per_tag,
                "confusion_matrix": confusion_matrix,
                "arg_errors": arg_errors,
                "json_valid_rate": f"{json_valid_rate:.2f}%",
                "schema_valid_rate": f"{schema_valid_rate:.2f}%",
                "avg_elapsed_ms": avg_elapsed_ms,
                "avg_steps": avg_steps,
                "sequence_tests": sequence_tests,
                "behavior": {
                    "compliance": f"{compliance_raw:.2f}%",
                    "creativity": f"{creativity_raw:.2f}%",
                    "coherence": f"{coherence_raw:.2f}%"
                }
            },
            "metadata": {
                "model_name": model_name,
                "suite": test_suite_name,
                "prompt_name": system_prompt_name or None,
                "schema_name": tool_schema_name or None,
                "inference_model": inference_override or model_name,
                "sample_fraction": sample_fraction,
                "scoring": {
                    "policies_used": scoring_counts,
                    "schema_validated": bool(schema_index)
                }
            }
        }
        
        print(f"Benchmark finished. Pass rate: {pass_rate:.2f}% ({passed_count}/{total_count})")

        return summary

    def _execute_sequence_test_case(self, model_name: str, test_case: Dict[str, Any],
                                    system_prompt_name: str,
                                    tool_schema_name: str,
                                    schema_index: Dict[str, Any],
                                    inference_override: str = None) -> Dict[str, Any]:
        """Evaluate a multi-step sequence where each step has its own expected tool call.

        test_case shape:
        {
          "category": "Workflows",
          "skill": "multi_step_read_then_search",
          "sequence": [
            {"input": "...", "expected_tool": "file_read", "expected_args": { ... }, "scoring": "args_subset"},
            {"input": "...", "expected_tool": "grep_search", "expected_args": { ... }, "scoring": "exact_match"}
          ]
        }
        """
        steps = test_case.get("sequence") or []
        if not isinstance(steps, list) or not steps:
            return {
                "test_case": "<sequence: empty>",
                "skill": test_case.get("skill"),
                "category": test_case.get("category"),
                "passed": False,
                "details": "Invalid or empty sequence.",
            }

        per_step = []
        all_passed = True
        for idx, step in enumerate(steps, start=1):
            # Reuse single-step executor by projecting a step-shaped test
            single = {
                "category": test_case.get("category"),
                "skill": test_case.get("skill"),
                "input": step.get("input"),
                "expected_tool": step.get("expected_tool"),
                "expected_args": step.get("expected_args"),
                "scoring": step.get("scoring", test_case.get("scoring", "args_subset")),
            }
            r = self._execute_test_case(model_name, single, system_prompt_name, tool_schema_name, schema_index, inference_override)
            per_step.append({
                "step": idx,
                "passed": bool(r.get("passed")),
                "details": r.get("details"),
                "predicted": r.get("predicted"),
                "expected": r.get("expected"),
                "error_type": r.get("error_type"),
            })
            if not r.get("passed"):
                all_passed = False

        return {
            "test_case": f"Sequence of {len(steps)} steps",
            "skill": test_case.get("skill"),
            "category": test_case.get("category"),
            "passed": all_passed,
            "details": f"{sum(1 for s in per_step if s['passed'])}/{len(per_step)} steps passed.",
            "sequence_details": per_step,
            "policy": "sequence",
        }

    def _get_model_response(self, model_name: str, prompt: str,
                            system_prompt_name: str = None,
                            tool_schema_name: str = None,
                            *, inference_override: str = None) -> Dict[str, Any]:
        """
        Gets a response from a model via the Ollama API, incorporating optional system prompt and tool schema.
        """
        messages = []
        tools_payload = []

        # 1. Load and apply System Prompt
        if system_prompt_name and system_prompt_name != "None":
            try:
                system_prompt_data = load_system_prompt(system_prompt_name)
                system_content = system_prompt_data.get("prompt", "")
                messages.append({"role": "system", "content": system_content})
            except FileNotFoundError:
                print(f"Warning: System prompt '{system_prompt_name}' not found. Proceeding without it.")
            except Exception as e:
                print(f"Error loading system prompt '{system_prompt_name}': {e}. Proceeding without it.")

        # 2. Load and apply Tool Schema
        if tool_schema_name and tool_schema_name != "None":
            try:
                tool_schema_data = load_tool_schema(tool_schema_name)
                tools_payload = tool_schema_data.get("tools", [])
                if not tools_payload:
                    print(f"Warning: Tool schema '{tool_schema_name}' loaded but contains no tools.")
            except FileNotFoundError:
                print(f"Warning: Tool schema '{tool_schema_name}' not found. Proceeding without it.")
            except Exception as e:
                print(f"Error loading tool schema '{tool_schema_name}': {e}. Proceeding without it.")

        # Add user message
        messages.append({"role": "user", "content": prompt})

        # Construct the request payload for Ollama chat API
        ollama_payload = {
            "model": (inference_override or model_name),
            "messages": messages,
            "stream": False,
            "format": "json"
        }
        if tools_payload:
            ollama_payload["tools"] = tools_payload

        # First try /api/chat (newer Ollama supports messages + tools)
        try:
            # Debug: record request outline (no full prompt content to keep log compact)
            self._log(
                "POST /api/chat model=%s msgs=%d tools=%d format=json" % (
                    (inference_override or model_name), len(messages), len(tools_payload)
                )
            )
        except Exception:
            pass
        try:
            response = requests.post("http://localhost:11434/api/chat", json=ollama_payload, timeout=60)
            # If server is reachable but endpoint missing, fallback to /api/generate
            if response.status_code == 404:
                return self._ollama_generate_fallback(model_name, system_prompt_name, tool_schema_name, prompt)
            response.raise_for_status()
            data = response.json()
            # Debug: record response shape
            try:
                snippet = str(data)[:300].replace('\n', ' ')
                self._log(f"/api/chat OK status={response.status_code} body~={len(str(data))} chars snippet={snippet}")
            except Exception:
                pass
            if "message" in data and "tool_calls" in data["message"]:
                calls = data["message"]["tool_calls"] or []
                if calls:
                    fn = calls[0].get("function", {})
                    raw_args = fn.get("arguments")
                    parsed_args = {}
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {}
                    elif isinstance(raw_args, dict):
                        parsed_args = raw_args
                    try:
                        self._log(f"tool_call parsed name={fn.get('name')} args_keys={list(parsed_args.keys())}")
                    except Exception:
                        pass
                    return {"tool_name": fn.get("name"), "tool_args": parsed_args}
                return {"error": "Model did not suggest a tool call."}
            if "message" in data and "content" in data["message"]:
                raw = data["message"]["content"]
                try:
                    j = json.loads(raw)
                    try:
                        _ak = j.get('args') or j.get('arguments') or {}
                        self._log(f"content JSON parsed name={j.get('name')} args_keys={list((_ak or {}).keys())}")
                    except Exception:
                        pass
                    return {"tool_name": j.get("name"), "tool_args": (j.get("args") or j.get("arguments") or {})}
                except json.JSONDecodeError:
                    # Try to extract first JSON object
                    try:
                        self._log("content not JSON; attempting extraction")
                    except Exception:
                        pass
                    return self._parse_json_object(raw)
            return {"error": f"Unexpected response format from Ollama: {data}"}
        except requests.exceptions.ConnectionError:
            print("ERROR: Connection to Ollama failed. Is Ollama running?")
            return {"error": "Ollama connection failed."}
        except requests.exceptions.RequestException as e:
            # Network/HTTP error (not 404), attempt generate fallback
            try:
                return self._ollama_generate_fallback(model_name, system_prompt_name, tool_schema_name, prompt)
            except Exception:
                print(f"ERROR: Ollama API request failed: {e}")
                return {"error": str(e)}
        except Exception as e:
            print(f"An unexpected error occurred during model call: {e}")
            return {"error": str(e)}

    def _ollama_generate_fallback(self, model_name: str, system_prompt_name: str, tool_schema_name: str, user_prompt: str) -> Dict[str, Any]:
        """Fallback for older Ollama servers: call /api/generate with a strict JSON instruction and parse output."""
        # Build a compact instruction
        sys_text = ""
        try:
            if system_prompt_name and system_prompt_name != "None":
                sys_text = (load_system_prompt(system_prompt_name) or {}).get("prompt", "")
        except Exception:
            sys_text = ""
        tools_text = ""
        try:
            if tool_schema_name and tool_schema_name != "None":
                schema = load_tool_schema(tool_schema_name) or {}
                names = [ (t.get('function') or {}).get('name') for t in (schema.get('tools') or []) ]
                names = [n for n in names if n]
                if names:
                    tools_text = "Available tools: " + ", ".join(sorted(set(names)))
        except Exception:
            tools_text = ""
        instr = (
            (sys_text + "\n\n") if sys_text else ""
            ) + (
            (tools_text + "\n") if tools_text else ""
            ) + (
            "Respond ONLY with a single JSON object in the form "
            "{\"name\":\"TOOL_NAME\",\"args\":{...}} matching the available tool. "
            "No extra text.\n\nUser: " + user_prompt
        )
        try:
            # Debug: record fallback request
            self._log(f"POST /api/generate model={model_name} prompt_len={len(instr)}")
            resp = requests.post("http://localhost:11434/api/generate", json={"model": model_name, "prompt": instr, "stream": False}, timeout=60)
            resp.raise_for_status()
            data = resp.json() if isinstance(resp.json(), dict) else {"response": resp.text}
            content = data.get("response") or data.get("message") or ""
            try:
                _snippet = (content or '')[:200].replace('\n', ' ')
                self._log(f"/api/generate OK status={resp.status_code} content_len={len(content)} snippet={_snippet}")
            except Exception:
                pass
            return self._parse_json_object(content)
        except Exception as e:
            self._log(f"/api/generate ERROR: {e}")
            return {"error": f"Fallback generate failed: {e}"}

    def _parse_json_object(self, text: str) -> Dict[str, Any]:
        """Extract first JSON object from text and map to tool_name/args if possible."""
        try:
            return_obj = json.loads(text)
        except Exception:
            # naive extraction
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1 or end <= start:
                return {"error": f"Model responded with non-JSON: {text[:200]}"}
            try:
                return_obj = json.loads(text[start:end+1])
            except Exception:
                return {"error": f"Invalid JSON content: {text[:200]}"}
        return {"tool_name": return_obj.get("name"), "tool_args": (return_obj.get("args") or return_obj.get("arguments") or {})}

    def _execute_test_case(self, model_name: str, test_case: Dict[str, Any],
                            system_prompt_name: str = None,
                            tool_schema_name: str = None,
                            schema_index: Dict[str, Any] = None,
                            inference_override: str = None) -> Dict[str, Any]:
        """
        Executes a single test case against a model.
        """
        # Build a more specific prompt with context and gentle steering per skill
        skill = (test_case.get('skill') or '').strip().lower()
        ctx_files = []
        try:
            ctx_files = list((test_case.get('context') or {}).get('files') or [])
        except Exception:
            ctx_files = []
        hints = []
        if skill == 'grep_search':
            hints.append("This is a text search task; use 'grep_search' and include 'pattern'. If searching across Python files, set file_pattern='*.py'.")
        elif skill == 'file_search':
            hints.append("This is a file listing/search task; use 'file_search'. For 'all in project', use recursive pattern='**/*.py'.")
        elif skill == 'file_read':
            hints.append("This is a file read task; use 'file_read' and include 'file_path' exactly as given. Include start_line/end_line if specified.")
        elif skill == 'file_write':
            hints.append("This is a file write task; use 'file_write' (not file_create) with both 'file_path' and 'content'. Preserve exact newlines.")
        if ctx_files:
            hints.append("Context files: " + ", ".join(ctx_files))
        hints_text = ("\n" + "\n".join(hints) + "\n") if hints else "\n"
        prompt = (
            "You are an expert assistant. Based on the user's request, generate a single, valid JSON object representing a tool call.\n"
            + hints_text + f"User request: '{test_case['input']}'"
        )
        import time
        t0 = time.time()
        model_output = self._get_model_response(model_name, prompt, system_prompt_name, tool_schema_name, inference_override=inference_override)
        t1 = time.time()
        elapsed_ms = int((t1 - t0) * 1000)
        json_valid = ("error" not in model_output)
        try:
            self._log(
                f"TEST '{test_case.get('input')}' -> parsed tool={model_output.get('tool_name')} args_keys={list((model_output.get('tool_args') or {}).keys())}"
            )
        except Exception:
            pass

        if "error" in model_output:
            return {
                "test_case": test_case["input"],
                "skill": test_case["skill"],
                "category": test_case.get("category"),
                "passed": False,
                "details": f"Model API call failed: {model_output['error']}",
                "predicted": {"tool": None, "args": {}},
                "expected": {"tool": test_case.get("expected_tool"), "args": test_case.get("expected_args", {})},
                "policy": test_case.get("scoring", "exact_match"),
                "difficulty": test_case.get("difficulty"),
                "tags": test_case.get("tags"),
                "error_type": "non_json" if 'non-JSON' in model_output.get('error','').lower() else "api_error",
                "json_valid": False,
                "schema_valid": None,
                "elapsed_ms": elapsed_ms
            }
        
        passed = False
        details = ""
        scoring_method = test_case.get("scoring", "exact_match")

        # Schema validation layer (if schema provided)
        if schema_index and "error" not in model_output:
            tool = (model_output.get("tool_name") or "").strip()
            args = model_output.get("tool_args") or {}
            schema_ok, schema_errors = self._validate_against_schema(tool, args, schema_index)
            if not schema_ok:
                return {
                    "test_case": test_case.get("input"),
                    "skill": test_case.get("skill"),
                    "category": test_case.get("category"),
                    "passed": False,
                    "details": f"Schema validation failed: {'; '.join(schema_errors)}",
                    "predicted": {"tool": tool, "args": args},
                    "expected": {"tool": test_case.get("expected_tool"), "args": test_case.get("expected_args", {})},
                    "policy": test_case.get("scoring", "exact_match"),
                    "difficulty": test_case.get("difficulty"),
                    "tags": test_case.get("tags"),
                    "error_type": "schema_validation_failed",
                    "json_valid": json_valid,
                    "schema_valid": False,
                    "elapsed_ms": elapsed_ms,
                    "test_case_obj": test_case
                }

        error_type = None
        arg_diff = {"missing": [], "mismatch": [], "extra": []}
        if scoring_method == "exact_match":
            tool_match = model_output["tool_name"] == test_case["expected_tool"]
            args_match = model_output["tool_args"] == test_case["expected_args"]
            
            if tool_match and args_match:
                passed = True
                details = "Exact match on tool name and arguments."
            else:
                details = f"Mismatch. Expected tool '{test_case['expected_tool']}' with args {test_case['expected_args']}, but got tool '{model_output['tool_name']}' with args {model_output['tool_args']}"
                error_type = "tool_mismatch" if not tool_match else "args_mismatch"

        elif scoring_method == "partial_match":
            tool_match = model_output["tool_name"] == test_case["expected_tool"]
            if not tool_match:
                details = f"Tool name mismatch. Expected '{test_case['expected_tool']}', got '{model_output['tool_name']}'."
                error_type = "tool_mismatch"
            else:
                args_match = True
                mismatched_args = []
                for arg_key, arg_value in model_output["tool_args"].items():
                    if arg_key not in test_case["expected_args"] or test_case["expected_args"][arg_key] != arg_value:
                        args_match = False
                        mismatched_args.append(f"Arg '{arg_key}': Expected '{test_case['expected_args'].get(arg_key)}', Got '{arg_value}'")
                        arg_diff["mismatch"].append(arg_key)
                
                if args_match:
                    passed = True
                    details = "Partial match successful. All provided arguments were correct."
                else:
                    details = "Partial match failed. " + "; ".join(mismatched_args)
                    error_type = "args_mismatch"
        elif scoring_method == "function_call_match":
            # Only verify tool name is correct; ignore arguments.
            tool_match = model_output.get("tool_name") == test_case.get("expected_tool")
            passed = bool(tool_match)
            details = "Tool name matches expected." if passed else (
                f"Tool mismatch. Expected '{test_case.get('expected_tool')}', got '{model_output.get('tool_name')}'.")
            if not passed:
                error_type = "tool_mismatch"
        elif scoring_method == "args_subset":
            # Verify provided args include at least all required keys with matching values.
            tool_match = model_output.get("tool_name") == test_case.get("expected_tool")
            if not tool_match:
                passed = False
                details = f"Tool name mismatch. Expected '{test_case.get('expected_tool')}', got '{model_output.get('tool_name')}'."
                error_type = "tool_mismatch"
            else:
                expected_args = test_case.get("expected_args", {}) or {}
                actual_args = model_output.get("tool_args", {}) or {}
                missing_or_mismatch = []
                for k, v in expected_args.items():
                    if k not in actual_args or actual_args.get(k) != v:
                        missing_or_mismatch.append(k)
                        if k not in actual_args:
                            arg_diff["missing"].append(k)
                        else:
                            arg_diff["mismatch"].append(k)
                passed = len(missing_or_mismatch) == 0
                details = (
                    "Arguments subset satisfied." if passed else
                    f"Missing/mismatched required args: {missing_or_mismatch}"
                )
                if not passed:
                    error_type = "args_missing" if any(k in arg_diff["missing"] for k in missing_or_mismatch) else "args_mismatch"
        elif scoring_method == "llm_judge":
            # Placeholder: no LLM judge configured in this environment
            passed = False
            details = "LLM_judge not configured; skipping. Use exact/partial/function_call_match/args_subset."
        else:
            details = f"Scoring method '{scoring_method}' is not a recognized type."

        # Inferred tags
        cat = (test_case.get("category") or "").lower()
        tags = test_case.get("tags") or []
        if not tags:
            if cat == "adversarial": tags = ["adversarial"]
            elif cat == "paraphrasing": tags = ["paraphrasing"]
            elif cat in ("thinktime", "think_time"): tags = ["think_time"]
            elif cat == "workflows": tags = ["workflows"]

        return {
            "test_case": test_case["input"],
            "skill": test_case["skill"],
            "category": test_case.get("category"),
            "passed": passed,
            "details": details,
            "predicted": {"tool": model_output.get("tool_name"), "args": (model_output.get("tool_args") or {})},
            "expected": {"tool": test_case.get("expected_tool"), "args": test_case.get("expected_args", {})},
            "policy": scoring_method,
            "difficulty": test_case.get("difficulty"),
            "tags": tags,
            "error_type": (None if passed else (error_type or "unknown")),
            "arg_diff": (None if passed else arg_diff),
            "json_valid": json_valid,
            "schema_valid": (True if schema_index else None),
            "elapsed_ms": elapsed_ms
        }

    # --- Schema helpers ---
    def _build_schema_index(self, schema_dict: Dict[str, Any]) -> Dict[str, Any]:
        try:
            tools = schema_dict.get("tools", [])
            index = {}
            for t in tools:
                fn = (t.get("function") or {})
                name = fn.get("name")
                params = (fn.get("parameters") or {})
                props = (params.get("properties") or {})
                required = set(params.get("required", []))
                index[name] = {"properties": props, "required": required}
            return index
        except Exception:
            return {}

    def _validate_against_schema(self, tool: str, args: Dict[str, Any], index: Dict[str, Any]):
        errors = []
        if not tool or tool not in index:
            return False, [f"Unknown or missing tool '{tool}'"]
        spec = index[tool]
        required = spec.get("required", set())
        props = spec.get("properties", {})
        # Required keys
        for rk in required:
            if rk not in args:
                errors.append(f"Missing required arg '{rk}'")
        # Type checks (simple)
        for k, v in args.items():
            if k in props:
                t = props[k].get("type")
                if t == "string" and not isinstance(v, str):
                    errors.append(f"Arg '{k}' expects string")
                elif t == "integer" and not isinstance(v, int):
                    errors.append(f"Arg '{k}' expects integer")
                elif t == "boolean" and not isinstance(v, bool):
                    errors.append(f"Arg '{k}' expects boolean")
        return (len(errors) == 0), errors

    def compare_models(self, baseline_scores: Dict, new_scores: Dict, *, regression_threshold: float = 5.0, improvement_threshold: float = 5.0) -> Dict[str, Any]:
        """
        Compares two sets of scores and generates an improvement report.

        Args:
            baseline_scores: The scores from the baseline model.
            new_scores: The scores from the newly trained model.

        Returns:
            A dictionary representing the improvement report.
        """
        def _percent_to_float(p: str) -> float:
            try:
                return float(p.replace('%', ''))
            except Exception:
                return 0.0

        baseline_overall = _percent_to_float(baseline_scores.get("pass_rate_percent", "0%"))
        new_overall = _percent_to_float(new_scores.get("pass_rate_percent", "0%"))
        overall_delta = new_overall - baseline_overall

        baseline_skills = baseline_scores.get("per_skill", {}) or {}
        new_skills = new_scores.get("per_skill", {}) or {}
        all_skills = sorted(set(list(baseline_skills.keys()) + list(new_skills.keys())))

        per_skill = {}
        regressions = []
        improvements = []

        for skill in all_skills:
            b = _percent_to_float((baseline_skills.get(skill) or {}).get("pass_rate_percent", "0%"))
            n = _percent_to_float((new_skills.get(skill) or {}).get("pass_rate_percent", "0%"))
            delta = n - b
            per_skill[skill] = {
                "baseline": f"{b:.2f}%",
                "new": f"{n:.2f}%",
                "delta": f"{delta:+.2f}%"
            }
            if delta < -float(regression_threshold):
                regressions.append({"skill": skill, "drop": f"{delta:.2f}%"})
            if delta > float(improvement_threshold):
                improvements.append({"skill": skill, "gain": f"{delta:.2f}%"})

        return {
            "overall": {
                "baseline": f"{baseline_overall:.2f}%",
                "new": f"{new_overall:.2f}%",
                "delta": f"{overall_delta:+.2f}%"
            },
            "per_skill": per_skill,
            "regressions": regressions,
            "improvements": improvements
        }

    # --- Suggestions & Training Aids ---
    def _classify_reason(self, details: str) -> str:
        d = (details or "").lower()
        if "missing required arg" in d:
            return "missing_arg"
        if "tool name mismatch" in d or "mismatch" in d:
            return "tool_mismatch"
        if "args subset" in d:
            return "args_subset"
        if "schema validation failed" in d:
            return "schema_validation"
        if "non-json" in d or "invalid json" in d:
            return "json_format"
        return "other"

    def generate_training_suggestions(self, baseline_report: Dict, new_report: Dict) -> Dict[str, Any]:
        """Analyze diffs between two reports and produce actionable suggestions and JSONL example stubs.

        Returns a dict with keys: summary, top_failures, reason_counts, examples_jsonl
        """
        try:
            bres = { (r.get('test_case') or r.get('skill')): r for r in (baseline_report or {}).get('results', []) }
            nres = { (r.get('test_case') or r.get('skill')): r for r in (new_report or {}).get('results', []) }
            suggestions = { 'summary': {}, 'top_failures': [], 'reason_counts': {}, 'examples_jsonl': '' }

            # Identify cases where new failed but baseline passed (regressions)
            reg_cases = []
            for key, nr in nres.items():
                if not nr.get('passed'):
                    br = bres.get(key)
                    if (br and br.get('passed')) or (not br):
                        reg_cases.append((key, br, nr))

            # Count reasons and collect example stubs
            examples = []
            reason_counts = {}
            for key, br, nr in reg_cases:
                reason = self._classify_reason(nr.get('details') or '')
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
                tc = nr.get('test_case_obj') or br.get('test_case_obj') if br else None
                if isinstance(tc, dict):
                    exp_tool = tc.get('expected_tool')
                    exp_args = tc.get('expected_args') or {}
                    prompt = tc.get('input') or key
                    examples.append({
                        'category': tc.get('category') or 'Unknown',
                        'skill': tc.get('skill') or 'Unknown',
                        'input': prompt,
                        'expected_tool': exp_tool,
                        'expected_args': exp_args,
                        'note': f'suggested due to {reason}'
                    })

            # Build JSONL content (up to 20 examples)
            import json as _json
            lines = []
            for ex in examples[:20]:
                lines.append(_json.dumps(ex, ensure_ascii=False))
            examples_jsonl = "\n".join(lines)

            # Summary
            suggestions['summary'] = {
                'regression_cases': len(reg_cases),
                'unique_reasons': len(reason_counts)
            }
            # Sort failures by reason frequency
            suggestions['reason_counts'] = dict(sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True))
            # Top failures list (test_case, reason)
            suggestions['top_failures'] = [ {'test_case': k, 'reason': self._classify_reason(nr.get('details') or '')} for k, br, nr in reg_cases[:20] ]
            suggestions['examples_jsonl'] = examples_jsonl
            return suggestions
        except Exception as e:
            return {'error': f'suggestion generation failed: {e}'}

    def verify_skill(self, model_name: str, skill_name: str) -> bool:
        """
        Tests a specific skill and returns a Pass/Fail result.

        Args:
            model_name: The name of the model to test.
            skill_name: The name of the skill to verify.

        Returns:
            True if the skill is verified, False otherwise.
        """
        # Scan all tests for matching skill regardless of suite
        test_files: List[Path] = []
        if self.tests_dir.exists():
            for suite in [d for d in self.tests_dir.iterdir() if d.is_dir()]:
                test_files.extend(sorted(suite.glob("*.jsonl")))

        cases = []
        for tf in test_files:
            try:
                with open(tf, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        obj = json.loads(line)
                        if obj.get("skill") == skill_name:
                            cases.append(obj)
            except Exception:
                continue

        if not cases:
            return False

        results = [
            self._execute_test_case(model_name, c, None, None)
            for c in cases
        ]
        passed = sum(1 for r in results if r.get("passed"))
        rate = passed / len(results)
        return rate >= 0.80

    def detect_regression(self, model_name: str, all_test_suites: List[str]) -> List[str]:
        """
        Checks if any skills have degraded compared to a baseline.

        Args:
            model_name: The name of the model to test.
            all_test_suites: A list of all test suites to run for regression checking.

        Returns:
            A list of skills that have shown regression.
        """
        # Minimal implementation: run current tests (All or provided) and compare to baseline if available
        from config import load_baseline_report

        baseline = load_baseline_report(model_name)
        if not baseline:
            return []

        # Run either 'All' or each provided suite and aggregate
        if not all_test_suites:
            current = self.run_benchmark(model_name, "All")
        else:
            combined = {"results": [], "per_skill": {}, "pass_rate_percent": "0%", "passed": 0, "failed": 0, "total_tests": 0}
            for suite in all_test_suites:
                r = self.run_benchmark(model_name, suite)
                if "error" in r:
                    continue
                combined["results"].extend(r.get("results", []))
            # Recompute aggregates
            passed_count = sum(1 for r in combined["results"] if r.get("passed"))
            total = len(combined["results"])
            combined["passed"] = passed_count
            combined["failed"] = total - passed_count
            combined["total_tests"] = total
            combined["pass_rate_percent"] = f"{(passed_count/total*100) if total else 0.0:.2f}%"
            # Per-skill
            per_skill: Dict[str, Dict[str, Any]] = {}
            for r in combined["results"]:
                s = r.get("skill") or "Unknown"
                bucket = per_skill.setdefault(s, {"passed": 0, "total": 0, "pass_rate_percent": "0.00%"})
                bucket["total"] += 1
                if r.get("passed"):
                    bucket["passed"] += 1
            for s, v in per_skill.items():
                rate = (v["passed"] / v["total"] * 100) if v["total"] else 0.0
                v["pass_rate_percent"] = f"{rate:.2f}%"
            combined["per_skill"] = per_skill
            current = combined

        comparison = self.compare_models(baseline, current)
        # Return just the list of regressed skills' names
        return [r["skill"] for r in comparison.get("regressions", [])]

    def auto_trigger_corrective_training(
        self,
        model_name: str,
        test_suites: List[str] = None,
        regression_threshold: float = 5.0
    ) -> Dict[str, Any]:
        """
        Automatically detect regressions and trigger corrective training data generation.

        Args:
            model_name: Model to check for regressions
            test_suites: Suites to run (None = all)
            regression_threshold: Minimum percentage drop to consider a regression

        Returns:
            Dict with regression analysis and paths to generated corrective data
        """
        print(f"Auto-trigger: Checking {model_name} for regressions...")

        # Get regressions
        regressed_skills = self.detect_regression(model_name, test_suites or ["Tools"])

        if not regressed_skills:
            return {
                "status": "no_regression",
                "message": f"No regressions detected for {model_name}",
                "regressed_skills": []
            }

        print(f"Auto-trigger: Found {len(regressed_skills)} regressed skills: {regressed_skills}")

        # Generate corrective training data
        corrective_files = []

        try:
            # 1. Generate from runtime failures
            from tabs.custom_code_tab.runtime_to_training import RuntimeToTrainingConverter
            converter = RuntimeToTrainingConverter()

            runtime_corrective = converter.generate_corrective_training_data(
                model_name=model_name,
                min_failures=3,
                target_tools=regressed_skills
            )

            if runtime_corrective:
                corrective_files.append(runtime_corrective)
                print(f"Auto-trigger: Generated runtime corrective data: {runtime_corrective}")

        except Exception as e:
            print(f"Auto-trigger ERROR: Failed to generate runtime corrective data: {e}")

        try:
            # 2. Generate from chat history successes (to show correct patterns)
            from tabs.custom_code_tab.chat_history_manager import get_history_manager
            history_mgr = get_history_manager()

            chat_training = history_mgr.extract_training_examples(
                model_name=model_name,
                min_tool_calls=1,
                successful_only=True
            )

            if chat_training:
                corrective_files.append(chat_training)
                print(f"Auto-trigger: Generated chat history examples: {chat_training}")

        except Exception as e:
            print(f"Auto-trigger ERROR: Failed to generate chat training data: {e}")

        return {
            "status": "regression_detected",
            "message": f"Detected {len(regressed_skills)} regressed skills",
            "regressed_skills": regressed_skills,
            "corrective_training_files": corrective_files,
            "recommendation": f"Re-train {model_name} using generated corrective data to address regressions."
        }

if __name__ == '__main__':
    # This block demonstrates how to use the EvaluationEngine.
    import json

    print("--- Running EvaluationEngine Demo ---")
    
    # Define the root directory for test suites
    test_suite_dir = Path(__file__).parent.parent / "Training_Data-Sets" / "Test"
    
    # Initialize the engine
    engine = EvaluationEngine(tests_dir=test_suite_dir)
    print(f"EvaluationEngine initialized. Test suites directory: {engine.tests_dir}")
    
    # Define the model and test suite to run
    model_to_test = "Qwen2.5-0.5b-Instruct"
    suite_to_run = "Tools"
    
    # Run the benchmark
    results = engine.run_benchmark(model_to_test, suite_to_run)
    
    # Print the results in a readable format
    print("\n--- Benchmark Results ---")
    print(json.dumps(results, indent=2))
    print("--- End of Demo ---")
