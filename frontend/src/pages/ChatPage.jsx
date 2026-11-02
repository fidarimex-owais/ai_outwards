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
import { formatSubmission, groupedQuestionsBody } from "../services/formatters";
import "./ChatPage.css";

const SESSION_KEY = "vda_session_id";
let nextMessageId = 1;

export default function ChatPage({ token, username, onLogout }) {
  const [messages, setMessages] = useState([]);
  const [turn, setTurn] = useState(null); // last TurnResponse from the backend
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const sessionIdRef = useRef(sessionStorage.getItem(SESSION_KEY));

  const addMessage = useCallback((role, text) => {
    setMessages((prev) => [...prev, { id: nextMessageId++, role, text }]);
  }, []);

  const describeTurn = useCallback((t) => {
    if (t.state === "PAUSED") {
      return "Something went wrong processing your last answer. I've saved your progress - click Try Again when you're ready.";
    }
    if (t.state === "AWAITING_CONFIRMATION" && t.summary) {
      return t.summary;
    }
    if (t.state === "COMPLETED") {
      return "✅ Saved!\n\n" + (t.summary || "Your entry has been submitted.");
    }
    if (t.state === "COLLECTING" || t.state === "CLARIFICATION") {
      const questions = t.questions || [];
      const answered = t.answered_field_keys || [];
      const parts = [];
      if (t.clarification_prompt) parts.push(t.clarification_prompt);
      if (questions.length > 0) {
        const intro =
          answered.length === 0
            ? "Please answer the following questions - you can type or record them all together:"
            : "I still need a few things - please answer these together:";
        parts.push(`${intro}\n\n${groupedQuestionsBody(questions)}`);
      }
      return parts.join("\n\n") || "Please continue.";
    }
    return "Please continue.";
  }, []);

  const applyTurn = useCallback(
    (t, { silent = false } = {}) => {
      setTurn(t);
      if (!silent) addMessage("assistant", describeTurn(t));
      if (t.state === "COMPLETED") {
        sessionStorage.removeItem(SESSION_KEY);
        sessionIdRef.current = null;
      }
    },
    [addMessage, describeTurn]
  );

  // Boot: resume an existing session if one exists, otherwise start a brand-new one. A new
  // conversation shows all 16 questions; a resumed one restores exactly where it left off.
  useEffect(() => {
    let cancelled = false;
    async function boot() {
      setBusy(true);
      try {
        if (sessionIdRef.current) {
          addMessage("system", "Resuming your session...");
          const t = await getSession(token, sessionIdRef.current);
          if (!cancelled) applyTurn(t);
        } else {
          const t = await createSession(token);
          if (cancelled) return;
          sessionIdRef.current = t.session_id;
          sessionStorage.setItem(SESSION_KEY, t.session_id);
          applyTurn(t);
        }
      } catch (bootErr) {
        if (bootErr instanceof ApiError && bootErr.status === 401) {
          // The token itself is invalid/expired - retrying would just 401 again. Log out
          // cleanly instead of masking it as a session problem.
          onLogout();
          return;
        }
        // stale/expired session id - drop it and start a fresh conversation
        sessionStorage.removeItem(SESSION_KEY);
        sessionIdRef.current = null;
        try {
          const t = await createSession(token);
          if (cancelled) return;
          sessionIdRef.current = t.session_id;
          sessionStorage.setItem(SESSION_KEY, t.session_id);
          applyTurn(t);
        } catch (err) {
          if (!cancelled) setError(err.message);
        }
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

  async function handleTranscribe(blob) {
    return transcribeAudio(token, blob);
  }

  async function handleSend(text) {
    if (!sessionIdRef.current) return;
    setError("");
    addMessage("user", text);
    setBusy(true);
    try {
      const t = await submitBatchAnswer(token, sessionIdRef.current, text);
      applyTurn(t);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        const t = { state: "PAUSED" };
        applyTurn(t);
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
      const t = await resumeSession(token, sessionIdRef.current);
      applyTurn(t);
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
      const submission = await confirmSession(token, sessionIdRef.current);
      applyTurn({ state: "COMPLETED", summary: formatSubmission(submission) });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleCorrect(fieldKey, text) {
    setError("");
    addMessage("user", text);
    setBusy(true);
    try {
      const t = await correctField(token, sessionIdRef.current, fieldKey, text);
      applyTurn(t);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function handleNewEntry() {
    setMessages([]);
    sessionStorage.removeItem(SESSION_KEY);
    sessionIdRef.current = null;
    window.location.reload();
  }

  const state = turn?.state;

  return (
    <div className="chat-page">
      <header className="chat-header">
        <span className="chat-title">Voice Data Collection Assistant</span>
        <div className="chat-header-right">
          <span className="chat-username">{username}</span>
          <button type="button" className="link-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      </header>

      <ChatThread messages={messages} />

      {error && <div className="chat-error">{error}</div>}

      {state === "PAUSED" && (
        <div className="summary-actions">
          <button type="button" className="primary-btn" onClick={handleResume} disabled={busy}>
            Try Again
          </button>
        </div>
      )}

      {state === "AWAITING_CONFIRMATION" && (
        <SummaryActions onConfirm={handleConfirm} onCorrect={handleCorrect} disabled={busy} onTranscribe={handleTranscribe} />
      )}

      {state === "COMPLETED" && (
        <div className="summary-actions">
          <button type="button" className="primary-btn" onClick={handleNewEntry}>
            Start Another Entry
          </button>
        </div>
      )}

      {(state === "COLLECTING" || state === "CLARIFICATION" || state === undefined) && (
        <InputBar onSend={handleSend} onTranscribe={handleTranscribe} disabled={busy} />
      )}
    </div>
  );
}
