import logging
import json
import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

# Configure structured logger
logger = logging.getLogger("nexus.observability")

@dataclass
class DegradationEvent:
    """Logs when a subsystem fails and a fallback is used."""
    subsystem: str
    event_type: str  # 'timeout', 'error', 'fallback'
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class TurnMetrics:
    """Complete telemetry for a single conversation turn."""
    user_id: str
    session_id: str
    total_latency_ms: float
    tokens_used: int
    budget_utilization_pct: float
    degradation_events: List[DegradationEvent] = field(default_factory=list)
    status: str = "success" # 'success', 'degraded', 'failed'
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ObservabilityService:
    """
    Provides structured telemetry for the Nexus Orchestrator.
    Outputs JSON logs ready for ingestion by ELK/Prometheus/Grafana.
    """
    @staticmethod
    def log_turn(metrics: TurnMetrics):
        """Serializes and logs turn metrics."""
        log_data = asdict(metrics)
        # Convert datetime objects to ISO strings for JSON serialization
        log_data['timestamp'] = metrics.timestamp.isoformat()
        for event in log_data['degradation_events']:
            event['timestamp'] = event['timestamp'].isoformat()
            
        logger.info(json.dumps(log_data))

    @staticmethod
    def record_degradation(subsystem: str, event_type: str, message: str) -> DegradationEvent:
        event = DegradationEvent(subsystem=subsystem, event_type=event_type, message=message)
        logger.warning(f"DEGRADATION: {subsystem} | {event_type} | {message}")
        return event