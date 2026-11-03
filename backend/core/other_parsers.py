import re
from collections import Counter, defaultdict
from pathlib import Path

import tree_sitter_c, tree_sitter_cpp, tree_sitter_go
import tree_sitter_java, tree_sitter_ruby, tree_sitter_rust
from tree_sitter import Language, Parser

_LANG = {
    "java": Language(tree_sitter_java.language()),
    "go": Language(tree_sitter_go.language()),
    "rust": Language(tree_sitter_rust.language()),
    "ruby": Language(tree_sitter_ruby.language()),
    "c": Language(tree_sitter_c.language()),
    "cpp": Language(tree_sitter_cpp.language()),
}
_parsers: dict[str, Parser] = {}


def _parse(path: Path, lang: str):
    if lang not in _parsers:
        _parsers[lang] = Parser(_LANG[lang])
    return _parsers[lang].parse(path.read_bytes())


def _walk(root):
    stack = [root]
    while stack:                       # iterative: no recursion limit
        node = stack.pop()
        yield node
        stack.extend(node.children)


def _text(node) -> str:
    return node.text.decode("utf-8", errors="ignore")


def _rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root))


# ───────────────────────── Java ─────────────────────────
def java_imports(path: Path) -> list[str]:
    out = []
    for n in _walk(_parse(path, "java").root_node):
        if n.type == "import_declaration":
            t = re.sub(r"\s+", "", _text(n))
            t = re.sub(r"^import(static)?", "", t).rstrip(";")
            out.append(t)                       # 'com.foo.Bar' or 'com.foo.*'
    return out


def build_edges_java(files, root):
    root = root.resolve()
    files = [f.resolve() for f in files]
    by_stem, by_dir = defaultdict(list), defaultdict(list)
    for f in files:
        by_stem[f.stem].append(f)
        by_dir[f.parent.name].append(f)
    edges, external = set(), Counter()
    for f in files:
        for name in java_imports(f):
            target_files = []
            if name.endswith(".*"):                         # wildcard: whole package
                pkg = tuple(name[:-2].split("."))
                target_files = [g for g in by_dir.get(pkg[-1], [])
                                if g.parent.parts[-len(pkg):] == pkg]
            else:                                           # a.b.C  or  static a.b.C.member
                segs = name.split(".")
                for k in range(len(segs), 0, -1):
                    hit = [g for g in by_stem.get(segs[k - 1], [])
                           if g.with_suffix("").parts[-k:] == tuple(segs[:k])]
                    if hit:
                        target_files = hit[:1]
                        break
            if not target_files:
                external[".".join(name.split(".")[:2])] += 1
            for g in target_files:
                if g != f:
                    edges.add((_rel(f, root), _rel(g, root)))
    return sorted(edges), external


# ───────────────────────── Go ─────────────────────────
def go_imports(path: Path) -> list[str]:
    out = []
    for n in _walk(_parse(path, "go").root_node):
        if n.type == "import_spec":
            p = n.child_by_field_name("path")
            if p is not None:
                out.append(_text(p).strip('"`'))
    return out


def build_edges_go(files, root):
    root = root.resolve()
    files = [f.resolve() for f in files]
    module = None
    gomod = root / "go.mod"
    if gomod.exists():
        m = re.search(r"^module\s+(\S+)", gomod.read_text(errors="ignore"), re.M)
        module = m.group(1) if m else None
    by_dir = defaultdict(list)
    for f in files:
        if not f.name.endswith("_test.go"):
            by_dir[f.parent].append(f)
    edges, external = set(), Counter()
    for f in files:
        for imp in go_imports(f):
            if module and (imp == module or imp.startswith(module + "/")):
                pkg_dir = root / imp[len(module):].lstrip("/")      # a package = a folder
                for g in by_dir.get(pkg_dir, []):
                    if g != f:
                        edges.add((_rel(f, root), _rel(g, root)))
            else:
                external[imp.split("/")[0] if "." not in imp.split("/")[0] else "/".join(imp.split("/")[:3])] += 1
    return sorted(edges), external


# ───────────────────────── Rust ─────────────────────────
def _expand_use(t: str) -> list[str]:
    if "{" not in t:
        return [t[:-3] if t.endswith("::*") else t]
    prefix, _, rest = t.partition("{")
    rest = rest[:rest.rfind("}")]
    items, depth, cur = [], 0, ""
    for ch in rest:
        if ch == "," and depth == 0:
            items.append(cur); cur = ""; continue
        depth += (ch == "{") - (ch == "}")
        cur += ch
    if cur:
        items.append(cur)
    out = []
    for it in items:
        out += [prefix.rstrip(":")] if it == "self" else _expand_use(prefix + it)
    return out


