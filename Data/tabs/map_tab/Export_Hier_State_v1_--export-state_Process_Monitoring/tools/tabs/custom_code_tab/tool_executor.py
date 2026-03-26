# [SYSTEM: GUI | VERSION: Main | STATUS: ACTIVE]
"""
Tool Executor - Executes OpenCode tools from model tool_calls
Bridges Ollama function calling with OpenCode tool system
"""

import asyncio
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add opencode to path
sys.path.insert(0, str(Path(__file__).parent / "site-packages"))

from logger_util import log_message

_LEGACY_IMPORT_WARNED = False


def import_module(module_name: str):
    """Compatibility shim for legacy call sites."""
    global _LEGACY_IMPORT_WARNED
    if not _LEGACY_IMPORT_WARNED:
        log_message("TOOL_EXECUTOR: Legacy import_module shim in use; please switch to importlib.import_module.")
        _LEGACY_IMPORT_WARNED = True
    return importlib.import_module(module_name)


class ToolExecutor:
    """Executes OpenCode tools based on model tool calls"""

    def __init__(self, working_dir: Optional[Path] = None):
        self.working_dir = working_dir or Path.cwd()
        self.tool_instances = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Initialize OpenCode tool instances"""
        try:
            # Minimal import of opencode submodules (no MCP) by setting env flag
            import os as _os
            _os.environ['OPENCODE_MINIMAL_IMPORT'] = '1'
            from opencode.tools import (
                FileReadTool, FileWriteTool, FileEditTool,
                FileCopyTool, FileMoveTool, FileDeleteTool,
                FileCreateTool, FileFillTool, GrepSearchTool,
                FileSearchTool, DirectoryListTool, BashExecuteTool,
                GitOperationsTool, SystemInfoTool, ChangeDirectoryTool,
                ResourceRequestTool, ThinkTimeTool,
                WebSearchTool, WebFetchTool, CodeAnalyzeTool,
                ProcessManageTool, PackageCheckTool
            )
            from opencode.config import ToolsConfig

            # Import browser tools (Phase 1.6B)
            from browser_tools_opencode import (
                BrowserScreenshotTool, BrowserClickTool, BrowserDoubleClickTool,
                BrowserRightClickTool, BrowserDragTool, BrowserTypeTextTool,
                BrowserPressKeyTool, BrowserPressHotkeyTool, BrowserScrollTool,
                BrowserMoveMouseTool, BrowserWaitTool, BrowserLocateImageTool,
                BrowserGetMousePositionTool, BrowserGetPixelColorTool,
                BrowserAlertTool, BrowserConfirmTool
            )

            # Create config
            config = ToolsConfig()

            # Initialize each tool
            self.tool_instances = {
                'file_read': FileReadTool(config),
                'read_text': FileReadTool(config),
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
                'think_time': ThinkTimeTool(config),
                # Extended set
                'web_search': WebSearchTool(config),
                'web_fetch': WebFetchTool(config),
                'code_analyze': CodeAnalyzeTool(config),
                'process_manage': ProcessManageTool(config),
                'package_check': PackageCheckTool(config),
                # Browser automation tools (Phase 1.6B)
                'browser_screenshot': BrowserScreenshotTool(config),
                'browser_click': BrowserClickTool(config),
                'browser_double_click': BrowserDoubleClickTool(config),
                'browser_right_click': BrowserRightClickTool(config),
                'browser_drag': BrowserDragTool(config),
                'browser_type': BrowserTypeTextTool(config),
                'browser_press': BrowserPressKeyTool(config),
                'browser_hotkey': BrowserPressHotkeyTool(config),
                'browser_scroll': BrowserScrollTool(config),
                'browser_navigate': BrowserMoveMouseTool(config),
                'wait': BrowserWaitTool(config),
                'element_detect': BrowserLocateImageTool(config),
                'get_mouse_position': BrowserGetMousePositionTool(config),
                'get_pixel_color': BrowserGetPixelColorTool(config),
                'browser_alert': BrowserAlertTool(config),
                'browser_confirm': BrowserConfirmTool(config),
            }

            # Set working directory for all tools
            for tool in self.tool_instances.values():
                tool.working_dir = self.working_dir

            log_message(f"TOOL_EXECUTOR: Initialized {len(self.tool_instances)} tools")

        except Exception as e:
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

        # Phase Sub-Zero-D: Check for planner agent tools
        planner_tools = ['read_plans', 'create_plan', 'link_plan_to_todo',
                        'estimate_duration', 'add_todo_to_plan']

        if tool_name in planner_tools:
            try:
                # Import and execute planner tool
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from planner_tools import execute_planner_tool
                result = await execute_planner_tool(tool_name, parameters)
                log_message(f"TOOL_EXECUTOR: Planner tool {tool_name} executed: {result.get('success', False)}")
                return result
            except Exception as e:
                error_msg = f"Planner tool execution failed: {str(e)}"
                log_message(f"TOOL_EXECUTOR ERROR: {error_msg}")
                return {
                    'success': False,
                    'output': '',
                    'error': error_msg
                }

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

            # Post-validate side effects for filesystem tools to prevent false positives
            try:
                from pathlib import Path as _P
                if tool_name in ('file_create', 'file_write', 'file_fill'):
                    fp = (parameters.get('file_path') or parameters.get('path') or '').strip()
                    if fp:
                        abs_path = (_P(fp) if _P(fp).is_absolute() else (self.working_dir / fp)).resolve()
                        exists = abs_path.exists()
                        if not exists and result.success:
                            # Correct the result to failure with a clear reason
                            result.success = False
                            result.error = f"Post-check failed: file not found at {abs_path}"
                            result.output = ''
                elif tool_name == 'file_delete':
                    fp = (parameters.get('file_path') or '').strip()
                    if fp:
                        abs_path = (_P(fp) if _P(fp).is_absolute() else (self.working_dir / fp)).resolve()
                        if abs_path.exists() and result.success:
                            result.success = False
                            result.error = f"Post-check failed: file still exists at {abs_path}"
                            result.output = ''
            except Exception:
                pass

            # Convert ToolResult to dict (after post-checks)
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
