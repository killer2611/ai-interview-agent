---
name: adaptive-interview
description: Implements and reviews the adaptive interviewing behavior of the AI Interview Agent, including candidate personalization, interview planning, question generation, answer evaluation, follow-ups, difficulty adaptation, curriculum coverage, and evidence collection. Use when building or modifying interview behavior.
---

# Adaptive Interview Skill

## Goal

Make the Interview Agent behave like an experienced technical interviewer rather than a fixed questionnaire.

## Personalization

Build the interview around:

- candidate job role
- years of experience
- completed missions
- skipped topics
- failed missions
- attempts
- learning signals

Prefer deeper questions for experienced candidates.

Prefer foundational questions for junior candidates.

Do not treat all candidates identically.

## Interview Planning

Create an interview plan before the interview begins.

The plan should specify:

- curriculum days
- modules
- objectives
- question intent
- initial difficulty
- expected follow-up areas

The plan must satisfy:

- at least 8 questions
- at least 4 curriculum days
- meaningful curriculum coverage

The plan may change dynamically based on candidate performance.

## Question Generation

Questions should test:

- conceptual understanding
- reasoning
- implementation
- tradeoffs
- architecture
- debugging
- production thinking

Prefer questions such as:

- Why?
- How?
- What tradeoff?
- What would happen if?
- How would you debug this?
- How would you productionize this?

Avoid relying primarily on definition questions.

## Adaptive Follow-ups

After every candidate answer:

1. Evaluate the answer.
2. Identify missing or incorrect concepts.
3. Decide whether a follow-up is useful.
4. Generate a targeted follow-up when appropriate.
5. Update interview state.
6. Select the next topic or increase/decrease difficulty.

Strong answer:

→ increase depth or difficulty.

Partial answer:

→ probe the missing concept.

Weak answer:

→ simplify and test the prerequisite concept.

Never ask a generic follow-up that ignores the candidate's answer.

## Evaluation Dimensions

Evaluate:

- correctness
- completeness
- depth
- reasoning
- technical terminology
- communication
- confidence

The evaluation should influence the next question.

## Difficulty

Difficulty should adapt continuously.

Increase difficulty after consistently strong performance.

Maintain difficulty after mixed performance.

Decrease difficulty after repeated weak performance.

Do not punish a candidate with unnecessarily difficult questions.

## Coverage

Track:

- curriculum days
- modules
- objectives
- question count

Avoid repeated coverage unless repetition is deliberately used as a diagnostic follow-up.

## Evidence

Record evidence supporting:

- strengths
- weaknesses
- topic mastery
- knowledge gaps

Final feedback must be derived from this evidence.

## Conversational Behavior

The interviewer should:

- acknowledge answers naturally
- ask one meaningful question at a time
- avoid revealing evaluation scores during the interview unless intentionally designed
- reference previous answers when useful
- maintain a professional technical-interview tone