from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.chunker import chunk_file
from backend.core.vector_index import CodeIndex

root = clone_github("https://github.com/pallets/flask")

chunks = []
for f in collect_files(root):
    meta = classify_file(f, root)
    if meta["category"] == "source" and meta["language"]:   # skip tests and docs for now
        chunks += chunk_file(f, root, meta)
print(len(chunks), "chunks")

index = CodeIndex()
index.build(chunks)

questions = [
    "how are routes registered on the app",
    "where is the session cookie handled",
    "how does the app load configuration from a file",
    "how are templates rendered",
]
for q in questions:
    print("\nQ:", q)
    for score, c in index.search(q, k=3):
        print(f"  {score:.3f}  {c.path}:{c.start}-{c.end}  [{c.kind}] {c.symbol}")