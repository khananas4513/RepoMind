from dataclasses import dataclass

STYLES = {
    "beginner": (
        "The user is new to programming or to this codebase. Use plain language. "
        "Define any technical term the first time you use it. Walk through the flow "
        "step by step, one idea per step. A short analogy is welcome. Show only tiny "
        "snippets. End with a one-sentence summary."
    ),
    "intermediate": (
        "The user knows programming basics. Skip fundamentals, but briefly explain "
        "framework-specific concepts. Focus on how the functions connect and why."
    ),
    "expert": (
        "The user is an experienced engineer. Be concise and precise. Focus on design "
        "decisions, edge cases, coupling between modules and trade-offs. Skip basics "
        "and avoid restating what the code obviously does."
    ),
}

BEGINNER_HINTS = ("what is", "what does", "explain", "simpl", "beginner", "eli5",
                  "i don't understand", "new to", "step by step")
EXPERT_HINTS = ("trade-off", "tradeoff", "complexity", "concurren", "thread-safe",
                "race condition", "coupling", "refactor", "invariant", "lifecycle",
                "idempot", "contextvar", "circular", "cyclic")


@dataclass
class UserProfile:
    explicit_level: str | None = None     # if the user picked a level, it always wins
    score: float = 0.5                    # 0 = beginner ... 1 = expert
    questions_seen: int = 0

    def observe(self, question: str) -> None:
        """Update the estimate from one question (exponential moving average)."""
        q = question.lower()
        delta = -0.2 * sum(h in q for h in BEGINNER_HINTS)
        delta += 0.2 * sum(h in q for h in EXPERT_HINTS)
        if len(q.split()) > 25:           # long, detailed questions suggest experience
            delta += 0.1
        q_score = min(1.0, max(0.0, 0.5 + delta))
        self.score = 0.7 * self.score + 0.3 * q_score
        self.questions_seen += 1

    @property
    def level(self) -> str:
        if self.explicit_level:
            return self.explicit_level
        if self.score < 0.42:
            return "beginner"
        if self.score > 0.58:
            return "expert"
        return "intermediate"


def _fmt(paths, limit=4):
    if not paths:
        return "none"
    shown = ", ".join(paths[:limit])
    return shown + (f" (+{len(paths) - limit} more)" if len(paths) > limit else "")


def structure_notes(G, results) -> str:
    """Graph-derived facts about the files the retrieval touched."""
    lines, seen = [], set()
    for _, c in results:
        if c.path in seen or c.path not in G:
            continue
        seen.add(c.path)
        imports = sorted(G.successors(c.path))
        imported_by = sorted(G.predecessors(c.path))
        domain = G.nodes[c.path].get("domain", "?")
        lines.append(f"- {c.path} [{domain}] imports: {_fmt(imports)}; "
                     f"imported by {len(imported_by)} files: {_fmt(imported_by)}")
    return "\n".join(lines) or "(no dependency data for these files)"