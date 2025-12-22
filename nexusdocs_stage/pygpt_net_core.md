# Section: core

Path: src/pygpt_net/core

## Bugs / Risks
- Web renderer memory cleanup uses a fixed 2GB threshold with a TODO to scale by RAM (core/render/web/renderer.py). This can under- or over-clean depending on system size.
- Indexer has a TODO for zip handling (core/idx/indexing.py); zipped inputs can fail without pre-unpack.
- Agent runner and llama-index chat have TODOs for unsupported modes and multimodal support (core/agents/runner.py, core/idx/chat.py), which can produce incorrect routing.
- Experts flow has TODO about clearing ctx.output (core/experts/experts.py) that could leave stale data attached to a context.

## Optimizations
- Bridge quick-call paths are synchronous; introduce timeouts and cancellation to avoid UI stalls in context prep and retrieval.
- Normalize token accounting so all call paths clamp max_tokens based on model limits.
- Add caching for tokenizer computations in high-frequency flows (chat and retrieval) to reduce repeated work.

## Enhancements
- Introduce a unified error type hierarchy for bridge/index/agent subsystems to improve handling and diagnostics.
- Add structured metrics (timings, token usage, retries) surfaced in Debug UI.
- Expand offline mode support for idx retrieval and tools when external services are unavailable.

## Additional Functions
- Add a core-level task scheduler to coordinate long background jobs with progress reporting.
- Add a core-level watchdog to detect stalled workers and auto-recover where safe.
