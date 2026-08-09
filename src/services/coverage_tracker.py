"""Coverage Tracker — tracks curriculum coverage and enforces completion quality gate (v3 spec).

Purely deterministic — no LLM calls. Enforces meaningful coverage rules:
- "I don't know" alone does NOT meaningfully cover a day.
- A weak but substantive answer DOES meaningfully cover a day.
"""

from __future__ import annotations

from src.models.evaluation import AnswerEvaluation
from src.models.interview import GeneratedQuestion, InterviewState
from src.config import settings


class CoverageTracker:
    """Tracks curriculum coverage and enforces quality gate constraints."""

    NON_SUBSTANTIVE_ANSWERS = {
        "i don't know",
        "idk",
        "no idea",
        "pass",
        "skip",
        "dont know",
        "don't know",
        "not sure",
        "no clue",
        "",
    }

    @classmethod
    def is_substantive_answer(cls, answer: str) -> bool:
        """Check if an answer text is substantive (not just 'I don't know')."""
        cleaned = answer.strip().lower()
        if not cleaned or cleaned in cls.NON_SUBSTANTIVE_ANSWERS:
            return False
        # If the answer is extremely short and contains IDK phrases, it's non-substantive
        if len(cleaned.split()) <= 4 and any(phrase in cleaned for phrase in ["dont know", "don't know", "no idea", "idk"]):
            return False
        return True

    @classmethod
    def is_meaningfully_covered(
        cls,
        question: GeneratedQuestion | None,
        answer: str,
        evaluation: AnswerEvaluation,
    ) -> bool:
        """Determine if a turn meaningfully covers its curriculum day (v3 spec).

        Conditions for meaningful coverage:
        1. Question targeted a curriculum day (question is not None)
        2. Candidate provided a substantive answer (not 'I don't know' / skip)
        3. Answer was evaluated
        4. Evaluation contains demonstrated concepts OR specific evaluated gaps

        'I don't know' alone returns False.
        A weak but substantive answer returns True.
        """
        if question is None:
            return False

        if not cls.is_substantive_answer(answer):
            return False

        has_demonstrated = len(evaluation.key_concepts_demonstrated) > 0
        has_specific_gaps = len(evaluation.missing_concepts) > 0

        return has_demonstrated or has_specific_gaps

    def can_complete(self, state: InterviewState) -> bool:
        """Determine whether the interview meets all completion quality gate constraints.

        Quality Gate Requirements (v3 spec):
        - question_count >= min_questions (default 8)
        - meaningfully_covered_days >= min_covered_days (default 4)
        - meaningfully_covered_modules >= min_covered_modules (default 2)
        - EITHER plan_coverage >= 0.7 OR question_count >= max_questions (default 12+)

        Args:
            state: Current interview state.

        Returns:
            True if all constraints are satisfied.
        """
        if state.question_count < settings.min_questions:
            return False

        meaningful_days_count = len(state.meaningfully_covered_days)
        if meaningful_days_count < settings.min_covered_days:
            return False

        # Compute modules derived from meaningfully covered days
        meaningful_modules = {
            state.interview_plan.topics[i].module
            for i, topic in enumerate(state.interview_plan.topics)
            if topic.day in state.meaningfully_covered_days
        }
        # Fallback if planned topics didn't catch all days
        if len(meaningful_modules) < settings.min_covered_modules:
            # Check asked questions directly
            for q in state.asked_questions:
                if q.day in state.meaningfully_covered_days:
                    meaningful_modules.add(q.module)

        if len(meaningful_modules) < settings.min_covered_modules:
            return False

        plan_cov = self.get_plan_coverage(state)
        if plan_cov >= settings.plan_coverage_threshold:
            return True

        if state.question_count >= settings.max_questions:
            return True

        if state.question_count >= settings.target_questions and plan_cov >= 0.5:
            return True

        return False

    @staticmethod
    def get_plan_coverage(state: InterviewState) -> float:
        """Calculate what fraction of planned topics have been meaningfully covered."""
        if not state.interview_plan.topics:
            return 1.0

        planned_days = {t.day for t in state.interview_plan.topics}
        covered = planned_days & state.meaningfully_covered_days
        return len(covered) / len(planned_days)
