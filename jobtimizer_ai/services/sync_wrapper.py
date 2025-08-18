import asyncio
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime  # Add this import

from services.database import db_service
from services.openai_service import openai_service
from models import JobAdRequest, JobAdResponse, FeedbackRequest
from config import settings

logger = logging.getLogger(__name__)


import asyncio
import threading

class SyncJobtimizerService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._initialized = False

        # Create a dedicated background loop
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._start_loop, daemon=True)
        self.loop_thread.start()

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run_async(self, coro):
        """Submit coroutine to the background loop and block until result"""
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result()  # block until done
        except Exception as e:
            logger.error(f"Async execution error: {e}")
            raise

    def initialize(self):
        """Initialize the service"""
        if self._initialized:
            return True

        try:
            # Ensure database service is fresh
            async def fresh_connect():
                # Disconnect if already connected
                if db_service.client:
                    db_service.client.close()
                    db_service.client = None
                    db_service.db = None
                    db_service.users_col = None
                    db_service.occupations_col = None
                    db_service.feedback_col = None

                # Fresh connection
                await db_service.connect()

                # Test the connection
                if db_service.occupations_col is None:
                    raise RuntimeError("Database connection not properly established")

                return await db_service.occupations_col.count_documents({})

            count = self._run_async(fresh_connect())
            logger.info(f"Sync service initialized. Found {count} ESCO occupations")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize sync service: {e}")
            return False

    def search_job_titles(self, query: str, limit: int = 8) -> List[Dict]:
        """Search job titles for autocomplete suggestions using vector embeddings"""
        if len(query) < 2:
            return []

        try:
            async def search_titles_async():
                # Embed user input
                query_embedding = await openai_service.create_embedding(query)

                # Vector search in DB
                occupations = await db_service.vector_search_occupations(query_embedding, limit)

                if not occupations:
                    return [{"title": "couldn't found", "original_name": "", "esco_code": "", "description": ""}]

                # Format results
                suggestions = []
                for occ in occupations:
                    name = occ.get('name', 'Unknown')
                    name_with_suffix = f"{name} (m/w/d)"
                    suggestions.append({
                        'title': name_with_suffix,
                        'original_name': name,
                        'esco_code': occ.get('esco_code', ''),
                        'description': occ.get('description', '')[:100] + '...' if occ.get('description') else ''
                    })
                return suggestions

            return self._run_async(search_titles_async())

        except Exception as e:
            logger.error(f"Job title search error: {e}")
            return [{"title": "couldn't found", "original_name": "", "esco_code": "", "description": ""}]

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        try:
            from utils.auth import verify_password

            # Get user from database
            user = self._run_async(db_service.get_user_by_username(username))

            if user and verify_password(password, user['password_hash']):
                # Update last login
                self._run_async(db_service.update_user_login(user['_id']))
                logger.info(f"User {username} authenticated successfully")
                return user

            logger.warning(f"Authentication failed for user {username}")
            return None

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    def register_user(self, registration_data: Dict) -> str:
        """Register a new user"""
        try:
            from utils.auth import hash_password
            from datetime import datetime

            async def register_user_async():
                # Check if user already exists
                existing_user = await db_service.get_user_by_username(registration_data['username'])

                if existing_user:
                    raise ValueError("User with this email already exists")

                # Prepare user data
                user_data = registration_data.copy()
                user_data['password_hash'] = hash_password(user_data.pop('password'))
                user_data['created_at'] = datetime.utcnow()

                # Set default preferences if not provided
                if 'preferences' not in user_data:
                    user_data['preferences'] = settings.default_preferences

                # Create user
                return await db_service.create_user(user_data)

            user_id = self._run_async(register_user_async())
            logger.info(f"New user registered: {registration_data['username']}")
            return user_id

        except Exception as e:
            logger.error(f"Registration error: {e}")
            raise

    def search_occupations(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for ESCO occupations using vector embeddings only"""
        try:
            async def comprehensive_search():
                # Step 1: Embed user input
                query_embedding = await openai_service.create_embedding(query)

                # Step 2: Vector search
                results = await db_service.vector_search_occupations(query_embedding, limit)

                # Step 3: If no results, return fallback
                if not results:
                    logger.warning(f"No matches found for '{query}'")
                    return [{"name": "couldn't found", "esco_code": "", "description": "", "score": 0.0}]

                return results

            return self._run_async(comprehensive_search())

        except Exception as e:
            logger.error(f"Search error: {e}")
            return [{"name": "couldn't found", "esco_code": "", "description": "", "score": 0.0}]

    def generate_job_ad(self, request: JobAdRequest, user_id: str) -> JobAdResponse:
    """Stellenanzeige mit Vektorsuche für ESCO-Matching generieren"""
    try:
        async def generate_async():
            # Get user data
            user = await db_service.get_user_by_id(user_id)
            if not user:
                raise ValueError("Benutzer nicht gefunden")

            # Vector search for matching occupation
            occupations = await self._search_occupations_async(request.job_title, limit=1)

            if not occupations or occupations[0].get("name") == "couldn't found":
                broader_query = request.job_title.split()[0]
                occupations = await self._search_occupations_async(broader_query, limit=1)

            if not occupations or occupations[0].get("name") == "couldn't found":
                raise ValueError(f"Keine passende Berufsbezeichnung gefunden für: {request.job_title}")

            raw_esco_data = occupations[0]

            company_info = user.get('company_info', {})
            preferences = user.get('preferences', settings.default_preferences)

            # Prepare the final job title with seniority if provided
            final_job_title = request.job_title
            if request.seniority_level and request.seniority_years:
                from models.job_ad import SENIORITY_LEVELS
                seniority_obj = next((s for s in SENIORITY_LEVELS if s.level == request.seniority_level), None)
                if seniority_obj and seniority_obj.display_name:  # Only add if display_name exists
                    final_job_title = f"{seniority_obj.display_name} {request.job_title}"

            # Add seniority context - NO pay_range_context
            seniority_context = ""
            if request.seniority_level and request.seniority_years:
                seniority_context = f"Seniority Level: {request.seniority_level} ({request.seniority_years} Erfahrung). "

            combined_context = seniority_context + (request.additional_context or "")

            # Generate job ad using OpenAI service
            job_ad = await openai_service.generate_job_ad(
                esco_data=raw_esco_data,
                company_info=company_info,
                preferences=preferences,
                additional_context=combined_context,
                final_job_title=final_job_title
            )

            # Normalize ESCO data
            normalized_esco_data = openai_service._normalize_esco_data(raw_esco_data)

            from models import ESCOData
            esco_data_obj = ESCOData(**normalized_esco_data)

            return JobAdResponse(
                job_ad=job_ad,
                esco_data=esco_data_obj,
                generation_timestamp=datetime.utcnow(),
                user_id=user_id
            )

        response = self._run_async(generate_async())
        logger.info(f"Stellenanzeige generiert für Benutzer {user_id}, ESCO-Match: {response.esco_data.name}")
        return response

    except Exception as e:
        logger.error(f"Fehler bei der Stellenanzeigen-Generierung: {e}")
        raise

    def update_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        """Update user preferences"""
        try:
            async def update_preferences_async():
                return await db_service.update_user_preferences(user_id, preferences)

            result = self._run_async(update_preferences_async())
            logger.info(f"Updated preferences for user {user_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Failed to update user preferences: {e}")
            return False

    async def _search_occupations_async(self, query: str, limit: int = 5) -> List[Dict]:
        """Async helper for searching occupations using vector embeddings only"""
        try:
            # Step 1: Embed user input
            query_embedding = await openai_service.create_embedding(query)

            # Step 2: Vector search
            results = await db_service.vector_search_occupations(query_embedding, limit)

            # Step 3: Fallback if no results
            if not results:
                logger.warning(f"No vector match found for '{query}'")
                return [{"name": "konnte nicht gefunden", "esco_code": "", "description": "", "score": 0.0}]

            return results

        except Exception as e:
            logger.error(f"Vector search failed for '{query}': {e}")
            return [{"name": "konnte nicht gefunden", "esco_code": "", "description": "", "score": 0.0}]

    def refine_job_ad_with_feedback(self, original_ad: str,
                                    feedback_request: FeedbackRequest,
                                    user_id: str) -> str:
        """Refine job ad based on feedback"""
        try:
            async def refine_async():
                # Convert feedback to expected format
                feedback_data = {
                    "feedback_type": feedback_request.feedback_type,
                    "button_clicks": feedback_request.button_clicks or [],
                    "text_feedback": feedback_request.text_feedback,
                    "manual_changes": feedback_request.manual_changes
                }

                # Refine using OpenAI
                refined_ad = await openai_service.refine_job_ad_with_feedback(original_ad, feedback_data)

                # Save feedback
                from models import Feedback
                from datetime import datetime

                feedback = Feedback(
                    user_id=user_id,
                    job_title="",
                    original_ad=original_ad,
                    feedback_request=feedback_request,
                    refined_ad=refined_ad,
                    created_at=datetime.utcnow()
                )

                await db_service.save_feedback(feedback.model_dump())
                return refined_ad

            refined_ad = self._run_async(refine_async())

            self._update_user_preferences_from_feedback(user_id, feedback_request)

            logger.info(f"Job ad refined for user {user_id}")
            return refined_ad

        except Exception as e:
            logger.error(f"Refinement error: {e}")
            raise

    def _update_user_preferences_from_feedback(self, user_id: str, feedback: FeedbackRequest):
        """Update user preferences based on feedback patterns"""
        try:
            async def update_preferences_async():
                user = await db_service.get_user_by_id(user_id)
                if not user:
                    return

                preferences = user.get('preferences', {})
                updated = False

                # Analyze button clicks - Updated for new feedback options
                if feedback.button_clicks:
                    for click in feedback.button_clicks:
                        if click == "mehr_formell":
                            preferences['formality_level'] = 'formal'
                            updated = True
                        elif click == "lockerer":  # Changed from "weniger_formell" to "lockerer"
                            preferences['casual_tone'] = True  # Set casual_tone instead of formality_level
                            updated = True
                        elif click == "mehr_du_ton":
                            preferences['tone'] = 'du'
                            updated = True
                        elif click == "mehr_sie_ton":
                            preferences['tone'] = 'sie'
                            updated = True
                        elif click == "mehr_benefits":
                            if 'template_customizations' not in preferences:
                                preferences['template_customizations'] = {}
                            preferences['template_customizations']['include_benefits'] = True
                            updated = True

                # Analyze text feedback
                if feedback.text_feedback:
                    text = feedback.text_feedback.lower()
                    if 'formell' in text or 'formal' in text:
                        preferences['formality_level'] = 'formal'
                        updated = True
                    elif 'locker' in text or 'casual' in text:
                        preferences['casual_tone'] = True
                        updated = True

                # Save updated preferences
                if updated:
                    await db_service.update_user_preferences(user_id, preferences)
                    logger.info(f"Updated preferences for user {user_id}")

            self._run_async(update_preferences_async())

        except Exception as e:
            logger.error(f"Preference update error: {e}")

    def cleanup(self):
        """Cleanup resources"""
        if self.executor:
            self.executor.shutdown(wait=True)


# Global sync service instance
sync_service = SyncJobtimizerService()

