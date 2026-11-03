from collections import Counter
from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.parsers import build_all_edges

REPOS = [
    ("Python",     "https://github.com/pallets/flask"),
    ("JavaScript", "https://github.com/expressjs/express"),
    ("Java",       "https://github.com/spring-projects/spring-petclinic"),
    ("C",          "https://github.com/DaveGamble/cJSON"),
    ("C++",        "https://github.com/gabime/spdlog"),
    ("Go",         "https://github.com/gorilla/mux"),
    ("Rust",       "https://github.com/sharkdp/fd"),
    ("Ruby",       "https://github.com/sinatra/sinatra"),
]

for name, url in REPOS:
    root = clone_github(url)
    meta = {}
    for f in collect_files(root):
        m = classify_file(f, root)
        if m["language"]:
            meta[m["path"]] = m
    edges, external = build_all_edges(meta, root)
    print(f"\n== {name}: {len(meta)} code files, {len(edges)} edges")
    print("   languages:", dict(Counter(m["language"] for m in meta.values())))
    for e in edges[:3]:
        print("  ", e[0], "->", e[1])
    for label, ext in external.items():
        print("   external:", ext.most_common(4))