import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble";
import "./ChatThread.css";

export default function ChatThread({ messages }) {
  const threadRef = useRef(null);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  return (
    <div className="chat-thread" ref={threadRef}>
      {messages.map((m) => (
        <MessageBubble key={m.id} role={m.role} text={m.text} />
      ))}
    </div>
  );
}
