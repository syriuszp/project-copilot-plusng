
import os
import sys
from importlib.metadata import version, PackageNotFoundError

def get_app_version():
    """
    Returns (version_string, is_dev_mode)
    """
    # 1. Check Env Override
    env_ver = os.environ.get("PROJECT_COPILOT_VERSION")
    if env_ver:
        return env_ver, False # Assuming env var overrides are specific

    # 2. Check installed package (Wheel)
    try:
        # Assuming package name is 'project-copilot' or similar from pyproject.toml
        # If running from source, this might still find the installed version if present
        # So we check for "editable" or dev markers if possible.
        pkg_ver = version("project_copilot") 
        return pkg_ver, False
    except PackageNotFoundError:
        pass

    # 3. Fallback to DEV
    return "v0.3.3-dev", True

def get_commit_hash_short():
    # Optional: try to read git if .git exists
    return "dev"
