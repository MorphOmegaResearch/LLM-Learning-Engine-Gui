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

        # Tool-to-skill mapping for rating system integration
        self.tool_skill_map = self._build_tool_skill_map()
        self.type_catalog = self._load_type_catalog()

    def _load_type_catalog(self) -> Dict:
        """Load type catalog for tool proficiency requirements"""
        try:
            from pathlib import Path
            catalog_path = Path(__file__).parent.parent.parent / "type_catalog_v2.json"
            if catalog_path.exists():
                with open(catalog_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _build_tool_skill_map(self) -> Dict[str, List[str]]:
        """
        Map tools to the skills they demonstrate

        Returns:
            Dict[tool_name, List[skill_names]]
        """
        return {
            # File operations
            "file_read": ["syntax", "code_analysis", "debugging"],
            "file_write": ["syntax", "code_generation"],
            "file_edit": ["syntax", "refactoring", "code_generation"],

            # Search operations
            "glob": ["code_analysis", "architecture"],
            "file_search": ["code_analysis", "architecture"],
            "grep": ["debugging", "code_analysis", "search"],
            "grep_search": ["debugging", "code_analysis", "search"],

            # Execution operations
            "bash_execute": ["system_integration", "debugging", "automation"],
            "run_bash_command": ["system_integration", "debugging", "automation"],

            # Web operations
            "web_fetch": ["research", "information_gathering", "synthesis"],

            # Testing operations
            "run_tests": ["tests", "verification", "quality_assessment"],
            "test_execution": ["tests", "verification"],

            # Git operations
            "git_operations": ["version_control", "architecture"],

            # Agent operations
            "agent_request": ["task_decomposition", "agent_selection", "orchestration"],
            "agents_status": ["workflow_optimization", "orchestration"],
            "agents_route_task": ["agent_selection", "routing_logic", "orchestration"],

            # Browser operations
            "browser_click": ["navigation", "interaction", "gui_control"],
            "browser_type": ["interaction", "form_handling", "gui_control"],
            "browser_screenshot": ["element_detection", "verification"],
            "element_detect": ["element_detection", "test_validation"],

            # Image/Audio operations
            "image_read": ["image_understanding", "ocr"],
            "audio_read": ["transcription", "audio_comprehension"],

            # Documentation
            "documentation_generate": ["documentation", "communication"],

            # Planning
            "plan_task": ["task_breakdown", "feasibility_analysis", "planning"],

            # Training/Meta
            "data_generation": ["data_generation", "curriculum_planning"],
            "eval_design": ["eval_design", "quality_assessment"],
        }

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

    def map_tool_to_skills(self, tool_name: str, assigned_type: Optional[str] = None,
                          class_level: Optional[str] = None) -> List[str]:
        """
        Map tool usage to relevant skills

        Args:
            tool_name: e.g., "file_read", "grep", "bash_execute"
            assigned_type: Model type (e.g., "coder", "researcher") - optional
            class_level: Class level (e.g., "novice", "skilled") - optional

        Returns:
            List of applicable skill names
        """
        # Get base skills from tool map
        base_skills = self.tool_skill_map.get(tool_name, [])

        if not assigned_type or not class_level:
            return base_skills

        # Get type-specific skills from type catalog
        type_skills = self._get_type_specific_skills(assigned_type, class_level)

        # Intersect base skills with what's required for this type/class
        # This ensures we only suggest skills that are relevant AND required
        relevant_skills = [s for s in base_skills if s in type_skills]

        # If no intersection, return base skills
        return relevant_skills if relevant_skills else base_skills

    def _get_type_specific_skills(self, assigned_type: str, class_level: str) -> List[str]:
        """Get required skills for a specific type and class level"""
        if not self.type_catalog:
            return []

        # Find type definition
        type_def = None
        for t in self.type_catalog.get('types', []):
            if t.get('id') == assigned_type:
                type_def = t
                break

        if not type_def:
            return []

        # Get class definition
        classes = type_def.get('classes', {})
        class_info = classes.get(class_level, {})

        # Get required skills
        required_skills = class_info.get('required_skills', [])

        # Also include skills from the full skills_tree
        skills_tree = type_def.get('skills_tree', [])

        return list(set(required_skills + skills_tree))

    def get_tool_info(self, tool_name: str) -> Optional[Dict]:
        """
        Get information about a tool

        Returns:
            {
                "name": str,
                "skills": List[str],
                "category": str
            }
        """
        if tool_name not in self.tool_skill_map:
            return None

        # Categorize tool
        category = self._categorize_tool(tool_name)

        return {
            "name": tool_name,
            "skills": self.tool_skill_map[tool_name],
            "category": category
        }

    def _categorize_tool(self, tool_name: str) -> str:
        """Categorize tool into high-level category"""
        if tool_name in ["file_read", "file_write", "file_edit"]:
            return "file_operations"
        elif tool_name in ["glob", "grep", "file_search", "grep_search"]:
            return "search_operations"
        elif tool_name in ["bash_execute", "run_bash_command"]:
            return "execution"
        elif tool_name in ["web_fetch"]:
            return "web_operations"
        elif tool_name in ["agent_request", "agents_status", "agents_route_task"]:
            return "orchestration"
        elif tool_name.startswith("browser_"):
            return "browser_automation"
        elif tool_name in ["image_read", "audio_read"]:
            return "multimodal"
        else:
            return "other"


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
