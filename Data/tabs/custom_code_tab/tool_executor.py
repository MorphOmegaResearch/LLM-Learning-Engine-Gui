"""
Tool Executor - Executes OpenCode tools from model tool_calls
Bridges Ollama function calling with OpenCode tool system
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add opencode to path
sys.path.insert(0, str(Path(__file__).parent / "site-packages"))

from logger_util import log_message


class ToolExecutor:
    """Executes OpenCode tools based on model tool calls"""

    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
        self.tool_instances = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize OpenCode tool instances"""
        try:
            # Import OpenCode tools
            from opencode.tools import (
                FileReadTool, FileWriteTool, FileEditTool,
                FileCopyTool, FileMoveTool, FileDeleteTool,
                FileCreateTool, FileFillTool, GrepSearchTool,
                FileSearchTool, DirectoryListTool, BashExecuteTool,
                GitOperationsTool, SystemInfoTool, ChangeDirectoryTool,
                ResourceRequestTool
            )
            from opencode.config import ToolsConfig
        except ImportError as e:
            if "No module named 'rich'" in str(e):
                log_message("TOOL_EXECUTOR ERROR: The 'rich' library is not installed. Please install it using 'pip install rich'")
            else:
                log_message(f"TOOL_EXECUTOR ERROR: Failed to import OpenCode tools: {e}")
            self.tool_instances = {}
            return

        try:
            # Create config
            config = ToolsConfig()

            # Initialize each tool
            self.tool_instances = {
                'file_read': FileReadTool(config),
                'file_write': FileWriteTool(config),
                'file_edit': FileEditTool(config),
                'file_copy': FileCopyTool(config),
                'file_move': FileMoveTool(config),
                'file_delete': FileDeleteTool(config),
                'file_create': FileCreateTool(config),
                'file_fill': FileFillTool(config),
                'grep_search': GrepSearchTool(config),
                'file_search': FileSearchTool(config),
                'directory_list': DirectoryListTool(config),
                'bash_execute': BashExecuteTool(config),
                'git_operations': GitOperationsTool(config),
                'system_info': SystemInfoTool(config),
                'change_directory': ChangeDirectoryTool(config),
                'resource_request': ResourceRequestTool(config),
            }

            # Set working directory for all tools
            for tool in self.tool_instances.values():
                tool.working_dir = self.working_dir

            log_message(f"TOOL_EXECUTOR: Initialized {len(self.tool_instances)} tools")

        except Exception as e:
            log_message(f"TOOL_EXECUTOR ERROR: Failed to initialize OpenCode tools: {e}")
            self.tool_instances = {}

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters from model

        Returns:
            Dict with 'success', 'output', 'error' keys
        """
        log_message(f"TOOL_EXECUTOR: Executing {tool_name} with params: {parameters}")

        if tool_name not in self.tool_instances:
            error_msg = f"Tool '{tool_name}' not found or not initialized"
            log_message(f"TOOL_EXECUTOR ERROR: {error_msg}")
            return {
                'success': False,
                'output': '',
                'error': error_msg
            }

        try:
            tool = self.tool_instances[tool_name]

            # Execute the tool (async)
            result = await tool.execute(**parameters)

            # Convert ToolResult to dict
            return {
                'success': result.success,
                'output': result.output,
                'error': result.error if result.error else None,
                'data': result.data if hasattr(result, 'data') and result.data else None
            }

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            log_message(f"TOOL_EXECUTOR ERROR: {error_msg}")
            return {
                'success': False,
                'output': '',
                'error': error_msg
            }

    def _execute_ostk_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Os_Toolkit subcommand as tool call."""
        _ostk_path = Path(__file__).parent.parent / "action_panel_tab" / "Os_Toolkit.py"
        if not _ostk_path.exists():
            return {"success": False, "output": "", "error": f"Os_Toolkit.py not found at {_ostk_path}"}

        _cmd_map = {
            "ostk_todo_view": ["todo", "view"],
            "ostk_assess":    ["assess"],
            "ostk_query":     ["query"],
            "ostk_explain":   ["explain"],
            "ostk_latest":    ["latest"],
        }
        _cmd = [sys.executable, str(_ostk_path)] + _cmd_map.get(tool_name, [])

        if args.get("file_path"):
            _cmd.append(args["file_path"])
        if args.get("graph"):
            _cmd.append("--graph")
        if args.get("since"):
            _cmd.extend(["--since", args["since"]])

        try:
            result = subprocess.run(
                _cmd, capture_output=True, text=True, timeout=15,
                cwd=str(_ostk_path.parent)
            )
            # Strip Os_Toolkit noise lines
            _out = '\n'.join(
                l for l in result.stdout.splitlines()
                if not l.startswith('BABEL_LOG:')
                and not l.startswith('[+]')
                and not l.startswith('[-]')
                and not l.startswith('[*]')
                and not l.startswith('[]')
            )
            log_message(f"TOOL_EXECUTOR: ostk_{tool_name} returned {len(_out)} chars")
            return {
                "success": result.returncode == 0,
                "output": _out.strip()[:2000],
                "error": result.stderr.strip()[:500] if result.returncode != 0 else None
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"{tool_name} timed out (15s)"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}

    def execute_tool_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for execute_tool.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
        # Route Os_Toolkit tools to subprocess handler
        if tool_name.startswith('ostk_'):
            return self._execute_ostk_tool(tool_name, parameters)

        # Create new event loop for async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self.execute_tool(tool_name, parameters))
            return result
        finally:
            loop.close()

    def get_working_directory(self) -> str:
        """Get current working directory"""
        return str(self.working_dir)

    def set_working_directory(self, new_dir: str) -> bool:
        """
        Set working directory.

        Args:
            new_dir: New working directory path

        Returns:
            True if successful
        """
        try:
            new_path = Path(new_dir).resolve()
            if new_path.exists() and new_path.is_dir():
                self.working_dir = new_path

                # Update all tool instances
                for tool in self.tool_instances.values():
                    tool.working_dir = new_path

                log_message(f"TOOL_EXECUTOR: Working directory changed to {new_path}")
                return True
            else:
                log_message(f"TOOL_EXECUTOR ERROR: Directory does not exist: {new_dir}")
                return False

        except Exception as e:
            log_message(f"TOOL_EXECUTOR ERROR: Failed to change directory: {e}")
            return False
