from typing import Dict, List, Optional
from pathlib import Path
import sys

# Ensure project root is in sys.path for cross-module imports
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from modules.brain import CLIWorkflow, ConfigManager, OllamaManager
    from modules.ag_importer import stream_tsv_file, filter_by_focus, parse_metadata, populate_ag_forge_data
    from modules.meta_learn_agriculture import KnowledgeForgeApp
except ImportError as e:
    print(f"FATAL ERROR: Could not import necessary modules in ag_onboarding.py: {e}", file=sys.stderr)
    sys.exit(1)

class OnboardingReviewWorkflow:
    """
    An interactive workflow to help a new user identify business opportunities
    by analyzing available data and scripts, then generating a prompt for an AI reviewer.
    """
    def __init__(self, config: ConfigManager, agent_mode: bool = False):
        self.config = config
        self.agent_mode = agent_mode
        self.python_master_path = Path(self.config.config["scripts"]["python_master_path"])
        self.trusted_merit_path = project_root / "modules" / "Imports" / "seed_pack"

    def run(self) -> str:
        """
        Executes the interactive review workflow.

        Returns:
            A detailed user request string to be passed to the Gemini reviewer.
        """
        if not self.agent_mode:
            print("\n" + "="*60)
            print("🔍 Interactive Onboarding Review")
            print("="*60)
            print("Let's identify potential business opportunities for your new project.")

        # 1. Analyze available resources
        script_capabilities = self._analyze_scripts()
        data_potentials = self._analyze_data()
        
        all_options = script_capabilities + data_potentials
        if not all_options:
            if not self.agent_mode:
                print("\n⚠️ No potential opportunities found in scripts or data.")
            return "User was prompted for onboarding, but no specific business opportunities could be auto-detected from the project's scripts or data imports."

        # 2. Get user's choice (or agent's automatic choice)
        if self.agent_mode:
            selected_focus, source = all_options[0] # Auto-select the first, most logical option
            print(f"🤖 Agent Mode: Auto-selected business focus: {selected_focus}")
        else:
            print("\nBased on an analysis of the system, here are some potential business focuses:")
            for i, (option, source) in enumerate(all_options, 1):
                print(f"  {i}. {option} (Source: {source})")
            
            while True:
                try:
                    choice_str = input(f"\nPlease select a focus area (1-{len(all_options)}): ")
                    choice_idx = int(choice_str) - 1
                    if 0 <= choice_idx < len(all_options):
                        selected_focus, source = all_options[choice_idx]
                        print(f"\n✅ You've selected: {selected_focus}")
                        break
                    else:
                        print("Invalid selection. Please try again.")
                except ValueError:
                    print("Please enter a number.")
                except (KeyboardInterrupt, EOFError):
                    print("\n\nAborted onboarding review.")
                    sys.exit(0)
        
        # 3. Generate a detailed request for the AI reviewer
        user_request = self._generate_reviewer_request(selected_focus, source, all_options)
        return user_request

    def _analyze_scripts(self) -> List[tuple[str, str]]:
        """Scans the Python-master directory for potential capabilities."""
        if not self.agent_mode:
            print("\nAnalyzing available scripts...")
        capabilities = []
        if self.python_master_path.exists():
            categories = self.config.discover_scripts_by_category(self.python_master_path)
            if "financial" in categories:
                capabilities.append(("Financial Analysis & Forecasting", "Financial Scripts"))
            if "statistics" in categories:
                 capabilities.append(("Statistical Modeling", "Statistics Scripts"))
            if "optimization" in categories:
                capabilities.append(("Resource Optimization", "Optimization Scripts"))
        return capabilities

    def _analyze_data(self) -> List[tuple[str, str]]:
        """Scans the trusted merit data for potential business areas."""
        if not self.agent_mode:
            print("Analyzing available agricultural data...")
        potentials = []
        vernacular_path = self.trusted_merit_path / "VernacularName.tsv"
        if vernacular_path.exists():
            potentials.append(("Dairy Farming", "Vernacular Name Data"))
            potentials.append(("Crop Cultivation", "Vernacular Name Data"))
            potentials.append(("Livestock Management", "Vernacular Name Data"))
        return potentials

    def _generate_reviewer_request(self, focus: str, source: str, all_options: list) -> str:
        """Creates the detailed request prompt for the AI reviewer."""
        request = f"""
This is a 'first session' onboarding review for a new user. The user is setting up the Agribusiness Knowledge Management System.

Through an interactive process, the user has selected a primary business focus.

**Selected Business Focus:**
- **Focus:** {focus}
- **Identified From:** {source}

**Other Potential Opportunities Considered:**
{chr(10).join(f"- {opt} (from {src})" for opt, src in all_options)}

**Your Task as the AI Reviewer:**

1.  **Acknowledge the User's Choice**: Start by confirming their selection of '{focus}'.
2.  **Generate a High-Level Project Plan**: Based on the chosen focus, create a simple, actionable 3-5 step plan. For example, if they chose 'Dairy Farming', the plan might be:
    *   Step 1: Onboard Core Data - Import all relevant data for 'Dairy' and 'Cattle'.
    *   Step 2: Establish Financial Baseline - Set up initial financial accounts and track startup costs.
    *   Step 3: Define Key Tasks - Create initial tasks for daily, weekly, and monthly dairy operations.
3.  **Provide the EXACT Next Command**: Your primary goal is to guide the user. Conclude your response by telling them the *exact* command to run next to officially start the project. This command MUST be:
    `python3 modules/brain.py --agribusiness`
4.  **Keep it Simple and Action-Oriented**: The user is new. Avoid jargon and focus on getting them started successfully.
"""
        return request.strip()

