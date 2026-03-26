"""
Tool Call Detector - Detects tool calls from model responses
Reuses working parsers from chat_interface_tab.py
"""

import json
import re
from typing import List, Dict, Any, Optional


class ToolCallDetector:
    """Detects and parses tool calls from various model response formats"""

    def __init__(self):
        """Initialize the tool call detector"""
        self.json_fixer_available = False
        self.format_translator_available = False

        # Try to import JSON fixer if available
        try:
            from opencode.json_fixer import smart_json_parse
            self.smart_json_parse = smart_json_parse
            self.json_fixer_available = True
        except ImportError:
            pass

        # Try to import format translator if available
        try:
            from opencode.format_translator import FormatTranslator
            self.format_translator = FormatTranslator()
            self.format_translator_available = True
        except ImportError:
            pass

    def detect_from_ollama_response(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect tool calls from Ollama API response

        Args:
            response_data: Full Ollama API response dict

        Returns:
            List of tool call dicts with {"function": {"name": str, "arguments": dict}}
        """
        # Standard Ollama tool_calls format
        message_data = response_data.get("message", {})
        tool_calls = message_data.get("tool_calls", [])

        if tool_calls:
            return self._normalize_tool_calls(tool_calls)

        # If no standard tool_calls, try format translator on content
        if self.format_translator_available:
            content = message_data.get("content", "")
            if content:
                translated = self.format_translator.translate(content)
                if translated:
                    # Convert to Ollama format
                    return [{
                        "function": {
                            "name": translated.get("name", ""),
                            "arguments": translated.get("args", {})
                        }
                    }]

        return []

    def detect_from_message(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect tool calls from a message dict

        Args:
            message: Message dict with role and content

        Returns:
            List of tool call dicts
        """
        # Check for direct tool_calls field
        if "tool_calls" in message:
            return self._normalize_tool_calls(message["tool_calls"])

        # Check content for tool call patterns
        content = message.get("content", "")
        if content:
            detected = self._detect_from_text(content)
            if detected:
                return detected

        return []

    def detect_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect tool calls from plain text content

        Args:
            text: Text content to search for tool calls

        Returns:
            List of tool call dicts
        """
        return self._detect_from_text(text)

    def _detect_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Internal method to detect tool calls from text"""
        tool_calls = []

        # Try format translator first if available
        if self.format_translator_available:
            try:
                translated = self.format_translator.translate(text)
                if translated:
                    tool_calls.append({
                        "function": {
                            "name": translated.get("name", ""),
                            "arguments": translated.get("args", {})
                        }
                    })
                    return tool_calls
            except Exception:
                pass

        # Fallback: Try to detect common patterns
        # Pattern 1: JSON-like function calls
        # Example: {"name": "file_read", "arguments": {"path": "/home/file.txt"}}
        json_pattern = r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}'
        json_matches = re.finditer(json_pattern, text, re.DOTALL)

        for match in json_matches:
            try:
                parsed = self._safe_json_parse(match.group(0))
                if "name" in parsed and "arguments" in parsed:
                    tool_calls.append({
                        "function": {
                            "name": parsed["name"],
                            "arguments": parsed["arguments"]
                        }
                    })
            except Exception:
                continue

        # Pattern 2: Function call style
        # Example: file_read(path="/home/file.txt")
        func_pattern = r'(\w+)\s*\(([^)]+)\)'
        func_matches = re.finditer(func_pattern, text)

        for match in func_matches:
            tool_name = match.group(1)
            args_str = match.group(2)

            # Skip common non-tool patterns
            if tool_name in ['print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set']:
                continue

            # Parse arguments
            try:
                arguments = self._parse_function_args(args_str)
                tool_calls.append({
                    "function": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                })
            except Exception:
                continue

        return tool_calls

    def _normalize_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize tool calls to standard format"""
        normalized = []

        for tool_call in tool_calls:
            # Get function data
            if "function" in tool_call:
                function_data = tool_call["function"]
            else:
                # Assume it's already in the right format
                function_data = tool_call

            tool_name = function_data.get("name", "")
            arguments = function_data.get("arguments", {})

            # Parse arguments if they're a string
            if isinstance(arguments, str):
                arguments = self._safe_json_parse(arguments)

            normalized.append({
                "function": {
                    "name": tool_name,
                    "arguments": arguments if isinstance(arguments, dict) else {}
                }
            })

        return normalized

    def _safe_json_parse(self, json_str: str) -> Dict[str, Any]:
        """Safely parse JSON with optional JSON fixer"""
        # Try with JSON fixer if available
        if self.json_fixer_available:
            try:
                return self.smart_json_parse(json_str)
            except Exception:
                pass

        # Fallback to standard JSON
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {}

    def _parse_function_args(self, args_str: str) -> Dict[str, Any]:
        """Parse function-style arguments to dict"""
        arguments = {}

        # Split by commas (simple parser, doesn't handle nested commas)
        parts = [p.strip() for p in args_str.split(',')]

        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

                # Try to parse as JSON for complex types
                try:
                    value = json.loads(value)
                except Exception:
                    pass

                arguments[key] = value

        return arguments

    def extract_tool_results(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract tool result messages from conversation history

        Args:
            messages: List of message dicts

        Returns:
            List of tool result dicts with tool info and result
        """
        results = []

        for i, msg in enumerate(messages):
            if msg.get("role") == "tool":
                # Look back for the corresponding tool call
                tool_name = "unknown"
                tool_args = {}

                # Search backwards for assistant message with tool_calls
                for j in range(i-1, -1, -1):
                    prev_msg = messages[j]
                    if prev_msg.get("role") == "assistant":
                        tool_calls = prev_msg.get("tool_calls", [])
                        if tool_calls and len(tool_calls) > len(results):
                            # Assume this is the corresponding tool call
                            tc_index = len(results)
                            if tc_index < len(tool_calls):
                                tool_call = tool_calls[tc_index]
                                func_data = tool_call.get("function", {})
                                tool_name = func_data.get("name", "unknown")
                                tool_args = func_data.get("arguments", {})
                        break

                results.append({
                    "tool_name": tool_name,
                    "arguments": tool_args,
                    "result": msg.get("content", ""),
                    "success": "Error:" not in msg.get("content", "")
                })

        return results

    def count_tool_calls(self, messages: List[Dict[str, Any]]) -> int:
        """Count total tool calls in conversation history"""
        count = 0
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                count += len(msg["tool_calls"])
        return count

    def get_tool_usage_summary(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get summary of tool usage from conversation

        Returns:
            Dict mapping tool names to call counts
        """
        summary = {}

        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tool_call in msg["tool_calls"]:
                    func_data = tool_call.get("function", {})
                    tool_name = func_data.get("name", "unknown")
                    summary[tool_name] = summary.get(tool_name, 0) + 1

        return summary


# Convenience function
def detect_tool_calls(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convenience function to detect tool calls from Ollama response

    Args:
        response_data: Ollama API response dict

    Returns:
        List of normalized tool call dicts
    """
    detector = ToolCallDetector()
    return detector.detect_from_ollama_response(response_data)
