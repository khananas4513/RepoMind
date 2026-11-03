from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file
from backend.core.chunker import chunk_file
from backend.core.vector_index import CodeIndex
from backend.core.rag import answer

root = clone_github("https://github.com/pallets/flask")

chunks = []
for f in collect_files(root):
    meta = classify_file(f, root)
    if meta["category"] == "source" and meta["language"]:
        chunks += chunk_file(f, root, meta)
print(len(chunks), "chunks")

index = CodeIndex()
index.build(chunks)

for q in ["How are templates rendered?",
          "How does the app load configuration from a file?",
          "How does Flask send an email?"]:        # NOT in the code: tests honesty
    text, sources = answer(index, q)
    print("\n" + "=" * 70)
    print("Q:", q)
    print(text)
    print("Retrieved:", sources)