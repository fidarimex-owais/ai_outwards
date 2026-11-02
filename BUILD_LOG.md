# Build Log — Voice Data Collection Assistant

This file documents what was built, in what order, and why. Files/folders are created only when a step actually needs them — nothing is scaffolded ahead of time.

Project root: `ai_outward/backend/`

## Architecture Reference

HLD: Frontend → API Gateway/Auth → Speech-to-Text → Input Guardrail → Dialogue Manager (Redis) → MSI Router (Python rules → Gemini → Backup LLM) → Validate → Total → Summary → Confirm → Save (MongoDB).

Stack: FastAPI, MongoDB (pymongo), Redis, Gemini (primary LLM) + backup LLM provider, JWT auth.

---

## Step 1 — Project Setup + Config

**What:** Minimal backend project: dependency list, env files, and the one module with actual logic so far — settings loading.

**Why:** Every later piece (Mongo client, Redis client, LLM clients) needs config values, so this is the first real dependency in the chain.

**Files added:**
```
backend/
├── requirements.txt
├── .env.example
├── .env              (gitignored, copied from .env.example)
├── .gitignore
└── app/
    ├── __init__.py
    └── core/
        ├── __init__.py
        └── config.py   # Settings class (pydantic-settings), reads .env
```

**Dependency notes (reflected in `requirements.txt`):**
- `google-genai==2.33.0` — not an older `0.x`, which is yanked (Pillow CVE-2026-54058)
- `mongomock==4.1.2` — `4.2.0` requires Python ≥3.11; this environment runs Python 3.10
- Most other packages use floors (`>=`) rather than exact pins, since `google-genai` pulls in newer `pydantic`/`httpx` than an exact pin would allow

**Resolved versions (`pip freeze` after install):**
```
fastapi==0.115.0          uvicorn==0.32.0           pydantic==2.14.2
pydantic-settings==2.6.0  pymongo==4.10.1           redis==5.1.1
google-genai==2.33.0      python-jose==3.3.0        passlib==1.7.4
python-multipart==0.0.12  pytest==8.3.3             pytest-asyncio==0.24.0
httpx==0.28.1             fakeredis==2.26.1         mongomock==4.1.2
```

**How to verify:**
```
cd backend
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env
./.venv/Scripts/python.exe -c "from app.core.config import settings; print(settings.mongo_url)"
```
Confirmed working — prints `mongodb://localhost:27017`.

**Status:** ✅ Done

---

## Step 2 — MongoDB Client

**What:** A single module owning the MongoDB connection lifecycle and a `get_db()` accessor other modules will depend on.

**Why:** `submissions` (final storage) and, later, `auth` (if user-backed) both need a database handle. Centralizing connect/close here means `main.py` can open it on startup and close it on shutdown, and every feature just calls `get_db()`.

**Files added:**
```
backend/app/core/mongodb.py
```

**What it does:**
- `connect_to_mongo()` — opens the `MongoClient`, selects the `voice_assistant` db, and creates a **unique index on `session_id`** in the `submissions` collection (this is what makes save-on-confirm idempotent/duplicate-proof later)
- `close_mongo_connection()` — closes the client, clears the module-level reference
- `get_db()` — returns the active database handle; raises `RuntimeError` if called before `connect_to_mongo()` or after `close_mongo_connection()`, so a misordered startup fails loudly instead of silently using a dead connection

**How to verify:**
```
./.venv/Scripts/python.exe -c "
from app.core import mongodb
mongodb.connect_to_mongo()
db = mongodb.get_db()
print(db['submissions'].index_information())
mongodb.close_mongo_connection()
"
```
Confirmed: a local MongoDB instance was reachable at `mongodb://localhost:27017`; the call created the `voice_assistant` database with the `submissions` collection correctly indexed (`session_id_1`, unique). `get_db()` was also confirmed to raise `RuntimeError` both before connecting and after closing.

**Status:** ✅ Done

---

## Step 3 — Redis Client

**What:** A single module owning the Redis connection lifecycle and a `get_redis()` accessor, mirroring the shape of `core/mongodb.py`.

**Why:** The dialogue manager (Step 4+) needs a place to read/write session state (`session:{id}` with TTL). Centralizing connect/close here means `main.py` opens it on startup and closes it on shutdown, same pattern as Mongo.

**Files added:**
```
backend/app/core/redis.py
```

**What it does:**
- `connect_to_redis()` — opens a `redis.Redis` client from `settings.redis_url` with `decode_responses=True` (so callers get `str`, not `bytes`), and `ping()`s it immediately so a bad connection fails at startup, not on first use
- `close_redis_connection()` — closes the client, clears the module-level reference
- `get_redis()` — returns the active client; raises `RuntimeError` if called before connecting or after closing (same guard pattern as Mongo)

**How to verify:**
Initially verified guard logic only, with connect→set→get→delete logic checked against `fakeredis` (no local server was running at the time). **Since resolved:** you started a real Redis container (`docker run -d --name redis -p 6379:6379 redis`). Re-ran the verification against it directly — `connect_to_redis()`, a real `set`/`get`/`delete` round-trip, and the post-close guard all confirmed working against the live server.

**Status:** ✅ Done — fully verified against a live Redis instance

---

## Step 4 — Security (Password Hashing + JWT)

**What:** Password hashing/verification (for operator login) and JWT create/decode (for session auth), kept together since both are "prove who you are" concerns the auth feature will depend on.

**Why:** Needed before `features/auth` can issue tokens or protect routes with `get_current_user`.

**Files added:**
```
backend/app/core/security.py
```

**What it does:**
- `hash_password()` / `verify_password()` — bcrypt via passlib
- `create_access_token(subject, expires_minutes=None)` — signs a JWT with `sub` + `exp` claims, defaults to `settings.jwt_expire_minutes`
- `decode_access_token(token)` — returns the subject, raises `jose.JWTError` on invalid signature, expiry, or missing `sub` claim

**Dependency issue found and fixed:** `passlib==1.7.4` is incompatible with `bcrypt>=4.1` (passlib reads `bcrypt.__about__.__version__`, which newer bcrypt removed — a known unpatched upstream issue). Pinned `bcrypt==4.0.1` explicitly in `requirements.txt` to keep passlib working.

**How to verify:** Ran hash/verify round-trip (correct password passes, wrong password fails), token create/decode round-trip, an expired token (rejected), and a tampered token (rejected). All passed after the bcrypt pin fix.

**Status:** ✅ Done

