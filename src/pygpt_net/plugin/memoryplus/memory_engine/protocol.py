from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import uuid


ENGINE_MODES = ("auto", "persistent", "subprocess")

REQUEST_SEARCH = "SEARCH"
REQUEST_INGEST = "INGEST"
REQUEST_FORGET = "FORGET"
REQUEST_SYNTH = "SYNTH"
REQUEST_HEALTH = "HEALTH"
REQUEST_SHUTDOWN = "SHUTDOWN"


@dataclass
class EngineRequest:
    operation: str
    payload: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "payload": self.payload,
            "request_id": self.request_id,
        }


@dataclass
class EngineResponse:
    request_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "data": self.data or {},
            "error": self.error,
        }
