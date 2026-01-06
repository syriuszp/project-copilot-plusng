
import pytest
import logging

@pytest.fixture(autouse=True)
def shutdown_logging_teardown():
    """
    Force shutdown of logging handlers to release file locks on Windows.
    This prevents PermissionError during tmp_path cleanup.
    """
    yield
    # Aggressively close handlers
    root = logging.getLogger()
    for h in root.handlers[:]:
        h.close()
        root.removeHandler(h)
    logging.shutdown()
