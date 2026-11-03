import zipfile
from backend.core.ingestion import safe_extract_zip
from backend.core.pipeline import analyze_repo

# 1) a zip-slip attack must be rejected
with zipfile.ZipFile("evil.zip", "w") as z:
    z.writestr("../../evil.txt", "pwned")
try:
    safe_extract_zip("evil.zip")
    print("FAIL: malicious zip was extracted")
except ValueError as e:
    print("OK, blocked:", e)

# 2) a normal GitHub-style zip (one wrapper folder) goes through the whole pipeline
with zipfile.ZipFile("demo.zip", "w") as z:
    z.writestr("demo-main/app.py", "from helpers import add\n\ndef run():\n    return add(1, 2)\n")
    z.writestr("demo-main/helpers.py", "def add(a, b):\n    return a + b\n")
a = analyze_repo("demo.zip", is_zip=True, with_index=False)
print(dict(a.languages), a.edges)