# Forge — Agentic Test Automation & PyTest Script Generator

Ingest a software requirement specification. The in-browser pipeline drafts structured test cases, compiles an executable PyTest suite, and plays back a pytest-style execution log. Domain synthesizers cover telecom rate-limiters, wireless A3 handover, and a generic specification engine.

This demo runs entirely in the frontend — no API server required.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Click **Generate suite**.

## Deploy (Vercel)

1. Import the GitHub repo.
2. Set **Root Directory** to `frontend`.
3. Deploy. No environment variables needed.

## Agents

1. **Test Architect** — parses the spec, emits typed cases (happy path, edge, failure, security, concurrency).
2. **Test Engineer** — writes `sut.py` plus a PyTest module with fixtures, mocks, and assertions.
3. **Execution** — collects generated tests and shows a pytest-style pass log.
4. **Self-Healing** — reserved for repair loops; skipped when the suite is clean.
