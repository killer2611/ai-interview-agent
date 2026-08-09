"""Regression tests for question generation quality and internal instruction leakage prevention."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.main import curriculum_engine, llm_provider
from src.models.candidate import CandidateList, CandidateProfile
from src.models.interview import AskedQuestion, GeneratedQuestion, PlannedTopic, QuestionIntent
from src.services.interview_controller import InterviewController
from src.services.question_generator import QuestionGenerator, QuestionValidator, _LLMQuestionResponse


@pytest.fixture
def test_candidate() -> CandidateProfile:
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data).candidates[0]


def test_internal_instruction_leakage_rejected():
    """Test 1: Internal instruction leakage is flagged and rejected by QuestionValidator."""
    validator = QuestionValidator()

    bad_questions = [
        "Building on your response about Embeddings Explained: How would you design the system architecture? Specially regarding: Simplify the question. Test foundational prerequisite understanding.",
        "How do vector databases work? Specially regarding: Probe the specific missing aspect: missing details.",
        "Regarding Embeddings: Test foundational prerequisite understanding of tokenization?",
        "How would you implement SQLite? Internal instruction: probe error handling.",
    ]

    for bad_q in bad_questions:
        is_valid, _, reason = validator.validate_question(
            bad_q,
            topic_title="Embeddings Explained",
            tools=["Numpy"],
            objectives=["Understand tokenization"],
            asked_questions=[],
        )
        assert is_valid is False
        assert "Internal instruction leakage detected" in reason


def test_repeated_question_rejected():
    """Test 2: Repeated question is rejected by deduplication check."""
    validator = QuestionValidator()
    asked = AskedQuestion(
        question_text="How do dense vector embeddings handle token length limits?",
        day=7,
        module=3,
        objectives=[],
        intent=QuestionIntent.CONCEPTUAL,
        difficulty=3,
    )

    duplicate_q = "How do dense vector embeddings handle token length limits?"
    is_valid, _, reason = validator.validate_question(
        duplicate_q,
        topic_title="Embeddings Explained",
        tools=["Numpy"],
        objectives=["Understand tokenization"],
        asked_questions=[asked],
    )
    assert is_valid is False
    assert "Duplicate question text" in reason


def test_clean_followup_accepted():
    """Test 3: Clean candidate-facing follow-up question is accepted."""
    validator = QuestionValidator()
    clean_followup = "When generating dense embeddings for vector search, how does tokenization handle out-of-vocabulary terms?"


    is_valid, text, reason = validator.validate_question(
        clean_followup,
        topic_title="Embeddings Explained",
        tools=["Numpy"],
        objectives=["Understand tokenization"],
        asked_questions=[],
    )
    assert is_valid is True
    assert reason == ""
    assert text == clean_followup


def test_fallback_contains_only_candidate_facing_text():
    """Test 4: Fallback question contains only clean candidate-facing text with zero internal markers."""
    mock_llm = MagicMock()
    qgen = QuestionGenerator(mock_llm, curriculum_engine)
    day7 = curriculum_engine.get_day(7)

    # Test new topic fallback
    fallback_new = qgen._get_template_fallback(day7, "conceptual", "Embeddings & Vector Search", is_followup=False)
    assert "Specially regarding" not in fallback_new
    assert "Simplify the question" not in fallback_new
    assert "missing details" not in fallback_new
    assert fallback_new.startswith("Regarding Embeddings Explained")

    # Test follow-up fallback
    fallback_followup = qgen._get_template_fallback(day7, "conceptual", "Embeddings & Vector Search", is_followup=True)
    assert "Specially regarding" not in fallback_followup
    assert "Simplify the question" not in fallback_followup
    assert "missing details" not in fallback_followup
    assert fallback_followup == "Building on your response about Embeddings Explained, how do you handle technical trade-offs and edge cases in practice?"


@pytest.mark.asyncio
async def test_end_to_end_question_generator_leakage_prevention(test_candidate: CandidateProfile):
    """Test 5: End-to-end QuestionGenerator rejects leaked LLM output and uses clean fallback."""
    mock_llm = MagicMock()
    # LLM returns bad output with leaked internal instructions
    mock_llm.generate_structured.return_value = _LLMQuestionResponse(
        question_text="How do vector embeddings work? Specially regarding: Simplify the question."
    )

    qgen = QuestionGenerator(mock_llm, curriculum_engine)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-leak-guard", test_candidate)
    topic = PlannedTopic(
        day=7,
        title="Embeddings Explained",
        module=3,
        objectives=["Understand tokenization"],
        tools=["Numpy"],
        intent=QuestionIntent.CONCEPTUAL,
        initial_difficulty=3,
    )

    q = await qgen.generate_question(state, topic, 3, is_followup=True, followup_context="Prerequisite foundational concepts")

    # Verify leaked text was rejected and clean fallback was used
    assert "Specially regarding" not in q.question_text
    assert "Simplify the question" not in q.question_text
    assert q.question_text == "Building on your response about Embeddings Explained, how do you handle technical trade-offs and edge cases in practice?"
