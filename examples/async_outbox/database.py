
import sqlite3
import os

DB_PATH = "demo.db"

def init_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Outbox Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS outbox_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()
    print(f"Database {DB_PATH} initialized.")

def get_connection():
    return sqlite3.connect(DB_PATH)

def insert_outbox_event(conn, event_type, payload):
    """
    Transactional insert. Assumes conn is part of a larger transaction or manages commit itself.
    Here we take conn as arg to allow atomicity with other logic if needed.
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO outbox_events (event_type, payload) VALUES (?, ?)", 
        (event_type, payload)
    )
    # Note: We do NOT commit here. The caller (Process) should commit to ensure atomicity.
