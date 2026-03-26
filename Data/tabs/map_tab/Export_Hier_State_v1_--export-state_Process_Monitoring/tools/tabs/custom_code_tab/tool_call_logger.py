# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Tool Call Logger - Simple logging module for tool call training data
No external dependencies beyond standard library
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

from config import TRAINING_DATA_DIR


class ToolCallLogger:
    """Logs tool calls and results for training data collection"""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize the tool call logger

        Args:
            log_dir: Directory to store log files. If None, uses default Training_Data-Sets/Tools
        """
        if log_dir is None:
            # Default to Training_Data-Sets/Tools directory
            self.log_dir = TRAINING_DATA_DIR / "Tools"
        else:
            self.log_dir = Path(log_dir)

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.training_log = self.log_dir / "tool_training_data.jsonl"
        self.realtime_log = self.log_dir / "tool_realtime_data.jsonl"
        self.error_log = self.log_dir / "tool_errors.jsonl"

        # Statistics tracking
        self.session_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'tools_used': set()
        }

    # ------------------------------------------------------------------
    # Internal helpers

    @staticmethod
    def _sanitize_project_name(project: Optional[str]) -> Optional[str]:
        """Return a filesystem-safe project identifier or None."""
        if not project:
            return None
        safe = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in project).strip('_')
        return safe or None

    def _project_log_path(self, filename: str, project: Optional[str]) -> Optional[Path]:
        safe = self._sanitize_project_name(project)
        if not safe:
            return None
        project_dir = self.log_dir / "Projects" / safe
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir / filename

    @staticmethod
    def _write_jsonl(path: Path, payload: Dict[str, Any]):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload) + '\n')

    def log_training_example(
        self,
        messages: List[Dict[str, Any]],
        model_name: str = "unknown",
        project: Optional[str] = None,
    ):
        """
        Log a complete training example (full conversation history)

        Args:
            messages: List of message dicts with role/content
            model_name: Name of the model being used
        """
        try:
            training_example = {
                "timestamp": datetime.now().isoformat(),
                "model": model_name,
                "messages": messages
            }

            self._write_jsonl(self.training_log, training_example)

            project_log = self._project_log_path("tool_training_data.jsonl", project)
            if project_log:
                self._write_jsonl(project_log, training_example)

            return True
        except Exception as e:
            self._log_error("training_example", str(e), {"model": model_name}, project=project)
            return False

    def log_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: str,
        success: bool,
        model_name: str = "unknown",
        execution_time: Optional[float] = None,
        project: Optional[str] = None,
    ):
        """
        Log a single tool call with its result

        Args:
            tool_name: Name of the tool called
            tool_args: Arguments passed to the tool
            result: Result/output from the tool
            success: Whether the tool call was successful
            model_name: Name of the model making the call
            execution_time: Time taken to execute the tool (seconds)
        """
        try:
            # Update session stats
            self.session_stats['total_calls'] += 1
            if success:
                self.session_stats['successful_calls'] += 1
            else:
                self.session_stats['failed_calls'] += 1
            self.session_stats['tools_used'].add(tool_name)

            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "model": model_name,
                "tool": tool_name,
                "arguments": tool_args,
                "result": result[:1000] if len(result) > 1000 else result,  # Limit result size
                "success": success,
                "execution_time": execution_time
            }

            # Log to realtime file
            self._write_jsonl(self.realtime_log, log_entry)

            project_realtime = self._project_log_path("tool_realtime_data.jsonl", project)
            if project_realtime:
                self._write_jsonl(project_realtime, log_entry)

            # If failed, also log to error file
            if not success:
                self._log_error(tool_name, result, {
                    "model": model_name,
                    "arguments": tool_args,
                    "execution_time": execution_time
                }, project=project)

            return True
        except Exception as e:
            self._log_error("log_tool_call", str(e), {
                "tool": tool_name,
                "model": model_name
            }, project=project)
            return False

    def log_batch_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        model_name: str = "unknown",
        project: Optional[str] = None,
    ):
        """
        Log multiple tool calls at once (batch logging)

        Args:
            tool_calls: List of tool call dicts with function/arguments
            tool_results: List of result dicts with content
            model_name: Name of the model making the calls
        """
        if len(tool_calls) != len(tool_results):
            self._log_error(
                "log_batch_tool_calls",
                "Mismatch between tool_calls and tool_results length",
                {"calls": len(tool_calls), "results": len(tool_results)}
            )
            return False

        success = True
        for tool_call, result in zip(tool_calls, tool_results):
            tool_name = tool_call.get("function", {}).get("name", "unknown")
            tool_args = tool_call.get("function", {}).get("arguments", {})
            result_content = result.get("content", "")

            # FIXED: Use structured success detection instead of string matching
            # Try to parse result as JSON first (most tool results are JSON)
            is_success = True  # Default to success
            try:
                import json
                if isinstance(result_content, str) and result_content.strip().startswith('{'):
                    parsed = json.loads(result_content)
                    # Check for error field in JSON
                    if isinstance(parsed, dict) and 'error' in parsed:
                        is_success = False
                    elif isinstance(parsed, dict) and 'success' in parsed:
                        is_success = bool(parsed['success'])
                    # Fallback: string check only if JSON parsing succeeded but no clear indicator
                    elif "Error:" in result_content or "error" in result_content.lower():
                        is_success = False
                else:
                    # Non-JSON result: use string check
                    is_success = "Error:" not in result_content and "error" not in result_content.lower()
            except (json.JSONDecodeError, Exception):
                # JSON parse failed: fallback to string check
                is_success = "Error:" not in result_content

            if not self.log_tool_call(
                tool_name=tool_name,
                tool_args=tool_args,
                result=result_content,
                success=is_success,
                model_name=model_name,
                project=project
            ):
                success = False

        return success

    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for the current session"""
        return {
            'total_calls': self.session_stats['total_calls'],
            'successful_calls': self.session_stats['successful_calls'],
            'failed_calls': self.session_stats['failed_calls'],
            'success_rate': (
                self.session_stats['successful_calls'] / self.session_stats['total_calls'] * 100
                if self.session_stats['total_calls'] > 0 else 0
            ),
            'tools_used': list(self.session_stats['tools_used']),
            'unique_tools': len(self.session_stats['tools_used'])
        }

    def reset_session_stats(self):
        """Reset session statistics"""
        self.session_stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'tools_used': set()
        }

    def log_tool_feedback(self, feedback_data: Dict[str, Any], project: Optional[str] = None):
        """
        Log user feedback for tool execution (Phase 2A - Training Progression)

        Args:
            feedback_data: Complete feedback data including tool execution and user rating
            project: Optional project name for scoped logging

        Feedback data structure:
            {
                'execution_id': str,
                'tool_name': str,
                'arguments': dict,
                'result': dict,
                'variant_id': str,
                'timestamp': str (ISO),
                'user_feedback': {
                    'rating': str (good/partial/bad),
                    'quality_score': float (0.0-1.0),
                    'notes': str,
                    'feedback_time': str (ISO)
                },
                'detected_success': bool,
                'feedback_match': bool
            }
        """
        try:
            # Create feedback log path
            feedback_log = self.log_dir / "tool_feedback.jsonl"

            # Write to main feedback log
            self._write_jsonl(feedback_log, feedback_data)

            # Write to project-specific log if project provided
            project_feedback = self._project_log_path("tool_feedback.jsonl", project)
            if project_feedback:
                self._write_jsonl(project_feedback, feedback_data)

            # Also append to training data with feedback metadata
            training_entry = {
                "timestamp": feedback_data['timestamp'],
                "model": feedback_data['variant_id'],
                "tool": feedback_data['tool_name'],
                "arguments": feedback_data['arguments'],
                "result": feedback_data['result'],
                "success": feedback_data['detected_success'],
                "user_feedback": feedback_data['user_feedback'],
                "feedback_match": feedback_data['feedback_match'],
                "quality_score": feedback_data['user_feedback']['quality_score']
            }

            self._write_jsonl(self.training_log, training_entry)

            # Generate corrective example if feedback indicates failure (Phase 2D)
            if feedback_data['user_feedback']['rating'] == 'bad':
                try:
                    from training_generator import get_training_generator
                    generator = get_training_generator()

                    failed_call = {
                        'name': feedback_data['tool_name'],
                        'args': feedback_data['arguments']
                    }
                    error_msg = feedback_data['result'].get('error', 'Tool execution failed')

                    corrective_example = generator.generate_corrective_example(failed_call, error_msg)

                    if corrective_example:
                        # Calculate quality and write if high enough
                        quality = generator.calculate_quality_score(corrective_example, feedback_data['user_feedback'])

                        if quality >= 0.6:  # Minimum quality threshold
                            corrective_log = self.log_dir / "tool_corrective_examples.jsonl"
                            corrective_example['metadata']['quality_score'] = quality
                            self._write_jsonl(corrective_log, corrective_example)
                except Exception as e:
                    # Non-fatal - log but continue
                    self._log_error("generate_corrective", str(e), {"tool": feedback_data['tool_name']})

            return True
        except Exception as e:
            self._log_error("log_tool_feedback", str(e), {
                "execution_id": feedback_data.get('execution_id'),
                "tool_name": feedback_data.get('tool_name')
            }, project=project)
            return False

    def get_tool_statistics(self, model_name: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        Get statistics per tool from the realtime log

        Args:
            model_name: Filter by model name (optional)

        Returns:
            Dict mapping tool names to {success: count, failure: count}
        """
        stats = {}

        if not self.realtime_log.exists():
            return stats

        try:
            with open(self.realtime_log, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue

                    entry = json.loads(line)

                    # Filter by model if specified
                    if model_name and entry.get('model') != model_name:
                        continue

                    tool = entry.get('tool', 'unknown')
                    success = entry.get('success', False)

                    if tool not in stats:
                        stats[tool] = {'success': 0, 'failure': 0, 'errors': []}

                    if success:
                        stats[tool]['success'] += 1
                    else:
                        stats[tool]['failure'] += 1
                        # Store error message (limit to 5 most recent)
                        if len(stats[tool]['errors']) < 5:
                            stats[tool]['errors'].append(entry.get('result', 'Unknown error'))

        except Exception as e:
            self._log_error("get_tool_statistics", str(e), {"model": model_name})

        return stats

    def clear_logs(self, log_type: str = "all"):
        """
        Clear log files

        Args:
            log_type: Which logs to clear - "training", "realtime", "errors", or "all"
        """
        try:
            if log_type in ["training", "all"]:
                if self.training_log.exists():
                    self.training_log.unlink()

            if log_type in ["realtime", "all"]:
                if self.realtime_log.exists():
                    self.realtime_log.unlink()

            if log_type in ["errors", "all"]:
                if self.error_log.exists():
                    self.error_log.unlink()

            self.reset_session_stats()
            return True
        except Exception as e:
            self._log_error("clear_logs", str(e), {"log_type": log_type})
            return False

    def _log_error(self, context: str, error_msg: str, metadata: Dict[str, Any], project: Optional[str] = None):
        """Internal method to log errors"""
        try:
            error_entry = {
                "timestamp": datetime.now().isoformat(),
                "context": context,
                "error": error_msg,
                "metadata": metadata
            }

            self._write_jsonl(self.error_log, error_entry)

            project_error = self._project_log_path("tool_errors.jsonl", project)
            if project_error:
                self._write_jsonl(project_error, error_entry)
        except Exception:
            # If we can't log the error, silently fail to avoid recursion
            pass


# Convenience singleton instance
_global_logger = None

def get_logger(log_dir: Optional[Path] = None) -> ToolCallLogger:
    """Get the global logger instance (singleton pattern)"""
    global _global_logger
    if _global_logger is None:
        _global_logger = ToolCallLogger(log_dir)
    return _global_logger
