import logging
from typing import Dict

logger = logging.getLogger(__name__)

class TokenBudget:
    """
    Manages and enforces token allocation across prompt components.
    Ensures the context window never overflows by staying within a safety buffer.
    """
    def __init__(
        self, 
        total_context: int = 128000, 
        reserved_output: int = 8000, 
        safety_buffer_percent: float = 0.85
    ):
        self.total_context = total_context
        self.reserved_output = reserved_output
        self.safety_buffer_percent = safety_buffer_percent

        # available_input = (128000 * 0.85) - 8000 = 100,800 tokens by default
        self.available_input = int(total_context * safety_buffer_percent) - reserved_output
        
        if self.available_input < 1000:
            raise ValueError("Context window too small for reasonable operation")

        self.used = 0
        self.allocations: Dict[str, int] = {}

    def allocate(self, component: str, token_count: int) -> bool:
        """
        Attempt to allocate tokens for a component. 
        Returns True if successful, False if it would exceed budget.
        """
        if self.used + token_count > self.available_input:
            logger.warning(
                f"Budget Refused: {component} requested {token_count} tokens. "
                f"Used: {self.used}, Available: {self.available_input}"
            )
            return False
        
        self.used += token_count
        self.allocations[component] = self.allocations.get(component, 0) + token_count
        return True

    def remaining(self) -> int:
        """Return remaining available tokens for input."""
        return self.available_input - self.used

    def report(self) -> Dict:
        """Return a report of current usage."""
        return {
            "available_input": self.available_input,
            "used": self.used,
            "remaining": self.remaining(),
            "utilization_pct": (self.used / self.available_input) * 100 if self.available_input > 0 else 0,
            "sections": self.allocations
        }
