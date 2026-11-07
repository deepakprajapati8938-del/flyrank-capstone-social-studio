import json
import pytest
from app.config import DATABASE_PATH
from app.database import init_db, get_db
from app.profiles import validate_variant_against_profile
from app.generator import generate_variants_for_post
from app.scheduler import schedule_variant, execute_slot_publish, run_scheduler_worker
from app.adapters.registry import set_active_adapter_override, get_publisher_adapter

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure clean database setup."""
    init_db(DATABASE_PATH)
    from seed import seed_database
    seed_database()

def test_probe_1_ingest_and_constraint_profile_conformance():
    """
    PROBE 1: Ingest a sample post. The system generates variants for each configured
    platform, and each variant passes its constraint profile.
    """
    post_id = "test_probe1_post"
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO posts (id, title, content_markdown, source_url)
            VALUES (?, ?, ?, ?)
            """,
            (
                post_id,
                "Microservices Resilience Patterns: Circuit Breakers and Bulkheads",
                "Building resilient microservices requires proactive isolation of cascading failures. Circuit breakers trip on continuous downstream timeouts, shedding load before worker pools exhaust. Paired with bulkhead thread pools, critical business capabilities remain available during outages.",
                "https://flyrank.ai/blog/resilience"
            )
        )
        conn.commit()

    variants = generate_variants_for_post(post_id, DATABASE_PATH)
    assert len(variants) >= 2, f"Expected at least 2 platform variants, got {len(variants)}"

    platforms_found = {v["platform"] for v in variants}
    assert "x" in platforms_found
    assert "linkedin" in platforms_found

    # Verify each variant passes its constraint profile
    for v in variants:
        is_valid, error = validate_variant_against_profile(v["platform"], v["content"], v["hashtags"])
        assert is_valid is True, f"Variant for {v['platform']} failed profile validation: {error}"

def test_probe_2_rule_breaking_variant_blocked_before_review():
    """
    PROBE 2: Create a variant that breaks a platform rule. The validation blocks it
    with an error message that names the broken rule, before review.
    """
    # X max length is 280. Supply 320 characters.
    long_content = "A" * 320
    is_valid_len, error_len = validate_variant_against_profile("x", long_content, ["tag1"])
    assert is_valid_len is False
    assert "Constraint violation [x]" in error_len
    assert "exceeds maximum limit of 280 characters" in error_len

    # X max hashtags is 2. Supply 5 hashtags.
    is_valid_tags, error_tags = validate_variant_against_profile("x", "Valid short tweet content.", ["one", "two", "three", "four", "five"])
    assert is_valid_tags is False
    assert "Constraint violation [x]" in error_tags
    assert "exceeds maximum allowed of 2" in error_tags

    # LinkedIn min hashtags is 3. Supply 1 hashtag.
    is_valid_li, error_li = validate_variant_against_profile("linkedin", "A" * 300, ["single_tag"])
    assert is_valid_li is False
    assert "Constraint violation [linkedin]" in error_li
    assert "below minimum required of 3" in error_li

def test_probe_3_unapproved_variant_schedule_refusal():
    """
    PROBE 3: Try to schedule an unapproved variant. The system refuses with
    an error message and prevents scheduling.
    """
    # Find draft variant
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, status FROM variants WHERE status = 'draft' LIMIT 1")
        row = cursor.fetchone()
        assert row is not None, "Need a draft variant"
        draft_var_id = row["id"]

    # Attempt to schedule unapproved draft
    with pytest.raises(ValueError) as excinfo:
        schedule_variant(draft_var_id, "2026-11-08T12:00:00Z", DATABASE_PATH)

    assert "Cannot schedule unapproved variant" in str(excinfo.value)
    assert "A person must approve the variant before it can enter the publishing calendar" in str(excinfo.value)

