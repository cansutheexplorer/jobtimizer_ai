# models/__init__.py
from .job_ad import (
    CompanyInfo,
    ESCOData,
    EscoOccupation,
    JobAdRequest,
    JobAdResponse,
    FeedbackRequest,
    Feedback,
    User
)

from .scoring import (
    ScoreLevel,
    ScoreCategory,
    StepstoneScore,
    WestpressExpertScore,
    JobAdScore
)

__all__ = [
    "CompanyInfo",
    "ESCOData", 
    "EscoOccupation",
    "JobAdRequest",
    "JobAdResponse",
    "FeedbackRequest",
    "Feedback",
    "User",
    "ScoreLevel",
    "ScoreCategory", 
    "StepstoneScore",
    "WestpressExpertScore",
    "JobAdScore"
]
