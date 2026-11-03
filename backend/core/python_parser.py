import ast
from collections import Counter
from pathlib import Path


def module_name(path: Path, root: Path) -> str:
    """Dotted module name of a .py file, e.g. src/flask/app.py -> 'flask.app'.
    We climb upward while the folder has an __init__.py (i.e. is a package)."""
    parts = [] if path.stem == "__init__" else [path.stem]
    d = path.parent
    while d != root and (d / "__init__.py").exists():
        parts.insert(0, d.name)
        d = d.parent
    return ".".join(parts)


def build_module_index(py_files: list[Path], root: Path) -> dict[str, Path]:
    return {module_name(f, root): f for f in py_files}


def extract_imports(path: Path, root: Path) -> list[str]:
    """Return absolute dotted names that this file imports."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    this_mod = module_name(path, root)
    is_pkg = path.stem == "__init__"
    found = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):                 # import a.b.c
            for alias in node.names:
                found.append(alias.name)

        elif isinstance(node, ast.ImportFrom):           # from x import y
            if node.level:                               # relative: from . / from ..
                pkg = this_mod.split(".") if this_mod else []
                if not is_pkg:
                    pkg = pkg[:-1]                       # a module's package is its parent
                keep = max(0, len(pkg) - (node.level - 1))
                pkg = pkg[:keep]
                base = ".".join(pkg + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            for alias in node.names:
                found.append(f"{base}.{alias.name}" if base else alias.name)

    return found


def resolve(name: str, index: dict[str, Path]) -> Path | None:
    """Match a dotted name to a repo file, trying shorter prefixes:
    'flask.app.Flask' -> 'flask.app' (a file) -> done."""
    while name:
        if name in index:
            return index[name]
        name = name.rpartition(".")[0]
    return None


def build_edges(py_files: list[Path], root: Path):
    index = build_module_index(py_files, root)
    edges, external = set(), Counter()
    for f in py_files:
        for name in extract_imports(f, root):
            target = resolve(name, index)
            if target is None:
                external[name.split(".")[0]] += 1        # os, typing, click...
            elif target != f:
                edges.add((str(f.relative_to(root)), str(target.relative_to(root))))
    return sorted(edges), external