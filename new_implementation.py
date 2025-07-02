import threading
import time
import random
import logging
from collections import defaultdict

# Configure logging for clear output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(message)s",
    datefmt="%H:%M:%S",
)


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
        self.waiting_for = None  # This now represents a persistent goal
        self.running = True

        # Snapshot state
        self.local_state = {}
        self.snapshot_lock = threading.RLock()
        self.received_marker = defaultdict(bool)
        self.channel_state = defaultdict(list)

    def run(self):
        """Main loop for the user thread."""
        while self.running:
            self.perform_action()
            time.sleep(random.uniform(0.5, 1.5))
        logging.info(f"{self.name} gracefully shutting down.")

    def perform_action(self):
        """Decides what action to take based on the current state."""
        if not self.running:
            return

        # If we are already waiting for a table, our only action is to keep trying to acquire it.
        if self.waiting_for:
            logging.info(f"Continuing to wait for {self.waiting_for}")
            self.try_acquire_lock(self.waiting_for)
            return

        # If not waiting for anything, choose a new action.
        action = random.choice(["read", "write"])
        table = random.choice(self.tables)

        if action == "read":
            self.read(table)
        elif action == "write":
            # Set the intention to acquire this lock as a persistent goal.
            self.waiting_for = table
            logging.info(f"New goal: WRITE to {table}")
            self.try_acquire_lock(table)

    def read(self, table):
        """Performs a read operation on a table."""
        logging.info(f"Attempting to READ from {table}")
        logging.info(f"Successfully READ from {table}")

    def try_acquire_lock(self, table):
        """Attempts to acquire a lock for a write operation."""
        if table in self.held_locks:
            logging.info(f"Already holds lock for {table}. Goal achieved.")
            self.waiting_for = None  # Clear the goal
            return

        # Use a timeout on the lock acquire.
        lock_acquired = table.lock.acquire(blocking=True, timeout=1)

        if lock_acquired:
            # Check if the thread was stopped while waiting for the lock
            if not self.running:
                table.lock.release()
                self.waiting_for = None
                return

            logging.info(f"Acquired lock on {table}. Writing.")
            self.held_locks.append(table)
            table.locked_by = self
            # Goal achieved, clear the waiting state.
            self.waiting_for = None
        else:
            logging.warning(f"Could not acquire lock for {table}, will keep trying.")
            # IMPORTANT: We do NOT clear self.waiting_for here.
            # The user will retry in the next perform_action call.

    def release_lock(self, table):
        """Releases a lock held by the user."""
        if table in self.held_locks:
            table.lock.release()
            table.locked_by = None
            self.held_locks.remove(table)
            logging.info(f"Released lock on {table}")

    def stop(self):
        """Signals the user thread to stop."""
        logging.info("Stop signal received.")
        self.running = False

    def initiate_snapshot(self, snapshot_id):
        """Initiates the Chandy-Lamport snapshot algorithm."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                logging.info(f"Initiating snapshot {snapshot_id}")
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                for user in self.all_users:
                    if user.id != self.id:
                        logging.info(
                            f"Sending marker for snapshot {snapshot_id} to User-{user.id}"
                        )
                        user.receive_marker(self, snapshot_id)

    def receive_marker(self, from_user, snapshot_id):
        """Handles receiving a snapshot marker from another user."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                logging.info(
                    f"Received marker for snapshot {snapshot_id} from {from_user.name}"
                )
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                for user in self.all_users:
                    if user.id != self.id:
                        logging.info(
                            f"Forwarding marker for snapshot {snapshot_id} to User-{user.id}"
                        )
                        user.receive_marker(self, snapshot_id)
            else:
                logging.info(
                    f"Received subsequent marker for snapshot {snapshot_id} from {from_user.name}. Recording channel state."
                )

    def record_local_state(self, snapshot_id):
        """Records the user's current state for a snapshot."""
        state = {
            "held_locks": [table.id for table in self.held_locks],
            "waiting_for": self.waiting_for.id
            if self.waiting_for is not None
            else None,
        }
        self.local_state[snapshot_id] = state
        logging.info(f"Recorded local state for snapshot {snapshot_id}: {state}")


class DeadlockDetector(threading.Thread):
    """Manages the simulation, initiates snapshots, and detects deadlocks."""

    def __init__(self, users, tables):
        super().__init__(name="Deadlock-Detector")
        self.users = users
        self.tables = tables
        self.snapshot_id_counter = 0
        self.running = True

    def run(self):
        """Periodically initiates snapshots and checks for deadlocks."""
        while self.running:
            time.sleep(10)
            if not self.running:
                break

            self.snapshot_id_counter += 1
            snapshot_id = self.snapshot_id_counter
            logging.info(f"--- Starting Global Snapshot {snapshot_id} ---")

            initiator = self.users[0]
            initiator.initiate_snapshot(snapshot_id)

            time.sleep(2)  # Allow time for markers to propagate

            global_state = self.collect_global_state(snapshot_id)
            logging.info(f"--- Global State for Snapshot {snapshot_id} ---")
            for user_id, state in sorted(global_state.items()):
                logging.info(f"User-{user_id}: {state}")

            wait_for_graph = self.build_wait_for_graph(global_state)
            logging.info(f"Wait-For Graph: {dict(wait_for_graph)}")

            if self.detect_cycle(wait_for_graph):
                logging.error("!!! DEADLOCK DETECTED! Terminating simulation. !!!")
                self.stop_simulation()
            else:
                logging.info("--- No deadlock detected in snapshot. ---")

    def stop_simulation(self):
        """Stops all threads in the simulation."""
        self.running = False
        for user in self.users:
            user.stop()

    def collect_global_state(self, snapshot_id):
        """Collects the local states from all users for a given snapshot."""
        global_state = {}
        for user in self.users:
            # We need a lock here to prevent reading state while it's being written
            with user.snapshot_lock:
                if snapshot_id in user.local_state:
                    global_state[user.id] = user.local_state[snapshot_id]
        return global_state

    def build_wait_for_graph(self, global_state):
        """Builds a wait-for graph from the collected global state."""
        graph = defaultdict(list)
        table_holders = {}
        for user_id, state in global_state.items():
            for table_id in state.get("held_locks", []):
                table_holders[table_id] = user_id

        for user_id, state in global_state.items():
            waiting_for_table = state.get("waiting_for")
            # CORRECTED: Explicitly check for None instead of relying on truthiness,
            # as waiting_for_table could be 0, which evaluates to False.
            if waiting_for_table is not None and waiting_for_table in table_holders:
                holder_user_id = table_holders[waiting_for_table]
                if user_id != holder_user_id:
                    graph[user_id].append(holder_user_id)
        return graph

    def detect_cycle(self, graph):
        """Detects a cycle in the wait-for graph using DFS."""
        visiting = set()
        visited = set()

        for node in list(graph.keys()):
            if node not in visited:
                if self._is_cyclic_util(node, graph, visiting, visited):
                    return True
        return False

    def _is_cyclic_util(self, node, graph, visiting, visited):
        """Utility function for DFS cycle detection."""
        visiting.add(node)

        for neighbor in graph.get(node, []):
            if neighbor in visiting:
                logging.info(f"Cycle detected: Path includes {neighbor} -> {node}")
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

    logging.info("Starting simulation...")
    for user in users:
        user.start()
    detector.start()

    # Wait for the detector thread to finish, which happens after a deadlock
    detector.join()

    # Ensure all user threads have also terminated
    for user in users:
        user.join()

    logging.info("Simulation finished.")


if __name__ == "__main__":
    main()
