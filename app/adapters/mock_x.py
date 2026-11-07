import hashlib
from typing import List
from app.adapters.base import SocialPublisher, PublishResult

class MockXPublisher(SocialPublisher):
    """Mock publisher for X (Twitter) simulating API v2 endpoints."""

    @property
    def adapter_id(self) -> str:
        return "mock_x"

    @property
    def platform_name(self) -> str:
        return "x"

    def publish(
        self,
        variant_id: str,
        content: str,
        hashtags: List[str],
        idempotency_key: str
    ) -> PublishResult:
        tags_str = " ".join([f"#{t.lstrip('#')}" for t in hashtags])
        full_tweet = f"{content} {tags_str}".strip()

        # Deterministic tweet snowflake ID from idempotency key
        snowflake_id = int(hashlib.md5(idempotency_key.encode()).hexdigest()[:12], 16)
        live_url = f"https://x.com/mock_developer/status/{snowflake_id}"

        return PublishResult(
            success=True,
            live_post_url=live_url,
            platform=self.platform_name,
            adapter_name=self.adapter_id,
            message=f"Successfully simulated tweet publication on X. Length: {len(full_tweet)} chars."
        )

