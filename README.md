# Nexus Client

[![Version](https://img.shields.io/badge/version-0.1.0-informational)](#versioning)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](#requirements)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#license)

A production-grade AI orchestration client that keeps an agent **coherent over time** by enforcing **identity invariants**, managing **long-term memory**, and maintaining a **persistent mood state**, all under strict **token budgets** with **graceful degradation**.

---

## Why Nexus Client exists

Most “agent” systems fail in predictable ways:
- They drift in tone and values across long sessions (identity drift).
- They forget crucial context or explode token budgets (context bloat).
- They get brittle: one subsystem failure breaks the whole flow.

Nexus Client’s Stage 1 MVP is designed to prevent those failures with four foundational subsystems:
- **SynthCore**: orchestration, token budgeting, prompt assembly, graceful degradation
- **SynthMemory**: episodic memory + nightly consolidation (semantic facts stored for Phase 2)
- **SynthIdentity**: immutable kernel + versioned snapshots + invariant enforcement
- **SynthMood**: structural PAD state (valence/arousal/dominance) with decay and safe injection

---

## Architecture at a glance

**Turn loop (single request → single response):**
1. Load **Identity** (fallback to minimal skeleton if needed)
2. Load **Mood** and apply decay
3. Compute **Token Budget** (hard ceiling)
4. Retrieve **Memory** (budget-aware packing)
5. Assemble prompt (strict sectioned template)
6. Call primary model
7. Post-check invariants + log metrics
8. Store episodic memory (sanitized / gated)
9. Return response (even when degraded)

**Graceful degradation is mandatory:** memory can time out, embedding can fail, mood can fail, identity can fail, and Nexus still returns a response with reduced capability.

---

## Features (Stage 1)

### ✅ Token-budgeted prompt assembly
- Fixed allocations for system + identity + mood
- Greedy packing for memory to fit remaining budget
- Hard refusal for overflow conditions

### ✅ Identity consistency
- Immutable **IdentityKernel** (values, rules, style)
- Versioned snapshots (Phase 2 expands approval workflow)
- Post-generation invariant checks

### ✅ Memory you can actually live with
- Episodic store (turn-level)
- Multi-factor ranking (semantic similarity + recency + session boost + domain relevance)
- Nightly consolidation job to prevent context bloat

### ✅ Mood without “the model pretending to feel”
- PAD vector is metadata that modulates task approach, not roleplay
- Exponential decay + inertia
- Safe injection template that discourages emotional hallucination

---

## Repository layout (suggested)

```

nexus_client/
nexus/
core/
orchestrator.py
budgets.py
prompt_assembler.py
contracts.py
identity/
models.py
store.py
invariants.py
mood/
models.py
decay.py
store.py
memory/
models.py
store.py
retrieval.py
consolidation.py
telemetry/
metrics.py
logging.py
tests/
docs/
pyproject.toml
README.md

````

---

## Requirements

- Python **3.11+** (3.12 supported)
- A storage backend (pick one):
  - **PostgreSQL + pgvector** (recommended)
  - SQLite (for embedded/dev-only scenarios)
- Optional vector DB:
  - Weaviate (easy ops, solid defaults)

---

## Quickstart (local dev)

### 1) Create a venv
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
````

### 2) Install

```bash
pip install -e ".[dev]"
```

### 3) Run tests

```bash
pytest -q
```

---

## Configuration

Use env vars (or a `.env`) to keep config explicit and deployable:

**Core**

* `NEXUS_CONTEXT_WINDOW_TOKENS=128000`
* `NEXUS_RESERVED_OUTPUT_TOKENS=8000`
* `NEXUS_INPUT_BUDGET_FRACTION=0.85`

**Storage**

* `NEXUS_DB_URL=postgresql+psycopg://...`
* `NEXUS_VECTOR_BACKEND=pgvector|weaviate|sqlite`

**Models**

* `NEXUS_LLM_PROVIDER=openai|anthropic|local`
* `NEXUS_EMBED_PROVIDER=openai|local`

---

## CI & quality gates

Suggested minimum gates:

* Unit tests must pass
* Token budget never exceeds cap in tests
* Invariant violations fail the build (or at minimum, are surfaced as red alerts)
* Type checks clean
* Lint clean

**Recommended tooling**

* `pytest` (tests)
* `ruff` (lint)
* `black` (format)
* `mypy` (typing)
* `pre-commit` (hooks)

---

## Testing

```bash
pytest
```

Add targeted suites:

* `tests/test_budgets.py` (budget invariants)
* `tests/test_prompt_assembly.py` (section template + packing)
* `tests/test_identity_invariants.py` (drift detection)
* `tests/test_mood_decay.py` (determinism + clamping)
* `tests/test_memory_retrieval.py` (ranking + packing + tenancy)
* `tests/test_degradation_paths.py` (timeouts + fallbacks)

---

## Linting & formatting

```bash
ruff check .
black .
```

---

## Type checking

```bash
mypy nexus
```

---

## Pre-commit

```bash
pre-commit install
pre-commit run --all-files
```

---

## Roadmap

### Stage 1 (MVP foundation)

* Single-process orchestration
* Episodic memory + consolidation
* Identity kernel + invariants
* Mood PAD + decay
* Full observability and degradation paths

### Stage 2 (planned)

* Semantic fact retrieval (high-confidence only + contradiction checks)
* Identity learning vector (controlled, versioned, reviewable)
* Mood appraisal engine (still structural, not theatrical)
* Plugin ecosystem with permissions + sandboxing
* Kafka/event bus for multi-tenant scaling

---

## Versioning

This repo uses semantic versioning:

* `0.x` = rapid iteration while interfaces harden
* `1.0` = stable contracts (plugins, stores, public APIs)

---

## License

MIT License. See `LICENSE`.

---

## Credits

Built under the Project Nexus architecture: a practical, production-minded approach to long-horizon agent coherence through **contracts, budgets, invariants, consolidation, and resilience**.
