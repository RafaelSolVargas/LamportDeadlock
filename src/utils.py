import time
import threading
import os

LOG_FILE = "/home/caio/8o-semestre-UFSC/INE5418-Comp-Distribuida/LamportDeadlock/logs.txt"

# Clear the log file at the start of execution
if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w") as log_file:
        log_file.write("")  # Clear the file

def log(message):
    """Log function to print messages with a timestamp and the current thread's name."""
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    formatted_message = f"[{timestamp}] [{threading.current_thread().name}] {message}"
    
    # Print to console
    print(formatted_message)    
    
    # Append to log file
    with open(LOG_FILE, "a") as log_file:
        log_file.write(formatted_message + "\n")