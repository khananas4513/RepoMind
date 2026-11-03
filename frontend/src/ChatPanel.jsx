import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

// [src/flask/app.py:1369-1378] or [src/flask/app.py:1380]
const CITE = /\[([\w./-]+\.\w+):(\d+)(?:-(\d+))?\]/g;

const SUGGESTIONS = [
  "Which files should I read first to understand this repo?",
  "How is the main entry point wired together?",
  "Where is configuration loaded?",
];

function linkCitations(text) {
  return text.replace(CITE, (_, path, a, b) =>
    `[${path.split("/").pop()}:${a}${b ? "-" + b : ""}](#cite=${encodeURIComponent(path)}&start=${a}&end=${b || a})`);
}

function Answer({ text, onCite, paths }) {
  const md = useMemo(() => linkCitations(text), [text]);
  return (
    <div className="md">
      <ReactMarkdown
        components={{
          // `src/app.py` written as inline code becomes a button when it is a file we analyzed
          code: ({ className, children }) => {
            const t = String(children).trim();
            if (!className && !t.includes("\n") && paths.has(t)) {
              return <button className="cite" onClick={() => onCite({ path: t, start: 0, end: 0 })}>{t}</button>;
            }
            return <code className={className}>{children}</code>;
          },
          a: ({ href, children }) => {
            if (href && href.startsWith("#cite=")) {
              const p = new URLSearchParams(href.slice(1));
              return (
                <button className="cite"
                  onClick={() => onCite({ path: p.get("cite"), start: +p.get("start"), end: +p.get("end") })}>
                  {children}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
          },
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}

export default function ChatPanel({ messages, busy, level, onLevel, onSend, onCite, ready, paths }) {
  const [text, setText] = useState("");
  const end = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  function send(question) {
    const q = (question ?? text).trim();
    if (!q || busy || !ready) return;
    setText("");
    onSend(q);
  }

  return (
    <div className="chat">
      <div className="chat-head">
        <label>Explain at{" "}
          <select value={level} onChange={(e) => onLevel(e.target.value)}>
            <option value="auto">auto (adapts to you)</option>
            <option value="beginner">beginner</option>
            <option value="intermediate">intermediate</option>
            <option value="expert">expert</option>
          </select>
        </label>
      </div>

      <div className="chat-body">
        {!ready && <p className="muted pad">Analyze a repository first, then ask questions about it.</p>}
        {ready && messages.length === 0 && (
          <div className="suggest">
            <p className="muted">Ask anything about this codebase. Try:</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggest-btn" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant" ? (
              <>
                <Answer text={m.text} onCite={onCite} paths={paths} />
                <div className="sources">
                  <span className="muted small">Retrieved code (click to open):</span>
                  {m.sources.map((s, j) => (
                    <button key={j} className="cite"
                      onClick={() => onCite({ path: s.path, start: s.start, end: s.end })}>
                      {s.path.split("/").pop()}:{s.start}-{s.end}
                    </button>
                  ))}
                </div>
                <div className="muted small">Explained at {m.level} level</div>
              </>
            ) : (
              <div>{m.text}</div>
            )}
          </div>
        ))}
        {busy && <div className="msg assistant"><span className="spinner" /> Searching the code and thinking…</div>}
        <div ref={end} />
      </div>

      <div className="chat-input">
        <textarea
          rows={2}
          value={text}
          placeholder={ready ? "Ask about the code…  (Enter to send)" : "Analyze a repository first"}
          disabled={!ready || busy}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
        />
        <button className="primary" disabled={!ready || busy || !text.trim()} onClick={() => send()}>Send</button>
      </div>
    </div>
  );
}