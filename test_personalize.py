import time
from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.chunker import chunk_file
from backend.core.vector_index import CodeIndex
from backend.core.python_parser import build_edges
from backend.core.graph import build_graph, without_tests
from backend.core.personalize import UserProfile
from backend.core.rag import answer

root = clone_github("https://github.com/pallets/flask")

chunks, meta = [], {}
for f in collect_files(root):
    m = classify_file(f, root)
    if m["language"] == "python":
        meta[m["path"]] = m
    if m["category"] == "source" and m["language"]:
        chunks += chunk_file(f, root, m)

edges, _ = build_edges([root / p for p in meta], root)
G = without_tests(build_graph(meta, edges))

index = CodeIndex()
index.build(chunks)

# ---- Part 1: adaptive level inference (no LLM calls) ----
print("\n=== PART 1: level inferred from the user's questions ===")
profile = UserProfile()
for q in [
    "what is a blueprint? explain it simply",
    "explain how the app context works",
    "what are the trade-off and coupling between blueprints and the app object, including lifecycle?",
    "does the circular dependency between app and ctx hurt the lifecycle design?",
]:
    profile.observe(q)
    print(f"score={profile.score:.2f}  level={profile.level:12}  <- {q[:60]}")

# ---- Part 2: same question, two explanation styles ----
print("\n=== PART 2: same question, different levels ===")
question = "How does Flask handle a request using the app context?"
for level in ("beginner", "expert"):
    print("\n" + "=" * 70)
    print("LEVEL:", level)
    text, sources = answer(index, question, profile=UserProfile(explicit_level=level), G=G)
    print(text)
    print("Retrieved:", sources)
    time.sleep(5)          # stay under the free-tier rate limit