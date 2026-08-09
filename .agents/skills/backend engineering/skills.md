---
name: backend-engineering
description: Builds and reviews the Interview Agent backend using clean Python, FastAPI, Pydantic, modular services, validation, error handling, and testable architecture. Use when implementing or modifying backend APIs and services.
---

# Backend Engineering Skill

## Architecture

Prefer modular service boundaries over one large application file.

Separate:

- API routes
- models
- business logic
- LLM integration
- interview state
- configuration
- testing

## FastAPI

Follow production-quality FastAPI conventions.

Use:

- typed request models
- typed response models
- dependency injection where useful
- clear HTTP status codes
- validation
- structured errors
- async operations when appropriate

## Pydantic

Use Pydantic models for:

- candidate data
- curriculum structures
- interview requests
- interview responses
- interview state
- evaluations
- feedback

Avoid untyped dictionaries when a stable schema exists.

## API Contract

Preserve:

POST /api/interview

The implementation must support:

- sessionId
- initial candidate object
- subsequent candidate messages
- conversational state
- done
- final feedback

Do not silently change the supplied technical specification.

## LLM Boundary

Keep LLM calls isolated behind service interfaces.

Do not scatter model calls throughout API routes.

## Configuration

Use environment variables for:

- API keys
- model configuration
- deployment settings

Never hardcode secrets.

## Error Handling

Handle:

- invalid requests
- missing sessions
- malformed candidate data
- LLM failures
- timeouts
- unexpected model output

Return useful errors without leaking secrets.

## Maintainability

Prefer:

- small functions
- explicit types
- descriptive names
- testable services
- minimal global state

Avoid unnecessary frameworks and abstractions.