import math
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import json
import numpy as np

from .service import EpisodicMemory, MemoryRanker
from .persistence import DatabaseManager, EpisodicModel
from ..core.token_budget import TokenBudget
from ..core.prompt_assembler import PromptAssembler

class MemoryService:
    """
    Coordinates database storage, retrieval, ranking, and packing of episodic memories.
    """
    def __init__(self, assembler: PromptAssembler, db_manager: DatabaseManager):
        self.assembler = assembler
        self.db = db_manager

    async def store_interaction(self, user_id: str, session_id: str, role: str, text: str, embedding: List[float]):
        """Saves a new interaction to the database."""
        session = self.db.get_session()
        try:
            episode = EpisodicModel(
                user_id=user_id,
                session_id=session_id,
                role=role,
                text=text,
                embedding_json=embedding,
                timestamp=datetime.now(timezone.utc)
            )
            session.add(episode)
            session.commit()
        finally:
            session.close()

    async def retrieve_relevant(
        self, 
        user_id: str, 
        session_id: str, 
        query_text: str, 
        query_embedding: List[float], 
        budget: TokenBudget,
        expertise_domains: List[str],
        max_history_scan: int = 1000,
        diversity_threshold: float = 0.9
    ) -> str:
        """
        Retrieves from DB with limits, ranks, and packs with diversity constraints.
        """
        session = self.db.get_session()
        try:
            # Fetch with limits to avoid OOM/performance hits
            # We fetch latest N from this user
            models = session.query(EpisodicModel).filter(
                EpisodicModel.user_id == user_id
            ).order_by(EpisodicModel.timestamp.desc()).limit(max_history_scan).all()
            
            memories = []
            for m in models:
                memories.append(EpisodicMemory(
                    id=m.id,
                    user_id=m.user_id,
                    session_id=m.session_id,
                    timestamp=m.timestamp.replace(tzinfo=timezone.utc),
                    role=m.role,
                    text=m.text,
                    embedding=m.embedding_json
                ))

            # Rank
            ranked = [(MemoryRanker.calculate_score(query_embedding, m, session_id, expertise_domains), m) for m in memories]
            ranked.sort(key=lambda x: x[0], reverse=True)

            # Diversified Greedy Packing
            packed_text = []
            selected_embeddings = []
            
            for score, m in ranked:
                # Diversity Check (Simple Phase 1: check if too similar to what's already packed)
                if selected_embeddings and m.embedding:
                    curr_emb = np.array(m.embedding)
                    is_redundant = False
                    for prev_emb in selected_embeddings:
                        # Fast dot product check (assuming normalized embeddings from Ranker logic)
                        sim = np.dot(curr_emb, prev_emb) / (np.linalg.norm(curr_emb) * np.linalg.norm(prev_emb) + 1e-9)
                        if sim > diversity_threshold:
                            is_redundant = True
                            break
                    if is_redundant: continue

                formatted = f"[{m.timestamp.strftime('%Y-%m-%d %H:%M')}] {m.role.upper()}: {m.text}"
                tokens = self.assembler.count_tokens(formatted)
                
                # Use 'memory_fragment' budget key (Must align with SynthCore policy)
                if budget.allocate("memory_fragment", tokens):
                    packed_text.append(formatted)
                    if m.embedding:
                        selected_embeddings.append(np.array(m.embedding))
                else:
                    # Budget exhausted
                    break
            
            return "\n\n".join(packed_text) if packed_text else "[No prior relevant context]"
        finally:
            session.close()
