"""
Runtime to Training Data Converter
Converts runtime tool call logs into training data format for fine-tuning
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from config import TRAINING_DATA_DIR, sanitize_identifier


class RuntimeToTrainingConverter:
    """Converts runtime tool call logs to training data format"""

    def __init__(self, runtime_log_dir: Optional[Path] = None, output_dir: Optional[Path] = None):
        """
        Initialize the converter

        Args:
            runtime_log_dir: Directory containing runtime logs (default: Training_Data-Sets/Tools)
            output_dir: Directory to write training data (default: Training_Data-Sets/Training)
        """
        if runtime_log_dir is None:
            self.runtime_log_dir = TRAINING_DATA_DIR / "Tools"
        else:
            self.runtime_log_dir = Path(runtime_log_dir)

        if output_dir is None:
            self.output_dir = TRAINING_DATA_DIR / "Training"
        else:
            self.output_dir = Path(output_dir)

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Input files
        self.training_log = self.runtime_log_dir / "tool_training_data.jsonl"
        self.realtime_log = self.runtime_log_dir / "tool_realtime_data.jsonl"

        # Conversion statistics
        self.stats = {
            'total_conversations': 0,
            'total_tool_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'conversations_with_tools': 0,
            'tools_used': set()
        }

    def convert_all(
        self,
        model_name: Optional[str] = None,
        min_tool_calls: int = 1,
        include_failed: bool = True,
        output_format: str = "openai",
        min_quality: Optional[float] = None
    ) -> str:
        """
        Convert all runtime logs to training data

        Args:
            model_name: Filter by specific model (None for all models)
            min_tool_calls: Minimum tool calls required in a conversation
            include_failed: Whether to include conversations with failed tool calls
            output_format: Output format - "openai" (chat format) or "completion" (instruction format)
            min_quality: Minimum quality score threshold (0.0-1.0). None disables filtering. (Phase 2D)

        Returns:
            Path to the generated training file
        """
        self._reset_stats()

        if not self.training_log.exists():
            raise FileNotFoundError(f"Training log not found: {self.training_log}")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_suffix = f"_{model_name}" if model_name else "_all"
        quality_suffix = f"_q{int(min_quality*100)}" if min_quality else ""
        output_file = self.output_dir / f"training_data{model_suffix}{quality_suffix}_{timestamp}.jsonl"

        training_examples = []

        # Initialize quality scorer if filtering enabled (Phase 2D)
        quality_scorer = None
        quality_stats = {'total': 0, 'filtered': 0, 'passed': 0, 'quality_sum': 0.0}
        if min_quality is not None:
            try:
                from training_generator import get_training_generator
                quality_scorer = get_training_generator()
            except Exception as e:
                print(f"RuntimeToTrainingConverter: Failed to load quality scorer: {e}")
                print(f"RuntimeToTrainingConverter: Proceeding without quality filtering")
                min_quality = None

        try:
            with open(self.training_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by model if specified
                        if model_name and entry.get('model') != model_name:
                            continue

                        # Extract conversation
                        messages = entry.get('messages', [])

                        # Count tool calls
                        tool_call_count = self._count_tool_calls(messages)

                        if tool_call_count < min_tool_calls:
                            continue

                        # Check for failed calls
                        has_failures = self._has_failed_calls(messages)

                        if has_failures and not include_failed:
                            continue

                        # Convert to training format
                        if output_format == "openai":
                            training_example = self._convert_to_openai_format(messages)
                        else:
                            training_example = self._convert_to_completion_format(messages)

                        if training_example:
                            # Phase 2D: Apply quality filtering if enabled
                            if quality_scorer is not None and min_quality is not None:
                                quality_stats['total'] += 1

                                # Get user feedback if available from entry
                                user_feedback = entry.get('user_feedback')

                                # Calculate quality score
                                quality_score = quality_scorer.calculate_quality_score(
                                    training_example,
                                    user_feedback
                                )
                                quality_stats['quality_sum'] += quality_score

                                # Filter by quality threshold
                                if quality_score < min_quality:
                                    quality_stats['filtered'] += 1
                                    continue

                                quality_stats['passed'] += 1

                                # Add quality score to metadata
                                if 'metadata' not in training_example:
                                    training_example['metadata'] = {}
                                training_example['metadata']['quality_score'] = quality_score

                            training_examples.append(training_example)

                            # Update stats
                            self.stats['total_conversations'] += 1
                            self.stats['total_tool_calls'] += tool_call_count
                            if tool_call_count > 0:
                                self.stats['conversations_with_tools'] += 1

                            # Track tools used
                            self._track_tools_used(messages)

                    except json.JSONDecodeError:
                        continue

            # Write training examples to file
            with open(output_file, 'w', encoding='utf-8') as f:
                for example in training_examples:
                    f.write(json.dumps(example) + '\n')

            # Phase 2D: Print quality statistics if filtering was enabled
            if quality_scorer is not None and quality_stats['total'] > 0:
                avg_quality = quality_stats['quality_sum'] / quality_stats['total']
                filter_rate = (quality_stats['filtered'] / quality_stats['total'] * 100)
                print(f"RuntimeToTrainingConverter: Quality filtering stats:")
                print(f"  Total examples: {quality_stats['total']}")
                print(f"  Passed: {quality_stats['passed']} ({100-filter_rate:.1f}%)")
                print(f"  Filtered: {quality_stats['filtered']} ({filter_rate:.1f}%)")
                print(f"  Average quality: {avg_quality:.3f}")

            return str(output_file)

        except Exception as e:
            raise RuntimeError(f"Failed to convert runtime data: {e}")

    # --- Strict JSONL writer for runtime batches (MVP) -----------------
    @staticmethod
    def write_strict_runtime_jsonl(
        *,
        model_tag: str,
        variant_id: str,
        assigned_type: str | None,
        user_input: str,
        tool_calls: list,
        tool_results: list,
        output_dir: Optional[Path] = None,
        include_success: bool = False
    ) -> tuple[str, int]:
        """
        Write strict JSONL entries derived from a single chat turn with tool_calls + tool_results.

        Produces entries where assistant content is a JSON string of a single tool_call:
          {"type":"tool_call","name":"<tool>","args":{...}}

        Returns (path, count).
        """
        import json as _json
        from datetime import datetime as _dt

        if output_dir is None:
            output_dir = TRAINING_DATA_DIR / "Tools"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        entries = []
        count = 0
        assigned_type = assigned_type or "Unknown"
        # Pair tool_calls with results by index
        for tc, res in zip(tool_calls or [], tool_results or []):
            try:
                func = (tc.get('function') or {})
                name = func.get('name')
                args = func.get('arguments')
                # Normalize args to dict
                if isinstance(args, str):
                    try:
                        args = _json.loads(args)
                    except Exception:
                        args = {"_raw": args}
                if not isinstance(args, dict):
                    args = {}

                success = not (isinstance(res, dict) and 'Error:' in (res.get('content') or ''))
                if not include_success and success is True:
                    continue

                tool_obj = {"type": "tool_call", "name": name, "args": args}
                entry = {
                    "messages": [
                        {"role": "user", "content": user_input or ""},
                        {"role": "assistant", "content": _json.dumps(tool_obj, ensure_ascii=False)}
                    ],
                    "scenario": f"auto_from_runtime::{assigned_type}::{name or 'unknown'}",
                    "source": {"model": model_tag, "variant_id": variant_id}
                }
                entries.append(entry)
                count += 1
            except Exception:
                continue

        if not entries:
            return "", 0

        ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        safe_type = str(assigned_type).replace(' ', '_')
        # Sanitize variant_id for filesystem safety (remove /, :, etc.)
        safe_variant_id = sanitize_identifier(variant_id) if variant_id else "unknown"
        out_path = output_dir / f"auto_runtime_{safe_variant_id}_{safe_type}_{ts}.jsonl"
        with open(out_path, 'w', encoding='utf-8') as f:
            for en in entries:
                f.write(_json.dumps(en, ensure_ascii=False) + "\n")

        return str(out_path), count

    def convert_successful_only(
        self,
        model_name: Optional[str] = None,
        output_format: str = "openai",
        min_quality: Optional[float] = None
    ) -> str:
        """
        Convert only conversations with successful tool calls

        Args:
            model_name: Filter by specific model
            output_format: Output format
            min_quality: Minimum quality score threshold (Phase 2D)

        Returns:
            Path to the generated training file
        """
        return self.convert_all(
            model_name=model_name,
            min_tool_calls=1,
            include_failed=False,
            output_format=output_format,
            min_quality=min_quality
        )

    def convert_by_tool(
        self,
        tool_name: str,
        model_name: Optional[str] = None,
        output_format: str = "openai",
        min_quality: Optional[float] = None
    ) -> str:
        """
        Convert conversations that use a specific tool

        Args:
            tool_name: Name of the tool to filter by
            model_name: Filter by specific model
            output_format: Output format
            min_quality: Minimum quality score threshold (Phase 2D)

        Returns:
            Path to the generated training file
        """
        self._reset_stats()

        if not self.training_log.exists():
            raise FileNotFoundError(f"Training log not found: {self.training_log}")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_suffix = f"_{model_name}" if model_name else "_all"
        quality_suffix = f"_q{int(min_quality*100)}" if min_quality else ""
        output_file = self.output_dir / f"training_data_{tool_name}{model_suffix}{quality_suffix}_{timestamp}.jsonl"

        training_examples = []

        # Initialize quality scorer if filtering enabled (Phase 2D)
        quality_scorer = None
        quality_stats = {'total': 0, 'filtered': 0, 'passed': 0, 'quality_sum': 0.0}
        if min_quality is not None:
            try:
                from training_generator import get_training_generator
                quality_scorer = get_training_generator()
            except Exception as e:
                print(f"RuntimeToTrainingConverter: Failed to load quality scorer: {e}")
                print(f"RuntimeToTrainingConverter: Proceeding without quality filtering")
                min_quality = None

        try:
            with open(self.training_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by model if specified
                        if model_name and entry.get('model') != model_name:
                            continue

                        messages = entry.get('messages', [])

                        # Check if conversation uses the target tool
                        if not self._uses_tool(messages, tool_name):
                            continue

                        # Convert to training format
                        if output_format == "openai":
                            training_example = self._convert_to_openai_format(messages)
                        else:
                            training_example = self._convert_to_completion_format(messages)

                        if training_example:
                            # Phase 2D: Apply quality filtering if enabled
                            if quality_scorer is not None and min_quality is not None:
                                quality_stats['total'] += 1
                                user_feedback = entry.get('user_feedback')
                                quality_score = quality_scorer.calculate_quality_score(
                                    training_example,
                                    user_feedback
                                )
                                quality_stats['quality_sum'] += quality_score

                                if quality_score < min_quality:
                                    quality_stats['filtered'] += 1
                                    continue

                                quality_stats['passed'] += 1
                                if 'metadata' not in training_example:
                                    training_example['metadata'] = {}
                                training_example['metadata']['quality_score'] = quality_score

                            training_examples.append(training_example)
                            self.stats['total_conversations'] += 1

                    except json.JSONDecodeError:
                        continue

            # Write training examples to file
            with open(output_file, 'w', encoding='utf-8') as f:
                for example in training_examples:
                    f.write(json.dumps(example) + '\n')

            # Phase 2D: Print quality statistics if filtering was enabled
            if quality_scorer is not None and quality_stats['total'] > 0:
                avg_quality = quality_stats['quality_sum'] / quality_stats['total']
                filter_rate = (quality_stats['filtered'] / quality_stats['total'] * 100)
                print(f"RuntimeToTrainingConverter: Quality filtering stats for {tool_name}:")
                print(f"  Total examples: {quality_stats['total']}")
                print(f"  Passed: {quality_stats['passed']} ({100-filter_rate:.1f}%)")
                print(f"  Filtered: {quality_stats['filtered']} ({filter_rate:.1f}%)")
                print(f"  Average quality: {avg_quality:.3f}")

            return str(output_file)

        except Exception as e:
            raise RuntimeError(f"Failed to convert runtime data: {e}")

    def _convert_to_openai_format(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert messages to OpenAI chat format

        Format:
        {
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "...", "tool_calls": [...]},
                {"role": "tool", "content": "...", "tool_call_id": "..."},
                ...
            ]
        }
        """
        return {"messages": messages}

    def _convert_to_completion_format(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert messages to completion format (instruction-response pairs)

        Format:
        {
            "prompt": "...",
            "completion": "..."
        }
        """
        # Combine all user messages into prompt
        prompt_parts = []
        completion_parts = []

        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            if role == 'system':
                prompt_parts.insert(0, f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                completion_parts.append(content)
                # Include tool calls in completion
                if 'tool_calls' in msg:
                    for tc in msg['tool_calls']:
                        func = tc.get('function', {})
                        completion_parts.append(
                            f"[TOOL_CALL: {func.get('name', '')}({func.get('arguments', {})})]"
                        )
            elif role == 'tool':
                completion_parts.append(f"[TOOL_RESULT: {content}]")

        return {
            "prompt": "\n".join(prompt_parts),
            "completion": "\n".join(completion_parts)
        }

    def _count_tool_calls(self, messages: List[Dict[str, Any]]) -> int:
        """Count tool calls in a conversation"""
        count = 0
        for msg in messages:
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                count += len(msg['tool_calls'])
        return count

    def _has_failed_calls(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if conversation has any failed tool calls"""
        for msg in messages:
            if msg.get('role') == 'tool':
                content = msg.get('content', '')
                if 'Error:' in content or 'error' in content.lower():
                    return True
        return False

    def _uses_tool(self, messages: List[Dict[str, Any]], tool_name: str) -> bool:
        """Check if conversation uses a specific tool"""
        for msg in messages:
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                for tc in msg['tool_calls']:
                    func = tc.get('function', {})
                    if func.get('name') == tool_name:
                        return True
        return False

    def _track_tools_used(self, messages: List[Dict[str, Any]]):
        """Track which tools were used in a conversation"""
        for msg in messages:
            if msg.get('role') == 'assistant' and 'tool_calls' in msg:
                for tc in msg['tool_calls']:
                    func = tc.get('function', {})
                    tool_name = func.get('name', 'unknown')
                    self.stats['tools_used'].add(tool_name)

                    # Track success/failure
                    # Note: Would need to correlate with tool result messages for accurate counting

    def _reset_stats(self):
        """Reset conversion statistics"""
        self.stats = {
            'total_conversations': 0,
            'total_tool_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'conversations_with_tools': 0,
            'tools_used': set()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get conversion statistics"""
        return {
            'total_conversations': self.stats['total_conversations'],
            'total_tool_calls': self.stats['total_tool_calls'],
            'successful_calls': self.stats['successful_calls'],
            'failed_calls': self.stats['failed_calls'],
            'conversations_with_tools': self.stats['conversations_with_tools'],
            'unique_tools': len(self.stats['tools_used']),
            'tools_used': sorted(list(self.stats['tools_used']))
        }

    def get_tool_usage_summary(self, model_name: Optional[str] = None) -> Dict[str, int]:
        """
        Get summary of tool usage from realtime logs

        Args:
            model_name: Filter by specific model

        Returns:
            Dict mapping tool names to call counts
        """
        if not self.realtime_log.exists():
            return {}

        summary = {}

        try:
            with open(self.realtime_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by model if specified
                        if model_name and entry.get('model') != model_name:
                            continue

                        tool = entry.get('tool', 'unknown')
                        summary[tool] = summary.get(tool, 0) + 1

                    except json.JSONDecodeError:
                        continue

            return summary

        except Exception as e:
            print(f"RuntimeToTrainingConverter ERROR: {e}")
            return {}

    def preview_conversation(self, index: int = 0, model_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Preview a conversation from the training log

        Args:
            index: Index of conversation to preview (0-based)
            model_name: Filter by specific model

        Returns:
            Conversation dict or None if not found
        """
        if not self.training_log.exists():
            return None

        try:
            current_index = 0

            with open(self.training_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Filter by model if specified
                        if model_name and entry.get('model') != model_name:
                            continue

                        if current_index == index:
                            return entry

                        current_index += 1

                    except json.JSONDecodeError:
                        continue

            return None

        except Exception as e:
            print(f"RuntimeToTrainingConverter ERROR: {e}")
            return None

    def generate_corrective_training_data(
        self,
        model_name: str,
        min_failures: int = 3,
        target_tools: Optional[List[str]] = None
    ) -> str:
        """
        Generate corrective training data from failed tool calls.
        Creates training examples that show the CORRECT way to use tools that the model is failing at.

        Args:
            model_name: Model to generate corrections for
            min_failures: Minimum number of failures before generating corrective data
            target_tools: Specific tools to generate corrections for (None = all failed tools)

        Returns:
            Path to generated corrective training file
        """
        try:
            # Get tool usage statistics from ToolCallLogger
            from tabs.custom_code_tab.tool_call_logger import ToolCallLogger
            logger = ToolCallLogger()
            stats = logger.get_tool_statistics(model_name)

            # Identify tools with high failure rates
            failed_tools = {}
            for tool_name, tool_stats in stats.items():
                success = tool_stats.get('success', 0)
                failure = tool_stats.get('failure', 0)
                total = success + failure

                if total == 0:
                    continue

                success_rate = (success / total) * 100

                # Tool is failing if success rate < 60% and has enough attempts
                if success_rate < 60 and failure >= min_failures:
                    if target_tools is None or tool_name in target_tools:
                        failed_tools[tool_name] = {
                            'failure_count': failure,
                            'success_rate': success_rate,
                            'errors': tool_stats.get('errors', [])
                        }

            if not failed_tools:
                print(f"RuntimeToTrainingConverter: No tools meet failure criteria for {model_name}")
                return ""

            print(f"RuntimeToTrainingConverter: Generating corrective data for {len(failed_tools)} tools: {list(failed_tools.keys())}")

            # Generate output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"corrective_{model_name}_{timestamp}.jsonl"

            corrective_examples = []

            # For each failed tool, create corrective training examples
            for tool_name, tool_data in failed_tools.items():
                # Generate examples showing CORRECT usage
                examples = self._generate_correct_examples_for_tool(tool_name, tool_data['errors'])
                corrective_examples.extend(examples)

            # Write corrective examples
            with open(output_file, 'w', encoding='utf-8') as f:
                for example in corrective_examples:
                    f.write(json.dumps(example) + '\n')

            print(f"RuntimeToTrainingConverter: Generated {len(corrective_examples)} corrective examples")
            print(f"RuntimeToTrainingConverter: Saved to {output_file}")

            return str(output_file)

        except Exception as e:
            print(f"RuntimeToTrainingConverter ERROR: Failed to generate corrective data: {e}")
            return ""

    def _generate_correct_examples_for_tool(
        self,
        tool_name: str,
        error_samples: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate corrective training examples for a specific tool.
        Uses error patterns to create examples showing the CORRECT way.
        """
        examples = []

        # Tool-specific corrective examples based on common failures
        if tool_name == 'file_read':
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful coding assistant with access to file operations."},
                    {"role": "user", "content": "Read the contents of config.py"},
                    {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "file_read",
                            "arguments": json.dumps({"path": "config.py"})
                        }
                    }]},
                    {"role": "tool", "tool_call_id": "call_1", "content": "# Config file contents...\nDEBUG = True\n"},
                    {"role": "assistant", "content": "Here are the contents of config.py. The DEBUG flag is set to True."}
                ]
            })

        elif tool_name == 'file_write':
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful coding assistant with access to file operations."},
                    {"role": "user", "content": "Create a new file called test.txt with the content 'Hello World'"},
                    {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "file_write",
                            "arguments": json.dumps({"path": "test.txt", "content": "Hello World"})
                        }
                    }]},
                    {"role": "tool", "tool_call_id": "call_1", "content": "File written successfully: test.txt"},
                    {"role": "assistant", "content": "I've created test.txt with the content 'Hello World'."}
                ]
            })

        elif tool_name == 'grep_search':
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful coding assistant with access to search operations."},
                    {"role": "user", "content": "Find all occurrences of 'def main' in the codebase"},
                    {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "grep_search",
                            "arguments": json.dumps({"pattern": "def main", "path": "."})
                        }
                    }]},
                    {"role": "tool", "tool_call_id": "call_1", "content": "app.py:15:def main():\nserver.py:42:def main():"},
                    {"role": "assistant", "content": "I found 'def main' in two files: app.py (line 15) and server.py (line 42)."}
                ]
            })

        elif tool_name == 'bash':
            examples.append({
                "messages": [
                    {"role": "system", "content": "You are a helpful coding assistant with access to shell commands."},
                    {"role": "user", "content": "List all Python files in the current directory"},
                    {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "bash",
                            "arguments": json.dumps({"command": "ls *.py"})
                        }
                    }]},
                    {"role": "tool", "tool_call_id": "call_1", "content": "main.py\nconfig.py\nutils.py"},
                    {"role": "assistant", "content": "Here are the Python files: main.py, config.py, and utils.py."}
                ]
            })

        # Add more examples based on error patterns
        # TODO: Could analyze error_samples to generate more specific corrections

        return examples


# Convenience function
def convert_runtime_to_training(
    model_name: Optional[str] = None,
    output_format: str = "openai",
    successful_only: bool = False,
    min_quality: Optional[float] = None
) -> str:
    """
    Convenience function to convert runtime data to training format

    Args:
        model_name: Filter by specific model
        output_format: "openai" or "completion"
        successful_only: Only include successful tool calls
        min_quality: Minimum quality score threshold (Phase 2D)

    Returns:
        Path to generated training file
    """
    converter = RuntimeToTrainingConverter()

    if successful_only:
        return converter.convert_successful_only(model_name, output_format, min_quality)
    else:
        return converter.convert_all(model_name, output_format=output_format, min_quality=min_quality)
