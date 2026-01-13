
from app.db.database import init_or_upgrade_db
import logging

# Configure minimal logging
logging.basicConfig(level=logging.INFO)

config = {
    "paths": {
        "db_path": "data/project_copilot.db"
    }
}

print("Upgrading database...")
res = init_or_upgrade_db(config)
print(f"Result: {res.status}")
if res.error:
    print(f"Error: {res.error}")
else:
    print("Database is up to date.")