---

## Step 5 — Custom Exceptions + Error Handlers

**What:** Domain-specific exceptions and FastAPI handlers that turn them into clean JSON error responses instead of raw tracebacks.

**Why:** `conversation/service.py`, `submissions/service.py`, and `llm/chain.py` (all built later) need to signal specific failure conditions from your HLD (session not found, session expired, invalid state transition, all LLM providers failed) without each route handler writing its own try/except boilerplate.

**Files added:**
```
backend/app/core/exceptions.py
backend/app/core/error_handlers.py
```

**What it does:**
- `exceptions.py` — `AppError` base class, plus `SessionNotFound`, `SessionExpired`, `InvalidTransition`, `AllLLMsFailed`, each carrying the context needed for a useful error message
- `error_handlers.py` — `register_error_handlers(app)` wires each exception to an HTTP status:
  - `SessionNotFound` → 404
  - `SessionExpired` → 410 (Gone)
  - `InvalidTransition` → 409 (Conflict)
  - `AllLLMsFailed` → 503, with a user-facing message ("We saved your progress...") matching the HLD's "all LLMs fail → keep conversation in Redis, tell user to retry shortly" behavior — internal detail (which providers failed) stays in the exception/logs, not the response

**How to verify:** Built a throwaway FastAPI app registering these handlers, hit each error route via `TestClient`, confirmed status code + JSON body for all four. All passed.

**Note:** `TestClient` emitted a harmless deprecation warning (`httpx` → `httpx2`) — not a functional issue now, but worth checking when the real test suite is built in a later step.

**Status:** ✅ Done

---

## Step 6 — `main.py` (App Boots)

**What:** The FastAPI composition root. Wires together everything built so far into a running app.

**Why:** First point where the pieces (config, Mongo, Redis, error handlers) actually combine into something you can start with `uvicorn` and hit over HTTP.

**Files added:**
```
backend/app/main.py
```

**What it does:**
- `lifespan()` — on startup: `connect_to_mongo()` then `connect_to_redis()`; on shutdown: closes Redis then Mongo (reverse order)
- `register_error_handlers(app)` — wires in the Step 5 exception handlers
- `GET /health` — returns `{"status": "ok"}`, a liveness check for later (deployment, monitoring, or just confirming the server booted)

**How to verify:** Started the real app with `uvicorn app.main:app --port 8010` against the live MongoDB and Redis instances, hit `GET /health`, got `200 {"status":"ok"}`. Startup log showed `Application startup complete` with no connection errors, confirming Mongo + Redis both connected cleanly through the lifespan hook. Server was stopped after verification.

**Status:** ✅ Done — verified against live Mongo + Redis

---

## Step 7 — Speech-to-Text Feature

**What:** The first feature module. An `STTClient` interface, a concrete provider, and a service function that applies the HLD's "low confidence → repeat" rule.

**Why:** Every voice turn starts here — audio in, text + confidence out, decide whether to ask the user to repeat before anything downstream (guardrail, dialogue manager) sees it.

**Provider decision:** The original spec left STT "to be selected." Picked **OpenAI's Whisper API** as the default — cheap, accurate, simple REST call, no infra to run. Not committed in architecture: everything downstream only ever talks to `STTClient`, so swapping to Deepgram/Google STT/local `faster-whisper` later means replacing `provider.py` only.

**Files added:**
```
backend/app/features/speech/
├── __init__.py
├── base.py       # STTClient ABC, STTResult dataclass
├── provider.py   # WhisperSTTClient (OpenAI Whisper API)
└── service.py    # transcribe_audio() — applies CONFIDENCE_THRESHOLD, flags needs_repeat
```

**What it does:**
- `base.py` — `STTClient.transcribe(audio_bytes, audio_format) -> STTResult(text, confidence)`; abstract, can't be instantiated directly
- `provider.py` — calls OpenAI's `whisper-1` model with `response_format="verbose_json"`. Whisper doesn't return a direct confidence score, so `_estimate_confidence()` approximates one from each segment's `avg_logprob` (log-probability → probability via `exp()`, averaged, clamped to `[0,1]`); falls back to `1.0` if no segment data
- `service.py` — `transcribe_audio()` flags `needs_repeat=True` when confidence is below `CONFIDENCE_THRESHOLD = 0.5` **or** the transcribed text is blank (covers silence/noise that Whisper might still score confidently)

**How to verify — and the gap:** No OpenAI API key is configured in `.env` yet (`STT_API_KEY` is blank), so the live Whisper call itself is unverified. Verified everything that doesn't need network:
- `STTClient` can't be instantiated directly (abstract method enforced)
- `transcribe_audio()` against a fake `STTClient`: high confidence → no repeat, low confidence → repeat, blank text with high confidence → repeat (the blank-text guard working as intended)
- `_estimate_confidence()` math against fake Whisper segment objects: realistic segments → ~0.93, no segments → falls back to `1.0`

**Action needed from you:** add a real `STT_API_KEY` (OpenAI key) to `.env` when you're ready to test an actual audio file end-to-end.

**Status:** ✅ Done — logic fully verified; live API call pending a real key

---

## Step 7b — Swapped STT Provider to Local `faster-whisper`

**What:** Replaced the OpenAI Whisper API provider with a locally-run `faster-whisper` model. Only `provider.py` changed — `base.py` and `service.py` are untouched, which is exactly the point of the `STTClient` interface from Step 7.

**Why:** Genuinely free (no per-minute API cost, no trial credit that runs out), matches the MSI goal of minimizing operational cost, same underlying Whisper model quality, works offline.

**Files changed:**
```
backend/app/features/speech/provider.py   # rewritten: LocalWhisperSTTClient replaces WhisperSTTClient
backend/requirements.txt                   # openai removed, faster-whisper>=1.0.3 added
```

**What it does:**
- `LocalWhisperSTTClient` — lazy-loads the `faster-whisper` model on first `transcribe()` call, not at construction, so creating the client is instant and doesn't block app startup or require network until actually needed
- Writes incoming audio bytes to a temp file (faster-whisper/PyAV needs a file, not raw bytes), transcribes, deletes the temp file in a `finally` block
- Same `avg_logprob`-based confidence estimation as the OpenAI version (faster-whisper segments expose the same field)
- Default model: `base`, CPU, `int8` compute type — a reasonable accuracy/speed tradeoff for short warehouse voice clips on modest hardware

