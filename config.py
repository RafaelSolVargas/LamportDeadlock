"""
Central configuration file for the Deadlock Detection Simulation.
Tune these parameters to alter the simulation's behavior and the
likelihood of deadlocks.
"""

# --- Simulation Setup ---
NUM_CLIENTS = 10
NUM_TABLES = 4          # Lower number increases resource contention
SNAPSHOT_INTERVAL = 5   # In seconds

# --- Client Behavior Tuning ---
# Probability (0.0 to 1.0) that a client's next operation is a WRITE.
# The chance of a READ is (1.0 - WRITE_PROBABILITY).
WRITE_PROBABILITY = 0.5

# Probability (0.0 to 1.0) that a WRITE transaction will involve two tables.
# A two-table transaction is required to create a deadlock.
MULTI_TABLE_TX_PROBABILITY = 0.4

# --- Timing (in seconds) ---
# Duration of a simulated READ operation.
READ_DURATION_RANGE = (2, 5)

# Duration of the actual "work" in a WRITE transaction (when all locks are held).
WRITE_DURATION_RANGE = (3, 6)

# Pause between acquiring the first and second lock in a multi-table transaction.
# This "window of opportunity" is crucial for deadlocks to occur.
DEADLOCK_WINDOW_RANGE = (0.1, 0.4)

# Cooldown period for a client after completing an operation.
CLIENT_COOLDOWN_RANGE = (1, 2)