import json
from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.python_parser import build_edges
from backend.core.graph import build_graph, without_tests, analyze, to_json

root = clone_github("https://github.com/pallets/flask")

meta = {}
for f in collect_files(root):
    m = classify_file(f, root)
    if m["language"] == "python":
        meta[m["path"]] = m

py_files = [root / p for p in meta]
edges, external = build_edges(py_files, root)

G = build_graph(meta, edges)
print("FULL GRAPH     :", G.number_of_nodes(), "nodes,", G.number_of_edges(), "edges")

G2 = without_tests(G)
report = analyze(G2)
print("WITHOUT TESTS  :", report["nodes"], "nodes,", report["edges"], "edges")

for key in ("most_imported", "most_dependencies", "most_important"):
    print("\n" + key.upper())
    for path, score in report[key]:
        print(f"  {score:.3f}  {path}")

print("\nAcyclic?", report["is_acyclic"])
print("Circular groups:", report["cycles"])
print("Cluster sizes  :", report["clusters"])

with open("graph.json", "w") as fh:
    json.dump(to_json(G2), fh, indent=2)
print("\nSaved graph.json")