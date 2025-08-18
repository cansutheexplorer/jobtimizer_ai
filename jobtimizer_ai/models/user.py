# models/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional
from datetime import datetime
from bson import ObjectId


class CompanyInfo(BaseModel):
    """Company information model"""
    company_name: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(..., min_length=1, max_length=100)
    mission: Optional[str] = Field(None, max_length=500)
    culture: List[str] = Field(default_factory=list)
    values: List[str] = Field(default_factory=list)
    size: Optional[str] = Field(None, pattern=r'^\d+-\d+$|^<\d+$|^>\d+$')  # e.g., "50-200", "<10", ">500"
    location: Optional[str] = Field(None, max_length=200)


class TemplateCustomizations(BaseModel):
    """Template customization preferences"""
    include_benefits: bool = True
    emphasize_growth: bool = True
    include_company_culture: bool = True
    show_salary_range: bool = False


class UserPreferences(BaseModel):
    """User preference model for job ad generation"""
    tone: str = Field("du", pattern=r'^(du|sie)$')
    formality_level: str = Field("professional", pattern=r'^(casual|professional|formal)$')
    candidate_focus: str = Field("medium", pattern=r'^(low|medium|high)$')
    language_style: str = Field("modern", pattern=r'^(traditional|modern|startup)$')
    template_customizations: TemplateCustomizations = Field(default_factory=TemplateCustomizations)


class User(BaseModel):
    """User model"""
    username: EmailStr
    password_hash: str
    company_info: CompanyInfo
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

    class Config:
        # Allow ObjectId serialization
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class UserLogin(BaseModel):
    """User login model"""
    username: EmailStr
    password: str = Field(..., min_length=6)


class UserRegistration(BaseModel):
    """User registration model"""
    username: EmailStr
    password: str = Field(..., min_length=6)
    company_info: CompanyInfo
    preferences: Optional[UserPreferences] = None