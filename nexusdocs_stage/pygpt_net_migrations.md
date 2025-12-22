# Section: migrations

Path: src/pygpt_net/migrations

## Bugs / Risks
- Migration scripts appear timestamp-driven with no explicit test coverage; failures can leave partial state without rollback.
- There is no clear idempotency guarantee or downgrade path noted in migration modules.

## Optimizations
- Add a migration registry to detect and skip already-applied steps more efficiently.
- Ensure migration ordering is deterministic and logged to avoid silent replays.

## Enhancements
- Add migration unit tests that run against a temp workdir to verify each version step.
- Provide a compatibility report for older config/data versions to reduce upgrade surprises.

## Additional Functions
- Add a CLI command for running, dry-running, and validating migrations.
