---
name: verification
description: Verifies the Interview Agent through tests, API checks, runtime validation, and targeted debugging after implementation changes. Use after implementing features, fixing bugs, refactoring code, or preparing a demo.
---

# Verification Skill

## Principle

Never assume code works because it was generated successfully.

Implementation must be verified.

## Verification Loop

After meaningful changes:

1. Inspect the affected files.
2. Run relevant tests.
3. Run static/type checks when available.
4. Start the application when appropriate.
5. Exercise the affected API or feature.
6. Inspect failures.
7. Fix the root cause.
8. Re-run verification.

## Interview API Verification

Verify:

POST /api/interview

Test:

1. New session with candidate object.
2. Response contains reply and done.
3. Follow-up request using same sessionId.
4. Previous conversation affects the next question.
5. Interview reaches at least 8 questions.
6. At least 4 curriculum days are covered.
7. Final response contains:
   - done=true
   - feedback.summary
   - feedback.strengths
   - feedback.gaps
   - feedback.next

## Data Integrity

Verify that:

- candidate data comes from candidates.json
- curriculum data comes from curriculum.json
- API behavior matches technical-spec.md
- skipped topics are handled correctly
- no candidate information is invented

## Regression

After fixing a bug, rerun the relevant tests and any affected integration tests.

## Reporting

When reporting completion, distinguish:

- implemented
- tested
- not tested
- known limitations

Never claim successful verification without actually performing it.