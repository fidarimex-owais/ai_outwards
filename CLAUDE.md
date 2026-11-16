# ai_outward

## Karpathy principles (apply to all work here)
1. **Think first** — state assumptions explicitly; surface tradeoffs instead of picking silently.
2. **Simplicity** — minimum code that solves the problem; no speculative config/flexibility.
3. **Surgical changes** — touch only what's needed; match existing style; don't "improve" adjacent code.
4. **Goal-driven** — define a verifiable success criterion (a test) before calling something done.

## Standing rules for this project
- One work unit at a time (a source file + the tests that must change with it). Stop after each and wait for "go."
- Run `python -m pytest -q` from `backend/` after every change. Show the diff and a plain-language explanation of what changed and what the output is.
- Comments say which file/function plays which role — not what the code obviously does.
- Never print, log, or echo an API key or `.env`/`.env.docker` contents.
- Never edit `.env` or `.env.docker` — the user edits those themselves.
- No live Gemini or Groq calls without explicit approval in-chat. Tests use fakes by default.
- Live tests are marked `@pytest.mark.live` and excluded by default (`pytest.ini`: `addopts = -m "not live"`). Run them on purpose with `python -m pytest -m live -q`.
- Mark anything you could not verify as UNVERIFIED. Do not guess.

## Windows / PowerShell
- Backend venv: `backend\.venv\Scripts\python.exe`
- Run tests: `cd backend; .venv\Scripts\python -m pytest -q`
- Run backend: `.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Run frontend: `cd frontend; npm run dev`

## Project facts
- Stack: FastAPI + Redis (session state) + MongoDB (submissions) backend; React+Vite frontend. Gemini (primary) + Groq (backup) via `LLMChain`, selectable with `LLM_PRIMARY_PROVIDER`.
- Default Gemini model is `gemini-3.1-flash-lite` (`GEMINI_MODEL`), not `gemini-3.8-flash` — the free tier caps `gemini-3.8-flash` at 20 requests/day vs. 500/day + 15/min for the Lite model.
- `gemini-3.5-flash-lite` was tried as an alternative and rejected: it returned a live `400 Bad Request` under this app's exact call shape (`thinking_config=ThinkingConfig(thinking_budget=0)`).
- OPEN: JWT_SECRET is still the placeholder (user deferred the fix). Never deploy or expose the backend until fixed; remove this line when it is fixed.
