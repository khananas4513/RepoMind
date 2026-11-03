import ast
from dataclasses import dataclass
from pathlib import Path

MAX_CLASS_LINES = 60      # bigger classes are split per method
MAX_MODULE_HEADER = 60    # cap for the imports/constants block at the top
WINDOW, OVERLAP = 40, 8   # fallback line windows for non-Python files

FUNC = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass
class Chunk:
    path: str
    start: int
    end: int
    symbol: str
    kind: str
    language: str
    domain: str
    text: str


def _make(rel, lines, start, end, symbol, kind, meta):
    return Chunk(rel, start, end, symbol, kind, meta["language"], meta["domain"],
                 "\n".join(lines[start - 1:end]))


def _start(node):
    """First line of a node, including its decorators."""
    return min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])


def chunk_by_lines(src, rel, meta):
    lines = src.splitlines()
    chunks, i = [], 0
    while i < len(lines):
        end = min(i + WINDOW, len(lines))
        chunks.append(_make(rel, lines, i + 1, end, f"lines {i + 1}-{end}", "block", meta))
        if end == len(lines):
            break
        i = end - OVERLAP
    return chunks


def chunk_python(src, rel, meta):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return chunk_by_lines(src, rel, meta)

    lines = src.splitlines()
    defs = [n for n in tree.body if isinstance(n, FUNC + (ast.ClassDef,))]
    if not defs:                                   # script with no functions/classes
        return chunk_by_lines(src, rel, meta)

    chunks = []
    head_end = min(min(_start(n) for n in defs) - 1, MAX_MODULE_HEADER)
    if head_end >= 1:                              # docstring + imports + constants
        chunks.append(_make(rel, lines, 1, head_end, "module header", "module", meta))

    for node in defs:
        if isinstance(node, FUNC):
            chunks.append(_make(rel, lines, _start(node), node.end_lineno,
                                node.name, "function", meta))
            continue

        size = node.end_lineno - _start(node) + 1
        methods = [n for n in node.body if isinstance(n, FUNC)]
        if size <= MAX_CLASS_LINES or not methods:
            chunks.append(_make(rel, lines, _start(node), node.end_lineno,
                                node.name, "class", meta))
        else:                                      # big class: header + one chunk per method
            first = min(_start(m) for m in methods)
            if first - 1 >= _start(node):
                chunks.append(_make(rel, lines, _start(node), first - 1,
                                    node.name, "class header", meta))
            for m in methods:
                chunks.append(_make(rel, lines, _start(m), m.end_lineno,
                                    f"{node.name}.{m.name}", "method", meta))
    return chunks


def chunk_file(path: Path, root: Path, meta: dict) -> list[Chunk]:
    rel = str(path.relative_to(root))
    src = path.read_text(encoding="utf-8", errors="ignore")
    if meta["language"] == "python":
        return chunk_python(src, rel, meta)
    return chunk_by_lines(src, rel, meta)