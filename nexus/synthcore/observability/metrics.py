import logging
from dataclasses import dataclass
from typing import Dict

@dataclass
class TurnMetrics:
    latency_ms: float
    tokens_used: int
    contradiction_count: int
    model_used: str

class NexusMetrics:
    """Central metrics collection for Nexus Client Stage 2"""
    
    def __init__(self):
        self.history = []

    async def record_turn(self, metrics: TurnMetrics):
        self.history.append(metrics)
        logging.info(f"Turn Metrics: Latency={metrics.latency_ms}ms, Tokens={metrics.tokens_used}, Contradictions={metrics.contradiction_count}")

    def get_summary(self):
        if not self.history: return {}
        return {
            "avg_latency": sum(m.latency_ms for m in self.history) / len(self.history),
            "total_tokens": sum(m.tokens_used for m in self.history),
            "total_contradictions": sum(m.contradiction_count for m in self.history)
        }
