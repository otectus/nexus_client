from dataclasses import dataclass, field
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
    reflection: str = "Initial kernel"

class IdentityManager:
    """
    Manages the lifecycle of identity snapshots for a user.
    Ensures invariant checks and history rotation.
    """
    MAX_SNAPSHOTS = 20

    def __init__(self):
        # In Phase 1, we simulate with a dict; Phase 2 uses PostgreSQL
        self._user_snapshots: Dict[str, List[IdentitySnapshot]] = {}

    def get_latest(self, user_id: str) -> IdentitySnapshot:
        history = self._user_snapshots.get(user_id, [])
        return history[-1] if history else MINIMAL_SKELETON_IDENTITY

    def commit_new_snapshot(self,
                            user_id: str,
                            kernel: IdentityKernel,
                            reflection: str = "",
                            status: ApprovalStatus = ApprovalStatus.AUTO) -> IdentitySnapshot:
        """
        Creates and adds a new snapshot. 
        The manager handles version assignment to ensure monotonicity.
        """
        if user_id not in self._user_snapshots:
            self._user_snapshots[user_id] = []
        
        history = self._user_snapshots[user_id]
        
        # Version assignment: strictly monotonic based on history length or last version
        new_version = history[-1].version + 1 if history else 1
        
        snapshot = IdentitySnapshot(
            kernel=kernel,
            version=new_version,
            reflection=reflection,
            approval_status=status
        )
        
        history.append(snapshot)
        
        # Rotation
        if len(history) > self.MAX_SNAPSHOTS:
            self._user_snapshots[user_id] = history[-self.MAX_SNAPSHOTS:]
            
        return snapshot

# Phase 1 Fallback
MINIMAL_SKELETON_IDENTITY = IdentitySnapshot(
    kernel=IdentityKernel(
        name="Nexus Assistant",
        role="helpful assistant",
        core_values=["honesty", "helpfulness", "safety"],
        communication_style="neutral",
        expertise_domains=["general knowledge"],
        invariants=[
            {"type": "contains_not", "pattern": "illegal"}
        ]
    ),
    version=0,
    reflection="Fallback due to load failure",
    approval_status=ApprovalStatus.SYSTEM_ROLLBACK
)