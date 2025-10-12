import os
from datetime import datetime

DEBUG_MODE = True # Set to False to disable debug logging

LOG_DIR = '/home/commander/Desktop/Trainer/Data/DeBug'
LOG_FILE_PATH = None

def init_logger():
    """
    Initializes the logger.
    If GEMINI_LOG_FILE env var is set, it uses that file.
    Otherwise, it creates a new log file with a timestamp.
    """
    global LOG_FILE_PATH
    
    env_log_file = os.getenv("GEMINI_LOG_FILE")
    
    if env_log_file:
        LOG_FILE_PATH = env_log_file
        # Ensure directory exists if specified in env var
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    elif LOG_FILE_PATH is None: # Only create a new file if not already initialized
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        LOG_FILE_PATH = os.path.join(LOG_DIR, f"debug_log_{timestamp}.txt")
        log_message(f"--- Log initialized at {LOG_FILE_PATH} ---")

def get_log_file_path():
    """Returns the path to the current log file."""
    if LOG_FILE_PATH is None:
        init_logger()
    return LOG_FILE_PATH

def log_message(message):
    """Appends a message to the current log file."""
    if not DEBUG_MODE:
        return
    if LOG_FILE_PATH is None:
        init_logger()
    
    # Ensure message is a string
    if not isinstance(message, str):
        message = str(message)

    with open(LOG_FILE_PATH, 'a') as f:
        f.write(f"{message}\n")

# Initialize logger when module is first imported
init_logger()