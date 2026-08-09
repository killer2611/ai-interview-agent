"""Profile Analyzer — classifies candidates and extracts learning signals (v3 spec).

Takes a CandidateProfile and produces a ProfileAnalysis containing:
- Experience tier (for question framing and communication expectations only)
- Starting difficulty (derived SOLELY from curriculum learning signals)
- Categorized mission days (strong, weak, failed, skipped, struggle)
- Profile metrics (first_try_ratio, engagement_ratio)
"""

from __future__ import annotations

from src.models.candidate import CandidateProfile
from src.models.interview import ExperienceTier, ProfileAnalysis
from src.services.curriculum_engine import CurriculumEngine


class ProfileAnalyzer:
    """Analyzes a candidate's profile to inform interview planning."""

    def __init__(self, curriculum_engine: CurriculumEngine) -> None:
        self._curriculum = curriculum_engine

    def analyze(self, candidate: CandidateProfile) -> ProfileAnalysis:
        """Perform full profile analysis on a candidate.

        Args:
            candidate: Candidate's complete profile from candidates.json.

        Returns:
            ProfileAnalysis containing learning signals, tier, and starting difficulty.
        """
        tier = self._classify_tier(candidate.member.yearsExperience)
        role_relevance = self._assess_role_relevance(candidate.member.jobRole)

        strong_days: list[int] = []
        weak_days: list[int] = []
        failed_days: list[int] = []
        skipped_days: list[int] = []
        struggle_days: list[int] = []

        for mission in candidate.missions:
            if mission.is_first_try:
                strong_days.append(mission.day)
            if mission.status == "failed":
                failed_days.append(mission.day)
                weak_days.append(mission.day)
            elif mission.status == "skipped":
                skipped_days.append(mission.day)
                # Skipped is unassessed/not completed — tracked separately from failed
                if mission.day not in weak_days:
                    weak_days.append(mission.day)
            elif mission.is_struggle:
                struggle_days.append(mission.day)
                if mission.day not in weak_days:
                    weak_days.append(mission.day)

        engagement_ratio = candidate.signals.engagement_ratio
        first_try_ratio = candidate.signals.first_try_ratio

        # Starting difficulty derived SOLELY from learning signals (yearsExperience excluded)
        starting_difficulty = self._compute_starting_difficulty(
            first_try_ratio=first_try_ratio,
            engagement_ratio=engagement_ratio,
        )

        return ProfileAnalysis(
            tier=tier,
            starting_difficulty=starting_difficulty,
            role_relevance=role_relevance,
            strong_days=strong_days,
            weak_days=weak_days,
            failed_days=failed_days,
            skipped_days=skipped_days,
            struggle_days=struggle_days,
            topic_priorities=[],  # Topic priorities are built by TopicScorer/InterviewPlanner
            engagement_ratio=engagement_ratio,
            first_try_ratio=first_try_ratio,
        )

    @staticmethod
    def _classify_tier(years: int) -> ExperienceTier:
        """Classify years of experience into a tier for framing and communication expectations."""
        if years <= 2:
            return ExperienceTier.JUNIOR
        elif years <= 7:
            return ExperienceTier.MID
        elif years <= 14:
            return ExperienceTier.SENIOR
        else:
            return ExperienceTier.EXPERT

    @staticmethod
    def _assess_role_relevance(job_role: str) -> str:
        """Assess candidate's job role relevance to the AI curriculum."""
        role_lower = job_role.lower()
        high_roles = ["ai", "ml", "machine learning", "data scientist", "data engineer", "ai engineer"]
        mod_roles = ["software", "developer", "engineer", "architect", "backend", "frontend", "full-stack", "devops", "it"]

        if any(r in role_lower for r in high_roles):
            return "high_relevance"
        elif any(r in role_lower for r in mod_roles):
            return "moderate_relevance"
        else:
            return "low_relevance"

    @staticmethod
    def _compute_starting_difficulty(first_try_ratio: float, engagement_ratio: float) -> int:
        """Compute starting technical difficulty SOLELY from curriculum learning signals.

        Rule (v3 spec): yearsExperience MUST NOT mathematically influence technical difficulty.

        Table:
        - first_try >= 0.8 AND engagement >= 0.8 -> 4
        - first_try >= 0.5 AND engagement >= 0.5 -> 3
        - first_try >= 0.3 AND engagement >= 0.4 -> 2
        - first_try < 0.3 -> 2
        - first_try < 0.1 -> 1
        """
        if first_try_ratio >= 0.8 and engagement_ratio >= 0.8:
            return 4
        elif first_try_ratio >= 0.5 and engagement_ratio >= 0.5:
            return 3
        elif first_try_ratio < 0.1:
            return 1
        elif first_try_ratio < 0.3:
            return 2
        elif first_try_ratio >= 0.3 and engagement_ratio >= 0.4:
            return 2
        else:
            return 2
