import threading
import time
import sys
import config
from src.utils import log
from src.db_resources import Table
from src.db_system import LockManager, ClientConnection
from src.snapshot import Snapshotter

def main():
    """Main function to set up and run the DBMS deadlock simulation."""
    log("Starting Database Deadlock Detection Simulation.")
    shutdown_event = threading.Event()

    tables = [Table(f"tbl_{i+1:02d}") for i in range(config.NUM_TABLES)]
    log(f"Database tables available: {[t.name for t in tables]}")
    
    # Create the central Lock Manager
    lock_manager = LockManager(tables, shutdown_event)
    
    # Create Client Connections (threads)
    log(f"Opening {config.NUM_CLIENTS} client connections...")
    client_threads = []
    for i in range(config.NUM_CLIENTS):
        client_name = f"Client-{i+1}"
        client_thread = ClientConnection(client_name, lock_manager, tables, shutdown_event)
        client_threads.append(client_thread)
        lock_manager.register_connection(client_thread)
    
    # Create the Snapshotter thread
    snapshotter = Snapshotter(lock_manager, config.SNAPSHOT_INTERVAL, shutdown_event)

    # Start all threads
    log("Starting all client connections...")
    for thread in client_threads:
        time.sleep(0.3)
        thread.start()
    snapshotter.start()

    try:
        while not shutdown_event.is_set():
            time.sleep(0.5)
        log("Shutdown initiated. MainThread is exiting.")
    except KeyboardInterrupt:
        log("Ctrl+C received! Initiating shutdown...")
        shutdown_event.set()
        log("MainThread is exiting.")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
