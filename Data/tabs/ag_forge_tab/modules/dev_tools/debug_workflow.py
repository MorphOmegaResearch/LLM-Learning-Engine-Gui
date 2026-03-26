#!/usr/bin/env python3
"""
Debug Review Workflow
---------------------
A workflow for performing targeted, AI-assisted debugging on a specific file.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is in sys.path for module imports
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from modules.dev_tools.context_aggregator import aggregate_context, create_ai_review_prompt
except ImportError:
    print("Error: Could not import context_aggregator.", file=sys.stderr)
    sys.exit(1)

class DebugReviewWorkflow:
    def __init__(self, target_file: str, agent_mode: bool = False):
        self.target_file = Path(target_file).resolve()
        self.agent_mode = agent_mode
        self.log_dir = project_root / "logs"

    def run(self) -> str:
        """
        Executes the debug review workflow.

        Returns:
            A detailed prompt for the AI reviewer.
        """
        if not self.target_file.exists():
            return f"Error: The target file for debugging does not exist: {self.target_file}"

        if not self.agent_mode:
            print("\n" + "="*60)
            print(f"🔍 Debug Review for: {self.target_file.name}")
            print("="*60)

        # 1. Scan for relevant errors in logs
        relevant_errors = self._scan_logs()
        if relevant_errors:
            print(f"Found {len(relevant_errors)} relevant error(s) in logs.")

        # 2. Aggregate deep context (with full analysis enabled)
        print("Aggregating deep context and running full code analysis...")
        user_request = self._generate_debug_request(relevant_errors)
        
        context = aggregate_context(
            target_file_path_str=str(self.target_file),
            user_request=user_request,
            project_dir=project_root,
            enable_analysis=True,
            target_files=[str(self.target_file)] # Pass the specific file to the analyzer
        )

        # 3. Create the final prompt for the reviewer
        ai_prompt = create_ai_review_prompt(context)
        return ai_prompt

    def _scan_logs(self) -> List[str]:
        """Scans log files for errors related to the target file."""
        errors = []
        target_filename = self.target_file.name
        
        if not self.log_dir.exists():
            return errors

        for log_file in self.log_dir.glob("*.log"):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Simple check: does the line contain "error" and the filename?
                        if "error" in line.lower() and target_filename in line:
                            errors.append(line.strip())
            except Exception:
                continue # Ignore files we can't read
        
        return errors

    def _generate_debug_request(self, errors: List[str]) -> str:
        """Generates the user_request portion of the prompt for the AI."""
        request = f"""
This is a 'debug review' for the file `{self.target_file.name}`. My goal is to find and fix a bug.

**Analysis Task:**
1.  **Examine the Code:** Analyze the full content of `{self.target_file.name}` provided in the context.
2.  **Review the Static Analysis Report:** Pay close attention to any errors or warnings found by the `tkinter_analyzer`.
3.  **Consider Logged Errors:** I have found the following errors in the system logs that may be related to this file. Use them as a starting point for your investigation:
"""
        if errors:
            for error in errors:
                request += f"- `{error}`\n"
        else:
            request += "- No specific errors were found in the logs, but please perform a general bug hunt based on the static analysis.\n"

        request += """
**Your Goal:**
Your primary objective is to **provide a concrete code fix**.

- **Propose a fix as a `replace` tool call.** The tool call must include enough surrounding context to be unambiguous.
- **Explain your reasoning** for the fix in your high-level plan.
- If you cannot find a definitive bug, explain what additional information you would need.
"""
        return request.strip()
