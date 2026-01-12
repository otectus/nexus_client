import sqlite3
import json
import os
import re
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

@dataclass
class SemanticFact:
    """Structured semantic triple"""
    subject: str
    predicate: str
    object: str
    confidence: float
    timestamp: datetime
    decay_age: float = 1.0  # Decay multiplier (1.0 = no decay)

    def to_dict(self):
        d = asdict(self)
        d['timestamp'] = self.timestamp.isoformat()
        return d

class SemanticStore:
    """Persistent semantic knowledge graph with temporal decay"""
    
    def __init__(self, db_path: str = "/home/novus/.config/pygpt-net/data/nexus_semantic.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self._init_schema()
    
    def _init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS semantic_facts (
                subject TEXT,
                predicate TEXT,
                object TEXT,
                confidence REAL,
                timestamp TEXT,
                decay_age REAL,
                PRIMARY KEY (subject, predicate, object)
            )
        """)
        self.db.commit()
    
    async def store_facts(self, facts: List[SemanticFact]):
        """Store extracted semantic facts using UPSERT logic"""
        for fact in facts:
            self.db.execute("""
                INSERT INTO semantic_facts
                (subject, predicate, object, confidence, timestamp, decay_age)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(subject, predicate, object) DO UPDATE SET
                confidence = MAX(confidence, excluded.confidence),
                timestamp = excluded.timestamp,
                decay_age = MIN(1.0, decay_age + 0.1) -- Reinforcement
            """, (
                fact.subject,
                fact.predicate,
                fact.object,
                fact.confidence,
                fact.timestamp.isoformat(),
                fact.decay_age
            ))
        self.db.commit()
    
    async def retrieve_relevant_facts(
        self, 
        query: str, 
        limit: int = 15
    ) -> List[SemanticFact]:
        """
        Retrieve semantically relevant facts.
        Simple lexical search for now; Phase 3 will introduce embeddings.
        """
        # Clean query for simple LIKE matching
        clean_query = re.sub(r'[^a-zA-Z0-9\s]', '', query)
        terms = clean_query.split()
        
        if not terms:
            return []

        # Build a simple multi-term match query
        conditions = []
        params = []
        for term in terms:
            conditions.append("(subject LIKE ? OR predicate LIKE ? OR object LIKE ?)")
            params.extend([f"%{term}%", f"%{term}%", f"%{term}%"])
        
        sql = f"""
            SELECT * FROM semantic_facts
            WHERE {' AND '.join(conditions)}
            ORDER BY confidence * decay_age DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor = self.db.execute(sql, params)
        return [self._row_to_fact(row) for row in cursor.fetchall()]
    
    def _row_to_fact(self, row) -> SemanticFact:
        return SemanticFact(
            subject=row[0],
            predicate=row[1],
            object=row[2],
            confidence=row[3],
            timestamp=datetime.fromisoformat(row[4]),
            decay_age=row[5]
        )

    async def apply_decay(self):
        """
        Apply temporal decay to facts.
        Older facts become less relevant unless reinforced.
        """
        self.db.execute("""
            UPDATE semantic_facts
            SET decay_age = MAX(0.1, decay_age - 0.05 * (
                (julianday('now') - julianday(timestamp))
            ))
        """)
        self.db.commit()
