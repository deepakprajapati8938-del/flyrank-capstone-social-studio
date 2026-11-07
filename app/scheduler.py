import json
import datetime
from typing import Dict, Any, Optional, List
from app.config import DATABASE_PATH
from app.database import get_db
from app.adapters.registry import get_publisher_adapter

def schedule_variant(
    variant_id: str,
    slot_time: str,
    db_path: str = DATABASE_PATH
) -> Dict[str, Any]:
    """
    Schedules an approved variant for publication at a given slot time.
    Enforces the core rule: ONLY approved variants can be scheduled.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status, platform, content FROM variants WHERE id = ?", (variant_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Variant '{variant_id}' does not exist.")
        
        var = dict(row)
        if var["status"] != "approved":
            raise ValueError(
                f"Cannot schedule unapproved variant '{variant_id}' (current status: '{var['status']}'). "
                f"A person must approve the variant before it can enter the publishing calendar."
            )

        idempotency_key = f"{variant_id}:{slot_time}"

        # Check if already scheduled
        cursor.execute("SELECT id, status FROM scheduled_slots WHERE idempotency_key = ?", (idempotency_key,))
        existing_slot = cursor.fetchone()
        if existing_slot:
            return {
                "slot_id": existing_slot["id"],
                "variant_id": variant_id,
                "slot_time": slot_time,
                "idempotency_key": idempotency_key,
                "status": existing_slot["status"]
            }

        cursor.execute(
            """
            INSERT INTO scheduled_slots (variant_id, slot_time, idempotency_key, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (variant_id, slot_time, idempotency_key)
        )
        slot_id = cursor.lastrowid
        conn.commit()

    return {
        "slot_id": slot_id,
        "variant_id": variant_id,
        "slot_time": slot_time,
        "idempotency_key": idempotency_key,
        "status": "pending"
    }

def execute_slot_publish(
    slot_id: int,
    adapter_id: Optional[str] = None,
    db_path: str = DATABASE_PATH
) -> Dict[str, Any]:
    """
    Executes publication for a specific scheduled slot:
    - Verifies exactly-once idempotency (avoids double-posting on retries)
    - Publishes through the SocialPublisher adapter interface
    - Records audit in publish_history
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.id as slot_id, s.variant_id, s.slot_time, s.idempotency_key, s.status as slot_status,
                   v.platform, v.content, v.hashtags, v.status as variant_status
            FROM scheduled_slots s
            JOIN variants v ON s.variant_id = v.id
            WHERE s.id = ?
            """,
            (slot_id,)
        )
        slot_row = cursor.fetchone()
        if not slot_row:
            raise ValueError(f"Scheduled slot {slot_id} not found.")

        slot = dict(slot_row)
        idemp_key = slot["idempotency_key"]

        # 1. Idempotency Gate: If this slot was already published, return cached history without re-publishing
        cursor.execute("SELECT * FROM publish_history WHERE idempotency_key = ? AND status = 'success'", (idemp_key,))
        existing_history = cursor.fetchone()
        if existing_history:
            return {
                "success": True,
                "is_duplicate": True,
                "message": f"[IDEMPOTENT RETRY] Slot {slot_id} already published.",
                "history_id": existing_history["id"],
                "live_post_url": existing_history["live_post_url"],
                "adapter_used": existing_history["adapter_used"]
            }

        # 2. Mark slot as publishing
        cursor.execute("UPDATE scheduled_slots SET status = 'publishing' WHERE id = ?", (slot_id,))
        conn.commit()

    # 3. Resolve publisher adapter (application depends strictly on SocialPublisher interface)
    publisher = get_publisher_adapter(adapter_id)
    hashtags = json.loads(slot["hashtags"]) if slot["hashtags"] else []

    # 4. Dispatch publish action
    result = publisher.publish(
        variant_id=slot["variant_id"],
        content=slot["content"],
        hashtags=hashtags,
        idempotency_key=idemp_key
    )

    # 5. Persist publish history & update statuses atomically
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        hist_status = "success" if result.success else "failed"

        cursor.execute(
            """
            INSERT INTO publish_history (
                slot_id, variant_id, platform, adapter_used, live_post_url, status, error_message, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slot["slot_id"],
                slot["variant_id"],
                result.platform,
                result.adapter_name,
                result.live_post_url,
                hist_status,
                result.error,
                idemp_key
            )
        )
        history_id = cursor.lastrowid

        if result.success:
            cursor.execute("UPDATE scheduled_slots SET status = 'completed' WHERE id = ?", (slot_id,))
            cursor.execute("UPDATE variants SET status = 'published' WHERE id = ?", (slot["variant_id"],))
        else:
            cursor.execute("UPDATE scheduled_slots SET status = 'failed' WHERE id = ?", (slot_id,))

        conn.commit()

    return {
        "success": result.success,
        "is_duplicate": False,
        "message": result.message,
        "history_id": history_id,
        "live_post_url": result.live_post_url,
        "adapter_used": result.adapter_name
    }

def run_scheduler_worker(
    adapter_id: Optional[str] = None,
    db_path: str = DATABASE_PATH
) -> Dict[str, Any]:
    """
    Durable scheduler worker:
    - Finds all pending or mid-crash 'publishing' slots
    - Safely executes them one-by-one with crash-recovery guarantees
    """
    now_iso = datetime.datetime.utcnow().isoformat()
    slots_to_process = []

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        # Find all pending or recovering slots
        cursor.execute(
            """
            SELECT id FROM scheduled_slots 
            WHERE status IN ('pending', 'publishing')
            ORDER BY id ASC
            """
        )
        slots_to_process = [r["id"] for r in cursor.fetchall()]

    processed = []
    for sid in slots_to_process:
        res = execute_slot_publish(sid, adapter_id, db_path)
        processed.append({"slot_id": sid, "result": res})

    return {
        "timestamp": now_iso,
        "total_processed": len(processed),
        "results": processed
    }

