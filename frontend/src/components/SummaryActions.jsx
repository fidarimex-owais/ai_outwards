import { useState } from "react";
import InputBar from "./InputBar";
import "./SummaryActions.css";

export default function SummaryActions({ onConfirm, onCorrect, disabled, onTranscribe }) {
  const [correcting, setCorrecting] = useState(false);

  if (correcting) {
    return (
      <div className="summary-actions">
        <InputBar
          placeholder='e.g. "Correct the labor name to Sagar Panidrahi"'
          disabled={disabled}
          onTranscribe={onTranscribe}
          onSend={(text) => {
            onCorrect(text);
          }}
        />
        <button type="button" className="link-btn" onClick={() => setCorrecting(false)}>
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="summary-actions">
      <button type="button" className="primary-btn" onClick={onConfirm} disabled={disabled}>
        Confirm &amp; Save
      </button>
      <button type="button" className="link-btn" onClick={() => setCorrecting(true)} disabled={disabled}>
        Correct a field
      </button>
    </div>
  );
}
