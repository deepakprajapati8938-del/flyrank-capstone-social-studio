import sys
import json
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import DATABASE_PATH
from app.database import init_db, get_db
from app.generator import generate_variants_for_post
from app.scheduler import schedule_variant

def seed_database():
    print("=========================================================")
    print("[SEED] SOCIAL MEDIA STUDIO — MULTI-PLATFORM CAMPAIGN PUBLISHER")
    print(f"[SEED] Database Target: {DATABASE_PATH}")
    print("=========================================================")

    # 1. Initialize schema
    init_db(DATABASE_PATH)
    print("[OK] Initialized SQLite tables and performance indexes.")

    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM publish_history")
        cursor.execute("DELETE FROM scheduled_slots")
        cursor.execute("DELETE FROM variants")
        cursor.execute("DELETE FROM posts")
        conn.commit()

    # 2. Ingest Sample Blog Post (Single Source of Truth)
    post_id = "post_sample_01"
    post_title = "Reliability Engineering in Distributed Publishing: Retries, Timeouts, and Idempotency"
    post_markdown = (
        "In production backend engineering, making an API call is easy. The real challenge is surviving "
        "the messy realities of distributed networks: duplicate client retries, intermittent timeouts, "
        "and worker crashes mid-batch. By decoupling publication requests into deterministic idempotency keys, "
        "enforcing strict constraint profiles before human review, and abstracting social targets behind "
        "clean publisher adapters, modern content architectures guarantee exactly-once delivery across platforms."
    )
    post_url = "https://flyrank.ai/blog/reliability-engineering"

    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts (id, title, content_markdown, source_url)
            VALUES (?, ?, ?, ?)
            """,
            (post_id, post_title, post_markdown, post_url)
        )
        conn.commit()
    print(f"[OK] Ingested canonical post: '{post_title}' (ID: {post_id}).")

    # 3. Generate Platform Variants
    variants = generate_variants_for_post(post_id, DATABASE_PATH)
    print(f"[OK] Generated {len(variants)} platform variants conforming to constraint profiles:")
    for v in variants:
        print(f"     - Platform: {v['platform'].upper()} | ID: {v['id']} | Length: {len(v['content'])} chars | Status: {v['status']}")

    # 4. Review Workflow Setup:
    # - Pre-approve X variant and LinkedIn variant
    # - Leave Instagram variant as 'draft' (for testing unapproved scheduling refusal)
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE variants SET status = 'approved' WHERE platform IN ('x', 'linkedin')")
        conn.commit()
    print("[OK] Review Workflow: Approved 'x' and 'linkedin' variants. Kept 'instagram' as 'draft'.")

    # 5. Pre-schedule the approved X variant
    x_var_id = [v["id"] for v in variants if v["platform"] == "x"][0]
    slot_info = schedule_variant(x_var_id, "2026-11-08T10:00:00Z", DATABASE_PATH)
    print(f"[OK] Scheduled calendar slot: Slot {slot_info['slot_id']} for variant '{x_var_id}' at {slot_info['slot_time']}.")

    print("\n[COMPLETE] Seed complete! System is primed for acceptance probes.")
    print("=========================================================")

if __name__ == "__main__":
    seed_database()
