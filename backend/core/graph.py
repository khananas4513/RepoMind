import networkx as nx
from networkx.readwrite import json_graph


def build_graph(meta: dict[str, dict], edges: list[tuple[str, str]]) -> nx.DiGraph:
    """meta: path -> {language, category, domain}. edges: (importer, imported)."""
    G = nx.DiGraph()
    for path, m in meta.items():
        G.add_node(path, language=m["language"], category=m["category"], domain=m["domain"])
    G.add_edges_from(edges)
    return G


def without_tests(G: nx.DiGraph) -> nx.DiGraph:
    keep = [n for n, d in G.nodes(data=True) if d["category"] != "test"]
    return G.subgraph(keep).copy()


def analyze(G: nx.DiGraph, top: int = 5) -> dict:
    pagerank = nx.pagerank(G)
    in_deg = dict(G.in_degree())
    out_deg = dict(G.out_degree())

    def best(scores):
        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top]

    cycles = [sorted(c) for c in nx.strongly_connected_components(G) if len(c) > 1]
    clusters = sorted(nx.weakly_connected_components(G), key=len, reverse=True)

    return {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "most_imported": best(in_deg),
        "most_dependencies": best(out_deg),
        "most_important": best(pagerank),
        "cycles": cycles,
        "is_acyclic": nx.is_directed_acyclic_graph(G),
        "clusters": [len(c) for c in clusters],
    }


def to_json(G: nx.DiGraph) -> dict:
    """Format the frontend graph library will consume later."""
    return json_graph.node_link_data(G, edges="edges")