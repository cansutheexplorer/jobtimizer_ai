# services/stepstone_scoring.py
import asyncio
from openai import AsyncOpenAI
import logging
import re
from typing import Dict, List
from config import settings
from models.scoring import ScoreCategory, ScoreLevel, StepstoneScore

logger = logging.getLogger(__name__)

class StepstoneScoringService:
    """Stepstone Bewertungsservice für deutsche Stellenanzeigen"""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    def _get_score_level(self, score: float) -> ScoreLevel:
        """Bewertungsstufe basierend auf Score bestimmen"""
        if score >= 81:
            return ScoreLevel.SEHR_GUT
        elif score >= 61:
            return ScoreLevel.GUT
        elif score >= 41:
            return ScoreLevel.VERBESSERUNGSWUERDIG
        else:
            return ScoreLevel.SCHLECHT
    
    async def score_job_ad(self, job_ad_text: str, job_title: str) -> StepstoneScore:
        """Vollständige Stepstone-Bewertung einer Stellenanzeige"""
        
        # Bewerte alle Kategorien parallel
        tasks = [
            self._score_anzeigenkopf(job_ad_text, job_title),
            self._score_einleitung(job_ad_text),
            self._score_aufgabenbeschreibung(job_ad_text),
            self._score_profil_anforderungen(job_ad_text),
            self._score_benefits(job_ad_text),
            self._score_kontakt_bewerbung(job_ad_text),
            self._score_sprache_stil(job_ad_text),
            self._score_suchverhalten_keywords(job_ad_text, job_title),
            self._score_agg_bias_check(job_ad_text)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Kategorien zuweisen
        (anzeigenkopf, einleitung, aufgabenbeschreibung, profil_anforderungen,
         benefits, kontakt_bewerbung, sprache_stil, suchverhalten_keywords, agg_bias_check) = results
        
        # Gesamtscore berechnen (gewichteter Durchschnitt)
        weights = {
            'anzeigenkopf': 0.15,
            'einleitung': 0.10,
            'aufgabenbeschreibung': 0.15,
            'profil_anforderungen': 0.15,
            'benefits': 0.10,
            'kontakt_bewerbung': 0.08,
            'sprache_stil': 0.12,
            'suchverhalten_keywords': 0.10,
            'agg_bias_check': 0.05
        }
        
        gesamt_score = (
            anzeigenkopf.score * weights['anzeigenkopf'] +
            einleitung.score * weights['einleitung'] +
            aufgabenbeschreibung.score * weights['aufgabenbeschreibung'] +
            profil_anforderungen.score * weights['profil_anforderungen'] +
            benefits.score * weights['benefits'] +
            kontakt_bewerbung.score * weights['kontakt_bewerbung'] +
            sprache_stil.score * weights['sprache_stil'] +
            suchverhalten_keywords.score * weights['suchverhalten_keywords'] +
            agg_bias_check.score * weights['agg_bias_check']
        )
        
        return StepstoneScore(
            anzeigenkopf=anzeigenkopf,
            einleitung=einleitung,
            aufgabenbeschreibung=aufgabenbeschreibung,
            profil_anforderungen=profil_anforderungen,
            benefits=benefits,
            kontakt_bewerbung=kontakt_bewerbung,
            sprache_stil=sprache_stil,
            suchverhalten_keywords=suchverhalten_keywords,
            agg_bias_check=agg_bias_check,
            gesamt_score=round(gesamt_score, 1),
            gesamt_level=self._get_score_level(gesamt_score)
        )
    
    async def _score_anzeigenkopf(self, job_ad_text: str, job_title: str) -> ScoreCategory:
        """Bewertung Anzeigenkopf (Job Title)"""
        
        system_prompt = """Du bist Stepstone Bewertungsexperte für deutsche Stellenanzeigen. 
        
        Bewerte den ANZEIGENKOPF (Job Title) nach diesen Kriterien:
        
        1. **Klarheit & Verständlichkeit** (25 Punkte)
           - Ist der Titel klar und präzise?
           - Keine mehrdeutigen Begriffe?
           - Sofort verständlich was gesucht wird?
        
        2. **Relevanz für die Suche** (25 Punkte) 
           - Verwendet gängige Suchbegriffe?
           - Keine überflüssigen Zusätze?
           - Stepstone/Google-optimiert?
        
        3. **Gendergerechte Formulierung** (25 Punkte)
           - Enthält (m/w/d) oder ähnlich?
           - Inklusiv formuliert?
           - Kein Gender-Bias?
        
        4. **Suchvolumen-Optimierung** (25 Punkte)
           - Nutzt bekannte Berufsbezeichnungen?
           - Branchenüblich formuliert?
           - Zielgruppe findet es leicht?
        
        Gib eine Bewertung von 0-100 Punkten und konkretes Feedback."""
        
        user_prompt = f"""
        JOBTITEL: {job_title}
        
        STELLENANZEIGE:
        {job_ad_text[:1000]}...
        
        Bewerte nur den Anzeigenkopf/Jobtitel und gib zurück:
        - Score (0-100)
        - Feedback (kurz und konkret)
        - 2-3 Verbesserungsvorschläge
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2,VORSCHLAG3"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Anzeigenkopf")
            
        except Exception as e:
            logger.error(f"Fehler bei Anzeigenkopf-Bewertung: {e}")
            return ScoreCategory(
                name="Anzeigenkopf",
                score=50.0,
                feedback="Bewertung konnte nicht durchgeführt werden",
                suggestions=["Technischer Fehler aufgetreten"],
                level=ScoreLevel.VERBESSERUNGSWUERDIG
            )
    
    async def _score_einleitung(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Einleitung"""
        
        system_prompt = """Du bewertest die EINLEITUNG von Stellenanzeigen nach Stepstone-Kriterien:
        
        1. **Aufmerksamkeitshöhe** (35 Punkte)
           - Catchy und einprägsam?
           - Kandidaten-fokussiert statt Unternehmen-fokussiert?
           - Neugier weckend?
        
        2. **Nutzenorientierung** (35 Punkte)
           - Zeigt Vorteile für Bewerber?
           - Nicht nur Anforderungen?
           - "Was habe ich davon?"-Test bestanden?
        
        3. **Zielgruppen-Ansprache** (30 Punkte)
           - Anrede passend zur Zielgruppe?
           - Tonalität stimmig?
           - Richtige Sie/Du-Form?
        
        Bewerte 0-100 Punkte."""
        
        # Extrahiere wahrscheinliche Einleitung (erste 2-3 Absätze nach Titel)
        lines = job_ad_text.split('\n')
        einleitung_text = '\n'.join(lines[:5])  # Erste paar Zeilen
        
        user_prompt = f"""
        EINLEITUNG DER STELLENANZEIGE:
        {einleitung_text}
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Einleitung")
            
        except Exception as e:
            logger.error(f"Fehler bei Einleitungs-Bewertung: {e}")
            return self._create_error_category("Einleitung")
    
    async def _score_aufgabenbeschreibung(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Aufgabenbeschreibung"""
        
        system_prompt = """Bewerte die AUFGABENBESCHREIBUNG nach Stepstone-Standards:
        
        1. **Struktur & Lesbarkeit** (30 Punkte)
           - Klare Bulletpoints oder Absätze?
           - Keine Textblöcke?
           - Übersichtlich gegliedert?
        
        2. **Konkretheit** (40 Punkte)
           - Keine Floskeln wie "abwechslungsreiche Tätigkeiten"?
           - Messbare, spezifische Aufgaben?
           - Realistische Beschreibung?
        
        3. **Vollständigkeit** (30 Punkte)
           - Hauptaufgaben abgedeckt?
           - Wichtige Tätigkeiten erwähnt?
           - Ausgewogene Darstellung?"""
        
        # Aufgaben-Sektion finden
        aufgaben_section = self._extract_section(job_ad_text, ["aufgaben", "tätigkeiten", "ihre aufgaben", "das erwartet"])
        
        user_prompt = f"""
        AUFGABENBESCHREIBUNG:
        {aufgaben_section[:800]}
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2,VORSCHLAG3"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Aufgabenbeschreibung")
            
        except Exception as e:
            logger.error(f"Fehler bei Aufgaben-Bewertung: {e}")
            return self._create_error_category("Aufgabenbeschreibung")
    
    async def _score_profil_anforderungen(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Profil & Anforderungen"""
        
        system_prompt = """Bewerte PROFIL & ANFORDERUNGEN nach Stepstone-Kriterien:
        
        1. **Relevanz** (40 Punkte)
           - Realistische Muss-/Kann-Kriterien?
           - Keine Überqualifikation gefordert?
           - Angemessen für die Position?
        
        2. **Verständlichkeit** (30 Punkte)
           - Keine Fachjargon-Überladung?
           - Klare, verständliche Sprache?
           - Auch für Branchenfremde verständlich?
        
        3. **Fairness & Inklusion** (30 Punkte)
           - Keine verdeckte Diskriminierung?
           - AGG-konform?
           - Diverse Bewerber ermutigt?"""
        
        profil_section = self._extract_section(job_ad_text, ["profil", "anforderungen", "qualifikation", "ihr profil", "das bringen sie mit"])
        
        user_prompt = f"""
        PROFIL & ANFORDERUNGEN:
        {profil_section[:800]}
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Profil & Anforderungen")
            
        except Exception as e:
            logger.error(f"Fehler bei Profil-Bewertung: {e}")
            return self._create_error_category("Profil & Anforderungen")
    
    async def _score_benefits(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Benefits"""
        
        system_prompt = """Bewerte BENEFITS nach Stepstone-Standards:
        
        1. **Attraktivität & Vielfalt** (40 Punkte)
           - Mix aus monetären und nicht-monetären Benefits?
           - Attraktiv für Zielgruppe?
           - Vielfältige Angebote?
        
        2. **Authentizität** (30 Punkte)
           - Realistisch und glaubwürdig?
           - Nicht übertrieben?
           - Konkret beschrieben?
        
        3. **Klarheit** (30 Punkte)
           - Übersichtlich dargestellt?
           - Keine leeren Floskeln?
           - Spezifisch formuliert?"""
        
        benefits_section = self._extract_section(job_ad_text, ["wir bieten", "benefits", "vorteile", "das bieten wir"])
        
        user_prompt = f"""
        BENEFITS-SEKTION:
        {benefits_section[:600]}
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Benefits")
            
        except Exception as e:
            logger.error(f"Fehler bei Benefits-Bewertung: {e}")
            return self._create_error_category("Benefits")
    
    async def _score_kontakt_bewerbung(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Kontakt & Bewerbungsprozess"""
        
        system_prompt = """Bewerte KONTAKT & BEWERBUNGSPROZESS:
        
        1. **Transparenz** (40 Punkte)
           - Klare Kontaktdaten?
           - Ansprechpartner sichtbar?
           - Wie kann man sich bewerben?
        
        2. **Einfachheit** (35 Punkte)
           - Bewerbungsprozess erklärt?
           - Kurze Wege beschrieben?
           - Nicht zu kompliziert?
        
        3. **Zusatzinfos** (25 Punkte)
           - Gehaltsangaben wenn möglich?
           - Starttermin genannt?
           - Weitere wichtige Details?"""
        
        # Meist am Ende der Anzeige
        kontakt_section = job_ad_text[-500:]  # Letzten 500 Zeichen
        
        user_prompt = f"""
        KONTAKT & BEWERBUNG (meist Ende der Anzeige):
        {kontakt_section}
        
        GESAMTE ANZEIGE (für Kontext):
        {job_ad_text[:200]}...
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Kontakt & Bewerbung")
            
        except Exception as e:
            logger.error(f"Fehler bei Kontakt-Bewertung: {e}")
            return self._create_error_category("Kontakt & Bewerbung")
    
    async def _score_sprache_stil(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung Sprache & Stil"""
        
        system_prompt = """Bewerte SPRACHE & STIL nach Stepstone-Kriterien:
        
        1. **Zielgruppenorientierung** (35 Punkte)
           - Sprache passt zur Zielgruppe?
           - Angemessene Komplexität?
           - Regionalität berücksichtigt?
        
        2. **Genderneutralität** (35 Punkte)
           - Gendergerechte Sprache verwendet?
           - Decoder-Test bestanden?
           - Inklusiv formuliert?
        
        3. **Aktivierende Sprache** (30 Punkte)
           - Positive, einladende Wortwahl?
           - Motivierend geschrieben?
           - Action-orientiert?"""
        
        user_prompt = f"""
        STELLENANZEIGE (für Sprach-/Stilanalyse):
        {job_ad_text[:1200]}
        
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Sprache & Stil")
            
        except Exception as e:
            logger.error(f"Fehler bei Sprache-Bewertung: {e}")
            return self._create_error_category("Sprache & Stil")
    
    async def _score_suchverhalten_keywords(self, job_ad_text: str, job_title: str) -> ScoreCategory:
        """Bewertung Suchverhalten & Keywords"""
        
        system_prompt = """Bewerte SUCHVERHALTEN & KEYWORDS:
        
        1. **Keyword-Optimierung** (40 Punkte)
           - Relevante Suchbegriffe integriert?
           - Stepstone-Algorithmus berücksichtigt?
           - Natürlich eingebaut?
        
        2. **Lesefreundlichkeit** (30 Punkte)
           - Gute Absätze und Struktur?
           - Bulletpoints verwendet?
           - Zwischenüberschriften?
        
        3. **Aufmerksamkeitsspanne** (30 Punkte)
           - Wichtige Infos früh platziert?
           - "Goldfisch-Theorie" berücksichtigt?
           - Schnell erfassbar?"""
        
        user_prompt = f"""
        JOBTITEL: {job_title}
        STELLENANZEIGE: {job_ad_text[:1000]}
        
        Analysiere auf Keywords und Suchverhalten.
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=400
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "Suchverhalten & Keywords")
            
        except Exception as e:
            logger.error(f"Fehler bei Suchverhalten-Bewertung: {e}")
            return self._create_error_category("Suchverhalten & Keywords")
    
    async def _score_agg_bias_check(self, job_ad_text: str) -> ScoreCategory:
        """Bewertung AGG & Bias Check"""
        
        system_prompt = """Bewerte AGG-KONFORMITÄT & BIAS-CHECK (sehr wichtig!):
        
        1. **AGG-Konformität** (50 Punkte)
           - Keine Alters-Diskriminierung ("junges Team", Altersangaben)?
           - Keine Geschlechts-Diskriminierung?
           - Keine Herkunfts-/Religions-Diskriminierung?
           - Keine Behinderung-Diskriminierung?
        
        2. **Genderbias Decoder-Test** (30 Punkte)
           - Keine männlich-konnotierten Begriffe übermäßig?
           - Balanced Language?
           - Frauen/Diverse ermutigt zu bewerben?
        
        3. **Inklusiver Ton** (20 Punkte)
           - Alle Gruppen angesprochen?
           - Barrierefreie Sprache?
           - Diverse Teams erwähnt?
        
        ACHTUNG: Bei AGG-Verstößen maximal 30 Punkte Gesamtscore!"""
        
        user_prompt = f"""
        STELLENANZEIGE (für AGG & Bias-Analyse):
        {job_ad_text}
        
        Prüfe sehr sorgfältig auf Diskriminierung!
        Format: SCORE|FEEDBACK|VORSCHLAG1,VORSCHLAG2"""
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            return self._parse_score_response(result, "AGG & Bias Check")
            
        except Exception as e:
            logger.error(f"Fehler bei AGG-Bewertung: {e}")
            return self._create_error_category("AGG & Bias Check")
    
    def _extract_section(self, text: str, keywords: List[str]) -> str:
        """Extrahiere Textabschnitt basierend auf Keywords"""
        text_lower = text.lower()
        lines = text.split('\n')
        
        section_lines = []
        in_section = False
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if this line contains any of our keywords
            if any(keyword in line_lower for keyword in keywords):
                in_section = True
                section_lines.append(line)
                continue
            
            if in_section:
                # Stop if we hit another section or empty lines
                if line.strip() == '' and len(section_lines) > 3:
                    break
                if any(stop_word in line_lower for stop_word in ['bewerbung', 'kontakt', 'über uns', 'unternehmen']):
                    break
                section_lines.append(line)
        
        result = '\n'.join(section_lines)
        return result if result else text[:300]  # Fallback to first 300 chars
    
    def _parse_score_response(self, response: str, category_name: str) -> ScoreCategory:
        """Parse AI response in format: SCORE|FEEDBACK|SUGGESTION1,SUGGESTION2"""
        try:
            parts = response.split('|')
            
            # Extract score
            score_text = parts[0].strip()
            score_match = re.search(r'(\d+(?:\.\d+)?)', score_text)
            score = float(score_match.group(1)) if score_match else 50.0
            score = max(0, min(100, score))  # Clamp between 0-100
            
            # Extract feedback
            feedback = parts[1].strip() if len(parts) > 1 else "Keine detaillierte Bewertung verfügbar"
            
            # Extract suggestions
            suggestions = []
            if len(parts) > 2:
                suggestions_text = parts[2].strip()
                suggestions = [s.strip() for s in suggestions_text.split(',') if s.strip()]
            
            if not suggestions:
                suggestions = ["Keine spezifischen Verbesserungsvorschläge"]
            
            return ScoreCategory(
                name=category_name,
                score=score,
                feedback=feedback,
                suggestions=suggestions[:3],  # Max 3 suggestions
                level=self._get_score_level(score)
            )
            
        except Exception as e:
            logger.error(f"Fehler beim Parsen der Antwort für {category_name}: {e}")
            return self._create_error_category(category_name)
    
    def _create_error_category(self, name: str) -> ScoreCategory:
        """Erstelle Fehler-Kategorie bei technischen Problemen"""
        return ScoreCategory(
            name=name,
            score=50.0,
            feedback=f"Bewertung von {name} konnte nicht durchgeführt werden (technischer Fehler)",
            suggestions=["Bitte versuchen Sie es später erneut"],
            level=ScoreLevel.VERBESSERUNGSWUERDIG
        )

# Global Stepstone scoring service instance  
stepstone_scoring_service = StepstoneScoringService()
