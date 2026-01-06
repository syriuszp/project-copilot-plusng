
import sqlite3
import zipfile
import os
import datetime

# Configuration
DB_PATH = "dev_data/db/project_copilot.dev.db"
OUTPUT_ZIP = f"ProjectCopilot_Audit_Package_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
DIRS_TO_INCLUDE = ["app", "config", "tests", "db"]
FILES_TO_INCLUDE = ["requirements.txt", "pyproject.toml", "README.md", "MANIFEST.in", "audit_proof_log.txt"]

def create_schema_dump(db_path, output_file):
    print(f"Dumping schema from {db_path} to {output_file}...")
    try:
        conn = sqlite3.connect(db_path)
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in conn.iterdump():
                if "CREATE" in line: # Filter for schema mainly, but iterdump gives data too? No, iterdump gives everything.
                    # User asked for "schema bazy danych". 
                    # iterdump() dumps everything (schema + data).
                    # For just schema, we can filter or use specific query.
                    # But often schema dump implies schema.
                    # Let's use a cleaner schema extraction loop.
                    pass
            
            # Better schema only approach
            cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' OR type='index' OR type='view' OR type='trigger'")
            for row in cursor:
                if row[0]: # sql can be None for sqlite_sequence
                    f.write(row[0] + ";\n")
        print("Schema dump successful.")
    except Exception as e:
        print(f"Error dumping schema: {e}")

def create_zip(zip_name, schema_file):
    print(f"Creating ZIP archive: {zip_name}...")
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Add Code, Config, Tests
        for dir_name in DIRS_TO_INCLUDE:
            if os.path.exists(dir_name):
                for root, _, files in os.walk(dir_name):
                    for file in files:
                        if "__pycache__" in root or file.endswith(".pyc") or file.endswith(".DS_Store"):
                            continue
                        
                        file_path = os.path.join(root, file)
                        zipf.write(file_path, file_path)
                        print(f"Added: {file_path}")
        
        # 2. Add specific root files
        for file in FILES_TO_INCLUDE:
            if os.path.exists(file):
                 zipf.write(file, file)
                 print(f"Added: {file}")

        # 3. Add Database
        if os.path.exists(DB_PATH):
             zipf.write(DB_PATH, DB_PATH)
             print(f"Added: {DB_PATH}")
        else:
             print(f"WARNING: Database not found at {DB_PATH}")

        # 4. Add Schema
        if os.path.exists(schema_file):
             zipf.write(schema_file, "database_schema.sql")
             print(f"Added: {schema_file} as database_schema.sql")

    print(f"Successfully created {zip_name}")

if __name__ == "__main__":
    schema_file = "temp_schema_dump.sql"
    try:
        if os.path.exists(DB_PATH):
            create_schema_dump(DB_PATH, schema_file)
        else:
            print("DB not found, skipping schema dump.")
            with open(schema_file, "w") as f: f.write("-- Database file not found")

        create_zip(OUTPUT_ZIP, schema_file)
    finally:
        if os.path.exists(schema_file):
            os.remove(schema_file)
