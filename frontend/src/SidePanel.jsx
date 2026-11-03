import { useEffect, useMemo, useRef } from "react";

const MAX_LINES = 4000;

function FileList({ title, items, onSelect, limit = 8 }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="block">
      <h4>{title}</h4>
      <ul className="files">
        {items.slice(0, limit).map((p) => (
          <li key={p}><button className="link" onClick={() => onSelect(p)}>{p}</button></li>
        ))}
        {items.length > limit && <li className="more">+ {items.length - limit} more</li>}
      </ul>
    </div>
  );
}

export function CodeView({ file, highlight }) {
  const ref = useRef(null);
  const lines = useMemo(() => file.content.split("\n").slice(0, MAX_LINES), [file]);

  useEffect(() => {
    if (!highlight || !ref.current) return;
    ref.current.querySelector(`[data-line="${highlight.start}"]`)?.scrollIntoView({ block: "center" });
  }, [file, highlight]);

  return (
    <div className="code" ref={ref}>
      {lines.map((text, i) => {
        const n = i + 1;
        const hl = highlight && n >= highlight.start && n <= highlight.end;
        return (
          <div key={n} data-line={n} className={hl ? "line hl" : "line"}>
            <span className="ln">{n}</span>
            <span className="tx">{text || " "}</span>
          </div>
        );
      })}
    </div>
  );
}

function Overview({ report, onSelect }) {
  if (!report) return null;
  const top = (report.most_important || []).map(([p]) => p);
  const imported = (report.most_imported || []).map(([p]) => p);
  const cycles = report.cycles || [];
  return (
    <div className="overview">
      <p className="hint">Click a node in the graph to see its code and what depends on it.</p>
      <FileList title="Most important files (PageRank)" items={top} onSelect={onSelect} />
      <FileList title="Most imported files" items={imported} onSelect={onSelect} />
      <div className="block">
        <h4>Circular dependencies</h4>
        {cycles.length === 0 ? (
          <p className="muted">None found.</p>
        ) : (
          cycles.map((group, i) => (
            <p key={i} className="muted">
              Group of {group.length} files, e.g. {group.slice(0, 2).join(", ")}
            </p>
          ))
        )}
        <p className="muted small">Includes imports used only for type hints, so some cycles are harmless.</p>
      </div>
    </div>
  );
}

export default function SidePanel({ selected, impact, file, highlight, report, onSelect, onClose }) {
  if (!selected) return <aside className="side"><Overview report={report} onSelect={onSelect} /></aside>;

  return (
    <aside className="side">
      <div className="side-head">
        <span className="path" title={selected}>{selected}</span>
        <button className="icon" onClick={onClose} aria-label="Close">×</button>
      </div>

      {impact && (
        <div className="impact">
          <div className="stat"><b>{impact.direct.length}</b><span>import it directly</span></div>
          <div className="stat"><b>{impact.total}</b><span>files affected if it changes</span></div>
          <div className="stat"><b>{impact.tests.length}</b><span>tests to re-run</span></div>
        </div>
      )}
      {impact && <FileList title="Imported directly by" items={impact.direct} onSelect={onSelect} limit={5} />}
      {impact && <FileList title="Tests to re-run" items={impact.tests} onSelect={onSelect} limit={4} />}

      {file ? <CodeView file={file} highlight={highlight} /> : <p className="muted pad">Loading code…</p>}
    </aside>
  );
}