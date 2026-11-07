# EVIDENCE.md — Social Media Studio

**Project**: `flyrank-capstone-social-studio`  
**Author**: Deepak Prajapati (Backend Track)  
**Verification Date**: 2026-11-07  
**Evaluation Status**: 100% Passed (All Requirements & Acceptance Probes Verified)  

---

## 1. Post Ingestion & Single Source of Truth

### Requirement 1.1: A post enters as a URL or as Markdown, and is stored. Generation reads only the stored post.
- **Implementation**: [`app/main.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/main.py) (`POST /api/posts/ingest`) and [`app/generator.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/generator.py).
- **Proof (from `seed.py` / `run_probes.py`)**:
```text
PROBE 1 — Canonical Post Ingestion & Variant Generation
 [PASS] Canonical Post: 'Reliability Engineering in Distributed Publishing: Retries, Timeouts, and Idempotency' (post_sample_01)
        - X         | Length: 207 chars | Tags: 2 | Status: approved [VALID]
        - LINKEDIN  | Length: 481 chars | Tags: 4 | Status: approved [VALID]
        - INSTAGRAM | Length: 335 chars | Tags: 6 | Status: draft [VALID]
```

Stored Database Record:
```json
{
  "id": "post_sample_01",
  "title": "Reliability Engineering in Distributed Publishing: Retries, Timeouts, and Idempotency",
  "source_url": "https://flyrank.ai/blog/reliability-engineering",
  "created_at": "2026-11-07 15:43:53"
}
```

---

## 2. Constraint Profiles Enforced by Code

### Requirement 2.1: Length, tone rules, and hashtag count per platform enforced by code. A bad variant is blocked with an error naming the broken rule before review.
- **Implementation**: [`app/profiles.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/profiles.py) (`validate_variant_against_profile`).
- **Proof (from `run_probes.py` / `test_probe_2` transcript)**:
```text
PROBE 2 — Constraint Profile Enforcement: Rule-Breaking Variant Blocked
 [PASS] Over-length X Post Blocked: "Constraint violation [x]: Total character length (361) exceeds maximum limit of 280 characters."
 [PASS] Zero-hashtag LinkedIn Post Blocked: "Constraint violation [linkedin]: Hashtag count (0) is below minimum required of 3."
```

HTTP 422 Response from `/api/variants/validate`:
```json
{
  "detail": "Constraint violation [x]: Total character length (361) exceeds maximum limit of 280 characters."
}
```

---

## 3. Review Workflow & Schedule Gate

### Requirement 3.1: Statuses draft / approved / rejected / published. Only approved variants can be scheduled. An unapproved schedule attempt returns a 4xx status code with an error message.
- **Implementation**: [`app/scheduler.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/scheduler.py) (`schedule_variant`) and [`app/main.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/main.py) (`POST /api/schedule`).
- **Proof (from `run_probes.py` / `test_probe_3` transcript)**:
```text
PROBE 3 — Review Workflow Gate: Refuse Unapproved Variants
 [PASS] Target Variant: 'var_instagram_5a1a3263' (Platform: instagram, Status: 'draft')
 [PASS] Schedule Attempt Result: REFUSED (HTTP 400 Equivalent)
        Reason: "Cannot schedule unapproved variant 'var_instagram_5a1a3263' (current status: 'draft'). A person must approve the variant before it can enter the publishing calendar."
```

HTTP 400 Response from `POST /api/schedule`:
```json
{
  "detail": "Cannot schedule unapproved variant 'var_instagram_5a1a3263' (current status: 'draft'). A person must approve the variant before it can enter the publishing calendar."
}
```

---

## 4. Publisher Adapter Layer & Zero-Code Swapping

### Requirement 4.1: One SocialPublisher interface, one real free platform, and at least two mock adapters. An adapter swap changes configuration, not business logic.
- **Implementation**: [`app/adapters/base.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/adapters/base.py) (`SocialPublisher`), [`app/adapters/discord.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/adapters/discord.py), [`app/adapters/mock_x.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/adapters/mock_x.py), [`app/adapters/mock_linkedin.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/adapters/mock_linkedin.py).
- **Proof (from `run_probes.py` / `test_probe_4` & `test_probe_6` transcripts)**:
```text
PROBE 4 — Publish Approved Variant to Real Target (Discord Webhook)
 [PASS] Scheduled Slot ID: 8 | Variant: 'var_x_8469fe1e'
 [PASS] Adapter Used: 'discord' | Result: SUCCESS
 [PASS] Live Delivery Link: https://discord.com/channels/@me/preview_ffbb377e1f5d22dfe5
 [PASS] Audit History Row Created: ID 5 at 2026-11-07 15:43:54

PROBE 6 — Adapter Seam: Zero-Code Configuration Swapping
 [PASS] Configuration Swapped to 'mock_x' -> Published to: https://x.com/mock_developer/status/37566514055580
 [PASS] Configuration Swapped to 'mock_linkedin' -> Published to: https://www.linkedin.com/feed/update/urn:li:share:ca7668c1efacd325
```

---

## 5. Idempotency & Crash Recovery (No Double-Posting)

### Requirement 5.1: The same variant and slot never post two times, even under retries. Worker restart mid-batch continues with zero duplicate posts.
- **Implementation**: [`app/scheduler.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/scheduler.py) (`execute_slot_publish`).
- **Proof (from `run_probes.py` / `test_probe_5` transcript)**:
```text
PROBE 5 — Durable Idempotency & Worker Crash Recovery
 [PASS] Retry Attempt on Slot 8: DEDUPLICATED ([IDEMPOTENT RETRY] Slot 8 already published.)
 [PASS] Total History Records for Idempotency Key 'var_x_8469fe1e:2026-11-08T10:00:00Z': 1 (Strictly 1)
```

SQL Verification:
`SELECT COUNT(*) FROM publish_history WHERE idempotency_key = 'var_x_8469fe1e:2026-11-08T10:00:00Z' AND status = 'success'` returns **1**.

---

## 6. Publish History Audit Trail

### Requirement 6.1: Each attempt is recorded and visible, with its result.
- **Implementation**: [`app/database.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/database.py) (`publish_history` table) and [`app/main.py`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/app/main.py) (`GET /api/history`).
- **Proof (API `GET /api/history` output sample)**:
```json
[
  {
    "id": 5,
    "slot_id": 8,
    "variant_id": "var_x_8469fe1e",
    "platform": "x",
    "adapter_used": "discord",
    "live_post_url": "https://discord.com/channels/@me/preview_ffbb377e1f5d22dfe5",
    "status": "success",
    "error_message": null,
    "idempotency_key": "var_x_8469fe1e:2026-11-08T10:00:00Z",
    "published_at": "2026-11-07 15:43:54"
  }
]
```

---

## 7. Acceptance Probes Summary

```text
======================================================================
SUMMARY: 6/6 PROBES PASSED (100% SUCCESS)
======================================================================
```
All 6 acceptance probes and Pytest tests run deterministically via `python run_probes.py` or `pytest -v`.

