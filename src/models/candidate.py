"""Pydantic models mapping candidates.json schema exactly."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MemberInfo(BaseModel):
    """Candidate personal and demographic information."""

    id: str = Field(..., description="Candidate ID (e.g. CAND-001)")
    name: str = Field(..., description="Candidate full name")
    jobRole: str = Field(..., description="Current job role")
    yearsExperience: int = Field(..., ge=0, description="Years of professional experience")
    education: str = Field(..., description="Highest education level")
    status: str = Field(..., description="Status (e.g. COMPLETED)")


class MissionRecord(BaseModel):
    """Record of a single curriculum mission attempted by the candidate."""

    day: int = Field(..., ge=1, le=31, description="Curriculum day number")
    title: str = Field(..., description="Mission title")
    passed: bool | None = Field(None, description="True if mission was passed")
    attempts: int | None = Field(None, ge=1, description="Number of attempts taken")
    skipped: bool | None = Field(None, description="True if mission was skipped")

    @property
    def is_first_try(self) -> bool:
        """True if the mission was passed on the very first attempt."""
        return bool(self.passed and self.attempts == 1)

    @property
    def is_struggle(self) -> bool:
        """True if the mission required 4 or more attempts."""
        return bool(self.passed and self.attempts is not None and self.attempts >= 4)

    @property
    def status(self) -> str:
        """Normalized mission status: passed, failed, skipped, or unknown."""
        if self.skipped:
            return "skipped"
        elif self.passed:
            return "passed"
        elif self.passed is False:
            return "failed"
        return "unknown"


class LearningSignals(BaseModel):
    """Quantitative engagement and performance signals."""

    commitDays: int = Field(..., ge=0, description="Days with active code commits")
    missionsCompleted: int = Field(..., ge=0, description="Total missions completed")
    missionsFirstTry: int = Field(..., ge=0, description="Missions passed on first attempt")

    @property
    def first_try_ratio(self) -> float:
        """Ratio of first-try passes to total completed missions (0.0 to 1.0)."""
        if self.missionsCompleted == 0:
            return 0.0
        return min(1.0, max(0.0, self.missionsFirstTry / self.missionsCompleted))

    @property
    def engagement_ratio(self) -> float:
        """Ratio of commit days to the 31-day curriculum length (0.0 to 1.0)."""
        return min(1.0, max(0.0, self.commitDays / 31.0))


class CandidateProfile(BaseModel):
    """Complete profile of a candidate from candidates.json."""

    member: MemberInfo
    missions: list[MissionRecord] = Field(default_factory=list)
    signals: LearningSignals


class CandidateList(BaseModel):
    """Wrapper for candidates.json top-level object."""

    candidates: list[CandidateProfile]
