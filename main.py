import logging
from src.db_resources import User, Table
from src.deadlock_detector import DeadlockDetector
from src.utils import setup_logging

def main():
    """Main function to set up and run the simulation."""
    setup_logging()
    logger = logging.getLogger(__name__)

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