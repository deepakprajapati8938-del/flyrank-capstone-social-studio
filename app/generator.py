import json
import uuid
from typing import Dict, Any, List
from app.config import DATABASE_PATH
from app.database import get_db
from app.profiles import validate_variant_against_profile

def generate_variants_for_post(post_id: str, db_path: str = DATABASE_PATH) -> List[Dict[str, Any]]:
    """
    Reads the stored blog post and generates platform-tailored variants
    conforming strictly to platform constraint profiles.
    """
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Post '{post_id}' not found.")
        post = dict(row)

    title = post["title"]
    content = post["content_markdown"]
    url = post.get("source_url") or "https://flyrank.ai/blog"

    # Extract short excerpt
    first_sentence = content.split(".")[0].strip()
    if len(first_sentence) > 120:
        first_sentence = first_sentence[:117] + "..."

    # 1. Platform Variant: X (Twitter) — strict <= 280 chars, 2 hashtags
    # Calculate available space: 280 - tags (approx 20) - url (approx 25) = ~235
    x_body = f"{title}: {first_sentence} Read more: {url}"
    if len(x_body) > 245:
        x_body = x_body[:242] + "..."
    x_hashtags = ["Backend", "Engineering"]

    # 2. Platform Variant: LinkedIn — 200-1500 chars, 3-5 hashtags, structured analysis
    li_body = (
        f"🚀 {title}\n\n"
        f"Key Engineering Takeaways:\n"
        f"• Architectural Reliability: System design must anticipate network retries and partial failures.\n"
        f"• Boundary Honesty: Enforce strict constraints before triggering downstream workflows.\n"
        f"• State Isolation: Single source of truth guarantees deterministic outcomes across platforms.\n\n"
        f"Full deep-dive article available here: {url}"
    )
    li_hashtags = ["SoftwareArchitecture", "BackendEngineering", "TechLeadership", "Reliability"]

    # 3. Platform Variant: Instagram — 100-1000 chars, 5-15 hashtags, conversational tone
    ig_body = (
        f"💡 Behind the Architecture: {title}\n\n"
        f"Building distributed systems that survive real-world chaos isn't about happy paths—it's about "
        f"graceful handling of retries, timeouts, and state machines.\n\n"
        f"Check out our latest post for the complete breakdown. Link in bio!"
    )
    ig_hashtags = ["CodingLife", "BackendDev", "SoftwareEngineering", "TechCommunity", "DevTips", "SystemDesign"]

    variants_to_create = [
        {"platform": "x", "content": x_body, "hashtags": x_hashtags},
        {"platform": "linkedin", "content": li_body, "hashtags": li_hashtags},
        {"platform": "instagram", "content": ig_body, "hashtags": ig_hashtags}
    ]

    saved_variants = []
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        for v in variants_to_create:
            # Validate against constraint profile
            is_valid, error = validate_variant_against_profile(v["platform"], v["content"], v["hashtags"])
            if not is_valid:
                raise ValueError(f"Generated variant failed constraint check: {error}")

            var_id = f"var_{v['platform']}_{uuid.uuid4().hex[:8]}"
            cursor.execute(
                """
                INSERT INTO variants (id, post_id, platform, content, hashtags, status, rejection_reason)
                VALUES (?, ?, ?, ?, ?, 'draft', NULL)
                """,
                (var_id, post_id, v["platform"], v["content"], json.dumps(v["hashtags"]))
            )
            saved_variants.append({
                "id": var_id,
                "post_id": post_id,
                "platform": v["platform"],
                "content": v["content"],
                "hashtags": v["hashtags"],
                "status": "draft"
            })
        conn.commit()

    return saved_variants

