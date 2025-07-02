import logging
from collections import defaultdict

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

def setup_logging():
    """Configures logging with the custom formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter("%(asctime)s - %(threadName)s - %(message)s"))
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = [handler]