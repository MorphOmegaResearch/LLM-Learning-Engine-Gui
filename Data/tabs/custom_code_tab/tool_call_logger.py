"""
Tool Call Logger - Simple logging module for tool call training data
No external dependencies beyond standard library
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


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
            self.log_dir = Path(__file__).parent.parent.parent / "Training_Data-Sets" / "Tools"
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

    def log_training_example(self, messages: List[Dict[str, Any]], model_name: str = "unknown"):
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

            with open(self.training_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(training_example) + '\n')

            return True
        except Exception as e:
            self._log_error("training_example", str(e), {"model": model_name})
            return False

    def log_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        result: str,
        success: bool,
        model_name: str = "unknown",
        execution_time: Optional[float] = None
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
            with open(self.realtime_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

            # If failed, also log to error file
            if not success:
                self._log_error(tool_name, result, {
                    "model": model_name,
                    "arguments": tool_args,
                    "execution_time": execution_time
                })

            return True
        except Exception as e:
            self._log_error("log_tool_call", str(e), {
                "tool": tool_name,
                "model": model_name
            })
            return False

    def log_batch_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, Any]],
        model_name: str = "unknown"
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
            is_success = "Error:" not in result_content

            if not self.log_tool_call(
                tool_name=tool_name,
                tool_args=tool_args,
                result=result_content,
                success=is_success,
                model_name=model_name
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

    def _log_error(self, context: str, error_msg: str, metadata: Dict[str, Any]):
        """Internal method to log errors"""
        try:
            error_entry = {
                "timestamp": datetime.now().isoformat(),
                "context": context,
                "error": error_msg,
                "metadata": metadata
            }

            with open(self.error_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(error_entry) + '\n')
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
