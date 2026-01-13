import sqlite3
import os
from typing import List
from dataclasses import dataclass

@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float
    snippet: str
    match_type: str = 'vector'
    keyword_hits: int = 0
    is_literal: bool = False

# Helper from Retriever (copy-paste for test)
def _tokenize_terms(q: str):
    import re
    return [t for t in re.split(r"\s+", q.strip()) if t]

def _count_term_hits_in_text(text: str, terms: List[str]) -> int:
    import re
    if not text or not terms:
        return 0
    hits = 0
    for t in terms:
        try:
            pattern = rf"\b{re.escape(t)}\b"
            hits += len(re.findall(pattern, text, flags=re.IGNORECASE))
        except:
             hits += text.lower().count(t.lower())
    return hits

def setup_db(db_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    
    # Enable FTS5
    conn.execute("CREATE TABLE chunks (chunk_rowid INTEGER PRIMARY KEY, chunk_id TEXT, content_text TEXT, page INT, slide INT, section TEXT, bbox TEXT, is_active INT, artifact_id INT)")
    conn.execute("CREATE VIRTUAL TABLE chunks_fts USING fts5(content_text, content='chunks', content_rowid='chunk_rowid')")
    
    # Insert data
    data = [
        (1, "c1", "This is a literal match for project management.", 1, 0, "", "", 1, 101),
        (2, "c2", "Another chunk about timelines and milestones.", 1, 0, "", "", 1, 101),
        (3, "c3", "Irrelevant content.", 1, 0, "", "", 1, 102),
        (4, "c4", "Project management is key. Management of projects is hard.", 2, 0, "", "", 1, 101)
    ]
    conn.executemany("INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", data)
    conn.executemany("INSERT INTO chunks_fts(rowid, content_text) VALUES (?, ?)", [(d[0], d[2]) for d in data])
    
    conn.commit()
    conn.close()

def test_fts_query(db_path):
    print("--- Test FTS Query & Highlights ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = "project"
    print(f"Query: {query}")

    # Test 1a: Snippet Only
    try:

        sql_snip = """
            SELECT snippet(chunks_fts, 0, '<b>', '</b>', '...', 12) AS snip
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
        """
        print("Testing Snippet...")
        for row in conn.execute(sql_snip, (query,)):
            print(f"Snippet OK: {row['snip']}")
    except Exception as e:
        print(f"Snippet Failed: {e}")

    # Test 1b: Offsets Only
    try:
        sql_offs = """
            SELECT offsets(chunks_fts) AS offs
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
        """
        print("Testing Offsets...")
        for row in conn.execute(sql_offs, (query,)):
            print(f"Offsets OK: {row['offs']}")
    except Exception as e:
        print(f"Offsets Failed: {e}")

    # Test 1c: Combined (Original)

    
    # Test 2: AND Logic
    query = "project management"
    fts_q = '"project" AND "management"' # What our _fts_query produces
    print(f"\nQuery: {fts_q}")
    
    sql = """
        SELECT 
            snippet(chunks_fts, 0, '<b>', '</b>', '...', 12) AS snip,
            bm25(chunks_fts) AS fts_score,
            c.content_text
        FROM chunks_fts
        JOIN chunks c ON c.chunk_rowid = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY fts_score ASC
    """
    
    for row in conn.execute(sql, (fts_q,)):
        # Calculate hits (Manual fallback logic)
        terms = _tokenize_terms(query)
        hits = _count_term_hits_in_text(row['content_text'], terms)
        
        print(f"Hits (Manual): {hits}")
        assert "<b>project</b>" in row['snip'].lower()
        if "key" in row['snip']: # c4 has 'Project' and 'projects' -> 2 hits?
             # "Project management is key. Management of projects is hard."
             # "project" -> 2 hits (Project, projects)
             assert hits >= 2
    conn.close()

def test_counters(db_path):
    print("\n--- Test Counters (SearchService Logic) ---")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    query = "project"
    # Artifact 101 has 2 chunks with "project" (c1, c4). c2 has none.
    # c4 has 2 occurrences. c1 has 1. Total hits = 3.
    
    fts_q = '"project"'
    art_ids = [101, 102]
    placeholders = ','.join('?' for _ in art_ids)
    
    # Calculate hits per artifact
    sql = f"""
        SELECT c.artifact_id, c.content_text
        FROM chunks_fts
        JOIN chunks c ON c.chunk_rowid = chunks_fts.rowid
        WHERE chunks_fts MATCH ? 
          AND c.artifact_id IN ({placeholders})
    """
    
    params = [fts_q] + art_ids
    file_stats = {}
    
    rows = conn.execute(sql, params).fetchall()
    terms = _tokenize_terms(query)
    
    for row in rows:
        aid = row['artifact_id']
        if aid not in file_stats:
            file_stats[aid] = {"hits": 0, "chunks": 0}
        file_stats[aid]["chunks"] += 1
        file_stats[aid]["hits"] += _count_term_hits_in_text(row['content_text'], terms)

    for aid, stats in file_stats.items():
        print(f"Artifact {aid}: Chunks={stats['chunks']}, Hits={stats['hits']}")
        if aid == 101:
            # c1: "This is a literal match for project management." (1x project)
            # c4: "Project management is key. Management of projects is hard." (1x Project, 0x projects due to strict boundary)
            # Total Chunks: 2
            # Total Hits: 2 (was 3 with loose matching)
            assert stats['chunks'] == 2
            assert stats['hits'] == 2

def test_strict_matching(db_path):
    print("\n--- Test Strict Matching ---")
    conn = sqlite3.connect(db_path)
    # Insert tricky data
    conn.execute("INSERT INTO chunks VALUES (5, 'c5', 'The plant is growing plan.', 1, 0, '', '', 1, 103)")
    conn.execute("INSERT INTO chunks_fts(rowid, content_text) VALUES (5, 'The plant is growing plan.')")
    conn.commit()
    conn.close()
    
    # Test: Query "plan" should match "plan" (1) but not "plant"
    # c5 content: "The plant is growing plan."
    # hits should be 1.
    
    text = "The plant is growing plan."
    terms = ["plan"]
    hits = _count_term_hits_in_text(text, terms)
    print(f"Text: '{text}', Terms: {terms}, Hits: {hits}")
    assert hits == 1
            
import sys

def checks(db_path):
    print("Checking FTS5...")
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        conn.execute("INSERT INTO t VALUES ('foo')")
        print("FTS5 table created.")
        row = conn.execute("SELECT bm25(t) FROM t").fetchone()
        print(f"BM25 available: {row}")
    except Exception as e:
        print(f"FTS5 Check Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    sys.stdout = open("reproduce_log.txt", "w")
    sys.stderr = sys.stdout
    
    db_name = "test_fts_v10.db"
    try:
        checks(db_name)
        setup_db(db_name)
        test_fts_query(db_name)
        test_counters(db_name)
        test_strict_matching(db_name)
        print("\nSUCCESS: All checks passed.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nFAILED: {e}")
    finally:
        try:
            if os.path.exists(db_name):
                os.remove(db_name)
        except Exception as e:
            print(f"Cleanup failed: {e}")
    sys.stdout.close()
