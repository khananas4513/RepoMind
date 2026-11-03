from collections import defaultdict
from pathlib import Path

from backend.core.python_parser import build_edges as python_edges
from backend.core.js_parser import build_edges_js
from backend.core import other_parsers as op


def build_all_edges(meta: dict[str, dict], root: Path):
    """meta: relative path -> classify_file() result.
    Returns (edges, external_by_language). One call works for any supported language."""
    by_lang = defaultdict(list)
    for rel, m in meta.items():
        if m["language"]:
            by_lang[m["language"]].append(root / rel)

    edges, external = set(), {}

    def run(label, fn, files):
        if files:
            e, ext = fn(files)
            edges.update(e)
            external[label] = ext

    run("python", lambda fs: python_edges(fs, root), by_lang["python"])
    # JS and TS are merged so a .ts file can import a .js file and vice versa
    run("javascript/typescript", lambda fs: build_edges_js(fs, root),
        by_lang["javascript"] + by_lang["typescript"])
    run("java", lambda fs: op.build_edges_java(fs, root), by_lang["java"])
    run("go", lambda fs: op.build_edges_go(fs, root), by_lang["go"])
    run("rust", lambda fs: op.build_edges_rust(fs, root), by_lang["rust"])
    run("ruby", lambda fs: op.build_edges_ruby(fs, root), by_lang["ruby"])
    # C and C++ are merged: headers are shared between them
    lang_of = lambda f: "cpp" if f.suffix.lower() in (".cpp", ".cc", ".cxx", ".hpp") else "c"
    run("c/c++", lambda fs: op.build_edges_c(fs, root, lang_of), by_lang["c"] + by_lang["cpp"])
    return sorted(edges), external