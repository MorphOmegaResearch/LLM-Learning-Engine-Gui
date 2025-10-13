# Data/logger_util.py
def log_message(msg: str, level: str = "info"):
    try:
        print(f"[{level.upper()}] {msg}")
    except Exception:
        # absolute last-resort no-op
        pass

def get_log_file_path():
    # This is a dummy function to avoid import errors.
    # The actual log file path is handled by the logger setup in the main script.
    import os
    return os.path.join(os.getcwd(), "DeBug", "trainer.log")