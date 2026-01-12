import http.server
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import logging

logger = logging.getLogger(__name__)

class PrometheusExporter:
    """
    Exports Stage 2 metrics to Prometheus.
    Tracks latency, token usage, and contradiction frequency.
    """
    
    def __init__(self, port: int = 8000):
        self.port = port
        # Define Prometheus Metrics
        self.turn_latency = Histogram('nexus_turn_latency_ms', 'Latency of turn processing in ms')
        self.tokens_used = Counter('nexus_tokens_total', 'Total tokens consumed', ['task_type'])
        self.contradictions = Counter('nexus_contradictions_total', 'Count of contradictions detected', ['type'])
        self.identity_drift = Gauge('nexus_identity_drift_score', 'Current calculated identity drift')
        self.mood_valence = Gauge('nexus_mood_valence', 'Current PAD valence state')
        
    def start(self):
        """Start the Prometheus metrics server"""
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus metrics exported on port {self.port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus exporter: {e}")

    def record_turn_metrics(self, metrics_data: dict):
        self.turn_latency.observe(metrics_data.get('latency', 0))
        self.identity_drift.set(metrics_data.get('drift', 0))
        
        for task, tokens in metrics_data.get('token_usage', {}).items():
            self.tokens_used.labels(task_type=task).inc(tokens)
            
        for c_type, count in metrics_data.get('contradictions', {}).items():
            self.contradictions.labels(type=c_type).inc(count)
