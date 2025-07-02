import threading
import time
import random
import logging
from collections import defaultdict
import queue


# --- Enhanced Logging Setup ---
class ColoredFormatter(logging.Formatter):
    """A custom formatter to add colors to log messages."""

    COLORS = {
        "DEBUG": "\033[94m",  # Blue
        "INFO": "\033[92m",  # Green
        "WARNING": "\033[93m",  # Yellow
        "ERROR": "\033[91m",  # Red
        "CRITICAL": "\033[91m",  # Red
        "RESET": "\033[0m",  # Reset
    }
    THREAD_COLORS = [
        "\033[96m",  # Cyan
        "\033[95m",  # Magenta
        "\033[94m",  # Blue
        "\033[93m",  # Yellow
        "\033[92m",  # Green
        "\033[91m",  # Red
    ]

    def __init__(self, fmt):
        super().__init__(fmt)
        self.thread_color_map = {}

    def format(self, record):
        thread_name = record.threadName
        if thread_name not in self.thread_color_map:
            color_index = len(self.thread_color_map) % len(self.THREAD_COLORS)
            self.thread_color_map[thread_name] = self.THREAD_COLORS[color_index]

        thread_color = self.thread_color_map[thread_name]
        record.threadName = f"{thread_color}{thread_name}{self.COLORS['RESET']}"

        log_message = super().format(record)
        return f"{self.COLORS.get(record.levelname, self.COLORS['RESET'])}{log_message}{self.COLORS['RESET']}"


# Configure logging with the custom formatter
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter("%(asctime)s - %(threadName)s - %(message)s"))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers = [handler]


# --- Simulation Classes ---
class Table:
    """Represents a table in the database that can be locked by a user."""

    def __init__(self, table_id):
        self.id = table_id
        self.lock = threading.Lock()
        self.locked_by = None

    def __str__(self):
        return f"Table-{self.id}"


class User(threading.Thread):
    """Represents a user who can perform read/write operations on tables."""

    def __init__(self, user_id, tables, all_users):
        super().__init__(name=f"User-{user_id}")
        self.id = user_id
        self.tables = tables
        self.all_users = all_users
        self.held_locks = []
        self.waiting_for = None
        self.running = True

        # Message queue for receiving markers
        self.in_channel = queue.Queue()

        # Snapshot state
        self.local_state = {}
        self.snapshot_lock = threading.RLock()
        self.received_marker = defaultdict(bool)
        self.channel_state = defaultdict(list)

    def run(self):
        """Main loop for the user thread."""
        while self.running:
            self.process_messages()
            self.perform_action()
            time.sleep(random.uniform(0.5, 1.5))
        logger.info(f"Gracefully shutting down.")

    def process_messages(self):
        """Processes incoming messages from the channel."""
        try:
            while not self.in_channel.empty():
                message = self.in_channel.get_nowait()
                if message["type"] == "MARKER":
                    self.receive_marker(message["from_user"], message["snapshot_id"])
        except queue.Empty:
            pass  # No messages to process

    def perform_action(self):
        """Decides what action to take based on the current state."""
        if not self.running:
            return

        if self.waiting_for:
            logger.info(f"Continuing to wait for {self.waiting_for}")
            self.try_acquire_lock(self.waiting_for)
            return

        action = random.choice(["read", "write"])
        table = random.choice(self.tables)

        if action == "read":
            self.read(table)
        elif action == "write":
            self.waiting_for = table
            logger.info(f"New goal: WRITE to {table}")
            self.try_acquire_lock(table)

    def read(self, table):
        logger.info(f"Attempting to READ from {table}")
        logger.info(f"Successfully READ from {table}")

    def try_acquire_lock(self, table):
        if table in self.held_locks:
            logger.info(f"Already holds lock for {table}. Goal achieved.")
            self.waiting_for = None
            return

        lock_acquired = table.lock.acquire(blocking=True, timeout=1)

        if lock_acquired:
            if not self.running:
                table.lock.release()
                self.waiting_for = None
                return
            logger.info(f"Acquired lock on {table}. Writing.")
            self.held_locks.append(table)
            table.locked_by = self
            self.waiting_for = None
        else:
            logger.warning(f"Could not acquire lock for {table}, will keep trying.")

    def stop(self):
        logger.info("Stop signal received.")
        self.running = False

    def initiate_snapshot(self, snapshot_id):
        """Initiates the snapshot by recording its state and sending markers."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                logger.info(f"Initiating snapshot {snapshot_id}")
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                for user in self.all_users:
                    if user.id != self.id:
                        marker_message = {
                            "type": "MARKER",
                            "from_user": self.id,
                            "snapshot_id": snapshot_id,
                        }
                        logger.info(f"  -> Sending marker to User-{user.id}")
                        user.in_channel.put(marker_message)

    def receive_marker(self, from_user_id, snapshot_id):
        """Handles receiving a snapshot marker from another user."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                logger.info(
                    f"Received first marker for snapshot {snapshot_id} from User-{from_user_id}"
                )
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                # Forward the marker to all other users
                for user in self.all_users:
                    if user.id != self.id:
                        marker_message = {
                            "type": "MARKER",
                            "from_user": self.id,
                            "snapshot_id": snapshot_id,
                        }
                        logger.info(f"  -> Forwarding marker to User-{user.id}")
                        user.in_channel.put(marker_message)
            else:
                logger.info(
                    f"Received subsequent marker for snapshot {snapshot_id} from User-{from_user_id}. Recording channel state."
                )

    def record_local_state(self, snapshot_id):
        state = {
            "held_locks": [table.id for table in self.held_locks],
            "waiting_for": self.waiting_for.id
            if self.waiting_for is not None
            else None,
        }
        self.local_state[snapshot_id] = state
        logger.info(f"  [State Recorded for Snapshot {snapshot_id}: {state}]")


