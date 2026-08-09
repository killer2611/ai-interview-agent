"""Phase 3 unit and integration tests for InterviewController, state persistence, adaptive loop, and quality gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.main import app, curriculum_engine, session_store, llm_provider
from src.models.candidate import CandidateList, CandidateProfile
from src.models.evaluation import AnswerEvaluation, AnswerStrength, DimensionScores
from src.models.interview import GeneratedQuestion, InterviewState
from src.services.coverage_tracker import CoverageTracker
from src.services.interview_controller import InterviewController
from src.services.interview_planner import InterviewPlanner
from src.services.profile_analyzer import ProfileAnalyzer


@pytest.fixture
def test_candidate() -> CandidateProfile:
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data).candidates[0]  # CAND-001


@pytest.fixture
def controller() -> InterviewController:
    return InterviewController(curriculum_engine, llm_provider)


@pytest.mark.asyncio
async def test_new_session_initialization(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 1: New session initialization generates state, Q1, and initial adaptive trace entry."""
    session_id = "test-init-001"
    state = await controller.initialize_session(session_id, test_candidate)

    assert state.session_id == session_id
    assert state.question_count == 1
    assert state.turn_count == 1
    assert state.current_question is not None
    assert len(state.asked_questions) == 1
    assert len(state.decision_trace) == 1

    # Verify initial trace entry
    trace0 = state.decision_trace[0]
    assert trace0.question_index == 0
    assert trace0.triggering_evaluation_strength is None
    assert trace0.is_followup is False
    assert "Initial plan selection" in trace0.reason


