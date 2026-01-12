import logging
from datetime import datetime, timedelta, timezone
from typing import List
import uuid

from .persistence import DatabaseManager, EpisodicModel, SemanticFact, ConsolidationJobRecord

logger = logging.getLogger(__name__)

class ConsolidationManager:
    """
    Handles the nightly consolidation of episodic memories into semantic facts.
    Ensures the system remains 'budget-aware' by reducing raw context over time.
    """
    def __init__(self, db_manager: DatabaseManager, max_episodes_per_run: int = 500):
        self.db = db_manager
        self.max_episodes_per_run = max_episodes_per_run

    async def run_for_user(self, user_id: str):
        """
        Main consolidation loop for a specific user.
        Fetches settled episodes (older than 24h) and clusters them.
        """
        session = self.db.get_session()
        job_id = str(uuid.uuid4())
        
        try:
            # 1. Register Job with job_id persistence
            job_record = ConsolidationJobRecord(
                job_id=job_id,
                user_id=user_id, 
                status='running'
            )
            session.add(job_record)
            session.commit()

            # 2. Fetch Unconsolidated Episodes
            # We consolidate memories OLDER than 24h to allow context to 'settle'.
            cutoff = datetime.now(timezone.utc) - timedelta(days=1)
            episodes = session.query(EpisodicModel).filter(
                EpisodicModel.user_id == user_id,
                EpisodicModel.consolidated == False,
                EpisodicModel.timestamp < cutoff 
            ).limit(self.max_episodes_per_run).all()

            if not episodes:
                logger.info(f"No episodes older than 24h to consolidate for user {user_id}")
                job_record.status = 'completed'
                session.commit()
                return

            # 3. Clustering & Fact Extraction (Simulated for Phase 1)
            facts_to_add = self._simulate_fact_extraction(user_id, episodes)

            # 4. Atomic Update
            for fact in facts_to_add:
                session.add(fact)
            
            for ep in episodes:
                ep.consolidated = True
            
            job_record.status = 'completed'
            job_record.episodes_processed = len(episodes)
            session.commit()
            logger.info(f"Consolidation complete ({job_id}) for {user_id}: {len(facts_to_add)} facts extracted from {len(episodes)} episodes.")

        except Exception as e:
            session.rollback()
            logger.error(f"Consolidation job {job_id} failed for {user_id}: {e}")
            # Try to mark job as failed
            try:
                failed_job = session.query(ConsolidationJobRecord).filter_by(job_id=job_id).first()
                if failed_job:
                    failed_job.status = 'failed'
                    session.commit()
            except:
                pass
        finally:
            session.close()

    def _simulate_fact_extraction(self, user_id: str, episodes: List[EpisodicModel]) -> List[SemanticFact]:
        session_groups = {}
        for ep in episodes:
            session_groups.setdefault(ep.session_id, []).append(ep)

        facts = []
        for session_id, group in session_groups.items():
            summary_text = f"User discussed {len(group)} items in session {session_id}."
            facts.append(SemanticFact(
                user_id=user_id,
                fact_text=summary_text,
                confidence=0.6,
                support_episode_ids=[ep.id for ep in group]
            ))
        return facts
