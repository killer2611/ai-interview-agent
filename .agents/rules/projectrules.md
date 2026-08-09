---
trigger: always_on
---

# AI Interview Agent — Project Rules

## Source of Truth

The following files are authoritative:

- @curriculum.json
- @candidates.json
- @technical-spec.md

Do not invent, rewrite, or silently replace their contents.

## Curriculum

Treat curriculum.json as structured data.

Use its:

- modules
- days
- titles
- objectives
- tools

to drive interview planning and question generation.

Do not invent curriculum days or topics.

## Candidates

Treat candidates.json as the source of candidate information.

Use:

- job role
- experience
- completed missions
- skipped missions
- failed missions
- attempts
- learning signals

for personalization.

Never fabricate candidate history.

## API Contract

technical-spec.md defines the required API.

Preserve:

POST /api/interview

and its sessionId-based conversational state.

Do not change the required response structure without explicit approval.

## Architecture

Prefer modular services.

Keep separate concerns for:

- curriculum
- candidate analysis
- interview planning
- question generation
- evaluation
- adaptation
- memory
- feedback
- API

Do not create unnecessary autonomous agents.

## AI Behavior

Every interview question must have a purpose.

Every follow-up should be based on the candidate's previous response.

Every final feedback claim should have supporting interview evidence.

## Engineering

Use:

- Python
- FastAPI
- Pydantic
- typed interfaces
- modular services
- environment variables for secrets

Avoid hardcoded secrets.

## Verification

Do not claim that functionality works without testing it.

After meaningful changes, run appropriate tests or API checks.

## Safety

Do not execute destructive commands without explicit approval.

Do not delete project files unless explicitly requested.

Do not expose API keys or credentials.

## Change Management

Before major architectural changes:

1. inspect the existing implementation
2. inspect relevant source-of-truth files
3. explain the proposed change
4. implement
5. verify