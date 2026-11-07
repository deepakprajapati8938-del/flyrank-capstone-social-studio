# Social Media Studio — Multi-Platform Campaign Publisher

[![Acceptance Probes](https://img.shields.io/badge/Probes-6%2F6%20Passed-brightgreen)](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/EVIDENCE.md)
[![Pytest](https://img.shields.io/badge/Pytest-6%2F6%20Passed-blue)](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/tests/test_acceptance_probes.py)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Zero Cost](https://img.shields.io/badge/%240%20Stack-No%20Credit%20Card-success)](#)

> **FlyRank Backend Track Capstone Project**  
> **Author**: Deepak Prajapati ([Portfolio](https://internship-badge.netlify.app/verify/deepakprajapati) · [GitHub](https://github.com/deepakprajapati8938-del))  
> **Mission**: Turn one published blog post into a multi-platform social media campaign: platform-tailored variants, code-enforced constraint profiles, a strict human review workflow, an adapter layer with zero business-logic coupling, and durable, idempotent scheduling that guarantees zero duplicate posts under retries.

---

## 1. Executive Summary

Publishing to social media in enterprise environments involves significant reliability challenges:
- Posts violating platform character limits or hashtag guidelines trigger immediate API rejections.
- Unapproved drafts accidentally get published by automated schedulers.
- Network timeouts and crashed workers cause double-posting on retries.
- Applications tightly couple platform APIs directly into business logic.

**Social Media Studio** provides an industrial-grade publishing engine:
- **Canonical Ingestion**: Stored blog posts act as the immutable single source of truth for all variant generation.
- **Constraint Profiles**: Strict, code-enforced character length boundaries and hashtag rules per platform. Violations are blocked before reaching review.
- **Review Workflow Gate**: Hard state machine (`draft` -> `approved` | `rejected` -> `published`). Unapproved variants cannot be scheduled (HTTP 400 Bad Request).
- **Publisher Adapter Seam**: Standardized `SocialPublisher` interface with one real free target (Discord Webhooks) and two mock adapters (`MockXPublisher`, `MockLinkedInPublisher`). Adapters can be swapped via configuration with zero code changes.
- **Durable Idempotency & Crash Recovery**: State-backed time slots with composite idempotency keys (`variant_id:slot_time`). Worker restarts mid-batch resume safely with **exactly-once publishing**.

---

## 2. Architecture & Data Flow

```
     [ Blog Post: URL or Markdown ]
                   │
                   ▼
     ┌────────────────────────────┐
     │ Ingestion & Single Truth   │
     │   (SQLite `posts` table)   │
     └─────────────┬──────────────┘
                   │
                   ▼
     ┌────────────────────────────┐
     │ Variant Generator Engine   │
     │  (X, LinkedIn, Instagram)  │
     └─────────────┬──────────────┘
                   │
                   ▼
     ┌────────────────────────────┐
     │ Constraint Profile Check   │
     │  - Max/Min Chars (e.g. 280)│
     │  - Hashtag Limits (e.g. 2) │
     └─────────────┬──────────────┘
                   ├── Invalid ──► Blocked (HTTP 422)
                   └── Valid
                        │
                        ▼
     ┌────────────────────────────┐
     │   Review Workflow Gate     │
     │ (draft -> approved/reject) │
     └─────────────┬──────────────┘
                   ├── Unapproved ──► Schedule Blocked (HTTP 400)
                   └── Approved
                        │
                        ▼
     ┌────────────────────────────┐
     │ Durable Calendar Scheduler │
     │  - Idempotency Key Gate    │
     │  - Crash Recovery State    │
     └─────────────┬──────────────┘
                   │
                   ▼
     ┌────────────────────────────┐
     │  SocialPublisher Interface │
     ├────────────────────────────┤
     │ + Discord Webhook (Real)   │
     │ + MockXPublisher           │
     │ + MockLinkedInPublisher    │
     └─────────────┬──────────────┘
                   │
                   ▼
     ┌────────────────────────────┐
     │ Publish History Audit Trail│
     │  (One slot = exactly 1 post│
     └────────────────────────────┘
```

---

## 3. Platform Constraint Profiles

| Platform | Min Chars | Max Chars | Tone / Style | Hashtags Limit | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **X (Twitter)** | 10 | 280 | Punchy, direct, urgent | 0 to 2 tags | Hard limit: text + tags ≤ 280 chars |
| **LinkedIn** | 150 | 1,500 | Professional, analytical | 3 to 5 tags | Thought leadership & takeaways |
| **Instagram** | 100 | 1,000 | Visual, storytelling | 5 to 15 tags | Engaging narrative with CTA |

---

## 4. Quickstart Guide (Reproducible by a Stranger)

### Prerequisites
- Python 3.10+ (Tested on Python 3.11)
- Git

### 1. Setup & Installation
```bash
git clone https://github.com/deepakprajapati8938-del/flyrank-capstone-social-studio.git
cd flyrank-capstone-social-studio

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 2. Seed Demo Data
Initializes SQLite schema, ingests sample blog post, generates variants, and pre-schedules demo slots:
```bash
python seed.py
```

### 3. Run Acceptance Probes Suite
Validates all 6 capstone acceptance probes end-to-end:
```bash
python run_probes.py
# Or run with pytest:
pytest -v
```

### 4. Start API Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger API documentation available at: **`http://localhost:8000/docs`**

---

## 5. API Reference & Usage Examples

### 1. Ingest Canonical Blog Post
```bash
curl -X POST "http://localhost:8000/api/posts/ingest" \
     -H "Content-Type: application/json" \
     -d '{
       "title": "Architecting Durable Schedulers",
       "content_markdown": "Full article markdown body explaining idempotency and crash recovery...",
       "source_url": "https://flyrank.ai/blog/durable-schedulers"
     }'
```

### 2. Validate Variant Text against Constraint Profile
```bash
curl -X POST "http://localhost:8000/api/variants/validate?platform=x&content=Short%20punchy%20tweet&hashtags=Tech"
```

### 3. Human Review Gate (Approve Variant)
```bash
curl -X POST "http://localhost:8000/api/variants/var_x_8469fe1e/review" \
     -H "Content-Type: application/json" \
     -d '{"action": "approve"}'
```

### 4. Schedule Approved Variant
```bash
curl -X POST "http://localhost:8000/api/schedule" \
     -H "Content-Type: application/json" \
     -d '{
       "variant_id": "var_x_8469fe1e",
       "slot_time": "2026-11-08T10:00:00Z"
     }'
```

### 5. Trigger Durable Scheduler Worker
```bash
curl -X POST "http://localhost:8000/api/scheduler/run"
```

### 6. Swap Active Publisher Adapter via Configuration
```bash
curl -X POST "http://localhost:8000/api/adapters/select?adapter_id=mock_linkedin"
```

---

## 6. Honest Limitations & Edge Cases

1. **Platform Policy Volatility**: Real social media platform limits (e.g. X algorithm character counters for emojis vs URLs) frequently change. Our engine utilizes strict standard unicode length checks.
2. **Calendar Slot Granularity**: Scheduled slots are defined down to the minute. High-frequency sub-second slot clustering is outside project scope.
3. **Webhook Callback Ingestion**: For platforms sending asynchronous delivery callbacks, our webhook receiver validates events before flipping the final delivery state.

---

## 7. Evaluator Manifest & Pack Structure

- [`capstone.yaml`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/capstone.yaml): Automated runner configuration.
- [`DESIGN.md`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/DESIGN.md): Phase 1 architecture design doc.
- [`EVIDENCE.md`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/EVIDENCE.md): Verbatim command output proofs for all 6 acceptance probes.
- [`BUILDLOG.md`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/BUILDLOG.md): AI transparency disclosure and code defense.
- [`.env.example`](file:///x:/Medicaps/Internship/flyrank-capstone-social-studio/.env.example): Safe environment variable defaults.
