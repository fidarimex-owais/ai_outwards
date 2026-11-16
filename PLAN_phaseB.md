# Phase B — Complete Fix Plan (plan only, no edits made)

This supersedes the earlier chat-only Phase B output, which was cut off mid-item. Everything below is the full, non-truncated plan. No code has been changed. No live Gemini/Groq calls were made. Verification facts cited below (Groq's upload limit) came from a web search done while writing this plan — marked explicitly where that applies.

Ordered by value: bugs/security first, style last.

---

## 1. Make `gemini-3.1-flash-lite` the project default Gemini model

*(your new item — also fixes Phase A finding §4.1, the currently-failing test, since both touch the same hardcoded string)*

**Files, smallest change each:**

- **`app/core/config.py`** — `gemini_model: str = "gemini-3.8-flash"` → `"gemini-3.1-flash-lite"` (1 line).
- **`app/features/llm/gemini.py`** — the fallback literal (`resolved_model = "gemini-3.8-flash"`) and the warning string (`"GEMINI_MODEL is empty - falling back to gemini-3.8-flash"`) both → `gemini-3.1-flash-lite` (2 lines, must match exactly — the warning text is asserted verbatim by `test_gemini_model_config.py:65`).
- **`.env.example`** — `GEMINI_MODEL=gemini-3.8-flash` → `GEMINI_MODEL=gemini-3.1-flash-lite`; comment updated to state the quota numbers you verified yourself (Google AI Studio rate-limit page): `gemini-3.8-flash` = 20 requests/day free tier; `gemini-3.1-flash-lite` = 500 requests/day, 15/min.
- **`.env.docker.example`** — currently has **no** `GEMINI_MODEL` or `LLM_PRIMARY_PROVIDER` line at all (confirmed by reading the file — it jumps straight from `BACKUP_LLM_API_KEY=` to the STT section). Plan adds both lines here, matching `.env.example`'s new values and comment.
- **`tests/test_gemini_logging.py:57`** — `assert "gemini-3.8-flash" in line` → add `monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")` at the top of `test_usage_metadata_present_logs_token_counts` (matching the pattern `test_gemini_model_config.py` already uses) and update the asserted string to match. This is the fix for the test that's failing right now against your real `.env`.
- **`tests/test_gemini_model_config.py:41,43,63,65`** — these 4 lines are the 2 tests (T1 and T4) that specifically assert *the default's* literal value (`"gemini-3.8-flash"`), not an arbitrary override value like `"some-other-model"`. Update all 4 to `"gemini-3.1-flash-lite"`, including the exact warning-text assertion on line 65.
- **`scripts/probe_gemini_models.py:3`** — docstring currently calls `gemini-3.8-flash` "the rate-limited default." Update wording to name `gemini-3.1-flash-lite` as the new default, and `gemini-3.8-flash` as the original/now-replaced one. `CANDIDATE_MODELS` list stays both entries (`gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`), but add a comment marking which one is now the default (`gemini-3.1-flash-lite`) vs. the one that already failed with a live `400` in your probe (`gemini-3.5-flash-lite`).
- **`BUILD_LOG.md`** — add a new dated entry stating: default changed to `gemini-3.1-flash-lite`; `gemini-3.5-flash-lite` returned a live `400 Bad Request` (`ClientError`) with `thinking_config=ThinkingConfig(thinking_budget=0)` in your probe/live test on 2026-11-16; `gemini-3.8-flash` is capped at 20 requests/day on the free tier (source: your own Google AI Studio rate-limit page check).
- **`CLAUDE.md`** (project root, `ai_outward/CLAUDE.md`) — **confirmed this file does not currently exist anywhere in the repo.** Plan creates it, containing the same three facts as the `BUILD_LOG.md` entry above, so a future session doesn't have to rediscover them from scratch.

**Explicitly NOT touched:** `.env`, `.env.docker` (the real files) — per your standing rule, untouched regardless of this change.

**Risk:** Low-to-medium.
- *Low* because every change is a literal-string swap or a new doc/env-example line — no control flow, no new logic, no new dependency.
- *Medium* because it's a real, user-visible behavior change for anyone relying on the unset default (see below) — the risk isn't "this could break," it's "this deliberately changes what model real traffic goes to."

**Test proving the fix:** full `pytest -q` → expect **117/117** (currently 116/117 — the 1 failure in `test_gemini_logging.py` closes). The 2 corrected assertions in `test_gemini_model_config.py` and the new monkeypatch line in `test_gemini_logging.py` are run individually too, to confirm they pass against the *new* default itself, not incidentally against whatever happens to be sitting in real `.env` at the time.

**Behavior change — explicit:**
- Anyone who has never set `GEMINI_MODEL` in their own `.env` now gets **`gemini-3.1-flash-lite` instead of `gemini-3.8-flash`** the moment they pull this change and restart. This includes a fresh clone of the repo, a new teammate's machine, or any Docker deployment using `.env.docker.example` as a starting point.
- **What could go wrong:** `gemini-3.1-flash-lite` is, as of this plan, untested by you on Hindi/Marathi — your manual testing so far has been English only. Lite models generally trade some accuracy for speed/cost; if Hindi/Marathi transliteration quality (proper nouns, numbers-as-words, Devanagari-script answers) degrades versus `gemini-3.8-flash`, nothing in the current automated test suite would catch it, since every extraction test uses a fake LLM client with canned responses — the suite tests the *pipeline*, not model quality. Recommend you manually verify at least one Hindi and one Marathi submission before trusting this as the new default, separately from the English testing already underway.
- Your own `.env` already has `GEMINI_MODEL=gemini-3.1-flash-lite` set explicitly (added earlier this session), so this change has **no effect on your running instance** either way — it only changes behavior for anyone/anything relying on the unset default.

---

## 2. `unloading_time` has no sequence validation (Phase A §1.1 — BUG)

**File:** `app/features/conversation/service.py`, lines ~255-270 (the block that calls `validate_time_sequence`).

**What's wrong, with evidence:**
```python
if "vehicle_in_time" in answers and "vehicle_out_time" in answers:
    out_label = get_field("vehicle_out_time").localized_label(language)
    in_label = get_field("vehicle_in_time").localized_label(language)
    seq = validate_time_sequence(
        answers["vehicle_in_time"], answers["vehicle_out_time"], in_label, out_label, language,
    )
    ...
```
Only `vehicle_in_time` and `vehicle_out_time` are cross-checked. `unloading_time` — the third time field, asked in the order In → Out → Unloading per `fields.py:74-78` — is never validated against either of the other two. A submission with `vehicle_in_time=14:00`, `vehicle_out_time=17:00`, `unloading_time=23:00` is accepted as-is today, with no error, no clarification prompt, nothing.

**Smallest change:** after the existing `vehicle_in_time < vehicle_out_time` check succeeds, add one more `validate_time_sequence` call (the function already exists and is generically reusable — no new validator needed) cross-checking `unloading_time` against the other two, using whatever ordering rule you confirm.

**Risk:** Low to implement once the rule is known; the only real risk is implementing the *wrong* rule and rejecting valid real-world timings.

**Test:** a new case in `test_conversation_flow.py`, mirroring the existing `test_time_sequence_validation_rejects_out_before_in`, with an out-of-order `unloading_time` relative to whatever rule is confirmed.

**Visible behavior change:** yes — a submission that is silently accepted today (an `unloading_time` with no relation to In/Out time) would be rejected and re-asked, once the rule is implemented.

**STATUS: not implementing yet.** Per your instruction, you're confirming the actual business rule yourself (is it `in ≤ unloading ≤ out`? Is unloading allowed to be after the vehicle has notionally "left"? Your warehouse process decides this, not the code) — no code will be written for this item until you say what the rule is.

---

## 3. `JWT_SECRET` placeholder must refuse to start, not just warn

*(upgraded per your instruction — this was previously a "log a warning" item; now a hard refusal)*

**File:** `app/main.py` (the `lifespan()` startup block, alongside the existing `connect_to_mongo()`/`connect_to_redis()` calls) or `app/core/config.py` (a validator on the `Settings` class itself — slightly preferred, since it fails at the earliest possible point, before any connection attempt).

**What it does:** at startup, if `settings.jwt_secret == "change-me-to-a-long-random-string"` **and** `settings.environment != "development"`, raise immediately and refuse to start the app — not a warning log that can be scrolled past, a hard failure. In `development`, allow it through (so local work isn't blocked), but still log a visible warning so it's not silently ignored even there.

**Never prints the value either way** — the check is an equality comparison against the known placeholder literal, never logs `settings.jwt_secret` itself in any branch (matching the project's standing rule on secrets).

**How tests should handle it:** every test that boots the real app (`conftest.py`'s `client` fixture, which uses the real `TestClient(app)` lifespan) would hit this check too. Since `pytest`'s run almost certainly has `ENVIRONMENT` unset or `development` in the test environment already (matching real `.env`), this should pass through unaffected — but the plan adds one explicit test for this, in `conftest.py` or a new `test_startup_checks.py`:
- a test that monkeypatches `settings.environment = "production"` and `settings.jwt_secret` to the placeholder, and asserts startup raises;
- a test that does the same with `environment = "development"` and confirms startup succeeds (just with the warning logged, checked via `caplog`);
- a test with a real (non-placeholder) secret and `environment = "production"` confirming startup succeeds normally.

**How Docker setups should handle it:** `.env.docker.example` already ships `JWT_SECRET=change-me-to-a-long-random-string` as a placeholder, and `.env.docker.example`'s header comment should gain one line stating that `ENVIRONMENT` must be set to something other than `development` for this placeholder-refusal check to apply, and that `docker-compose.yml`'s production deployment path **must** override `JWT_SECRET` with a real generated value before `ENVIRONMENT=production` is set — otherwise the container will refuse to start (by design). This is a deliberate, visible failure instead of a silently-forgeable-token production deployment.

**Risk:** Low-medium. Low because it only changes behavior for the specific combination of "production + never-changed placeholder," which should never be a real deployment state anyway. Medium only in the sense that if you *do* have a real deployment currently running with `ENVIRONMENT=production` and the placeholder secret (unlikely, but unverified from here), this would intentionally stop it from restarting until fixed — which is the point, but worth you confirming that's not your current Docker state before this lands.

**Test proving the fix:** the 3 new tests above; full suite still green otherwise.

**Visible behavior change:** only for a production-environment boot with the never-changed placeholder secret — refuses to start instead of running insecurely. No effect on your current dev setup (which only needs the warning, not the refusal, under this rule).

---

## 4. Input-guard length cap — worst-case derivation

**File:** `app/features/guardrails/input_guard.py:5` (`MAX_LENGTH`, raised from 500 to 1000 earlier today).

**Deriving a number, instead of picking one empirically:**

Known facts used below:
- There are **18 fields** (`fields.py:56-79`).
- A real test submission today, in English, covering essentially all 18 fields with realistic verbose/filler human phrasing (including redundant phrasing like "the co-storage name is and storage name is Corale Global"), measured at **exactly 555 characters** — this was reproduced directly (`len()` on the actual pasted text), not estimated.
- Hindi and Marathi answers would be typed/transcribed in **Devanagari script**. Devanagari text commonly uses more Unicode codepoints per rendered syllable than English uses per rendered letter, because a single visual character (akshara) is frequently composed of a base consonant codepoint plus one or more combining vowel-sign (matra) codepoints — each of which counts separately under Python's `len()` (codepoint count, not grapheme-cluster count). This is a general property of the script, not something measured against this app's own real Hindi/Marathi transcripts (**UNVERIFIED against this project's actual data** — no real Hindi/Marathi test submission has been run and measured yet).

**Derivation:**
1. English baseline, all 18 fields, realistic verbose phrasing: **555 chars** (measured, not estimated).
2. Add headroom for a *more* verbose answer than today's sample (e.g. someone restating a field, or adding a brief aside) — a generous **+30%** buffer: 555 × 1.3 ≈ **722 chars**.
3. Apply a Devanagari script-expansion margin for Hindi/Marathi. Since no real sample exists for this project, this plan uses a commonly-cited conservative multiplier of **1.3-1.5×** for Devanagari vs. Latin-script codepoint counts (reflecting the base+matra composition above) — this specific multiplier is an **assumption, not a measurement**. Using 1.4× as a middle estimate: 722 × 1.4 ≈ **1011 chars**.

**Conclusion:** the derivation lands at **≈1000-1050 characters**, which is where `MAX_LENGTH` already sits after today's change (1000). This is a reasonable, non-arbitrary number given the assumptions stated — but the Devanagari multiplier is explicitly unverified against this project's real usage. Recommend: once you've done real Hindi/Marathi manual testing (which you're already doing for the model-quality question in Item 1), capture one real multi-field Devanagari submission and re-measure its actual character count, to replace the assumed 1.3-1.5× with a real number. No code change proposed here beyond what's already done — this item is the written derivation you asked for, confirming 1000 isn't an arbitrary guess, while flagging exactly which part of the math is still an assumption.

**Risk / Test / Behavior change:** none — no further code change proposed in this item.

---

## 5. Gemini `400` fallback decision — two options

**Context:** verified live today — `gemini-3.5-flash-lite` returned a real `400 Bad Request` (`ClientError`), which `chain.py`'s `_is_retryable()` correctly classifies as non-retryable, so `LLMChain` does **not** fall back to Groq, and the caller gets a `503`. This is today's actual, working behavior — the question is whether it's the *right* behavior for every kind of `400`.

**Option A — keep today's behavior: no Groq fallback on a `400` from the primary.**
- **Files:** none — this is "do nothing," listed as an explicit option rather than a silent default.
- **Reasoning for keeping it:** a `400` (`INVALID_ARGUMENT`) from Gemini usually means something is *wrong with the request itself* — a bad model id (exactly what happened today), a malformed prompt, an invalid parameter. Falling back to Groq on this class of error would silently paper over a configuration bug (e.g. a typo'd `GEMINI_MODEL`) by making Groq do all the work every time, with no visible signal that Gemini is actually broken, until someone notices the Gemini usage logs are all failures.
- **Risk of this option:** every `400` — including ones that are genuinely just "this specific request was malformed" rather than "the whole configuration is broken" — costs the user a full failed turn (`503`, "something went wrong," re-ask) instead of recovering via Groq. If `400`s are rare and mean "config is broken," this is correct; if they can happen per-request for reasons unrelated to config, this is overly strict.

**Option B — fall back to Groq on a `400` from the primary too, with a loud log.**
- **Files:** `app/features/llm/chain.py` (`_is_retryable()` or the caller's branching logic) — would need to special-case Gemini `400`s specifically (not all `400`s generically — Groq's own `400`s, if Groq were ever primary, likely mean something different) to still fall back, while logging at `ERROR` (not just `WARNING`, to stay loud) every time this happens, since it now masks a potentially broken primary.
- **Risk of this option:** every Gemini misconfiguration (wrong model id, bad API key format, etc.) now *looks like it's working* from the user's point of view — Groq quietly handles every turn — right up until Groq's own quota/outage hits too, at which point both fail simultaneously and the failure is much harder to diagnose, because by then nobody's been looking at Gemini's logs (it's been "working" via silent fallback for however long). This directly trades user-facing reliability today for operator-visibility risk later.

**Not recommending a default here** — this is a product/ops tradeoff (user experience now vs. diagnosability later), not a pure code-correctness question, and genuinely depends on how often you expect a Gemini `400` to mean "real misconfiguration" vs. "one bad request." Your call for Phase C.

**Test, either option:** `test_llm_chain.py` would need a new end-to-end case (see Item 7 below) regardless of which option is chosen, confirming the actual chosen behavior.

---

## 6. `/speech/transcribe` upload limit

**File:** `app/features/speech/router.py:20` (`audio_bytes = audio.file.read()`).

**Why not `audio.size` alone:** `UploadFile.size` (when Starlette does populate it) reflects what the client *declared*, not a byte count independently enforced as data streams in — a malicious or buggy client could under-report it, or it may be `None` depending on how the multipart body was sent, so a check gated only on that field is not a hard guarantee.

**Smallest change — read in capped chunks instead:**
```python
MAX_UPLOAD_BYTES = ...  # see derivation below
chunks = []
total = 0
while True:
    chunk = audio.file.read(1024 * 1024)  # 1MB at a time
    if not chunk:
        break
    total += len(chunk)
    if total > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large")
    chunks.append(chunk)
audio_bytes = b"".join(chunks)
```
This enforces the cap against actual bytes received, not a client-declared field, regardless of what the client claims.

**Deriving the limit — typical 1-2 minute browser recording:**
- `frontend/src/hooks/useRecorder.js:32` constructs `new MediaRecorder(stream)` with **no explicit `audioBitsPerSecond`** — confirmed by reading the file directly — so the browser's own default bitrate applies, which varies by browser/codec (commonly in the 32-128 kbps range for Opus/WebM audio-only recording, per general browser behavior; the exact figure for whichever browser the operator uses was **not independently measured** in this session — **UNVERIFIED** against a real recorded file's actual size).
- Using that range: a 2-minute recording at 32 kbps ≈ 0.48 MB; at 128 kbps ≈ 1.92 MB. So a realistic 1-2 minute recording should land well under **2 MB** regardless of exact bitrate within that range.
- **Groq's documented limit** (verified via web search while writing this plan): Groq's speech-to-text docs state a **25 MB** file-size limit on the free tier (100 MB on their paid "dev" tier, though community reports describe inconsistent enforcement above 25 MB even on that tier) — source: [Groq speech-to-text docs](https://console.groq.com/docs/speech-to-text), discussed further in [this Groq community thread](https://community.groq.com/t/whisper-large-v3-returns-entity-too-large-with-37mb-audio-on-developer-plan/921).
- **Recommended cap:** something well above the realistic 1-2 minute use case (≈2 MB) but no higher than Groq's own enforced free-tier ceiling (25 MB) — e.g. **20 MB**, leaving headroom for a longer-than-typical recording or a noisier/higher-bitrate browser encoding, while still rejecting anything that would just fail at Groq anyway (or balloon memory use for the local-Whisper path, which has no provider-side cap at all).

**Risk:** Low — a guard that only ever rejects requests already far outside realistic use, or that were already going to fail downstream.

**Test:** a new test posting a fake upload just over the chosen cap (expect `413`), and one just under it (expect normal success), using a fake STT client so no real audio processing is needed.

**Visible behavior change:** none for realistic recordings (≈2 MB) — only affects uploads already abnormally large.

---

## 7. Groq 429 / Gemini-`400`-skip-fallback — end-to-end test gap

**File:** `tests/test_llm_chain.py`.

**Gap:** the existing parametrized tests (`test_httpx_rate_limit_and_server_errors_are_retryable`, `test_httpx_invalid_request_and_auth_errors_are_not_retryable`) test the `_is_retryable()` classifier function directly, in isolation — not an actual `GroqLLMClient.generate()` or `GeminiLLMClient.generate()` call raising a real error and being classified by the real `LLMChain.generate()` path end-to-end.

**Smallest change:** add 2 new tests using fake `LLMClient` subclasses that raise a real `httpx.HTTPStatusError` (429, matching Groq's shape) and a real `genai_errors.ClientError` (400, matching Gemini's shape) from inside `.generate()`, run through the actual `LLMChain.generate()`, confirming: the 429 case retries via backup and succeeds; the 400 case does **not** call backup at all (confirming today's Option A behavior from Item 5 — or whichever option is chosen there) and raises/propagates correctly.

**Risk:** None — test-only, no production code change.

**Visible behavior change:** none.

---

## 8. Extraction value handling — rewritten per your check

**Your question:** show the exact file/line where a `KeyError` can occur, or rewrite the item around the real risk.

**Finding: there is no `KeyError` risk.** Read `app/features/extraction/router_msi.py` directly, in full: every single access into the parsed LLM JSON response uses `.get(...)` — `parsed.get("value")`, `parsed.get("ambiguous", False)`, `parsed.get("display_value")` (lines 42-45), `parsed.get(key)` for batch entries (line 73), `entry.get("value")`/`entry.get("ambiguous", False)`/`entry.get("display_value")` (lines 78-81), `parsed.get("field_key")`/`parsed.get("value")` for corrections (lines 111, 118). None of this code ever uses `parsed["..."]` bracket access anywhere. So a missing key never raises — it just produces `None`, exactly like a present-but-null value would.

**What's actually at risk — a wrong *type*, not a missing key:**

Traced the full downstream path for what happens when `extracted.value` is a **list or dict** instead of the expected `str`/`number`, since the LLM is not schema-enforced and nothing stops it from returning e.g. `{"value": ["Ravi"], ...}` instead of `{"value": "Ravi", ...}`:

- **`validate_number`** (`app/features/validation/validators.py:53-56`): `float(value)` on a list/dict raises `TypeError`, which is caught (`except (TypeError, ValueError)`) and returns a clean `ValidationResult(valid=False, "must_be_number")`. **No crash** — handled correctly already.
- **`validate_vehicle_number`** (`validators.py:76`) and **`validate_time`** (`validators.py:90`): both call `str(value).strip()...` then regex-match; a stringified list/dict (e.g. `"['Ravi']"`) simply fails the regex and is cleanly rejected. **No crash.**
- **`validate_text`** (`validators.py:17-44`, used for every free-text field: `labor_name`, `driver_name`, `cold_storage_name`, `cold_storage_supervisor_name`, `line_supervisor_name`, `container_number`, and `company_name`/`brand` when `allowed_values` is set): `stripped = str(value).strip()`. `str()` **never raises**, regardless of input type. For a closed-set field (`allowed_values` set), the stringified garbage then fails the `allowed_values` check and is cleanly rejected — still no crash. **But for an *open* free-text field with no `allowed_values`** (`labor_name`, `driver_name`, `cold_storage_name`, `cold_storage_supervisor_name`, `line_supervisor_name`, `container_number`), there is no such check: `str(["Ravi"])` → `"['Ravi']"` passes validation as a normal string and is **silently stored as corrupted data** — no error, no crash, no clarification re-ask, just a wrong-looking value saved to MongoDB (e.g. `labor_name: "['Ravi']"` instead of `labor_name: "Ravi"`).

**Revised item:** this is a **silent-data-corruption risk for open free-text fields**, not a crash risk anywhere in the pipeline. Fix: in `extract_field`/`extract_batch` (`router_msi.py`), after getting `value` from the parsed response, reject (treat as `ambiguous=True`, same as a parse failure) if `value` is present but isn't one of `str | int | float | None` — i.e. explicitly disallow `list`/`dict` before it ever reaches validation, rather than letting `validate_text`'s permissive `str()` silently accept it.

**Files:** `app/features/extraction/router_msi.py` (`extract_field`, `extract_batch`, `extract_correction` — all three construct `ExtractedField`/`ExtractedCorrection` from the same `.get()` pattern and would need the same guard).

**Risk:** Low — the guard only tightens behavior for a case (non-scalar `value`) that was never a valid/intended outcome in the first place.

**Test:** a new fake-LLM test per function, returning `{"value": ["Ravi"], ...}` and confirming the result comes back `ambiguous=True`/`value=None` instead of a stringified list.

**Visible behavior change:** a case that silently stored corrupted text today would instead be treated as "unclear, please repeat" — strictly an improvement, no legitimate case was found that would newly break.

---

## 9. `BUILD_LOG.md` stale (Phase A §3.1 — RISK, doc-trust)

**File:** `BUILD_LOG.md`.

**Smallest change:** one consolidated "catch-up" entry (separate from the Item 1-specific entry above) listing: the real current field list (18 fields, with their actual current names — including the `line_mark`→`line_supervisor_name` rename and the removed `remarks`/`vehicle_for_storage`/`vehicle_receiver_name` fields), the STT provider split (`faster-whisper` local vs. Groq cloud, selected by `STT_PROVIDER`), the input-guard cap history (500 → 1000), and the `LLM_PRIMARY_PROVIDER`/Gemini-usage-logging additions from earlier this session.

**Risk:** None (docs only). **Test:** none applicable. **Visible behavior change:** none.

---

## 10. Closed-set near-miss test — **NOT RECOMMENDED**

*(Phase A §1.3 — per your instruction, marking this as not recommended rather than planning it.)*

**Reasoning for not recommending:** a test that only confirms "if the fake LLM returns the correctly-matched value, downstream accepts it" doesn't actually test the thing worth testing (whether the *real* LLM's fuzzy-matching is accurate on a real near-miss like "Corale" vs. "Khorale") — that requires a live call, which is explicitly out of scope without your approval, and even then would just be one anecdotal data point, not a regression-proof test. The fake-LLM version would pass trivially regardless of real model behavior, giving false confidence rather than real coverage. Not worth the effort for what it actually proves.

---

## Recommended NOT to fix (style-only, working/tested code, cosmetic only — unchanged from the earlier plan)

- **Dead single-field `/answer` path** (Phase A §2.1) — still tested, still reachable via direct API call/Swagger; removing it is a bigger, riskier change than this plan warrants unless you specifically want the API surface reduced.
- **Unused `fakeredis`/`mongomock` in `requirements.txt`** (Phase A §2.2) — already self-documented as "kept on purpose" in `BUILD_LOG.md`; removing saves nothing functionally.
- **Duplicated extraction pipeline** between `conversation/service.py` and `submissions/service.py` (Phase A §2.3) — explicitly a deliberate tradeoff per `BUILD_LOG.md` Step 15; de-duplicating risks coupling two features kept intentionally independent.
- **Unprovable historical `BUILD_LOG.md` claims** (Phase A §4.2) — acceptable, already self-acknowledged as a manual-only verification gap in the log itself.

---

STOP — waiting for your "go" (and your confirmed `unloading_time` business rule for Item 2) before Phase C.
