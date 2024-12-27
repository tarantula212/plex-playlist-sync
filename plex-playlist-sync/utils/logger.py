import logging
from colorama import Fore, Style

# Define colors for each log level
COLORS = {
    "DEBUG": Fore.BLUE,
    "INFO": Fore.CYAN,
    "SUCCESS": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR": Fore.RED,
    "CRITICAL": Fore.RED + Style.BRIGHT,
}


class CustomLogger(logging.Logger):
    def success(self, message, *args, **kwargs):
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, message, args, **kwargs)


# Define a custom SUCCESS log level
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")
logging.setLoggerClass(CustomLogger)


class ColorFormatter(logging.Formatter):
    """Custom formatter to add colors to log levels."""

    def format(self, record):
        log_color = COLORS.get(record.levelname, "")
        reset = Style.RESET_ALL
        message = super().format(record)
        return f"{log_color}{message}{reset}"


def setup_logger(name="AppLogger", level=logging.DEBUG) -> CustomLogger:
    """Sets up a logger with colored output."""
    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if the logger already has handlers
    if not logger.handlers:
        # Create console handler with color formatting
        console_handler = logging.StreamHandler()
        formatter = ColorFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(console_handler)

    return logger
