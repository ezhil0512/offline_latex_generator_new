import logging
import sys
from offline_latex_generator.config import config

def setup_logger(name: str = "offline_latex_generator") -> logging.Logger:
    """Configures and returns a structured logger based on active configuration."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    log_level = config.get("logging.level", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    handler = sys.stdout
    stream_handler = logging.StreamHandler(handler)
    
    # In a full implementation, JSON format would be applied if logging.format is "json"
    log_format = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format)
    stream_handler.setFormatter(formatter)
    
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger

# Primary logger instance
logger = setup_logger()
