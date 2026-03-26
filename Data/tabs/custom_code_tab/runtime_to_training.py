"""
Runtime to Training Data Converter
Converts runtime tool call logs into training data format for fine-tuning
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


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
            self.runtime_log_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Tools"
        else:
            self.runtime_log_dir = Path(runtime_log_dir)

        if output_dir is None:
            self.output_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Training"
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
        output_format: str = "openai"
    ) -> str:
        """
        Convert all runtime logs to training data

        Args:
            model_name: Filter by specific model (None for all models)
            min_tool_calls: Minimum tool calls required in a conversation
            include_failed: Whether to include conversations with failed tool calls
            output_format: Output format - "openai" (chat format) or "completion" (instruction format)

        Returns:
            Path to the generated training file
        """
        self._reset_stats()

        if not self.training_log.exists():
            raise FileNotFoundError(f"Training log not found: {self.training_log}")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_suffix = f"_{model_name}" if model_name else "_all"
        output_file = self.output_dir / f"training_data{model_suffix}_{timestamp}.jsonl"

        training_examples = []

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

            return str(output_file)

        except Exception as e:
            raise RuntimeError(f"Failed to convert runtime data: {e}")

    def convert_successful_only(
        self,
        model_name: Optional[str] = None,
        output_format: str = "openai"
    ) -> str:
        """
        Convert only conversations with successful tool calls

        Args:
            model_name: Filter by specific model
            output_format: Output format

        Returns:
            Path to the generated training file
        """
        return self.convert_all(
            model_name=model_name,
            min_tool_calls=1,
            include_failed=False,
            output_format=output_format
        )

    def convert_by_tool(
        self,
        tool_name: str,
        model_name: Optional[str] = None,
        output_format: str = "openai"
    ) -> str:
        """
        Convert conversations that use a specific tool

        Args:
            tool_name: Name of the tool to filter by
            model_name: Filter by specific model
            output_format: Output format

        Returns:
            Path to the generated training file
        """
        self._reset_stats()

        if not self.training_log.exists():
            raise FileNotFoundError(f"Training log not found: {self.training_log}")

        # Generate output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_suffix = f"_{model_name}" if model_name else "_all"
        output_file = self.output_dir / f"training_data_{tool_name}{model_suffix}_{timestamp}.jsonl"

        training_examples = []

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
                            training_examples.append(training_example)
                            self.stats['total_conversations'] += 1

                    except json.JSONDecodeError:
                        continue

            # Write training examples to file
            with open(output_file, 'w', encoding='utf-8') as f:
                for example in training_examples:
                    f.write(json.dumps(example) + '\n')

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

    def convert_morph_interactions(
        self,
        variant_name: Optional[str] = None,
        domain: Optional[str] = None,
        accepted_only: bool = True,
    ) -> Optional[Path]:
        """Convert accepted morph interactions to OpenAI training format.

        Reads morph_evals/accepted_*.jsonl (written by lineage_tracker.record_morph_interaction).
        Optionally filters by variant_name (via variant_sha_index.json) and/or domain.
        Writes output to Training_Data-Sets/Training/morph_training_{variant}_{date}.jsonl.

        Args:
            variant_name: Pymanifest variant name (e.g. 'omega_v40', 'specialist_debug').
                          Resolved to SHA via Data/pymanifest/variants/variant_sha_index.json.
            domain:       Filter to interactions with this domain tag (e.g. 'debug').
            accepted_only: If True, only read accepted_*.jsonl; if False also read rejected.

        Returns:
            Path to written training file, or None if no interactions found.
        """
        lineage_dir = self.runtime_log_dir.parent / "Lineage"
        morph_eval_dir = lineage_dir / "morph_evals"
        if not morph_eval_dir.exists():
            return None

        # Resolve variant_name → sha via variant_sha_index
        sha_filter: Optional[str] = None
        if variant_name:
            idx_path = (Path(__file__).parent.parent.parent
                        / "pymanifest" / "variants" / "variant_sha_index.json")
            if idx_path.exists():
                try:
                    idx = json.loads(idx_path.read_text())
                    # index is {sha: name}; reverse lookup
                    sha_filter = next((s for s, n in idx.items() if n == variant_name), None)
                except Exception:
                    pass

        # Collect eval files
        glob_patterns = ["accepted_*.jsonl"] if accepted_only else ["accepted_*.jsonl",
                                                                      "rejected_*.jsonl"]
        records: List[Dict[str, Any]] = []
        for pattern in glob_patterns:
            for fpath in sorted(morph_eval_dir.glob(pattern)):
                try:
                    for line in fpath.read_text().splitlines():
                        if not line.strip():
                            continue
                        rec = json.loads(line)
                        if sha_filter and rec.get('variant_sha', '') != sha_filter:
                            continue
                        if domain and rec.get('domain', rec.get('control_signal', '')) != domain:
                            continue
                        records.append(rec)
                except Exception:
                    pass

        if not records:
            return None

        # Convert to OpenAI messages format
        training_examples: List[Dict[str, Any]] = []
        for rec in records:
            prompt    = rec.get('prompt', '')
            response  = rec.get('response', '')
            if not prompt or not response:
                continue
            training_examples.append({
                "messages": [
                    {"role": "user",      "content": str(prompt)},
                    {"role": "assistant", "content": str(response)},
                ]
            })

        if not training_examples:
            return None

        # Write output
        self.output_dir.mkdir(parents=True, exist_ok=True)
        tag  = variant_name or domain or "all"
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / f"morph_training_{tag}_{date}.jsonl"
        with open(out_path, 'w') as f:
            for ex in training_examples:
                f.write(json.dumps(ex) + '\n')

        return out_path


# Convenience function
def convert_runtime_to_training(
    model_name: Optional[str] = None,
    output_format: str = "openai",
    successful_only: bool = False
) -> str:
    """
    Convenience function to convert runtime data to training format

    Args:
        model_name: Filter by specific model
        output_format: "openai" or "completion"
        successful_only: Only include successful tool calls

    Returns:
        Path to generated training file
    """
    converter = RuntimeToTrainingConverter()

    if successful_only:
        return converter.convert_successful_only(model_name, output_format)
    else:
        return converter.convert_all(model_name, output_format=output_format)
