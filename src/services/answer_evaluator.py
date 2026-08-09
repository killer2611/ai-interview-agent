"""Answer Evaluator — evaluates candidate answers via LLM rubric or deterministic fallback (v3 spec).

The LLM scores the 7 rubric dimensions; strength classification is strictly deterministic.
"""

from __future__ import annotations

import logging
from pydantic import Field

from src.config import settings
from src.models.evaluation import (
    AnswerEvaluation,
    AnswerStrength,
    DimensionScores,
)
from src.models.interview import GeneratedQuestion, InterviewState
from src.prompts.answer_evaluation import build_evaluation_prompt
from src.services.curriculum_engine import CurriculumEngine
from src.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class _LLMEvaluationResponse(DimensionScores):
    """Schema expected from LLM evaluation structured call."""

    key_concepts_demonstrated: list[str] = Field(
        default_factory=list,
        description="Specific technical concepts the candidate demonstrated correctly",
    )
    missing_concepts: list[str] = Field(
        default_factory=list,
        description="Important concepts the candidate omitted or failed to address",
    )
    misconceptions: list[str] = Field(
        default_factory=list,
        description="Incorrect technical assumptions or errors in the answer",
    )
    evidence_quote: str = Field(
        "",
        description="EXACT verbatim substring from candidate answer text",
    )
    gap_summary: str = Field(
        "",
        description="Summary of gaps or weaknesses",
    )
    suggested_followup_focus: str = Field(
        "",
        description="Recommended focus for follow-up probe if needed",
    )


class AnswerEvaluator:
    """Evaluates candidate answers against the curriculum rubric."""

    def __init__(self, llm_provider: LLMProvider, curriculum_engine: CurriculumEngine) -> None:
        self._llm = llm_provider
        self._curriculum = curriculum_engine

    async def evaluate(
        self,
        question: GeneratedQuestion | None,
        answer: str,
        state: InterviewState,
    ) -> AnswerEvaluation:
        """Evaluate candidate's answer text.

        Args:
            question: Question that was asked.
            answer: Candidate's raw answer text.
            state: Current interview state.

        Returns:
            AnswerEvaluation with scores, strength, concepts, evidence quote, and follow-up signal.
        """
        if question is None:
            return self._default_evaluation(state.question_count - 1)

        day_entry = self._curriculum.get_day(question.day)
        if day_entry is None:
            return self._default_evaluation(state.question_count - 1)

        # Check for non-substantive / IDK answers -> deterministic weak evaluation (NO LLM CALL)
        stripped = answer.strip().lower()
        idk_phrases = {"i don't know", "idk", "no idea", "pass", "skip", "dont know", "not sure", "no clue"}
        if not stripped or stripped in idk_phrases:
            return self._build_idk_evaluation(state.question_count - 1, answer)

        # Build prompts
        system_prompt, user_prompt = build_evaluation_prompt(
            question_text=question.question_text,
            answer_text=answer,
            day_entry=day_entry,
            question_index=state.question_count - 1,
        )

        try:
            llm_eval = self._llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=_LLMEvaluationResponse,
                temperature=settings.llm_temperature_evaluation,
                max_tokens=600,
            )

            scores = DimensionScores(
                correctness=llm_eval.correctness,
                completeness=llm_eval.completeness,
                depth=llm_eval.depth,
                reasoning=llm_eval.reasoning,
                terminology=llm_eval.terminology,
                communication=llm_eval.communication,
                confidence=llm_eval.confidence,
            )

            strength = scores.classify_strength()

            return AnswerEvaluation(
                scores=scores,
                strength=strength,
                key_concepts_demonstrated=llm_eval.key_concepts_demonstrated,
                missing_concepts=llm_eval.missing_concepts,
                misconceptions=llm_eval.misconceptions,
                evidence_quote=llm_eval.evidence_quote,
                gap_summary=llm_eval.gap_summary,
                suggested_followup_focus=llm_eval.suggested_followup_focus,
                question_index=state.question_count - 1,
            )

        except Exception as e:
            logger.warning("LLM evaluation failed (%s) — using fallback evaluation", str(e))
            return self._heuristic_fallback_evaluation(answer, state.question_count - 1)

    @staticmethod
    def _build_idk_evaluation(question_index: int, answer: str) -> AnswerEvaluation:
        """Deterministic evaluation for 'I don't know' style answers."""
        scores = DimensionScores(
            correctness=1, completeness=1, depth=1, reasoning=1,
            terminology=1, communication=1, confidence=1,
        )
        return AnswerEvaluation(
            scores=scores,
            strength=AnswerStrength.WEAK,
            key_concepts_demonstrated=[],
            missing_concepts=["Unable to assess — candidate indicated they do not know"],
            misconceptions=[],
            evidence_quote=answer.strip(),
            gap_summary="Candidate stated they do not know the topic",
            suggested_followup_focus="Simplify question to test basic foundation",
            question_index=question_index,
        )

    @staticmethod
    def _heuristic_fallback_evaluation(answer: str, question_index: int) -> AnswerEvaluation:
        """Deterministic heuristic evaluation when LLM provider fails."""
        word_count = len(answer.split())
        if word_count > 30:
            scores = DimensionScores(
                correctness=3, completeness=3, depth=3, reasoning=3,
                terminology=3, communication=3, confidence=3,
            )
            key_concepts = ["Detailed technical response provided"]
            missing_concepts = []
            misconceptions = []
        elif word_count > 10:
            scores = DimensionScores(
                correctness=2, completeness=2, depth=2, reasoning=2,
                terminology=2, communication=2, confidence=2,
            )
            key_concepts = ["Basic response provided"]
            missing_concepts = ["Response lacks full technical depth"]
            misconceptions = []
        else:
            scores = DimensionScores(
                correctness=1, completeness=1, depth=1, reasoning=1,
                terminology=1, communication=1, confidence=1,
            )
            key_concepts = []
            missing_concepts = ["Brief answer lacking technical details"]
            misconceptions = []

        quote = answer[:100] if answer else ""

        return AnswerEvaluation(
            scores=scores,
            strength=scores.classify_strength(),
            key_concepts_demonstrated=key_concepts,
            missing_concepts=missing_concepts,
            misconceptions=misconceptions,
            evidence_quote=quote,
            gap_summary="Heuristic evaluation fallback used",
            suggested_followup_focus="",
            question_index=question_index,
        )

    @staticmethod
    def _default_evaluation(question_index: int) -> AnswerEvaluation:
        scores = DimensionScores(
            correctness=3, completeness=3, depth=3, reasoning=3,
            terminology=3, communication=3, confidence=3,
        )
        return AnswerEvaluation(
            scores=scores,
            strength=AnswerStrength.PARTIAL,
            key_concepts_demonstrated=[],
            missing_concepts=[],
            misconceptions=[],
            evidence_quote="",
            gap_summary="",
            suggested_followup_focus="",
            question_index=question_index,
        )
