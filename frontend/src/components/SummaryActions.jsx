import { useState } from "react";
import InputBar from "./InputBar";
import "./SummaryActions.css";

const FIELD_LABELS = [
  ["company_name", "Company Name"], ["vehicle_number", "Vehicle Number"], ["brand", "Brand"],
  ["line_mark", "Line Mark"], ["weight", "Weight"], ["four_hand", "Four-Hand Quantity"],
  ["five_hand", "Five-Hand Quantity"], ["six_hand", "Six-Hand Quantity"], ["eight_hand", "Eight-Hand Quantity"],
  ["cluster", "Cluster Quantity"], ["remarks", "Remarks"], ["labor_name", "Labor Name"],
  ["vehicle_out_time", "Vehicle Out Time"], ["vehicle_in_time", "Vehicle In Time"],
  ["vehicle_for_storage", "Vehicle for Storage"], ["vehicle_receiver_name", "Vehicle Receiver Name"],
];

export default function SummaryActions({ onConfirm, onCorrect, disabled, onTranscribe }) {
  const [correcting, setCorrecting] = useState(false);
  const [fieldKey, setFieldKey] = useState(FIELD_LABELS[0][0]);

  if (correcting) {
    return (
      <div className="summary-actions">
        <select value={fieldKey} onChange={(e) => setFieldKey(e.target.value)} disabled={disabled}>
          {FIELD_LABELS.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <InputBar
          placeholder="Correction for this field..."
          disabled={disabled}
          onTranscribe={onTranscribe}
          onSend={(text) => {
            onCorrect(fieldKey, text);
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
