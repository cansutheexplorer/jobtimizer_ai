import asyncio
from openai import AsyncOpenAI
from typing import Dict, List
import logging
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

    async def generate_job_ad(
            self,
            esco_data: Dict,
            company_info: Dict,
            preferences: Dict,
            additional_context: str = "",
            final_job_title: str = None
    ) -> str:
        """Generate a German job ad using OpenAI with AGG compliance, tone scaling, and seniority support"""

        # Normalize incoming ESCO data
        esco_data = self._normalize_esco_data(esco_data)

        # Use final job title if provided, otherwise use ESCO name
        job_title_to_use = final_job_title or esco_data.get('name', 'Unknown Position')

        system_prompt = """You are Jobtimizer, an expert system for generating and refining German job advertisements that are 10% Company max, and then about 30% Tasks, Profile and Benefits - depends on the Role & Department.
Your purpose is to help companies create inclusive, professional, and optimized job ads based on ESCO occupational data, company context, user preferences, and seniority levels.

## Core Rules
- Always comply with German AGG (Allgemeines Gleichbehandlungsgesetz):
  - Keine Diskriminierung nach Rasse oder ethnischer Herkunft
  - Geschlecht: immer gendergerechte Formulierungen (z. B. "Mitarbeiter*in", "Kolleg*innen")
  - Religion und Weltanschauung: neutral, diskriminierungsfrei
  - Behinderung: keine Einschränkungen oder diskriminierende Formulierungen
  - Alter: niemals Begriffe wie „junges Team", keine Alterspräferenzen
  - Sexuelle Identität: inklusiv, ohne stereotype Sprache

## Seniority Level Handling
When a seniority level is provided in the job title or additional context:
- Entry Level (0-2 Jahre): Focus on learning opportunities, mentoring, basic requirements
- Junior (2-4 Jahre): Emphasize growth potential, teamwork, foundational skills
- Mid-Level (4-7 Jahre): Highlight project responsibility, technical expertise, leadership potential
- Senior (7-12 Jahre): Focus on strategic thinking, mentoring others, complex problem solving
- Lead/Principal (12+ Jahre): Emphasize vision, architecture decisions, team leadership, industry expertise

Adjust the entire job ad accordingly:
- Requirements should match the seniority level
- Responsibilities should be appropriate for the experience level
- Language tone should suit the target audience
- Benefits should appeal to professionals at that career stage

## Tone and Experience Scale
- Introduce a Tone/Experience Scale (1–5):
  - 1 = Senior/Expert audience → fachlich anspruchsvoll, detailliert, längere Texte
  - 5 = Entry-level audience → leicht verständlich, zugänglich, kürzere Texte
- Adjust tone, length, and focus automatically based on:
  - Candidate experience level (from seniority level and/or ESCO role)
  - User's feedback (e.g., "make it shorter", "use Du instead of Sie", "focus on teamwork")

## Input Structure
You will always receive structured input:

[JOB TITLE]
{job_title}

[ESCO BERUFSDATEN]
{esco_data}

[UNTERNEHMENSINFORMATIONEN]
{company_info}

[NUTZERPRÄFERENZEN]
{preferences}

[ZUSÄTZLICHER KONTEXT]
{additional_context}

## Task
1. Generate a German job advertisement that integrates all inputs and respects seniority level.
2. Ensure consistency across multiple outputs (same formatting, tone scale, compliance).
3. Make the ad professional, human-readable, and ready for publishing.
4. Adapt content complexity and requirements based on seniority level.
5. Mark placeholders clearly if information is missing.

## Refinement Loop
When given an original ad and user feedback:
- Interpret the feedback precisely (tone scale, length, focus, Du/Sie, seniority adjustments).
- Apply changes without losing overall consistency.
- Maintain AGG compliance at all times.
- Respect seniority-appropriate content.
- Return the improved ad as the final output.

## Output
- Return only the final German job ad text, clean and publishable.
- Use the provided job title exactly as given (including seniority prefix if present).
- Do not explain your reasoning, just output the optimized ad."""

        user_prompt = f"""Erstelle eine deutsche Stellenanzeige mit folgenden Eingaben:

[JOB TITLE]
{job_title_to_use}

[ESCO BERUFSDATEN]
{esco_data}

[UNTERNEHMENSINFORMATIONEN]
{company_info}

[NUTZERPRÄFERENZEN]
{preferences}

[ZUSÄTZLICHER KONTEXT]
{additional_context}

Verwende den angegebenen Job Title exakt wie vorgegeben. Falls ein Seniority Level im Titel enthalten ist (z.B. "Senior", "Junior", "Lead"), passe die gesamte Stellenanzeige entsprechend an das Erfahrungslevel an."""

        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2000
            )
            generated_ad = response.choices[0].message.content
            logger.info(f"Job ad generated successfully for title: {job_title_to_use}")
            return generated_ad

        except Exception as e:
            logger.error(f"Failed to generate job ad: {e}")
            raise

    async def refine_job_ad_with_feedback(self, original_ad: str, feedback: Dict) -> str:
        """Refine job ad based on user feedback while maintaining seniority appropriateness"""

        feedback_prompt = """Du bist Jobtimizer und spezialisiert auf die Verfeinerung deutscher Stellenanzeigen basierend auf Nutzerfeedback.

## Wichtige Regeln für die Verfeinerung:
1. Halte die AGG-Konformität ein (keine Diskriminierung nach Geschlecht, Alter, etc.)
2. Behalte das Seniority Level bei - wenn die ursprüngliche Anzeige für "Senior" oder "Junior" Positionen war, passe das Feedback entsprechend an
3. Achte auf angemessene Anforderungen für das Erfahrungslevel
4. Verwende gendergerechte Sprache
5. Halte den professionellen Ton bei

## Bei Seniority-Levels beachten:
- Entry/Junior: Einfachere Sprache, Fokus auf Lernen und Entwicklung
- Mid-Level: Ausgewogene Mischung aus Anforderungen und Entwicklungsmöglichkeiten  
- Senior/Lead: Anspruchsvollere Sprache, Fokus auf Führung und Expertise

Verfeinere die Stellenanzeige entsprechend dem Feedback, aber halte sie angemessen für das ursprüngliche Seniority Level."""

        user_message = f"""
URSPRÜNGLICHE STELLENANZEIGE:
{original_ad}

NUTZERFEEDBACK:
{feedback}

Bitte verfeinere die Stellenanzeige entsprechend diesem Feedback, aber achte darauf, dass das Seniority Level und die damit verbundenen Anforderungen angemessen bleiben."""

        try:
            response = await self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": feedback_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_completion_tokens=2000
            )

            refined_ad = response.choices[0].message.content
            logger.info("Job ad refined successfully with seniority awareness")
            return refined_ad

        except Exception as e:
            logger.error(f"Failed to refine job ad: {e}")
            raise


# Global OpenAI service instance
openai_service = OpenAIService()