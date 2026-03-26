import json
import os
from providers import get_provider
from utils import read_context_from_source

class WorkflowEngine:
    def __init__(self, args):
        self.args = args
        self.recipe = self.load_recipe()
        self.rolling_context = {} # To store outputs of steps

    def load_recipe(self):
        """Loads the workflow recipe JSON file."""
        try:
            with open(self.args.workflow, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Workflow recipe not found at {self.args.workflow}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {self.args.workflow}")
            return None

    def run(self):
        """Executes the full workflow defined in the recipe."""
        if not self.recipe:
            return

        print(f"--- Running Workflow: {self.recipe.get('name', 'Untitled Workflow')} ---")

        for i, step in enumerate(self.recipe.get('steps', [])):
            step_name = step.get('name', f"Step {i+1}")
            print(f"\n--- Executing Step: {step_name} ---")

            # 1. Get the AI provider for this step
            provider_name = step.get('provider', 'ollama')
            provider = get_provider(provider_name)
            if not provider:
                print(f"Error: Provider '{provider_name}' not found. Skipping step.")
                continue

            # 2. Assemble the prompt and context
            prompt = self.assemble_prompt(step)
            
            # 3. Execute the AI call
            try:
                ai_output = provider.execute(prompt, self.args)
                print(f"Step '{step_name}' completed successfully.")
            except Exception as e:
                print(f"Error during AI execution for step '{step_name}': {e}")
                continue # Move to next step

            # 4. Handle the output
            self.handle_output(ai_output, step)
        
        print("\n--- Workflow Finished ---")

    def assemble_prompt(self, step):
        """Assembles the full prompt from various sources defined in the step."""
        prompt_parts = []

        # Add the main instruction/prompt for the step
        if 'prompt' in step:
            prompt_parts.append(step['prompt'])

        # Process inputs
        for input_source in step.get('inputs', []):
            source_type = input_source.get('type')
            
            if source_type == 'literal':
                prompt_parts.append(f"\n--- {input_source.get('name', 'Context')} ---\n{input_source.get('content', '')}")

            elif source_type == 'file':
                content, error = read_context_from_source(file_path=input_source.get('path'))
                if error:
                    print(error)
                else:
                    prompt_parts.append(f"\n--- Context from file: {input_source.get('path')} ---\n{content}")

            elif source_type == 'clipboard':
                content, error = read_context_from_source(use_clipboard=True)
                if error:
                    print(error)
                else:
                    prompt_parts.append(f"\n--- Context from clipboard ---\n{content}")

            elif source_type == 'step_output':
                # Use the output from a previous step
                source_step_name = input_source.get('source_step')
                if source_step_name in self.rolling_context:
                    prompt_parts.append(f"\n--- Context from previous step: {source_step_name} ---\n{self.rolling_context[source_step_name]}")
                else:
                    print(f"Warning: Could not find output from step '{source_step_name}'.")

        return "\n".join(prompt_parts)

    def handle_output(self, ai_output, step):
        """Handles the output of an AI call, saving it to a file or storing it in context."""
        step_name = step.get('name')
        
        # Store in rolling context if the step has a name
        if step_name:
            self.rolling_context[step_name] = ai_output

        # Save to file if specified
        output_def = step.get('output')
        if output_def and output_def.get('type') == 'file':
            output_path = output_def.get('path')
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(ai_output)
                print(f"Output saved to: {output_path}")
            except Exception as e:
                print(f"Error saving output file for step '{step_name}': {e}")
