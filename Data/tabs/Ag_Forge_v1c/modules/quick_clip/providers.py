import requests
import json
import subprocess
from pathlib import Path

class BaseProvider:
    def execute(self, prompt, args):
        raise NotImplementedError

class OllamaProvider(BaseProvider):
    def execute(self, prompt, args):
        """Executes a prompt using the Ollama provider."""
        model = getattr(args, 'model', 'llama2')
        url = getattr(args, 'ollama_url', 'http://localhost:11434/api/generate')
        
        print(f"Using Ollama provider (model: {model})...")
        try:
            payload = {
                "model": model, 
                "prompt": prompt,
                "stream": False
            }
            # Add GPU preset logic if available in args
            num_gpu = getattr(args, 'num_gpu', None)
            if num_gpu is not None:
                payload["options"] = {"num_gpu": int(num_gpu)}

            response = requests.post(url, json=payload, timeout=120)
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
        Executes a prompt using the Gemini provider.
        Supports Mock mode (agent_mode), external TUI, and direct API calls.
        """
        # Try to get API key from args, then from config.ini
        api_key = getattr(args, 'gemini_api_key', '')
        if not api_key:
            try:
                from modules.quick_clip.config import ConfigManager
                cfg = ConfigManager()
                api_key = cfg.get('Endpoints', 'gemini_api_key', '')
            except:
                pass
        
        model_name = getattr(args, 'model', 'gemini-1.5-flash')
        if not model_name or model_name == 'llama2': # Fallback if brain.py default leaks in
            model_name = 'gemini-1.5-flash'
        
        def has_net():
            import socket
            try:
                socket.setdefaulttimeout(2)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
                return True
            except:
                return False

        # 1. Agent Mode (Closing the Loop)
        if args and getattr(args, 'agent_mode', False):
            # If we have an API Key AND Internet, do a LIVE call
            if api_key and has_net():
                print(f"🤖 Agent Mode (LIVE): Calling Gemini API (model: {model_name})...")
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    headers = {'Content-Type': 'application/json'}
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    response = requests.post(url, headers=headers, json=payload, timeout=60)
                    response.raise_for_status()
                    result = response.json()
                    ai_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    return f"Gemini review completed successfully. Reviewer Output:\n---\n{ai_text}"
                except Exception as e:
                    print(f"⚠️ Live Gemini call failed ({e}). Falling back to Mock.")
            
            # Fallback to Mock
            print("🤖 Agent Mode (MOCK): Executing Mock Reviewer...")
            temp_file_path = "/tmp/gemini_review_context.txt"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            mock_reviewer_path = Path(__file__).parent.parent / "dev_tools" / "mock_reviewer.py"
            
            command = f"python3 {mock_reviewer_path} {temp_file_path}"
            
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode == 0:
                    return f"Gemini review completed successfully. Reviewer Output:\n---\n{result.stdout}"
                else:
                    return f"Error during Mock Reviewer execution. Stderr:\n---\n{result.stderr}"
            except Exception as e:
                return f"An exception occurred during agent-mode execution: {e}"

        # 2. Live API Call (if API Key is provided and internet is available)
        elif api_key and has_net():
            print(f"Using Gemini Live API (model: {model_name})...")
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                headers = {'Content-Type': 'application/json'}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                response = requests.post(url, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                result = response.json()
                # Extract text from Gemini response structure
                try:
                    return result['candidates'][0]['content']['parts'][0]['text'].strip()
                except (KeyError, IndexError):
                    return "Error: Unexpected response structure from Gemini API."
            except Exception as e:
                print(f"Error calling Gemini API: {e}")
                raise

        # 3. Default behavior for interactive user (External TUI)
        else:
            temp_file_path = "/tmp/gemini_review_context.txt"
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            print("Using Gemini provider (spawning external TUI)...")
            command_for_user = f"gemini-cli --prompt-file {temp_file_path}"
            print(f"Executing command: {command_for_user}")
            print("Please complete the review in the external terminal. The application will wait.")
            return f"Gemini review context has been prepared. Please run the command above."


_providers = {
    "ollama": OllamaProvider(),
    "gemini": GeminiProvider()
}

def get_provider(name):
    return _providers.get(name.lower())
