import threading
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

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

        time.sleep(3) # propagation time

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