from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.js_parser import build_edges_js

root = clone_github("https://github.com/expressjs/express")
files = [f for f in collect_files(root)
         if classify_file(f, root)["language"] in ("javascript", "typescript")]
print(len(files), "JS/TS files")

edges, external = build_edges_js(files, root)
print(len(edges), "internal edges")
for e in edges[:12]:
    print(e[0], "->", e[1])
print("Top external:", external.most_common(8))