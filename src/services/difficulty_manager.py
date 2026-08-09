"""Difficulty Manager — adjusts interview difficulty based on candidate performance.

Purely deterministic sliding-window difficulty manager (1-5 scale).
"""

from __future__ import annotations

from src.models.evaluation import AnswerEvaluation, AnswerStrength


class DifficultyManager:
    """Manages interview difficulty adjustments dynamically."""

    WINDOW_SIZE = 3
    MIN_DIFFICULTY = 1
    MAX_DIFFICULTY = 5

    def adjust(
        self,
        current_difficulty: int,
        evaluations: list[AnswerEvaluation],
    ) -> int:
        """Adjust difficulty based on the last N evaluations.

        Rules (using last 3 evaluations):
        - 3 strong OR 2 strong + 1 partial -> increase by 1
        - 2+ weak -> decrease by 1
        - Mixed -> maintain (0)

        Args:
            current_difficulty: Current difficulty level (1-5).
            evaluations: Evaluation history.

        Returns:
            Adjusted difficulty level clamped between 1 and 5.
        """
        if not evaluations:
            return current_difficulty

        window = evaluations[-self.WINDOW_SIZE:]
        strengths = [e.strength for e in window]

        strong_count = strengths.count(AnswerStrength.STRONG)
        weak_count = strengths.count(AnswerStrength.WEAK)
        partial_count = strengths.count(AnswerStrength.PARTIAL)

        adjustment = 0
        if len(window) >= 2:
            if strong_count >= 3:
                adjustment = 1
            elif strong_count >= 2 and partial_count >= 1 and weak_count == 0:
                adjustment = 1
            elif weak_count >= 2:
                adjustment = -1

        new_difficulty = current_difficulty + adjustment
        return max(self.MIN_DIFFICULTY, min(self.MAX_DIFFICULTY, new_difficulty))

    @staticmethod
    def get_difficulty_label(difficulty: int) -> str:
        """Convert difficulty level to human-readable label."""
        labels = {
            1: "foundational",
            2: "basic",
            3: "intermediate",
            4: "advanced",
            5: "expert",
        }
        return labels.get(difficulty, "intermediate")
