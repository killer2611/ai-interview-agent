"""Feedback Generator — generates evidence-grounded final feedback (Call Site 3, v3 spec).

Handles:
- Aggregation of verified strengths and gaps evidence
- Identification of skipped/unassessed curriculum topics
- LLM structured feedback generation with evidence_id traceability
- Deterministic verification and rejection of unsupported claims
- Conversion to public API response contract (technical-spec.md)
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field

from src.config import settings
from src.models.feedback import FeedbackClaim, InterviewFeedback
from src.models.interview import InterviewState
from src.prompts.feedback_generation import build_feedback_prompt
from src.services.curriculum_engine import CurriculumEngine
from src.services.evidence_verifier import EvidenceVerifier
from src.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class _LLMFeedbackClaim(BaseModel):
    """Internal model for structured LLM feedback claim with evidence IDs."""
    claim: str = Field(..., description="The feedback claim text")
    evidence_ids: list[str] = Field(default_factory=list, description="List of verified evidence IDs supporting this claim")


class _LLMFeedbackResponse(BaseModel):
    """Schema expected from Call Site 3 LLM feedback generation."""
    summary: str = Field(..., description="2-4 sentence holistic candidate summary")
    strengths: list[_LLMFeedbackClaim] = Field(default_factory=list)
    gaps: list[_LLMFeedbackClaim] = Field(default_factory=list)
    next: list[str] = Field(default_factory=list)


class FeedbackGenerator:
    """Generates evidence-grounded technical feedback at interview completion."""

    def __init__(self, llm_provider: LLMProvider, curriculum_engine: CurriculumEngine) -> None:
        self._llm = llm_provider
        self._curriculum = curriculum_engine
        self._verifier = EvidenceVerifier()

    async def generate_feedback(self, state: InterviewState) -> InterviewFeedback:
        """Generate final evidence-grounded feedback for a completed interview.

        Args:
            state: Complete interview state containing verified evidence.

        Returns:
            InterviewFeedback matching technical-spec.md public API contract.
        """
        # 1. Identify skipped curriculum topics not covered in interview
        self._populate_unassessed_topics(state)

        # 2. Attempt structured LLM feedback generation (Call Site 3)
        system_prompt, user_prompt = build_feedback_prompt(state)

        try:
            llm_response = self._llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=_LLMFeedbackResponse,
                temperature=settings.llm_temperature_feedback,
                max_tokens=800,
            )

            # Convert to internal claims
            internal_strengths = [
                FeedbackClaim(claim=item.claim, evidence_ids=item.evidence_ids)
                for item in llm_response.strengths
            ]
            internal_gaps = [
                FeedbackClaim(claim=item.claim, evidence_ids=item.evidence_ids)
                for item in llm_response.gaps
            ]

            # 3. Deterministically verify evidence_ids (strip unsupported claims)
            verified_strengths, verified_gaps = self._verify_claim_evidence(
                internal_strengths, internal_gaps, state
            )

            # Ensure unassessed topics are in next recommendations, NOT in gaps
            next_steps = self._ensure_unassessed_in_next(llm_response.next, state)

            return InterviewFeedback(
                summary=llm_response.summary,
                strengths=[c.claim for c in verified_strengths],
                gaps=[c.claim for c in verified_gaps],
                next=next_steps,
            )

        except Exception as e:
            logger.warning("LLM feedback generation failed (%s) — using deterministic fallback", str(e))
            return self._deterministic_fallback_feedback(state)

    def _populate_unassessed_topics(self, state: InterviewState) -> None:
        """Identify skipped missions that were never probed in the interview."""
        unassessed = []
        for mission in state.candidate.missions:
            if mission.status == "skipped" and mission.day not in state.covered_days:
                day_entry = self._curriculum.get_day(mission.day)
                title = day_entry.title if day_entry else f"Day {mission.day}"
                unassessed.append(f"Day {mission.day}: {title}")

        state.unassessed_topics = unassessed

    @staticmethod
    def _verify_claim_evidence(
        strengths: list[FeedbackClaim],
        gaps: list[FeedbackClaim],
        state: InterviewState,
    ) -> tuple[list[FeedbackClaim], list[FeedbackClaim]]:
        """Verify that every feedback claim references at least one verified evidence ID.

        Any claim with zero verified evidence IDs is removed (unsupported claim rejection).
        """
        valid_strength_ids = {e.evidence_id for e in state.strengths_evidence if e.is_verified}
        valid_gap_ids = {e.evidence_id for e in state.weaknesses_evidence if e.is_verified}

        verified_strengths = [
            c for c in strengths
            if any(eid in valid_strength_ids for eid in c.evidence_ids)
        ]
        verified_gaps = [
            c for c in gaps
            if any(eid in valid_gap_ids for eid in c.evidence_ids)
        ]

        # If LLM didn't attach evidence_ids properly, fallback to using all verified claims
        if not verified_strengths and state.strengths_evidence:
            verified_strengths = [
                FeedbackClaim(claim=e.claim, evidence_ids=[e.evidence_id])
                for e in state.strengths_evidence if e.is_verified
            ]
        if not verified_gaps and state.weaknesses_evidence:
            verified_gaps = [
                FeedbackClaim(claim=e.claim, evidence_ids=[e.evidence_id])
                for e in state.weaknesses_evidence if e.is_verified
            ]

        return verified_strengths, verified_gaps

    @staticmethod
    def _ensure_unassessed_in_next(next_steps: list[str], state: InterviewState) -> list[str]:
        """Ensure unassessed topics are recommended in next steps, not gaps."""
        result = list(next_steps)
        for topic in state.unassessed_topics:
            rec = f"Review unassessed topic ({topic})"
            if not any(topic in r for r in result):
                result.append(rec)
        return result[:5]

    def _deterministic_fallback_feedback(self, state: InterviewState) -> InterviewFeedback:
        """Deterministic fallback feedback generator when LLM provider fails."""
        name = state.candidate.member.name
        meaningful_count = len(state.meaningfully_covered_days)
        module_count = len(state.covered_modules)

        summary = (
            f"{name} completed a {state.question_count}-question technical interview covering "
            f"{meaningful_count} curriculum days across {module_count} modules. "
            f"Demonstrated solid baseline understanding with specific technical areas identified for growth."
        )

        strengths = [e.claim for e in state.strengths_evidence if e.is_verified]
        if not strengths:
            strengths = ["Engaged with technical interview questions across multiple curriculum modules."]

        gaps = [e.claim for e in state.weaknesses_evidence if e.is_verified]

        next_steps = []
        if gaps:
            next_steps.append(f"Focus on strengthening technical areas identified during interview.")
        for topic in state.unassessed_topics[:2]:
            next_steps.append(f"Complete unassessed curriculum area: {topic}")
        if not next_steps:
            next_steps = ["Continue building hands-on projects to deepen architecture experience."]

        return InterviewFeedback(
            summary=summary,
            strengths=strengths,
            gaps=gaps,
            next=next_steps,
        )