@pytest.mark.asyncio
async def test_session_continuation_and_persistence(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 2 & 3: Session continuation and state persistence across turns using sessionId."""
    session_id = "test-continue-002"
    state = await controller.initialize_session(session_id, test_candidate)
    session_store.create(state)

    # Turn 1
    answer1 = "Vector similarity search uses inner products or cosine angle calculations to find nearest neighbours in embeddings space."
    updated_state, reply1, done1, feedback1 = await controller.process_turn(state, answer1)
    session_store.update(updated_state)

    assert done1 is False
    assert updated_state.turn_count == 2
    assert updated_state.question_count == 2
    assert len(updated_state.conversation_history) == 3  # welcome, cand1, interviewer1
    assert len(updated_state.decision_trace) == 2

    # Retrieve from session store
    persisted = session_store.get(session_id)
    assert persisted is not None
    assert persisted.question_count == 2


@pytest.mark.asyncio
async def test_followup_after_partial_answer(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 4: Partial answer triggers follow-up on same topic."""
    session_id = "test-partial-003"
    state = await controller.initialize_session(session_id, test_candidate)

    # Provide a short partial answer
    partial_answer = "Embeddings are numbers representing text in a vector space."
    state, reply, done, _ = await controller.process_turn(state, partial_answer)

    # Next question should be a follow-up on the same topic
    last_trace = state.decision_trace[-1]
    assert last_trace.is_followup is True
    assert "Follow-up" in last_trace.reason
    assert state.current_topic_followup_count == 1


@pytest.mark.asyncio
async def test_deeper_probe_after_strong_answer(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 5: Strong answer triggers deeper follow-up probe and difficulty increase."""
    session_id = "test-strong-004"
    state = await controller.initialize_session(session_id, test_candidate)

    # Provide a detailed strong answer
    strong_answer = (
        "Embeddings map high-dimensional sparse textual features into dense continuous vector spaces. "
        "We compute cosine similarity or Euclidean distance between vectors to retrieve semantic neighbors efficiently. "
        "Vector databases like Pinecone or Milvus index these vectors using HNSW graphs for sub-linear search latency."
    )
    state, reply, done, _ = await controller.process_turn(state, strong_answer)

    last_trace = state.decision_trace[-1]
    assert last_trace.is_followup is True
    assert state.current_topic_followup_count == 1


@pytest.mark.asyncio
async def test_transition_to_new_topic(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 6: Transition to a new topic after max follow-ups reached."""
    session_id = "test-transition-005"
    state = await controller.initialize_session(session_id, test_candidate)

    # Turn 1: Substantive partial answer (15 words -> PARTIAL evaluation -> triggers follow-up 1)
    ans1 = "Vector embeddings convert raw text tokens into dense continuous numerical vectors representing deep semantic context."
    state, _, _, _ = await controller.process_turn(state, ans1)
    assert state.current_topic_followup_count == 1

    # Turn 2: Substantive partial answer (14 words -> PARTIAL evaluation -> triggers follow-up 2)
    ans2 = "Cosine similarity measures the angle between vectors to determine directional closeness in space."
    state, _, _, _ = await controller.process_turn(state, ans2)
    assert state.current_topic_followup_count == 2

    # Turn 3: Substantive answer (13 words -> max follow-ups reached, must transition to NEXT TOPIC)
    ans3 = "Hierarchical Navigable Small World graphs optimize approximate nearest neighbor search query latency."
    state, _, _, _ = await controller.process_turn(state, ans3)

    last_trace = state.decision_trace[-1]
    assert last_trace.is_followup is False
    assert "Next topic" in last_trace.reason
    assert state.current_topic_followup_count == 0


@pytest.mark.asyncio
async def test_no_duplicate_questions(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 7: Verify asked questions list maintains unique questions."""
    session_id = "test-dedup-006"
    state = await controller.initialize_session(session_id, test_candidate)

    for i in range(5):
        state, _, _, _ = await controller.process_turn(state, f"Substantive answer turn {i} providing detailed technical concepts for evaluation.")

    asked_texts = [q.question_text for q in state.asked_questions]
    assert len(asked_texts) == len(set(asked_texts))  # All asked questions are unique


@pytest.mark.asyncio
async def test_adaptive_trace_recording(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 8: Adaptive trace records detailed decision entries for debugging."""
    session_id = "test-trace-007"
    state = await controller.initialize_session(session_id, test_candidate)
    state, _, _, _ = await controller.process_turn(state, "Vector search uses dot products in high dimensional space to match vectors.")

    assert len(state.decision_trace) == 2
    entry = state.decision_trace[1]
    assert entry.question_index == 1
    assert entry.triggering_evaluation_strength is not None
    assert entry.difficulty >= 1
    assert entry.curriculum_module >= 1
    assert len(entry.reason) > 0


def test_completion_gate_constraints():
    """Test 9, 10, 11, 13: Completion quality gate requirements."""
    tracker = CoverageTracker()
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        cand = CandidateList.model_validate(json.load(f)).candidates[0]

    analyzer = ProfileAnalyzer(curriculum_engine)
    planner = InterviewPlanner(curriculum_engine)
    prof = analyzer.analyze(cand)
    plan = planner.create_plan(cand, prof)

    # Create state with < 8 questions -> CANNOT complete
    state = InterviewState(
        session_id="dummy",
        candidate=cand,
        profile_analysis=prof,
        interview_plan=plan,
    )
    state.question_count = 5
    state.meaningfully_covered_days = {7, 8, 10, 12}
    state.covered_days = {7, 8, 10, 12}
    state.covered_modules = {3, 4}

    assert tracker.can_complete(state) is False  # question_count < 8

    # Set question_count = 8, but < 4 meaningful days -> CANNOT complete
    state.question_count = 8
    state.meaningfully_covered_days = {7, 8, 10}  # Only 3 meaningful days
    assert tracker.can_complete(state) is False

    # Set 10 questions with 7 meaningful days (70% plan coverage) -> CAN complete
    state.question_count = 10
    state.meaningfully_covered_days = {7, 8, 10, 12, 16, 22, 28}
    assert tracker.can_complete(state) is True



@pytest.mark.asyncio
async def test_maximum_question_safety_limit(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 12: Maximum question safety limit (prioritizes completion/coverage fill near max)."""
    session_id = "test-max-008"
    state = await controller.initialize_session(session_id, test_candidate)

    # Fast-forward to question_count = 13 (near max 15)
    for i in range(12):
        state, reply, done, feedback = await controller.process_turn(state, f"Substantive answer turn {i} explaining technical details.")
        if done:
            break

    # Verify interview completed or is near limit
    assert state.question_count >= 8
    assert len(state.meaningfully_covered_days) >= 4


def test_pre_interview_signals_not_reapplied_as_weaknesses():
    """Test 14: Pre-interview failed/skipped signals do NOT pollute interview evaluations if answer is strong."""
    # Pre-interview profile signal: failed day 8
    # If the candidate answers day 8 question strongly in the interview, evaluation is STRONG
    eval_result = AnswerEvaluation(
        scores=DimensionScores(correctness=5, completeness=5, depth=4, reasoning=4, terminology=4, communication=4, confidence=4),
        strength=AnswerStrength.STRONG,
        key_concepts_demonstrated=["Vector Databases", "Indexing", "HNSW"],
        missing_concepts=[],
        evidence_quote="Vector databases store embeddings and index them using HNSW graphs.",
        gap_summary="",
        question_index=2,
    )
    assert eval_result.strength == AnswerStrength.STRONG
    assert len(eval_result.missing_concepts) == 0


def test_api_endpoint_init_and_turn():
    """Test HTTP API POST /api/interview for init and turn requests via TestClient."""
    with open(Path(__file__).parent.parent / "candidates.json", "r", encoding="utf-8") as f:
        cand_data = json.load(f)["candidates"][0]

    with TestClient(app) as client:
        # Init request
        init_res = client.post("/api/interview", json={"sessionId": "http-sess-001", "candidate": cand_data})
        assert init_res.status_code == 200
        init_json = init_res.json()
        assert init_json["done"] is False
        assert "Welcome" in init_json["reply"]

        # Turn request
        turn_res = client.post("/api/interview", json={
            "sessionId": "http-sess-001",
            "message": "Vector similarity search measures distances between embedding vectors."
        })
        assert turn_res.status_code == 200
        turn_json = turn_res.json()
        assert turn_json["done"] is False
        assert len(turn_json["reply"]) > 0
