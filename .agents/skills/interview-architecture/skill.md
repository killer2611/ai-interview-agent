---
name: interview-architecture
description: Designs and reviews the architecture of the AI Interview Agent, including candidate profiling, curriculum modeling, interview planning, session state, adaptive questioning, evaluation, coverage tracking, and evidence-based feedback. Use when designing, reviewing, refactoring, or extending the system architecture.
---

# Interview Architecture Skill

## Purpose

Design the Interview Agent as an adaptive AI system, not a scripted questionnaire.

The system must make explicit decisions about:

- what to ask
- why to ask it
- how to evaluate the answer
- whether to follow up
- whether to increase or decrease difficulty
- which curriculum areas remain uncovered
- what evidence supports the final feedback

## Architectural Principles

1. Treat curriculum.json as structured knowledge, not plain text.
2. Treat candidates.json as structured candidate-learning data.
3. Treat technical-spec.md as the API contract.
4. Separate planning, questioning, evaluation, adaptation, memory, and feedback.
5. Prefer deterministic business logic where possible.
6. Use the LLM for language generation and semantic judgment, not for basic state management.
7. Every question must have a reason.
8. Every follow-up must be based on the candidate's previous answer.
9. Every feedback claim should be traceable to interview evidence.
10. Avoid unnecessary multi-agent complexity.

## Core Pipeline

Candidate Profile
→ Profile Analysis
→ Interview Plan
→ Question Generation
→ Candidate Answer
→ Answer Evaluation
→ Difficulty Adaptation
→ Follow-up Decision
→ State Update
→ Next Question
→ Final Feedback

## Core Components

The architecture should maintain clear boundaries between:

- Curriculum Engine
- Profile Analyzer
- Interview Planner
- Question Generator
- Answer Evaluator
- Follow-up Engine
- Difficulty Manager
- Coverage Tracker
- Interview Memory
- Feedback Generator
- API Layer

## Interview State

Interview state should track at minimum:

- sessionId
- candidate profile
- interview plan
- question count
- asked questions
- covered curriculum days
- covered modules
- covered objectives
- conversation history
- current topic
- current difficulty
- answer evaluations
- strengths
- weaknesses
- evidence
- completion status

## Design Constraints

Never:

- hardcode candidate information
- invent curriculum topics
- replace the supplied API contract
- generate random questions unrelated to the candidate
- duplicate questions unnecessarily
- finish before minimum interview requirements are satisfied

Before major architectural changes, inspect the existing project structure and source-of-truth files first.