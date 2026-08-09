# PROMPTS.md — AI Development Log

This document records the prompt progression and AI-assisted pair-programming trajectory used to build **The Interview Agent** across its architectural and implementation phases.

---

## 🏛️ Architecture Phase

### Prompt 1: System Inspection & Requirements Analysis
> "You are the lead AI systems architect for this hackathon project. Do NOT write, modify, delete, rename, or generate application code. Completely inspect curriculum.json, candidates.json, technical-spec.md, and workspace rules. Propose a complete system architecture for 'The Interview Agent' following 5 core principles: curriculum as structured knowledge, candidate personalization, rubric evaluation, state persistence, and adaptive follow-up."

### Prompt 2: State Model & Failure Mode Design
> "Analyze candidate profiles, state schemas, and system failure modes. Define the deterministic state model `InterviewState`, missing concept tracking, evidence verification rules, and coverage quality gates. Ensure the LLM does NOT make state transition decisions."

### Prompt 3: Architecture Hardening (Revision 3)
> "Incorporate six hardening rules into Revision 3 Architecture:
> 1. Mutually exclusive precedence-based gap signals (`failed > skipped > attempts >= 4 > attempts 3 > attempts 2 > none`).
> 2. Starting technical difficulty derived SOLELY from learning signals (`first_try_ratio`, `engagement_ratio`).
> 3. Evidence verification exact substring match policy (discard unverified quotes).
> 4. Deterministic `evidence_id` assignment (`EVID-001`).
> 5. Meaningful coverage logic (requires substantive evaluated answer; 'I don't know' alone does not count).
> 6. 5-check post-generation question validation."

---

## 📦 Phase 1: Foundation (Models, Config, Services, FastAPI Stub)

### Prompt
> "Implement Phase 1 of the frozen Revision 3 architecture ONLY.
> Scope: Pydantic models (candidate, curriculum, evaluation, feedback, interview state, API schemas), config/settings, curriculum engine (O(1) index), in-memory session store, LLM provider abstraction, minimal FastAPI app stub, and requirements.txt.
> Test requirements: Verify curriculum loading, session CRUD, candidate parsing, config loading, and FastAPI `/health` endpoint."

---

## 📊 Phase 2: Candidate Analysis & Topic Scoring

### Prompt
> "Implement Phase 2 of the frozen Revision 3 architecture ONLY.
> Scope: Profile Analyzer, precedence-based Topic Scorer, Interview Planner, Coverage Tracker, Difficulty Manager.
> Rules:
> - `failed > skipped > attempts >= 4 > 3 > 2 > none` (first match only, NOT additive).
> - Skipped is unassessed/not completed.
> - Starting technical difficulty derived SOLELY from learning signals (yearsExperience ignored).
> - Plan must support >=8 topics, >=4 curriculum days across >=2 modules.
> - Meaningful coverage requires a substantive evaluated answer; 'I don't know' alone does not count.
> Unit tests: Focused unit tests for candidate analysis, precedence gap scoring, skipped vs failed, starting difficulty, meaningful coverage, and plan constraints."

---

## 🔄 Phase 3: Interview Controller & Adaptive Loop

### Prompt
> "Implement Phase 3 of the frozen Revision 3 architecture ONLY.
> Scope: Interview Controller, adaptive interview loop, session continuation, follow-up decision logic, next-topic selection, completion integration, deterministic adaptive trace (`decision_trace`).
> Rules:
> - Interview Controller is single owner of next-action decisions.
> - Follow-up vs new-topic selection is deterministic.
> - Record `AdaptiveTraceEntry` for every decision.
> - Never repeat an asked question.
> - Enforce completion gate (>=8 questions, >=4 meaningful days, >=2 modules).
> Testing: Focused tests covering init, turn continuation, persistence, follow-ups, transitions, deduplication, trace recording, and safety limits."

---

## 🧠 Phase 4: Structured LLM Question Generation & Answer Evaluation

### Prompt
> "Implement Phase 4 of the frozen Revision 3 architecture ONLY.
> Scope: Structured LLM Question Generation (`_LLMQuestionResponse`), Structured LLM Answer Evaluation (`_LLMEvaluationResponse`), prompt templates, 5-check question validation, exact quote verification, and deterministic IDK short-circuiting.
> Rules:
> - Controller provides deterministic metadata (day, module, objectives, intent, difficulty).
> - LLM generates natural interview questions (NO title-restatement).
> - 5 post-generation validation checks: topic match, conceptual anchor, single question, dedup, plausibility.
> - Evidence quotes MUST be exact substrings of candidate answer; unverified quotes cleared to `""`.
> - 'I don't know' handled deterministically without calling LLM.
> Testing: Focused unit tests covering valid question generation, fallbacks, topic validation, deduplication, follow-ups, answer evaluation, exact quote verification, quote discard, and IDK handling."

---

## 📋 Phase 5: Feedback Generator & End-to-End API Integration

### Prompt
> "Implement Phase 5 of the frozen Revision 3 architecture ONLY.
> Scope: Feedback Generator, Call Site 3 LLM feedback generation, evidence-grounded claims (`evidence_ids`), unsupported claim rejection, skipped vs gap handling, completion integration, and exact API contract (`technical-spec.md`).
> Rules:
> - Every strength/gap claim must reference verified `evidence_ids`.
> - Claims with zero verified evidence IDs are stripped.
> - Skipped curriculum topics go to `next[]` study recommendations, NEVER `gaps[]`.
> - Public API response MUST match `technical-spec.md` (`summary`, `strengths: string[]`, `gaps: string[]`, `next: string[]`) without exposing internal decision traces or evidence IDs.
> Testing: End-to-end integration tests for feedback generation, evidence traceability, unsupported claim rejection, skipped handling, and API response contract."

---

## 🎨 Phase 6: Demo Frontend & UX

### Prompt
> "Implement Phase 6: lightweight demo frontend and UX ONLY.
> Scope: Single-page Web UI (`index.html`, `style.css`, `app.js`) supporting candidate selection, active conversational chat, typing indicators, question progress tracking, and structured feedback display.
> Rules:
> - Dark slate technical interview theme (`#0f172a`), Inter typography, glassmorphic cards.
> - Connects to `POST /api/interview` and `GET /api/candidates`.
> - No authentication, no new frameworks, no persistent user accounts.
> Testing: Serve static files via FastAPI StaticFiles, add integration test for static assets and candidates endpoint."

---

## 🛡️ Phase 7: Final Hardening, Security Scan & Submission Packaging

### Prompt
> "Implement PHASE 7 — FINAL HARDENING, DEPLOYMENT PREPARATION & SUBMISSION PACKAGING.
> Scope:
> - Add CORSMiddleware to FastAPI app.
> - Repository-wide security scan for API keys, passwords, credentials, and Breeth tokens.
> - Verify `.gitignore`, `.env.example`, `Procfile`, and `render.yaml`.
> - Create comprehensive, judge-friendly `README.md`.
> - Create `PROMPTS.md` documenting vibe-coded development trajectory.
> - Run full 40-test suite across all phases."

---

## 🐛 Key Debugging & Refinement Prompts

### LLM Provider Offline Fail-Fast Optimization
> "Ensure `LLMProvider.generate_text` and `generate_structured` fail fast when `OPENAI_API_KEY` is dummy or missing, avoiding 150-second test suite timeouts and falling back instantly to deterministic template fallbacks."

### Template Fallback Deduplication Fix
> "Update `QuestionGenerator._get_template_fallback` to incorporate `is_followup` and `followup_context` so fallback questions generated during follow-up turns on the same topic produce distinct, non-duplicate strings."

### Evidence Verifier Index Guard
> "Ensure `EvidenceVerifier.verify_and_record_evidence` computes `max(0, state.question_count - 1)` so unit tests operating on uninitialized question states do not trigger Pydantic `question_index >= 0` validation errors."
