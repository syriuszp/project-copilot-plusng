
import sqlite3
import os

try:
    conn = sqlite3.connect('dev_data/db/project_copilot.dev.db')
    conn.row_factory = sqlite3.Row
    print("Connected to DB")
    
    cur = conn.execute("SELECT * FROM artifacts WHERE filename LIKE '%Risk List%.csv'")
    row = cur.fetchone()
    
    if row:
        print("Artifact Found:")
        print(dict(row))
        
        t_cur = conn.execute("SELECT * FROM artifact_text WHERE artifact_id=?", (row['id'],))
        t_row = t_cur.fetchone()
        
        if t_row:
            print("Text Found:")
            d = dict(t_row)
            # Preview text start/end
            text = d['text']
            print(f"Extractor: {d['extractor']}")
            print(f"Text Length: {len(text)}")
            print(f"Start: {text[:100]!r}")
            print(f"End: {text[-100:]!r}")
        else:
            print("No Text Record Found!")
    else:
        print("No CSV Artifact Found")

except Exception as e:
    print(f"Error: {e}")
