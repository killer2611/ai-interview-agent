"""Phase 5 unit and end-to-end integration tests for FeedbackGenerator, evidence traceability, and exact API contract."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.main import app, curriculum_engine, llm_provider, session_store
from src.models.candidate import CandidateList, CandidateProfile
from src.models.evaluation import AnswerEvaluation, AnswerStrength, DimensionScores, Evidence
from src.models.feedback import FeedbackClaim, InterviewFeedback
from src.models.interview import GeneratedQuestion, InterviewState
from src.services.evidence_verifier import EvidenceVerifier
from src.services.feedback_generator import FeedbackGenerator, _LLMFeedbackClaim, _LLMFeedbackResponse
from src.services.interview_controller import InterviewController
from src.services.interview_planner import InterviewPlanner
from src.services.profile_analyzer import ProfileAnalyzer


@pytest.fixture
def test_candidate() -> CandidateProfile:
    path = Path(__file__).parent.parent / "candidates.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateList.model_validate(data).candidates[0]  # Sarah Johnson (has skipped day 29)


@pytest.fixture
def controller() -> InterviewController:
    return InterviewController(curriculum_engine, llm_provider)


@pytest.mark.asyncio
async def test_feedback_generation(test_candidate: CandidateProfile):
    """Test 1: Feedback generation produces an InterviewFeedback object."""
    mock_llm = MagicMock()
    mock_llm.generate_structured.return_value = _LLMFeedbackResponse(
        summary="Sarah demonstrated strong overall technical capability across vector search and LLM backend architecture.",
        strengths=[_LLMFeedbackClaim(claim="Demonstrated strong understanding of Embeddings Explained", evidence_ids=["EVID-001"])],
        gaps=[_LLMFeedbackClaim(claim="Struggled with Prompt Engineering Fundamentals", evidence_ids=["EVID-002"])],
        next=["Review prompt engineering techniques", "Study monitoring and observability"],
    )

    fg = FeedbackGenerator(mock_llm, curriculum_engine)
    state = await InterviewController(curriculum_engine, mock_llm).initialize_session("test-p5-fb", test_candidate)

    # Add dummy verified evidence
    state.strengths_evidence.append(Evidence(
        evidence_id="EVID-001", question_index=0, day=7, module=3, topic="Embeddings", claim="Demonstrated strong understanding", candidate_quote="vector space", evaluation_strength=AnswerStrength.STRONG, is_verified=True
    ))
    state.weaknesses_evidence.append(Evidence(
        evidence_id="EVID-002", question_index=1, day=12, module=4, topic="Prompt Engineering", claim="Struggled with prompt techniques", candidate_quote="few shot", evaluation_strength=AnswerStrength.WEAK, is_verified=True
    ))

    feedback = await fg.generate_feedback(state)

    assert isinstance(feedback, InterviewFeedback)
    assert len(feedback.summary) > 0
    assert len(feedback.strengths) >= 1
    assert len(feedback.gaps) >= 1
    assert len(feedback.next) >= 1


def test_unsupported_claim_rejection(test_candidate: CandidateProfile):
    """Test 2 & 3: Unsupported claim rejection strips claims with zero verified evidence IDs."""
    prof = ProfileAnalyzer(curriculum_engine).analyze(test_candidate)
    plan = InterviewPlanner(curriculum_engine).create_plan(test_candidate, prof)

    state = InterviewState(session_id="test-unsupported", candidate=test_candidate, profile_analysis=prof, interview_plan=plan)

    # Only EVID-001 is a verified strength ID in state
    state.strengths_evidence.append(Evidence(
        evidence_id="EVID-001", question_index=0, day=7, module=3, topic="Embeddings", claim="Strong embeddings", candidate_quote="vec", evaluation_strength=AnswerStrength.STRONG, is_verified=True
    ))

    # Claim A has valid EVID-001; Claim B has invalid fake EVID-999
    claim_a = FeedbackClaim(claim="Valid strength", evidence_ids=["EVID-001"])
    claim_b = FeedbackClaim(claim="Hallucinated strength", evidence_ids=["EVID-999"])

    verified_s, verified_g = FeedbackGenerator._verify_claim_evidence([claim_a, claim_b], [], state)

    assert len(verified_s) == 1
    assert verified_s[0].claim == "Valid strength"  # Hallucinated claim_b rejected!


def test_skipped_vs_demonstrated_gap_handling(test_candidate: CandidateProfile):
    """Test 4: Skipped curriculum topics are placed in next[] study recommendations, NOT in gaps[]."""
    mock_llm = MagicMock()
    fg = FeedbackGenerator(mock_llm, curriculum_engine)

    prof = ProfileAnalyzer(curriculum_engine).analyze(test_candidate)
    plan = InterviewPlanner(curriculum_engine).create_plan(test_candidate, prof)
    state = InterviewState(session_id="test-skipped", candidate=test_candidate, profile_analysis=prof, interview_plan=plan)

    fg._populate_unassessed_topics(state)

    assert len(state.unassessed_topics) >= 1
    assert any("Day 29" in t for t in state.unassessed_topics)  # Day 29 was skipped in candidates.json

    next_steps = fg._ensure_unassessed_in_next(["Review general topics"], state)
    assert any("Day 29" in n or "unassessed" in n.lower() for n in next_steps)


@pytest.mark.asyncio
async def test_final_completion_and_api_contract(controller: InterviewController, test_candidate: CandidateProfile):
    """Test 5, 6 & 7: Multi-turn end-to-end interview flow and exact HTTP response contract."""
    with open(Path(__file__).parent.parent / "candidates.json", "r", encoding="utf-8") as f:
        cand_data = json.load(f)["candidates"][0]

    session_id = "e2e-contract-session-999"

    with TestClient(app) as client:
        # 1. Start Interview (Init Request)
        init_res = client.post("/api/interview", json={"sessionId": session_id, "candidate": cand_data})
        assert init_res.status_code == 200
        init_json = init_res.json()
        assert init_json["done"] is False
        assert "reply" in init_json
        assert "feedback" not in init_json or init_json["feedback"] is None

        # 2. Execute turns until completion
        done = False
        turn = 0
        final_json = {}

        substantive_answers = [
            "Vector embeddings convert raw text tokens into dense continuous numerical vectors representing deep semantic context.",
            "Cosine similarity measures the angle between vectors to determine directional closeness in vector space.",
            "Hierarchical Navigable Small World graphs optimize approximate nearest neighbor search query latency.",
            "Prompt engineering optimizes system instructions, zero-shot/few-shot examples, and output constraints for LLMs.",
            "Chatbot backends use FastAPI endpoints with streaming Server-Sent Events to deliver low-latency responses.",
            "LangChain agents use ReAct loops with tool calling to evaluate context and execute actions sequentially.",
            "Model Context Protocol defines standardized client-server protocols for exposing tools and prompts to LLMs.",
            "Docker containers package applications with dependencies for consistent Kubernetes orchestration.",
            "Observability metrics track token latency, error rates, and throughput across microservices.",
            "Capstone projects integrate vector retrieval, prompt pipelines, and multi-agent coordination end-to-end.",
            "Fine-tuning adapts model weights on domain-specific datasets using LoRA parameter-efficient tuning.",
            "Security guardrails detect prompt injection attacks and sanitize external untrusted inputs.",
        ]

        for ans in substantive_answers:
            if done:
                break
            turn += 1
            res = client.post("/api/interview", json={"sessionId": session_id, "message": ans})
            assert res.status_code == 200
            data = res.json()
            done = data["done"]
            final_json = data

        # 3. Verify final completion response contract matching technical-spec.md exactly
        assert done is True
        assert "reply" in final_json
        assert "feedback" in final_json
        feedback = final_json["feedback"]
        assert feedback is not None

        # Exact technical-spec.md field checks:
        assert isinstance(feedback["summary"], str)
        assert isinstance(feedback["strengths"], list)
        assert isinstance(feedback["gaps"], list)
        assert isinstance(feedback["next"], list)

        # Internal trace metadata MUST NOT be exposed in public API response
        assert "evidence_ids" not in feedback
        assert "decision_trace" not in feedback