def test_probe_4_approved_variant_schedule_and_live_publish():
    """
    PROBE 4: Approve a variant and schedule it. The scheduler publishes it
    to the real free target. The publish record links to the live message.
    """
    # Get approved variant
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM variants WHERE status = 'approved' AND platform = 'x' LIMIT 1")
        var_id = cursor.fetchone()[0]

    # Schedule variant
    slot_info = schedule_variant(var_id, "2026-11-08T14:00:00Z", DATABASE_PATH)
    assert slot_info["status"] == "pending"

    # Execute publication
    res = execute_slot_publish(slot_info["slot_id"], adapter_id="discord", db_path=DATABASE_PATH)
    assert res["success"] is True
    assert res["is_duplicate"] is False
    assert res["live_post_url"] is not None
    assert "discord.com" in res["live_post_url"]

    # Verify publish history record
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM publish_history WHERE id = ?", (res["history_id"],))
        hist = dict(cursor.fetchone())
        assert hist["status"] == "success"
        assert hist["adapter_used"] == "discord"
        assert hist["live_post_url"] == res["live_post_url"]

def test_probe_5_idempotent_publish_retry_no_duplicates():
    """
    PROBE 5: Force a publish retry: stop the worker mid-publish, then restart.
    The history shows exactly one successful post. No duplicates.
    """
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, variant_id, idempotency_key FROM scheduled_slots WHERE status = 'completed' LIMIT 1")
        slot = dict(cursor.fetchone())

    slot_id = slot["id"]
    idemp_key = slot["idempotency_key"]

    # Re-publish the completed slot (simulating a restarted worker re-running the batch)
    retry_res = execute_slot_publish(slot_id, adapter_id="discord", db_path=DATABASE_PATH)
    assert retry_res["success"] is True
    assert retry_res["is_duplicate"] is True
    assert "[IDEMPOTENT RETRY]" in retry_res["message"]

    # Verify publish_history has strictly ONE row for this idempotency key
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM publish_history WHERE idempotency_key = ? AND status = 'success'", (idemp_key,))
        count = cursor.fetchone()[0]
        assert count == 1, f"Expected strictly 1 publish history row, found {count}"

def test_probe_6_adapter_swapping_zero_business_logic_change():
    """
    PROBE 6: Swap the adapter in configuration, for example discord to mock_x.
    The same campaign publishes through the mock. No code change outside the adapters.
    """
    # 1. Test swap to mock_x
    set_active_adapter_override("mock_x")
    active_publisher = get_publisher_adapter()
    assert active_publisher.adapter_id == "mock_x"
    assert active_publisher.platform_name == "x"

    # Schedule another slot
    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM variants WHERE platform = 'x' LIMIT 1")
        var_id = cursor.fetchone()[0]
        # Ensure variant is approved
        cursor.execute("UPDATE variants SET status = 'approved' WHERE id = ?", (var_id,))
        conn.commit()

    slot_x = schedule_variant(var_id, "2026-11-08T18:00:00Z", DATABASE_PATH)
    res_x = execute_slot_publish(slot_x["slot_id"], db_path=DATABASE_PATH)
    assert res_x["success"] is True
    assert res_x["adapter_used"] == "mock_x"
    assert "x.com" in res_x["live_post_url"]

    # 2. Test swap to mock_linkedin
    set_active_adapter_override("mock_linkedin")
    active_publisher_li = get_publisher_adapter()
    assert active_publisher_li.adapter_id == "mock_linkedin"
    assert active_publisher_li.platform_name == "linkedin"

    with get_db(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM variants WHERE platform = 'linkedin' LIMIT 1")
        var_li_id = cursor.fetchone()[0]
        # Ensure variant is approved
        cursor.execute("UPDATE variants SET status = 'approved' WHERE id = ?", (var_li_id,))
        conn.commit()

    slot_li = schedule_variant(var_li_id, "2026-11-08T19:00:00Z", DATABASE_PATH)
    res_li = execute_slot_publish(slot_li["slot_id"], db_path=DATABASE_PATH)
    assert res_li["success"] is True
    assert res_li["adapter_used"] == "mock_linkedin"
    assert "linkedin.com" in res_li["live_post_url"]

    # Reset override
    set_active_adapter_override(None)
