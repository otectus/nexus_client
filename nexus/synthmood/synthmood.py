import logging
from typing import Dict, Any
from ..synthcore.model_provider import NexusModelProvider
from .mood import PADState

logger = logging.getLogger(__name__)

class SynthMood:
    def __init__(self, model_provider: NexusModelProvider):
        self.models = model_provider
    
    async def modulate_response_prompt(self, base_prompt: str, mood: PADState) -> str:
        self.mood_model = self.models.get_model_for_task('mood_modulation')
        mood_desc = self._describe_pad_state(mood)
        return f"""{base_prompt}\n\n[MOOD CONTEXT]\nCurrent emotional state (PAD):\n- Valence: {mood.valence:.2f} ({mood_desc['valence']})\n- Arousal: {mood.arousal:.2f} ({mood_desc['arousal']})\n- Dominance: {mood.dominance:.2f} ({mood_desc['dominance']})\n\nRespond in a way that reflects this emotional state.\nTemperature: {self._pad_to_temperature(mood):.2f}\nTop-p: {self._pad_to_top_p(mood):.2f}"""

    def _describe_pad_state(self, mood: PADState) -> Dict[str, str]:
        return {
            "valence": "positive" if mood.valence > 0 else "negative",
            "arousal": "high intensity" if mood.arousal > 0.3 else "calm",
            "dominance": "dominant" if mood.dominance > 0.5 else "submissive"
        }

    def _pad_to_temperature(self, mood: PADState) -> float:
        return min(2.0, max(0.0, 0.3 + (mood.arousal * 0.7)))

    def _pad_to_top_p(self, mood: PADState) -> float:
        return min(1.0, max(0.0, 0.7 + (mood.valence * 0.2)))
