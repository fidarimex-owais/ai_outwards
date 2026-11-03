import { useState } from "react";
import InputBar from "./InputBar";
import { t } from "../services/i18n";
import "./SummaryActions.css";

export default function SummaryActions({ onConfirm, onCorrect, disabled, onTranscribe, language = "en" }) {
  const [correcting, setCorrecting] = useState(false);

  if (correcting) {
    return (
      <div className="summary-actions">
        <InputBar
          placeholder={t(language, "correctionPlaceholder")}
          disabled={disabled}
          onTranscribe={onTranscribe}
          language={language}
          onSend={(text) => {
            onCorrect(text);
          }}
        />
        <button type="button" className="link-btn" onClick={() => setCorrecting(false)}>
          {t(language, "cancel")}
        </button>
      </div>
    );
  }

  return (
    <div className="summary-actions">
      <button type="button" className="primary-btn" onClick={onConfirm} disabled={disabled}>
        {t(language, "confirmSave")}
      </button>
      <button type="button" className="link-btn" onClick={() => setCorrecting(true)} disabled={disabled}>
        {t(language, "correctAField")}
      </button>
    </div>
  );
}
