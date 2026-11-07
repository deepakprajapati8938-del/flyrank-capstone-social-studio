# DESIGN.md — Social Media Studio

**Project**: `flyrank-capstone-social-studio`  
**Author**: Deepak Prajapati (Backend Track)  
**Status**: Approved (Phase 1 Gate Complete)  

---

## 1. Problem Statement & Mission

Marketing and editorial teams publish blog articles that need distribution across multiple social platforms. However, existing publishing tools fail in production:
1. **Rule Violations**: Platforms have strict rules (e.g., X limits posts to 280 characters, LinkedIn expects professional analysis, Instagram requires hashtags). Sending inappropriate lengths or formats triggers platform API rejections.
2. **Accidental Publishing**: Unapproved drafts get scheduled and published automatically without human sign-off.
3. **Double-Posting Bugs**: Network retries or crashed background workers re-publish the same content multiple times, spamming customer social feeds.
4. **Tightly-Coupled Platform Code**: Modifying or adding a social platform requires rewriting core application logic.

### Mission:
Build a reliable multi-platform social campaign publisher that:
- Ingests blog articles as the single source of truth.
- Generates platform-specific variants enforced by strict **Constraint Profiles**.
- Enforces an unbreakable **Review Workflow** (`draft` -> `approved` -> `published`), refusing to schedule any unapproved variant.
- Publishes through a clean **`SocialPublisher` Adapter Layer** with zero business logic dependencies on specific platform APIs.
- Provides **Durable, Idempotent Scheduling** ensuring that retries or worker restarts produce exactly one post per slot.

---

## 2. Platform Constraint Profiles

| Platform | Min Length | Max Length | Target Tone | Allowed Hashtags | Safe Zone Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **X (Twitter)** | 10 chars | 280 chars | Punchy, direct, urgent | 1 to 2 hashtags | Compact single thought |
| **LinkedIn** | 200 chars | 1,500 chars | Professional, insightful, analytical | 3 to 5 hashtags | Thought leadership & takeaways |
| **Instagram** | 100 chars | 1,000 chars | Visual, conversational, engaging | 5 to 15 hashtags | Caption narrative with call-to-action |

### Validation Gate:
Before a generated variant enters the review queue, `ConstraintValidator` validates the text against the platform profile. Any violation (e.g. text length > 280 on X or < 3 hashtags on LinkedIn) is rejected with an explicit error message naming the violated constraint.

---

## 3. Review Workflow State Machine

```
              ┌───────────────┐
              │     draft     │
              └───────┬───────┘
                      │
           [ Human Editor Action ]
           ├── Approve ──► status: "approved"
           └── Reject  ──► status: "rejected"
                      │
                      ▼
              ┌───────────────┐
              │   approved    │
              └───────┬───────┘
                      │
           [ Schedule in Slot ]
                      │
                      ▼
              ┌───────────────┐
              │   scheduled   │
              └───────┬───────┘
                      │
             [ Worker Executes ]
                      ├── Success ──► status: "published"
                      └── Error   ──► status: "failed"
```

### Safety Rule:
Only variants with `status == "approved"` can be scheduled. Attempting to schedule a `draft` or `rejected` variant returns **HTTP 400 Bad Request** with an explicit error message.

---

## 4. Publisher Adapter Layer

```
                        ┌───────────────────────────────┐
                        │        SocialPublisher        │
                        │      (Abstract Interface)     │
                        └───────────────┬───────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│DiscordWebhookPublisher│    │    MockXPublisher    │     │MockLinkedInPublisher │
├──────────────────────┤     ├──────────────────────┤     ├──────────────────────┤
│ Live delivery to     │     │ Persists to DB,      │     │ Persists to DB,      │
│ Discord channel      │     │ renders 280-char     │     │ renders formatted    │
│ webhook URL          │     │ visual preview       │     │ executive article    │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

The application interacts strictly with `SocialPublisher`. Swapping the active publisher from `discord` to `mock_x` or `mock_linkedin` requires changing a single configuration key (`DEFAULT_PUBLISHER_ADAPTER`), modifying zero business logic.

---

## 5. Durable Scheduling & Idempotency

### Slot Idempotency Key:
Each publish slot generates a deterministic key:
$$\text{idempotency\_key} = \text{hash}(\text{variant\_id} + \text{slot\_time})$$

### Exactly-Once Execution:
1. When worker wakes to process due slots, it checks `publish_history` for `idempotency_key`.
2. If already published, it marks the slot complete and skips publication.
3. If unperformed, it executes the adapter's `publish()` call and logs the result atomically in `publish_history`.
4. If a worker crashes mid-batch, restarting the worker safely inspects the state; already completed slots are bypassed, and pending slots resume with zero duplicate posts.

---

## 6. Database Schema

```
┌───────────────────────────┐         ┌───────────────────────────┐
│           posts           │         │         variants          │
├───────────────────────────┤         ├───────────────────────────┤
│ id (PK, TEXT)             │         │ id (PK, TEXT)             │
│ title (TEXT)              │◄────────┤ post_id (FK, TEXT)        │
│ content_markdown (TEXT)   │    1:N  │ platform (TEXT: x/li/ig)  │
│ source_url (TEXT)         │         │ content (TEXT)            │
│ created_at (DATETIME)     │         │ hashtags (TEXT: JSON)     │
└───────────────────────────┘         │ status (TEXT: draft/appr) │
                                      │ rejection_reason (TEXT)   │
                                      │ created_at (DATETIME)     │
                                      └─────────────┬─────────────┘
                                                    │ 1:N
                                                    ▼
┌───────────────────────────┐         ┌───────────────────────────┐
│      scheduled_slots      │         │      publish_history      │
├───────────────────────────┤         ├───────────────────────────┤
│ id (PK, INTEGER)          │         │ id (PK, INTEGER)          │
│ variant_id (FK, TEXT)     │◄────────┤ slot_id (FK, INTEGER)     │
│ slot_time (DATETIME)      │    1:N  │ variant_id (FK, TEXT)     │
│ idempotency_key (TEXT)    │         │ platform (TEXT)           │
│ status (TEXT)             │         │ adapter_used (TEXT)       │
│ created_at (DATETIME)     │         │ live_post_url (TEXT)      │
└───────────────────────────┘         │ status (TEXT: success/err)│
                                      │ published_at (DATETIME)   │
                                      └───────────────────────────┘
```

---

## 7. Explicit Non-Goals
1. **No Paid Social Platform Subscriptions**: No real X API developer tier ($100/mo) or LinkedIn marketing partner approval required. We use one real free platform (Discord/Telegram webhook) plus realistic local mock adapters.
2. **No Video Transcoding Engine**: System focuses strictly on text variants, hashtag profiles, and link previews.
3. **No Heavy Frontend Framework**: Review workflow and scheduling are driven through clean REST API endpoints and lightweight interactive dashboards.
