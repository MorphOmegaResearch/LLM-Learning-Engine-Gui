"""
Tool Alias Translator - Maps common agent framework tools to OpenCode equivalents

Many models are trained on LangChain, AutoGen, Qwen-Agent, and other frameworks
that use different tool naming conventions. This translator allows models to use
familiar tool names from their training data.
"""

from typing import Dict, Optional, Any


class ToolAliasTranslator:
    """Translates common agent framework tool names to OpenCode tools."""

    def __init__(self):
        # Maps: alias_name -> (opencode_tool, arg_transformer)
        # arg_transformer is a function that converts alias args to opencode args
        self.aliases = {
            # LangChain-style tools
            'parse_tool_result': ('PASSTHROUGH', self._passthrough_last_result),
            'extract_data': ('PASSTHROUGH', self._passthrough_last_result),
            'format_output': ('PASSTHROUGH', self._passthrough_last_result),
            'get_result': ('PASSTHROUGH', self._passthrough_last_result),

            # File operation aliases (common variations)
            'read_file': ('file_read', self._map_file_path),
            'write_file': ('file_write', self._map_file_write),
            'search_files': ('file_search', self._map_file_search),
            'list_directory': ('directory_list', self._map_path),
            'list_dir': ('directory_list', self._map_path),
            'ls': ('directory_list', self._map_path),

            # Code execution aliases
            'execute_python': ('bash_execute', self._map_python_code),
            'run_python': ('bash_execute', self._map_python_code),
            'python': ('bash_execute', self._map_python_code),
            'code_interpreter': ('bash_execute', self._map_code_interpreter),
            'run_code': ('bash_execute', self._map_bash_command),
            'shell': ('bash_execute', self._map_bash_command),

            # Search aliases
            'grep': ('grep_search', self._map_grep),
            'search': ('grep_search', self._map_search_pattern),
            'find_in_files': ('grep_search', self._map_search_pattern),

            # Web aliases
            'google_search': ('web_search', self._map_query),
            'search_web': ('web_search', self._map_query),
            'fetch_url': ('web_fetch', self._map_url),
            'get_url': ('web_fetch', self._map_url),

            # Analysis aliases
            'analyze_code': ('code_analyze', lambda args: args),
            'check_package': ('package_check', lambda args: args),

            # System aliases
            'get_system_info': ('system_info', lambda args: {}),
            'system_status': ('system_info', lambda args: {}),
        }

        # Track last tool result for PASSTHROUGH
        self.last_result = None

    def translate(self, tool_name: str, args: Dict[str, Any]) -> Optional[tuple]:
        """
        Translate alias to OpenCode tool.

        Args:
            tool_name: Tool name (might be an alias)
            args: Tool arguments

        Returns:
            (opencode_tool_name, translated_args) or None if not an alias
        """
        if tool_name not in self.aliases:
            return None

        target_tool, arg_transformer = self.aliases[tool_name]

        # Special case: PASSTHROUGH
        if target_tool == 'PASSTHROUGH':
            return arg_transformer(args)

        # Normal alias translation
        translated_args = arg_transformer(args)
        return (target_tool, translated_args)

    def is_alias(self, tool_name: str) -> bool:
        """Check if tool name is a known alias."""
        return tool_name in self.aliases

    def set_last_result(self, result: Any):
        """Store last tool result for PASSTHROUGH operations."""
        self.last_result = result

    # ARG TRANSFORMER FUNCTIONS

    def _passthrough_last_result(self, args: Dict) -> tuple:
        """
        PASSTHROUGH: Return last tool result instead of calling new tool.
        Used for meta-tools like parse_tool_result that just want to see the data again.
        """
        return ('PASSTHROUGH', {'result': self.last_result, 'note': 'Returning previous tool result'})

    def _map_file_path(self, args: Dict) -> Dict:
        """Map common file path variations to file_path."""
        if 'file_path' in args:
            return args
        elif 'path' in args:
            return {'file_path': args['path']}
        elif 'filename' in args:
            return {'file_path': args['filename']}
        elif 'file' in args:
            return {'file_path': args['file']}
        return args

    def _map_file_write(self, args: Dict) -> Dict:
        """Map file write arguments."""
        result = self._map_file_path(args)
        # Ensure content exists
        if 'content' not in result:
            if 'text' in args:
                result['content'] = args['text']
            elif 'data' in args:
                result['content'] = args['data']
        return result

    def _map_file_search(self, args: Dict) -> Dict:
        """Map file search arguments."""
        result = {}
        if 'pattern' in args:
            result['pattern'] = args['pattern']
        elif 'filename' in args:
            result['pattern'] = args['filename']
        elif 'name' in args:
            result['pattern'] = args['name']

        if 'path' in args:
            result['path'] = args['path']
        elif 'directory' in args:
            result['path'] = args['directory']
        else:
            result['path'] = '.'

        return result

    def _map_path(self, args: Dict) -> Dict:
        """Map path argument."""
        if 'path' in args:
            return args
        elif 'directory' in args:
            return {'path': args['directory']}
        elif 'dir' in args:
            return {'path': args['dir']}
        return {'path': '.'}

    def _map_python_code(self, args: Dict) -> Dict:
        """Map Python code execution to bash_execute."""
        if 'code' in args:
            return {'command': f'python3 -c "{args["code"]}"'}
        elif 'script' in args:
            return {'command': f'python3 -c "{args["script"]}"'}
        return args

    def _map_code_interpreter(self, args: Dict) -> Dict:
        """Map code_interpreter to bash execution."""
        if 'code' in args:
            # Write to temp file and execute
            code = args['code'].replace('"', '\\"')
            return {'command': f'python3 -c "{code}"'}
        return self._map_bash_command(args)

    def _map_bash_command(self, args: Dict) -> Dict:
        """Map bash command arguments."""
        if 'command' in args:
            return args
        elif 'cmd' in args:
            return {'command': args['cmd']}
        elif 'code' in args:
            return {'command': args['code']}
        return args

    def _map_grep(self, args: Dict) -> Dict:
        """Map grep arguments to grep_search."""
        result = {}
        if 'pattern' in args:
            result['pattern'] = args['pattern']
        elif 'text' in args:
            result['pattern'] = args['text']
        elif 'search' in args:
            result['pattern'] = args['search']

        if 'path' in args:
            result['path'] = args['path']
        elif 'file' in args:
            result['path'] = args['file']
        else:
            result['path'] = '.'

        return result

    def _map_search_pattern(self, args: Dict) -> Dict:
        """Map search pattern to grep_search."""
        return self._map_grep(args)

    def _map_query(self, args: Dict) -> Dict:
        """Map query argument for web search."""
        if 'query' in args:
            return args
        elif 'q' in args:
            return {'query': args['q']}
        elif 'search' in args:
            return {'query': args['search']}
        return args

    def _map_url(self, args: Dict) -> Dict:
        """Map URL argument for web fetch."""
        if 'url' in args:
            return args
        elif 'link' in args:
            return {'url': args['link']}
        elif 'address' in args:
            return {'url': args['address']}
        return args


# Global instance
_alias_translator = None

def get_alias_translator() -> ToolAliasTranslator:
    """Get global alias translator instance."""
    global _alias_translator
    if _alias_translator is None:
        _alias_translator = ToolAliasTranslator()
    return _alias_translator
