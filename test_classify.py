from collections import Counter
from backend.core.ingestion import clone_github, collect_files
from backend.core.classify import classify_file

root = clone_github("https://github.com/pallets/flask")
results = [classify_file(f, root) for f in collect_files(root)]

print(Counter(r["language"] for r in results))
print(Counter(r["category"] for r in results))
print(Counter(r["domain"] for r in results if r["category"] == "source"))
for r in results[:8]:
    print(r)