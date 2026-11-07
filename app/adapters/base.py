from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class PublishResult:
    success: bool
    live_post_url: Optional[str]
    platform: str
    adapter_name: str
    message: str
    error: Optional[str] = None

class SocialPublisher(ABC):
    """Abstract interface defining the contract for all social publishing adapters."""

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique key identifying the adapter (e.g. 'mock_x', 'mock_linkedin', 'discord')."""
        pass

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Target social platform (e.g. 'x', 'linkedin', 'discord')."""
        pass

    @abstractmethod
    def publish(
        self,
        variant_id: str,
        content: str,
        hashtags: List[str],
        idempotency_key: str
    ) -> PublishResult:
        """
        Publishes content through the platform adapter.
        Must be idempotent with respect to idempotency_key.
        """
        pass

