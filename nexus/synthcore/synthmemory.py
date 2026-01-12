import logging
import json
from typing import List, Optional, Dict
from datetime import datetime
from .model_provider import NexusModelProvider
from ..synthmemory.episodic_store import EpisodicStore, EpisodicMemory
from ..synthmemory.semantic_store import SemanticStore, SemanticFact
from ..synthmemory.semantic_consolidation import SemanticConsolidationEngine

logger = logging.getLogger(__name__)

class SynthMemory:
    """
    Stage 2 Memory Subsystem.
    Integrates Episodic (turn-level) and Semantic (fact-level) storage.
    """
    
    def __init__(
        self, 
        model_provider: NexusModelProvider,
        episodic_store: Optional[EpisodicStore] = None,
        semantic_store: Optional[SemanticStore] = None
    ):
        self.models = model_provider
        self.episodic = episodic_store or EpisodicStore()
        self.semantic = semantic_store or SemanticStore()
        self.consolidation = SemanticConsolidationEngine(model_provider, self.episodic, self.semantic)

    async def retrieve_memory_for_turn(
        self, 
        user_input: str, 
        token_budget: int
    ) -> str:
        """
        Context Retrieval Pipeline:
        1. Recent episodic (hot context)
        2. Relevant semantic (long-term facts)
        3. Formatted and truncated to budget
        """
        recent_episodes = await self.episodic.retrieve_range(hours=24)
        semantic_facts = await self.semantic.retrieve_relevant_facts(user_input, limit=10)
        return await self._pack_memory(recent_episodes, semantic_facts, token_budget)

    async def _pack_memory(self, episodes: List[EpisodicMemory], facts: List[SemanticFact], budget: int) -> str:
        sections = ["[RELEVANT FACTS]"]
        for f in facts:
            sections.append(f"- {f.subject} {f.predicate} {f.object} (confidence: {f.confidence:.2f})")
            
        sections.append("\n[RECENT HISTORY]")
        for m in reversed(episodes[:5]):
            sections.append(f"User: {m.user_input}\nAssistant: {m.assistant_response}")

        combined = "\n".join(sections)
        if len(combined) > budget * 4:
            combined = combined[:budget * 4] + "... [Context Truncated]"
        return combined

    async def store_turn_memory(
        self, 
        turn_id: str,
        user_input: str, 
        response_text: str,
        identity_state: dict,
        mood_state: dict,
        token_usage: dict
    ):
        memory = EpisodicMemory(
            turn_id=turn_id,
            timestamp=datetime.now(),
            user_input=user_input,
            assistant_response=response_text,
            identity_state=identity_state,
            mood_state=mood_state,
            token_usage=token_usage
        )
        await self.episodic.store(memory)

    async def trigger_consolidation(self):
        return await self.consolidation.consolidate_nightly()
