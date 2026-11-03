import { useCallback, useEffect, useRef, useState } from "react";
import ChatThread from "../components/ChatThread";
import InputBar from "../components/InputBar";
import SummaryActions from "../components/SummaryActions";
import {
  ApiError,
  confirmSession,
  correctField,
  createSession,
  getSession,
  resumeSession,
  submitBatchAnswer,
  transcribeAudio,
} from "../services/api";
import { groupedQuestionsBody } from "../services/formatters";
import { LANGUAGES, t } from "../services/i18n";
import "./ChatPage.css";

const SESSION_KEY = "vda_session_id";
const LANGUAGE_KEY = "vda_language";
let nextMessageId = 1;

export default function ChatPage({ token, username, onLogout }) {
  const [messages, setMessages] = useState([]);
  const [turn, setTurn] = useState(null); // last TurnResponse from the backend
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState(sessionStorage.getItem(LANGUAGE_KEY) || null);
  const sessionIdRef = useRef(sessionStorage.getItem(SESSION_KEY));
  // Only a brand-new entry needs the picker - a resumed session already has a language fixed
  // server-side for its whole lifetime (see backend/app/features/conversation/repository.py).
  const [needsLanguage, setNeedsLanguage] = useState(!sessionIdRef.current && !language);

  const addMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { id: nextMessageId++, role, text }]);
  }, []);

  const describeTurn = useCallback((turnData) => {
    const lang = turnData.language || language || "en";
    if (turnData.state === "PAUSED") {
      return t(lang, "paused");
    }
    if (turnData.state === "AWAITING_CONFIRMATION" && turnData.summary) {
      return turnData.summary;
    }
    if (turnData.state === "COMPLETED") {
      return t(lang, "savedPrefix") + (turnData.summary || t(lang, "savedFallback"));
    }
    if (turnData.state === "COLLECTING" || turnData.state === "CLARIFICATION") {
      const questions = turnData.questions || [];
      const answered = turnData.answered_field_keys || [];
      const parts = [];
      if (turnData.clarification_prompt) parts.push(turnData.clarification_prompt);
      if (questions.length > 0) {
        const intro = answered.length === 0 ? t(lang, "intro") : t(lang, "stillNeed");
        parts.push(`${intro}\n\n${groupedQuestionsBody(questions)}`);
      }
      return parts.join("\n\n") || t(lang, "pleaseContinue");
    }
    return t(lang, "pleaseContinue");
  }, [language]);

  const applyTurn = useCallback(
    (turnData, { silent = false } = {}) => {
      setTurn(turnData);
      if (turnData.language) {
        setLanguage(turnData.language);
        sessionStorage.setItem(LANGUAGE_KEY, turnData.language);
      }
      if (!silent) addMessage("assistant", describeTurn(turnData));
      if (turnData.state === "COMPLETED") {
        sessionStorage.removeItem(SESSION_KEY);
        sessionIdRef.current = null;
      }
    },
    [addMessage, describeTurn]
  );

  const startNewSession = useCallback(
    async (chosenLanguage) => {
      const t = await createSession(token, chosenLanguage);
      sessionIdRef.current = t.session_id;
      sessionStorage.setItem(SESSION_KEY, t.session_id);
      applyTurn(t);
    },
    [token, applyTurn]
  );

  // Boot: resume an existing session if one exists. A brand-new conversation instead waits
  // for the language picker (see handleLanguageSelect) before creating a session, since the
  // language is fixed for the session's whole lifetime once chosen.
  useEffect(() => {
    if (!sessionIdRef.current) return;
    let cancelled = false;
    async function boot() {
      setBusy(true);
      try {
        addMessage("system", t(language || "en", "resuming"));
        const turnData = await getSession(token, sessionIdRef.current);
        if (!cancelled) applyTurn(turnData);
      } catch (bootErr) {
        if (bootErr instanceof ApiError && bootErr.status === 401) {
          // The token itself is invalid/expired - retrying would just 401 again. Log out
          // cleanly instead of masking it as a session problem.
          onLogout();
          return;
        }
        // stale/expired session id - drop it and fall back to the language picker
        sessionStorage.removeItem(SESSION_KEY);
        sessionIdRef.current = null;
        if (!cancelled) setNeedsLanguage(true);
      } finally {
        if (!cancelled) setBusy(false);
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLanguageSelect(code) {
    setNeedsLanguage(false);
    setLanguage(code);
    sessionStorage.setItem(LANGUAGE_KEY, code);
    setError("");
    setBusy(true);
    try {
      await startNewSession(code);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleTranscribe(blob) {
    return transcribeAudio(token, blob, language || "en");
  }

  async function handleSend(text) {
    if (!sessionIdRef.current) return;
    setError("");
    addMessage("user", text);
    setBusy(true);
    try {
      const turnData = await submitBatchAnswer(token, sessionIdRef.current, text);
      applyTurn(turnData);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        applyTurn({ state: "PAUSED", language });
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleResume() {
    setError("");
    setBusy(true);
    try {
      const turnData = await resumeSession(token, sessionIdRef.current);
      applyTurn(turnData);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    setError("");
    setBusy(true);
    try {
      // The localized summary already shown at AWAITING_CONFIRMATION hasn't changed - reuse
      // it rather than reformatting the raw submission response, which is English-only (see
      // backend/app/features/submissions/service.py) and would otherwise mix languages here.
      const previousSummary = turn?.summary;
      await confirmSession(token, sessionIdRef.current);
      applyTurn({ state: "COMPLETED", language, summary: previousSummary });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCorrect(text) {
    setError("");
    addMessage("user", text);
    setBusy(true);
    try {
      const turnData = await correctField(token, sessionIdRef.current, text);
      applyTurn(turnData);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function _startFreshConversation() {
    setError("");
    setTurn(null);
    setMessages([]);
    sessionStorage.removeItem(SESSION_KEY);
    sessionIdRef.current = null;
    setBusy(true);
    try {
      await startNewSession(language || "en");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function handleNewEntry() {
    // Nothing to lose here - the entry is already saved - so no confirmation needed, and the
    // language carries over rather than re-prompting for it every time.
    _startFreshConversation();
  }

  function handleClearChat() {
    if (!window.confirm(t(lang, "clearChatConfirm"))) return;
    _startFreshConversation();
  }

  const state = turn?.state;
  const lang = language || "en";

  return (
    <div className="chat-page">
      <header className="chat-header">
        <span className="chat-title">{t(lang, "chatTitle")}</span>
        <div className="chat-header-right">
          <span className="chat-username">{username}</span>
          {!needsLanguage && state !== "COMPLETED" && (
            <button type="button" className="link-btn" onClick={handleClearChat} disabled={busy}>
              {t(lang, "clearChat")}
            </button>
          )}
          <button type="button" className="link-btn" onClick={onLogout}>
            {t(lang, "logOut")}
          </button>
        </div>
      </header>

      {needsLanguage ? (
        <div className="language-picker">
          <p className="language-picker-title">{t("en", "chooseLanguage")}</p>
          <p className="language-picker-hint">{t("en", "chooseLanguageHint")}</p>
          <div className="language-picker-options">
            {LANGUAGES.map(({ code, label }) => (
              <button
                key={code}
                type="button"
                className="primary-btn"
                disabled={busy}
                onClick={() => handleLanguageSelect(code)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <>
          <ChatThread messages={messages} />

          {error && <div className="chat-error">{error}</div>}

          {state === "PAUSED" && (
            <div className="summary-actions">
              <button type="button" className="primary-btn" onClick={handleResume} disabled={busy}>
                {t(lang, "tryAgain")}
              </button>
            </div>
          )}

          {state === "AWAITING_CONFIRMATION" && (
            <SummaryActions
              onConfirm={handleConfirm}
              onCorrect={handleCorrect}
              disabled={busy}
              onTranscribe={handleTranscribe}
              language={lang}
            />
          )}

          {state === "COMPLETED" && (
            <div className="summary-actions">
              <button type="button" className="primary-btn" onClick={handleNewEntry}>
                {t(lang, "startAnother")}
              </button>
            </div>
          )}

          {(state === "COLLECTING" || state === "CLARIFICATION" || state === undefined) && (
            <InputBar onSend={handleSend} onTranscribe={handleTranscribe} disabled={busy} language={lang} />
          )}
        </>
      )}
    </div>
  );
}
