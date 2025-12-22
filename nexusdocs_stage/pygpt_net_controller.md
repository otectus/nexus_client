# Section: controller

Path: src/pygpt_net/controller

## Bugs / Risks
- Several TODOs indicate unfinished behavior in chat rendering and input flow (controller/chat/render.py, controller/chat/text.py, controller/chat/common.py). These can cause incorrect output routing or stalled UI.
- Attachment and file controllers still contain TODOs for core functions (controller/attachment/attachment.py, controller/files/files.py). These should be completed or feature-flagged.
- Preset editor has a TODO placeholder (controller/presets/editor.py) that can leave UI in a partially wired state.
- Assistant store state is not reset on profile reload (controller/assistant/store.py), which can lead to stale state and leaks.

## Optimizations
- Move long-running or IO-heavy controller actions to threadpool tasks to prevent UI freezes (file indexing, large context ops).
- Reduce repeated config lookups inside hot paths (chat input/output) by caching frequently used values per request.
- Consolidate duplicated chat rendering logic across modes into shared helpers to reduce maintenance overhead.

## Enhancements
- Add controller-level cancellation/timeout support for long operations (index queries, file scans).
- Provide structured error routing from controllers to UI dialogs instead of silent returns.
- Add controller unit tests around chat render switch, context load/save, and attachment lifecycle.

## Additional Functions
- Add a controller health dashboard for in-app diagnostics (threads, queue depth, pending tasks).
- Add a safe-mode controller toggle to disable optional subsystems at runtime.
