from typing import Dict, Optional
from app.config import DEFAULT_PUBLISHER_ADAPTER
from app.adapters.base import SocialPublisher
from app.adapters.mock_x import MockXPublisher
from app.adapters.mock_linkedin import MockLinkedInPublisher
from app.adapters.discord import DiscordWebhookPublisher

# Registered adapter catalog
ADAPTERS: Dict[str, SocialPublisher] = {
    "mock_x": MockXPublisher(),
    "mock_linkedin": MockLinkedInPublisher(),
    "discord": DiscordWebhookPublisher()
}

_active_adapter_override: Optional[str] = None

def set_active_adapter_override(adapter_id: Optional[str]):
    """Allows runtime configuration swap of the active publisher."""
    global _active_adapter_override
    _active_adapter_override = adapter_id

def get_publisher_adapter(adapter_id: Optional[str] = None) -> SocialPublisher:
    """
    Returns the resolved publisher adapter instance.
    Resolution order:
    1. Explicit function argument
    2. Runtime override configuration
    3. DEFAULT_PUBLISHER_ADAPTER environment setting
    """
    selected = adapter_id or _active_adapter_override or DEFAULT_PUBLISHER_ADAPTER
    adapter = ADAPTERS.get(selected.lower())
    if not adapter:
        raise ValueError(f"Unknown publisher adapter '{selected}'. Registered adapters: {list(ADAPTERS.keys())}")
    return adapter
