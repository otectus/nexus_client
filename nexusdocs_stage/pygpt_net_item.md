# Section: item

Path: src/pygpt_net/item

## Bugs / Risks
- Item models rely on loosely typed dict inputs with minimal validation. Invalid or partially populated items can propagate into UI and provider layers.

## Optimizations
- Use dataclass slots or attrs consistently to reduce memory overhead for high-volume context items.
- Centralize serialization/deserialization to avoid repeated ad-hoc parsing in multiple classes.

## Enhancements
- Add validation helpers for model IDs, mode support, and token limits to prevent invalid state at the edge of the system.
- Introduce explicit schema versions for serialized items so migrations can be automated.

## Additional Functions
- Provide a lint/repair function to scan existing persisted items and fix schema drift.
