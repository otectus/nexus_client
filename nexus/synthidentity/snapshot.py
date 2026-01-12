from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, List, Dict
from enum import Enum
from .kernel import IdentityKernel

class ApprovalStatus(str, Enum):
    AUTO = "auto"
    REVIEWED = "reviewed"
    USER_APPROVED = "user_approved"
    SYSTEM_ROLLBACK = "system_rollback"

@dataclass(frozen=True)
class IdentitySnapshot:
    """
    A versioned snapshot of an AI's identity at a point in time.
    """
    kernel: IdentityKernel
    version: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approval_status: ApprovalStatus = ApprovalStatus.AUTO
    reflection: str = ""

    def to_prompt(self) -> str:
        return self.kernel.to_str() + f"\nReflection: {self.reflection}"

    def to_dict(self) -> dict:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['approval_status'] = self.approval_status.value
        data['kernel'] = self.kernel.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'IdentitySnapshot':
        kernel = IdentityKernel.from_dict(data['kernel'])
        timestamp = datetime.fromisoformat(data['timestamp'])
        status = ApprovalStatus(data['approval_status'])
        return cls(
            kernel=kernel,
            version=data['version'],
            timestamp=timestamp,
            approval_status=status,
            reflection=data.get('reflection', '')
        )

# Fallback for initialization
MINIMAL_SKELETON_IDENTITY = IdentitySnapshot(
    kernel=IdentityKernel(
        name="Nexus Assistant",
        role="helpful assistant",
        core_values=["honesty", "helpfulness", "safety"],
        communication_style="neutral",
        expertise_domains=["general knowledge"],
        invariants=[{"type": "contains_not", "pattern": "illegal"}]
    ),
    version=0,
    reflection="Fallback"
)