class DeadlockDetector(threading.Thread):
    """Manages the simulation, initiates snapshots, and detects deadlocks."""

    def __init__(self, users, tables):
        super().__init__(name="Detector")
        self.users = users
        self.tables = tables
        self.snapshot_id_counter = 0
        self.running = True

    def run(self):
        while self.running:
            time.sleep(10)
            if not self.running:
                break
            self.run_snapshot_and_detection()

    def run_snapshot_and_detection(self):
        self.snapshot_id_counter += 1
        snapshot_id = self.snapshot_id_counter
        header = f"--- Starting Global Snapshot {snapshot_id} ---"
        logger.info("\n" + "=" * len(header) + f"\n{header}\n" + "=" * len(header))

        initiator = self.users[0]
        initiator.initiate_snapshot(snapshot_id)

        time.sleep(3)  # Allow time for markers to propagate via queues

        global_state = self.collect_global_state(snapshot_id)
        logger.info("--- Global State Collected ---")
        for user_id, state in sorted(global_state.items()):
            logger.info(f"  User-{user_id}: {state}")

        wait_for_graph = self.build_wait_for_graph(global_state)
        logger.info("--- Wait-For Graph ---")
        if not wait_for_graph:
            logger.info("  (Empty)")
        else:
            for node, edges in sorted(wait_for_graph.items()):
                logger.info(f"  User-{node} is waiting for User(s): {edges}")

        if self.detect_cycle(wait_for_graph):
            logger.error(
                "\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n!!! DEADLOCK DETECTED! !!!\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            )
            self.stop_simulation()
        else:
            logger.info("--- No deadlock detected. ---\n")

    def stop_simulation(self):
        self.running = False
        for user in self.users:
            user.stop()

    def collect_global_state(self, snapshot_id):
        global_state = {}
        for user in self.users:
            with user.snapshot_lock:
                if snapshot_id in user.local_state:
                    global_state[user.id] = user.local_state[snapshot_id]
        return global_state

    def build_wait_for_graph(self, global_state):
        graph = defaultdict(list)
        table_holders = {}
        for user_id, state in global_state.items():
            for table_id in state.get("held_locks", []):
                table_holders[table_id] = user_id

        for user_id, state in global_state.items():
            waiting_for_table = state.get("waiting_for")
            if waiting_for_table is not None and waiting_for_table in table_holders:
                holder_user_id = table_holders[waiting_for_table]
                if user_id != holder_user_id:
                    graph[user_id].append(holder_user_id)
        return graph

    def detect_cycle(self, graph):
        visiting, visited = set(), set()
        for node in list(graph.keys()):
            if node not in visited:
                if self._is_cyclic_util(node, graph, visiting, visited):
                    return True
        return False

    def _is_cyclic_util(self, node, graph, visiting, visited):
        visiting.add(node)
        for neighbor in graph.get(node, []):
            if neighbor in visiting:
                logger.info(f"  Cycle detected: Path includes {neighbor} -> {node}")
                return True
            if neighbor not in visited:
                if self._is_cyclic_util(neighbor, graph, visiting, visited):
                    return True
        visiting.remove(node)
        visited.add(node)
        return False


def main():
    """Main function to set up and run the simulation."""
    num_users = 4
    num_tables = 4

    tables = [Table(i) for i in range(num_tables)]
    all_users = []
    users = [User(i, tables, all_users) for i in range(num_users)]
    all_users.extend(users)

    detector = DeadlockDetector(users, tables)

    logger.info("Starting simulation...")
    for user in users:
        user.start()
    detector.start()

    detector.join()
    for user in users:
        user.join()

    logger.info("Simulation finished.")


if __name__ == "__main__":
    main()
