import time
import httpx

BASE = "http://127.0.0.1:8000/api"
c = httpx.Client(timeout=120)

r = c.post(f"{BASE}/analyze", json={"url": "https://github.com/pallets/flask"})
print(r.status_code, r.json())
rid = r.json()["id"]

while True:                                    # poll until the background job finishes
    s = c.get(f"{BASE}/repos/{rid}").json()
    print("status:", s["status"])
    if s["status"] in ("done", "error"):
        break
    time.sleep(5)
if s["status"] == "error":
    raise SystemExit(s["error"])
print(s["stats"])
print("most important:", s["report"]["most_important"][:3])

g = c.get(f"{BASE}/repos/{rid}/graph").json()
print("graph:", len(g["nodes"]), "nodes,", len(g["links"]), "links")

i = c.get(f"{BASE}/repos/{rid}/impact", params={"path": "src/flask/globals.py"}).json()
print("impact of globals.py:", i["total"], "files,", len(i["tests"]), "tests")

print("traversal attempt:",
      c.get(f"{BASE}/repos/{rid}/file", params={"path": "../../etc/passwd"}).status_code)

for body in ({"question": "what is a blueprint? explain simply", "level": "auto"},
             {"question": "How does Flask handle a request?", "level": "expert"}):
    a = c.post(f"{BASE}/repos/{rid}/ask", json=body)
    print("\nask ->", a.status_code, "| level:", a.json().get("level"))
    print(a.json().get("answer", a.json())[:600])
    print(a.json().get("sources"))
    time.sleep(5)                              # stay under the free-tier rate limit