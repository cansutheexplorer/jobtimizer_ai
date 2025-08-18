# services/job_generator.py - Update the search_occupations method
import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime

from services.database import db_service
from services.openai_service import openai_service
from models import JobAdRequest, JobAdResponse, FeedbackRequest, Feedback
from config import settings

logger = logging.getLogger(__name__)


class JobGeneratorService:
    """Main job ad generation service"""

    def __init__(self):
        self.db = db_service
        self.openai = openai_service

    async def initialize(self):
        """Initialize the service by connecting to database"""
        await self.db.connect()

        # Test that ESCO data exists
        sample_occupations = await self.db.get_random_occupations(3)
        if sample_occupations:
            logger.info(
                f"Successfully connected to ESCO data. Sample occupations: {[occ['name'] for occ in sample_occupations]}")
        else:
            logger.warning("No ESCO occupations found in database")

    async def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        from utils.auth import verify_password

        user = await self.db.get_user_by_username(username)
        if user and verify_password(password, user['password_hash']):
            await self.db.update_user_login(user['_id'])
            logger.info(f"User {username} authenticated successfully")
            return user

        logger.warning(f"Authentication failed for user {username}")
        return None

    async def register_user(self, registration_data: Dict) -> str:
        """Register a new user"""
        from utils.auth import hash_password

        # Check if user already exists
        existing_user = await self.db.get_user_by_username(registration_data['username'])
        if existing_user:
            raise ValueError("User with this email already exists")

        # Hash password
        registration_data['password_hash'] = hash_password(registration_data.pop('password'))
        registration_data['created_at'] = datetime.utcnow()

        # Set default preferences if not provided
        if 'preferences' not in registration_data:
            registration_data['preferences'] = settings.default_preferences

        user_id = await self.db.create_user(registration_data)
        logger.info(f"New user registered: {registration_data['username']}")
        return user_id

    async def search_occupations(self, query: str, limit: int = 5) -> List[Dict]:
        """Search for ESCO occupations using both vector and text search"""
        results = []

        # Try vector search first (if embeddings are available)
        try:
            # Create embedding for the search query
            query_embedding = await self.openai.create_embedding(query)
            vector_results = await self.db.vector_search_occupations(query_embedding, limit)

            if vector_results:
                logger.info(f"Vector search found {len(vector_results)} results for: '{query}'")
                results = vector_results
            else:
                # Fallback to text search
                logger.info("Vector search returned no results, falling back to text search")
                results = await self.db.search_occupations_by_text(query, limit)

        except Exception as e:
            logger.warning(f"Vector search failed: {e}. Using text search fallback.")
            # Fallback to text search
            results = await self.db.search_occupations_by_text(query, limit)

        logger.info(f"Final search results: {len(results)} occupations found for query: '{query}'")

        # Log the found occupations for debugging
        for i, occ in enumerate(results[:3]):  # Log first 3
            logger.info(f"  {i + 1}. {occ.get('name', 'Unknown')} (Score: {occ.get('score', 'N/A')})")

        return results

    async def generate_job_ad(self, request: JobAdRequest, user_id: str) -> JobAdResponse:
        """Generate a job ad"""
        # Get user data
        user = await self.db.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Search for relevant occupation
        occupations = await self.search_occupations(request.job_title, limit=1)
        if not occupations:
            # If no exact match, try a broader search
            broader_query = request.job_title.split()[0]  # Take first word
            occupations = await self.search_occupations(broader_query, limit=1)

        if not occupations:
            raise ValueError(f"No matching occupation found for: {request.job_title}")

        esco_data = occupations[0]
        company_info = user.get('company_info', {})
        preferences = user.get('preferences', settings.default_preferences)

        # Generate job ad using OpenAI
        job_ad = await self.openai.generate_job_ad(
            esco_data=esco_data,
            company_info=company_info,
            preferences=preferences,
            additional_context=request.additional_context or ""
        )

        response = JobAdResponse(
            job_ad=job_ad,
            esco_data=esco_data,
            generation_timestamp=datetime.utcnow(),
            user_id=user_id
        )

        logger.info(
            f"Job ad generated for user {user_id}, job title: {request.job_title}, matched ESCO: {esco_data.get('name')}")
        return response

    # services/job_generator.py - Update the refine_job_ad_with_feedback method
    async def refine_job_ad_with_feedback(self, original_ad: str,
                                          feedback_request: FeedbackRequest,
                                          user_id: str) -> str:
        """Refine job ad based on feedback"""

        # Convert feedback request to format expected by OpenAI
        feedback_data = {
            "feedback_type": feedback_request.feedback_type,
            "button_clicks": feedback_request.button_clicks or [],
            "text_feedback": feedback_request.text_feedback,
            "manual_changes": feedback_request.manual_changes
        }

        # Refine using OpenAI
        refined_ad = await self.openai.refine_job_ad_with_feedback(
            original_ad, feedback_data
        )

        # Save feedback to database
        feedback = Feedback(
            user_id=user_id,
            job_title="",  # We could extract this from the ad
            original_ad=original_ad,
            feedback_request=feedback_request,
            refined_ad=refined_ad
        )

        await self.db.save_feedback(feedback.model_dump())  # Changed from .dict() to .model_dump()

        # Update user preferences based on feedback patterns
        await self._update_preferences_from_feedback(user_id, feedback_request)

        logger.info(f"Job ad refined for user {user_id}")
        return refined_ad

    async def _update_preferences_from_feedback(self, user_id: str,
                                                feedback: FeedbackRequest):
        """Update user preferences based on feedback patterns"""
        user = await self.db.get_user_by_id(user_id)
        if not user:
            return

        preferences = user.get('preferences', {})
        updated = False

        # Analyze button clicks for preference updates
        if feedback.button_clicks:
            for click in feedback.button_clicks:
                if click == "mehr_formell":
                    preferences['formality_level'] = 'formal'
                    updated = True
                elif click == "weniger_formell":
                    preferences['formality_level'] = 'casual'
                    updated = True
                elif click == "mehr_du_ton":
                    preferences['tone'] = 'du'
                    updated = True
                elif click == "mehr_sie_ton":
                    preferences['tone'] = 'sie'
                    updated = True
                elif click == "mehr_benefits":
                    preferences['template_customizations']['include_benefits'] = True
                    updated = True

        # Analyze text feedback for preferences
        if feedback.text_feedback:
            text = feedback.text_feedback.lower()
            if 'formell' in text or 'formal' in text:
                preferences['formality_level'] = 'formal'
                updated = True
            elif 'locker' in text or 'casual' in text:
                preferences['formality_level'] = 'casual'
                updated = True
        if updated:
            await self.db.update_user_preferences(user_id, preferences)
            logger.info(f"Updated preferences for user {user_id}")

# Global job generator service
job_generator = JobGeneratorService()