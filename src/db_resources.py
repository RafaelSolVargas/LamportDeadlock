import threading

class Table:
    """
    Represents a database table that can be locked for writing.
    """
    def __init__(self, name):
        self.name = name
        self.write_lock = threading.Lock()
        self.lock_owner = None

    def __repr__(self):
        return f"Table({self.name})"
