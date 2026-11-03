from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import networkx as nx

from backend.core.ingestion import clone_github, safe_extract_zip, collect_files
from backend.core.classify import classify_file
from backend.core.chunker import chunk_file
from backend.core.parsers import build_all_edges
from backend.core.graph import build_graph, without_tests, analyze

CPP_SOURCES = {".cpp", ".cc", ".cxx", ".hpp"}


def _posix(p: str) -> str:
    """One path style everywhere (graph ids, chunks, citations, the UI)."""
    return p.replace("\\", "/")


def _unwrap(root: Path) -> Path:
    """GitHub ZIPs wrap everything in one folder (repo-main/...). Step inside it."""
    kids = [k for k in root.iterdir() if k.name != "__MACOSX"]
    return kids[0] if len(kids) == 1 and kids[0].is_dir() else root


def refine_header_language(meta: dict) -> None:
    """A .h file could be C or C++. If the repo has more C++ sources than .c files,
    treat its .h headers as C++."""
    cpp = sum(1 for p in meta if Path(p).suffix.lower() in CPP_SOURCES)
    c = sum(1 for p in meta if Path(p).suffix.lower() == ".c")
    if cpp > c:
        for p, m in meta.items():
            if Path(p).suffix.lower() == ".h":
                m["language"] = "cpp"


@dataclass
class RepoAnalysis:
    source: str
    root: Path
    meta: dict
    edges: list
    external: dict
    graph: nx.DiGraph          # every code file, tests included
    graph_src: nx.DiGraph      # tests removed (used for rankings and answers)
    chunks: list
    index: object              # CodeIndex, or None when built without embeddings
    report: dict

    @property
    def languages(self) -> Counter:
        return Counter(m["language"] for m in self.meta.values())


def analyze_repo(source: str, is_zip: bool = False, with_index: bool = True) -> RepoAnalysis:
    root = safe_extract_zip(source) if is_zip else clone_github(source)
    root = _unwrap(root)

    meta = {}
    for f in collect_files(root):
        m = classify_file(f, root)
        if m["language"]:
            m["path"] = _posix(m["path"])
            meta[m["path"]] = m
    refine_header_language(meta)

    raw_edges, external = build_all_edges(meta, root)
    edges = [(_posix(a), _posix(b)) for a, b in raw_edges]
    edges = [(a, b) for a, b in edges if a in meta and b in meta]     # safety net

    graph = build_graph(meta, edges)
    graph_src = without_tests(graph)
    report = analyze(graph_src) if graph_src.number_of_nodes() else {}

    chunks = []
    for path, m in meta.items():
        if m["category"] == "source":
            for c in chunk_file(root / path, root, m):
                c.path = _posix(c.path)
                chunks.append(c)

    index = None
    if with_index and chunks:
        from backend.core.vector_index import CodeIndex     # heavy import, only when needed
        index = CodeIndex()
        index.build(chunks)

    return RepoAnalysis(source, root, meta, edges, external, graph, graph_src, chunks, index, report)


def impact(a: RepoAnalysis, path: str):
    """What is affected if `path` changes? Direct and indirect importers, plus which tests."""
    G = a.graph
    if path not in G:
        return None
    affected = nx.ancestors(G, path)
    tests = sorted(p for p in affected if G.nodes[p]["category"] == "test")
    return {
        "direct": sorted(G.predecessors(path)),
        "total": len(affected),
        "tests": tests,
        "source": sorted(affected - set(tests)),
    }


def repo_overview(a: RepoAnalysis) -> str:
    """Whole-repo facts for questions that no single code chunk can answer."""
    r = a.report or {}
    names = lambda key, n=5: ", ".join(f"`{p}`" for p, _ in r.get(key, [])[:n]) or "n/a"
    folders = Counter(p.split("/")[0] if "/" in p else "(root)"
                      for p, m in a.meta.items() if m["category"] == "source")
    langs = ", ".join(f"{k} {v}" for k, v in a.languages.most_common())
    return (
        f"Languages (files): {langs}. Import links: {len(a.edges)}.\n"
        f"Most important files (PageRank, tests excluded): {names('most_important')}.\n"
        f"Most imported files: {names('most_imported')}.\n"
        f"Files with the most dependencies: {names('most_dependencies')}.\n"
        f"Top-level source folders (files): {', '.join(f'{k} {v}' for k, v in folders.most_common(6))}.\n"
        f"Circular import groups: {len(r.get('cycles', []))}."
    )


def ask(a: RepoAnalysis, question: str, profile=None, k: int = 5):
    from backend.core.rag import answer
    return answer(a.index, question, k=k, profile=profile, G=a.graph_src, overview=repo_overview(a))