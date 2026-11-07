import sqlite3
from contextlib import contextmanager
from app.config import DATABASE_PATH

def init_db(db_path: str = DATABASE_PATH):
    """Initializes SQLite schema, WAL mode, and creates performance indexes."""
    with sqlite3.connect(db_path, timeout=10.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        cursor = conn.cursor()

        # 1. Stored Blog Posts (Single Source of Truth)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content_markdown TEXT NOT NULL,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Platform Variants with Review Status
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variants (
                id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                hashtags TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                rejection_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id)
            )
        """)

        # 3. Scheduled Slots Calendar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                variant_id TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (variant_id) REFERENCES variants(id)
            )
        """)

        # 4. Publish History (Audit & Delivery Record)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS publish_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER,
                variant_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                adapter_used TEXT NOT NULL,
                live_post_url TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                idempotency_key TEXT NOT NULL,
                published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (variant_id) REFERENCES variants(id)
            )
        """)

        # 5. Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_post_id ON variants(post_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_variants_status ON variants(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_slots_status ON scheduled_slots(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_idemp ON publish_history(idempotency_key)")

        conn.commit()

@contextmanager
def get_db(db_path: str = DATABASE_PATH):
    """Context manager for SQLite connection with timeout."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

