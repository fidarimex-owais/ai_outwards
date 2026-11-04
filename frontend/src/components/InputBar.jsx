import { forwardRef, useCallback, useImperativeHandle, useRef, useState } from "react";
import { useRecorder } from "../hooks/useRecorder";
import { t } from "../services/i18n";
import Waveform from "./Waveform";
import "./InputBar.css";

// onTranscribe(blob) -> Promise<{ text, needs_repeat }>. Transcription never auto-submits -
// it only ever fills the text field for you to review/edit; onSend(text) is the only path
// that actually submits an answer, and only fires when you click Send (or press Enter).
const InputBar = forwardRef(function InputBar(
  { onSend, onTranscribe, disabled, placeholder, language = "en" },
  ref
) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState("idle"); // "idle" | "starting" | "recording" | "transcribing"
  const [error, setError] = useState("");
  const volumeRef = useRef(0);
  const recorder = useRecorder();

  const getVolume = useCallback(() => volumeRef.current, []);

  // Exposed so a parent can drop an in-progress recording from the actual event that calls
  // for it (e.g. Clear Chat / New Entry resets this same InputBar instance without unmounting
  // it) - an explicit call from that event, not a useEffect guessing at "disabled changed".
  useImperativeHandle(ref, () => ({
    stopRecording() {
      if (recorder.isRecording) {
        recorder.stop({ cancel: true });
        setMode("idle");
      }
    },
  }));

  async function handleMicClick() {
    if (mode !== "idle") return; // ignore a duplicate/rapid click - already starting/recording/busy
    // Claim the slot synchronously, before the async getUserMedia call below - `mode` only
    // becomes "recording" once that call resolves, so without this, a second click fired
    // while the first is still pending would also see "idle" and start a second recording.
    setMode("starting");
    setError("");
    try {
      await recorder.start((rms) => {
        volumeRef.current = rms;
      });
      setMode("recording");
    } catch (err) {
      setMode("idle");
      setError(t(language, "micDenied") + err.message);
    }
  }

  async function handleCancel() {
    await recorder.stop({ cancel: true });
    setMode("idle");
  }

  async function handleStop() {
    const blob = await recorder.stop();
    setMode("transcribing");
    if (!blob) {
      setMode("idle");
      return;
    }
    try {
      const result = await onTranscribe(blob);
      setMode("idle");
      if (result.text?.trim()) {
        setText(result.text);
      } else {
        setError(t(language, "didntCatch"));
      }
    } catch (err) {
      setMode("idle");
      setError(err.message);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <div className="input-bar-wrap">
      {mode === "idle" || mode === "starting" ? (
        <form className="input-row" onSubmit={handleSubmit}>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder || t(language, "typeAnswer")}
            disabled={disabled || mode === "starting"}
            autoComplete="off"
          />
          <button
            type="button"
            className="icon-btn"
            title="Record"
            onClick={handleMicClick}
            disabled={disabled || mode === "starting"}
          >
            🎙️
          </button>
          <button type="submit" className="icon-btn send-icon-btn" title="Send" disabled={disabled || !text.trim()}>
            ➤
          </button>
        </form>
      ) : (
        <div className="input-row recording-row">
          <button type="button" className="icon-btn" title="Cancel" onClick={handleCancel}>
            ✕
          </button>
          <Waveform active={mode === "recording"} getVolume={getVolume} />
          <button type="button" className="icon-btn stop-icon-btn" title="Stop" onClick={handleStop}>
            ■
          </button>
        </div>
      )}
      <div className="input-status-hint">
        {mode === "recording" && t(language, "listening")}
        {mode === "transcribing" && t(language, "transcribing")}
        {error && <span className="input-error">{error}</span>}
      </div>
    </div>
  );
});

export default InputBar;
