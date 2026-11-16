# Karpathy-Guidelines Audit — Phase A (Read-Only)

Scope: `backend/app/`, `backend/tests/`, `frontend/src/`. No files changed. No live Gemini/Groq calls made.

Baseline held while auditing: backend 116/117 pytest (1 pre-existing env-dependent failure, see GOAL-DRIVEN #1 below), frontend 15/15 vitest, lint clean, build clean.

Legend: **VERIFIED** = read/traced/reproduced in this session. **SUSPECTED** = plausible from code shape, not independently reproduced.

---

## 1. THINK FIRST — Hidden Assumptions

### 1.1 `unloading_time` has no sequence validation against `vehicle_in_time`/`vehicle_out_time`
- **File:** `backend/app/features/conversation/service.py:255-270`
- **Severity:** BUG
- **Status:** VERIFIED (read the full validation block — only `vehicle_in_time`/`vehicle_out_time` are passed to `validate_time_sequence`)
- **Evidence:**
  ```python
  if "vehicle_in_time" in answers and "vehicle_out_time" in answers:
      ...
      seq = validate_time_sequence(answers["vehicle_in_time"], answers["vehicle_out_time"], in_label, out_label, language)
  ```
  `unloading_time` is one of the 18 fields, asked in the order In → Out → Unloading (`fields.py:74-78`), but it is never cross-checked. A submission with `vehicle_in_time=14:00`, `vehicle_out_time=17:00`, `unloading_time=23:00` is accepted as-is.
- **Why it matters:** this is exactly the kind of hidden assumption the time-ordering check was built for (`vehicle_in_time < vehicle_out_time`, flagged explicitly in `BUILD_LOG.md` Step 13b) — but the field list grew by one time field since, and the validation wasn't extended to match.

### 1.2 Input guard length cap vs. an 18-field spoken/typed batch
- **File:** `backend/app/features/guardrails/input_guard.py:5`
- **Severity:** RISK (now partially mitigated this session)
- **Status:** VERIFIED — reproduced live in this session (555-char real answer rejected at the old `MAX_LENGTH = 500`; now raised to 1000 per your instruction today)
- **Note:** 1000 chars comfortably fit the 18-field answer tested today, but there's still no actual headroom analysis tying the cap to "18 fields, worst-case verbose phrasing" — it's an empirically-chosen number, not a derived one. A sufficiently verbose answer (long proper nouns in Hindi/Marathi transliteration, which run longer per word than English) could still hit it. No test encodes "the cap must comfortably fit N fields' worth of realistic answers."

### 1.3 Closed-set company/brand lists are stale relative to real usage
- **File:** `backend/app/features/conversation/fields.py:53-54`
- **Severity:** RISK
- **Status:** VERIFIED
- **Evidence:** `_COMPANY_NAMES = ["Khorale Global", "Rajmata", "Jaywant"]`, `_BRAND_NAMES = ["Joker Banana", "Banana Man", "Hi Banana"]`. Today's real test submission used **"Corale Global"** — one letter off from "Khorale Global" — and relies entirely on the LLM's fuzzy-match instruction in `prompts.py` to resolve it correctly; there is no test asserting that specific near-miss resolves correctly, and no deterministic fallback if the LLM mismatches a close name to the wrong allowed value.

### 1.4 Language assumption baked into STT domain prompts
- **File:** `backend/app/features/speech/provider.py:18-20`
- **Severity:** STYLE/RISK
- **Status:** VERIFIED
- **Evidence:** `DOMAIN_PROMPTS` is built from `FIELD_TEXT` labels per `SUPPORTED_LANGUAGES` — correct and self-maintaining as fields change, so not itself a bug. Flagging only because it's the one place a future 4th language would need a corresponding translation table entry or this silently produces an empty/missing prompt bias for that language (`DOMAIN_PROMPTS[lang]` would `KeyError` in `GroqSTTClient.transcribe` if `lang` normalizes to something not in `SUPPORTED_LANGUAGES`). Not reproduced — `normalize_language()` wasn't traced for its full fallback behavior.

### 1.5 Model-output-format dependency has no schema validation beyond JSON-parseability
- **File:** `backend/app/features/extraction/router_msi.py` (`_parse_json_response`)
- **Severity:** RISK
- **Status:** SUSPECTED
- Parsing only checks "is this valid JSON," not "does it have the exact keys/types the code expects" (e.g. `value`, `display_value`, `ambiguous`). A model response that's valid JSON but missing `ambiguous` or using a different key name would likely raise an uncaught `KeyError`/`AttributeError` deeper in the call stack rather than a clean `ExtractionParseFailed`. Not reproduced live (would require a live or fabricated malformed-but-valid-JSON response); flagging as a gap, not a confirmed crash.

---

## 2. SIMPLICITY

### 2.1 Single-field answer path (`/answer`) is dead weight in production, alive only in tests
- **Files:** `backend/app/features/conversation/router.py:36-39`, `service.py` (`submit_answer`), `frontend/src/services/api.js:58` (`submitAnswer`)
- **Severity:** STYLE
- **Status:** VERIFIED
- **Evidence:** `frontend/src/pages/ChatPage.jsx` imports and calls `submitBatchAnswer` only (`ChatPage.jsx:12,153`) — `submitAnswer` is exported from `api.js` but has zero callers anywhere in `frontend/src/`. On the backend, `fields.py` sets every field to `batch=1` (single batch), meaning the production UI only ever drives `/answer-batch`. The single-field `/answer` endpoint, `submit_answer()`, and the `CLARIFICATION`-state single-field retry path still exist and are heavily tested (`test_conversation_flow.py`), but are genuinely unreachable from the real frontend.
- **Not a bug** — this was clearly a deliberate decision to keep the single-field path working (per `BUILD_LOG.md`'s "Reverted" section, it existed before the batch redesign and was kept rather than deleted). Flagging per your instruction to look for "leftover code paths (single-field versus batch)."

### 2.2 Unused dependencies in `requirements.txt`
- **File:** `backend/requirements.txt`
- **Severity:** STYLE
- **Status:** VERIFIED (grepped all of `app/` and `tests/` for imports — zero hits outside `.venv`/`venv` site-packages)
- **Evidence:** `fakeredis>=2.26.1` and `mongomock==4.1.2` are listed but never imported anywhere in `app/` or `tests/`. This is self-acknowledged in `BUILD_LOG.md` Step 16 ("left in case you want to switch to fully-isolated tests later") — not a surprise, just confirming it's still true today.

### 2.3 Duplicated extraction pipeline between `conversation/service.py` and `submissions/service.py`
- **Files:** `backend/app/features/conversation/service.py` (`submit_batch_answer`/`submit_answer`), `backend/app/features/submissions/service.py` (`correct_field`)
- **Severity:** STYLE
- **Status:** VERIFIED — confirmed by reading both; also explicitly self-documented in `BUILD_LOG.md` Step 15 ("intentionally duplicated here, ~15 lines, rather than importing across feature boundaries")
- Not re-litigating this — it's a known, acknowledged tradeoff, not an oversight. Listed because your prompt specifically asked to check for it.

---

## 3. SURGICAL CHANGES — Stale Docs / Inconsistencies

### 3.1 `BUILD_LOG.md` is substantially out of date vs. the current codebase
- **Severity:** RISK (for anyone, including a future agent session, trusting it as ground truth)
- **Status:** VERIFIED — every mismatch below was directly diffed against current code
- Mismatches found:
  1. **Field count/names:** `BUILD_LOG.md` (Steps 12, 13, 20) repeatedly states **16 fields** with keys including `remarks`, `vehicle_for_storage`, `vehicle_receiver_name`, `line_mark`. Current `fields.py` has **18 fields**; `remarks`, `vehicle_for_storage`, `vehicle_receiver_name` don't exist anymore, and `line_mark` was renamed to `line_supervisor_name`. `container_number`, `driver_name`, `cold_storage_name`, `cold_storage_supervisor_name`, `unloading_time` exist in code with no corresponding log entry.
  2. **STT provider:** Step 7b describes switching to **local-only** `faster-whisper`, and the Step 16/19 sections never mention Groq. Current code (`speech/provider.py`) supports **both** `LocalWhisperSTTClient` and `GroqSTTClient`, selected by `STT_PROVIDER`, and the real `.env`/`backend.log` confirm Groq is what's actually running. This swap (per git log: commit `098329c`, "Switch STT to Groq cloud Whisper") has no `BUILD_LOG.md` entry at all.
  3. **Input guard length:** Step 8 documents `MAX_LENGTH = 500`. Current code (after today's change) is `1000`; even before today's change, the number in the log (500) matched code, so this entry will go stale again unless updated — flagging so it's not forgotten this time.
  4. **LLM config additions:** `GEMINI_MODEL`, `LLM_PRIMARY_PROVIDER`, the Gemini usage-logging block, and `app/main.py`'s explicit `logging.basicConfig()` call — all built earlier in this session — have no `BUILD_LOG.md` entries.
  5. **Test counts:** Step 20 states "107/107 passing" as the final verified count. Actual current count is **117** (116 passing + 1 failing, see GOAL-DRIVEN #1).
- **Not fixing in Phase A** — this is a documentation-debt finding, listed per your explicit instruction to check `BUILD_LOG.md` against the code.

### 3.2 No other inconsistent/leftover-revert code found
- **Status:** VERIFIED (checked for commented-out blocks, orphaned imports, half-removed code paths)
- Nothing found beyond 3.1 and the already-acknowledged items in section 2. The "Reverted" section in `BUILD_LOG.md` (frontend removal, then batch-answering re-add) left no dead code behind — the current code is internally consistent with itself; only the **documentation** of it is stale.

---

## 4. GOAL-DRIVEN

### 4.1 — ADDED CHECK: tests that read real `.env` values, and live-call safety

**Tests that read a real `.env`-sourced `settings` value without monkeypatching it:**

| Test | File:line | Reads | Breaks or behaves differently when `.env` changes? |
|---|---|---|---|
| `test_usage_metadata_present_logs_token_counts` | `test_gemini_logging.py:40-57` | `settings.gemini_model` (via `GeminiLLMClient(api_key="test")` with no `model=`) | **BREAKS.** Line 57 hardcodes `assert "gemini-3.8-flash" in line`. **VERIFIED failing right now** — today's baseline run shows exactly this failure, because real `.env` has `GEMINI_MODEL=gemini-3.1-flash-lite`. |
| `test_usage_metadata_none_does_not_crash_and_logs_na` | `test_gemini_logging.py:60-71` | same as above | Behaves differently but doesn't break — never asserts the model name, only token-count fields. |
| `test_rate_limit_error_is_logged_with_status_code_and_reraised` | `test_gemini_logging.py:74-89` | same | Same as above — doesn't assert model name, unaffected. |
| `test_log_lines_never_contain_the_prompt_or_api_key` | `test_gemini_logging.py:92-106` | same | Unaffected — doesn't assert model name. |
| `test_logging_config` | `test_logging_config.py:10` | `settings.log_level` | **Would BREAK** if `.env`'s `LOG_LEVEL` is ever set to anything other than `"INFO"`. Currently passes only because `.env` happens to have `LOG_LEVEL=INFO`. |
| `test_repeated_failed_logins_are_rate_limited` | `test_auth.py:65` | `settings.login_rate_limit_attempts` | **Does not break** — the loop bound is read from the same live setting it's testing against, so it self-adjusts to whatever `.env` (or the hardcoded default of 5, since no `LOGIN_RATE_LIMIT_ATTEMPTS` line exists in `.env` today) specifies. Behaves differently (tests a different concrete limit) but not incorrectly. |
| `test_rate_limit_is_scoped_per_ip_and_does_not_lock_out_other_ips` | `test_auth.py:107` | same | Same — self-adjusting, not fragile. |

No test was found reading `llm_primary_provider`, `operator_credentials`, `stt_provider`, `cors_allowed_origins`, `session_ttl_seconds`, or any API key field without an explicit `monkeypatch.setattr(settings, ...)` override first (`test_llm_chain.py`, `test_gemini_model_config.py`, `test_auth.py`'s `operator_credentials` test, `test_probe_script.py` — all confirmed monkeypatched before use).

**Fix needed for the one real break:** `test_gemini_logging.py`'s `_client_with_fake_sdk()` helper (line 34-37) should either pass `model="gemini-3.8-flash"` explicitly to `GeminiLLMClient(...)` or the test should `monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")`, matching the pattern `test_gemini_model_config.py` already uses. Not fixed in Phase A per your instruction — logged here for Phase B.

**Live-call safety check — can any test make a real Gemini/Groq call if a real key is present?**
- **VERIFIED SAFE.** Every test that constructs a `GeminiLLMClient` either (a) swaps `client._client` (the internal `genai.Client`) for a `SimpleNamespace`/fake object *before* calling `.generate()` (`test_gemini_logging.py`, `test_gemini_model_config.py`), or (b) never calls `.generate()` at all after construction (`test_llm_chain.py:143-154` only checks `isinstance(chain._primary, GeminiLLMClient)`), or (c) prevents construction entirely via a monkeypatched stub that raises `AssertionError` if instantiated (`test_probe_script.py`).
- Every HTTP-level test (`test_conversation_flow.py`, `test_batch_answer.py`) goes through `conftest.py`'s `fake_llm` fixture, which overrides the FastAPI `get_llm_chain` dependency with a fully fake `LLMChain` — confirmed this fixture is used by every test in those files except `test_batch_all_llms_failed_pauses_session`, which manually installs its own fake `AlwaysFailLLM` override instead (equally safe).
- **One assumption not independently verified against SDK source** (SUSPECTED, not VERIFIED): `genai.Client(api_key=..., http_options=...)`'s constructor itself (called inside `GeminiLLMClient.__init__`, including in `test_llm_chain.py`'s two tests that construct a real `GeminiLLMClient` via `get_llm_chain()`) is assumed not to make any network call at construction time — only `.generate()` →`models.generate_content()` does. This is standard SDK behavior and consistent with everything observed live this session, but wasn't traced into the SDK's own source to rule out e.g. an eager auth-discovery call. Flagging as the one unverified link in the "no live calls from tests" chain. `GroqLLMClient.__init__` (`backup.py:14-20`) was read directly and confirmed to do nothing but store config — no ambiguity there.

### 4.2 Claims in `BUILD_LOG.md` not provable by any current test
- **Severity:** STYLE
- **Status:** VERIFIED (cross-referenced against current `tests/`)
- Step 7's live Whisper API verification, Step 9's live Gemini/Groq "PONG" calls, Step 10's live end-to-end extraction, Step 20's live CORS/MongoDB integration run — all describe one-off manual verifications via throwaway scripts that were deleted afterward. None of these specific claims (e.g. "a slow Gemini response now raises `ServerError: 504` within 15s") are re-provable by anything in the current `tests/` directory; they were true when written but aren't regression-protected. This is explicitly acknowledged in the log itself ("Live Gemini/Groq behavior was verified manually... re-verify live manually if either provider's API changes again") so it's a known, accepted gap, not a hidden one.

### 4.3 Error paths with partial or no test coverage
- **Status:** mixed VERIFIED/SUSPECTED
- **Groq 429 specifically:** `test_llm_chain.py:61` parametrizes retryable-status tests with `[429, 500, 502, 503]` generically via `_is_retryable()`, but this tests the classifier function directly, not an actual `GroqLLMClient.generate()` call raising a real `httpx.HTTPStatusError` with status 429 from Groq's response shape. VERIFIED no test exercises `GroqLLMClient.generate()` itself raising and being classified end-to-end — only the classifier in isolation.
- **Non-retryable Gemini 400 skipping Groq fallback:** `test_llm_chain.py:66` (`test_httpx_invalid_request_and_auth_errors_are_not_retryable`) tests the classifier only, same gap as above. However, this exact path was **VERIFIED live** today (not via a test, via your real submission): `gemini-3.5-flash-lite` returned a real `400`, correctly classified non-retryable, correctly skipped the Groq fallback, correctly surfaced as `503` to the client. Behavior is confirmed correct in practice; just not pinned by an automated test against the real chain object (only against the classifier function).
- **Expired session mid-conversation:** `test_repository.py` (not fully read this pass, flagging as SUSPECTED gap) — `SessionNotFound` is raised by `load_session` per `BUILD_LOG.md` Step 13, but whether a test specifically simulates a session expiring (TTL elapsing) *mid-batch* rather than just "key never existed" wasn't confirmed either way this pass.
- **Failed Mongo insert (non-duplicate-key failure):** `submissions/service.py`'s `confirm()` catches duplicate-key errors specifically (Step 15). SUSPECTED gap: no test was found simulating a *different* Mongo failure (e.g. connection drop mid-insert) to confirm it propagates as a clean error rather than crashing unhandled — not independently confirmed either way this pass.

---

## 5. SECURITY

### 5.1 `JWT_SECRET` default placeholder has no startup enforcement
- **File:** `backend/app/core/config.py:35`, `backend/app/core/security.py:30,36`
- **Severity:** RISK
- **Status:** VERIFIED (no value printed — confirmed only that the *code path* has no check, not what your actual `.env` value is)
- **Evidence:** `jwt_secret: str = "change-me-to-a-long-random-string"` is the default, and `security.py` uses `settings.jwt_secret` directly for both signing and verifying — nothing anywhere checks whether the running value still equals that placeholder before issuing tokens. If `ENVIRONMENT=production` with the default never overridden, every JWT is forgeable by anyone who's read the (public) source. No test or startup check catches this.

### 5.2 `/speech/transcribe` has no upload size limit
- **File:** `backend/app/features/speech/router.py:20`
- **Severity:** RISK
- **Status:** VERIFIED (read the route directly — `audio.file.read()` with no size check, no `Content-Length` validation, no FastAPI `max_length`/`File(...)` size constraint anywhere in the route or `UploadFile` usage)
- **Evidence:** `audio_bytes = audio.file.read()` reads the entire upload into memory unconditionally. The route does require auth (`get_current_user`, confirmed route-level dependency), so this isn't anonymous-DoS-exposed, but any authenticated operator (or a compromised/leaked token) could upload an arbitrarily large file, exhausting memory or (for the local Whisper path) disk via the temp file. No reproduction attempted (would require sending a live oversized request) — severity rated RISK, not confirmed crash.

### 5.3 Auth coverage — confirmed correct
- **Status:** VERIFIED — all four routers checked directly
- `conversation/router.py`, `submissions/router.py`, `speech/router.py` all declare `dependencies=[Depends(get_current_user)]` at the router level (not per-route, so nothing can be added later and accidentally skip auth). `auth/router.py` is correctly the only unauthenticated router (it's the login endpoint itself). No gaps found.

### 5.4 CORS configuration — confirmed correct
- **Status:** VERIFIED
- `main.py` uses an explicit `cors_allowed_origins` allowlist (not `"*"`) with `allow_credentials=True` — the correct pairing (browsers reject wildcard-origin + credentials anyway, but this doesn't rely on that browser behavior since the origin list is explicit). No gap found.

### 5.5 Logging — confirmed no sensitive data leakage
- **Status:** VERIFIED — every `logger.*` call site in `app/` was enumerated (10 call sites total, all confined to `llm/gemini.py` and `llm/chain.py`) and each one read directly; none log prompt text, API keys, or raw user answers. This matches and extends the existing `test_log_lines_never_contain_the_prompt_or_api_key` test's coverage (that test only covers `gemini.py`; `chain.py`'s log lines were checked manually in this pass and also contain no sensitive data — session IDs and provider names only).

### 5.6 Docker files — not reviewed this pass
- **Status:** NOT CHECKED — no `Dockerfile`/`docker-compose.yml` was located and reviewed in this pass; flagging as explicitly unverified rather than silently skipping it, since your prompt asked for it by name. (`BUILD_LOG.md` Step 20 mentions "the Docker Compose setup for mongo/redis/api" exists, but its current contents weren't read in this audit.)

---

## Earlier Audit Findings (6 bugs, 4 security risks)

**Honest limitation:** the specific enumerated list from that earlier audit (referenced in the task prompt) is not present verbatim in this session's active context — it was from an earlier phase of this same project history, summarized but not retained in full detail. I cannot mark each original item FIXED/OPEN against text I don't have in front of me without guessing, which would violate the VERIFIED/SUSPECTED discipline this report is trying to hold to.

What I can confirm from this pass: no currently-open security risk found in this audit (5.1, 5.2) was something I could cross-check against that original list — they may be new, or may be numbered items from it that were never closed. If you still have that original audit output (or want me to search for it, e.g. in git history or an earlier commit message), I can do the FIXED/OPEN mapping properly instead of guessing.

---

## Summary

**By severity:**
- BUG: 1 (§1.1 — unloading_time not sequence-validated)
- RISK: 7 (§1.2, §1.3, §1.5, §3.1, §5.1, §5.2, plus §4.3's partial-coverage gaps grouped as one)
- STYLE: 5 (§1.4, §2.1, §2.2, §2.3, §4.2)

**Top 10, ordered by what I'd actually want fixed first:**
1. §1.1 — `unloading_time` has no sequence validation (BUG)
2. §4.1 — `test_gemini_logging.py` hardcodes `gemini-3.8-flash`, currently failing against real `.env` (RISK, VERIFIED failing right now)
3. §5.1 — `JWT_SECRET` placeholder has no startup enforcement (RISK)
4. §5.2 — `/speech/transcribe` has no upload size limit (RISK)
5. §1.3 — closed-set company/brand fuzzy-matching has no test for near-miss resolution (RISK)
6. §3.1 — `BUILD_LOG.md` field list/STT provider/test counts all stale (RISK, documentation trust)
7. §1.2 — input-guard length cap is empirical, not derived, for 18-field answers (RISK)
8. §4.3 — Groq 429 / Gemini-400-skip-fallback only tested at the classifier level, not end-to-end (RISK)
9. §1.5 — extraction JSON parsing doesn't validate expected keys/types (RISK)
10. §2.1 — single-field `/answer` path is dead in production, alive only in tests (STYLE)

**UNVERIFIED (listed separately, per your instruction):**
- §1.4 — `DOMAIN_PROMPTS[lang]` `KeyError` risk for an unsupported normalized language
- §1.5 — extraction parse failure mode for valid-JSON-wrong-shape responses
- §4.1 — whether `genai.Client()`'s constructor itself ever makes a network call (SDK-internal, not traced)
- §4.3 — session-expiry-mid-batch and non-duplicate-key Mongo failure test coverage
- §5.6 — Docker files, not located/reviewed this pass
- The FIXED/OPEN status of the original "6 bugs, 4 security risks" audit — no verbatim source available this session

STOP — awaiting your "go" for Phase B (turning this into an ordered fix list).
