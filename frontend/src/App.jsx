import { useEffect, useRef, useState } from "react";
import { analyzeUrl, analyzeZip, askQuestion, getFile, getGraph, getImpact, getStatus } from "./api.js";
import GraphView from "./GraphView.jsx";
import SidePanel from "./SidePanel.jsx";
import ChatPanel from "./ChatPanel.jsx";
import { LEGENDS, LANGUAGE_COLORS } from "./palette.js";

export default function App() {
  const [url, setUrl] = useState("https://github.com/pallets/flask");
  const [repoId, setRepoId] = useState(null);
  const [status, setStatus] = useState(null);
  const [graph, setGraph] = useState(null);
  const [includeTests, setIncludeTests] = useState(false);
  const [colorBy, setColorBy] = useState("language");
  const [selected, setSelected] = useState(null);
  const [impact, setImpact] = useState(null);
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [highlight, setHighlight] = useState(null);
  const [tab, setTab] = useState("explore");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [level, setLevel] = useState("auto");
    const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || "light");
  const sessionId = useRef(crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2));
  const fileInput = useRef(null);

  const state = status?.status;
  const busy = repoId !== null && state !== "done" && state !== "error";

  function reset() {
    setStatus(null); setGraph(null); setSelected(null);
    setImpact(null); setFile(null); setError("");
    setHighlight(null); setMessages([]); setTab("explore");
  }

  function selectFile(path) {                    // from graph clicks and file lists
    setSelected(path);
    setHighlight(null);
    if (path) setTab("explore");
  }

  function openCitation({ path, start, end }) { // from chat answers
    setSelected(path);
        setHighlight(start > 0 ? { start, end } : null);   // start 0 = just open the file
    setTab("explore");
  }

  async function ask(question) {
    setMessages((m) => [...m, { role: "user", text: question }]);
    setAsking(true);
    try {
      const res = await askQuestion(repoId, { question, level, session_id: sessionId.current });
      setMessages((m) => [...m, { role: "assistant", text: res.answer, sources: res.sources, level: res.level }]);
    } catch (e) {
      setMessages((m) => [...m, { role: "error", text: e.message }]);
    } finally {
      setAsking(false);
    }
  }

  async function start(promise) {
    reset();
    try {
      const { id } = await promise;
      setRepoId(id);
    } catch (e) {
      setRepoId(null);
      setError(e.message);
    }
  }
  // Apply and remember the chosen theme.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch { /* storage may be blocked */ }
  }, [theme]);
  // Poll the job until it finishes.
  useEffect(() => {
    if (!repoId) return;
    let stop = false;
    const tick = async () => {
      try {
        const s = await getStatus(repoId);
        if (stop) return;
        setStatus(s);
        if (s.status === "done" || s.status === "error") return;
      } catch (e) {
        if (!stop) setError(e.message);
        return;
      }
      setTimeout(tick, 3000);
    };
    tick();
    return () => { stop = true; };
  }, [repoId]);

  // Load the graph when the analysis is done (and when the tests toggle changes).
  useEffect(() => {
    if (state !== "done") return;
    getGraph(repoId, includeTests).then(setGraph).catch((e) => setError(e.message));
  }, [state, repoId, includeTests]);

  // Load impact and code for the selected file.
  useEffect(() => {
    setImpact(null); setFile(null);
    if (!selected || !repoId) return;
    let stop = false;
    Promise.all([
      getImpact(repoId, selected).catch(() => null),
      getFile(repoId, selected).catch(() => null),
    ]).then(([i, f]) => {
      if (!stop) { setImpact(i); setFile(f ?? { content: "Could not load this file.", language: null }); }
    });
    return () => { stop = true; };
  }, [selected, repoId]);

  const stats = status?.stats;
  const legend = LEGENDS[colorBy];
  const present = new Set(graph?.nodes.map((n) => (colorBy === "domain" ? n.domain : n.language)));

  return (
    <div className="app">
      <header className="top">
        <div className="brand">RepoMind</div>
        <input
          className="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          disabled={busy}
        />
        <button className="primary" disabled={busy || !url.trim()} onClick={() => start(analyzeUrl(url.trim()))}>
          Analyze
        </button>
        <button disabled={busy} onClick={() => fileInput.current.click()}>Upload ZIP</button>
        <input
          ref={fileInput}
          type="file"
          accept=".zip"
          hidden
          onChange={(e) => {
            const f = e.target.files[0];
            e.target.value = "";
            if (f) start(analyzeZip(f));
          }}
        />
                <button className="icon-btn" title="Switch light / dark theme" aria-label="Switch theme"
          onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}>
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>

      {error && <div className="banner error">{error}</div>}
      {busy && (
        <div className="banner"><span className="spinner" />
          {state === "running" ? "Analyzing: cloning, parsing imports, building the graph and embedding code. About a minute."
                               : "Queued…"}
        </div>
      )}
      {state === "error" && <div className="banner error">Analysis failed: {status.error}</div>}

      {stats && (
        <div className="stats">
          {Object.entries(stats.languages).map(([lang, n]) => (
            <span key={lang} className="chip">
              <i style={{ background: LANGUAGE_COLORS[lang] || "#94a3b8" }} />{lang} {n}
            </span>
          ))}
          <span className="chip plain">{stats.files} files</span>
          <span className="chip plain">{stats.edges} import links</span>
          <span className="chip plain">{stats.chunks} code chunks</span>
        </div>
      )}

      <main className="main">
        <section className="graph-col">
          {graph && (
            <div className="toolbar">
              <label><input type="checkbox" checked={includeTests}
                onChange={(e) => setIncludeTests(e.target.checked)} /> Show tests</label>
              <label>Color by{" "}
                <select value={colorBy} onChange={(e) => setColorBy(e.target.value)}>
                  <option value="language">language</option>
                  <option value="domain">domain</option>
                </select>
              </label>
              <span className="legend">
                {Object.entries(legend).filter(([k]) => present.has(k)).map(([k, c]) => (
                  <span key={k} className="chip"><i style={{ background: c }} />{k}</span>
                ))}
              </span>
              <span className="muted small">Node size = importance</span>
            </div>
          )}
                   {graph ? (
            <GraphView data={graph} selected={selected} onSelect={selectFile} colorBy={colorBy} theme={theme} />
          ) : (
            <div className="graph-wrap empty">
              {busy ? "" : "Paste a GitHub URL or upload a ZIP, then press Analyze."}
            </div>
          )}
        </section>

        <div className="side-wrap">
          <div className="tabs">
            <button className={tab === "explore" ? "tab on" : "tab"} onClick={() => setTab("explore")}>Explore</button>
            <button className={tab === "chat" ? "tab on" : "tab"} onClick={() => setTab("chat")}>Ask</button>
          </div>
          {tab === "explore" ? (
            <SidePanel
              selected={selected}
              impact={impact}
              file={file}
              highlight={highlight}
              report={status?.report}
              onSelect={selectFile}
              onClose={() => selectFile(null)}
            />
          ) : (
           <ChatPanel
              messages={messages}
              busy={asking}
              level={level}
              onLevel={setLevel}
              onSend={ask}
              onCite={openCitation}
              ready={state === "done"}
              paths={new Set(graph ? graph.nodes.map((n) => n.id) : [])}
            />
          )}
        </div>
      </main>
    </div>
  );
}