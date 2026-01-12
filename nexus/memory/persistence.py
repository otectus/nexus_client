from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, JSON, Float, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone
import logging
import os

logger = logging.getLogger(__name__)
Base = declarative_base()

class EpisodicModel(Base):
    __tablename__ = 'episodic_memory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    session_id = Column(String, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    role = Column(String)
    text = Column(String)
    # Phase 1: Storing as JSON. Phase 2: Migrate to pgvector 'VECTOR' type.
    embedding_json = Column(JSON, nullable=True)
    consolidated = Column(Boolean, default=False)

class SemanticFact(Base):
    __tablename__ = 'semantic_memory'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, index=True)
    fact_text = Column(String)
    confidence = Column(Float, default=0.6)
    support_episode_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ConsolidationJobRecord(Base):
    __tablename__ = 'consolidation_jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, unique=True) # UUID string
    user_id = Column(String, index=True)
    status = Column(String)  # 'running', 'completed', 'failed'
    episodes_processed = Column(Integer, default=0)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class DatabaseManager:
    """
    Manages PostgreSQL connections and sessions for the Nexus client.
    Heavily utilizes environment variables for production-ready defaults.
    """
    def __init__(self, connection_string: Optional[str] = None):
        # Prioritize passed string, then ENV, then fail.
        conn_str = connection_string or os.getenv("NEXUS_DB_URL")
        if not conn_str:
            raise ValueError("Database connection string not provided and NEXUS_DB_URL environment variable is missing.")
        
        self.engine = create_engine(conn_str)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def initialize_db(self):
        """Create tables and ensure pgvector extension is present."""
        try:
            with self.engine.connect() as conn:
                # Note: This requires the database user to have superuser or appropriate privileges.
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    def get_session(self) -> Session:
        return self.SessionLocal()
