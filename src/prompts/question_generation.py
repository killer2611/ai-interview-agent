"""Prompt templates for LLM Question Generation (Call Site 1).

Encourages realistic, natural technical interview questions appropriate for the
candidate's role, experience tier, intent, and curriculum objectives.
"""

from __future__ import annotations

from typing import Sequence

from src.models.interview import InterviewState, PlannedTopic, AskedQuestion
from src.services.difficulty_manager import DifficultyManager


def build_question_prompt(
    state: InterviewState,
    topic: PlannedTopic,
    difficulty: int,
    is_followup: bool = False,
    followup_context: str = "",
) -> tuple[str, str]:
    """Build system and user prompts for generating a technical interview question.

    Args:
        state: Current interview state.
        topic: Planned topic metadata determined by controller.
        difficulty: Target technical difficulty (1-5).
        is_followup: Whether this question is a follow-up.
        followup_context: Focus of probe if follow-up.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    difficulty_label = DifficultyManager.get_difficulty_label(difficulty)
    tier = state.profile_analysis.tier
    role = state.candidate.member.jobRole
    name = state.candidate.member.name

    system_prompt = f"""You are an experienced lead technical interviewer conducting a live interview with {name}, a {role} with {tier.value}-level experience.

Your goal is to generate ONE realistic, conversational, and technically insightful interview question.

STRICT REQUIREMENTS:
- Ask exactly ONE question. Do not ask multiple questions or sub-questions.
- Do NOT use robotic title-restatement phrasing (e.g. NEVER ask "How would you design the system architecture incorporating <Title>?").
- Frame the question as a natural, realistic technical interview scenario or technical inquiry suitable for a {role}.
- Difficulty level: {difficulty_label} ({difficulty}/5).
- Question intent: {topic.intent.value.upper()}.
- Focus on how concepts work, why trade-offs are made, or how to solve engineering problems in practice.
- Keep the question concise (1 to 3 sentences maximum).
- Do NOT provide the answer or criteria in your question text.
- Respond with ONLY a JSON object matching the requested schema."""

    objectives_text = "\n".join(f"- {obj}" for obj in topic.objectives)
    tools_text = ", ".join(topic.tools) if topic.tools else "Standard Python/AI stack"

    recent_questions_text = ""
    if state.asked_questions:
        recent = state.asked_questions[-4:]
        recent_questions_text = "\n".join(f"- {q.question_text}" for q in recent)

    if is_followup:
        user_prompt = f"""Generate a targeted FOLLOW-UP question probing a specific gap or concept.

Curriculum Context:
- Topic Title: {topic.title} (Day {topic.day}, Module {topic.module})
- Learning Objectives:
{objectives_text}
- Tools & Libraries: {tools_text}

Follow-up Target:
{followup_context}

Constraints:
- Target Difficulty: {difficulty_label} ({difficulty}/5)
- Question Intent: {topic.intent.value}
- Candidate Role: {role} ({tier.value} tier)

Recent Questions (do NOT duplicate):
{recent_questions_text if recent_questions_text else "None"}

Generate one concise, targeted follow-up question probing the candidate on the follow-up target."""

    else:
        user_prompt = f"""Generate a NEW technical interview question on the following curriculum topic.

Curriculum Context:
- Topic Title: {topic.title} (Day {topic.day}, Module {topic.module})
- Learning Objectives:
{objectives_text}
- Tools & Libraries: {tools_text}

Constraints:
- Target Difficulty: {difficulty_label} ({difficulty}/5)
- Question Intent: {topic.intent.value}
- Candidate Role: {role} ({tier.value} tier)

Recent Questions (do NOT duplicate):
{recent_questions_text if recent_questions_text else "None"}

Generate one realistic, natural technical question that tests the candidate's understanding of these objectives."""

    return system_prompt, user_prompt
