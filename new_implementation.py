import threading
import time
import random
import logging
from collections import defaultdict

# Configure logging for clear output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(message)s',
    datefmt='%H:%M:%S'
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
        self.waiting_for = None
        self.running = True

        # Snapshot state
        self.local_state = {}
        # Use a re-entrant lock (RLock) for the snapshot process.
        # This is crucial because the snapshot algorithm is initiated by a single thread
        # (the Deadlock-Detector) that makes nested calls to different User objects.
        # A standard Lock would cause a deadlock if the thread tried to acquire a lock
        # it already holds further up the call stack. RLock allows a thread to
        # acquire the same lock multiple times.
        self.snapshot_lock = threading.RLock()
        self.received_marker = defaultdict(bool)
        self.channel_state = defaultdict(list)

    def run(self):
        """Main loop for the user thread."""
        while self.running:
            self.perform_action()
            time.sleep(random.uniform(0.5, 2))

    def perform_action(self):
        """Randomly chooses to read or write to a table."""
        action = random.choice(['read', 'write'])
        table = random.choice(self.tables)

        if action == 'read':
            self.read(table)
        elif action == 'write':
            self.write(table)

    def read(self, table):
        """Performs a read operation on a table."""
        logging.info(f"Attempting to READ from {table}")
        # In a real system, a read might still need a shared lock,
        # but for this simulation, we'll keep it simple.
        logging.info(f"Successfully READ from {table}")

    def write(self, table):
        """Performs a write operation, requiring a lock."""
        logging.info(f"Attempting to WRITE to {table}")
        if table in self.held_locks:
            logging.info(f"Already holds lock for {table}. Writing.")
            return

        self.waiting_for = table
        logging.info(f"Waiting for lock on {table}")
        if table.lock.acquire():
            self.waiting_for = None
            table.locked_by = self
            self.held_locks.append(table)
            logging.info(f"Acquired lock on {table}. Writing.")
            # Simulate holding the lock for some time
            time.sleep(random.uniform(1, 3))
            # For this simulation, we'll make users hold locks to induce deadlocks
            # self.release_lock(table)
        else:
            logging.warning(f"Failed to acquire lock for {table}")


    def release_lock(self, table):
        """Releases a lock held by the user."""
        if table in self.held_locks:
            table.lock.release()
            table.locked_by = None
            self.held_locks.remove(table)
            logging.info(f"Released lock on {table}")

    def stop(self):
        """Stops the user thread."""
        self.running = False
        # Release all held locks on exit
        for table in list(self.held_locks):
            self.release_lock(table)

    def initiate_snapshot(self, snapshot_id):
        """Initiates the Chandy-Lamport snapshot algorithm."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                logging.info(f"Initiating snapshot {snapshot_id}")
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                # Send marker to all other users (processes)
                for user in self.all_users:
                    if user.id != self.id:
                        logging.info(f"Sending marker for snapshot {snapshot_id} to User-{user.id}")
                        # In a real system, this would be a message pass.
                        # Here we directly call the method.
                        user.receive_marker(self, snapshot_id)

    def receive_marker(self, from_user, snapshot_id):
        """Handles receiving a snapshot marker from another user."""
        with self.snapshot_lock:
            if not self.received_marker[snapshot_id]:
                # First time receiving marker for this snapshot
                logging.info(f"Received marker for snapshot {snapshot_id} from {from_user.name}")
                self.record_local_state(snapshot_id)
                self.received_marker[snapshot_id] = True
                # Send marker to all other users
                for user in self.all_users:
                    if user.id != self.id:
                         logging.info(f"Forwarding marker for snapshot {snapshot_id} to User-{user.id}")
                         user.receive_marker(self, snapshot_id)
            else:
                # Already recorded state, now record channel state
                logging.info(f"Received subsequent marker for snapshot {snapshot_id} from {from_user.name}. Recording channel state.")
                # For this simulation, the "messages" in the channel are implicit dependencies.
                # We don't have explicit messages, so we leave this part abstract.


    def record_local_state(self, snapshot_id):
        """Records the user's current state for a snapshot."""
        state = {
            "held_locks": [table.id for table in self.held_locks],
            "waiting_for": self.waiting_for.id if self.waiting_for else None
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
            time.sleep(10) # Wait for a period before starting a new snapshot
            self.snapshot_id_counter += 1
            snapshot_id = self.snapshot_id_counter
            logging.info(f"--- Starting Global Snapshot {snapshot_id} ---")

            # Any process can initiate the snapshot. We'll pick the first user.
            initiator = self.users[0]
            initiator.initiate_snapshot(snapshot_id)

            # Give time for markers to propagate
            time.sleep(5)

            global_state = self.collect_global_state(snapshot_id)
            logging.info(f"--- Global State for Snapshot {snapshot_id} ---")
            for user_id, state in global_state.items():
                logging.info(f"User-{user_id}: {state}")

            wait_for_graph = self.build_wait_for_graph(global_state)
            logging.info(f"Wait-For Graph: {dict(wait_for_graph)}")

            if self.detect_cycle(wait_for_graph):
                logging.error("!!! DEADLOCK DETECTED! Terminating simulation. !!!")
                self.running = False
                # Stop all user threads
                for user in self.users:
                    user.stop()
            else:
                logging.info("--- No deadlock detected in snapshot. ---")


    def collect_global_state(self, snapshot_id):
        """Collects the local states from all users for a given snapshot."""
        global_state = {}
        for user in self.users:
            if snapshot_id in user.local_state:
                global_state[user.id] = user.local_state[snapshot_id]
        return global_state

    def build_wait_for_graph(self, global_state):
        """Builds a wait-for graph from the collected global state."""
        graph = defaultdict(list)
        # Create a map of table_id to the user holding the lock
        table_holders = {}
        for user_id, state in global_state.items():
            for table_id in state["held_locks"]:
                table_holders[table_id] = user_id

        # Build the graph
        for user_id, state in global_state.items():
            waiting_for_table = state["waiting_for"]
            if waiting_for_table and waiting_for_table in table_holders:
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
                logging.info(f"Cycle detected: {neighbor} is already in the visiting path.")
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
    # We pass a reference to the list of all users to each user.
    # We will populate this list after creating the user objects.
    all_users = []

    # Create users
    users = [User(i, tables, all_users) for i in range(num_users)]
    all_users.extend(users) # Now populate the list

    # Create the deadlock detector
    detector = DeadlockDetector(users, tables)

    # Start all threads
    logging.info("Starting simulation...")
    for user in users:
        user.start()
    detector.start()

    # The main thread will wait for the detector to finish
    detector.join()
    logging.info("Simulation finished.")


if __name__ == "__main__":
    main()

