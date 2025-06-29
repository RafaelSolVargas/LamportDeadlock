import threading
import time
from src.utils import log

class DeadlockDetector:
    def __init__(self, shutdown_event):
        self.shutdown_event = shutdown_event


    def analyze(self, snapshot):
        if self.shutdown_event.is_set():
            return

        log("Analyzing snapshot for deadlocks...")
        graph = self.__build_wait_for_graph(snapshot)
        if any(graph.values()):
            log(f"Built Wait-For Graph: {graph}")
        
        cycle = self.__find_cycle(graph)
        
        if cycle:
            log("="*40)
            log("!!! DEADLOCK DETECTED !!!")
            log(f"Dependency cycle found: {' -> '.join(cycle)}")
            log("Initiating graceful shutdown of the application...")
            log("="*40)
            self.shutdown_event.set()
        else:
            log("No deadlocks were detected in this snapshot.")

    def __build_wait_for_graph(self, snapshot):
        graph = {thread_id: [] for thread_id in snapshot}
        for thread_id, state in snapshot.items():
            waiting_for_table_name = state['waiting_for_table']
            if waiting_for_table_name:
                owner_found = None
                for other_thread_id, other_state in snapshot.items():
                    if waiting_for_table_name in [t.name for t in other_state['locked_tables']]:
                        owner_found = other_thread_id
                        break
                if owner_found and owner_found != thread_id:
                    graph[thread_id].append(owner_found)
        return graph

    def __find_cycle(self, graph):
        visited = set()
        recursion_stack = set()
        for node in graph:
            if node not in visited:
                path = self.__dfs_cycle_util(node, graph, visited, recursion_stack)
                if path:
                    start_node = path[-1]
                    try:
                        cycle_start_index = path.index(start_node)
                        return path[cycle_start_index:]
                    except ValueError:
                        return path
        return None

    def __dfs_cycle_util(self, node, graph, visited, recursion_stack, path=None):
        if path is None: path = []
        visited.add(node)
        recursion_stack.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                result = self.__dfs_cycle_util(neighbor, graph, visited, recursion_stack, path)
                if result: return result
            elif neighbor in recursion_stack:
                path.append(neighbor)
                return path
        recursion_stack.remove(node)
        path.pop()
        return None

class Snapshotter(threading.Thread):
    def __init__(self, lock_manager, interval, shutdown_event):
        super().__init__(name="DBA-Monitor", daemon=True)
        self.lock_manager = lock_manager
        self.interval = interval
        self.shutdown_event = shutdown_event

    def run(self):
        log(f"Monitoring started. Will take snapshots every {self.interval} seconds.")
        while not self.shutdown_event.is_set():
            time.sleep(self.interval)
            if not self.shutdown_event.is_set():
                self.lock_manager.take_snapshot()
