"""
Tool Schemas - Ollama-compatible tool definitions
Maps OpenCode tools to Ollama function calling format
"""

# Tool schemas for Ollama function calling
TOOL_SCHEMAS = {
    # File Operations
    "file_read": {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read the contents of a file. Returns the file content as text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read (relative to working directory)"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (optional, 1-indexed)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (optional, inclusive)"
                    }
                },
                "required": ["file_path"]
            }
        }
    },

    "file_write": {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write content to a file. Creates new file or overwrites existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to write"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },

    "file_edit": {
        "type": "function",
        "function": {
            "name": "file_edit",
            "description": "Edit an existing file by replacing specific content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "old_content": {
                        "type": "string",
                        "description": "Content to search for and replace"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "New content to replace with"
                    }
                },
                "required": ["file_path", "old_content", "new_content"]
            }
        }
    },

    "file_copy": {
        "type": "function",
        "function": {
            "name": "file_copy",
            "description": "Copy a file from source to destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to the source file"
                    },
                    "dest_path": {
                        "type": "string",
                        "description": "Path to the destination"
                    }
                },
                "required": ["source_path", "dest_path"]
            }
        }
    },

    "file_move": {
        "type": "function",
        "function": {
            "name": "file_move",
            "description": "Move or rename a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to the source file"
                    },
                    "dest_path": {
                        "type": "string",
                        "description": "Path to the destination"
                    }
                },
                "required": ["source_path", "dest_path"]
            }
        }
    },

    "file_delete": {
        "type": "function",
        "function": {
            "name": "file_delete",
            "description": "Delete a file. This operation cannot be undone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to delete"
                    }
                },
                "required": ["file_path"]
            }
        }
    },

    "file_create": {
        "type": "function",
        "function": {
            "name": "file_create",
            "description": "Create an empty file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to create"
                    }
                },
                "required": ["file_path"]
            }
        }
    },

    "file_fill": {
        "type": "function",
        "function": {
            "name": "file_fill",
            "description": "Create a file and fill it with content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to create"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to fill the file with"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },

    # Search & Discovery
    "grep_search": {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for text patterns in files using grep.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex supported)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to search in (file or directory)"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Search recursively in subdirectories"
                    }
                },
                "required": ["pattern", "path"]
            }
        }
    },

    "file_search": {
        "type": "function",
        "function": {
            "name": "file_search",
            "description": "Search for files by name or pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "File name pattern (wildcards supported)"
                    },
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search in"
                    }
                },
                "required": ["pattern"]
            }
        }
    },

    "directory_list": {
        "type": "function",
        "function": {
            "name": "directory_list",
            "description": "List contents of a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dir_path": {
                        "type": "string",
                        "description": "Path to the directory to list"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively"
                    }
                },
                "required": ["dir_path"]
            }
        }
    },

    # Execution
    "bash_execute": {
        "type": "function",
        "function": {
            "name": "bash_execute",
            "description": "Execute a bash command. Use with caution - can modify system state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Bash command to execute"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for command execution"
                    }
                },
                "required": ["command"]
            }
        }
    },

    "git_operations": {
        "type": "function",
        "function": {
            "name": "git_operations",
            "description": "Execute git commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Git operation (status, commit, push, pull, etc.)"
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional arguments for the git command"
                    }
                },
                "required": ["operation"]
            }
        }
    },

    # System
    "system_info": {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Get system information (OS, CPU, memory, disk usage).",
            "parameters": {
                "type": "object",
                "properties": {
                    "info_type": {
                        "type": "string",
                        "description": "Type of info to get: 'all', 'cpu', 'memory', 'disk'"
                    }
                },
                "required": []
            }
        }
    },

    "change_directory": {
        "type": "function",
        "function": {
            "name": "change_directory",
            "description": "Change the working directory for subsequent operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "new_dir": {
                        "type": "string",
                        "description": "Path to the new working directory"
                    }
                },
                "required": ["new_dir"]
            }
        }
    },

    "resource_request": {
        "type": "function",
        "function": {
            "name": "resource_request",
            "description": "Request system resource allocation (CPU threads, memory).",
            "parameters": {
                "type": "object",
                "properties": {
                    "resource_type": {
                        "type": "string",
                        "description": "Type of resource: 'cpu', 'memory'"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Amount to request"
                    }
                },
                "required": ["resource_type", "amount"]
            }
        }
    }
}


def get_enabled_tool_schemas(enabled_tools_dict):
    """
    Get tool schemas for enabled tools only.

    Args:
        enabled_tools_dict: Dict of {tool_name: bool} from tool_settings.json

    Returns:
        List of tool schemas for Ollama
    """
    enabled_schemas = []

    for tool_name, enabled in enabled_tools_dict.items():
        if enabled and tool_name in TOOL_SCHEMAS:
            enabled_schemas.append(TOOL_SCHEMAS[tool_name])

    return enabled_schemas
