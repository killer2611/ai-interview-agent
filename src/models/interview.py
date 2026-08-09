"""Pydantic models for interview state, plan, trace, and runtime tracking (v3 spec)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from src.models.candidate import CandidateProfile
from src.models.evaluation import AnswerEvaluation, AnswerStrength, Evidence
from src.models.feedback import InterviewFeedback


class ExperienceTier(str, Enum):
    """Candidate experience classification."""

    JUNIOR = "junior"       # 0-2 years
    MID = "mid"             # 3-7 years
    SENIOR = "senior"       # 8-14 years
    EXPERT = "expert"       # 15+ years


class TopicPriority(BaseModel):
    """A single topic prioritized for the interview plan."""

    day: int
    title: str
    priority: str = Field(..., description="mandatory_probe | struggle_probe | strength_validation | coverage_fill | role_relevant")
    reason: str = Field(..., description="Why this topic was selected")
    suggested_difficulty: int = Field(..., ge=1, le=5)
    gap_signal_weight: int = Field(0, description="Score contribution from highest-precedence gap signal")
    total_score: float = Field(0.0, description="Total topic priority score")


class ProfileAnalysis(BaseModel):
    """Result of analyzing a candidate's profile for interview planning (v3 spec)."""

    tier: ExperienceTier
    starting_difficulty: int = Field(..., ge=1, le=5, description="Derived SOLELY from learning signals")
    role_relevance: str = Field("", description="How the candidate's role relates to the curriculum")
    strong_days: list[int] = Field(default_factory=list, description="Days passed on first attempt")
    weak_days: list[int] = Field(default_factory=list, description="Days with high attempts, failed, or skipped")
    failed_days: list[int] = Field(default_factory=list, description="Days the candidate failed")
    skipped_days: list[int] = Field(default_factory=list, description="Days the candidate skipped")
    struggle_days: list[int] = Field(default_factory=list, description="Days with >=4 attempts")
    topic_priorities: list[TopicPriority] = Field(default_factory=list, description="Prioritized list of interview topics")
    engagement_ratio: float = Field(0.0, description="commitDays / 31")
    first_try_ratio: float = Field(0.0, description="missionsFirstTry / missionsCompleted")


class QuestionIntent(str, Enum):
    """The pedagogical intent of a question."""

    CONCEPTUAL = "conceptual"
    REASONING = "reasoning"
    IMPLEMENTATION = "implementation"
    TRADEOFF = "tradeoff"
    DEBUGGING = "debugging"
    PRODUCTION = "production"
    ARCHITECTURE = "architecture"


class PlannedTopic(BaseModel):
    """A single topic in the interview plan."""

    day: int = Field(..., description="Curriculum day number")
    title: str = Field(..., description="Curriculum day title")
    module: int = Field(..., description="Curriculum module number")
    objectives: list[str] = Field(default_factory=list, description="Relevant objectives from curriculum day")
    tools: list[str] = Field(default_factory=list, description="Tools associated with this day")
    intent: QuestionIntent = Field(..., description="What type of question to ask")
    initial_difficulty: int = Field(..., ge=1, le=5)
    priority: str = Field("", description="Why this topic is in the plan")
    topic_score: float = Field(0.0, description="The deterministic topic score")


class InterviewPlan(BaseModel):
    """The interview plan generated before the interview begins."""

    topics: list[PlannedTopic] = Field(default_factory=list)
    target_question_count: int = Field(10, ge=8, description="Target number of questions")
    candidate_tier: ExperienceTier = Field(...)


class ConversationTurn(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(..., description="'interviewer' or 'candidate'")
    content: str


class AskedQuestion(BaseModel):
    """Record of a question that was asked during the interview."""

    question_text: str
    day: int
    module: int
    objectives: list[str] = Field(default_factory=list)
    intent: QuestionIntent
    difficulty: int = Field(..., ge=1, le=5)
    is_followup: bool = Field(False, description="True if this was a follow-up")


class GeneratedQuestion(BaseModel):
    """Output of the Question Generator service."""

    question_text: str
    day: int
    module: int
    objectives: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    intent: QuestionIntent
    difficulty: int = Field(..., ge=1, le=5)
    is_followup: bool = False
    followup_context: str = Field("", description="If a follow-up, what is being probed")


class FollowUpAction(str, Enum):
    """The action the follow-up engine decided on."""

    FOLLOW_UP = "follow_up"
    NEXT_TOPIC = "next_topic"


class FollowUpDecision(BaseModel):
    """Output of the Follow-up Engine."""

    action: FollowUpAction
    rationale: str = Field(..., description="Why this decision was made")
    followup_context: str = Field("", description="If follow_up: what to probe")
    adjust_difficulty: int = Field(0, description="-1, 0, or +1 adjustment suggestion")
    target_plan_index: int | None = Field(None, description="If next_topic: which plan index to go to")


class AdaptiveTraceEntry(BaseModel):
    """Records WHY a question was asked for debugging and demo inspection (v3 spec)."""

    question_index: int
    triggering_evaluation_strength: AnswerStrength | None = None
    selected_topic_day: int
    selected_topic_title: str
    difficulty: int
    intent: QuestionIntent
    reason: str
    is_followup: bool
    curriculum_module: int
    topic_score: float = 0.0


class InterviewState(BaseModel):
    """Complete interview state — single source of truth for a session (v3 spec)."""

    # === Identity ===
    session_id: str
    candidate: CandidateProfile
    profile_analysis: ProfileAnalysis

    # === Plan ===
    interview_plan: InterviewPlan
    current_plan_index: int = 0

    # === Current turn ===
    current_question: GeneratedQuestion | None = None
    current_topic_followup_count: int = 0

    # === Counters ===
    question_count: int = 0
    turn_count: int = 0

    # === History ===
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    asked_questions: list[AskedQuestion] = Field(default_factory=list)
    decision_trace: list[AdaptiveTraceEntry] = Field(default_factory=list)

    # === Coverage ===
    covered_days: set[int] = Field(default_factory=set)
    meaningfully_covered_days: set[int] = Field(default_factory=set)
    covered_modules: set[int] = Field(default_factory=set)
    covered_objectives: set[str] = Field(default_factory=set)

    # === Difficulty ===
    current_difficulty: int = 3
    difficulty_history: list[int] = Field(default_factory=list)

    # === Evaluations ===
    evaluations: list[AnswerEvaluation] = Field(default_factory=list)

    # === Evidence ===
    evidence_counter: int = 0
    strengths_evidence: list[Evidence] = Field(default_factory=list)
    weaknesses_evidence: list[Evidence] = Field(default_factory=list)
    unassessed_topics: list[str] = Field(default_factory=list)

    # === Completion ===
    is_complete: bool = False
    feedback: InterviewFeedback | None = None

    # === Timestamps ===
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(arbitrary_types_allowed=True)
