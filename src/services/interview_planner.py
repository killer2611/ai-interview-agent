"""Interview Planner — deterministic topic scoring and plan generation (v3 spec).

Calculates topic priority scores using the 5-factor scoring formula with
precedence-based gap signals (mutually exclusive, not additive).
"""

from __future__ import annotations

from src.models.candidate import CandidateProfile, MissionRecord
from src.models.interview import (
    ExperienceTier,
    InterviewPlan,
    PlannedTopic,
    ProfileAnalysis,
    QuestionIntent,
    TopicPriority,
)
from src.services.curriculum_engine import CurriculumEngine
from src.config import settings


class TopicScorer:
    """Computes deterministic topic priority scores for curriculum days."""

    @staticmethod
    def compute_gap_signal_weight(mission: MissionRecord | None) -> tuple[int, str]:
        """Compute gap signal weight using PRECEDENCE (first match only, NOT additive).

        Returns:
            Tuple of (weight, reason_description).
        """
        if mission is None:
            return 0, "No mission record"

        if mission.status == "failed":
            return 40, "Failed mission (must probe)"
        elif mission.status == "skipped":
            return 25, "Skipped mission (unassessed, probe foundation)"
        elif mission.is_struggle:  # attempts >= 4
            return 30, f"Passed after {mission.attempts} attempts (verify depth)"
        elif mission.attempts == 3:
            return 15, "Passed after 3 attempts"
        elif mission.attempts == 2:
            return 5, "Passed after 2 attempts"
        else:
            return 0, "Passed on first try"

    @staticmethod
    def compute_coverage_weight(module_num: int, covered_modules_counts: dict[int, int]) -> int:
        """Compute coverage weight to ensure module breadth."""
        count = covered_modules_counts.get(module_num, 0)
        if count == 0:
            return 20
        elif count == 1:
            return 10
        return 0

    @staticmethod
    def compute_role_relevance_weight(role_relevance: str) -> int:
        """Compute role relevance weight."""
        if role_relevance == "high_relevance":
            return 15
        elif role_relevance == "moderate_relevance":
            return 10
        return 5

    @staticmethod
    def compute_progression_weight(module_num: int) -> int:
        """Compute curriculum progression weight favoring core AI modules."""
        if module_num in (3, 4, 6):  # Embeddings, LLM Core, Agents
            return 15
        elif module_num in (2, 5, 7):  # Data, Chatbot, Eval/Security
            return 10
        return 5  # Setup (1), Capstone (8)

    @staticmethod
    def compute_confidence_probe_weight(mission: MissionRecord | None, day_num: int) -> int:
        """Compute confidence probe weight for first-try passes."""
        if mission and mission.is_first_try:
            return 10 if day_num >= 7 else 5
        return 0


