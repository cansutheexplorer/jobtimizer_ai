# models/scoring.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class ScoreLevel(str, Enum):
    """Bewertungsstufen für Scores"""
    SCHLECHT = "schlecht"  # 0-40
    VERBESSERUNGSWUERDIG = "verbesserungswürdig"  # 41-60
    GUT = "gut"  # 61-80
    SEHR_GUT = "sehr_gut"  # 81-100

class ScoreCategory(BaseModel):
    """Einzelne Bewertungskategorie"""
    name: str
    score: float = Field(..., ge=0, le=100)
    max_score: float = Field(default=100)
    feedback: str
    suggestions: List[str] = Field(default_factory=list)
    level: ScoreLevel
    
class StepstoneScore(BaseModel):
    """Stepstone Bewertungssystem"""
    # Hauptkategorien mit deutschen Bezeichnungen
    anzeigenkopf: ScoreCategory
    einleitung: ScoreCategory  
    aufgabenbeschreibung: ScoreCategory
    profil_anforderungen: ScoreCategory
    benefits: ScoreCategory
    kontakt_bewerbung: ScoreCategory
    sprache_stil: ScoreCategory
    suchverhalten_keywords: ScoreCategory
    agg_bias_check: ScoreCategory
    
    # Gesamtergebnis
    gesamt_score: float = Field(..., ge=0, le=100)
    gesamt_level: ScoreLevel
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @property
    def kategorie_scores(self) -> Dict[str, ScoreCategory]:
        """Alle Kategorien als Dictionary"""
        return {
            "Anzeigenkopf": self.anzeigenkopf,
            "Einleitung": self.einleitung,
            "Aufgabenbeschreibung": self.aufgabenbeschreibung,
            "Profil & Anforderungen": self.profil_anforderungen,
            "Benefits": self.benefits,
            "Kontakt & Bewerbung": self.kontakt_bewerbung,
            "Sprache & Stil": self.sprache_stil,
            "Suchverhalten & Keywords": self.suchverhalten_keywords,
            "AGG & Bias Check": self.agg_bias_check
        }

class WestpressExpertScore(BaseModel):
    """Westpress Expert Bewertungssystem - Platzhalter für deine Kriterien"""
    # TODO: Hier fügst du deine eigenen Bewertungskriterien hinzu
    
    # Beispiel-Kategorien (anpassen nach deinen Bedürfnissen):
    content_qualitaet: Optional[ScoreCategory] = None
    zielgruppen_ansprache: Optional[ScoreCategory] = None
    unternehmen_branding: Optional[ScoreCategory] = None
    conversion_optimierung: Optional[ScoreCategory] = None
    
    gesamt_score: float = Field(default=0, ge=0, le=100)
    gesamt_level: ScoreLevel = ScoreLevel.VERBESSERUNGSWUERDIG
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_configured: bool = Field(default=False)  # Flag ob Kriterien definiert sind

class JobAdScore(BaseModel):
    """Gesamtbewertung einer Stellenanzeige"""
    user_id: str
    job_title: str
    job_ad_text: str
    stepstone_score: StepstoneScore
    westpress_score: WestpressExpertScore
    created_at: datetime = Field(default_factory=datetime.utcnow)
