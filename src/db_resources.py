import threading
import time
import random
import logging
from collections import defaultdict
import queue

logger = logging.getLogger(__name__)

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
            pass

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