def rust_refs(path: Path) -> list[tuple[str, str]]:
    out = []
    for n in _walk(_parse(path, "rust").root_node):
        if n.type == "mod_item" and n.child_by_field_name("body") is None:
            out.append(("mod", _text(n.child_by_field_name("name"))))      # mod foo;
        elif n.type == "use_declaration":
            arg = n.child_by_field_name("argument")
            if arg is not None:
                t = re.sub(r"\s+as\s+\w+", "", _text(arg))
                for p in _expand_use(re.sub(r"\s+", "", t)):
                    out.append(("use", p))
    return out


def build_edges_rust(files, root):
    root = root.resolve()
    files = [f.resolve() for f in files]
    known = set(files)
    edges, external = set(), Counter()

    def crate_src(f):
        for parent in f.parents:
            if parent.name == "src":
                return parent
        return None

    def first_existing(*cands):
        return next((c for c in cands if c in known), None)

    for f in files:
        for kind, ref in rust_refs(f):
            target = None
            if kind == "mod":
                base = f.parent if f.name in ("mod.rs", "lib.rs", "main.rs") else f.parent / f.stem
                target = first_existing(base / f"{ref}.rs", base / ref / "mod.rs")
            else:
                segs = ref.split("::")
                src = crate_src(f)
                if segs[0] == "crate" and src is not None:
                    path_segs = segs[1:]
                    for k in range(len(path_segs), 0, -1):
                        p = src.joinpath(*path_segs[:k])
                        target = first_existing(p.with_suffix(".rs"), p / "mod.rs")
                        if target:
                            break
                elif segs[0] not in ("self", "super"):
                    external[segs[0]] += 1
                    continue
            if target and target != f:
                edges.add((_rel(f, root), _rel(target, root)))
    return sorted(edges), external


# ───────────────────────── Ruby ─────────────────────────
def ruby_requires(path: Path) -> list[tuple[str, str]]:
    out = []
    for n in _walk(_parse(path, "ruby").root_node):
        if n.type == "call" and n.child_by_field_name("receiver") is None:
            m = n.child_by_field_name("method")
            args = n.child_by_field_name("arguments")
            if m is not None and args is not None and m.text in (b"require", b"require_relative", b"load"):
                for a in args.named_children:
                    if a.type == "string":
                        spec = "".join(_text(c) for c in a.named_children if c.type == "string_content")
                        out.append((_text(m), spec))
    return out


def build_edges_ruby(files, root):
    root = root.resolve()
    files = [f.resolve() for f in files]
    known = set(files)
    by_name = defaultdict(list)
    for f in files:
        by_name[f.name].append(f)
    edges, external = set(), Counter()
    for f in files:
        for kind, spec in ruby_requires(f):
            name = spec if spec.endswith(".rb") else spec + ".rb"
            target = None
            if kind == "require_relative":
                cand = (f.parent / name).resolve()
                target = cand if cand in known else None
            else:                                    # require 'a/b' -> any file ending a/b.rb
                tail = Path(name).parts
                hit = [g for g in by_name.get(Path(name).name, []) if g.parts[-len(tail):] == tail]
                target = hit[0] if hit else None
            if target is None:
                if kind != "require_relative":
                    external[spec.split("/")[0]] += 1
            elif target != f:
                edges.add((_rel(f, root), _rel(target, root)))
    return sorted(edges), external


# ───────────────────────── C / C++ ─────────────────────────
def c_includes(path: Path, lang: str) -> list[tuple[bool, str]]:
    out = []
    for n in _walk(_parse(path, lang).root_node):
        if n.type == "preproc_include":
            p = n.child_by_field_name("path")
            if p is not None:
                t = _text(p)
                out.append((t.startswith('"'), t.strip('"<>')))
    return out


def build_edges_c(files, root, lang_of):
    root = root.resolve()
    files = [f.resolve() for f in files]
    known = set(files)
    by_name = defaultdict(list)
    for f in files:
        by_name[f.name].append(f)
    edges, external = set(), Counter()
    for f in files:
        for quoted, spec in c_includes(f, lang_of(f)):
            target = None
            cand = (f.parent / spec).resolve()
            if quoted and cand in known:
                target = cand
            else:                                    # search include dirs: match by path tail
                tail = Path(spec).parts
                hit = [g for g in by_name.get(Path(spec).name, []) if g.parts[-len(tail):] == tail]
                target = hit[0] if hit else None
            if target is None:
                external[spec] += 1                  # stdio.h, <vector>, third-party headers
            elif target != f:
                edges.add((_rel(f, root), _rel(target, root)))
    return sorted(edges), external