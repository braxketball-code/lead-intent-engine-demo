from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Lead:
    id: str
    source: str
    vertical: str
    name: str
    message: str
    email: str | None = None
    phone: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Lead:
        return cls(
            id=data["id"],
            source=data["source"],
            vertical=data["vertical"],
            name=data.get("name", "Unknown"),
            message=data.get("message", ""),
            email=data.get("email") or None,
            phone=data.get("phone") or None,
            metadata=data.get("metadata") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScoredLead:
    lead: Lead
    score: int
    tier: str
    reasoning: str
    recommended_action: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.lead.to_dict(),
            "score": self.score,
            "tier": self.tier,
            "reasoning": self.reasoning,
            "recommended_action": self.recommended_action,
            "tags": self.tags,
        }
