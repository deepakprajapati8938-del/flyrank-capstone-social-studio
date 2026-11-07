from typing import List, Optional
from pydantic import BaseModel, Field

class PostIngestRequest(BaseModel):
    title: str = Field(..., min_length=3, description="Article title")
    content_markdown: str = Field(..., min_length=20, description="Full article markdown content")
    source_url: Optional[str] = Field(default=None, description="Original canonical URL")

class PostResponse(BaseModel):
    id: str
    title: str
    content_markdown: str
    source_url: Optional[str]
    created_at: str

class VariantCreateRequest(BaseModel):
    content: str = Field(..., min_length=5, description="Variant text")
    hashtags: List[str] = Field(default_factory=list, description="Associated hashtags without #")

class VariantResponse(BaseModel):
    id: str
    post_id: str
    platform: str
    content: str
    hashtags: List[str]
    status: str # "draft" | "approved" | "rejected" | "published"
    rejection_reason: Optional[str] = None
    created_at: str

class ReviewActionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    rejection_reason: Optional[str] = None

class ScheduleSlotRequest(BaseModel):
    variant_id: str = Field(..., description="ID of the approved variant to schedule")
    slot_time: str = Field(..., description="ISO 8601 timestamp for publication")

class ScheduleSlotResponse(BaseModel):
    slot_id: int
    variant_id: str
    slot_time: str
    idempotency_key: str
    status: str

class PublishHistoryEntry(BaseModel):
    id: int
    slot_id: Optional[int]
    variant_id: str
    platform: str
    adapter_used: str
    live_post_url: Optional[str]
    status: str
    error_message: Optional[str]
    idempotency_key: str
    published_at: str

