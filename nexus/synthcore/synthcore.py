import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .types import TurnRequest, TurnResponse, Turn, TokenUsage
from .model_provider import NexusModelProvider
from .synthmemory import SynthMemory
from .token_budget import TokenBudget
from .prompt_assembler import PromptAssembler, SectionSpec
from .mood_aware_budgeting import MoodAwareTokenBudgeting
from ..synthmood.mood import MoodDecayEngine, PADState
from ..synthmood.synthmood import SynthMood
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
        self.state_tracker = MultiTurnCoherenceTracker(model_provider)
        self.contradiction_detector = ContradictionDetector(model_provider)
        self.metrics = NexusMetrics()

    async def orchestrate_turn(self, request: TurnRequest) -> TurnResponse:
        start_time = time.time()
        turn_id = str(uuid.uuid4())

        # 1. Load context
        identity = await self._load_identity(request.user_id)
        raw_mood = await self._load_mood(request.user_id)
        mood = self.mood_engine.apply_decay(raw_mood, request.timestamp)

        # 2. Budget and Memory
        allocations = await self.budget_adjuster.allocate_tokens(mood, 4000)
        budget = TokenBudget(available_input=allocations['response'])
        memory_context = await self.memory.retrieve_memory_for_turn(request.user_input, allocations['memory_context'])

        # 3. Assemble Prompt
        modulated_system = await self.synth_mood.modulate_response_prompt("Act as defined in IDENTITY SNAPSHOT.", mood)
        prompt = self.assembler.assemble([
            SectionSpec("system", modulated_system, priority=1, degradable=False),
            SectionSpec("identity", identity.to_prompt(), priority=1),
            SectionSpec("memory", memory_context, priority=2),
            SectionSpec("request", request.user_input, priority=1)
        ], budget)

        # 4. Execute Primary Reasoning
        client = self.models.get_model_for_task('primary_reasoning')
        res = await client.call(prompt)
        response_text = res.text if hasattr(res, 'text') else str(res)

        # 5. Build Turn Object
        current_turn = Turn(
            id=turn_id, 
            timestamp=datetime.now(timezone.utc), 
            user_input=request.user_input, 
            response=response_text, 
            identity_snapshot=identity, 
            mood_state=mood, 
            token_usage=TokenUsage(total_tokens=budget.used)
        )

        # 6. Post-Check Protocols
        report = await self.contradiction_detector.detect_all_contradictions(response_text, self.state_tracker.state_history, self.memory.semantic)
        if report.severity == "error":
            logger.warning("Critical Coherence Failure. Regenerating...")
            response_text = await self._regenerate_response_with_constraints(request, report)

        # 7. Final State Operations
        await self.state_tracker.snapshot_after_turn(turn_id, current_turn.timestamp, identity, mood, self.memory, response_text)
        await self.memory.store_turn_memory(current_turn.id, current_turn.user_input, current_turn.response, current_turn.identity_snapshot.to_dict(), current_turn.mood_state.to_dict(), current_turn.token_usage.to_dict())

        # 8. Metrics
        total_latency = (time.time() - start_time) * 1000
        await self.metrics.record_turn(TurnMetrics(latency_ms=total_latency, tokens_used=budget.used, contradiction_count=len(report.intra_turn_contradictions), model_used=client.name if hasattr(client, 'name') else 'unknown'))

        return TurnResponse(text=response_text, metadata={"turn_id": turn_id})

    async def _regenerate_response_with_constraints(self, request, report) -> str:
        prompt = f"Fix your response to be consistent with your identity. Request: {request.user_input}"
        res = await self.models.get_model_for_task('primary_reasoning').call(prompt)
        return res.text if hasattr(res, 'text') else str(res)

    async def _load_identity(self, user_id: str) -> IdentitySnapshot: return MINIMAL_SKELETON_IDENTITY
    async def _load_mood(self, user_id: str) -> PADState: return MoodDecayEngine.BASELINE
