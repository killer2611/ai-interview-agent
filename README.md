# The Interview Agent

> **Build the Interviewer, Not the Interview.**
> An autonomous, adaptive AI technical interview platform that conducts realistic, personalized multi-turn interviews based on a candidate's learning journey and curriculum history.

---

## 📌 Problem Statement

Traditional technical interviews rely on static, generic question lists that fail to account for a candidate's specific background, past struggles, or learning trajectory. Standard AI interview tools either follow rigid pre-programmed scripts or hand complete control to an LLM, leading to unpredictable topic drift, hallucinated feedback, and ungrounded scoring. Technical hiring requires a system that maintains strict curriculum coverage and objective evaluation while dynamically adapting question framing, technical difficulty, and follow-ups based on live candidate responses.

---

## 💡 Solution Overview

**The Interview Agent** bridges structured curriculum knowledge and LLM intelligence. Built on a deterministic state machine architecture, the system ingests candidate learning signals (commit history, mission attempts, passed/failed/skipped days) to generate a personalized interview plan. 

During the interview, the central **Interview Controller** maintains complete state persistence, dynamically adjusts technical difficulty via a 3-turn sliding window, executes adaptive follow-ups on missing concepts, and enforces rigorous completion quality gates. Final feedback is grounded in verified candidate answer quotes traced to deterministic evidence IDs (`EVID-001`), ensuring 100% verifiable, hallucination-free technical assessments.

---

## 🔑 Key Features

- **Personalized Interview Planning**: Analyzes candidate commit history and mission records to generate scored, prioritized interview plans covering core AI engineering topics.
- **Precedence-Based Topic Scoring**: Evaluates candidate gaps using strict non-additive signal precedence (`failed > skipped > attempts >= 4 > attempts 3 > attempts 2`).
- **Learning-Signal Starting Difficulty**: Technical starting difficulty (1–5) is derived **solely** from learning signals (`first_try_ratio`, `engagement_ratio`). Years of experience guide question framing and communication expectations without mathematically inflating difficulty.
- **Adaptive Follow-up Engine**: Probes deeper on strong answers (+1 difficulty), scaffolds weak answers (-1 difficulty), or probes missing concepts on partial answers.
- **5-Check Post-Generation Validation**: Validates every LLM question against topic match, conceptual anchors, single question constraint, deduplication, and difficulty plausibility before presenting to the candidate.
- **Evidence-Grounded Feedback**: Traces every feedback claim to verified exact candidate answer quotes (`candidate_quote`). Unverified LLM quotes are automatically discarded.
- **Skipped vs. Gap Distinction**: Skipped curriculum missions are listed as unassessed study recommendations in `next[]`, NEVER as demonstrated weaknesses in `gaps[]`.
- **Zero-Dependency Production Architecture**: Built with FastAPI, Pydantic v2, and standard Python libraries — no heavy agent frameworks, vector databases, or complex infrastructure required.
- **Same-Origin Single-Package Deployment**: Frontend and API served from the same FastAPI origin, avoiding cross-origin deployment complexity.

---

## 🛠️ System Architecture

```
                                  ┌───────────────────────────┐
                                  │   candidates.json /       │
                                  │   curriculum.json         │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
┌──────────────────┐               ┌───────────────────────────┐
│   Web Frontend   │◄── Same Origin ──► POST /api/interview    │
│ (FastAPI Static) │               └─────────────┬─────────────┘
└──────────────────┘                             │
                                                 ▼
                                   ┌───────────────────────────┐
                                   │    InterviewController    │
                                   │ (Central State Coordinator)│
                                   └──────┬───┬───┬───┬───┬────┘
                                          │   │   │   │   │
                  ┌───────────────────────┘   │   │   │   └───────────────────────┐
                  ▼                           ▼   │   ▼                           ▼
       ┌────────────────────┐   ┌───────────────┐ │ ┌───────────────────┐   ┌───────────────────┐
       │  ProfileAnalyzer   │   │InterviewPlanner│ │ │ QuestionGenerator │   │  AnswerEvaluator  │
       │ & DifficultyMgr    │   │ & TopicScorer │ │ │(5-Check Validator)│   │ (7-Dimension Scale│
       └────────────────────┘   └───────────────┘ │ └───────────────────┘   └───────────────────┘
                                                  ▼
                                       ┌─────────────────────┐
                                       │  EvidenceVerifier   │
                                       │ (Exact Quote Match) │
                                       └─────────────────────┘
```

---

## 💻 Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`
- **LLM Provider**: OpenAI-compatible client SDK (supports OpenAI GPT-4o-mini, Groq, Ollama, vLLM)
- **Frontend**: Vanilla HTML5, CSS3 (Dark Slate Theme), ES6 JavaScript served directly via FastAPI `StaticFiles`
- **Testing**: `pytest`, `pytest-asyncio`, `httpx`

---

## ⚙️ Environment Variables & LLM Provider Configuration

