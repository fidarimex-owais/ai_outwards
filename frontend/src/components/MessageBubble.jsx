import "./MessageBubble.css";

export default function MessageBubble({ role, text }) {
  return <div className={`bubble bubble-${role}`}>{text}</div>;
}
