"""Prompt templates for LLM Answer Evaluation (Call Site 2).

Instructs the LLM to score the 7 rubric dimensions, extract demonstrated/missing concepts,
identify misconceptions, extract exact evidence quotes, and provide follow-up signals.
"""

from __future__ import annotations

from src.models.curriculum import DayEntry


def build_evaluation_prompt(
    question_text: str,
    answer_text: str,
    day_entry: DayEntry,
    question_index: int,
) -> tuple[str, str]:
    """Build system and user prompts for answer evaluation.

    Args:
        question_text: The question asked.
        answer_text: Candidate's answer text.
        day_entry: Curriculum day context.
        question_index: 0-indexed question count.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    objectives_text = "\n".join(f"- {obj}" for obj in day_entry.objectives)
    tools_text = ", ".join(day_entry.tools) if day_entry.tools else "None specified"

    system_prompt = """You are an expert technical evaluator scoring a candidate's response in a technical interview.

Score each dimension on a 1 to 5 scale:
1 = Poor / Incorrect / Non-existent
2 = Below Average / Partial / Significant gaps
3 = Satisfactory / Adequate understanding
4 = Above Average / Strong technical grasp
5 = Exceptional / Deep expert insight

Rubric Dimensions:
1. correctness: Technical accuracy of facts, formulas, APIs, and logic.
2. completeness: Coverage of the core requirements posed by the question.
3. depth: Level of technical nuance, architectural understanding, or edge cases.
4. reasoning: Explanation of 'why' choices were made, trade-offs, or underlying mechanics.
5. terminology: Accurate and natural usage of domain-specific technical terms.
6. communication: Structure, clarity, and coherence of the explanation.
7. confidence: Appropriate certainty without overconfidence or hesitancy.

Evidence Quote Rules:
- `evidence_quote` MUST be an EXACT VERBATIM SUBSTRING extracted directly from the Candidate's Answer text.
- Do NOT paraphrase, summarize, edit, or fabricate the quote.
- If no single representative quote exists, pick a short 5-15 word exact phrase from the candidate's answer.
- If the candidate provided no substantive content, return an empty string "" for evidence_quote.

Respond strictly with ONLY a JSON object matching the requested schema."""

    user_prompt = f"""Evaluate the candidate's response below against the curriculum context.

## Question Asked (Day {day_entry.day}: {day_entry.title})
{question_text}

## Candidate's Answer
{answer_text}

## Curriculum Context
Learning Objectives:
{objectives_text}
Tools & Technologies: {tools_text}

Provide structured evaluation scoring all 7 dimensions, identifying demonstrated concepts, missing concepts, misconceptions, exact evidence quote, and a suggested follow-up focus."""

    return system_prompt, user_prompt
