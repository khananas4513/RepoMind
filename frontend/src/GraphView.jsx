import { useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { colorOf } from "./palette.js";

const REL = 3;                                   // node radius = sqrt(val) * REL

// Canvas colors cannot use CSS variables, so each theme has its own set.
const THEMES = {
  light: { link: "rgba(29,27,22,0.20)", label: "rgba(29,27,22,0.75)", labelSel: "#1d1b16", ring: "#1d1b16", outline: "rgba(29,27,22,0.25)" },
  dark:  { link: "rgba(242,239,232,0.22)", label: "rgba(242,239,232,0.75)", labelSel: "#f2efe8", ring: "#f2efe8", outline: "rgba(0,0,0,0.5)" },
};

const GENERIC = new Set(["__init__.py", "index.js", "index.ts", "index.jsx", "index.tsx", "mod.rs", "lib.rs", "main.rs", "main.go"]);

// "src/flask/__init__.py" -> "flask/__init__.py" so repeated names stay distinguishable.
function shortName(id) {
  const parts = id.split("/");
  const name = parts.pop();
  return GENERIC.has(name) && parts.length ? `${parts.pop()}/${name}` : name;
}

function useSize(ref) {
  const [size, setSize] = useState({ w: 600, h: 500 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) =>
      setSize({ w: entry.contentRect.width, h: entry.contentRect.height }));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

export default function GraphView({ data, selected, onSelect, colorBy, theme = "light" }) {
  const t = THEMES[theme] || THEMES.light;
  const wrap = useRef(null);
  const fg = useRef(null);
  const fitted = useRef(false);
  const tuned = useRef(false);
  const { w, h } = useSize(wrap);

  // The graph library mutates its input, so give it its own copy.
  const graphData = useMemo(() => {
    const maxPr = Math.max(...data.nodes.map((n) => n.pagerank), 1e-9);
    return {
      nodes: data.nodes.map((n) => ({ ...n, val: 2 + 18 * (n.pagerank / maxPr) })),
      links: data.links.map((l) => ({ ...l })),
    };
  }, [data]);

  useEffect(() => { fitted.current = false; }, [graphData]);

  if (data.nodes.length === 0) {
    return <div className="graph-wrap empty">No files to show.</div>;
  }

  return (
    <div ref={wrap} className="graph-wrap">
      <button className="fit-btn" title="Fit the whole graph in view"
        onClick={() => fg.current?.zoomToFit(400, 40)}>
        Fit view
      </button>
      <div className="graph-hint">Scroll to zoom · drag to pan · click a node</div>
      <ForceGraph2D
        ref={fg}
        width={w}
        height={h}
        graphData={graphData}
        backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={REL}
        nodeColor={(n) => colorOf(n, colorBy)}
        nodeLabel={(n) => `${n.id} — imported by ${n.in_degree}, imports ${n.out_degree}`}
        linkColor={() => t.link}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        cooldownTicks={150}
        onEngineTick={() => {                       // tune the physics once, on the very first tick
          if (!tuned.current && fg.current) {
            fg.current.d3Force("charge")?.distanceMax(120);   // far-apart pieces stop repelling each other
            tuned.current = true;
          }
        }}
        onEngineStop={() => {                       // fit the whole graph on screen once it settles
          if (!fitted.current && fg.current) {
            fg.current.zoomToFit(400, 60);
            fitted.current = true;
          }
        }}
        onNodeClick={(n) => onSelect(n.id)}
        onBackgroundClick={() => onSelect(null)}
        nodeCanvasObjectMode={() => "after"}
        nodeCanvasObject={(node, ctx, scale) => {
          const r = Math.sqrt(node.val) * REL;
          const isSel = node.id === selected;
          ctx.beginPath();                          // thin outline so nodes stay crisp on any background
          ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
          ctx.strokeStyle = t.outline;
          ctx.lineWidth = 0.8 / scale;
          ctx.stroke();
          if (isSel) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, r + 2.5, 0, 2 * Math.PI);
            ctx.strokeStyle = t.ring;
            ctx.lineWidth = 2 / scale;
            ctx.stroke();
          }
          if (isSel || node.val > 12 || scale > 1.6) {
            ctx.font = `${11 / scale}px Inter, system-ui, sans-serif`;
            ctx.fillStyle = isSel ? t.labelSel : t.label;
            ctx.textAlign = "center";
            ctx.fillText(shortName(node.id), node.x, node.y + r + 10 / scale);
          }
        }}
      />
    </div>
  );
}