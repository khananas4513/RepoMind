from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file

root = clone_github("https://github.com/pallets/flask")
files = collect_files(root)

py_files = [f for f in files if classify_file(f, root)["language"] == "python"]
print(len(py_files), "python files")

from backend.core.python_parser import build_edges
edges, external = build_edges(py_files, root)

print(len(edges), "internal edges")
for e in edges[:15]:
    print(e[0], "->", e[1])
print("Top external imports:", external.most_common(8))