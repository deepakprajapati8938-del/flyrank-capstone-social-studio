import hashlib
from typing import List
from app.adapters.base import SocialPublisher, PublishResult

class MockLinkedInPublisher(SocialPublisher):
    """Mock publisher for LinkedIn simulating UGC Post API."""

    @property
    def adapter_id(self) -> str:
        return "mock_linkedin"

    @property
    def platform_name(self) -> str:
        return "linkedin"

    def publish(
        self,
        variant_id: str,
        content: str,
        hashtags: List[str],
        idempotency_key: str
    ) -> PublishResult:
        tags_str = " ".join([f"#{t.lstrip('#')}" for t in hashtags])
        full_post = f"{content}\n\n{tags_str}".strip()

        urn_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
        live_url = f"https://www.linkedin.com/feed/update/urn:li:share:{urn_hash}"

        return PublishResult(
            success=True,
            live_post_url=live_url,
            platform=self.platform_name,
            adapter_name=self.adapter_id,
            message=f"Successfully simulated LinkedIn professional share. Length: {len(full_post)} chars."
        )

