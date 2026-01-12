from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from ..synthidentity.snapshot import IdentitySnapshot
from ..synthmood.mood import PADState

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self): return {"prompt": self.prompt_tokens, "completion": self.completion_tokens, "total": self.total_tokens}

@dataclass
class TurnRequest:
    user_input: str
    user_id: str = "default"
    session_id: str = "session_0"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class TurnResponse:
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "success"

@dataclass
class Turn:
    id: str
    timestamp: datetime
    user_input: str
    response: str
    identity_snapshot: IdentitySnapshot
    mood_state: PADState
    token_usage: TokenUsage
    metadata: Dict[str, Any] = field(default_factory=dict)
