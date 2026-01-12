from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Optional, Dict

def clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))

@dataclass(frozen=True)
class MoodState:
    valence: float
    arousal: float
    dominance: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "decay"
    
    def to_dict(self) -> dict:
        return {"valence": self.valence, "arousal": self.arousal, "dominance": self.dominance, "timestamp": self.timestamp.isoformat()}

# Alias for roadmap compliance
PADState = MoodState

class MoodDecayEngine:
    DEFAULT_HALF_LIFE = 1800
    DEFAULT_INERTIA = 0.7
    BASELINE = MoodState(valence=0.0, arousal=0.0, dominance=0.5, source="baseline")

    def __init__(self, half_life: float = DEFAULT_HALF_LIFE, inertia: float = DEFAULT_INERTIA):
        self.half_life = half_life
        self.inertia = inertia

    def apply_decay(self, last_state: MoodState, current_time: datetime) -> MoodState:
        seconds_elapsed = (current_time - last_state.timestamp).total_seconds()
        decay_factor = math.exp(-math.log(2) * max(0, seconds_elapsed) / self.half_life)
        def decay_val(last, baseline): return clamp(baseline + (last - baseline) * self.inertia * decay_factor)
        return MoodState(
            valence=round(decay_val(last_state.valence, self.BASELINE.valence), 4),
            arousal=round(decay_val(last_state.arousal, self.BASELINE.arousal), 4),
            dominance=round(decay_val(last_state.dominance, self.BASELINE.dominance), 4),
            timestamp=current_time
        )
