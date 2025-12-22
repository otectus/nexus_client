# Changelog

## Nexus Update (Alpha v0.1) - [BUILD 2025-21-12]
- Integration of native MemoryPlus plugin operating alongside a Graphiti-vased back-end for persistent andd temporal memory.
- Refactored user-facing information to reflect that it is the 'Nexus Client'.
- Laid the groundwork for further updates, optimizations and expansions.
- MemoryPlus now writes runner config/content/query to temp files so subprocess calls don’t hit “argument list too long,” and I removed the host‑side writeability check that was flagging the Neo4j data path even though the - container can manage it. (plugin.py)
- Graphiti’s max tokens are clamped to 16,384 in both the persistent worker and the runner so max_tokens=128000 won’t blow up anymore. (plugin.py, worker.py, runner.py)
- OpenAI calls are now hard‑clamped to 16,384 max output tokens to prevent the global max_output_tokens=128000 error. (__init__.py)
- Update checker now ignores 404s instead of logging a stack trace. (updater.py)
