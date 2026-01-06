
import sqlite3
import time

def test_sqlite_types():
    conn = sqlite3.connect(":memory:")
    # Create table with TEXT column
    conn.execute("CREATE TABLE test (val TEXT)")
    
    # Insert float
    now_float = time.time() # e.g. 1700000.12345
    print(f"Inserting float: {now_float}")
    conn.execute("INSERT INTO test (val) VALUES (?)", (now_float,))
    
    # Read back
    row = conn.execute("SELECT val FROM test").fetchone()
    val_back = row[0]
    print(f"Read back type: {type(val_back)}")
    print(f"Read back value: {val_back}")
    
    # Insert MAX check (simulating copy)
    conn.execute("CREATE TABLE test2 (val TEXT)")
    conn.execute("INSERT INTO test2 (val) SELECT MAX(val) FROM test")
    
    row2 = conn.execute("SELECT val FROM test2").fetchone()
    val_back2 = row2[0]
    print(f"Copy (MAX) back type: {type(val_back2)}")
    print(f"Copy (MAX) back value: {val_back2}")
    
    # Check equality
    # Wait, if stored as TEXT, expected to be string "123.45"
    if isinstance(val_back, str):
        print("Stored as STRING due to Affinity!")
    else:
        print("Stored as FLOAT/REAL!")

if __name__ == "__main__":
    test_sqlite_types()
