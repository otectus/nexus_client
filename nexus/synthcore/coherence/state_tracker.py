import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any
from ..model_provider import NexusModelProvider
from ...synthmood.mood import PADState
from ...synthidentity.kernel import IdentityKernel
from ...synthidentity.snapshot import IdentitySnapshot

@dataclass
class InvariantViolation:
    invariant_id: str
    description: str
    severity: str # "warn" or "error"

@dataclass
class InvariantViolationReport:
    violations: List[InvariantViolation] = field(default_factory=list)

@dataclass
class DriftReport:
    drift_detected: bool
    identity_drift: float = 0.0
    mood_drift: float = 0.0
    reason: str = ""

@dataclass
class TurnStateSnapshot:
    turn_id: str
    timestamp: datetime
    identity_kernel: IdentityKernel
    identity_snapshot: IdentitySnapshot
    pad_state: PADState
    claims_made: List[str]
    episodic_count: int
    semantic_count: int

class MultiTurnCoherenceTracker:
    def __init__(self, model_provider: NexusModelProvider):
        self.models = model_provider
        self.state_history: List[TurnStateSnapshot] = []
        self.invariants = []

    async def snapshot_after_turn(self, turn_id, timestamp, identity, mood, memory, response_text):
        snapshot = TurnStateSnapshot(
            turn_id=turn_id,
            timestamp=timestamp,
            identity_kernel=identity.kernel,
            identity_snapshot=identity,
            pad_state=mood,
            claims_made=await self._extract_claims(response_text),
            episodic_count=await memory.episodic.count(),
            semantic_count=await memory.semantic.count()
        )
        self.state_history.append(snapshot)
        if len(self.state_history) > 100:
            self.state_history.pop(0)

    async def check_invariants(self, response_text, identity) -> InvariantViolationReport:
        report = InvariantViolationReport()
        if identity.kernel.name.lower() not in response_text.lower() and "I am" in response_text:
             report.violations.append(InvariantViolation("id_01", "Identity name mismatch in response", "warn"))
        return report

    async def detect_drift(self) -> DriftReport:
        if len(self.state_history) < 5:
            return DriftReport(drift_detected=False, reason="insufficient_history")

        recent = self.state_history[-1]
        historical = self.state_history[-min(20, len(self.state_history))]

        mood_drift = (abs(recent.pad_state.valence - historical.pad_state.valence) +
                      abs(recent.pad_state.arousal - historical.pad_state.arousal)) / 2
        
        return DriftReport(
            drift_detected=(mood_drift > 0.4),
            mood_drift=mood_drift,
            reason="Significant emotional shift detected over history" if mood_drift > 0.4 else ""
        )

    async def _extract_claims(self, text: str) -> List[str]:
        model = self.models.get_model_for_task('mood_modulation')
        prompt = f"List factual assertions the assistant made about itself: {text}"
        res = await model.call(prompt)
        return [l.strip('- ') for l in (res.text if hasattr(res, 'text') else str(res)).split('\n') if l.strip()]
