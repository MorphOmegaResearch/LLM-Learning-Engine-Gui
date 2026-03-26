"""
FIX FOR TOOL CALL PARSING ISSUE
================================

THE PROBLEM:
-----------
Your models are generating tool calls but _extract_one_line_json() isn't 
recognizing them. The function checks for specific JSON formats, but if the
model outputs something slightly different, it fails silently.

WHY MCP WON'T FIX THIS:
-----------------------
MCP is for EXTERNAL models to connect to your tools. It won't help your 
INTERNAL Gemma model parse tool calls. You need to fix the parsing first.

THE SOLUTION: Enhanced Tool Call Parser
----------------------------------------
"""

import re
import json
from typing import Optional, Dict
from rich.console import Console

console = Console()

def _extract_one_line_json_ENHANCED(raw: str, obj_type: str = None) -> Optional[dict]:
    """
    Enhanced tool call extraction that handles more formats and provides
    better debugging information.
    """
    
    # DEBUG: Show what we're searching for
    if obj_type == "tool_call":
        console.print(f"[dim yellow]DEBUG: Searching for tool call in response[/dim yellow]")
        
        # Check if response contains any tool-like patterns
        tool_indicators = [
            "tool_call", "function_call", "execute", "run_tool",
            "file_read", "file_write", "file_search", "bash_execute",
            '{"type":', '{"tool":', '{"name":', '{"function":',
            "I'll read", "I'll search", "Let me read", "Let me search"
        ]
        
        found_indicators = [ind for ind in tool_indicators if ind.lower() in raw.lower()]
        if found_indicators:
            console.print(f"[dim cyan]Found tool indicators: {found_indicators}[/dim cyan]")
    
    # ========== PATTERN 1: Clean JSON Lines ==========
    for ln in raw.splitlines():
        ln = ln.strip()
        # Remove markdown formatting
        ln = re.sub(r'^```.*?$', '', ln)  # Remove code blocks
        ln = re.sub(r'^[\s\*\-•›]+', '', ln)  # Remove bullets
        ln = ln.strip()
        
        if ln.startswith("{") and ln.endswith("}"):
            try:
                j = json.loads(ln)
                
                # OpenCode format: {"type":"tool_call","name":"...","args":{}}
                if obj_type == "tool_call" and j.get("type") == "tool_call":
                    console.print(f"[green]✓ Found OpenCode format tool call[/green]")
                    return j
                
                # Gemma-tools format: {"tool":"...","args":{}}
                if obj_type == "tool_call" and "tool" in j and "args" in j:
                    console.print(f"[green]✓ Found Gemma-tools format[/green]")
                    return {
                        "type": "tool_call",
                        "name": j["tool"],
                        "args": j.get("args", {})
                    }
                
                # Function call format: {"function":"...","parameters":{}}
                if obj_type == "tool_call" and "function" in j and "parameters" in j:
                    console.print(f"[green]✓ Found function call format[/green]")
                    return {
                        "type": "tool_call",
                        "name": j["function"],
                        "args": j.get("parameters", {})
                    }
                
                # Direct tool format: {"file_read":{"path":"..."}}
                for tool in ["file_read", "file_write", "file_search", "bash_execute", "directory_list"]:
                    if tool in j:
                        console.print(f"[green]✓ Found direct tool format: {tool}[/green]")
                        return {
                            "type": "tool_call",
                            "name": tool,
                            "args": j[tool] if isinstance(j[tool], dict) else {"path": j[tool]}
                        }
                
            except json.JSONDecodeError as e:
                if obj_type == "tool_call":
                    console.print(f"[dim red]JSON parse error: {e} for line: {ln[:100]}...[/dim red]")
    
    # ========== PATTERN 2: Embedded JSON with Regex ==========
    patterns = [
        # Standard formats
        r'\{"type"\s*:\s*"tool_call"[^}]*\}',
        r'\{"tool"\s*:\s*"([^"]+)"[^}]*\}',
        r'\{"function"\s*:\s*"([^"]+)"[^}]*\}',
        r'\{"name"\s*:\s*"([^"]+)"[^}]*"parameters"\s*:\s*\{[^}]*\}\s*\}',
        # Markdown code blocks
        r'```json\s*(\{[^`]*\})\s*```',
        r'```\s*(\{[^`]*\})\s*```',
        # Natural language patterns
        r'(?:I\'ll|Let me|Going to|Will)\s+(\w+)\s+(?:the\s+)?file\s+"([^"]+)"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, raw, re.IGNORECASE | re.DOTALL)
        for match in matches:
            try:
                if isinstance(match, tuple):
                    # Natural language pattern
                    action, target = match
                    if action.lower() in ['read', 'open', 'check', 'examine']:
                        console.print(f"[green]✓ Found natural language: {action} {target}[/green]")
                        return {
                            "type": "tool_call",
                            "name": "file_read",
                            "args": {"path": target}
                        }
                    elif action.lower() in ['search', 'find', 'look']:
                        console.print(f"[green]✓ Found natural language: {action} {target}[/green]")
                        return {
                            "type": "tool_call",
                            "name": "file_search",
                            "args": {"pattern": target}
                        }
                else:
                    # JSON pattern
                    j = json.loads(match)
                    if "type" in j and j["type"] == "tool_call":
                        console.print(f"[green]✓ Found tool call via regex[/green]")
                        return j
            except:
                continue
    
    # ========== PATTERN 3: Fallback Detection ==========
    if obj_type == "tool_call":
        # Look for common tool request phrases
        tool_phrases = {
            "file_read": ["read the file", "open the file", "show the file", "display the file"],
            "file_search": ["search for", "find the file", "look for", "locate"],
            "file_write": ["write to", "create a file", "save to"],
            "bash_execute": ["run the command", "execute", "run bash"],
            "directory_list": ["list files", "show files", "ls", "dir"]
        }
        
        raw_lower = raw.lower()
        for tool_name, phrases in tool_phrases.items():
            for phrase in phrases:
                if phrase in raw_lower:
                    # Extract potential file name or command
                    file_pattern = r'["\']([^"\']+)["\']'
                    file_matches = re.findall(file_pattern, raw)
                    if file_matches:
                        console.print(f"[yellow]⚠ Detected '{phrase}' with target: {file_matches[0]}[/yellow]")
                        console.print(f"[yellow]Creating fallback tool call for {tool_name}[/yellow]")
                        return {
                            "type": "tool_call",
                            "name": tool_name,
                            "args": {"path": file_matches[0]} if "file" in tool_name else {"pattern": file_matches[0]}
                        }
    
    # No tool call found
    if obj_type == "tool_call":
        console.print(f"[red]✗ No tool call found in response[/red]")
        console.print(f"[dim]Response preview: {raw[:200]}...[/dim]")
    
    return None


"""
HOW TO IMPLEMENT THIS FIX:
==========================

1. REPLACE the existing _extract_one_line_json function in interactive.py
   with this enhanced version

2. ADD DEBUGGING to see what your model is actually outputting:
"""

# In interactive.py, after the model generates a response, add:
def debug_model_response(response: str):
    """Debug what the model actually generated"""
    console.print("[cyan]═══ Model Response ═══[/cyan]")
    console.print(response[:500])  # First 500 chars
    console.print("[cyan]═══════════════════════[/cyan]")
    
    # Check for JSON-like content
    if "{" in response:
        console.print("[yellow]Found JSON-like content:[/yellow]")
        for line in response.splitlines():
            if "{" in line:
                console.print(f"  {line[:100]}")
    
    # Try extraction
    tool_call = _extract_one_line_json_ENHANCED(response, "tool_call")
    if tool_call:
        console.print(f"[green]✅ Tool extracted: {tool_call}[/green]")
    else:
        console.print("[red]❌ No tool extracted[/red]")

"""
3. UPDATE YOUR SYSTEM PROMPT to be VERY explicit:
"""

ENHANCED_SYSTEM_PROMPT = """
When you need to use a tool, output ONLY this exact JSON format on a single line:
{"type":"tool_call","name":"TOOL_NAME","args":{"param":"value"}}

Examples:
- To read a file: {"type":"tool_call","name":"file_read","args":{"file_path":"readme.txt"}}
- To search: {"type":"tool_call","name":"file_search","args":{"pattern":"*.py","path":"."}}
- To execute bash: {"type":"tool_call","name":"bash_execute","args":{"command":"ls -la"}}

CRITICAL: Output the JSON on its own line with NO other text on that line.
"""

"""
WHY YOUR TOOLS AREN'T WORKING:
==============================

1. FORMAT MISMATCH: Your model is outputting tool calls in a format the parser
   doesn't recognize (maybe wrapped in markdown, or using different field names)

2. SILENT FAILURE: When parsing fails, it returns None without error messages,
   so you never know WHY it failed

3. STRICT PARSING: The current parser is too strict - it expects exact formats

This enhanced parser:
- Handles multiple formats
- Shows debug info when searching
- Falls back to natural language detection
- Tells you exactly what it found or why it failed

ABOUT MCP:
==========
MCP is great for letting EXTERNAL models (Claude, GPT-4) connect to your tools.
But it WON'T fix your internal Gemma model's tool parsing. You need both:

1. Fix internal parsing (this solution) -> Makes Gemma work with tools
2. Add MCP integration -> Lets external models use your tools

Test the enhanced parser first, THEN add MCP for external model support.
"""