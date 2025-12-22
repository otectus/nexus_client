# Section: pygpt_net top-level files

Path: src/pygpt_net

## Bugs / Risks
- utils.set_env has inverted semantics for allow_overwrite; when True it refuses to overwrite. This can silently skip env setup in app.py and should be renamed or fixed.
- app.py globally monkey-patches builtins.open for Snap .env handling. Even with the SNAP guard, a global patch is fragile and can mask file access errors elsewhere.
- config.py reads and writes path.cfg without file locking or atomic write. Concurrent launches or partial writes can corrupt the workdir pointer.

## Optimizations
- app.py and launcher.py import a large registry of plugins/providers eagerly. Replace with a registry loader or entrypoints to reduce import time and memory.
- Large generated resource modules (fonts_rc.py, js_rc.py, icons_rc.py) are imported eagerly. Consider lazy-loading or split resources to reduce startup cost.
- utils.get_init_value re-parses __init__.py on first call and uses regex per key; cache parsed values as a dict once and reuse.

## Enhancements
- Add a structured plugin/provider registry config so user presets can enable/disable extensions without modifying app.py.
- Provide CLI flags for safe mode and for disabling update checks to simplify offline usage and troubleshooting.
- Replace print-based startup messages with Debug logger to unify output handling.

## Additional Functions
- Add a diagnostic command to dump effective env vars, workdir, and active plugins/providers for support cases.
- Add a configuration integrity check to validate JSON/QRC resources at startup.
