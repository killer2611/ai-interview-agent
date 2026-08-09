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

    system_prompt = f"""You are an experienced lead technical interviewer conducting a live technical interview with {name}, a candidate for {role} ({tier.value} tier).

Your goal is to generate ONE realistic, conversational, and technically insightful interview question.

STRICT GENERATION RULES:
1. Return ONLY the final candidate-facing question text inside the requested JSON schema `question_text`.
2. Do NOT include any internal meta-instructions, prompt labels, directives, or strategy phrases.
3. NEVER output phrases like "Simplify the question", "Test foundational prerequisite understanding", "Probe the specific missing aspect", "missing details", "specially regarding", "follow-up strategy", or "internal directive".
4. Do NOT restate curriculum titles robotically (e.g. NEVER ask "How would you design the system architecture incorporating <Title>?").
5. Frame the question naturally as a live technical inquiry suitable for a {role}.
6. Ask exactly ONE question. Do not ask multiple questions or sub-questions.
7. Keep the question concise (1 to 3 sentences maximum)."""

    objectives_text = "\n".join(f"- {obj}" for obj in topic.objectives)
    tools_text = ", ".join(topic.tools) if topic.tools else "Standard Python/AI stack"

    recent_questions_text = ""
    if state.asked_questions:
        recent = state.asked_questions[-4:]
        recent_questions_text = "\n".join(f"- {q.question_text}" for q in recent)

    if is_followup:
        clean_target = followup_context.strip() if followup_context else "core technical trade-offs and edge cases"
        user_prompt = f"""Generate a targeted FOLLOW-UP interview question on {topic.title}.

Target Concept to Probe:
{clean_target}

Curriculum Context:
- Topic: {topic.title}
- Key Objectives:
{objectives_text}
- Technologies: {tools_text}
- Target Difficulty: {difficulty_label} ({difficulty}/5)

Recent Questions (do NOT repeat):
{recent_questions_text if recent_questions_text else "None"}

Generate one natural follow-up question probing the target concept."""

    else:
        user_prompt = f"""Generate a NEW technical interview question on {topic.title}.

Curriculum Context:
- Topic: {topic.title}
- Key Objectives:
{objectives_text}
- Technologies: {tools_text}
- Target Difficulty: {difficulty_label} ({difficulty}/5)

Recent Questions (do NOT repeat):
{recent_questions_text if recent_questions_text else "None"}

Generate one natural, realistic technical question testing the candidate's understanding of these objectives."""

    return system_prompt, user_prompt
