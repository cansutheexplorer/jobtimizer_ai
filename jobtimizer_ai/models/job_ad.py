# models/job_ad.py
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId


class CompanyInfo(BaseModel):
    """Company metadata"""
    company_name: str
    industry: str
    mission: Optional[str] = None
    culture: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)
    size: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


class ESCOData(BaseModel):
    """ESCO occupation data model - matches what your code expects"""
    esco_code: str
    name: str
    description: str = ""
    essential_skills: List[str] = Field(default_factory=list)
    optional_skills: List[str] = Field(default_factory=list)
    alternative_labels: List[str] = Field(default_factory=list)
    regulatory_info: Optional[str] = None
    url: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class JobAdResponse(BaseModel):
    """Job ad generation response model"""
    job_ad: str  # The generated job advertisement text
    esco_data: ESCOData  # The matched ESCO occupation data
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FeedbackRequest(BaseModel):
    """Feedback request model"""
    feedback_type: str = Field(..., pattern=r'^(button_click|text_feedback|manual_edit)$')
    button_clicks: Optional[List[str]] = Field(default_factory=list)
    text_feedback: Optional[str] = None
    manual_changes: Optional[str] = None


class Feedback(BaseModel):
    """Feedback storage model"""
    user_id: str
    job_title: str
    original_ad: str
    feedback_request: FeedbackRequest
    refined_ad: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class SeniorityLevel(BaseModel):
    """Seniority level options - now in German"""
    level: str
    years: str
    display_name: str


SENIORITY_LEVELS = [
    SeniorityLevel(level="entry", years="0-1 Jahre", display_name="Entry Level"),
    SeniorityLevel(level="junior", years="1-5 Jahre", display_name="Junior"),
    SeniorityLevel(level="mid", years="6-9 Jahre", display_name="Mid-Level"),
    SeniorityLevel(level="senior", years="10+ Jahre", display_name="Senior")
]


class JobAdRequest(BaseModel):
    """Job ad generation request model - removed pay_range"""
    job_title: str = Field(..., min_length=1, max_length=150)
    additional_context: Optional[str] = Field(None, max_length=2000)
    seniority_level: Optional[str] = Field(None, help="Optional seniority level to add to job title")
    seniority_years: Optional[str] = Field(None, help="Years of experience for the seniority level")


class UserPreferences(BaseModel):
    """Enhanced user preferences for job ad generation"""
    # Core tone options - now includes 'lockerer' as separate option
    tone: str = Field(default="sie", pattern=r'^(sie|du|ohne)$')
    casual_tone: bool = Field(default=False, help="Make it more casual/relaxed regardless of Sie/Du")
    formality_level: str = Field(default="formal", pattern=r'^(formal|semi_formal|casual)$')
    candidate_focus: str = Field(default="experience", pattern=r'^(experience|potential|skills|culture,mission,vision)$')
    language_style: str = Field(default="Standard", pattern=r'^(Standard|Einfacher Deutsch|Kreativ)$')

    class Config:
        arbitrary_types_allowed = True


class User(BaseModel):
    """User model"""
    username: str
    password_hash: str
    company_info: CompanyInfo
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


# Alias for readability
EscoOccupation = ESCOData
