import time
import threading

def log(message):
    """Log function to print messages with a timestamp and the current thread's name."""
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    print(f"[{timestamp}] [{threading.current_thread().name}] {message}")
