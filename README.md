# Nexus Client: SynthCore Alpha

A modular, multi-agent AI system built on a recursive self-improvement architecture. Nexus focuses on persistence, dimensional affect (mood state), and strict identity governance.

## 🧠 Cognitive Architecture (SynthCore)

Nexus operates via the **SynthCore Orchestrator**, which manages the AI's cognitive loop across five strict prompt sections:

1.  **SYSTEM**: The operational kernel and behavioral constraints.
2.  **IDENTITY SNAPSHOT**: A versioned, immutable definition of the AI's core traits and expertise.
3.  **MOOD STATE**: Dimensional PAD model (Pleasure, Arousal, Dominance) context that influences task approach.
4.  **RELEVANT MEMORY**: Ranker-based episodic and semantic memory retrieval.
5.  **CURRENT REQUEST**: The immediate user input.

## 🚀 Features

-   **Deterministic Prompt Assembly**: Strict Delimitors and token budget enforcement per section.
-   **Affective Computing**: Integrated `MoodDecayEngine` for organic mood transitions.
-   **Identity Invariants**: Post-generation validation to maintain character integrity.
-   **Observability First**: Detailed telemetry for every turn, including degradation events (memory fallback, etc.).

## 🛠 Tech Stack

-   **OS**: Linux (Arch-based optimized)
-   **Language**: Python 3.10+
-   **Core Libs**: `tiktoken`, `numpy`, `sqlalchemy` (PostgreSQL target), `asyncio`.
-   **Identity Manager**: Monotonic versioning for identity evolution.

## 🚦 Getting Started

### Prerequisites
- Python 3.10 or 3.13
- Venv managed environment

### Installation
```bash
git clone https://github.com/yourusername/nexus_client.git
cd nexus_client
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.