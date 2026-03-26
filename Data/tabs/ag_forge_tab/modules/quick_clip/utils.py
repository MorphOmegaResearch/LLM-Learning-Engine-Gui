import pyperclip

def read_context_from_source(file_path=None, use_clipboard=False):
    """Reads context from a given file path or the clipboard."""
    context = ""
    error = None
    if use_clipboard:
        try:
            context = pyperclip.paste()
        except Exception as e:
            error = f"Error: Could not read from clipboard. {e}"
    elif file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                context = f.read()
        except FileNotFoundError:
            error = f"Error: Context file not found at {file_path}"
        except Exception as e:
            error = f"Error reading context file: {e}"
    return context, error
