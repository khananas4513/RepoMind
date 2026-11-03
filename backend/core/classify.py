import re
from pathlib import Path

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".rs": "rust",
    ".rb": "ruby",
}

CONFIG_EXT = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
DOC_EXT = {".md", ".rst", ".txt"}
BUILD_NAMES = {"dockerfile", "makefile", "cmakelists.txt", "package.json",
               "pyproject.toml", "setup.py", "go.mod", "cargo.toml", "gemfile", "pom.xml"}

TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}
TEST_NAME = re.compile(r"(^test_.*\.py$)|(_test\.(py|go)$)|(\.(test|spec)\.(js|jsx|ts|tsx)$)|(Test\.java$)")

DOMAINS = {
    "frontend": ({"components", "pages", "views", "ui", "frontend", "client", "public"},
                 re.compile(r"\b(react|vue|svelte|@angular|next/)\b")),
    "backend": ({"api", "routes", "controllers", "handlers", "server", "backend", "services"},
                re.compile(r"\b(flask|fastapi|django|express|spring|gin|actix|rails|sinatra)\b")),
    "data": ({"models", "schemas", "db", "migrations", "entities", "repository"},
             re.compile(r"\b(sqlalchemy|mongoose|prisma|hibernate|gorm|diesel|activerecord)\b")),
    "utils": ({"utils", "util", "helpers", "common", "lib", "shared"}, None),
}

def detect_language(path: Path) -> str | None:
    return EXT_TO_LANG.get(path.suffix.lower())

def classify_category(rel: Path) -> str:
    name = rel.name.lower()
    parts = {p.lower() for p in rel.parts[:-1]}
    if parts & TEST_DIRS or TEST_NAME.search(rel.name):
        return "test"
    if name in BUILD_NAMES or ".github" in parts or "ci" in parts:
        return "build"
    if rel.suffix.lower() in DOC_EXT or "docs" in parts:
        return "docs"
    if rel.suffix.lower() in CONFIG_EXT:
        return "config"
    if rel.suffix.lower() in EXT_TO_LANG:
        return "source"
    return "other"

def classify_domain(rel: Path, text: str) -> str:
    parts = {p.lower() for p in rel.parts[:-1]}
    head = text[:3000].lower()
    scores = {}
    for domain, (dirs, pattern) in DOMAINS.items():
        score = 2 * len(parts & dirs)
        if pattern and pattern.search(head):
            score += 3
        scores[domain] = score
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

def classify_file(path: Path, root: Path) -> dict:
    rel = path.relative_to(root)
    lang = detect_language(path)
    category = classify_category(rel)
    domain = "n/a"
    if category == "source":
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        domain = classify_domain(rel, text)
    return {"path": str(rel), "language": lang, "category": category, "domain": domain}