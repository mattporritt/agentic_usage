from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProviderCache:
    data: dict[str, Any] | None = None
    last_fetched: datetime | None = None
    error: str | None = None
    configured: bool = True


cache: dict[str, ProviderCache] = {
    "anthropic": ProviderCache(),
    "openai": ProviderCache(),
    "logs": ProviderCache(),
}