class AgWorkflow(CLIWorkflow):
    """
    An extended workflow for agribusiness project setup.
    """
    def __init__(self, config: ConfigManager, ollama: OllamaManager, app: KnowledgeForgeApp):
        super().__init__(config, ollama)
        self.business_focus = {}
        self.app: KnowledgeForgeApp = app
        self.trusted_merit_path = project_root / "modules" / "Imports" / "seed_pack"

    def guided_project_setup(self):
        """Overrides the base guided project setup for agribusiness specifics."""
        self.print_header("AGRIBUSINESS PROJECT SETUP WIZARD")

        project_config = {}
        step = 1

        while step <= 4:
            try:
                if step == 1:
                    # Project Name
                    name = self._prompt_for_input("Project name", required=True)
                    if name is None: continue
                    project_config['name'] = name
                    step += 1

                elif step == 2:
                    # Business Focus
                    focus = self._prompt_for_input("Primary business focus (e.g., Dairy, Wheat, Cattle)")
                    if focus is None: step -= 1; continue
                    project_config['focus'] = focus
                    step += 1
                
                elif step == 3:
                    # Initial Investment
                    investment = self._prompt_for_input("Initial investment amount (optional)")
                    if investment is None: step -= 1; continue
                    project_config['investment'] = investment
                    step += 1

                elif step == 4:
                    # Create Project and Process Data
                    print("\nCreating project and processing trusted data...")
                    self.process_trusted_data(project_config['focus'])
                    # Here you would also create the project structure like in the base class
                    print(f"\n✅ Agribusiness project '{project_config['name']}' with focus '{project_config['focus']}' created.")
                    return project_config

            except KeyboardInterrupt:
                print("\n\n👋 Setup cancelled by user.")
                sys.exit(0)
        return {}

    def process_trusted_data(self, focus: str):
        """Filters and imports data from the 'Trusted Merit' sources based on focus."""
        print(f"\nProcessing 'Trusted Merit' data for focus: {focus}")
        
        vernacular_path = self.trusted_merit_path / "VernacularName.tsv"
        if not vernacular_path.exists():
            print(f"⚠️ Warning: Trusted Merit data not found at {vernacular_path}")
            return

        # 1. Create Data Stream
        data_stream = stream_tsv_file(vernacular_path)
        
        # 2. Filter by Focus
        filtered_stream = filter_by_focus(data_stream, [focus])
        
        # 3. Populate Ag_Forge
        business_focus_dict = {
            "domain": focus,
            "keywords": [focus]
        }
        populate_ag_forge_data(self.app, filtered_stream, business_focus_dict)

    def _prompt_for_input(self, prompt: str, required: bool = False) -> Optional[str]:
        """Helper for getting user input with back/cancel support."""
        while True:
            response = input(f"{prompt} (or 'back', 'cancel'): ").strip()
            if response.lower() == 'cancel':
                raise KeyboardInterrupt()
            if response.lower() == 'back':
                return None
            if required and not response:
                print("❌ This field is required.")
                continue
            return response
