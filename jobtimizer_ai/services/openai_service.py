import asyncio
from openai import AsyncOpenAI
from typing import Dict, List
import logging
import random
from config import settings

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI service for Jobtimizer"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def create_embedding(self, text: str) -> List[float]:
        """Create embedding for search queries"""
        try:
            response = await self.client.embeddings.create(
                model=settings.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            logger.info(f"Created embedding for text: '{text[:50]}...'")
            return embedding
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            raise

    def _normalize_esco_data(self, raw: Dict) -> Dict:
        """Normalize raw ESCO data from Mongo into the format expected by ESCOData model."""

        # Handle different possible field names for ESCO code
        esco_code = (
                raw.get("esco_code") or
                raw.get("code") or
                raw.get("concept_uri") or
                raw.get("conceptUri") or
                str(raw.get("_id", "UNKNOWN"))
        )

        # Handle different possible field names for occupation name
        name = (
                raw.get("name") or
                raw.get("preferred_label") or
                raw.get("title") or
                raw.get("preferredLabel") or
                "UNKNOWN"
        )

        # Handle different possible field names for description
        description = (
                raw.get("description") or
                raw.get("Definition") or
                raw.get("definition") or
                ""
        )

        # Normalize skills - extract strings from objects or keep as strings
        def extract_skill_names(skills_field):
            if not skills_field:
                return []

            result = []
            for skill in skills_field:
                if isinstance(skill, dict):
                    # Try different field names for skill name
                    skill_name = (
                            skill.get("name") or
                            skill.get("title") or
                            skill.get("preferred_label") or
                            skill.get("preferredLabel") or
                            str(skill)
                    )
                    result.append(str(skill_name))
                elif isinstance(skill, str):
                    result.append(skill)
                else:
                    result.append(str(skill))
            return result

        essential_skills = extract_skill_names(raw.get("essential_skills", []))
        optional_skills = extract_skill_names(raw.get("optional_skills", []))

        # Handle alternative labels
        alt_labels = raw.get("alternative_labels", [])
        if isinstance(alt_labels, str):
            alt_labels = [alt_labels]
        elif not isinstance(alt_labels, list):
            alt_labels = []
        else:
            # Ensure all items in the list are strings
            alt_labels = [str(label) for label in alt_labels]

        return {
            "esco_code": str(esco_code),
            "name": str(name),
            "description": str(description),
            "essential_skills": essential_skills,
            "optional_skills": optional_skills,
            "alternative_labels": alt_labels,
            "regulatory_info": raw.get("regulatory_info"),
            "url": raw.get("url")
        }

    def _generate_randomization_seed(self) -> Dict:
        """Generate randomization parameters to ensure variety in job ads"""
        return {
            "structure_variant": random.choice([
                "classic", "benefits_first", "culture_focus", "tasks_heavy"
            ]),
            "intro_style": random.choice([
                "direct", "welcoming", "mission_driven", "opportunity_focused"
            ]),
            "benefits_emphasis": random.choice([
                "growth", "work_life", "team", "innovation", "stability"
            ]),
            "closing_tone": random.choice([
                "encouraging", "professional", "excited", "straightforward"
            ]),
            "detail_level": random.choice([
                "concise", "detailed", "moderate"
            ])
        }

    async def generate_job_ad(
            self,
            esco_data: Dict,
            company_info: Dict,
            preferences: Dict,
            additional_context: str = "",
            final_job_title: str = None
    ) -> str:
        """Generate a German job ad with enhanced tone logic and randomization"""

        # Normalize incoming ESCO data
        esco_data = self._normalize_esco_data(esco_data)

        # Use final job title if provided, otherwise use ESCO name
        job_title_to_use = final_job_title or esco_data.get('name', 'Unknown Position')

        # Generate randomization parameters
        randomization = self._generate_randomization_seed()

        system_prompt = """Du bist Jobtimizer, ein Expertensystem für die Erstellung deutscher Stellenanzeigen, die AGG-konform, professionell und zielgruppengerecht sind.

## Wichtige Anweisungen

### AGG-Konformität (ABSOLUT ZWINGEND)
- Immer gendergerechte Sprache verwenden (m/w/d, Mitarbeiter*innen, etc.)
- Keine Altersangaben oder -präferenzen ("junges Team" etc.)
- Keine diskriminierenden Formulierungen bezüglich Herkunft, Religion, Behinderung, sexueller Identität

### Anrede und Tonalität
Du erhältst Präferenzen für:
1. **tone**: "sie", "du", "ohne" (Anrede-Form)
2. **casual_tone**: true/false (Lockerer Stil - UNABHÄNGIG von Sie/Du)

**Wichtig**: "casual_tone" = true bedeutet lockerer/entspannter, auch wenn "Sie" verwendet wird!

Beispiele:
- tone="sie" + casual_tone=false: "Sie bringen Erfahrung mit und haben..."
- tone="sie" + casual_tone=true: "Sie haben Lust auf spannende Projekte und bringen mit..."
- tone="du" + casual_tone=false: "Du bringst fundierte Kenntnisse mit und verfügst über..."
- tone="du" + casual_tone=true: "Du hast Bock auf neue Herausforderungen und bringst mit..."
- tone="ohne": Keine direkte Anrede, neutral formulieren

### Aufgaben und Profil-Abschnitte
Diese müssen IMMER vollständige Sätze sein, nicht nur Stichpunkte:

**Bei tone="du":**
- "Du entwickelst innovative Softwarelösungen"
- "Du bringst mindestens 3 Jahre Erfahrung mit"
- "Du arbeitest eng mit unserem Entwicklungsteam zusammen"

**Bei tone="sie":**
- "Sie entwickeln innovative Softwarelösungen"
- "Sie bringen mindestens 3 Jahre Erfahrung mit"
- "Sie arbeiten eng mit unserem Entwicklungsteam zusammen"

**Bei tone="ohne":**
- "Entwicklung innovativer Softwarelösungen"
- "Mindestens 3 Jahre Berufserfahrung erforderlich"
- "Enge Zusammenarbeit mit dem Entwicklungsteam"

### Wir bieten-Abschnitt
NUR ausfüllen wenn:
- Konkrete Zusatzinformationen über Benefits im additional_context stehen
- Ansonsten minimal halten oder ganz weglassen

### Seniority-Anpassung
Passe Inhalt und Sprache an die Erfahrungsstufe an:
- **Einstieg/Junior**: Einfacher, Fokus auf Lernen und Entwicklung
- **Erfahren/Mid**: Ausgewogene Anforderungen und Verantwortung
- **Senior/Lead**: Anspruchsvoller, Führung und strategisches Denken

### Randomisierung für Vielfalt
Nutze verschiedene Strukturen und Formulierungen, damit nicht alle Anzeigen gleich aussehen, auch bei ähnlichen Unternehmen.

## Input-Format
Du erhältst strukturierte Daten zu Job, Unternehmen, Präferenzen und Kontext.

## Output
Gib NUR die fertige deutsche Stellenanzeige aus - sauber formatiert und publikationsbereit."""

        user_prompt = f"""Erstelle eine deutsche Stellenanzeige mit diesen Daten:

**JOBTITEL**: {job_title_to_use}

**ESCO-BERUFSDATEN**: {esco_data}

**UNTERNEHMEN**: {company_info}

**PRÄFERENZEN**: {preferences}

**ZUSATZKONTEXT**: {additional_context}

**RANDOMISIERUNG**: {randomization}

WICHTIGE REGELN:
1. Verwende den Jobtitel EXAKT wie angegeben
2. Anrede nach "tone"-Präferenz: {preferences.get('tone', 'sie')}
3. Lockerer Stil wenn casual_tone=True: {preferences.get('casual_tone', False)}
4. Aufgaben & Profil als vollständige Sätze (nicht Stichpunkte!)
5. "Wir bieten" nur bei konkreten Benefits-Infos im Zusatzkontext
6. Seniority-gerechte Sprache und Anforderungen"""

        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000,
                temperature=0.7  # Added some creativity for variety
            )
            generated_ad = response.choices[0].message.content
            logger.info(f"Job ad generated successfully for title: {job_title_to_use}")
            return generated_ad

        except Exception as e:
            logger.error(f"Failed to generate job ad: {e}")
            raise

    async def refine_job_ad_with_feedback(self, original_ad: str, feedback: Dict) -> str:
        """Refine job ad based on user feedback with enhanced tone awareness"""

        feedback_prompt = """Du bist Jobtimizer und spezialisiert auf die Verfeinerung deutscher Stellenanzeigen basierend auf Nutzerfeedback.

## Wichtige Regeln für die Verfeinerung:
1. **AGG-Konformität beibehalten** (gendergerechte Sprache, keine Diskriminierung)
2. **Seniority Level respektieren** - ursprüngliche Zielgruppe beibehalten
3. **Ton-Logik verstehen**:
   - "lockerer" = entspannter/lockerer Stil (unabhängig von Sie/Du)
   - "mehr_formell" = formeller/professioneller
   - "weniger_formell" = siehe "lockerer"

## Spezielle Feedback-Behandlung:
- **"lockerer"**: Mache es entspannter, auch bei "Sie" verwendbar
- **"mehr_formell"**: Professioneller und strukturierter
- **"mehr_benefits"**: Ergänze sinnvolle Benefits
- **"mehr_unternehmenskultur"**: Betone Kultur und Werte

## Aufgaben & Profil Abschnitte:
Immer vollständige Sätze, angepasst an die Anrede:
- Bei Du-Form: "Du entwickelst...", "Du bringst mit..."
- Bei Sie-Form: "Sie entwickeln...", "Sie bringen mit..."
- Ohne direkte Anrede: "Entwicklung von...", "Erforderlich sind..."

Verfeinere die Stellenanzeige entsprechend, aber halte das Seniority Level und die Grundstruktur bei."""

        user_message = f"""
URSPRÜNGLICHE STELLENANZEIGE:
{original_ad}

NUTZERFEEDBACK:
{feedback}

Bitte verfeinere die Stellenanzeige entsprechend diesem Feedback. Achte besonders darauf:
- Vollständige Sätze in Aufgaben/Profil-Abschnitten
- Angemessene Anrede-Form beibehalten
- "Lockerer" bedeutet entspannter, aber nicht unprofessionell
- Seniority-Level-gerechte Inhalte beibehalten"""

        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": feedback_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_completion_tokens=2000,
                temperature=0.6  # Slight creativity for refinement
            )

            refined_ad = response.choices[0].message.content
            logger.info("Job ad refined successfully with enhanced tone awareness")
            return refined_ad

        except Exception as e:
            logger.error(f"Failed to refine job ad: {e}")
            raise


# Global OpenAI service instance
openai_service = OpenAIService()
