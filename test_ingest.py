from backend.core.ingestion import clone_github, collect_files

root = clone_github("https://github.com/pallets/flask")
files = collect_files(root)
print(len(files), "files")
print([str(f.relative_to(root)) for f in files[:10]])