import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .model_provider import NexusModelProvider
from .synthmemory import SynthMemory
from .token_budget import TokenBudget
from .prompt_assembler import PromptAssembler, SectionSpec
from .mood_aware_budgeting import MoodAwareTokenBudgeting
from ..synthmood.mood import PADState, MoodDecayEngine
from ..synthmood.synthmood import SynthMood
from ..synthidentity.consistency_validator import IdentityConsistencyValidator
from ..synthidentity.snapshot import IdentitySnapshot, MINIMAL_SKELETON_IDENTITY
from .coherence.state_tracker import MultiTurnCoherenceTracker
from .coherence.contradiction_detector import ContradictionDetector
from .observability.metrics import NexusMetrics, TurnMetrics

logger = logging.getLogger(__name__)

class SynthCore:
    def __init__(self, model_provider: NexusModelProvider, memory: SynthMemory, assembler: PromptAssembler):
        self.models = model_provider
        self.memory = memory
        self.assembler = assembler
        self.mood_engine = MoodDecayEngine()
        self.synth_mood = SynthMood(model_provider)
        self.budget_adjuster = MoodAwareTokenBudgeting()
        self.validator = IdentityConsistencyValidator(model_provider)
        self.state_tracker = MultiTurnCoherenceTracker(model_provider)
        self.contradiction_detector = ContradictionDetector(model_provider)
        self.metrics = NexusMetrics()

    async def orchestrate_turn(self, user_id: str, session_id: str, user_text: str) -> Dict[str, Any]:
        start_time = time.time()
        turn_id = str(uuid.uuid4())
        
        # 1. State Initialization
        identity = await self._load_identity(user_id)
        raw_mood = await self._load_mood(user_id)
        mood = self.mood_engine.apply_decay(raw_mood, datetime.now(timezone.utc))

        # 2. Budgeting
        allocations = await self.budget_adjuster.allocate_tokens(mood, 4000)
        budget = TokenBudget(available_input=allocations['response'])
        
        # 3. Execution
        memory_context = await self.memory.retrieve_memory_for_turn(user_text, allocations['memory_context'])
        system_prompt = "Act as the kernel defined in IDENTITY SNAPSHOT."
        modulated_system = await self.synth_mood.modulate_response_prompt(system_prompt, mood)

        prompt = self.assembler.assemble([
            SectionSpec("system", modulated_system, priority=1, degradable=False),
            SectionSpec("identity", identity.to_prompt(), priority=1, degradable=False),
            SectionSpec("memory", memory_context, priority=2),
            SectionSpec("request", user_text, priority=1)
        ], budget)

        primary_model = self.models.get_model_for_task('primary_reasoning')
        response = await primary_model.call(prompt)
        response_text = response.text if hasattr(response, 'text') else str(response)

        # 4. Roadmap Post-Check Contradictions (2C.4)
        report = await self.contradiction_detector.detect_all_contradictions(
            response_text, self.state_tracker.state_history, self.memory.semantic
        )

        if report.severity == "error":
            logger.warning("Critical contradictions detected, regenerating...")
            response_text = await self._regenerate_response_with_constraints(user_text, report, identity, mood, budget)

        # 5. Invariant Checks & Drift
        inv_report = await self.state_tracker.check_invariants(response_text, identity)
        drift_report = await self.state_tracker.detect_drift()
        if drift_report.drift_detected:
             logger.warning(f"Identity drift detected: {drift_report.reason}")

        # 6. Persistence
        await self.memory.store_turn_memory(turn_id, user_text, response_text, identity.to_dict(), mood.to_dict(), {})
        await self.state_tracker.snapshot_after_turn(turn_id, datetime.now(), identity, mood, self.memory, response_text)

        return {"response": response_text, "turn_id": turn_id, "drift": drift_report.drift_detected}

    async def _regenerate_response_with_constraints(self, original_request, report, identity, mood, budget) -> str:
        """Roadmap Logic: Regenerate response if contradictions detected"""
        constraints = "\n".join([f"- {c.reason}" for c in (report.intra_turn_contradictions + report.cross_turn_contradictions)])
        prompt = f"REGENERATE this response to avoid the following contradictions:\n{constraints}\n\nOriginal Request: {original_request}"
        res = await self.models.get_model_for_task('primary_reasoning').call(prompt)
        return res.text if hasattr(res, 'text') else str(res)

    async def _load_identity(self, user_id: str): return MINIMAL_SKELETON_IDENTITY
    async def _load_mood(self, user_id: str): return MoodDecayEngine.BASELINE
