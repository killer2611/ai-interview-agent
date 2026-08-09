"""Interview Controller — central deterministic coordinator for the interview loop (v3 spec).

Single owner of state transitions, coverage tracking, difficulty adjustments,
follow-up decisions, topic selection, adaptive trace recording, and quality gates.
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.models.candidate import CandidateProfile
from src.models.evaluation import AnswerEvaluation, AnswerStrength
from src.models.feedback import InterviewFeedback
from src.models.interview import (
    AdaptiveTraceEntry,
    AskedQuestion,
    ConversationTurn,
    FollowUpAction,
    FollowUpDecision,
    GeneratedQuestion,
    InterviewState,
    PlannedTopic,
    QuestionIntent,
)
from src.services.answer_evaluator import AnswerEvaluator
from src.services.coverage_tracker import CoverageTracker
from src.services.curriculum_engine import CurriculumEngine
from src.services.difficulty_manager import DifficultyManager
from src.services.evidence_verifier import EvidenceVerifier
from src.services.feedback_generator import FeedbackGenerator
from src.services.followup_engine import FollowUpEngine
from src.services.interview_planner import InterviewPlanner
from src.services.llm_provider import LLMProvider
from src.services.profile_analyzer import ProfileAnalyzer
from src.services.question_generator import QuestionGenerator

logger = logging.getLogger(__name__)


class InterviewController:
    """Central deterministic orchestrator for all interview interactions."""

    def __init__(
        self,
        curriculum_engine: CurriculumEngine,
        llm_provider: LLMProvider,
    ) -> None:
        self._curriculum = curriculum_engine
        self._profile_analyzer = ProfileAnalyzer(curriculum_engine)
        self._planner = InterviewPlanner(curriculum_engine)
        self._evaluator = AnswerEvaluator(llm_provider, curriculum_engine)
        self._evidence_verifier = EvidenceVerifier()
        self._followup_engine = FollowUpEngine()
        self._difficulty_manager = DifficultyManager()
        self._coverage_tracker = CoverageTracker()
        self._question_generator = QuestionGenerator(llm_provider, curriculum_engine)
        self._feedback_generator = FeedbackGenerator(llm_provider, curriculum_engine)


    async def initialize_session(self, session_id: str, candidate: CandidateProfile) -> InterviewState:
        """Initialize a new interview session.

        Flow: Candidate -> Profile Analysis -> Interview Plan -> Q1 -> Initial State.

        Args:
            session_id: Unique session identifier.
            candidate: Candidate profile from candidates.json.

        Returns:
            Initialized InterviewState with Q1 generated and recorded.
        """
        # 1. Analyze candidate profile
        profile_analysis = self._profile_analyzer.analyze(candidate)

        # 2. Generate interview plan (scored & ranked topics)
        interview_plan = self._planner.create_plan(candidate, profile_analysis)

        # 3. Create initial InterviewState
        state = InterviewState(
            session_id=session_id,
            candidate=candidate,
            profile_analysis=profile_analysis,
            interview_plan=interview_plan,
            current_difficulty=profile_analysis.starting_difficulty,
        )

        # 4. Generate first question (Q1)
        first_topic = interview_plan.topics[0]
        q1 = await self._question_generator.generate_question(
            state=state,
            topic=first_topic,
            difficulty=first_topic.initial_difficulty,
            is_followup=False,
            followup_context="",
        )

        # 5. Update state for Q1
        state.current_question = q1
        state.question_count = 1
        state.turn_count = 1
        state.asked_questions.append(AskedQuestion(
            question_text=q1.question_text,
            day=q1.day,
            module=q1.module,
            objectives=q1.objectives,
            intent=q1.intent,
            difficulty=q1.difficulty,
            is_followup=False,
        ))
        state.covered_days.add(q1.day)
        state.covered_modules.add(q1.module)
        for obj in q1.objectives:
            state.covered_objectives.add(obj)
        state.difficulty_history.append(q1.difficulty)

        # 6. Record Q1 adaptive trace entry
        state.decision_trace.append(AdaptiveTraceEntry(
            question_index=0,
            triggering_evaluation_strength=None,
            selected_topic_day=q1.day,
            selected_topic_title=first_topic.title,
            difficulty=q1.difficulty,
            intent=q1.intent,
            reason="Initial plan selection — top ranked topic",
            is_followup=False,
            curriculum_module=q1.module,
            topic_score=first_topic.topic_score,
        ))

        # 7. Add natural welcome message to conversation history
        welcome = (
            f"Welcome, {candidate.member.name}. Thank you for joining this technical interview. "
            f"I'll be asking you a series of technical questions based on your background. "
            f"Take your time with each answer.\n\n{q1.question_text}"
        )
        state.conversation_history.append(ConversationTurn(role="interviewer", content=welcome))

        return state

    async def process_turn(
        self,
        state: InterviewState,
        candidate_answer: str,
    ) -> tuple[InterviewState, str, bool, InterviewFeedback | None]:
        """Process a candidate turn in an ongoing interview session.

        Flow:
        1. Record candidate answer
        2. Evaluate answer (AnswerEvaluator)
        3. Verify evidence quote (EvidenceVerifier)
        4. Check & record meaningful coverage (CoverageTracker)
        5. Adjust difficulty (DifficultyManager)
        6. Check completion quality gate
        7. Decides follow-up vs next-topic (FollowUpEngine)
        8. Generate next question under constraints (QuestionGenerator)
        9. Record adaptive trace entry
        10. Return reply string, done flag, and feedback if done

        Args:
            state: Current InterviewState.
            candidate_answer: Raw text response from candidate.

        Returns:
            Tuple of (updated_state, reply_text, is_done, optional_feedback).
        """
        if state.is_complete:
            return state, "Interview is already complete.", True, state.feedback

        # 1. Record candidate answer
        state.conversation_history.append(ConversationTurn(role="candidate", content=candidate_answer))
        state.turn_count += 1

        # 2. Evaluate answer
        evaluation = await self._evaluator.evaluate(
            question=state.current_question,
            answer=candidate_answer,
            state=state,
        )
        state.evaluations.append(evaluation)

        # 3. Verify evidence quote & record evidence in state
        evidence = self._evidence_verifier.verify_and_record_evidence(
            evaluation=evaluation,
            actual_answer=candidate_answer,
            state=state,
        )

        # 4. Check & record meaningful coverage (v3 spec)
        if self._coverage_tracker.is_meaningfully_covered(
            question=state.current_question,
            answer=candidate_answer,
            evaluation=evaluation,
        ):
            if state.current_question:
                state.meaningfully_covered_days.add(state.current_question.day)

        # 5. Adjust difficulty dynamically
        new_difficulty = self._difficulty_manager.adjust(
            current_difficulty=state.current_difficulty,
            evaluations=state.evaluations,
        )
        state.current_difficulty = new_difficulty

        # 6. Check completion quality gate
        if self._coverage_tracker.can_complete(state):
            # Completion criteria satisfied!
            state.is_complete = True
            feedback = await self._feedback_generator.generate_feedback(state)
            state.feedback = feedback
            closing = f"Thank you, {state.candidate.member.name}. That concludes our technical interview.\n\n{feedback.summary}"
            state.conversation_history.append(ConversationTurn(role="interviewer", content=closing))
            return state, closing, True, feedback


        # 7. Follow-up recommendation from FollowUpEngine
        decision = self._followup_engine.decide(evaluation, state)

        # 8. Topic selection and metadata setup
        if decision.action == FollowUpAction.FOLLOW_UP and state.current_question:
            # Same topic follow-up
            state.current_topic_followup_count += 1
            day_entry = self._curriculum.get_day(state.current_question.day)
            topic_obj = PlannedTopic(
                day=state.current_question.day,
                title=day_entry.title if day_entry else f"Day {state.current_question.day}",
                module=state.current_question.module,
                objectives=state.current_question.objectives,
                tools=state.current_question.tools,
                intent=state.current_question.intent,
                initial_difficulty=state.current_difficulty,
                priority="followup",
                topic_score=0.0,
            )
            is_followup = True
            followup_context = decision.followup_context
            reason = f"Follow-up: {decision.rationale}"
        else:
            # Transition to next planned topic
            state.current_topic_followup_count = 0
            if decision.target_plan_index is not None and 0 <= decision.target_plan_index < len(state.interview_plan.topics):
                state.current_plan_index = decision.target_plan_index
            else:
                state.current_plan_index = min(state.current_plan_index + 1, len(state.interview_plan.topics) - 1)

            topic_obj = state.interview_plan.topics[state.current_plan_index]
            is_followup = False
            followup_context = ""
            reason = f"Next topic: {decision.rationale}"

        # 9. Generate next question
        next_q = await self._question_generator.generate_question(
            state=state,
            topic=topic_obj,
            difficulty=state.current_difficulty,
            is_followup=is_followup,
            followup_context=followup_context,
        )

        # 10. Update state with next question
        state.current_question = next_q
        state.question_count += 1
        state.asked_questions.append(AskedQuestion(
            question_text=next_q.question_text,
            day=next_q.day,
            module=next_q.module,
            objectives=next_q.objectives,
            intent=next_q.intent,
            difficulty=next_q.difficulty,
            is_followup=is_followup,
        ))
        state.covered_days.add(next_q.day)
        state.covered_modules.add(next_q.module)
        for obj in next_q.objectives:
            state.covered_objectives.add(obj)
        state.difficulty_history.append(next_q.difficulty)

        # 11. Record AdaptiveTraceEntry (v3 spec)
        state.decision_trace.append(AdaptiveTraceEntry(
            question_index=state.question_count - 1,
            triggering_evaluation_strength=evaluation.strength,
            selected_topic_day=next_q.day,
            selected_topic_title=topic_obj.title,
            difficulty=next_q.difficulty,
            intent=next_q.intent,
            reason=reason,
            is_followup=is_followup,
            curriculum_module=next_q.module,
            topic_score=topic_obj.topic_score,
        ))

        # 12. Build conversational transition reply
        reply = self._build_turn_reply(evaluation.strength, next_q.question_text, is_followup)
        state.conversation_history.append(ConversationTurn(role="interviewer", content=reply))

        return state, reply, False, None

    @staticmethod
    def _build_turn_reply(strength: AnswerStrength, question_text: str, is_followup: bool) -> str:
        """Construct natural transition response."""
        if is_followup:
            transitions = {
                AnswerStrength.STRONG: "Great answer. Let's delve a bit deeper into this.",
                AnswerStrength.PARTIAL: "Thanks for that. I'd like to clarify one aspect further.",
                AnswerStrength.WEAK: "I appreciate your response. Let's approach this from a simpler angle.",
            }
        else:
            transitions = {
                AnswerStrength.STRONG: "Excellent. Let's move on to our next topic.",
                AnswerStrength.PARTIAL: "Thank you. Let's shift focus to a different area.",
                AnswerStrength.WEAK: "Thank you. Let's move on to the next topic.",
            }
        prefix = transitions.get(strength, "Thank you.")
        return f"{prefix}\n\n{question_text}"
