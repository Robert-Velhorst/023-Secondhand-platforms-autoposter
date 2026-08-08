from __future__ import annotations

from typing import Protocol

from app.models import Listing
from app.services.quality import analyze_listing_quality


class SuggestionProvider(Protocol):
    name: str
    deterministic: bool
    external_data_sent: bool

    def analyze(self, listing: Listing) -> dict: ...


class DeterministicLocalSuggestionProvider:
    name = "deterministic_local"
    deterministic = True
    external_data_sent = False

    def analyze(self, listing: Listing) -> dict:
        result = analyze_listing_quality(listing)
        return {
            "provider": self.name,
            "deterministic": self.deterministic,
            "external_data_sent": self.external_data_sent,
            **result,
        }


def get_suggestion_provider(name: str) -> SuggestionProvider:
    if name.lower() == "deterministic_local":
        return DeterministicLocalSuggestionProvider()
    raise ValueError(f"Unsupported suggestion provider: {name}")
