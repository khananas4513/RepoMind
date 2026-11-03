import tempfile, zipfile
from pathlib import Path
from git import Repo

IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__",
               "dist", "build", "target", ".idea", ".next", "vendor"}
MAX_FILE_BYTES = 500_000

def clone_github(url: str) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="repo_"))
    Repo.clone_from(url, dest, depth=1)
    return dest

def safe_extract_zip(zip_path: str) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="repo_")).resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():
            target = (dest / member).resolve()
            if not target.is_relative_to(dest):
                raise ValueError(f"Unsafe path in archive: {member}")
        zf.extractall(dest)
    return dest

def is_binary(path: Path) -> bool:
    with open(path, "rb") as f:
        return b"\0" in f.read(1024)

def collect_files(root: Path) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in IGNORE_DIRS for part in p.relative_to(root).parts):
            continue
        if p.stat().st_size > MAX_FILE_BYTES or is_binary(p):
            continue
        files.append(p)
    return files