**How to verify:**
- Confirmed `LocalWhisperSTTClient` implements `STTClient`
- Confirmed construction is instant (~0.0000s) and `_model` stays `None` until first `transcribe()` call — lazy loading works
- Re-verified the confidence math against fake segment data (same result as the OpenAI version: ~0.93 for good segments, 1.0 fallback for none)
- Full pipeline test: downloaded the `base` model (~150MB, cached locally now — no re-download on future runs) and transcribed a synthetic 2-second tone (440Hz, not real speech) through the real `faster-whisper` library. Ran cleanly end-to-end: `text=''`, `confidence=1.0` — correct, since a tone isn't speech, and this is exactly the blank-text case `service.py`'s `needs_repeat` guard is designed to catch

**Note on the Gemini key:** you pasted a live Gemini API key directly into chat. Stored it in `backend/.env` (gitignored, not committed). **Recommend rotating/regenerating it in Google AI Studio** since it was shared in a conversation that may be logged — treat it as potentially exposed.

**Status:** ✅ Done — fully verified end-to-end with a real model download and transcription

---

## Step 8 — Input Guardrail

**What:** Pure-Python rule checks on the transcribed text before it reaches the dialogue manager or any LLM call.

**Why:** This is MSI level 1 (Python Rules) applied to safety, not just extraction — catching empty/junk/malicious input here means the dialogue manager and the LLM never see it, no wasted LLM call, no risk of a transcribed "ignore previous instructions" reaching a prompt.

**Files added:**
```
backend/app/features/guardrails/
├── __init__.py
└── input_guard.py   # check_input() -> GuardResult(allowed, reason)
```

**What it does:**
- `check_input(text)` rejects: blank/whitespace-only text (`reason="empty"`), text over 500 chars (`reason="too_long"`, generous for a spoken answer but catches garbage/spam), and a set of regex prompt-injection patterns (`reason="prompt_injection"`) — "ignore/disregard previous instructions," "you are now," "act as a/an," "reveal your instructions," "new instructions:," etc.
- Returns `GuardResult(allowed: bool, reason: str | None)` so the caller (dialogue manager, built later) can decide what to tell the user for each reason

**How to verify:** Ran 13 cases — 3 legitimate warehouse-style answers (allowed), blank/whitespace (rejected), an oversized string (rejected), 6 prompt-injection phrasings (all rejected), and one deliberate negative control — a normal sentence that contains the word "ignore" but isn't an injection attempt ("the driver said to ignore the weighbridge reading") — correctly allowed through, confirming the patterns aren't so broad they block legitimate speech. All 13 passed.

**Status:** ✅ Done — fully verified

---

## Step 9 — LLM Feature (Primary + Backup + Chain)

**What:** The `LLMClient` interface, a Gemini provider (primary, per spec), a Groq provider (backup), and a chain that tries primary → backup → raises `AllLLMsFailed`.

**Backup provider decision:** you provided a Groq API key (`gsk_...` prefix identifies it as Groq). Groq exposes an OpenAI-compatible chat completions endpoint, called directly via `httpx` (no extra SDK needed for one endpoint).

**Files added:**
```
backend/app/features/llm/
├── __init__.py
├── base.py     # LLMClient ABC — generate(prompt, system) -> str
├── gemini.py   # GeminiLLMClient (primary)
├── backup.py   # GroqLLMClient (backup)
└── chain.py    # LLMChain — primary -> backup -> AllLLMsFailed
```

**Model names had to be corrected (both were stale):**
- Gemini: `gemini-2.0-flash` → **404, retired**. Google's own error message named the replacement: now using `gemini-3.8-flash`.
- Groq: `llama-3.1-8b-instant` → **404, decommissioned**. Queried Groq's `/models` endpoint with the real key to get the current list, switched to `openai/gpt-oss-20b`.

**Security note:** you pasted a second live key into chat (the Groq backup key). Same recommendation as the Gemini key — rotate it once we're done, since it's now in conversation history.

**How to verify:**
- `LLMChain` logic verified with fake clients: primary succeeds (used), primary fails/backup succeeds (falls back correctly), both fail (raises `AllLLMsFailed` with both error messages in the detail) — all 3 passed
- **Real Groq call confirmed:** `GroqLLMClient().generate(...)` → `'PONG'`
- **Real Gemini call confirmed:** `GeminiLLMClient().generate(...)` → `'PONG'`
- **Real chain call confirmed:** `LLMChain(primary=Gemini, backup=Groq).generate(...)` → `'PONG'`

**A real bug found and fixed along the way:** the first live Gemini call hung indefinitely instead of failing — the SDK has no timeout by default, so a stalled request never raises, which silently defeats `LLMChain`'s whole purpose (it can only fall back on a raised exception). Fixed by passing `http_options=types.HttpOptions(timeout=timeout_ms)` to the Gemini client (default 15s). Re-tested: a slow Gemini response now raises `ServerError: 504 DEADLINE_EXCEEDED` within 15s instead of hanging, and the chain correctly falls back to Groq when that happens — confirmed live, since Gemini's free tier was observed to be genuinely flaky during testing (timed out on one call, answered normally on the next).

**Status:** ✅ Done — all three (Gemini, Groq, chain) verified against live APIs, including the fallback path

---

## Step 10 — Extraction Feature (MSI Router)

**What:** The actual MSI decision point — given a field type and raw transcribed text, try a free Python rule first; only call the (costed, slower) `LLMChain` when the rule can't confidently handle it.

**Why:** This is the core cost/latency-saving mechanism from the spec. Most answers (company name, a clearly-spoken number, a vehicle plate) never need to touch an LLM at all.

**Files added:**
```
backend/app/features/extraction/
├── __init__.py
├── schemas.py      # FieldType enum (TEXT, NUMBER, VEHICLE_NUMBER, TIME), ExtractedField
├── rules.py        # extract_number, extract_vehicle_number, extract_text — pure Python, no LLM
├── prompts.py       # EXTRACTION_SYSTEM_PROMPT + build_extraction_prompt() for the LLM escalation path
└── router_msi.py    # extract_field() — the MSI decision point itself
```

**What it does:**
- `rules.py` — `extract_number()` handles digits ("1200") and spoken number words up to thousands ("twelve hundred", "two thousand five hundred") via a hand-rolled word map, returns `None` (not a guess) for anything it doesn't recognize. `extract_vehicle_number()` matches the Indian plate pattern (2 letters, 1-2 digits, 1-2 letters, 4 digits), tolerant of spaces/dashes. `extract_text()` just cleans free-text fields.
- `router_msi.extract_field()` — tries the matching rule for the field's `FieldType`; `TIME` has no rule yet (no `utils/time_parse.py` built so far) so it always escalates. On an LLM call, parses the JSON response (stripping markdown fences defensively), returns `ambiguous=True` with `value=None` if the response isn't valid JSON — never guesses.

