# Section: ui

Path: src/pygpt_net/ui

## Bugs / Risks
- Several TODOs indicate incomplete UI behaviors (e.g., option widgets, plugin dialogs, and web textarea normalization).
- Chat render TODOs around meta IDs and reload behavior suggest potential mismatches between stored context and UI state.

## Optimizations
- Virtualize long lists (history, presets, models) to reduce repaint cost.
- Avoid full UI refresh on small state changes; use incremental updates where possible.
- Batch theme/style recalculations to reduce jitter during heavy output streaming.

## Enhancements
- Add UI-level performance telemetry (frame time, render queue depth, active threads).
- Introduce a lightweight UI error banner for non-fatal warnings instead of only logging.

## Additional Functions
- Add an accessibility audit mode to flag contrast and keyboard navigation issues.
