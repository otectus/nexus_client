import sqlite3
import json
import os
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from ..synthcore.types import TokenUsage
from ..synthidentity.snapshot import IdentitySnapshot
from ..synthmood.mood import PADState

@dataclass
class EpisodicMemory:
    """Schema as defined in Stage 2 Roadmap 2B.1"""
    turn_id: str
    timestamp: datetime
    user_input: str
    assistant_response: str
    identity_state: IdentitySnapshot
    mood_state: PADState
    token_usage: TokenUsage
    salience_score: float = 0.5
    emotional_valence: float = 0.0
    concept_tags: List[str] = field(default_factory=list)
    contradiction_flags: List[str] = field(default_factory=list)

class EpisodicStore:
    def __init__(self, db_path: str = "/home/novus/.config/pygpt-net/data/nexus_episodic.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                turn_id TEXT PRIMARY KEY,
                timestamp TEXT,
                user_input TEXT,
                response TEXT, 
                identity_json TEXT,
                mood_json TEXT,
                token_json TEXT,
                salience REAL,
                valence REAL,
                tags TEXT,
                flags TEXT
            )
        """)
        self.db.commit()

    async def store(self, memory: EpisodicMemory):
        self.db.execute("""
            INSERT INTO episodic_memory 
            (turn_id, timestamp, user_input, response, 
             identity_json, mood_json, token_json, salience, valence, tags, flags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.turn_id,
            memory.timestamp.isoformat(),
            memory.user_input,
            memory.assistant_response,
            json.dumps(memory.identity_state.to_dict()),
            json.dumps(memory.mood_state.to_dict()),
            json.dumps(memory.token_usage.to_dict()),
            memory.salience_score,
            memory.emotional_valence,
            ",".join(memory.concept_tags),
            ",".join(memory.contradiction_flags)
        ))
        self.db.commit()

    async def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM episodic_memory").fetchone()[0]

    async def expire_records(self, days: int = 7):
        self.db.execute("DELETE FROM episodic_memory WHERE timestamp < datetime('now', '-{} days')".format(days))
        self.db.commit()
