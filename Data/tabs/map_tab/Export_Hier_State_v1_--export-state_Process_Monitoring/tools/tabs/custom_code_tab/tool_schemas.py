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
    },

    "agent_request": {
        "type": "function",
        "function": {
            "name": "agent_request",
            "description": "Request assistance from another agent in your expert panel. Only available to orchestrator agents with MoE enabled. Use this to delegate tasks to specialized agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the agent to consult (must be in your MoE expert panel)"
                    },
                    "task": {
                        "type": "string",
                        "description": "The specific task or question for the agent"
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional additional context to help the agent understand the task"
                    }
                },
                "required": ["agent_name", "task"]
            }
        }
    },

    # Agent Control Tools (Orchestrator Expert+)
    "agents_mount_all": {
        "type": "function",
        "function": {
            "name": "agents_mount_all",
            "description": "Mount all agents in the current roster, making them available for execution. Requires orchestrator type with Expert+ class or high trust level.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    "agents_unmount_all": {
        "type": "function",
        "function": {
            "name": "agents_unmount_all",
            "description": "Unmount all currently mounted agents, releasing their resources. Requires orchestrator type with Expert+ class or high trust level.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    "agents_status": {
        "type": "function",
        "function": {
            "name": "agents_status",
            "description": "Get current status of all agents in roster, including which are mounted, their variants, and MoE panel assignments.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    "agents_route_task": {
        "type": "function",
        "function": {
            "name": "agents_route_task",
            "description": "Route a specific task or message to a target agent's chat interface.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {
                        "type": "string",
                        "description": "Name of the target agent (also accepts 'agent_name')"
                    },
                    "text": {
                        "type": "string",
                        "description": "The message or task to send to the agent (also accepts 'message')"
                    }
                },
                "required": ["agent", "text"]
            }
        }
    },

    "agents_set_roster": {
        "type": "function",
        "function": {
            "name": "agents_set_roster",
            "description": "Set the active agent roster configuration. Requires orchestrator type with Expert+ class or high trust level.",
            "parameters": {
                "type": "object",
                "properties": {
                    "roster": {
                        "type": "array",
                        "description": "Array of agent configuration objects",
                        "items": {
                            "type": "object"
                        }
                    }
                },
                "required": ["roster"]
            }
        }
    },

    "agents_open_tab": {
        "type": "function",
        "function": {
            "name": "agents_open_tab",
            "description": "Focus the Agents tab in the UI to allow user interaction with agent configurations.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    "agents_highlight_in_collections": {
        "type": "function",
        "function": {
            "name": "agents_highlight_in_collections",
            "description": "Highlight a specific agent in the Collections/Model Browser panel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of the agent to highlight"
                    }
                },
                "required": ["agent_name"]
            }
        }
    },

    "agents_focus_mounts": {
        "type": "function",
        "function": {
            "name": "agents_focus_mounts",
            "description": "Open and focus the agent mounts control panel in the Quick Actions menu.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },

    # Tool aliases for compatibility with type_catalog_v2.json naming
    "glob": {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Search for files matching a pattern (glob syntax). Alias for file_search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "File name pattern (wildcards supported: *.txt, **/*.py, etc.)"
                    },
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search in (defaults to current directory)"
                    }
                },
                "required": ["pattern"]
            }
        }
    },

    "grep": {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for text patterns in files. Alias for grep_search.",
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

    "run_bash_command": {
        "type": "function",
        "function": {
            "name": "run_bash_command",
            "description": "Execute a bash command. Alias for bash_execute.",
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

    "web_fetch": {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch content from a URL. Supports HTTP/HTTPS requests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to fetch content from"
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, etc.)",
                        "enum": ["GET", "POST", "PUT", "DELETE"]
                    },
                    "headers": {
                        "type": "object",
                        "description": "Optional HTTP headers"
                    }
                },
                "required": ["url"]
            }
        }
    },

    # Browser automation tools
    "browser_screenshot": {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Take a screenshot of the current screen or a specific region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Optional region to screenshot (x, y, width, height)"
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Path to save the screenshot"
                    }
                },
                "required": []
            }
        }
    },

    "browser_click": {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click at a specific screen position or on a UI element.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate to click"
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate to click"
                    },
                    "button": {
                        "type": "string",
                        "description": "Mouse button to use (left, right, middle)",
                        "enum": ["left", "right", "middle"]
                    }
                },
                "required": ["x", "y"]
            }
        }
    },

    "browser_type": {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Type text using keyboard automation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    },
                    "interval": {
                        "type": "number",
                        "description": "Interval between keystrokes in seconds"
                    }
                },
                "required": ["text"]
            }
        }
    },

    "browser_navigate": {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Move mouse to a specific position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate"
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate"
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration of movement in seconds"
                    }
                },
                "required": ["x", "y"]
            }
        }
    },

    "browser_scroll": {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the screen or window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clicks": {
                        "type": "integer",
                        "description": "Number of scroll clicks (positive = down, negative = up)"
                    },
                    "x": {
                        "type": "integer",
                        "description": "X coordinate to scroll at (optional)"
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate to scroll at (optional)"
                    }
                },
                "required": ["clicks"]
            }
        }
    },

    "browser_drag": {
        "type": "function",
        "function": {
            "name": "browser_drag",
            "description": "Drag from one position to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_x": {
                        "type": "integer",
                        "description": "Starting X coordinate"
                    },
                    "start_y": {
                        "type": "integer",
                        "description": "Starting Y coordinate"
                    },
                    "end_x": {
                        "type": "integer",
                        "description": "Ending X coordinate"
                    },
                    "end_y": {
                        "type": "integer",
                        "description": "Ending Y coordinate"
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration of drag in seconds"
                    }
                },
                "required": ["start_x", "start_y", "end_x", "end_y"]
            }
        }
    },

    "element_detect": {
        "type": "function",
        "function": {
            "name": "element_detect",
            "description": "Detect UI elements or images on screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to reference image to find"
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence threshold (0.0 to 1.0)"
                    }
                },
                "required": ["image_path"]
            }
        }
    },

    "wait": {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for a specified duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Number of seconds to wait"
                    }
                },
                "required": ["seconds"]
            }
        }
    },

    "page_extract": {
        "type": "function",
        "function": {
            "name": "page_extract",
            "description": "Extract text or data from a webpage or screen region.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Screen region to extract from (x, y, width, height)"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format (text, json, etc.)",
                        "enum": ["text", "json", "html"]
                    }
                },
                "required": []
            }
        }
    },

    "browser_automation": {
        "type": "function",
        "function": {
            "name": "browser_automation",
            "description": "Execute complex browser automation sequences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        "description": "List of actions to perform",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "params": {"type": "object"}
                            }
                        }
                    }
                },
                "required": ["actions"]
            }
        }
    },

    # Media processing tools
    "image_read": {
        "type": "function",
        "function": {
            "name": "image_read",
            "description": "Read and analyze an image file. Extract text (OCR), detect objects, or describe contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the image file"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform",
                        "enum": ["ocr", "describe", "detect_objects", "metadata"]
                    }
                },
                "required": ["image_path"]
            }
        }
    },

    "audio_read": {
        "type": "function",
        "function": {
            "name": "audio_read",
            "description": "Read and analyze an audio file. Transcribe speech, extract metadata, or analyze audio properties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "audio_path": {
                        "type": "string",
                        "description": "Path to the audio file"
                    },
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform",
                        "enum": ["transcribe", "metadata", "properties"]
                    }
                },
                "required": ["audio_path"]
            }
        }
    },

    # Special meta-tool
    "all": {
        "type": "function",
        "function": {
            "name": "all",
            "description": "Meta-tool representing access to all available tools. Used for orchestrator agents with unrestricted tool access.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
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
