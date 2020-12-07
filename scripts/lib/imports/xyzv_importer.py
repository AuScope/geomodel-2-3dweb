import logging
import sys

DEBUG_LVL = logging.DEBUG

# Set up debugging
LOGGER = logging.getLogger(__name__)

# Create console handler
LOCAL_HANDLER = logging.StreamHandler(sys.stdout)

# Create formatter
LOCAL_FORMATTER = logging.Formatter('%(asctime)s -- %(name)s -- %(levelname)s - %(message)s')

# Add formatter to ch
LOCAL_HANDLER.setFormatter(LOCAL_FORMATTER)

# Add handler to LOGGER
LOGGER.addHandler(LOCAL_HANDLER)

# Set debug level
LOGGER.setLevel(DEBUG_LVL)


def process_xyzv(file_lines, src_dir, filename):
    # TODO: convert to Geom, Style, Meta points
    LOGGER.debug("I have lines %s", file_lines[0])
    return False, []
