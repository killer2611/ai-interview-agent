"""Evidence Verifier — verifies evidence quotes against candidate answers (v3 spec).

Rules:
- Confirm every candidate_quote is an EXACT SUBSTRING of actual_answer.
- If NOT an exact substring: DISCARD quote (set candidate_quote=""), set is_verified=False.
- Assign deterministic evidence_id: EVID-001, EVID-002, etc.
- No fabricated fallback excerpts!
"""

from __future__ import annotations

from src.models.evaluation import AnswerEvaluation, AnswerStrength, Evidence
from src.models.interview import InterviewState


class EvidenceVerifier:
    """Verifies candidate quote evidence spans and manages evidence IDs."""

    @staticmethod
    def verify_and_record_evidence(
        evaluation: AnswerEvaluation,
        actual_answer: str,
        state: InterviewState,
    ) -> Evidence | None:
        """Verify the raw candidate quote from an evaluation and record evidence in state.

        Args:
            evaluation: Raw evaluation from AnswerEvaluator.
            actual_answer: Candidate's actual raw answer text.
            state: Current interview state.

        Returns:
            Recorded Evidence object or None if answer was non-substantive.
        """
        if state.current_question is None:
            return None

        # Check exact substring match
        raw_quote = evaluation.evidence_quote.strip()
        if raw_quote and raw_quote in actual_answer:
            candidate_quote = raw_quote
            is_verified = True
        else:
            # DISCARD unverified quote — no fabricated excerpt per v3 spec
            candidate_quote = ""
            is_verified = False

        state.evidence_counter += 1
        evidence_id = f"EVID-{state.evidence_counter:03d}"

        day = state.current_question.day
        module = state.current_question.module
        topic = state.current_question.tools[0] if state.current_question.tools else f"Day {day}"

        # Generate claim text
        if evaluation.strength.value == "strong":
            claim = f"Demonstrated strong understanding of {topic}"
        elif evaluation.strength.value == "partial":
            concepts = ", ".join(evaluation.key_concepts_demonstrated[:2]) if evaluation.key_concepts_demonstrated else "core concepts"
            claim = f"Demonstrated partial understanding of {topic} ({concepts})"
        else:
            gaps = ", ".join(evaluation.missing_concepts[:2]) if evaluation.missing_concepts else "key concepts"
            claim = f"Struggled with {topic} (gaps in {gaps})"

        q_idx = max(0, state.question_count - 1)
        evidence = Evidence(
            evidence_id=evidence_id,
            question_index=q_idx,
            day=day,
            module=module,
            topic=topic,
            claim=claim,
            candidate_quote=candidate_quote,
            evaluation_strength=evaluation.strength,
            is_verified=is_verified,
        )


        if evaluation.strength == AnswerStrength.STRONG:
            state.strengths_evidence.append(evidence)
        elif evaluation.strength == AnswerStrength.WEAK:
            state.weaknesses_evidence.append(evidence)
        else:  # PARTIAL
            state.strengths_evidence.append(evidence)

        return evidence
