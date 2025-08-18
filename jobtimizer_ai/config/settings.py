# config/settings.py
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # MongoDB Configuration
        self.mongo_username = quote_plus(os.getenv('MONGO_DATALAKE_USERNAME', ''))
        self.mongo_password = quote_plus(os.getenv('MONGO_DATALAKE_PASSWORD', ''))
        self.mongo_ip = os.getenv('MONGO_IP', '')

        if not all([self.mongo_username, self.mongo_password, self.mongo_ip]):
            raise ValueError("Missing required MongoDB environment variables")

        self.mongo_uri = f"mongodb://{self.mongo_username}:{self.mongo_password}@{self.mongo_ip}:27017/?authSource=admin"
        self.database_name = 'datalake'

        # OpenAI Configuration
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        if not self.openai_api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")

        # Application Configuration
        self.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-change-in-production')

        # Collection names
        self.users_collection = 'jobtimizer_users'
        self.occupations_collection = 'jobtimizer_occupations'
        self.feedback_collection = 'jobtimizer_feedback'

        # OpenAI settings
        self.embedding_model = 'text-embedding-3-large'
        self.chat_model = 'gpt-5-mini'

        # Default user preferences
        self.default_preferences = {
            "tone": "du",
            "formality_level": "professional",
            "candidate_focus": "medium",
            "language_style": "modern",
            "template_customizations": {
                "include_benefits": True,
                "emphasize_growth": True,
                "include_company_culture": True,
                "show_salary_range": False
            }
        }


# Global settings instance
settings = Settings()