**How to verify:**
- Rules in isolation: 17 cases (numbers incl. word-numbers and non-numbers, vehicle plates in various formats, text incl. blank) — all passed
- Router with an `ExplodingClient` fake that raises if ever called: confirmed rule-hit fields (number, vehicle, text) never reach the LLM — all 3 passed
- JSON parsing: plain JSON, markdown-fenced JSON, and garbage text — all handled correctly
- LLM escalation path with fake clients: normal value, ambiguous response, and malformed JSON — all 3 produced the correct `ExtractedField`
- **Live end-to-end against the real Gemini/Groq chain:** "the truck left at half past two in the afternoon" → `14:30` (correct); "around twelve hundred fifty kilos" (a number the word-rule correctly declines to guess at) → escalated to the LLM → `1250` (correct) — confirms MSI is actually saving LLM calls on the easy cases while still handling the hard ones correctly

**Status:** ✅ Done — fully verified, including two live LLM extractions

---

## Step 11 — Validation Feature

**What:** Per-field type/range/format checks, and the total-quantity calculator.

**Why:** Rule-extracted or LLM-extracted values both still need validating before they're shown in a summary — extraction gets the *value*, validation decides if it's *acceptable* (right format, right range, consistent with other fields).

**Files added:**
```
backend/app/features/validation/
├── __init__.py
├── validators.py    # validate_text, validate_number, validate_vehicle_number, validate_time, validate_time_sequence
└── calculator.py    # calculate_total()
```

**What it does:**
- `validate_text(value, label, required=True, max_length=200)` — rejects blank when required, enforces a length cap; `required=False` (for optional fields like Remarks) allows blank
- `validate_number(value, label, min_value=0, max_value=None)` — coerces to float, rejects non-numeric/below-min/above-max, normalizes whole numbers back to `int`
- `validate_vehicle_number(value, label)` — normalizes (uppercase, strips spaces/dashes) then checks against the same plate pattern used in extraction
- `validate_time(value, label)` — strict `HH:MM` 24-hour format, rejects out-of-range hour/minute, zero-pads single-digit hours
- `validate_time_sequence(earlier_time, later_time, earlier_label, later_label)` — the In/Out time ordering rule; works via plain string comparison since both times are already normalized to zero-padded `HH:MM`
- `calculate_total(four_hand, five_hand, six_hand, eight_hand, cluster)` — straight sum, per spec

All return a `ValidationResult(valid, error, value)` — `error` is a user-facing message ready to surface in a clarification prompt, `value` is the normalized form when valid.

**How to verify:** 26 cases run — required/optional text, length limits, number coercion from string, negative/non-numeric/over-max rejection, vehicle number normalization and rejection, time format edge cases (single-digit hour, invalid hour/minute, non-numeric), time sequence in both directions plus the equal-times edge case, and the calculator with normal and all-zero inputs. All 26 passed.

**Status:** ✅ Done — fully verified

---

## Step 12 — Summary Feature

**What:** Template-only summary builder — turns validated fields + the computed total into the confirmation text shown to the user. No LLM, per spec.

**Files added:**
```
backend/app/features/summary/
├── __init__.py
└── builder.py   # SECTIONS layout, build_summary()
```

**What it does:**
- `SECTIONS` — mirrors the spec's three groupings (Company & Vehicle Details / Banana Hand & Cluster Quantities / Additional Information) with field key → display label pairs; **this is the canonical list of the 16 field keys** (`company_name`, `vehicle_number`, `brand`, `line_mark`, `weight`, `four_hand`, `five_hand`, `six_hand`, `eight_hand`, `cluster`, `remarks`, `labor_name`, `vehicle_out_time`, `vehicle_in_time`, `vehicle_for_storage`, `vehicle_receiver_name`) plus `total` — later steps (`conversation/fields.py`, `submissions/schemas.py`) should reuse these exact key names so nothing has to be remapped between modules
- `build_summary(fields)` — raises `ValueError` if any expected key is entirely missing from the dict (a safety net against integration bugs between extraction/validation and summary, not a business validation rule — that stays in `validation/`); blank optional values (e.g. empty Remarks) render as an em-dash

**How to verify:** Built a full 16-field + total dict, confirmed all 24 output lines render correctly, grouped into the right sections, blank Remarks shown as an em-dash (confirmed via `repr()` and a direct `'—' in line` check, since the raw em-dash itself displays as `�` in this Windows terminal — a console encoding quirk, not a code bug). Confirmed `ValueError` raised when a key is missing entirely.

**Status:** ✅ Done — fully verified

---

## Step 13 — Conversation Data Layer (State Machine + Fields + Repository)

