from collections import Counter
from pathlib import Path

import tree_sitter_javascript as ts_js
import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser

JS_EXTS = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]   # order = resolution priority

_LANGS = {
    "javascript": Language(ts_js.language()),
    "typescript": Language(ts_ts.language_typescript()),
    "tsx": Language(ts_ts.language_tsx()),
}
_parsers: dict[str, Parser] = {}


def _parser_for(path: Path) -> Parser:
    ext = path.suffix.lower()
    name = "typescript" if ext == ".ts" else "tsx" if ext == ".tsx" else "javascript"
    if name not in _parsers:
        _parsers[name] = Parser(_LANGS[name])
    return _parsers[name]


def _string_value(node) -> str | None:
    """Text of a string literal node, without the quotes."""
    if node is None or node.type != "string":
        return None
    return node.text.decode("utf-8", errors="ignore")[1:-1]


def extract_specifiers(path: Path) -> list[str]:
    """Every module specifier this file imports, e.g. './utils', 'express', '../lib/app'."""
    tree = _parser_for(path).parse(path.read_bytes())
    found, stack = [], [tree.root_node]
    while stack:                                   # iterative walk (no recursion limit)
        node = stack.pop()
        t = node.type

        if t in ("import_statement", "export_statement"):
            # import x from 'a'  |  import 'a'  |  export * from 'a'  |  export {x} from 'a'
            spec = _string_value(node.child_by_field_name("source"))
            if spec:
                found.append(spec)

        elif t == "call_expression":
            fn = node.child_by_field_name("function")
            args = node.child_by_field_name("arguments")
            # require('a')  and  dynamic import('a')
            if fn is not None and fn.type in ("identifier", "import") and args is not None:
                if fn.text in (b"require", b"import") and args.named_child_count >= 1:
                    spec = _string_value(args.named_children[0])
                    if spec:
                        found.append(spec)

        stack.extend(node.children)
    return found


def resolve_relative(spec: str, importer: Path, known: set[Path]) -> Path | None:
    """Resolve './x' the way Node/TypeScript do: exact file, + extension, or folder/index."""
    base = (importer.parent / spec).resolve()
    candidates = [base]
    if base.suffix in (".js", ".jsx", ".mjs", ".cjs"):            # TS: import './a.js' means a.ts
        stem = base.with_suffix("")
        candidates += [stem.with_suffix(e) for e in (".ts", ".tsx")]
    candidates += [Path(str(base) + e) for e in JS_EXTS]          # './utils' -> utils.js
    candidates += [base / f"index{e}" for e in JS_EXTS]           # './lib'   -> lib/index.js
    for c in candidates:
        if c in known:
            return c
    return None


def package_name(spec: str) -> str:
    if spec.startswith("node:"):
        return spec
    parts = spec.split("/")
    return "/".join(parts[:2]) if spec.startswith("@") else parts[0]


def build_edges_js(files: list[Path], root: Path):
    known = {f.resolve() for f in files}
    edges, external = set(), Counter()
    for f in files:
        try:
            specs = extract_specifiers(f)
        except OSError:
            continue
        for spec in specs:
            if spec.startswith("."):
                target = resolve_relative(spec, f.resolve(), known)
                if target is not None and target != f.resolve():
                    edges.add((str(f.relative_to(root)), str(target.relative_to(root.resolve()))))
            else:
                external[package_name(spec)] += 1
    return sorted(edges), external