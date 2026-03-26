#!/usr/bin/env python3
"""
Mock AI Reviewer
----------------
Simulates the Gemini AI's role in the onboarding conversation for testing purposes.
It reads the context/prompt file, analyzes the conversation history, and generates
the next logical response in the script.
"""

import sys
import re
import json

def main():
    if len(sys.argv) < 2:
        print("Error: No prompt file provided.")
        sys.exit(1)

    prompt_file = sys.argv[1]
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        sys.exit(1)

    # Extract explicit onboarding state from the prompt
    onboarding_state = {
        "project_name": None, 
        "business_focus": None, 
        "business_strategy": None,
        "initial_investment": None
    }
    state_block = ""
    if "--- CURRENT ONBOARDING STATE ---" in content:
        start_state = content.find("--- CURRENT ONBOARDING STATE ---") + len("--- CURRENT ONBOARDING STATE ---")
        end_state = content.find("--- YOUR TASK ---", start_state)
        if end_state > start_state:
            state_block = content[start_state:end_state].strip()
    
    for line in state_block.split('\n'):
        if "Project Name:" in line:
            name = line.split(":")[1].strip()
            if name != "Not Provided": onboarding_state["project_name"] = name
        elif "Business Focus:" in line:
            focus = line.split(":")[1].strip()
            if focus != "Not Provided": onboarding_state["business_focus"] = focus
        elif "Business Strategy:" in line:
            strategy = line.split(":")[1].strip()
            if strategy != "Not Provided": onboarding_state["business_strategy"] = strategy
        elif "Initial Investment:" in line:
            investment = line.split(":")[1].strip()
            if investment != "Not Provided": onboarding_state["initial_investment"] = investment

    response = ""

    # Determine response based on the explicit onboarding_state
    if not onboarding_state["project_name"]:
        response = "Welcome! What is the name of your new Agribusiness project?"
    elif not onboarding_state["business_focus"]:
        response = f"Excellent! What is the primary business focus for {onboarding_state['project_name']}? (e.g., Vertical Farming, Dairy, Viticulture)"
    elif not onboarding_state["business_strategy"]:
        response = f"Great choice! Now, what is your **business strategy**? (e.g., Direct-to-consumer app, local market supply, wholesale export)"
    elif not onboarding_state["initial_investment"]:
        response = f"Understood. Finally, what is the initial investment for this {onboarding_state['business_focus']} venture?"
    else:
        # The Final Architect Plan
        response = f"""Perfect! I have designed your project: **{onboarding_state['project_name']}**.
        
**Architecture Overview:**
- **Niche**: {onboarding_state['business_focus']}
- **Strategy**: {onboarding_state['business_strategy']}
- **Capital**: {onboarding_state['initial_investment']}

**Recommended Tech Patchwork (from Python-master):**
1. `modules/Python-master/financial/financial_analysis.py`: To track your {onboarding_state['initial_investment']} ROI.
2. `modules/Python-master/data_structures/tree/avl_tree.py`: For managing complex crop-cycle data.

I have queued these scripts in your Planner. Run the following to finalize:
`python3 modules/brain.py --agribusiness`

[[PLANNER_TASKS: financial/financial_analysis.py, data_structures/tree/avl_tree.py]]"""

    print(response)

if __name__ == "__main__":
    main()
