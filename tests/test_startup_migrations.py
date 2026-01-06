
import pytest
from unittest.mock import MagicMock, patch
from app.core.db_init import init_db

@patch("app.core.db_init.init_or_upgrade_db")
def test_core_db_init_called(mock_db_init):
    # Setup Config
    config = {
        "db_path": "/abs/path/to/db.sqlite",
        "env": "TEST",
        "status": "OK"
    }
    
    mock_db_init.return_value = MagicMock(status="OK", db_path="/abs/path/to/db.sqlite")
    
    # Act
    path = init_db(config)
    
    # Assert
    mock_db_init.assert_called_once_with(config)
    assert path == "/abs/path/to/db.sqlite"

@patch("app.core.db_init.init_or_upgrade_db")
def test_core_db_init_error(mock_db_init):
    # Setup Config
    config = {}
    mock_db_init.return_value = MagicMock(status="ERROR", error="SomeDBError", db_path="unknown.db")
    
    # Act
    path = init_db(config)
    
    # Assert
    mock_db_init.assert_called_once()
    assert path == "unknown.db"
