"""Pydantic models for the API request/response contract matching technical-spec.md exactly."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.candidate import CandidateProfile
from src.models.feedback import InterviewFeedback


class InterviewRequest(BaseModel):
    """Unified request model for POST /api/interview.

    Modes:
    1. Init: sessionId + candidate (no message)
    2. Turn: sessionId + message (no candidate)
    """

    sessionId: str = Field(..., description="Session identifier for the interview")
    candidate: CandidateProfile | None = Field(None, description="Candidate profile (init request only)")
    message: str | None = Field(None, description="Candidate's answer (turn request only)")


class InterviewResponse(BaseModel):
    """Response model for POST /api/interview matching technical-spec.md."""

    reply: str = Field(..., description="The interviewer's message")
    done: bool = Field(False, description="Whether the interview is complete")
    feedback: InterviewFeedback | None = Field(None, description="Final feedback (only when done=true)")
