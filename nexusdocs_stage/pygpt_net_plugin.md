# Section: plugin

Path: src/pygpt_net/plugin

## Bugs / Risks
- Llama-index inline plugin builds queries synchronously in the prompt pipeline; heavy input can still block the UI if not bounded.
- MemoryPlus has multiple moving parts (persistent worker, subprocess fallback, container lifecycle) and needs stronger health checks and clearer error surfaces for users.
- cmd_history and base worker modules include TODOs indicating incomplete features (cmd_history summarization helper, ResponseContext typing).

## Optimizations
- Lazy-load plugin dependencies to reduce startup time for unused plugins.
- Move plugin network and file operations off the UI thread consistently.
- Centralize plugin logging so noisy plugins do not spam the status bar.

## Enhancements
- Add a plugin health indicator and per-plugin retry/backoff configuration.
- Provide a shared plugin settings schema and validation to prevent invalid values at runtime.
- Expose plugin capability metadata so the UI can auto-hide unsupported options.

## Additional Functions
- Add a plugin sandbox permission system for file access, network access, and container control.
- Add a plugin diagnostics export (last error, last run time, queue depth).
