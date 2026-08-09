"""Pydantic models for rubric scores, answer evaluation, and evidence (v3 spec)."""

from __future__ import annotations

from enum import Enum
from statistics import mean

from pydantic import BaseModel, Field


class AnswerStrength(str, Enum):
    """Classification of an answer's quality based on dimension scores."""

    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"


class DimensionScores(BaseModel):
    """The 7 rubric dimensions evaluated on a 1-5 scale."""

    correctness: int = Field(..., ge=1, le=5, description="Technical accuracy of facts and concepts")
    completeness: int = Field(..., ge=1, le=5, description="Thoroughness in addressing all parts of the question")
    depth: int = Field(..., ge=1, le=5, description="Level of technical nuance beyond superficial overview")
    reasoning: int = Field(..., ge=1, le=5, description="Quality of explanation for 'why' choices/tradeoffs were made")
    terminology: int = Field(..., ge=1, le=5, description="Accurate and natural use of domain terms")
    communication: int = Field(..., ge=1, le=5, description="Clarity, structure, and coherence of response")
    confidence: int = Field(..., ge=1, le=5, description="Appropriate certainty without overconfidence")

    @property
    def core_mean(self) -> float:
        """Mean score across the 4 core technical dimensions."""
        return mean([self.correctness, self.completeness, self.depth, self.reasoning])

    def classify_strength(self) -> AnswerStrength:
        """Classify answer strength deterministically based on core dimensions.

        Classification rules:
        - STRONG: core_mean >= 3.5 AND correctness >= 3
        - PARTIAL: core_mean >= 2.0 AND correctness >= 2
        - WEAK: otherwise
        """
        avg = self.core_mean
        if avg >= 3.5 and self.correctness >= 3:
            return AnswerStrength.STRONG
        elif avg >= 2.0 and self.correctness >= 2:
            return AnswerStrength.PARTIAL
        else:
            return AnswerStrength.WEAK


class Evidence(BaseModel):
    """A verified evidence entry supporting a strength or gap claim (v3 spec)."""

    evidence_id: str = Field(..., description="Deterministic ID, e.g. EVID-001")
    question_index: int = Field(..., ge=0, description="0-indexed question number")
    day: int = Field(..., ge=1, le=31, description="Curriculum day number")
    module: int = Field(..., ge=1, le=8, description="Curriculum module number")
    topic: str = Field(..., description="Topic name")
    claim: str = Field(..., description="What this evidence supports")
    candidate_quote: str = Field("", description="Exact substring of candidate's answer, OR empty if unverified")
    evaluation_strength: AnswerStrength = Field(...)
    is_verified: bool = Field(..., description="True = quote is exact substring; False = quote discarded")


class AnswerEvaluation(BaseModel):
    """Complete evaluation result for a single candidate answer."""

    scores: DimensionScores
    strength: AnswerStrength
    key_concepts_demonstrated: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    evidence_quote: str = Field("", description="Raw candidate quote extracted by LLM prior to verification")
    gap_summary: str = Field("", description="Summary of gaps or missing elements")
    suggested_followup_focus: str = Field("", description="Signal suggesting focus for follow-up probe if needed")
    question_index: int = Field(..., ge=0)

