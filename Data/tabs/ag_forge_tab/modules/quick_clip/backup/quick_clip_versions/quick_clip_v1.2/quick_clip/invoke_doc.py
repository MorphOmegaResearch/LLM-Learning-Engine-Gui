#!/usr/bin/env python3
import subprocess
import sys
import os

try:
    from ollama import Client
    try:
        # Prefer top-level list API when available
        from ollama import list as ollama_list, ListResponse
    except Exception:
        ollama_list = None
        ListResponse = None
except ImportError:
    print("Please install the ollama package (pip install ollama).", file=sys.stderr)
    Client = None
    ollama_list = None
    ListResponse = None

def get_available_models(client):
    """Returns a list of available Ollama model names."""
    models = []
    # 1) Try official top-level API first
    if ollama_list is not None:
        try:
            resp = ollama_list()
            # Newer package: ListResponse with .models attribute
            if hasattr(resp, 'models'):
                for m in getattr(resp, 'models') or []:
                    # objects have .model (name)
                    name = getattr(m, 'model', None) or getattr(m, 'name', None)
                    if isinstance(name, str):
                        models.append(name)
            # Fallback: dict with 'models'
            elif isinstance(resp, dict) and 'models' in resp:
                for m in resp.get('models') or []:
                    if isinstance(m, dict):
                        name = m.get('name') or m.get('model')
                    else:
                        name = str(m)
                    if isinstance(name, str):
                        models.append(name)
        except Exception:
            # ignore and fallback to client
            pass
    # 2) Fallback to client.list() if needed
    if not models and client and hasattr(client, 'list'):
        try:
            resp = client.list()
            items = []
            if hasattr(resp, 'models'):
                items = resp.models  # type: ignore[attr-defined]
            elif isinstance(resp, dict) and 'models' in resp:
                items = resp['models'] or []
            elif isinstance(resp, list):
                items = resp
            for m in items:
                name = None
                if isinstance(m, dict):
                    name = m.get('name') or m.get('model')
                else:
                    name = getattr(m, 'model', None) or getattr(m, 'name', None) or (str(m) if m else None)
                if isinstance(name, str):
                    models.append(name)
        except Exception:
            pass
    return sorted(set(models))


def generate_document(model: str, user_prompt: str, output_format: str = None) -> str:
    """
    Generates a document using a specified Ollama model and prompt.

    Args:
        model: The name of the Ollama model to use.
        user_prompt: The prompt to send to the model.
        output_format: If specified (e.g., 'md', 'txt', 'py'), saves the output
                       to a file named 'output.{format}'.

    Returns:
        The generated text content from the model.
    """
    if not Client:
        raise ImportError("Ollama client is not available.")

    client = Client()
    print("\nGenerating...", end='', flush=True)
    
    try:
        # Using ollama.generate for a single completion is more direct
        response = client.generate(
            model=model,
            prompt=user_prompt
        )
        
        # The response structure for generate is different from chat
        generated_text = response.get('response', '').strip()
        
        print("Done.")
        print("\n\n" + "="*50)
        print(generated_text)
        print("="*50)

        if output_format and output_format in ("md", "txt", "py"):
            filename = f"output.{output_format}"
            # Explicitly use utf-8 encoding
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(generated_text)
            print(f"\nSaved to {filename}")
        
        return generated_text

    except Exception as e:
        error_message = f"\nError during generation: {e}"
        print(error_message, file=sys.stderr)
        return error_message


def main():
    """Main CLI entry point."""
    if not Client:
        sys.exit(1)

    # 1. Check Ollama installation and get models
    client = Client()
    try:
        models = get_available_models(client)
        if not models:
             # Fallback to subprocess if client API fails for some reason
            models_output = subprocess.check_output(["ollama", "list"], stderr=subprocess.STDOUT, text=True)
            models = [line.split()[0] for line in models_output.strip().split('\n')[1:] if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\nInstall Ollama first: https://ollama.com/download", file=sys.stderr)
        sys.exit(1)

    if not models:
        print("\nNo models found. Pull one with: ollama pull <name>", file=sys.stderr)
        sys.exit(1)

    # 2. Model selection UI
    print("\nAvailable models:")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model}")
    
    try:
        choice = input(f"\nSelect model (1-{len(models)}): ").strip()
        model = models[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection", file=sys.stderr)
        sys.exit(1)

    # 3. Get prompt input
    user_prompt = input("\nEnter prompt: ").strip()
    
    # 4. Final confirmation
    print(f"\nModel: {model}")
    print(f"Prompt: {user_prompt}")
    confirm = input("\nGenerate? [Y/n]: ").strip().lower()
    if confirm not in ("y", ""):
        print("Aborted")
        sys.exit(0)

    # 5. Execute generation using the refactored function
    output_format = input("\nSave as [md/txt/py] (skip to print only): ").strip().lower()
    generate_document(model, user_prompt, output_format)


if __name__ == "__main__":
    main()