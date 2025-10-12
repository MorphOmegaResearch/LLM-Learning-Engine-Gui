# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Tool Executor - Executes OpenCode tools from model tool_calls
Bridges Ollama function calling with OpenCode tool system
"""

import asyncio
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

        except ImportError as e:
            log_message(f"TOOL_EXECUTOR ERROR: Failed to import OpenCode tools: {e}")
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

    def execute_tool_sync(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for execute_tool.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result
        """
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
