#!/usr/bin/env python3
# [SYSTEM: GUI | VERSION: 1.9f | STATUS: ACTIVE]
"""
Training Data Generator for OpenCode Tools
Generates comprehensive training data for all tool scenarios
"""

import json
from typing import List, Dict, Any
from pathlib import Path
import random

class TrainingDataGenerator:
    """Generate comprehensive training data for tool usage"""

    def __init__(self):
        self.tools_schemas = self._load_tool_schemas()

    def _load_tool_schemas(self) -> Dict[str, Any]:
        """Load OpenCode tool schemas"""
        return {
            "file_read": {
                "description": "Read contents of a file",
                "parameters": ["file_path", "start_line", "end_line"],
                "required": ["file_path"]
            },
            "file_write": {
                "description": "Create or overwrite a file with content",
                "parameters": ["file_path", "content", "create_dirs"],
                "required": ["file_path", "content"]
            },
            "file_edit": {
                "description": "Edit file by replacing text",
                "parameters": ["file_path", "old_text", "new_text"],
                "required": ["file_path", "old_text", "new_text"]
            },
            "file_search": {
                "description": "Search for files by name pattern",
                "parameters": ["pattern", "path", "max_results", "case_sensitive"],
                "required": ["pattern"]
            },
            "file_delete": {
                "description": "Delete a file",
                "parameters": ["file_path"],
                "required": ["file_path"]
            },
            "file_copy": {
                "description": "Copy a file to new location",
                "parameters": ["source_path", "dest_path"],
                "required": ["source_path", "dest_path"]
            },
            "file_move": {
                "description": "Move a file to new location",
                "parameters": ["source_path", "dest_path"],
                "required": ["source_path", "dest_path"]
            },
            "directory_list": {
                "description": "List directory contents",
                "parameters": ["path", "recursive", "show_hidden"],
                "required": []
            },
            "grep_search": {
                "description": "Search for text pattern in files",
                "parameters": ["pattern", "path", "file_pattern"],
                "required": ["pattern"]
            },
            "bash_execute": {
                "description": "Execute bash command",
                "parameters": ["command", "cwd"],
                "required": ["command"]
            },
            "git_operations": {
                "description": "Git operations",
                "parameters": ["operation", "args"],
                "required": ["operation"]
            },
            "system_info": {
                "description": "Get system information",
                "parameters": [],
                "required": []
            },
            "process_manage": {
                "description": "Manage system processes",
                "parameters": ["operation", "pattern", "pid"],
                "required": ["operation"]
            },
            "web_search": {
                "description": "Search the web",
                "parameters": ["query", "max_results"],
                "required": ["query"]
            },
            "web_fetch": {
                "description": "Fetch web content",
                "parameters": ["url", "extract_text"],
                "required": ["url"]
            },
            "code_analyze": {
                "description": "Analyze code structure",
                "parameters": ["file_path", "language"],
                "required": ["file_path"]
            },
            "change_directory": {
                "description": "Change working directory",
                "parameters": ["path"],
                "required": ["path"]
            }
        }

    def generate_conversation_flow(self, scenario: str) -> List[Dict[str, str]]:
        """Generate a conversation flow for a given scenario"""
        flows = {
            "file_analysis": self._file_analysis_flow(),
            "code_review": self._code_review_flow(),
            "system_inspection": self._system_inspection_flow(),
            "web_research": self._web_research_flow(),
            "multi_tool_workflow": self._multi_tool_workflow(),
            "git_workflow": self._git_workflow(),
            "debug_session": self._debug_session_flow(),
            "project_setup": self._project_setup_flow()
        }

        return flows.get(scenario, [])

    def _file_analysis_flow(self) -> List[Dict[str, str]]:
        """File analysis conversation flow"""
        return [
            {"role": "user", "content": "Find all Python files in the project and analyze their structure"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_search","args":{"pattern":"*.py","path":".","max_results":5}}'},
            {"role": "system", "content": '{"success":true,"output":"main.py\\nutils.py\\nconfig.py","data":{"matches":3}}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"main.py"}}'},
            {"role": "system", "content": '{"success":true,"output":"import sys\\ndef main():\\n    print(\\"Hello\\")\\nif __name__ == \\"__main__\\":\\n    main()"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"code_analyze","args":{"file_path":"main.py","language":"python"}}'},
            {"role": "system", "content": '{"success":true,"output":"Code Analysis (python):\\nLines: 6\\nFunctions: 1\\nClasses: 0\\nImports: 1","data":{"lines":6,"functions":1}}'},
            {"role": "assistant", "content": "Found 3 Python files. main.py has 6 lines with 1 function (main) and 1 import. The structure looks clean."}
        ]

    def _code_review_flow(self) -> List[Dict[str, str]]:
        """Code review conversation flow"""
        return [
            {"role": "user", "content": "Review the utils.py file for any issues or TODOs"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"utils.py"}}'},
            {"role": "system", "content": '{"success":true,"output":"def calculate(x):\\n    return x * 2\\n\\ndef process_data(data):\\n    # TODO: implement this\\n    pass"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"grep_search","args":{"pattern":"TODO|FIXME|XXX","path":".","file_pattern":"*.py"}}'},
            {"role": "system", "content": '{"success":true,"output":"utils.py:4:    # TODO: implement this\\nconfig.py:15:    # FIXME: hardcoded value","data":{"matches":2}}'},
            {"role": "assistant", "content": "Found 2 issues in the codebase:\\n1. utils.py line 4: TODO - process_data() needs implementation\\n2. config.py line 15: FIXME - hardcoded value needs to be configurable"}
        ]

    def _system_inspection_flow(self) -> List[Dict[str, str]]:
        """System inspection conversation flow"""
        return [
            {"role": "user", "content": "Check system resources and show me what Python processes are running"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"system_info","args":{}}'},
            {"role": "system", "content": '{"success":true,"output":"System Information:\\nCPU: 25% (8 cores)\\nMemory: 8.5GB / 16.0GB (53%)\\nDisk: 120GB / 512GB (23%)\\nPlatform: Linux 6.8","data":{"cpu_percent":25,"memory_percent":53}}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"process_manage","args":{"operation":"list","pattern":"python"}}'},
            {"role": "system", "content": '{"success":true,"output":"PID 1234: python3 main.py (CPU: 15%, MEM: 2.5%)\\nPID 5678: python script.py (CPU: 5%, MEM: 1.8%)","data":{"count":2}}'},
            {"role": "assistant", "content": "System status: CPU at 25%, Memory 8.5GB/16GB (53%), Disk 120GB/512GB (23%). Found 2 Python processes using 20% CPU combined."}
        ]

    def _web_research_flow(self) -> List[Dict[str, str]]:
        """Web research conversation flow"""
        return [
            {"role": "user", "content": "Find information about Python async best practices"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"web_search","args":{"query":"Python async await best practices","max_results":3}}'},
            {"role": "system", "content": '{"success":true,"output":"• Real Python - Async IO Best Practices\\n  Comprehensive guide to asyncio...\\n  Source: https://realpython.com/async-io-python\\n\\n• Python Docs - Asyncio\\n  Official documentation...","data":{"result_count":3}}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"web_fetch","args":{"url":"https://realpython.com/async-io-python","extract_text":true}}'},
            {"role": "system", "content": '{"success":true,"output":"Async IO Best Practices:\\n1. Use async/await syntax\\n2. Avoid blocking calls\\n3. Use asyncio.gather() for concurrent tasks...","data":{"size":2500}}'},
            {"role": "assistant", "content": "Found comprehensive information on Python async best practices. Key points: use async/await syntax, avoid blocking calls, and use asyncio.gather() for concurrent tasks."}
        ]

    def _multi_tool_workflow(self) -> List[Dict[str, str]]:
        """Complex multi-tool workflow"""
        return [
            {"role": "user", "content": "Set up a new Python project with git"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"bash_execute","args":{"command":"mkdir -p myproject/src myproject/tests myproject/docs"}}'},
            {"role": "system", "content": '{"success":true,"output":""}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"myproject/README.md","content":"# My Project\\n\\nA new Python project.\\n\\n## Setup\\n\\npip install -r requirements.txt"}}'},
            {"role": "system", "content": '{"success":true,"output":"File written successfully: myproject/README.md"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"myproject/requirements.txt","content":"# Project dependencies\\n"}}'},
            {"role": "system", "content": '{"success":true,"output":"File written successfully: myproject/requirements.txt"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"change_directory","args":{"path":"myproject"}}'},
            {"role": "system", "content": '{"success":true,"output":"Changed directory to: myproject"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"init"}}'},
            {"role": "system", "content": '{"success":true,"output":"Initialized empty Git repository in myproject/.git/"}'},
            {"role": "assistant", "content": "Project setup complete! Created directory structure, added README.md and requirements.txt, and initialized git repository."}
        ]

    def _git_workflow(self) -> List[Dict[str, str]]:
        """Git workflow conversation"""
        return [
            {"role": "user", "content": "Show me the git status and recent commits"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"status"}}'},
            {"role": "system", "content": '{"success":true,"output":" M src/main.py\\n M src/utils.py\\n?? new_file.txt"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"log","limit":5}}'},
            {"role": "system", "content": '{"success":true,"output":"a1b2c3d Fix bug in utils\\nd4e5f6g Add new feature\\ng7h8i9j Update docs\\ni9j0k1l Initial commit"}'},
            {"role": "assistant", "content": "Git status shows:\\n- Modified: src/main.py, src/utils.py\\n- Untracked: new_file.txt\\n\\nRecent commits:\\n- a1b2c3d: Fix bug in utils\\n- d4e5f6g: Add new feature\\n- g7h8i9j: Update docs"}
        ]

    def _debug_session_flow(self) -> List[Dict[str, str]]:
        """Debugging session flow"""
        return [
            {"role": "user", "content": "I'm getting an error in my script, help me debug it"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"bash_execute","args":{"command":"python main.py"}}'},
            {"role": "system", "content": '{"success":false,"output":"","error":"Traceback (most recent call last):\\n  File \\"main.py\\", line 15\\n    def process(data\\nSyntaxError: invalid syntax"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"main.py","start_line":10,"end_line":20}}'},
            {"role": "system", "content": '{"success":true,"output":"10: import utils\\n11: \\n12: def main():\\n13:     data = [1,2,3]\\n14:     \\n15: def process(data\\n16:     return data * 2\\n17: \\n18: if __name__ == \\"__main__\\":\\n19:     main()"}'},
            {"role": "assistant", "content": "Found the issue! Line 15 is missing a closing parenthesis. The function definition should be `def process(data):` not `def process(data`"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_edit","args":{"file_path":"main.py","old_text":"def process(data","new_text":"def process(data):"}}'},
            {"role": "system", "content": '{"success":true,"output":"File edited successfully"}'},
            {"role": "assistant", "content": "Fixed! Added the missing closing parenthesis and colon."}
        ]

    def _project_setup_flow(self) -> List[Dict[str, str]]:
        """Project setup flow"""
        return [
            {"role": "user", "content": "Create a complete Python package structure"},
            {"role": "assistant", "content": '{"type":"tool_call","name":"bash_execute","args":{"command":"mkdir -p mypackage/mypackage mypackage/tests mypackage/docs"}}'},
            {"role": "system", "content": '{"success":true,"output":""}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"mypackage/setup.py","content":"from setuptools import setup, find_packages\\n\\nsetup(\\n    name=\\"mypackage\\",\\n    version=\\"0.1.0\\",\\n    packages=find_packages(),\\n)"}}'},
            {"role": "system", "content": '{"success":true,"output":"File written successfully"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"mypackage/mypackage/__init__.py","content":"__version__ = \\"0.1.0\\""}}'},
            {"role": "system", "content": '{"success":true,"output":"File written successfully"}'},
            {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"mypackage/.gitignore","content":"__pycache__/\\n*.pyc\\n*.pyo\\n*.egg-info/\\ndist/\\nbuild/"}}'},
            {"role": "system", "content": '{"success":true,"output":"File written successfully"}'},
            {"role": "assistant", "content": "Package structure created! Set up directories, setup.py, __init__.py, and .gitignore for a complete Python package."}
        ]

    def generate_error_recovery_examples(self) -> List[Dict[str, Any]]:
        """Generate examples of handling errors gracefully"""
        examples = []

        # File not found recovery
        examples.append({
            "conversation": [
                {"role": "user", "content": "Read the config file"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"config.yaml"}}'},
                {"role": "system", "content": '{"success":false,"error":"File not found: config.yaml"}'},
                {"role": "assistant", "content": "The config file doesn't exist. Let me search for any config files."},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_search","args":{"pattern":"config*","path":"."}}'},
                {"role": "system", "content": '{"success":true,"output":"config.json\\nconfig.ini"}'},
                {"role": "assistant", "content": "I found config.json and config.ini instead. Which one should I read?"}
            ]
        })

        # Permission denied recovery
        examples.append({
            "conversation": [
                {"role": "user", "content": "Delete the old log file"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_delete","args":{"file_path":"old.log"}}'},
                {"role": "system", "content": '{"success":false,"error":"Permission denied: old.log"}'},
                {"role": "assistant", "content": "Can't delete old.log due to permissions. You may need to run with elevated privileges or check file ownership."}
            ]
        })

        return examples

    def generate_all_scenarios(self) -> List[Dict[str, Any]]:
        """Generate all training scenarios"""
        all_examples = []

        scenarios = [
            "file_analysis",
            "code_review",
            "system_inspection",
            "web_research",
            "multi_tool_workflow",
            "git_workflow",
            "debug_session",
            "project_setup"
        ]

        for scenario in scenarios:
            conversation = self.generate_conversation_flow(scenario)
            if conversation:
                all_examples.append({
                    "scenario": scenario,
                    "conversation": conversation
                })

        # Add error recovery examples
        for example in self.generate_error_recovery_examples():
            example["scenario"] = "error_recovery"
            all_examples.append(example)

        return all_examples

    def generate_baseline_skill_tests(self) -> List[Dict[str, Any]]:
        """
        Generates a set of atomic test cases to verify baseline tool-use skills.
        Each test focuses on a single tool and a simple, verifiable interaction.
        """
        baseline_tests = []

        # --- File Operations ---
        # Skill: file_read
        baseline_tests.append({
            "scenario": "skill_file_read_basic",
            "skill_name": "File Read Basic",
            "tool_name": "file_read",
            "conversation": [
                {"role": "user", "content": "Read the contents of a_test_file.txt"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_read","args":{"file_path":"a_test_file.txt"}}'},
                {"role": "system", "content": '{"success":true,"output":"This is a test file content."}'},
                {"role": "assistant", "content": "The content of a_test_file.txt is: 'This is a test file content.'"}
            ]
        })

        # Skill: file_write
        baseline_tests.append({
            "scenario": "skill_file_write_basic",
            "skill_name": "File Write Basic",
            "tool_name": "file_write",
            "conversation": [
                {"role": "user", "content": "Create a file named new_file.txt with the text 'Hello from Trainer'"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_write","args":{"file_path":"new_file.txt","content":"Hello from Trainer"}}'},
                {"role": "system", "content": '{"success":true,"output":"File written successfully: new_file.txt"}'},
                {"role": "assistant", "content": "Created new_file.txt with the specified content."}
            ]
        })

        # Skill: file_edit
        baseline_tests.append({
            "scenario": "skill_file_edit_basic",
            "skill_name": "File Edit Basic",
            "tool_name": "file_edit",
            "conversation": [
                {"role": "user", "content": "In existing_file.txt, change 'old_text' to 'new_text'"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_edit","args":{"file_path":"existing_file.txt","old_text":"old_text","new_text":"new_text"}}'},
                {"role": "system", "content": '{"success":true,"output":"File edited successfully: 1 replacement made"}'},
                {"role": "assistant", "content": "Successfully updated existing_file.txt."}
            ]
        })

        # Skill: file_search
        baseline_tests.append({
            "scenario": "skill_file_search_basic",
            "skill_name": "File Search Basic",
            "tool_name": "file_search",
            "conversation": [
                {"role": "user", "content": "Find all files ending with .log"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"file_search","args":{"pattern":"*.log","path":"."}}'},
                {"role": "system", "content": '{"success":true,"output":"app.log\nerror.log"}'},
                {"role": "assistant", "content": "Found app.log and error.log."}
            ]
        })

        # --- System Operations ---
        # Skill: system_info
        baseline_tests.append({
            "scenario": "skill_system_info_basic",
            "skill_name": "System Info Basic",
            "tool_name": "system_info",
            "conversation": [
                {"role": "user", "content": "What's the current system status?"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"system_info","args":{}}'},
                {"role": "system", "content": '{"success":true,"output":"CPU: 10% Memory: 30% Disk: 50%"}'},
                {"role": "assistant", "content": "Current system status: CPU 10%, Memory 30%, Disk 50%."}
            ]
        })

        # Skill: bash_execute (simple command)
        baseline_tests.append({
            "scenario": "skill_bash_execute_ls",
            "skill_name": "Bash Execute (ls)",
            "tool_name": "bash_execute",
            "conversation": [
                {"role": "user", "content": "List files in the current directory"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"bash_execute","args":{"command":"ls -F"}}'},
                {"role": "system", "content": '{"success":true,"output":"file1.txt\nfolder1/\nscript.sh"}'},
                {"role": "assistant", "content": "Files and folders listed."}
            ]
        })

        # --- Web Operations ---
        # Skill: web_search
        baseline_tests.append({
            "scenario": "skill_web_search_basic",
            "skill_name": "Web Search Basic",
            "tool_name": "web_search",
            "conversation": [
                {"role": "user", "content": "Search for 'latest AI news'"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"web_search","args":{"query":"latest AI news","max_results":1}}'},
                {"role": "system", "content": '{"success":true,"output":"AI News Today: Google announces new model. Source: example.com"}'},
                {"role": "assistant", "content": "Found latest AI news: Google announced a new model."}
            ]
        })

        # Skill: web_fetch
        baseline_tests.append({
            "scenario": "skill_web_fetch_basic",
            "skill_name": "Web Fetch Basic",
            "tool_name": "web_fetch",
            "conversation": [
                {"role": "user", "content": "Fetch content from https://example.com"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"web_fetch","args":{"url":"https://example.com","extract_text":true}}'},
                {"role": "system", "content": '{"success":true,"output":"Example Domain\nThis domain is for use in illustrative examples."}'},
                {"role": "assistant", "content": "Content from example.com fetched successfully."}
            ]
        })

        # --- Git Operations ---
        # Skill: git_operations (status)
        baseline_tests.append({
            "scenario": "skill_git_status_basic",
            "skill_name": "Git Status Basic",
            "tool_name": "git_operations",
            "conversation": [
                {"role": "user", "content": "Check the git status"},
                {"role": "assistant", "content": '{"type":"tool_call","name":"git_operations","args":{"operation":"status"}}'},
                {"role": "system", "content": '{"success":true,"output":"On branch main\nYour branch is up to date with 'origin/main'.\n\nnothing to commit, working tree clean"}'},
                {"role": "assistant", "content": "Git status is clean, branch main is up to date."}
            ]
        })

        return baseline_tests
