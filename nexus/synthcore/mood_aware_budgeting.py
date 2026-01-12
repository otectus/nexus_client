import logging
from typing import Dict
from ..synthmood.mood import PADState

class MoodAwareTokenBudgeting:
    """Adjust token budgets based on mood"""
    
    async def allocate_tokens(self, mood: PADState, base_budget: int) -> Dict[str, int]:
        # Simple arousal/dominance scaling
        arousal_multiplier = 0.8 + (mood.arousal * 0.4)
        dominance_multiplier = 0.7 + (mood.dominance * 0.6)
        
        return {
            "response": int(base_budget * arousal_multiplier),
            "memory_context": base_budget // 4
        }
