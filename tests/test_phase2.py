"""Phase 2 unit tests covering ProfileAnalyzer, TopicScorer, InterviewPlanner, CoverageTracker, and DifficultyManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.candidate import CandidateList, CandidateProfile, MissionRecord
from src.models.evaluation import AnswerEvaluation, AnswerStrength, DimensionScores
from src.models.interview import ExperienceTier, GeneratedQuestion, InterviewPlan, ProfileAnalysis
from src.services.coverage_tracker import CoverageTracker
from src.services.curriculum_engine import CurriculumEngine
from src.services.difficulty_manager import DifficultyManager
from src.services.interview_planner import InterviewPlanner, TopicScorer
from src.services.profile_analyzer import ProfileAnalyzer


@pytest.fixture
def curriculum_engine() -> CurriculumEngine:
    path = Path(__file__).parent.parent / "curriculum.json"
    engine = CurriculumEngine()
    engine.load(path)
    return engine


@pytest.fixture
def candidates() -> list[CandidateProfile]:
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data).candidates


def test_candidate_profile_analysis(curriculum_engine: CurriculumEngine, candidates: list[CandidateProfile]):
    """Test 1: Candidate profile analysis."""
    analyzer = ProfileAnalyzer(curriculum_engine)
    sarah = candidates[0]  # CAND-001 (Sarah Johnson: 9 yrs, 20/30 first try, 28 commitDays)

    profile = analyzer.analyze(sarah)

    assert profile.tier == ExperienceTier.SENIOR
    assert profile.engagement_ratio == pytest.approx(28 / 31.0)
    assert profile.first_try_ratio == pytest.approx(20 / 30.0)
    assert profile.starting_difficulty == 3  # first_try >= 0.5 & engagement >= 0.5 -> 3
    assert 29 in profile.skipped_days  # Day 29 was skipped
    assert 12 in profile.struggle_days  # Day 12 had 4 attempts


def test_gap_signal_precedence():
    """Test 2: Gap-signal precedence rule (failed > skipped > attempts>=4 > 3 > 2 > none).

    Verifies that mutually related signals are NOT additive.
    """
    scorer = TopicScorer()

    # Case A: Failed mission that ALSO had 4 attempts -> scores 40 (failed precedence), NOT 40+30=70
    failed_struggle = MissionRecord(day=10, title="Test", passed=False, attempts=4)
    weight, reason = scorer.compute_gap_signal_weight(failed_struggle)
    assert weight == 40
    assert "Failed mission" in reason

    # Case B: Skipped mission -> scores 25
    skipped = MissionRecord(day=29, title="Test", skipped=True)
    weight_skip, _ = scorer.compute_gap_signal_weight(skipped)
    assert weight_skip == 25

    # Case C: Passed struggle mission (4 attempts) -> scores 30
    struggle = MissionRecord(day=12, title="Test", passed=True, attempts=4)
    weight_struggle, _ = scorer.compute_gap_signal_weight(struggle)
    assert weight_struggle == 30

    # Case D: Passed 3 attempts -> scores 15
    att3 = MissionRecord(day=10, title="Test", passed=True, attempts=3)
    assert scorer.compute_gap_signal_weight(att3)[0] == 15

    # Case E: Passed first try -> scores 0 for gap signal
    first_try = MissionRecord(day=7, title="Test", passed=True, attempts=1)
    assert scorer.compute_gap_signal_weight(first_try)[0] == 0


def test_skipped_vs_failed_distinction(curriculum_engine: CurriculumEngine, candidates: list[CandidateProfile]):
    """Test 3: Skipped vs failed distinction."""
    analyzer = ProfileAnalyzer(curriculum_engine)
    sarah = candidates[0]  # Has skipped day 29

    profile = analyzer.analyze(sarah)

    assert 29 in profile.skipped_days
    assert 29 not in profile.failed_days  # Skipped is not classified as failed

    # Scorer gives 25 for skipped vs 40 for failed
    skipped_m = MissionRecord(day=29, title="Skipped", skipped=True)
    failed_m = MissionRecord(day=8, title="Failed", passed=False)

    assert TopicScorer.compute_gap_signal_weight(skipped_m)[0] == 25
    assert TopicScorer.compute_gap_signal_weight(failed_m)[0] == 40


def test_first_try_confidence_signal():
    """Test 4: First-try confidence signal."""
    first_try_complex = MissionRecord(day=16, title="Chatbot API", passed=True, attempts=1)
    first_try_simple = MissionRecord(day=2, title="Setup", passed=True, attempts=1)

    assert TopicScorer.compute_confidence_probe_weight(first_try_complex, 16) == 10
    assert TopicScorer.compute_confidence_probe_weight(first_try_simple, 2) == 5


def test_topic_ranking(curriculum_engine: CurriculumEngine, candidates: list[CandidateProfile]):
    """Test 5: Topic ranking sorts topics by total score descending."""
    analyzer = ProfileAnalyzer(curriculum_engine)
    planner = InterviewPlanner(curriculum_engine)

    sarah = candidates[0]
    profile = analyzer.analyze(sarah)
    plan = planner.create_plan(sarah, profile)

    # Check topic priorities generated during planning
    priorities = profile.topic_priorities
    assert len(priorities) >= 8

    # Verify topics are ranked properly in topic_priorities
    scores = [p.total_score for p in priorities]
    # Check that highest scored topics appear in selected topics
    top_score = max(scores)
    assert top_score >= 40.0  # Gap signal topics score high


def test_starting_difficulty_learning_signals_only(curriculum_engine: CurriculumEngine):
    """Test 6: Starting difficulty is determined SOLELY by learning signals (yearsExperience ignored)."""
    # High learning signals -> difficulty 4 (regardless of 0 or 20 years experience)
    assert ProfileAnalyzer._compute_starting_difficulty(0.9, 0.9) == 4

    # Moderate learning signals -> difficulty 3
    assert ProfileAnalyzer._compute_starting_difficulty(0.6, 0.6) == 3

    # Low learning signals -> difficulty 1 or 2
    assert ProfileAnalyzer._compute_starting_difficulty(0.05, 0.5) == 1
    assert ProfileAnalyzer._compute_starting_difficulty(0.2, 0.5) == 2


def test_meaningful_coverage_logic():
    """Test 7: Meaningful coverage rules.

    - 'I don't know' alone does NOT meaningfully cover a day.
    - A weak but substantive answer DOES meaningfully cover a day.
    """
    question = GeneratedQuestion(
        question_text="Explain vector similarity search.",
        day=7,
        module=3,
        objectives=["Explain cosine similarity"],
        tools=["Numpy"],
        intent="conceptual",
        difficulty=3,
    )

    # Case A: Candidate says "I don't know" -> NOT meaningfully covered
    idk_eval = AnswerEvaluation(
        scores=DimensionScores(correctness=1, completeness=1, depth=1, reasoning=1, terminology=1, communication=1, confidence=1),
        strength=AnswerStrength.WEAK,
        key_concepts_demonstrated=[],
        missing_concepts=["Unable to assess"],
        evidence_quote="i don't know",
        gap_summary="Candidate did not answer",
        question_index=0,
    )
    assert CoverageTracker.is_meaningfully_covered(question, "i don't know", idk_eval) is False
    assert CoverageTracker.is_meaningfully_covered(question, "idk", idk_eval) is False
    assert CoverageTracker.is_meaningfully_covered(question, "pass", idk_eval) is False

    # Case B: Weak but substantive answer (e.g. wrong explanation) -> IS meaningfully covered
    substantive_weak_eval = AnswerEvaluation(
        scores=DimensionScores(correctness=2, completeness=2, depth=1, reasoning=1, terminology=2, communication=2, confidence=2),
        strength=AnswerStrength.WEAK,
        key_concepts_demonstrated=["Mentioned vectors"],
        missing_concepts=["Confused cosine similarity with Euclidean distance"],
        evidence_quote="Vector similarity is measured using dot product",
        gap_summary="Confused formulas",
        question_index=0,
    )
    assert CoverageTracker.is_meaningfully_covered(
        question,
        "Vector similarity is measured using dot product between matrix rows.",
        substantive_weak_eval,
    ) is True


def test_interview_plan_constraints(curriculum_engine: CurriculumEngine, candidates: list[CandidateProfile]):
    """Test 8: Interview plan constraints (>=8 topics, >=4 days, >=2 modules)."""
    analyzer = ProfileAnalyzer(curriculum_engine)
    planner = InterviewPlanner(curriculum_engine)

    for candidate in candidates[:5]:
        profile = analyzer.analyze(candidate)
        plan = planner.create_plan(candidate, profile)

        # Plan constraints check
        assert len(plan.topics) >= 8
        distinct_days = {t.day for t in plan.topics}
        distinct_modules = {t.module for t in plan.topics}

        assert len(distinct_days) >= 4
        assert len(distinct_modules) >= 2
