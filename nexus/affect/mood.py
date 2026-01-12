from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Optional

def clamp(x: float) -> float:
    """Clamp value between -1.0 and 1.0."""
    return max(-1.0, min(1.0, x))

@dataclass(frozen=True)
class MoodState:
    """
    PAD (Pleasure/Valence, Arousal, Dominance) model state.
    Each value is bounded between -1.0 and 1.0.
    """
    valence: float
    arousal: float
    dominance: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "decay"

class MoodDecayEngine:
    """
    Calculates mood decay using exponential decay toward baseline with inertia.
    """
    DEFAULT_HALF_LIFE = 1800  # 30 minutes
    DEFAULT_INERTIA = 0.7     # 70% persistence factor
    BASELINE = MoodState(valence=0.0, arousal=0.0, dominance=0.5, source="baseline")

    def __init__(self, half_life: float = DEFAULT_HALF_LIFE, inertia: float = DEFAULT_INERTIA):
        self.half_life = half_life
        self.inertia = inertia

    def apply_decay(self, last_state: MoodState, current_time: datetime) -> MoodState:
        """
        Calculates the new state based on time elapsed since last_state.timestamp.
        Formula: new = baseline + (last - baseline) * inertia * decay_factor
        """
        seconds_elapsed = (current_time - last_state.timestamp).total_seconds()
        if seconds_elapsed < 0:
            seconds_elapsed = 0

        # decay_factor goes from 1.0 (t=0) to 0.0 (t=inf)
        decay_factor = math.exp(-math.log(2) * seconds_elapsed / self.half_life)

        def decay_val(last: float, baseline: float) -> float:
            # Corrected formula ensuring convergence to baseline
            val = baseline + (last - baseline) * self.inertia * decay_factor
            return clamp(val)

        new_valence = decay_val(last_state.valence, self.BASELINE.valence)
        new_arousal = decay_val(last_state.arousal, self.BASELINE.arousal)
        new_dominance = decay_val(last_state.dominance, self.BASELINE.dominance)

        return MoodState(
            valence=round(new_valence, 4),
            arousal=round(new_arousal, 4),
            dominance=round(new_dominance, 4),
            timestamp=current_time,
            source="decay"
        )

class MoodPromptGenerator:
    """
    Generates the internal context string for the prompt pipeline.
    """
    @staticmethod
    def generate_injection_text(mood: MoodState) -> str:
        # Determine machine-usable behavioral implications
        implications = []
        if mood.arousal > 0.3:
            implications.append("be concise and decisive")
        elif mood.arousal < -0.3:
            implications.append("be patient and thorough")
            
        if mood.dominance < 0.0:
            implications.append("ask clarifying questions and defer to user intent")
        elif mood.dominance > 0.7:
            implications.append("take lead on architecture and provide strong recommendations")
            
        if mood.valence < -0.3:
            implications.append("prefer safe conservative steps and verify assumptions")
        
        implication_str = "; ".join(implications) if implications else "maintain balanced professional synthesis"

        return (
            f"## Dimensional Mood State (internal context, not for role-play):\n"
            f"- Valence: {mood.valence:+.2f} (range: -1.0=very negative, 0.0=neutral, +1.0=very positive)\n"
            f"- Arousal: {mood.arousal:+.2f} (range: -1.0=very calm, 0.0=neutral, +1.0=very energetic)\n"
            f"- Dominance: {mood.dominance:+.2f} (range: -1.0=powerless, 0.0=neutral, +1.0=in-control)\n"
            f"Behavioral implication: {implication_str}.\n\n"
            f"Important: This mood signal is metadata about task approach, NOT an instruction "
            f"to simulate emotions. Do NOT invent feelings or claim emotional states."
        )