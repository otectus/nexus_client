import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ..identity.snapshot import IdentitySnapshot, MINIMAL_SKELETON_IDENTITY
from ..affect.mood import MoodState, MoodDecayEngine, MoodPromptGenerator
from ..memory.manager import MemoryService
from .token_budget import TokenBudget

# Note: prompt_assembler should be imported carefully to avoid circular dependencies
from .prompt_assembler import PromptAssembler

logger = logging.getLogger(__name__)

class SynthCoreOrchestrator:
    """
    Orchestrates the AI's cognitive loop: Identity, Mood, Memory, and LLM Execution.
    Enforces budget constraints and graceful degradation.
    """
    def __init__(
        self, 
        memory_service: MemoryService, 
        assembler: PromptAssembler,
        llm_client: Any 
    ):
        self.memory = memory_service
        self.assembler = assembler
        self.llm = llm_client
        # Initialize Mood engine with defaults for Phase 1
        self.mood_engine = MoodDecayEngine()
        self.baseline_mood = MoodDecayEngine.BASELINE

    async def process_turn(
        self,
        user_id: str,
        session_id: str,
        user_text: str,
        identity_override: Optional[IdentitySnapshot] = None,
        mood_current: Optional[MoodState] = None
    ) -> Dict[str, Any]:
        """
        Main entry point. Single request -> single response.
        """
        start_time = time.time()
        metrics = {"degradation_events": [], "errors": []}
        
        # 1. Load Identity with Fallback (100ms timeout)
        try:
            identity = identity_override or await asyncio.wait_for(self._load_identity(user_id), timeout=0.1)
        except Exception as e:
            logger.error(f"Identity load failure: {e}")
            identity = MINIMAL_SKELETON_IDENTITY
            metrics["degradation_events"].append("identity_fallback")

        # 2. Load and Decay Mood (100ms timeout)
        try:
            raw_mood = mood_current or await asyncio.wait_for(self._load_mood(user_id), timeout=0.1)
            # Use the instance method for decay calculation
            mood = self.mood_engine.apply_decay(raw_mood, datetime.now(timezone.utc))
        except Exception as e:
            logger.warning(f"Mood load failure: {e}")
            mood = self.baseline_mood
            metrics["degradation_events"].append("mood_fallback_baseline")

        # 3. Initialize Budget
        budget = TokenBudget(total_context=128000, reserved_output=8000)

        # 4. Retrieve Memory (500ms timeout)
        try:
            # Note: query_embedding would be generated here in Phase 2
            # We pass a dummy embedding for Phase 1 logic
            memory_context = await asyncio.wait_for(
                self.memory.retrieve_relevant(
                    user_id, session_id, user_text, [0.0]*1536, budget, identity.kernel.expertise_domains
                ), 
                timeout=0.5
            )
        except Exception as e:
            logger.error(f"Memory retrieval degraded: {e}")
            memory_context = "[No prior relevant context]"
            metrics["degradation_events"].append("memory_skipped")

        # 5. Assemble Prompt (Strict 5-Section Template)
        identity_content = (
            f"Name: {identity.kernel.name}\n"
            f"Role: {identity.kernel.role}\n"
            f"Core Values: {', '.join(identity.kernel.core_values)}\n"
            f"Communication: {identity.kernel.communication_style}\n"
            f"Expertise: {', '.join(identity.kernel.expertise_domains)}\n"
            f"Invariants: {identity.kernel.invariants}"
        )

        sections = [
            ("SYSTEM", "Act as the kernel defined in IDENTITY SNAPSHOT."),
            ("IDENTITY SNAPSHOT", identity_content),
            ("MOOD STATE", MoodPromptGenerator.generate_injection_text(mood)),
            ("RELEVANT MEMORY", memory_context),
            ("CURRENT REQUEST", user_text)
        ]
        
        prompt = self.assembler.assemble(sections, budget)

        # 6. LLM Call (Fatal path if fails)
        try:
            # Placeholder for actual LLM call logic
            response_text = await self._call_llm(prompt)
        except Exception as e:
            logger.critical(f"Primary LLM failure: {e}")
            metrics["errors"].append("llm_unreachable")
            return {"error": "Service temporarily unavailable", "metrics": metrics}

        # 7. Metrics and Output
        metrics["latency_total"] = time.time() - start_time
        metrics["tokens_used"] = budget.used
        
        return {
            "response": response_text,
            "identity_version": identity.version,
            "mood_state": mood,
            "metrics": metrics
        }

    async def _load_identity(self, user_id: str) -> IdentitySnapshot:
        # Placeholder for DB load
        return MINIMAL_SKELETON_IDENTITY

    async def _load_mood(self, user_id: str) -> MoodState:
        # Placeholder for DB load
        return self.baseline_mood

    async def _call_llm(self, prompt: str) -> str:
        # Simulated LLM response for Phase 1 code structure
        return f"[Simulated Nexus Response based on core logic]".strip()