**What:** The foundational pieces of the dialogue manager, split out from the actual turn-running logic (that's Step 13b) so this stays reviewable: session states, the state transition table, the 16 field definitions batched into groups of 5–6, and Redis-backed session persistence.

**Files added:**
```
backend/app/features/conversation/
├── __init__.py
├── states.py          # SessionState enum
├── state_machine.py   # transition() - the allowed-transitions table
├── fields.py           # FieldDefinition, FIELD_DEFINITIONS (16 fields), get_field/get_batch/all_field_keys
└── repository.py       # Redis session storage: new_session, save_session, load_session, delete_session, session_exists
```

**What it does:**
- `states.py` — `IDLE, COLLECTING, CLARIFICATION, AWAITING_CONFIRMATION, SAVING, COMPLETED, PAUSED` (PAUSED added beyond the spec's listed states, to hold the "all LLMs failed, conversation preserved" case from the HLD)
- `state_machine.py` — `transition(current_state, event) -> SessionState`, raises `InvalidTransition` (Step 5) on any event not allowed from the current state. Encodes: `IDLE→COLLECTING→CLARIFICATION(if needed)→AWAITING_CONFIRMATION→SAVING→COMPLETED`, with `correct` keeping the session in `AWAITING_CONFIRMATION` and `llm_failure`/`resume` handling the `PAUSED` path
- `fields.py` — 16 `FieldDefinition`s (key, label, `FieldType`, question text, batch number, required flag), batched 5/5/6 to match "5-6 questions at a time." **The field keys here are deliberately identical to `summary/builder.py`'s `SECTIONS`** (flagged as a risk in Step 12) — verified matching, not just by convention
- `repository.py` — `new_session(id)` builds the initial session dict (`state`, `current_batch`, `answers`, `pending_clarification_field`, timestamps); `save_session`/`load_session` JSON-encode to/from Redis with the configured TTL; `load_session` raises `SessionNotFound` (Step 5) if the key's gone (expired or never existed)

**How to verify:**
- Confirmed `fields.py`'s 16 keys exactly match `summary/builder.py`'s keys (set equality, not eyeballing) — this was the main risk called out in Step 12, now closed
- Confirmed batch sizes are `[5, 5, 6]`
- Walked the full happy-path state sequence end to end (`IDLE→...→COMPLETED`), confirmed a terminal-state transition and an invalid event both raise `InvalidTransition`, confirmed the `PAUSED`/`resume` path
- **Repository verified against the live Redis instance**, not fakes: create → save → load (data round-trips correctly) → TTL confirmed set (3600s) → delete → `SessionNotFound` raised correctly on load after delete

**Status:** ✅ Done — fully verified, including live Redis

---

## Step 13b — Conversation Service + API Routes

**What:** The actual turn-runner that ties together everything built in Steps 7–13: guardrail → MSI extraction → validation → next question / clarification / summary. Plus the FastAPI routes that expose it, now wired into `main.py`.

**Files added:**
```
backend/app/features/conversation/
├── schemas.py    # AnswerRequest, QuestionOut, TurnResponse
├── service.py     # ConversationService - the orchestration logic
└── router.py       # POST /sessions, GET /sessions/{id}, POST /sessions/{id}/answer, POST /sessions/{id}/resume
```
```
backend/app/features/llm/chain.py    # added get_llm_chain() - FastAPI dependency, lazily builds one shared LLMChain
backend/app/main.py                   # registered the conversation router
```

**What `submit_answer()` does, per call:**
1. Rejects the call outright (`InvalidTransition`) if the session isn't `COLLECTING` or `CLARIFICATION`
2. **Optional-field blank bypass:** if the field isn't required (only `remarks`) and the answer is blank, accepts it directly — skips the guardrail entirely, since the guardrail's empty-text rule would otherwise reject a legitimate "no remarks" non-answer and loop forever asking for one
3. Guardrail (`check_input`) — rejects junk/injection input, asks to repeat (not an LLM call)
4. MSI extraction (`extract_field`) — rule first, LLM only if the rule can't handle it; `AllLLMsFailed` propagates up, after first transitioning the session to `PAUSED` and saving it (so the HLD's "preserve in Redis, ask to retry" behavior holds)
5. Validation (`validate_text`/`validate_number`/`validate_vehicle_number`/`validate_time`) — on failure, asks a clarification with the specific validation error baked into the prompt
6. On success: stores the value, clears any pending clarification, and calls `_advance()` — which checks if the batch is complete, advances to the next batch, or (once all 16 fields are in) runs the Vehicle In/Out time sequence check and transitions to `AWAITING_CONFIRMATION` with a built summary

**A design assumption flagged, not fully resolved:** the time sequence check assumes **Vehicle In Time comes before Vehicle Out Time** (vehicle arrives, is processed, then leaves). The original spec listed "Vehicle Out Time" before "Vehicle In Time" with no stated ordering — if your actual warehouse process is reversed (e.g. the vehicle is already loaded and "Out Time" is when it's dispatched from an outbound dock, arriving/"In Time" elsewhere later), this check needs flipping. Easy one-line fix in `service.py`'s `_advance()` once confirmed.

**Also not yet wired:** no auth dependency on these routes yet — any caller can hit `/sessions/*` right now. That's intentional, deferred to Step 14 (`features/auth`) which will add `Depends(get_current_user)` to all four routes.

**How to verify:** Wrote a throwaway script (deleted after use) exercising the real FastAPI app via `TestClient`, with the real Mongo/Redis lifespan and a fake `LLMClient` injected via `dependency_overrides` (deterministic, no cost, for the TIME fields that must hit the LLM). 19 checks, all passed:
- Full 16-field happy path: created a session, answered all 3 batches (5/5/6 questions), confirmed the response reached `AWAITING_CONFIRMATION` with a correct summary (`Total Quantity: 40`, correct vehicle number, correct extracted time `14:30`) — including word-number quantities ("twelve hundred", "ten", "twenty", etc.) and an LLM-escalated time field
- `GET /sessions/{id}` correctly reflects state + summary mid-conversation
- Clarification loop: an invalid vehicle number correctly triggers `CLARIFICATION`, a corrected one returns to `COLLECTING`
- `AllLLMsFailed` path: a chain that always raises → `503` response, session confirmed `PAUSED` via `GET`, then `POST /resume` correctly returns it to `COLLECTING`
- Time sequence validation: submitted Out Time before In Time → correctly rejected back into `CLARIFICATION` re-asking Out Time specifically (not In Time); corrected Out Time → reached `AWAITING_CONFIRMATION`

**Status:** ✅ Done — fully verified end-to-end through the real API, including the failure and clarification paths. One business-rule assumption (time ordering) flagged for your confirmation.

---

## Step 14 — Auth Feature (Static Operator List)

**What:** Login issuing a JWT, and a `get_current_user` dependency that now protects every `/sessions/*` route.

**Decision (yours):** static operator list, no Mongo-backed user table, no signup flow — matches "a handful of known warehouse operators," not public registration.

**Files added:**
```
backend/app/features/auth/
├── __init__.py
├── repository.py    # get_password_hash() - parses OPERATOR_CREDENTIALS from config
├── schemas.py         # TokenResponse
├── service.py          # login() - verify + issue JWT
├── dependencies.py     # get_current_user() - decodes bearer token
└── router.py            # POST /auth/login
```
```
backend/app/core/config.py          # added operator_credentials setting
backend/app/core/exceptions.py       # added InvalidCredentials
backend/app/core/error_handlers.py   # InvalidCredentials -> 401
backend/app/features/conversation/router.py   # added dependencies=[Depends(get_current_user)] to the whole router
backend/app/main.py                    # registered auth_router
```

**How operators are provisioned:** `OPERATOR_CREDENTIALS` in `.env`, format `username:bcrypt_hash;username2:bcrypt_hash2`. Generate a hash with:
```
./.venv/Scripts/python.exe -c "from app.core.security import hash_password; print(hash_password('your-password'))"
```
No code change needed to add/remove an operator — just edit `.env` and restart.

**What it does:**
- `POST /auth/login` — takes `username`/`password` as an OAuth2 form (not JSON), specifically so FastAPI's `/docs` "Authorize" button works out of the box; returns a JWT
- `get_current_user` — a FastAPI dependency wired onto the entire conversation router (`APIRouter(..., dependencies=[Depends(get_current_user)])`), so every `/sessions/*` route now requires a valid bearer token; invalid/expired tokens get a `401` with a `WWW-Authenticate: Bearer` header

**Verification credential (placeholder, not real):** added `operator1` / `ChangeMe123!` to `.env` to verify the flow end-to-end. **This is a placeholder for testing only — replace it with your own operator username(s)/password(s) before this goes anywhere near real use.**

**How to verify:** 8 checks against the real running app — unauthenticated access to `/sessions` rejected (401), wrong password rejected, unknown username rejected, correct login returns a token with `token_type: bearer`, the token then successfully authenticates `POST /sessions` and `GET /sessions/{id}`, and a garbage/malformed token is rejected. All 8 passed.

**Status:** ✅ Done — fully verified. **Action needed from you:** replace the placeholder operator credential in `.env` with real one(s) before deployment.

---

## Step 15 — Submissions Feature (Confirm, Save, Correct)

**What:** The last feature module — `POST /sessions/{id}/confirm` (save to MongoDB) and `PATCH /sessions/{id}/fields/{key}` (correct one field before confirming). This completes the pipeline from the HLD end to end.

**Files added:**
```
backend/app/features/submissions/
├── __init__.py
├── schemas.py     # SubmissionOut (all 16 fields + total + session_id + saved_at), CorrectionRequest
├── repository.py   # insert_submission() - idempotent via the Step 2 unique index, get_submission()
├── service.py        # SubmissionService.confirm() and .correct_field()
└── router.py           # POST /sessions/{id}/confirm, PATCH /sessions/{id}/fields/{key}
```
```
backend/app/main.py   # registered submissions_router
```

**What it does:**
- `confirm(session_id)` — `AWAITING_CONFIRMATION → SAVING`, builds the submission dict (answers + computed total + `session_id` + `saved_at`), inserts into MongoDB via `insert_submission()` (duplicate-key errors from the Step 2 unique index are caught and treated as success, not failure — confirming twice is a no-op, not a crash), then `SAVING → COMPLETED`. The session is kept in Redis (not deleted) so a repeated `GET` still reports `COMPLETED` until natural TTL expiry.
- `correct_field(session_id, field_key, raw_text)` — re-runs the same guardrail → MSI extraction → validation pipeline as `conversation/service.py`'s `submit_answer` (intentionally duplicated here, ~15 lines, rather than importing across feature boundaries), then rebuilds the summary. The `'correct'` transition is only defined from `AWAITING_CONFIRMATION` in the state machine, so corrections from any other state (mid-collection, after save) are rejected automatically as `InvalidTransition` — no extra guard code needed.
- **A gap flagged deliberately:** unlike `submit_answer`, `correct_field` does **not** catch `AllLLMsFailed` and pause the session — `AWAITING_CONFIRMATION` has no `llm_failure` transition defined (only `COLLECTING`/`CLARIFICATION` do). If both LLMs fail during a correction, the caller gets a `503` and the session simply stays in `AWAITING_CONFIRMATION`, ready to retry the same correction. This is intentional (no state to "pause" from here — the session is already fully collected) but worth knowing.

**How to verify:** Two scripts (both deleted after use, along with their test data):
- Full flow via `TestClient` with a fake LLM: logged in, ran a complete 16-field conversation to `AWAITING_CONFIRMATION`, corrected `labor_name` (confirmed the new value appears in the regenerated summary), attempted an invalid correction (rejected with a clarification, state unchanged), confirmed/saved, verified the exact submission via the API response **and independently via a direct MongoDB query** (not just trusting the API), confirmed session state flips to `COMPLETED`, confirmed a second confirm attempt is rejected (`409`, `InvalidTransition`), confirmed a correction attempt after completion is also rejected (`409`), and confirmed the MongoDB document was untouched by both rejected attempts — 15 checks, all passed
- Idempotent insert verified directly at the repository level: first insert returns `True`, a duplicate `session_id` insert returns `False` with no exception, and the original document's data is confirmed unchanged (the duplicate attempt didn't overwrite it) — 3 checks, all passed

**Status:** ✅ Done — fully verified end-to-end, including a real MongoDB write/read, idempotency, and both rejection paths

---

## All planned feature modules are now built

Every step from the original roadmap is complete: project setup, MongoDB, Redis, security, exceptions/error handlers, `main.py`, speech-to-text, guardrails, LLM layer (Gemini + Groq + chain), MSI extraction, validation, summary, the full conversation engine (state machine + service + routes), auth, and submissions (confirm/save/correct). The backend is a working, verified voice-data-collection API end to end: login → create session → answer questions (voice-transcribed text in, MSI-routed extraction, validated) → summary → confirm → saved in MongoDB, with corrections, clarifications, and LLM-outage handling all exercised against real services.

## Step 16 — Permanent `pytest` Test Suite

**What:** Converted every throwaway verification script from Steps 1–15 into a permanent, repeatable regression suite under `tests/`.

**Files added:**
```
backend/pytest.ini
backend/tests/
├── conftest.py              # fixtures: client, _bypass_auth (autouse), unauthed_client, fake_llm, created_sessions
├── test_rules.py              # extraction rules (17 parametrized cases)
├── test_validators.py          # all validators + time sequence
├── test_calculator.py           # total calculator
├── test_state_machine.py         # state transitions incl. terminal/invalid/paused/resume
├── test_llm_chain.py              # chain fallback logic (fakes only - no real API calls in the suite)
├── test_extraction_router.py       # MSI routing: rule-hit never calls LLM, LLM escalation paths
├── test_guardrails.py               # input guardrail, incl. the false-positive negative control
├── test_summary.py                    # summary builder
├── test_repository.py                  # conversation session storage against live Redis
├── test_auth.py                         # login/token flow, decoupled from real .env credentials
├── test_conversation_flow.py             # full integration: happy path, clarification, AllLLMsFailed/PAUSED/resume, time sequence
└── test_submissions.py                    # correction loop, confirm/save, idempotency, post-completion rejection
```

**Design decisions:**
- **Runs against real local Mongo + Redis**, not fakes/mocks — consistent with how every feature in this project was manually verified throughout. `fakeredis`/`mongomock` are in `requirements.txt` but unused; left in case you want to switch to fully-isolated tests later (e.g. for CI without live services), but for now the suite matches the project's established "verify against the real thing" approach.
- **LLM calls are always faked in the suite** (`conftest.py`'s `fake_llm` fixture / `test_llm_chain.py`'s fakes) — unlike the manual verification steps, an automated suite that runs repeatedly shouldn't cost money or depend on network/API uptime. Live Gemini/Groq behavior was verified manually in Step 9 and documented there; re-verify live manually if either provider's API changes again (like the stale-model-name issue hit in Step 9).
- **Auth is bypassed by default** (`_bypass_auth`, autouse) so no test depends on whatever's actually in `.env`'s `OPERATOR_CREDENTIALS` — meaning the suite keeps working after you replace the placeholder credential. `test_auth.py` is the only file that tests the real login path, using `monkeypatch` to inject a throwaway test credential instead of touching `.env`.
- **MongoDB test data is cleaned up automatically** via the `created_sessions` fixture (tracks session IDs a test creates, deletes the matching submissions after).

**A real bug caught while building this:** `requirements.txt` had `pytest>=8.3.3` (a floor, not a pin) and `pytest-asyncio>=0.24.0`. Installing fresh resolved to `pytest==9.2.0`, which **crashes immediately on startup** (`AttributeError: 'NodeId' object has no attribute '_str_cache'`, inside pytest's own fixture registration, before any of our code runs) when `pytest-asyncio` is also installed. Removed the unused `pytest-asyncio` (we have no async tests) and pinned `pytest==8.3.3` exactly, not just a floor. This is exactly the kind of thing a floor-pinned dependency can silently break on a future `pip install -r requirements.txt` — worth remembering if the suite ever mysteriously stops running after a clean install.

**How to verify:** `./.venv/Scripts/python.exe -m pytest -v` — **72 tests, all passing**, in ~3 seconds. Ran twice in a row to confirm no state-leakage flakiness between runs (shared Mongo/Redis across test runs is exactly the kind of thing that causes flaky suites if cleanup is wrong) — both runs identical, 72/72. Confirmed the `submissions` collection has 0 documents after the suite runs — no test data leaks into the real database.

**Status:** ✅ Done — 72/72 passing, verified stable across repeated runs, verified no data leakage

---

## Step 19 — `/speech/transcribe` Endpoint + `TurnResponse` Enhancements (Frontend Prep)

**Decisions (yours):** frontend will be a simple browser-based web app; voice input goes through a new backend `/transcribe` endpoint (reusing the already-built `faster-whisper` service) rather than the browser's built-in Web Speech API.

**What:** Two backend additions needed before the frontend can be built against something real.

**1. `POST /speech/transcribe`** — the first way to actually get audio into the system via the API (until now, `speech/service.py` existed but nothing exposed it over HTTP; `conversation`/`submissions` only ever accepted already-transcribed text).
```
backend/app/features/speech/schemas.py   # TranscriptionResponse
backend/app/features/speech/router.py     # POST /speech/transcribe (auth-protected)
backend/app/features/speech/provider.py    # added get_stt_client() - shared singleton, model loads once per process not per request
backend/app/main.py                          # registered speech_router
```
Accepts a multipart file upload, runs it through the real `faster-whisper` pipeline, returns `{text, confidence, needs_repeat}`.

**2. `TurnResponse` gained `next_field_key` and `answered_field_keys`** — a real gap caught while planning the frontend: the API told a client *that* questions or a clarification were pending, but never *which field* to ask about next. A client would have had to guess, and that guess breaks entirely on page reload / session recovery (the exact scenario the HLD's "session recovery while available" requirement describes). Fixed in `conversation/service.py`: every `COLLECTING`-state response now goes through a new `_collecting_response()` helper that computes the first unanswered field in the current batch plus which ones are already done; every `CLARIFICATION`-state response now includes the exact pending field key.

**How to verify:**
- `/speech/transcribe`: 2 tests (`tests/test_speech.py`) - unauthenticated upload rejected (401), and a real (not faked) run through the actual `faster-whisper` pipeline with a synthetic non-speech audio fixture, confirming the endpoint→service→provider wiring works and returns the expected shape
- `next_field_key`/`answered_field_keys`: extended `test_conversation_flow.py` with explicit assertions through the batch progression (`company_name` → `vehicle_number` → ... correctly tracked), the clarification path (exact field key returned), and - the specific scenario this was built for - **a simulated page reload mid-batch** (`test_session_recovery_mid_batch_shows_correct_next_field`): answer 2 of 5 batch-1 fields, then `GET /sessions/{id}` fresh (no client-side state at all) and confirm it correctly reports `next_field_key: "brand"` and `answered_field_keys: ["company_name", "vehicle_number"]`

**Suite status:** 91/91 passing.

**Status:** ✅ Done — fully verified, including the specific session-recovery scenario this was built to fix

---

## Reverted: Frontend and Everything Built On Top Of It

At your request, everything built after this point was removed, back to exactly this checkpoint. This included:
- The entire `frontend/` directory (the vanilla HTML/CSS/JS app: chat UI, Voice Mode, the full-screen call UI, the ChatGPT-style pill input bar, and all the bug fixes found along the way)
- `backend/app/main.py`'s static-file mounting that served it
- Batch voice answering (`submit_batch_answer`, `extract_batch`, `POST /sessions/{id}/answer-batch`) - the main flow is back to one field answered at a time via `POST /sessions/{id}/answer`
- The "all 16 questions in one recording" redesign (`conversation/fields.py` is back to the original 3-batch split of 5/5/6 questions)
- Grouped follow-up questions (missing/unclear answers are no longer batched into one message - back to one question or one clarification at a time)
- The `CLARIFICATION`-state compatibility fixes (no longer needed once the batch endpoint that required them was removed)
- The STT model size config (`STT_MODEL_SIZE`, `stt_model_size` setting) - speech-to-text is back to the `faster-whisper` `base` model, unconfigurable (hardcoded default)
- The "declined quantity means zero" handling for number fields (e.g. "cluster is none" → 0) - both the rule-level and LLM-prompt instructions

**What's untouched:** auth, MongoDB, Redis, the state machine (apart from one now-unused transition removed), the summary/confirm/save flow, the Docker Compose setup for mongo/redis/api (it never referenced the frontend), and the `/speech/transcribe` endpoint + `next_field_key`/`answered_field_keys` session-recovery fields from this step (Step 19) - those predate the frontend and stay.

**How this was verified:** since there's no git history to revert against, every changed file was manually reconstructed from the exact diffs recorded in this log, then validated two ways: `pytest` returns **91/91 passing** - the identical count this exact checkpoint reported the first time (a strong signal the reconstruction is accurate, not just "tests pass") - and the server was booted fresh, confirming `GET /` now 404s (no frontend mounted), `/health` and `/docs` still work.

---

## Step 20 — New React + Vite Frontend (Separate from the Backend)

**Your spec:** a completely new frontend, built from scratch as a separate React+Vite project (not served same-origin like the old vanilla-JS one), reusing the existing backend over REST/CORS. The spec required showing all 16 questions together and grouping follow-ups/clarifications - which needs the batch-answering backend logic reverted two steps ago, so per your explicit confirmation, that was re-added first.

### Part 1 — Backend: re-added batch answering + CORS

Re-implemented from the ground up (not copy-pasted from memory of old code, though the design is necessarily similar since it's the same problem): `extract_batch()`, the batch LLM prompt, `submit_batch_answer()`, grouped "remaining questions" responses, the `CLARIFICATION`-state compatibility fixes, and the "declined quantity means zero" rule/prompt handling - all the same capabilities removed in the revert, now back.

```
backend/app/features/extraction/prompts.py, router_msi.py, rules.py   # batch prompt + extract_batch() + zero-phrase handling
backend/app/features/conversation/fields.py                              # back to batch=1 (all 16 fields, one round), with `section` for display grouping
backend/app/features/conversation/schemas.py                               # BatchAnswerRequest, QuestionOut.section
backend/app/features/conversation/service.py                                 # submit_batch_answer(), _remaining_fields(), grouped _collecting_response()
backend/app/features/conversation/router.py                                    # POST /sessions/{id}/answer-batch
backend/app/features/conversation/state_machine.py                               # CLARIFICATION -> AWAITING_CONFIRMATION route
backend/tests/test_batch_answer.py (recreated), test_conversation_flow.py, test_state_machine.py, test_rules.py
```

**One genuinely new addition this time:** `CORSMiddleware` in `main.py`, configured via a new `cors_allowed_origins` setting (default `http://localhost:5173,http://127.0.0.1:5173`, the Vite dev server). The old frontend was served same-origin by FastAPI itself, so CORS never came up; a separate React app on its own port needs it. Verified with a real `OPTIONS` preflight request (`Origin: http://localhost:5173`) - correctly allowed, with credentials, `Authorization`, and `Content-Type` all permitted.

**Verification:** `pytest` → **107/107 passing**, matching the exact count this functionality reached before the revert (same confidence signal as the revert's own verification - an exact count match, not just "green").

### Part 2 — Frontend: React + Vite from scratch

```
frontend/
├── src/
│   ├── components/   # MessageBubble, ChatThread, InputBar, Waveform, SummaryActions
│   ├── pages/        # LoginPage, ChatPage
│   ├── services/      # api.js (the only file that knows the backend's HTTP contract), formatters.js
│   ├── hooks/           # useAuth, useRecorder
│   ├── styles/            # global.css (dark theme tokens)
│   ├── App.jsx, main.jsx
├── .env / .env.example     # VITE_API_BASE_URL
├── package.json, vite.config.js
```

**Design notes:**
- `services/api.js` is the single place that constructs requests to the backend - every component/hook goes through it rather than calling `fetch` directly, matching the spec's "don't duplicate backend functionality in the frontend" instruction by keeping the contract in one file.
- `useRecorder` and `Waveform` reuse the exact proven design from the earlier vanilla-JS build (live RMS volume via `AnalyserNode`, the same bar-animation math) - just reorganized as a React hook + component instead of plain functions, since that logic was already verified to work and the underlying Web Audio API usage doesn't change with the framework. `useRecorder` only supports manual start/stop/cancel this time (no silence-based auto-stop) since this spec didn't ask for a hands-free mode.
- `InputBar` implements the spec's three states in one component: the normal pill (text + mic + send), the recording row (cancel ✕ + waveform + stop ■), and transcription - **never auto-submits**; a finished recording always fills the text field for review, Send is the only path that calls `onSend`.
- `ChatPage` owns the conversation: boots by resuming an existing session (`sessionStorage`) or creating a new one, converts each `TurnResponse` into one assistant message (grouped questions by section via `formatters.groupedQuestionsBody()`, matching the spec's numbered/sectioned example exactly), and swaps the bottom panel between `InputBar` (collecting), `SummaryActions` (confirm/correct), a Try Again button (paused), and a Start Another Entry button (completed) based on session state - mirroring the backend state machine directly rather than inventing separate frontend state.
- A 401 during boot (expired/invalid token) triggers logout directly instead of retrying a request that would just fail again.

**How to verify - and what was actually verified without a browser:**
- `npx oxlint` → 0 warnings/errors across 13 files
- `npm run build` → succeeds, and the built bundle was grepped to confirm `VITE_API_BASE_URL` was correctly embedded
- `groupedQuestionsBody()` (the question-formatting logic) verified directly in Node against a multi-section sample - produces continuous numbering across sections exactly matching the spec's example output
- **Both dev servers booted together** (backend on :8000, Vite on :5173) and a **full live integration test run via curl with a `CORS Origin: http://localhost:5173` header on every request**, simulating exactly what the React app does: login → create session (confirmed 16 questions, 3 correct sections) → one realistic batch-recording-style answer via `/answer-batch` (real LLM, real extraction) → reached `AWAITING_CONFIRMATION` with a correct summary → confirmed → **saved to the real MongoDB** (verified `total: 40`) → test data cleaned up afterward
- Full backend suite re-confirmed: **107/107**

**What this does NOT verify, same honest limitation as every frontend step in this project:** the actual in-browser experience - whether the pill bar and recording transition look right, whether the waveform animates smoothly against a real voice, whether typing/clicking feels responsive. There's no browser automation tool available in this environment. Every API call the UI will make has been proven correct against the live backend; the visual/interaction layer on top of that needs your test.

**Status:** ✅ Backend re-add fully verified (107/107 + live CORS). Frontend structurally verified (lint, build, live API contract match end-to-end) - the actual UI experience needs your browser.

---
