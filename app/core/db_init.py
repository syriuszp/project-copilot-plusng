
from app.db.database import init_or_upgrade_db
import logging

logger = logging.getLogger(__name__)

def init_db(cfg: dict) -> str:
    """
    Core layer DB initialization.
    Does NOT depend on Streamlit.
    """
    res = init_or_upgrade_db(cfg)
    if res.status == "OK":
        return str(res.db_path)
    else:
        # In core, we might raise or log. 
        # The user requested signature: init_db(config: dict) -> str (zwraca ścieżkę DB)
        # Assuming we return path even if error (result object handling in previous step handles this)
        if res.error:
            logger.error(f"DB Init Failed in core: {res.error}")
        return str(res.db_path)
