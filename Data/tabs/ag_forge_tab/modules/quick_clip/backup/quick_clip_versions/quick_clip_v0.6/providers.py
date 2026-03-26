import requests
import json
import subprocess

class BaseProvider:
    def execute(self, prompt, args):
        raise NotImplementedError

class OllamaProvider(BaseProvider):
    def execute(self, prompt, args):
        """Executes a prompt using the Ollama provider."""
        print("Using Ollama provider...")
        try:
            # TODO: Get model and URL from config/args
            payload = {
                "model": "llama2", 
                "prompt": prompt,
                "stream": False
            }
            # TODO: Add GPU preset logic
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '').strip()

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Ollama: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred with Ollama: {e}")
            raise

class GeminiProvider(BaseProvider):
    def execute(self, prompt, args):
        """
        Executes a prompt by spawning an external TUI for Gemini review.
        This is a bridge, not a direct API call.
        """
        print("Using Gemini provider (spawning external TUI)...")
        try:
            # 1. Save the comprehensive prompt to a temporary file
            temp_file_path = "/tmp/gemini_review_context.txt"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            # 2. Construct the command to launch the user's TUI
            # This is an assumption and may need to be configured by the user
            command = f"gemini-cli --prompt-file {temp_file_path}"
            print(f"Executing command: {command}")
            print("Please complete the review in the external terminal. The application will wait.")

            # 3. Execute the command and wait for it to complete
            # This will block, which is the desired behavior for a review step.
            process = subprocess.run(command, shell=True)

            if process.returncode != 0:
                print(f"Warning: The external review process exited with code {process.returncode}.")

            # 4. For this workflow, we don't capture stdout. The review happens externally.
            # We return a confirmation message.
            return f"Gemini review process completed for prompt file: {temp_file_path}"

        except Exception as e:
            print(f"An error occurred while spawning the Gemini TUI: {e}")
            raise

_providers = {
    "ollama": OllamaProvider(),
    "gemini": GeminiProvider()
}

def get_provider(name):
    return _providers.get(name.lower())
