import json
import uuid
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import DATABASE_PATH, DEFAULT_PUBLISHER_ADAPTER
from app.database import init_db, get_db
from app.models import (
    PostIngestRequest, PostResponse, VariantResponse,
    ReviewActionRequest, ScheduleSlotRequest, ScheduleSlotResponse,
    PublishHistoryEntry
)
from app.profiles import validate_variant_against_profile, CONSTRAINT_PROFILES
from app.generator import generate_variants_for_post
from app.scheduler import schedule_variant, run_scheduler_worker, execute_slot_publish
from app.adapters.registry import ADAPTERS, set_active_adapter_override, get_publisher_adapter

# Initialize database
init_db(DATABASE_PATH)

app = FastAPI(
    title="Social Media Studio",
    description="Multi-platform social campaign publisher: constraint profiles, review workflows, adapter architecture, and durable idempotent scheduling.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["General"])
def read_root():
    return {
        "service": "Social Media Studio",
        "status": "online",
        "active_adapter": get_publisher_adapter().adapter_id,
        "endpoints": {
            "ingest_post": "POST /api/posts/ingest",
            "list_posts": "GET /api/posts",
            "review_variant": "POST /api/variants/{id}/review",
            "schedule_variant": "POST /api/schedule",
            "run_scheduler": "POST /api/scheduler/run",
            "publish_history": "GET /api/history",
            "adapters": "GET /api/adapters"
        }
    }

@app.get("/health", tags=["General"])
def health_check():
    return {"status": "healthy", "database": "connected"}

# -------------------------------------------------------------
# Post Ingestion & Generation Endpoints
# -------------------------------------------------------------

@app.post("/api/posts/ingest", status_code=status.HTTP_201_CREATED, tags=["Ingestion"])
def ingest_blog_post(req: PostIngestRequest):
    """
    Ingests a blog post as the single source of truth and automatically
    generates platform-tailored variants conforming to platform constraint profiles.
    """
    post_id = f"post_{uuid.uuid4().hex[:8]}"
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO posts (id, title, content_markdown, source_url)
            VALUES (?, ?, ?, ?)
            """,
            (post_id, req.title, req.content_markdown, req.source_url)
        )
        conn.commit()

    # Generate variants from stored post
    variants = generate_variants_for_post(post_id, DATABASE_PATH)

    return {
        "status": "ingested",
        "post_id": post_id,
        "title": req.title,
        "variants_generated": len(variants),
        "variants": variants
    }

@app.get("/api/posts", tags=["Ingestion"])
def list_posts():
    """Lists stored posts."""
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts ORDER BY created_at DESC")
        return [dict(r) for r in cursor.fetchall()]

@app.get("/api/posts/{post_id}/variants", tags=["Variants"])
def get_post_variants(post_id: str):
    """Lists all generated variants for a post."""
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM variants WHERE post_id = ?", (post_id,))
        rows = cursor.fetchall()
        variants = []
        for r in rows:
            d = dict(r)
            d["hashtags"] = json.loads(d["hashtags"]) if d.get("hashtags") else []
            variants.append(d)
        return variants

# -------------------------------------------------------------
# Constraint Validation Endpoint
# -------------------------------------------------------------

@app.post("/api/variants/validate", tags=["Constraint Profiles"])
def validate_variant_endpoint(platform: str, content: str, hashtags: List[str] = Query(default=[])):
    """
    Tests text against platform constraint profiles.
    Returns 200 if valid, or 422 Unprocessable Entity if constraints are violated.
    """
    is_valid, error = validate_variant_against_profile(platform, content, hashtags)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)
    return {"valid": True, "platform": platform, "message": "Content strictly satisfies constraint profile."}

# -------------------------------------------------------------
# Review Workflow Endpoints
# -------------------------------------------------------------

@app.post("/api/variants/{variant_id}/review", tags=["Review Workflow"])
def review_variant(variant_id: str, action_req: ReviewActionRequest):
    """
    Human review gate: an editor approves or rejects a generated variant.
    Only approved variants can be scheduled for publication.
    """
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM variants WHERE id = ?", (variant_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Variant '{variant_id}' not found.")

        new_status = "approved" if action_req.action == "approve" else "rejected"
        reason = action_req.rejection_reason if action_req.action == "reject" else None

        cursor.execute(
            "UPDATE variants SET status = ?, rejection_reason = ? WHERE id = ?",
            (new_status, reason, variant_id)
        )
        conn.commit()

    return {"status": "updated", "variant_id": variant_id, "new_status": new_status}

# -------------------------------------------------------------
# Scheduling & Execution Endpoints
# -------------------------------------------------------------

@app.post("/api/schedule", response_model=ScheduleSlotResponse, tags=["Scheduling"])
def schedule_post(req: ScheduleSlotRequest):
    """
    Places an approved variant into the publishing calendar.
    Rejects unapproved variants with HTTP 400 Bad Request.
    """
    try:
        slot = schedule_variant(req.variant_id, req.slot_time, DATABASE_PATH)
        return ScheduleSlotResponse(**slot)
    except ValueError as ve:
        # Honest boundary rejection
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

@app.get("/api/schedule", tags=["Scheduling"])
def list_scheduled_slots():
    """Lists calendar slots with status."""
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_slots ORDER BY slot_time ASC")
        return [dict(r) for r in cursor.fetchall()]

@app.post("/api/scheduler/run", tags=["Scheduling"])
def trigger_scheduler_run(adapter_override: Optional[str] = None):
    """Triggers durable scheduler worker to process due slots."""
    result = run_scheduler_worker(adapter_override, DATABASE_PATH)
    return result

@app.post("/api/slots/{slot_id}/publish-now", tags=["Scheduling"])
def force_slot_publish(slot_id: int, adapter_override: Optional[str] = None):
    """Forces execution of a specific slot (used for testing idempotency and retries)."""
    try:
        res = execute_slot_publish(slot_id, adapter_override, DATABASE_PATH)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))

# -------------------------------------------------------------
# Publish History & Adapters Endpoints
# -------------------------------------------------------------

@app.get("/api/history", tags=["Publish History"])
def get_publish_history():
    """Inspects all completed and attempted publish actions."""
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM publish_history ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]

@app.get("/api/adapters", tags=["Adapters"])
def list_adapters():
    """Lists registered SocialPublisher adapters and active selection."""
    active = get_publisher_adapter()
    return {
        "active_adapter": active.adapter_id,
        "registered_adapters": [
            {"adapter_id": a.adapter_id, "platform": a.platform_name}
            for a in ADAPTERS.values()
        ]
    }

@app.post("/api/adapters/select", tags=["Adapters"])
def select_active_adapter(adapter_id: str):
    """
    Swaps the active SocialPublisher adapter configuration (e.g. from discord to mock_x).
    Touches ZERO business logic!
    """
    try:
        # verify exists
        get_publisher_adapter(adapter_id)
        set_active_adapter_override(adapter_id)
        return {"status": "swapped", "active_adapter": adapter_id}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
