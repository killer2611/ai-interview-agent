"""Prompt templates for LLM Feedback Generation (Call Site 3).

Instructs the LLM to synthesize verified evidence into actionable candidate feedback,
enforcing evidence_id traceability and distinguishing unassessed topics from demonstrated gaps.
"""

from __future__ import annotations

from src.models.interview import InterviewState


def build_feedback_prompt(state: InterviewState) -> tuple[str, str]:
    """Build system and user prompts for synthesizing evidence-grounded feedback.

    Args:
        state: Complete interview state containing verified evidence lists.

    Returns:
        Tuple of (system_prompt, user_prompt).
    """
    candidate_name = state.candidate.member.name
    job_role = state.candidate.member.jobRole
    tier = state.profile_analysis.tier.value

    system_prompt = f"""You are a lead technical interviewer writing a final evaluation report for {candidate_name}, a candidate for {job_role} ({tier} tier).

Your task is to synthesize the verified interview evidence into constructive, evidence-backed technical feedback.

CRITICAL RULES FOR EVIDENCE TRACEABILITY:
1. Every item in `strengths` MUST include the exact `evidence_ids` from the verified strength evidence provided.
2. Every item in `gaps` MUST include the exact `evidence_ids` from the verified gap evidence provided.
3. NEVER claim a strength or gap unless supported by at least one provided evidence ID.
4. Do NOT classify skipped or unassessed curriculum topics as demonstrated gaps. Unassessed topics must be listed in `next` as recommended study areas.
5. Provide 2 to 4 actionable, specific items in `next` tying back to observed gaps and unassessed topics.

Respond strictly with ONLY a JSON object matching the requested schema."""

    # Format verified evidence lists
    strengths_text = ""
    if state.strengths_evidence:
        strengths_text = "\n".join(
            f"- [{e.evidence_id}] Day {e.day} ({e.topic}): {e.claim} (Quote: \"{e.candidate_quote}\")"
            for e in state.strengths_evidence if e.is_verified
        )
    if not strengths_text:
        strengths_text = "No specific verified strength evidence recorded."

    gaps_text = ""
    if state.weaknesses_evidence:
        gaps_text = "\n".join(
            f"- [{e.evidence_id}] Day {e.day} ({e.topic}): {e.claim} (Quote: \"{e.candidate_quote}\")"
            for e in state.weaknesses_evidence if e.is_verified
        )
    if not gaps_text:
        gaps_text = "No specific verified gap evidence recorded."

    unassessed_text = ""
    if state.unassessed_topics:
        unassessed_text = "\n".join(f"- {topic}" for topic in state.unassessed_topics)

    user_prompt = f"""Synthesize final technical feedback for {candidate_name}.

## Candidate Profile
- Role: {job_role}
- Experience Tier: {tier}
- Questions Answered: {state.question_count}
- Meaningfully Covered Days: {sorted(list(state.meaningfully_covered_days))}

## Verified Demonstrated Strength Evidence (use these IDs in strengths):
{strengths_text}

## Verified Demonstrated Gap Evidence (use these IDs in gaps):
{gaps_text}

## Unassessed / Skipped Curriculum Topics (place study recommendations in next, NOT gaps):
{unassessed_text if unassessed_text else "None"}

Generate a summary, evidence-grounded strengths, evidence-grounded gaps, and next step recommendations."""

    return system_prompt, user_prompt
