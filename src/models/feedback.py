"""Pydantic models for interview feedback structures matching technical-spec.md and internal evidence-traced claims."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeedbackClaim(BaseModel):
    """Internal model for a feedback claim linked to verified evidence IDs (v3 spec)."""

    claim: str = Field(..., description="The feedback claim text")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of verified evidence backing this claim")


class InterviewFeedback(BaseModel):
    """Feedback structure per technical-spec.md.

    This matches the public API contract:
    - summary: string
    - strengths: string[]
    - gaps: string[]
    - next: string[]
    """

    summary: str = Field(..., description="2-4 sentence holistic assessment of the candidate")
    strengths: list[str] = Field(default_factory=list, description="Demonstrated strength claims")
    gaps: list[str] = Field(default_factory=list, description="Demonstrated gap/weakness claims")
    next: list[str] = Field(default_factory=list, description="Actionable next step recommendations")
