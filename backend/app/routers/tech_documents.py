from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


@dataclass
class TechDocument:
    id: int
    user_id: int
    doc_type: str
    url: str
    mime_type: Optional[str] = None
    original_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TechDocument":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except Exception:
                created_at = datetime.utcnow()
        elif not isinstance(created_at, datetime):
            created_at = datetime.utcnow()

        return cls(
            id=int(data.get("id", 0)),
            user_id=int(data.get("user_id", 0)),
            doc_type=str(data.get("doc_type", "")),
            url=str(data.get("url", "")),
            mime_type=data.get("mime_type"),
            original_name=data.get("original_name"),
            created_at=created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "doc_type": self.doc_type,
            "url": self.url,
            "mime_type": self.mime_type,
            "original_name": self.original_name,
            "created_at": self.created_at.isoformat()
            if isinstance(self.created_at, datetime)
            else self.created_at,
        }
