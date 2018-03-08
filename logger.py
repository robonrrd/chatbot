import logging
import logging.handlers
import os

from colortext import ENDC

def initialize(output_dir):
    """Initialize the logging module to log messages to the right places."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # console handler (INFO+)
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s" +
                                  ENDC)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # channel log (uses DEBUG)
    handler = logging.FileHandler(os.path.join(output_dir, "channel.log"), "w",
                                  encoding=None, delay="true")
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s: %(message)s" + ENDC)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # log everything with level name
    # TODO: add color based on level
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(output_dir, "debug.log"), "w", encoding=None, delay="true",
        maxBytes=1*1024*1024, backupCount=5)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s" +
                                  ENDC)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

