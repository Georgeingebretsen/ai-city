import { useEffect, useRef, useMemo } from "react";
import { agentColor } from "../constants";

export default function Chat({ messages, agents }) {
  const bottomRef = useRef(null);

  const colorMap = useMemo(() => {
    const map = {};
    (agents || []).forEach((a, i) => {
      map[a.name] = agentColor(i);
    });
    return map;
  }, [agents]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  return (
    <div className="panel chat-panel">
      <h2>Chat</h2>
      <div className="chat-messages">
        {messages.length === 0 && <p className="empty">No messages yet</p>}
        {messages.map((m) => (
          <div key={m.id} className="chat-msg">
            <span className="chat-agent" style={{ color: colorMap[m.agent] }}>{m.agent}</span>
            <span className="chat-text">{m.content}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
