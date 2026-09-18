# Forge — Agentic Test Automation & PyTest Script Generator

Ingest a software requirement specification (Markdown or text). A three-agent LangGraph pipeline drafts structured test cases, compiles an executable PyTest suite, runs it in an isolated subprocess, and self-heals syntax/logic failures for up to three repair loops.

## Layout

```
/
  backend/          FastAPI + LangGraph + PyTest runner
  frontend/         Next.js 14 App Router workspace
  samples/          Example requirement specifications
```

## Backend

Python 3.11+. From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

The pipeline is fully offline when `LLM_PROVIDER=local` (default). Set `LLM_PROVIDER=openai` or `anthropic` and the matching API key to swap in LLM-backed architect/engineer/healer nodes. Invalid LLM output falls back to the deterministic synthesizer.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/generate-tests` | Run the full agent graph and return code, logs, metrics |
| `POST` | `/api/generate-tests/stream` | Same flow as SSE |
| `POST` | `/api/run-tests` | Re-execute stored or pasted suite sources |
| `GET`  | `/api/reports` | JSON + JUnit summaries |
| `GET`  | `/api/samples` | Bundled requirement specs |
| `GET`  | `/api/health` | Provider / liveness |

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Next.js rewrites `/api/*` to `http://127.0.0.1:8000`.

## Agents

1. **Test Architect** — parses the spec, emits typed cases (happy path, edge, failure, security, concurrency).
2. **Test Engineer** — writes `sut.py` plus a PyTest module with fixtures, mocks, and assertions.
3. **Execution & Self-Healing** — runs `pytest` in a tempdir sandbox; on failure, captures stdout/stderr and routes the traceback back to the engineer (max 3 loops).

Domain synthesizers currently specialize in telecom rate-limiters and wireless A3 handover controllers, with a generic specification engine for other documents.
