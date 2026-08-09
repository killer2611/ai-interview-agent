"""Question Generator — generates natural-language questions with structured schema and validation (v3 spec).

The Interview Controller provides all question metadata deterministically.
The Question Generator / LLM only generates the question text within those constraints.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence
from pydantic import BaseModel, Field

from src.config import settings
from src.models.interview import GeneratedQuestion, AskedQuestion
from src.prompts.question_generation import build_question_prompt
from src.services.curriculum_engine import CurriculumEngine
from src.services.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class _LLMQuestionResponse(BaseModel):
    """Schema expected from LLM question generation structured call."""

    question_text: str = Field(
        ...,
        description="The single, realistic natural-language technical question text",
    )


# Clean, candidate-facing template fallbacks keyed by intent
_TEMPLATE_FALLBACKS: dict[str, str] = {
    "conceptual": "Regarding {topic}, can you explain the core concepts and how it functions within an AI pipeline?",
    "reasoning": "When implementing {topic}, what technical reasoning guides your choice over alternative approaches?",
    "implementation": "How do you implement {topic} using tools like {tools} in practice?",
    "tradeoff": "What are the key technical trade-offs and operational limitations when using {topic}?",
    "debugging": "How do you diagnose and resolve performance or accuracy issues when working with {topic}?",
    "production": "What architectural considerations are required when deploying {topic} to production?",
    "architecture": "How would you design a scalable system architecture incorporating {topic}?",
}

# Forbidden internal leakage markers
_INTERNAL_LEAKAGE_MARKERS = [
    "specially regarding",
    "simplify the question",
    "probe the specific missing aspect",
    "test foundational prerequisite understanding",
    "missing details",
    "internal instruction",
    "follow-up strategy",
    "follow-up target",
    "meta-instruction",
    "evaluator output",
]


class QuestionValidator:
    """Performs deterministic post-generation validation checks on LLM question output."""

    @classmethod
    def validate_question(
        cls,
        question_text: str,
        topic_title: str,
        tools: Sequence[str],
        objectives: Sequence[str],
        asked_questions: Sequence[AskedQuestion],
    ) -> tuple[bool, str, str]:
        """Validate generated question against 6 deterministic checks.

        Returns:
            Tuple of (is_valid, sanitized_question_text, failure_reason).
        """
        text = question_text.strip()
        if not text:
            return False, "", "Empty question text"

        # Check 6 (Leakage Guard): Internal instruction leakage check
        text_lower = text.lower()
        for marker in _INTERNAL_LEAKAGE_MARKERS:
            if marker in text_lower:
                return False, text, f"Internal instruction leakage detected: '{marker}'"

        # Check 3: Single question check & sanitize
        q_marks = text.count("?")
        if q_marks > 1:
            parts = text.split("?")
            text = parts[0].strip() + "?"
        elif q_marks == 0:
            text = text.rstrip(".") + "?"

        # Check 4: Deduplication against asked questions
        for asked in asked_questions:
            asked_lower = asked.question_text.lower()
            current_lower = text.lower()
            if asked_lower == current_lower or asked_lower in current_lower or current_lower in asked_lower:
                return False, text, "Duplicate question text"

        # Check 1: Topic/day match (must contain title keyword, tool, or objective word)
        keywords = cls._extract_keywords(topic_title, tools, objectives)
        if not any(kw in text_lower for kw in keywords):
            return False, text, f"Missing topic keywords (expected one of: {keywords[:5]})"

        # Check 2: Conceptual anchor present
        if objectives:
            obj_words = set(w.lower() for obj in objectives for w in re.findall(r"\b\w{4,}\b", obj))
            if obj_words and not any(w in text_lower for w in obj_words):
                return False, text, "Missing conceptual anchor from objectives"

        return True, text, ""

    @staticmethod
    def _extract_keywords(title: str, tools: Sequence[str], objectives: Sequence[str]) -> list[str]:
        """Extract matching keywords for validation."""
        words = []
        for term in title.split():
            clean = re.sub(r"[^\w]", "", term).lower()
            if len(clean) >= 4:
                words.append(clean)

        for tool in tools:
            clean = tool.lower()
            if clean:
                words.append(clean)

        for obj in objectives:
            for w in re.findall(r"\b\w{4,}\b", obj):
                words.append(w.lower())

        return list(set(words))


class QuestionGenerator:
    """Generates natural-language interview questions under deterministic constraints."""

    def __init__(self, llm_provider: LLMProvider, curriculum_engine: CurriculumEngine) -> None:
        self._llm = llm_provider
        self._curriculum = curriculum_engine
        self._validator = QuestionValidator()

    async def generate_question(
        self,
        state,
        topic,
        difficulty: int,
        is_followup: bool = False,
        followup_context: str = "",
    ) -> GeneratedQuestion:
        """Generate a question using deterministic metadata from the Interview Controller.

        Args:
            state: InterviewState.
            topic: PlannedTopic or DayEntry.
            difficulty: Technical difficulty (1-5).
            is_followup: Whether this is a follow-up.
            followup_context: Probe context if follow-up.

        Returns:
            GeneratedQuestion passing all validation checks.
        """
        day_entry = self._curriculum.get_day(topic.day)
        if day_entry is None:
            raise ValueError(f"Day {topic.day} not found in curriculum")

        module_num = self._curriculum.get_module_for_day(topic.day) or 1
        module_entry = self._curriculum.get_module(module_num)
        module_title = module_entry.title if module_entry else f"Module {module_num}"

        # Attempt structured LLM generation
        system_prompt, user_prompt = build_question_prompt(
            state=state,
            topic=topic,
            difficulty=difficulty,
            is_followup=is_followup,
            followup_context=followup_context,
        )

        question_text = ""
        try:
            llm_response = self._llm.generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=_LLMQuestionResponse,
                temperature=settings.llm_temperature_question,
                max_tokens=350,
            )
            raw_text = llm_response.question_text

            # Perform post-generation validation checks
            is_valid, sanitized, reason = self._validator.validate_question(
                question_text=raw_text,
                topic_title=day_entry.title,
                tools=day_entry.tools,
                objectives=day_entry.objectives,
                asked_questions=state.asked_questions,
            )
            if is_valid:
                question_text = sanitized
            else:
                logger.warning("LLM question validation failed (%s) — using template fallback", reason)
                question_text = self._get_template_fallback(day_entry, topic.intent.value, module_title, is_followup)

        except Exception as e:
            logger.warning("LLM question generation failed (%s) — using template fallback", str(e))
            question_text = self._get_template_fallback(day_entry, topic.intent.value, module_title, is_followup)

        return GeneratedQuestion(
            question_text=question_text,
            day=topic.day,
            module=module_num,
            objectives=day_entry.objectives,
            tools=day_entry.tools,
            intent=topic.intent,
            difficulty=difficulty,
            is_followup=is_followup,
            followup_context=followup_context,
        )

    def _get_template_fallback(
        self,
        day_entry,
        intent_val: str,
        module_title: str,
        is_followup: bool = False,
    ) -> str:
        """Construct a clean, candidate-facing template question fallback.

        NEVER includes internal strategy text or metadata labels.
        """
        template = _TEMPLATE_FALLBACKS.get(
            intent_val,
            "Regarding {topic}, can you explain how you would apply it in practice?",
        )
        tools_str = ", ".join(day_entry.tools) if day_entry.tools else "Python tools"
        base_question = template.format(
            topic=day_entry.title,
            module_title=module_title,
            tools=tools_str,
        )

        if is_followup:
            return f"Building on your response about {day_entry.title}, how do you handle technical trade-offs and edge cases in practice?"

        return base_question
