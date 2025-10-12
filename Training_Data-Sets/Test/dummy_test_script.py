import time
import sys

# Add Data directory to path to find logger_util
sys.path.insert(0, '/home/commander/Desktop/Trainer/Data')
from logger_util import log_message

log_message("DUMMY_TEST: Dummy script started.")
print("="*50)
print("--- DUMMY TEST SCRIPT RUNNING ---")
print("This script will run for 10 seconds.")
log_message("DUMMY_TEST: Sleeping for 10 seconds...")

try:
    for i in range(10):
        print(f"Dummy script progress: {i+1}/10 seconds...")
        time.sleep(1)
except KeyboardInterrupt:
    print("Dummy script interrupted.")
    log_message("DUMMY_TEST: Dummy script interrupted by user.")

print("--- DUMMY TEST SCRIPT FINISHED ---")
print("="*50)
log_message("DUMMY_TEST: Dummy script finished.")
