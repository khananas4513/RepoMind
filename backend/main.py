import logging
import re
import tempfile
import threading
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Literal

import networkx as nx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.core.personalize import UserProfile
from backend.core.pipeline import analyze_repo, ask, impact

# Only public github.com/<owner>/<repo> URLs: blocks file://, ssh://, internal hosts (SSRF)
GITHUB_URL = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+?(\.git)?/?$")
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_REPOS = 5                                   # keep memory bounded

app = FastAPI(title="RepoMind API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],   # React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: "OrderedDict[str, dict]" = OrderedDict()
PROFILES: dict[tuple[str, str], UserProfile] = {}
_gate = threading.Semaphore(1)                  # one heavy analysis at a time


# ───────────── helpers ─────────────
def _get_job(repo_id: str) -> dict:
    job = JOBS.get(repo_id)
    if job is None:
        raise HTTPException(404, "Unknown repo id")
    return job


def _get_ready(repo_id: str):
    job = _get_job(repo_id)
    if job["status"] != "done":
        raise HTTPException(409, f"Analysis is {job['status']}")
    return job["analysis"]


def _run_job(repo_id: str, source: str, is_zip: bool) -> None:
    job = JOBS[repo_id]
    with _gate:
        job["status"] = "running"
        try:
            job["analysis"] = analyze_repo(source, is_zip=is_zip)
            job["status"] = "done"
        except Exception as e:                  # report the failure instead of crashing the worker
            job["status"] = "error"
            job["error"] = f"{type(e).__name__}: {e}"
        finally:
            if is_zip:
                Path(source).unlink(missing_ok=True)


def _start(bg: BackgroundTasks, source: str, is_zip: bool, label: str) -> dict:
    repo_id = uuid.uuid4().hex[:8]
    JOBS[repo_id] = {"status": "queued", "source": label, "error": None, "analysis": None}
    while len(JOBS) > MAX_REPOS:                # evict the oldest analysis
        JOBS.popitem(last=False)
    bg.add_task(_run_job, repo_id, source, is_zip)
    return {"id": repo_id, "status": "queued"}


_SRC = re.compile(r"^(.+):(\d+)-(\d+) \(score ([\d.]+)\)$")


def _parse_source(s: str) -> dict:
    m = _SRC.match(s)
    if not m:
        return {"path": s}
    return {"path": m[1], "start": int(m[2]), "end": int(m[3]), "score": float(m[4])}


# ───────────── endpoints ─────────────
class AnalyzeRequest(BaseModel):
    url: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/analyze", status_code=202)
def analyze(req: AnalyzeRequest, bg: BackgroundTasks):
    url = req.url.strip()
    if not GITHUB_URL.match(url):
        raise HTTPException(400, "Only public https://github.com/<owner>/<repo> URLs are accepted")
    return _start(bg, url, False, url)


@app.post("/api/analyze/zip", status_code=202)
async def analyze_zip(bg: BackgroundTasks, file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(400, "Please upload a .zip file")
    out = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp, size = Path(out.name), 0
    try:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_ZIP_BYTES:
                raise HTTPException(413, "ZIP too large (limit 50 MB)")
            out.write(chunk)
    except HTTPException:
        out.close()
        tmp.unlink(missing_ok=True)
        raise
    out.close()
    return _start(bg, str(tmp), True, file.filename)


@app.get("/api/repos/{repo_id}")
def status(repo_id: str):
    job = _get_job(repo_id)
    out = {"id": repo_id, "status": job["status"], "source": job["source"], "error": job["error"]}
    a = job["analysis"]
    if a is not None:
        out["stats"] = {
            "languages": dict(a.languages),
            "files": len(a.meta),
            "nodes": a.graph.number_of_nodes(),
            "edges": a.graph.number_of_edges(),
            "chunks": len(a.chunks),
        }
        out["report"] = {k: a.report.get(k) for k in
                         ("most_imported", "most_dependencies", "most_important",
                          "cycles", "is_acyclic", "clusters")}
    return out


@app.get("/api/repos/{repo_id}/graph")
def get_graph(repo_id: str, include_tests: bool = False):
    a = _get_ready(repo_id)
    G = a.graph if include_tests else a.graph_src
    pr = nx.pagerank(G) if G.number_of_nodes() else {}
    nodes = [{
        "id": n, "language": d["language"], "category": d["category"], "domain": d["domain"],
        "in_degree": G.in_degree(n), "out_degree": G.out_degree(n),
        "pagerank": round(pr.get(n, 0.0), 5),
    } for n, d in G.nodes(data=True)]
    links = [{"source": s, "target": t} for s, t in G.edges()]
    return {"nodes": nodes, "links": links}


@app.get("/api/repos/{repo_id}/impact")
def get_impact(repo_id: str, path: str):
    result = impact(_get_ready(repo_id), path)
    if result is None:
        raise HTTPException(404, "File not in the dependency graph")
    return result


@app.get("/api/repos/{repo_id}/file")
def get_file(repo_id: str, path: str):
    a = _get_ready(repo_id)
    if path not in a.meta:                      # allow-list: no path traversal possible
        raise HTTPException(404, "File not found in this analysis")
    text = (a.root / path).read_text(encoding="utf-8", errors="ignore")
    return {"path": path, "language": a.meta[path]["language"], "content": text}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    level: Literal["auto", "beginner", "intermediate", "expert"] = "auto"
    session_id: str = "default"
    k: int = Field(5, ge=1, le=10)


@app.post("/api/repos/{repo_id}/ask")
def ask_question(repo_id: str, req: AskRequest):
    a = _get_ready(repo_id)
    if a.index is None:
        raise HTTPException(409, "No searchable source code in this repository")
    if req.level == "auto":                     # adaptive: remember this user's history
        profile = PROFILES.setdefault((repo_id, req.session_id), UserProfile())
    else:                                       # explicit choice always wins
        profile = UserProfile(explicit_level=req.level)
    try:
        text, sources = ask(a, req.question, profile=profile, k=req.k)
    except Exception as e:                      # do not leak internals (or keys) to the client
        logging.getLogger("uvicorn.error").exception("LLM call failed")
        detail = str(e)
        if type(e).__name__ == "GoogleRateLimitError" or "RESOURCE_EXHAUSTED" in detail:
            raise HTTPException(429, "The free Gemini quota is used up for now. Wait for the daily "
                                     "reset, or configure a second model in LLM_FALLBACK_MODEL.")
        if "UNAVAILABLE" in detail or "503" in detail:
            raise HTTPException(503, "Gemini is overloaded right now (a temporary Google-side problem). "
                                     "Try again in a few minutes.")
        raise HTTPException(502, f"The language model call failed ({type(e).__name__}). "
                                 "Wait a minute and try again.")
    return {"answer": text, "sources": [_parse_source(s) for s in sources], "level": profile.level}