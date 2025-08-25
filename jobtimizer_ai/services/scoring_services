# services/scoring_service.py
import asyncio
import logging
from typing import Optional
from datetime import datetime
from models.scoring import JobAdScore
from services.stepstone_scoring import stepstone_scoring_service
from services.westpress_scoring import westpress_scoring_service
from services.database import db_service

logger = logging.getLogger(__name__)

class ScoringService:
    """Zentraler Service für alle Bewertungssysteme"""
    
    async def score_job_ad_complete(
        self, 
        job_ad_text: str, 
        job_title: str, 
        user_id: str
    ) -> JobAdScore:
        """
        Vollständige Bewertung einer Stellenanzeige mit allen Systemen
        """
        try:
            logger.info(f"Starte vollständige Bewertung für Job: {job_title}")
            
            # Beide Bewertungen parallel durchführen
            stepstone_task = stepstone_scoring_service.score_job_ad(job_ad_text, job_title)
            westpress_task = westpress_scoring_service.score_job_ad(job_ad_text, job_title)
            
            stepstone_score, westpress_score = await asyncio.gather(
                stepstone_task, westpress_task
            )
            
            # Gesamtergebnis zusammenstellen
            complete_score = JobAdScore(
                user_id=user_id,
                job_title=job_title,
                job_ad_text=job_ad_text,
                stepstone_score=stepstone_score,
                westpress_score=westpress_score,
                created_at=datetime.utcnow()
            )
            
            # In Datenbank speichern
            await self._save_score_to_database(complete_score)
            
            logger.info(f"Bewertung abgeschlossen - Stepstone: {stepstone_score.gesamt_score:.1f}, "
                       f"WP-Expert: {'nicht konfiguriert' if not westpress_score.is_configured else westpress_score.gesamt_score:.1f}")
            
            return complete_score
            
        except Exception as e:
            logger.error(f"Fehler bei vollständiger Bewertung: {e}")
            raise
    
    async def get_score_history(self, user_id: str, limit: int = 10) -> list:
        """Bewertungshistorie eines Benutzers abrufen"""
        try:
            # TODO: Implementiere Datenbank-Abfrage für Score-Historie
            logger.info(f"Lade Score-Historie für User {user_id}")
            return []  # Placeholder
        except Exception as e:
            logger.error(f"Fehler beim Laden der Score-Historie: {e}")
            return []
    
    async def _save_score_to_database(self, score: JobAdScore) -> bool:
        """Speichere Bewertung in Datenbank"""
        try:
            # TODO: Erweitere database.py um scores_collection
            logger.info(f"Speichere Bewertung für Job: {score.job_title}")
            # Placeholder - implementiere in database.py
            return True
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Bewertung: {e}")
            return False

# Global scoring service instance
scoring_service = ScoringService()
