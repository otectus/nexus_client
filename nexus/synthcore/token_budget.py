import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TokenBudget:
    """
    Manages token allocation with per-section hardware-enforced caps.
    """
    # Default Phase 1 Caps
    DEFAULT_CAPS = {
        "system": 400,
        "identity": 300,
        "mood": 150, # Slightly increased for implications
        "memory": 6000,
        "request": 100000 # Effectively unlimited context
    }

    def __init__(
        self, 
        total_context: int = 128000, 
        reserved_output: int = 8000, 
        safety_buffer_percent: float = 0.85,
        component_caps: Dict[str, int] = None
    ):
        self.total_context = total_context
        self.available_input = int(total_context * safety_buffer_percent) - reserved_output
        self.used = 0
        self.allocations: Dict[str, int] = {}
        self.caps = component_caps or self.DEFAULT_CAPS

    def allocate(self, component: str, token_count: int) -> bool:
        # 1. Individual Cap Check
        cap = self.caps.get(component, self.available_input)
        if token_count > cap:
            logger.warning(f"Budget Cap Exceeded: {component} requested {token_count} (Cap: {cap})")
            return False

        # 2. Total Window Check
        if self.used + token_count > self.available_input:
            return False
        
        self.used += token_count
        self.allocations[component] = self.allocations.get(component, 0) + token_count
        return True

    def report(self) -> Dict[str, Any]:
        return {
            "used": self.used,
            "available": self.available_input,
            "utilization": (self.used / self.available_input) if self.available_input > 0 else 1,
            "sections": self.allocations
        }