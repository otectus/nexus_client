from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict
import numpy as np
import math
import re

@dataclass
class EpisodicMemory:
    """
    Represents a single turn in a conversation session.
    """
    id: Optional[int]
    user_id: str
    session_id: str
    timestamp: datetime
    role: str  # 'user' or 'assistant'
    text: str
    embedding: Optional[List[float]] = None
    tags: List[str] = field(default_factory=list)
    consolidated: bool = False

@dataclass
class MemoryPack:
    """
    A collection of memories formatted for prompt injection.
    """
    entries: List[EpisodicMemory]
    total_tokens: int

class MemoryRanker:
    """
    Implements the Phase 1 ranking formula:
    score = similarity * 0.50 + recency * 0.30 + session_boost * 0.15 + expertise * 0.05
    """
    @staticmethod
    def calculate_score(
        query_embedding: List[float],
        memory: EpisodicMemory,
        current_session_id: str,
        expertise_domains: List[str]
    ) -> float:
        # 1. Cosine Similarity with hardening
        similarity = 0.5  # Default fallback
        if query_embedding and memory.embedding:
            q_arr = np.array(query_embedding)
            m_arr = np.array(memory.embedding)
            
            if q_arr.shape == m_arr.shape:
                norm_q = np.linalg.norm(q_arr)
                norm_m = np.linalg.norm(m_arr)
                
                if norm_q > 0 and norm_m > 0:
                    dot_product = np.dot(q_arr, m_arr)
                    similarity = dot_product / (norm_q * norm_m)
                    # Clamp to [-1, 1] to avoid float precision quirks
                    similarity = max(-1.0, min(1.0, float(similarity)))

        # 2. Recency Weight: exp(-k * age_hours)
        # Using hourly granularity for better precision
        diff = datetime.now(timezone.utc) - memory.timestamp
        age_hours = diff.total_seconds() / 3600.0
        # k=0.01 means ~50% weight after 70 hours
        recency = math.exp(-0.01 * age_hours)

        # 3. Session Boost: 1.0 if same session, 0.5 otherwise
        session_boost = 1.0 if memory.session_id == current_session_id else 0.5

        # 4. Domain Relevance (Word Boundary aware)
        domain_relevance = 0.5
        for domain in expertise_domains:
            # Use regex to ensure we don't match substrings inside other words (e.g., 'ram' in 'program')
            pattern = rf"\b{re.escape(domain.lower())}\b"
            if re.search(pattern, memory.text.lower()):
                domain_relevance = 0.9
                break

        score = (
            (similarity * 0.50) +
            (recency * 0.30) +
            (session_boost * 0.15) +
            (domain_relevance * 0.05)
        )
        return round(score, 4)