class InterviewPlanner:
    """Creates a deterministic, personalized interview plan from profile analysis."""

    def __init__(self, curriculum_engine: CurriculumEngine) -> None:
        self._curriculum = curriculum_engine
        self._scorer = TopicScorer()

    def create_plan(self, candidate: CandidateProfile, profile: ProfileAnalysis) -> InterviewPlan:
        """Generate a personalized interview plan adhering to all v3 constraints.

        Args:
            candidate: Full candidate profile.
            profile: Analyzed candidate profile.

        Returns:
            InterviewPlan with ranked PlannedTopic items.
        """
        mission_by_day: dict[int, MissionRecord] = {m.day: m for m in candidate.missions}

        scored_topics: list[tuple[float, PlannedTopic, TopicPriority]] = []
        module_counts: dict[int, int] = {}

        # First pass: calculate scores for candidate's mission days
        candidate_days = sorted(mission_by_day.keys())
        for day_num in candidate_days:
            mission = mission_by_day[day_num]
            day_entry = self._curriculum.get_day(day_num)
            if day_entry is None:
                continue

            module_num = self._curriculum.get_module_for_day(day_num) or 1

            gap_weight, gap_reason = self._scorer.compute_gap_signal_weight(mission)
            cov_weight = self._scorer.compute_coverage_weight(module_num, module_counts)
            role_weight = self._scorer.compute_role_relevance_weight(profile.role_relevance)
            prog_weight = self._scorer.compute_progression_weight(module_num)
            conf_weight = self._scorer.compute_confidence_probe_weight(mission, day_num)

            total_score = float(gap_weight + cov_weight + role_weight + prog_weight + conf_weight)

            # Determine priority label
            if mission.status == "failed":
                priority_label = "mandatory_probe"
            elif mission.status == "skipped":
                priority_label = "mandatory_probe"
            elif mission.is_struggle:
                priority_label = "struggle_probe"
            elif mission.is_first_try:
                priority_label = "strength_validation"
            else:
                priority_label = "coverage_fill"

            suggested_diff = self._determine_topic_difficulty(mission, profile.starting_difficulty)
            intent = self._select_intent(profile.tier, priority_label, day_entry.type)

            topic_priority = TopicPriority(
                day=day_num,
                title=day_entry.title,
                priority=priority_label,
                reason=gap_reason,
                suggested_difficulty=suggested_diff,
                gap_signal_weight=gap_weight,
                total_score=total_score,
            )

            planned_topic = PlannedTopic(
                day=day_num,
                title=day_entry.title,
                module=module_num,
                objectives=day_entry.objectives,
                tools=day_entry.tools,
                intent=intent,
                initial_difficulty=suggested_diff,
                priority=priority_label,
                topic_score=total_score,
            )

            scored_topics.append((total_score, planned_topic, topic_priority))

        # Sort by total_score descending
        scored_topics.sort(key=lambda item: item[0], reverse=True)

        # Select top topics
        selected_planned: list[PlannedTopic] = []
        selected_priorities: list[TopicPriority] = []
        seen_days: set[int] = set()
        seen_modules: set[int] = set()

        for score, planned, priority in scored_topics:
            if planned.day not in seen_days:
                selected_planned.append(planned)
                selected_priorities.append(priority)
                seen_days.add(planned.day)
                seen_modules.add(planned.module)

        # Ensure minimum 8 topics and minimum module/day coverage
        target_count = max(settings.min_questions, 8)
        if len(selected_planned) < target_count:
            # Fill from remaining curriculum days
            for day_entry in self._curriculum.all_days:
                if len(selected_planned) >= target_count:
                    break
                if day_entry.day in seen_days:
                    continue

                module_num = self._curriculum.get_module_for_day(day_entry.day) or 1
                intent = self._select_intent(profile.tier, "coverage_fill", day_entry.type)

                fill_planned = PlannedTopic(
                    day=day_entry.day,
                    title=day_entry.title,
                    module=module_num,
                    objectives=day_entry.objectives,
                    tools=day_entry.tools,
                    intent=intent,
                    initial_difficulty=profile.starting_difficulty,
                    priority="coverage_fill",
                    topic_score=10.0,
                )
                fill_priority = TopicPriority(
                    day=day_entry.day,
                    title=day_entry.title,
                    priority="coverage_fill",
                    reason="Curriculum coverage fill",
                    suggested_difficulty=profile.starting_difficulty,
                    gap_signal_weight=0,
                    total_score=10.0,
                )
                selected_planned.append(fill_planned)
                selected_priorities.append(fill_priority)
                seen_days.add(day_entry.day)
                seen_modules.add(module_num)

        # Sort final selected topics by day number (curriculum progression)
        selected_planned.sort(key=lambda t: t.day)

        # Update profile analysis with topic priorities
        profile.topic_priorities = selected_priorities

        return InterviewPlan(
            topics=selected_planned,
            target_question_count=max(len(selected_planned), 10),
            candidate_tier=profile.tier,
        )

    @staticmethod
    def _determine_topic_difficulty(mission: MissionRecord | None, base_difficulty: int) -> int:
        """Determine starting topic difficulty based on mission signal."""
        if mission is None:
            return base_difficulty
        if mission.status in ("failed", "skipped"):
            return max(1, base_difficulty - 1)
        elif mission.is_first_try:
            return min(5, base_difficulty + 1)
        return base_difficulty

    @staticmethod
    def _select_intent(tier: ExperienceTier, priority: str, day_type: str) -> QuestionIntent:
        """Select question intent based on tier, priority type, and day type."""
        if priority == "mandatory_probe":
            return QuestionIntent.CONCEPTUAL
        elif priority == "struggle_probe":
            return QuestionIntent.REASONING
        elif priority == "strength_validation":
            if tier in (ExperienceTier.SENIOR, ExperienceTier.EXPERT):
                return QuestionIntent.ARCHITECTURE
            return QuestionIntent.TRADEOFF

        if tier == ExperienceTier.EXPERT:
            return QuestionIntent.PRODUCTION if day_type in ("SHIP_IT", "CAPSTONE") else QuestionIntent.ARCHITECTURE
        elif tier == ExperienceTier.SENIOR:
            return QuestionIntent.TRADEOFF
        elif tier == ExperienceTier.MID:
            return QuestionIntent.IMPLEMENTATION
        else:
            return QuestionIntent.CONCEPTUAL
