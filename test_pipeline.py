from backend.core.pipeline import analyze_repo, impact, ask
from backend.core.personalize import UserProfile

# ---- Part 1: fast, no embeddings, no API key ----
a = analyze_repo("https://github.com/pallets/flask", with_index=False)
print(dict(a.languages), "| graph:", a.graph.number_of_nodes(), "nodes,",
      a.graph.number_of_edges(), "edges | chunks:", len(a.chunks))
print("sample node ids:", list(a.graph.nodes)[:3])

r = impact(a, "src/flask/globals.py")
print("\nIf src/flask/globals.py changes:")
print("  direct importers:", len(r["direct"]), "| total affected:", r["total"],
      "| tests to run:", len(r["tests"]))
print("  e.g.", r["tests"][:3])

b = analyze_repo("https://github.com/gabime/spdlog", with_index=False)
print("\nspdlog languages (headers fixed):", dict(b.languages))

# ---- Part 2: full pipeline with embeddings and the LLM (about 1.5 minutes) ----
print("\nBuilding the full index...")
full = analyze_repo("https://github.com/pallets/flask")
text, sources = ask(full, "How does ctx.py relate to the rest of the codebase?",
                    profile=UserProfile(explicit_level="intermediate"))
print(text)
print("Retrieved:", sources)