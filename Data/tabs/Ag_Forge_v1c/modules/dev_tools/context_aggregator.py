#!/usr/bin/env python3
"""
Context Aggregator for AI-Assisted Code Review and Refinement
--------------------------------------------------------------
This script gathers various forms of context (code analysis, file content, user requests)
and aggregates them into a comprehensive prompt for an external AI model (like Gemini).
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import asdict

# Ensure project root is in sys.path for module imports
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from modules.dev_tools.tkinter_analyzer import TkinterAnalyzer
except ImportError as e:
    TkinterAnalyzer = None

TEMP_CONTEXT_FILE = Path("/tmp/gemini_review_context.txt")

def aggregate_context(
    target_file_path_str: str,
    user_request: str,
    project_dir: Path,
    enable_analysis: bool = True,
    target_files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Aggregates code analysis, file content, and user request into a single context dictionary.
    """
    target_file = Path(target_file_path_str).resolve()
    
    # 1. Read Target File
    target_file_content = ""
    if target_file.exists():
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                target_file_content = f.read()
        except Exception as e:
            target_file_content = f"Error reading file: {e}"

    # 2. Code Analysis
    analysis_results_dict = {"status": "skipped"}
    if enable_analysis and TkinterAnalyzer:
        analyzer = TkinterAnalyzer()
        results = analyzer.select_project(str(project_dir), target_files=target_files)
        
        target_file_issues = [asdict(issue) for issue in results.issues if Path(issue.file).resolve() == target_file.resolve()]
        target_file_tk_issues = [asdict(issue) for issue in results.tk_specific_issues if Path(issue.file).resolve() == target_file.resolve()]

        analysis_results_dict = {
            "summary": results.stats,
            "project_issues_count": len(results.issues) + len(results.tk_specific_issues),
            "target_file_issues": target_file_issues,
            "target_file_tk_specific_issues": target_file_tk_issues
        }

    # 3. Script Discovery (Python-master)
    python_master_path = project_dir / "modules" / "Python-master"
    scripts_context = {}
    if python_master_path.exists():
        for category_dir in python_master_path.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                scripts = [f.name for f in category_dir.glob("*.py")]
                if scripts:
                    scripts_context[category_dir.name] = scripts
    
    return {
        "timestamp": datetime.now().isoformat(),
        "user_request": user_request,
        "target_file_path": target_file_path_str,
        "target_file_content": target_file_content,
        "code_analysis": analysis_results_dict,
        "available_scripts": scripts_context
    }

def create_ai_review_prompt(
    context: Dict[str, Any],
    known_project_name: Optional[str] = None,
    known_business_focus: Optional[str] = None,
    known_initial_investment: Optional[str] = None,
    known_business_strategy: Optional[str] = None
) -> str:
    """
    Formats the aggregated context into a comprehensive prompt for the AI model.
    Generates a single, explicit instruction based on the current onboarding state.
    """
    # Build the single, explicit instruction based on the current state
    instruction_message = ""
    if known_project_name is None:
        instruction_message = "Welcome to the Agribusiness Architect. To get started, what is the name of your project?"
    elif known_business_focus is None:
        instruction_message = f"Okay, \'{known_project_name}\' is a great start! What will be the primary business focus of this project? (e.g., vertical farming, viticulture)"
    elif known_business_strategy is None:
        instruction_message = f"Got it. Focusing on \'{known_business_focus}\'. What is your business strategy? (e.g., direct-to-consumer, local market supply, wholesale export)"
    elif known_initial_investment is None:
        instruction_message = f"Understood. What is the initial investment for this \'{known_business_focus}\' venture? (Enter 0 if none)"
    else:
        # All info provided, generate final recommendation and task list
        instruction_message = f"""Perfect! I have designed your project: **{known_project_name}**.
        
**Architecture Overview:**
- **Niche**: {known_business_focus}
- **Strategy**: {known_business_strategy}
- **Capital**: {known_initial_investment}

**Recommended Tech Patchwork (from Python-master):**
1. `modules/Python-master/financial/financial_analysis.py`: To track your {known_initial_investment} ROI.
2. `modules/Python-master/data_structures/tree/avl_tree.py`: For managing complex crop-cycle data.

I have queued these scripts in your Planner. Run the following to finalize:
`python3 modules/brain.py --agribusiness`

[[PLANNER_TASKS: financial/financial_analysis.py, data_structures/tree/avl_tree.py]]"""

    prompt = f"""You are an expert Agribusiness Architect. 
Your goal is to help the user setup a project AND select the right technical tools from the codebase.

--- AVAILABLE SCRIPTS (Knowledge Base) ---
{json.dumps(context.get('available_scripts', {}), indent=2)}

--- ARCHITECT INSTRUCTION (RESPOND ONLY WITH THIS) ---
{instruction_message}

IMPORTANT: Respond ONLY with the message provided in 'ARCHITECT INSTRUCTION'. Do NOT add anything else.
"""
    return prompt

def main():
    parser = argparse.ArgumentParser(description="Aggregates context for AI-assisted code review.")
    parser.add_argument("--file", type=str, required=True, help="Path to the target file.")
    parser.add_argument("--request", type=str, required=True, help="User's request.")
    parser.add_argument("--no-analysis", action="store_true", help="Skip static analysis.")
    args = parser.parse_args()

    context = aggregate_context(
        target_file_path_str=args.file,
        user_request=args.request,
        project_dir=project_root,
        enable_analysis=not args.no_analysis
    )

    ai_prompt = create_ai_review_prompt(context)
    
    try:
        with open(TEMP_CONTEXT_FILE, 'w', encoding='utf-8') as f:
            f.write(ai_prompt)
        print(f"Context saved to {TEMP_CONTEXT_FILE}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()