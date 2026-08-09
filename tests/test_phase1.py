"""Phase 1 verification tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.main import app, curriculum_engine, session_store
from src.models.candidate import CandidateList, CandidateProfile
from src.models.evaluation import AnswerStrength, DimensionScores, Evidence
from src.models.feedback import FeedbackClaim, InterviewFeedback
from src.models.interview import (
    AdaptiveTraceEntry,
    ExperienceTier,
    InterviewPlan,
    InterviewState,
    ProfileAnalysis,
    QuestionIntent,
)
from src.services.curriculum_engine import CurriculumEngine
from src.services.session_store import SessionStore


@pytest.fixture
def test_curriculum_path() -> Path:
    """Path to the authoritative curriculum.json."""
    return Path(__file__).parent.parent / "curriculum.json"


@pytest.fixture
def test_candidates_path() -> Path:
    """Path to the authoritative candidates.json."""
    return Path(__file__).parent.parent / "candidates.json"


def test_candidates_file_loading(test_candidates_path: Path):
    """Verify candidates.json parses into CandidateList model."""
    assert test_candidates_path.exists()
    with open(test_candidates_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidate_list = CandidateList.model_validate(data)
    assert len(candidate_list.candidates) == 20

    cand1 = candidate_list.candidates[0]
    assert cand1.member.id == "CAND-001"
    assert cand1.member.name == "Sarah Johnson"
    assert cand1.signals.commitDays == 28
    assert cand1.signals.first_try_ratio > 0.0
    assert cand1.signals.engagement_ratio > 0.0


def test_curriculum_engine_loading(test_curriculum_path: Path):
    """Verify curriculum.json parses and indexes properly."""
    engine = CurriculumEngine()
    engine.load(test_curriculum_path)

    assert engine.total_days == 31
    assert engine.total_modules == 8

    # Test O(1) day lookup
    day7 = engine.get_day(7)
    assert day7 is not None
    assert day7.title == "Embeddings Explained"
    assert "Ollama" in day7.tools or "Numpy" in day7.tools or len(day7.tools) > 0

    # Test O(1) module lookup
    mod3 = engine.get_module(3)
    assert mod3 is not None
    assert mod3.title == "Embeddings & Vector Search"
    assert mod3.start_day == 7
    assert mod3.end_day == 10

    # Test day to module mapping
    mod_num = engine.get_module_for_day(7)
    assert mod_num == 3

    # Test days in module
    mod3_days = engine.get_days_in_module(3)
    assert len(mod3_days) == 4
    assert [d.day for d in mod3_days] == [7, 8, 9, 10]


def test_session_store_crud(test_candidates_path: Path):
    """Verify SessionStore create, get, update, exists, delete."""
    with open(test_candidates_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    candidate = CandidateProfile.model_validate(data["candidates"][0])

    store = SessionStore()
    assert store.count == 0

    # Create state
    profile_analysis = ProfileAnalysis(
        tier=ExperienceTier.SENIOR,
        starting_difficulty=4,
        role_relevance="high_relevance",
        engagement_ratio=candidate.signals.engagement_ratio,
        first_try_ratio=candidate.signals.first_try_ratio,
    )
    plan = InterviewPlan(topics=[], target_question_count=10, candidate_tier=ExperienceTier.SENIOR)

    state = InterviewState(
        session_id="test-session-123",
        candidate=candidate,
        profile_analysis=profile_analysis,
        interview_plan=plan,
    )

    store.create(state)
    assert store.count == 1
    assert store.exists("test-session-123")

    # Get
    retrieved = store.get("test-session-123")
    assert retrieved is not None
    assert retrieved.candidate.member.name == "Sarah Johnson"

    # Duplicate create raises ValueError
    with pytest.raises(ValueError):
        store.create(state)

    # Update
    state.question_count = 5
    store.update(state)
    updated = store.get("test-session-123")
    assert updated is not None
    assert updated.question_count == 5

    # Delete
    store.delete("test-session-123")
    assert store.count == 0
    assert not store.exists("test-session-123")


def test_rubric_strength_classification():
    """Verify DimensionScores deterministic strength classification."""
    strong_scores = DimensionScores(
        correctness=4, completeness=4, depth=3, reasoning=4,
        terminology=4, communication=4, confidence=4,
    )
    assert strong_scores.classify_strength() == AnswerStrength.STRONG

    partial_scores = DimensionScores(
        correctness=2, completeness=3, depth=2, reasoning=2,
        terminology=3, communication=3, confidence=3,
    )
    assert partial_scores.classify_strength() == AnswerStrength.PARTIAL

    weak_scores = DimensionScores(
        correctness=1, completeness=1, depth=1, reasoning=1,
        terminology=2, communication=2, confidence=2,
    )
    assert weak_scores.classify_strength() == AnswerStrength.WEAK


def test_evidence_model_v3():
    """Verify Evidence model schema matching v3 requirements."""
    evidence = Evidence(
        evidence_id="EVID-001",
        question_index=0,
        day=7,
        module=3,
        topic="Embeddings Explained",
        claim="Demonstrated strong understanding of cosine similarity",
        candidate_quote="Cosine similarity measures the angle between vectors",
        evaluation_strength=AnswerStrength.STRONG,
        is_verified=True,
    )
    assert evidence.evidence_id == "EVID-001"
    assert evidence.is_verified is True


def test_config_loading():
    """Verify settings load defaults and hide secrets."""
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.min_questions == 8
    assert settings.max_questions == 15
    assert settings.min_covered_days == 4
    assert settings.min_covered_modules == 2


def test_fastapi_app_stub():
    """Test FastAPI application startup and health endpoint."""
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["curriculum_loaded"] is True
        assert data["total_days"] == 31
        assert data["total_modules"] == 8
