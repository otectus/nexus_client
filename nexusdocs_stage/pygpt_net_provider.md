# Section: provider

Path: src/pygpt_net/provider

## Bugs / Risks
- OpenAI Assistants tool submit streaming is marked TODO (provider/api/openai/worker/assistants.py), which can break streaming workflows.
- Google image edit is a TODO (provider/api/google/image.py), leaving UI options that may not work.
- Llama-index OpenAI utils note missing system prompt support for some models (provider/llms/llama_index/openai/utils.py); requests can silently degrade.

## Optimizations
- Standardize timeout and retry behavior across providers to avoid inconsistent hangs.
- Centralize token limit clamping and context length checks before API calls.
- Reuse HTTP clients across calls where supported to reduce connection overhead.

## Enhancements
- Add provider-level health checks and a unified error mapping layer.
- Expose per-provider capability metadata (streaming, tool calls, multimodal) for smarter UI gating.

## Additional Functions
- Add a provider diagnostics command (latency, retries, last error) for quick support triage.