The LLM provider abstraction uses standard OpenAI-compatible environment variables configured via `pydantic-settings`:

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | Your OpenAI-compatible API key for LLM calls | `your-api-key-here` |
| `OPENAI_BASE_URL` | Base URL for LLM provider API | `https://api.openai.com/v1` |
| `LLM_MODEL` | Target model name | `gpt-4o-mini` |
| `LLM_TEMPERATURE_QUESTION` | Temperature for question generation | `0.7` |
| `LLM_TEMPERATURE_EVALUATION` | Temperature for answer evaluation | `0.2` |
| `LLM_TEMPERATURE_FEEDBACK` | Temperature for feedback synthesis | `0.3` |
| `LLM_MAX_RETRIES` | Bounded retries for failed LLM calls | `2` |
| `LLM_TIMEOUT_SECONDS` | Timeout in seconds per LLM call | `30` |

> [!NOTE]
> **Important Credential Distinction**:
> - **LLM Provider Credentials** (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`) are used exclusively for question generation, answer evaluation, and feedback generation.
> - **Breeth Credentials**: Breeth integration is not required for the core interview runtime in the current submission. Breeth credentials (`ck_live_...`) must **NOT** be placed into `OPENAI_API_KEY`.

---

## 🚀 Quickstart & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/killer2611/ai-interview-agent.git
cd ai-interview-agent
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure your OpenAI-compatible API key:
```bash
cp .env.example .env
```

### 4. Run the Application Server
```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
Open your browser and navigate to **`http://localhost:8000/`** to launch the interactive demo.

---

## 🧪 Running Tests

Run the complete test suite:
```bash
pytest tests/
```
Output:
```
collected 40 items

tests/test_phase1.py .......                                             [ 17%]
tests/test_phase2.py ........                                            [ 38%]
tests/test_phase3.py ...........                                         [ 66%]
tests/test_phase4.py .........                                           [ 89%]
tests/test_phase5.py ....                                                [ 97%]
tests/test_phase6.py .                                                   [100%]

======================== 40 passed, 1 warning in 1.31s ========================
```

---

## 🌐 API Contract Reference

### 1. `POST /api/interview`

#### Mode A: Initialization Request
```json
{
  "sessionId": "session-1723200000",
  "candidate": {
    "member": {
      "id": "CAND-001",
      "name": "Sarah Johnson",
      "jobRole": "Senior Data Engineer",
      "yearsExperience": 9,
      "education": "Master's Computer Science",
      "status": "COMPLETED"
    },
    "missions": [ ... ],
    "signals": { "commitDays": 28, "missionsCompleted": 30, "missionsFirstTry": 20 }
  }
}
```
**Response**:
```json
{
  "reply": "Welcome, Sarah Johnson. Thank you for joining this technical interview...\n\nWhen building dense vector representations, how do you handle token length limits?",
  "done": false,
  "feedback": null
}
```

#### Mode B: Turn Response Request
```json
{
  "sessionId": "session-1723200000",
  "message": "Vector embeddings map raw text tokens into dense continuous numerical vectors representing deep semantic context."
}
```

#### Mode C: Interview Completion Response (`done: true`)
```json
{
  "reply": "Thank you, Sarah Johnson. That concludes our technical interview.",
  "done": true,
  "feedback": {
    "summary": "Sarah Johnson completed a 12-question technical interview covering 5 curriculum days across 3 modules.",
    "strengths": [
      "Demonstrated strong understanding of Sentence Transformers vector space representation"
    ],
    "gaps": [
      "Struggled with HNSW graph construction trade-offs under high write workloads"
    ],
    "next": [
      "Focus on strengthening technical areas identified during interview.",
      "Review unassessed topic (Day 29: Monitoring, Logging & Observability)"
    ]
  }
}
```

### 2. `GET /api/candidates`
Returns the list of candidate profiles from `candidates.json` for selection in the frontend UI.

### 3. `GET /health`
Exposes system operational status, curriculum load state, and active session count.

---

## ☁️ Deployment Instructions

The application is configured for deployment on cloud platforms such as Render, Railway, or AWS App Runner.

### Same-Origin Architecture
The deployed FastAPI application serves both the backend API and the static web frontend from the **same origin**. This eliminates cross-origin request issues and complex CORS configurations.

### Deploying to Render
1. Push your repository to GitHub: `https://github.com/killer2611/ai-interview-agent`
2. Create a new **Web Service** on Render connected to your repository.
3. Render detects `render.yaml` or set:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables in your Render dashboard:
   - `OPENAI_API_KEY`: Your OpenAI-compatible API key for live AI generation
   - `OPENAI_BASE_URL`: `https://api.openai.com/v1`
   - `LLM_MODEL`: `gpt-4o-mini`

---

## 🏆 Hackathon Context

This project was built for **The Interview Agent Hackathon** adhering strictly to the source-of-truth requirements in `curriculum.json`, `candidates.json`, and `technical-spec.md`.
