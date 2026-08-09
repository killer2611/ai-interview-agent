"""Follow-up Engine — deterministic recommendations for follow-up vs next topic (v3 spec).

Does NOT make final state transitions — returns recommendations to InterviewController.
"""

from __future__ import annotations

import logging

from src.models.evaluation import AnswerEvaluation, AnswerStrength
from src.models.interview import FollowUpAction, FollowUpDecision, InterviewState
from src.config import settings

logger = logging.getLogger(__name__)


class FollowUpEngine:
    """Decides whether to recommend a follow-up question or transition to next topic."""

    def decide(
        self,
        evaluation: AnswerEvaluation,
        state: InterviewState,
    ) -> FollowUpDecision:
        """Make a deterministic follow-up recommendation based on answer strength and state.

        Args:
            evaluation: Candidate's latest answer evaluation.
            state: Current interview state.

        Returns:
            FollowUpDecision with recommended action, rationale, context, and difficulty adjustment.
        """
        strength = evaluation.strength
        followup_count = state.current_topic_followup_count
        max_followups = settings.max_followups_per_topic

        # Approaching maximum questions safety limit -> prioritize module/day coverage fill
        uncovered_topics = [t for t in state.interview_plan.topics if t.day not in state.covered_days]
        approaching_cap = state.question_count >= settings.max_questions - 2

        if approaching_cap and uncovered_topics:
            return self._recommend_next_topic(state, "Approaching question limit — prioritizing curriculum coverage fill")

        # --- STRONG answer ---
        if strength == AnswerStrength.STRONG:
            if followup_count < max_followups:
                concepts = ", ".join(evaluation.key_concepts_demonstrated[:2]) if evaluation.key_concepts_demonstrated else "core concepts"
                return FollowUpDecision(
                    action=FollowUpAction.FOLLOW_UP,
                    rationale=f"Strong answer on {concepts} — probing deeper on tradeoffs/architecture",
                    followup_context=f"Advanced tradeoffs and system architecture regarding {concepts}",
                    adjust_difficulty=1,
                )
            else:
                return self._recommend_next_topic(state, "Strong answer — topic well covered, advancing to next topic")

        # --- PARTIAL answer ---
        if strength == AnswerStrength.PARTIAL:
            if followup_count < max_followups:
                missing = ", ".join(evaluation.missing_concepts[:2]) if evaluation.missing_concepts else "core trade-offs"
                return FollowUpDecision(
                    action=FollowUpAction.FOLLOW_UP,
                    rationale=f"Partial answer — probing missing concept: {missing}",
                    followup_context=missing,
                    adjust_difficulty=0,
                )
            else:
                return self._recommend_next_topic(state, "Partial answer — max follow-ups reached, advancing to next topic")

        # --- WEAK answer ---
        if strength == AnswerStrength.WEAK:
            if followup_count < 1:
                return FollowUpDecision(
                    action=FollowUpAction.FOLLOW_UP,
                    rationale="Weak answer — scaffolding/simplifying question on same concept",
                    followup_context="Prerequisite foundational concepts and basic definitions",
                    adjust_difficulty=-1,
                )
            else:
                return self._recommend_next_topic(state, "Weak answer — confirmed gap, advancing to next topic")

        return self._recommend_next_topic(state, "Default — advancing to next topic")

    def _recommend_next_topic(self, state: InterviewState, rationale: str) -> FollowUpDecision:
        """Find next planned topic index and return NEXT_TOPIC decision."""
        next_index = self.get_next_uncovered_plan_index(state)
        if next_index is None:
            next_index = min(state.current_plan_index + 1, len(state.interview_plan.topics) - 1)

        return FollowUpDecision(
            action=FollowUpAction.NEXT_TOPIC,
            rationale=rationale,
            followup_context="",
            adjust_difficulty=0,
            target_plan_index=next_index,
        )

    @staticmethod
    def get_next_uncovered_plan_index(state: InterviewState) -> int | None:
        """Find index of next planned topic whose day has not been touched yet."""
        for i, topic in enumerate(state.interview_plan.topics):
            if i <= state.current_plan_index:
                continue
            if topic.day not in state.covered_days:
                return i
        return None
