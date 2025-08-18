# models/__init__.py
from .job_ad import (
    CompanyInfo,
    ESCOData,
    EscoOccupation,  # For backward compatibility
    JobAdRequest,
    JobAdResponse,
    FeedbackRequest,
    Feedback,
    User  # Add this if you created the User model
)

__all__ = [
    "CompanyInfo",
    "ESCOData",
    "EscoOccupation",
    "JobAdRequest",
    "JobAdResponse",
    "FeedbackRequest",
    "Feedback",
    "User"  # Add this if you created the User model
]
