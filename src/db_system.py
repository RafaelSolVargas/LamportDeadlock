import threading
import time
import random
import config
from src.utils import log
from src.snapshot import DeadlockDetector

class LockManager:
    def __init__(self, tables, shutdown_event):
        self.tables = {t.name: t for t in tables}
        self.connections = {}
        self.snapshot_lock = threading.Lock()
        self.shutdown_event = shutdown_event
        self.deadlock_detector = DeadlockDetector(self.shutdown_event)

    def register_connection(self, connection_thread):
        self.connections[connection_thread.name] = connection_thread

    def acquire_lock(self, connection, table_name):
        table = self.tables.get(table_name)
        if not table: return
        log(f"Attempting to acquire WRITE lock on '{table.name}'...")
        connection.waiting_for_table = table
        
        table.write_lock.acquire()
        
        if self.shutdown_event.is_set():
            table.write_lock.release()
            return

        log(f"ACQUIRED write lock on '{table.name}'.")
        connection.locked_tables.add(table)
        table.lock_owner = connection
        connection.waiting_for_table = None

    def release_lock(self, connection, table_name):
        table = self.tables.get(table_name)
        if not table or table not in connection.locked_tables: return
        
        if table.lock_owner == connection:
            connection.locked_tables.remove(table)
            table.lock_owner = None
            try:
                table.write_lock.release()
                log(f"RELEASED write lock on '{table.name}'.")
            except threading.ThreadError:
                log(f"Could not release lock on '{table.name}', already unlocked.")
        else:
            log(f"WARNING: '{connection.name}' tried to release lock on '{table.name}' which is not held.")

    def take_snapshot(self):
        if self.shutdown_event.is_set(): return
        log("="*15 + " INITIATING GLOBAL SNAPSHOT " + "="*15)
        with self.snapshot_lock:
            snapshot_data = {}
            for thread_id, conn_obj in self.connections.items():
                snapshot_data[thread_id] = {
                    'locked_tables': set(conn_obj.locked_tables),
                    'waiting_for_table': conn_obj.waiting_for_table.name if conn_obj.waiting_for_table else None
                }
        log("="*15 + " SNAPSHOT COMPLETE " + "="*19)
        self.deadlock_detector.analyze(snapshot_data)


class ClientConnection(threading.Thread):
    def __init__(self, name, lock_manager, all_tables, shutdown_event):
        super().__init__(name=name, daemon=True)
        self.lock_manager = lock_manager
        self.all_tables = all_tables
        self.shutdown_event = shutdown_event
        self.locked_tables = set()
        self.waiting_for_table = None

    def run(self):
        log("Connection established, starting workload.")
        while not self.shutdown_event.is_set():
            self.__perform_operation()

    def __perform_operation(self):
        if self.shutdown_event.is_set(): return

        if random.random() > config.WRITE_PROBABILITY:
            self.__perform_read()
        else:
            self.__perform_write_transaction()

        if not self.shutdown_event.is_set():
            time.sleep(random.uniform(*config.CLIENT_COOLDOWN_RANGE))

    def __perform_read(self):
        if self.shutdown_event.is_set(): return
        table_to_read = random.choice(self.all_tables)
        read_duration = random.uniform(*config.READ_DURATION_RANGE)
        log(f"Performing READ on '{table_to_read.name}' for {read_duration:.2f}s.")
        time.sleep(read_duration)

    def __perform_write_transaction(self):
        if self.shutdown_event.is_set(): return
        num_tables = 2 if random.random() < config.MULTI_TABLE_TX_PROBABILITY else 1
        if num_tables > len(self.all_tables) or num_tables == 0: return

        tables_to_lock = random.sample(self.all_tables, num_tables)
        table_names = [t.name for t in tables_to_lock]
        log(f"Starting WRITE transaction on table(s): {table_names}")

        acquired_locks = []
        try:
            for i, table in enumerate(tables_to_lock):
                if self.shutdown_event.is_set(): break
                self.lock_manager.acquire_lock(self, table.name)
                if self.shutdown_event.is_set(): break
                acquired_locks.append(table)
                
                if i == 0 and len(tables_to_lock) > 1:
                    time.sleep(random.uniform(*config.DEADLOCK_WINDOW_RANGE))
            
            if not self.shutdown_event.is_set() and len(acquired_locks) == num_tables:
                write_duration = random.uniform(*config.WRITE_DURATION_RANGE)
                log(f"All locks acquired. Performing WRITE on {table_names} for {write_duration:.2f}s.")
                time.sleep(write_duration)
        finally:
            log(f"Finishing transaction, releasing locks for {table_names}.")
            for table in reversed(acquired_locks):
                self.lock_manager.release_lock(self, table.name)
