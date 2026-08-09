"""Phase 4 unit tests covering real/structured LLM question generation, structured answer evaluation, evidence verification, and post-generation validation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.main import curriculum_engine, llm_provider
from src.models.candidate import CandidateList, CandidateProfile
from src.models.evaluation import AnswerEvaluation, AnswerStrength, DimensionScores
from src.models.interview import AskedQuestion, GeneratedQuestion, InterviewState, PlannedTopic, QuestionIntent
from src.services.answer_evaluator import AnswerEvaluator, _LLMEvaluationResponse

from src.services.evidence_verifier import EvidenceVerifier
from src.services.interview_controller import InterviewController
from src.services.profile_analyzer import ProfileAnalyzer
from src.services.question_generator import QuestionGenerator, QuestionValidator, _LLMQuestionResponse


@pytest.fixture
def test_candidate() -> CandidateProfile:
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data).candidates[0]


@pytest.fixture
def controller() -> InterviewController:
    return InterviewController(curriculum_engine, llm_provider)


@pytest.mark.asyncio
async def test_valid_structured_question_generation(test_candidate: CandidateProfile):
    """Test 1: Valid structured question generation using mock LLM provider returning _LLMQuestionResponse."""
    mock_llm = MagicMock()
    # First call during init, second call during generate_question (different questions)
    mock_llm.generate_structured.side_effect = [
        _LLMQuestionResponse(question_text="Initial welcome question on embeddings and vector representations?"),
        _LLMQuestionResponse(question_text="When building dense vector representations with embeddings, how do you handle out-of-vocabulary tokens?"),
    ]

    qgen = QuestionGenerator(mock_llm, curriculum_engine)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p4-qgen", test_candidate)

    topic = PlannedTopic(
        day=7,
        title="Embeddings Explained",
        module=3,
        objectives=["Explain vector embeddings", "Understand tokenization"],
        tools=["Numpy", "Ollama"],
        intent=QuestionIntent.CONCEPTUAL,
        initial_difficulty=3,
    )

    q = await qgen.generate_question(state, topic, 3, is_followup=False)
    assert q.question_text == "When building dense vector representations with embeddings, how do you handle out-of-vocabulary tokens?"
    assert q.day == 7
    assert q.module == 3



@pytest.mark.asyncio
async def test_invalid_llm_output_retry_fallback(test_candidate: CandidateProfile):
    """Test 2: Invalid LLM output or exception triggers deterministic template fallback."""
    mock_llm = MagicMock()
    mock_llm.generate_structured.side_effect = Exception("API rate limit exceeded")

    qgen = QuestionGenerator(mock_llm, curriculum_engine)
    prof = ProfileAnalyzer(curriculum_engine).analyze(test_candidate)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p4-fallback", test_candidate)

    topic = PlannedTopic(
        day=8,
        title="Vector Databases Overview",
        module=3,
        objectives=["Compare vector databases"],
        tools=["Pinecone", "Milvus"],
        intent=QuestionIntent.ARCHITECTURE,
        initial_difficulty=3,
    )

    q = await qgen.generate_question(state, topic, 3, is_followup=False)
    assert "Vector Databases" in q.question_text
    assert q.day == 8


def test_question_topic_validation():
    """Test 3: Question topic validation (5 checks)."""
    validator = QuestionValidator()

    # Case A: Valid question containing topic keyword 'embeddings' and objective word 'tokenization'
    valid_q = "How does tokenization affect vector embeddings in search applications?"
    is_valid, text, reason = validator.validate_question(
        valid_q,
        topic_title="Embeddings Explained",
        tools=["Numpy"],
        objectives=["Understand tokenization concepts"],
        asked_questions=[],
    )
    assert is_valid is True
    assert reason == ""

    # Case B: Off-topic question missing keywords
    off_topic_q = "What is your favorite food to eat during lunch break?"
    is_valid_b, _, reason_b = validator.validate_question(
        off_topic_q,
        topic_title="Embeddings Explained",
        tools=["Numpy"],
        objectives=["Understand tokenization concepts"],
        asked_questions=[],
    )
    assert is_valid_b is False
    assert "Missing topic keywords" in reason_b


def test_duplicate_question_prevention():
    """Test 4: Duplicate-question prevention flags asked questions."""
    validator = QuestionValidator()

    asked_q = AskedQuestion(
        question_text="How does cosine similarity differ from Euclidean distance?",
        day=7,
        module=3,
        objectives=[],
        intent=QuestionIntent.TRADEOFF,
        difficulty=3,
    )

    duplicate_q = "How does cosine similarity differ from Euclidean distance?"
    is_valid, _, reason = validator.validate_question(
        duplicate_q,
        topic_title="Embeddings Explained",
        tools=["Numpy"],
        objectives=["cosine similarity"],
        asked_questions=[asked_q],
    )
    assert is_valid is False
    assert "Duplicate question text" in reason


@pytest.mark.asyncio
async def test_followup_targeting_missing_concept(test_candidate: CandidateProfile):
    """Test 5: Follow-up question generation targeting a missing concept."""
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = _LLMQuestionResponse(
        question_text="Building on vector indexing, how does HNSW graph construction maintain low retrieval latency?"
    )

    qgen = QuestionGenerator(mock_llm, curriculum_engine)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p4-followup", test_candidate)

    topic = PlannedTopic(
        day=8,
        title="Vector Databases Overview",
        module=3,
        objectives=["Indexing graph structures"],
        tools=["Milvus"],
        intent=QuestionIntent.REASONING,
        initial_difficulty=3,
    )

    q = await qgen.generate_question(
        state=state,
        topic=topic,
        difficulty=3,
        is_followup=True,
        followup_context="Candidate missed HNSW graph index construction details",
    )
    assert q.is_followup is True
    assert "HNSW" in q.question_text or "Vector Databases" in q.question_text


@pytest.mark.asyncio
async def test_structured_answer_evaluation(test_candidate: CandidateProfile):
    """Test 6 & 10: Structured answer evaluation returning dimension scores, concepts, misconceptions, and evidence."""
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = _LLMEvaluationResponse(
        correctness=4,
        completeness=4,
        depth=3,
        reasoning=4,
        terminology=4,
        communication=4,
        confidence=4,
        key_concepts_demonstrated=["Vector search", "Cosine similarity"],
        missing_concepts=["Dot product vs cosine scaling"],
        misconceptions=["Assumed Euclidean distance is always scale invariant"],
        evidence_quote="Cosine similarity measures vector angles",
        gap_summary="Slight confusion on scale invariance",
        suggested_followup_focus="Probe scale invariance in dot product search",
    )

    evaluator = AnswerEvaluator(mock_llm, curriculum_engine)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p4-eval", test_candidate)

    q = GeneratedQuestion(
        question_text="How do vector distance metrics differ in retrieval?",
        day=7,
        module=3,
        objectives=["Compare metrics"],
        intent=QuestionIntent.TRADEOFF,
        difficulty=3,
    )

    candidate_answer = "Cosine similarity measures vector angles in high-dimensional space for dense retrieval."
    eval_res = await evaluator.evaluate(q, candidate_answer, state)

    assert eval_res.scores.correctness == 4
    assert eval_res.strength == AnswerStrength.STRONG
    assert "Vector search" in eval_res.key_concepts_demonstrated
    assert "Dot product vs cosine scaling" in eval_res.missing_concepts
    assert "Assumed Euclidean distance" in eval_res.misconceptions[0]
    assert eval_res.suggested_followup_focus == "Probe scale invariance in dot product search"


def test_exact_evidence_span_verification(test_candidate: CandidateProfile):
    """Test 7: Exact evidence-span verification retains exact substring quote and marks is_verified=True."""
    actual_answer = "Cosine similarity measures the angle between normalized vector embeddings."

    raw_eval = AnswerEvaluation(
        scores=DimensionScores(correctness=4, completeness=4, depth=3, reasoning=4, terminology=4, communication=4, confidence=4),
        strength=AnswerStrength.STRONG,
        key_concepts_demonstrated=["Cosine similarity"],
        missing_concepts=[],
        evidence_quote="angle between normalized vector embeddings",  # EXACT SUBSTRING
        gap_summary="",
        question_index=0,
    )

    # Setup dummy state
    state = InterviewState(
        session_id="ev-test",
        candidate=test_candidate,
        profile_analysis=ProfileAnalyzer(curriculum_engine).analyze(test_candidate),
        interview_plan=InterviewController(curriculum_engine, llm_provider)._planner.create_plan(
            test_candidate, ProfileAnalyzer(curriculum_engine).analyze(test_candidate)
        ),
    )
    state.current_question = GeneratedQuestion(
        question_text="What is vector similarity?", day=7, module=3, intent=QuestionIntent.CONCEPTUAL, difficulty=3
    )

    evidence = EvidenceVerifier.verify_and_record_evidence(raw_eval, actual_answer, state)

    assert evidence is not None
    assert evidence.is_verified is True
    assert evidence.candidate_quote == "angle between normalized vector embeddings"
    assert evidence.evidence_id == "EVID-001"


def test_fabricated_evidence_rejection(test_candidate: CandidateProfile):
    """Test 8: Fabricated evidence rejection clears candidate_quote to "" and marks is_verified=False."""
    actual_answer = "Cosine similarity measures vector angles."

    raw_eval = AnswerEvaluation(
        scores=DimensionScores(correctness=4, completeness=4, depth=3, reasoning=4, terminology=4, communication=4, confidence=4),
        strength=AnswerStrength.STRONG,
        key_concepts_demonstrated=["Cosine similarity"],
        missing_concepts=[],
        evidence_quote="The candidate demonstrated exceptional deep understanding of linear algebra",  # FABRICATED PARAPHRASE
        gap_summary="",
        question_index=0,
    )

    state = InterviewState(
        session_id="ev-test-2",
        candidate=test_candidate,
        profile_analysis=ProfileAnalyzer(curriculum_engine).analyze(test_candidate),
        interview_plan=InterviewController(curriculum_engine, llm_provider)._planner.create_plan(
            test_candidate, ProfileAnalyzer(curriculum_engine).analyze(test_candidate)
        ),
    )
    state.current_question = GeneratedQuestion(
        question_text="What is vector similarity?", day=7, module=3, intent=QuestionIntent.CONCEPTUAL, difficulty=3
    )

    evidence = EvidenceVerifier.verify_and_record_evidence(raw_eval, actual_answer, state)

    assert evidence is not None
    assert evidence.is_verified is False
    assert evidence.candidate_quote == ""  # CLEARED (DISCARDED) — NO FABRICATED QUOTE


@pytest.mark.asyncio
async def test_idk_deterministic_handling(test_candidate: CandidateProfile):
    """Test 9: 'I don't know' deterministic handling without LLM invocation."""
    mock_llm = MagicMock()
    evaluator = AnswerEvaluator(mock_llm, curriculum_engine)

    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p4-idk", test_candidate)
    calls_after_init = mock_llm.generate_structured.call_count

    q = GeneratedQuestion(question_text="Explain HNSW graph parameters.", day=8, module=3, intent=QuestionIntent.CONCEPTUAL, difficulty=3)

    idk_eval = await evaluator.evaluate(q, "i don't know", state)

    assert idk_eval.strength == AnswerStrength.WEAK
    assert idk_eval.scores.correctness == 1
    # Verify no additional generate_structured calls occurred during evaluation
    assert mock_llm.generate_structured.call_count == calls_after_init

